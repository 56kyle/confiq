"""Integration tests pinning the assembled Stage 6 async load surface (`confiq._load.load_async`).

These drive load_async() end-to-end through the real async resolver: the sync/async
no-drift check (ADR 0035), dispatch equivalence across call forms, async-only acceptance,
mixed-color precedence, schemaless mode, profile threading, the shared _spec_from_args
guards, and error taxonomy preservation.

No async test plugin is configured; coroutines are driven with asyncio.run() inside sync
tests, mirroring tests/unit_tests/test_context.py (ADR 0013, no thread bridge).
"""

from __future__ import annotations

import asyncio
import copy
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel

from confiq import MemorySource
from confiq import ResolutionSpec
from confiq import SchemalessConfig
from confiq import load
from confiq import load_async
from confiq.exceptions import ConfigValidationError


if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any


class DbConfig(BaseModel):
    host: str
    port: int


class SinglePort(BaseModel):
    port: int


class _AsyncMemorySource:
    """Genuinely async, async-only in-memory source: fetch_async only, no fetch (ADR 0047).

    confiq ships no AsyncSource; this is the test-local driver for the async path.
    """

    def __init__(
        self,
        data: Mapping[str, Any],
        *,
        name: str = "async-memory",
        profile: str | None = None,
    ) -> None:
        self._data: dict[str, Any] = copy.deepcopy(dict(data))
        self.name = name
        self.profile = profile

    async def fetch_async(self) -> Mapping[str, Any]:
        return copy.deepcopy(self._data)


def test_load_async_agrees_with_load_for_all_sync_sources() -> None:
    sources = [
        MemorySource({"host": "localhost", "port": 1}, name="low"),
        MemorySource({"port": 5432}, name="high"),
    ]

    sync_result = load(DbConfig, sources)
    async_result = asyncio.run(load_async(DbConfig, sources))

    assert async_result == sync_result


def test_load_async_with_spec_form_routes_through_resolve_async() -> None:
    spec = ResolutionSpec(SinglePort, (_AsyncMemorySource({"port": 8080}),))

    result = asyncio.run(load_async(spec))

    assert isinstance(result, SinglePort)
    assert result.port == 8080


def test_load_async_with_convenience_positional_sources_routes_through_resolve_async() -> None:
    result = asyncio.run(load_async(SinglePort, [_AsyncMemorySource({"port": 8080})]))

    assert isinstance(result, SinglePort)
    assert result.port == 8080


def test_load_async_with_convenience_keyword_sources_routes_through_resolve_async() -> None:
    result = asyncio.run(load_async(SinglePort, sources=[_AsyncMemorySource({"port": 8080})]))

    assert isinstance(result, SinglePort)
    assert result.port == 8080


def test_load_async_accepts_async_only_source() -> None:
    result = asyncio.run(load_async(SinglePort, [_AsyncMemorySource({"port": 8080}, name="vault")]))

    assert isinstance(result, SinglePort)
    assert result.port == 8080


def test_load_async_with_mixed_sources_lets_highest_precedence_win() -> None:
    low = _AsyncMemorySource({"host": "async-host", "port": 1}, name="async-low")
    high = MemorySource({"port": 5432}, name="sync-high")

    result = asyncio.run(load_async(DbConfig, [low, high]))

    assert isinstance(result, DbConfig)
    assert result.host == "async-host"
    assert result.port == 5432


def test_load_async_with_none_schema_returns_schemaless_config_with_nested_subscript() -> None:
    result = asyncio.run(load_async(None, [_AsyncMemorySource({"a": {"b": 5}})]))

    assert isinstance(result, SchemalessConfig)
    assert result["a"]["b"] == 5


def test_load_async_with_schemaless_spec_returns_schemaless_config_with_nested_subscript() -> None:
    spec = ResolutionSpec.schemaless([_AsyncMemorySource({"a": {"b": 5}})])

    result = asyncio.run(load_async(spec))

    assert isinstance(result, SchemalessConfig)
    assert result["a"]["b"] == 5


def test_load_async_with_matching_profile_includes_profiled_async_source() -> None:
    unprofiled = _AsyncMemorySource({"port": 1}, name="base")
    profiled = _AsyncMemorySource({"port": 99}, name="prod-src", profile="prod")

    result = asyncio.run(load_async(SinglePort, [unprofiled, profiled], profile="prod"))

    assert isinstance(result, SinglePort)
    assert result.port == 99


def test_load_async_with_mismatched_profile_excludes_profiled_async_source() -> None:
    unprofiled = _AsyncMemorySource({"port": 1}, name="base")
    profiled = _AsyncMemorySource({"port": 99}, name="prod-src", profile="prod")

    result = asyncio.run(load_async(SinglePort, [unprofiled, profiled], profile="dev"))

    assert isinstance(result, SinglePort)
    assert result.port == 1


def test_load_async_with_spec_and_extra_argument_raises_type_error() -> None:
    spec = ResolutionSpec(SinglePort, (_AsyncMemorySource({"port": 1}),))

    with pytest.raises(TypeError):
        asyncio.run(load_async(spec, profile="prod"))  # pyright: ignore[reportCallIssue]  # spec form takes the spec alone; shared guard under test


def test_load_async_with_convenience_form_missing_sources_raises_type_error_naming_sources() -> None:
    with pytest.raises(TypeError, match="sources"):
        asyncio.run(load_async(SinglePort))  # pyright: ignore[reportArgumentType]  # convenience form requires sources; shared guard under test


def test_load_async_with_invalid_field_raises_validation_error_naming_field_and_source() -> None:
    source = _AsyncMemorySource({"host": "localhost", "port": "not-a-port"}, name="primary")

    with pytest.raises(ConfigValidationError) as exc_info:
        asyncio.run(load_async(DbConfig, [source]))

    error = exc_info.value
    assert error.field_path == "port"
    assert error.sources == ("primary",)
    assert "primary" in str(error)
