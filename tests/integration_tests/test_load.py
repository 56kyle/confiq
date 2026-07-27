"""Integration tests pinning the assembled Stage 5 sync load surface (`confiq._load.load`).

These drive load() end-to-end through the real resolver: dispatch equivalence, precedence,
schemaless, profile threading, the spec_with splice, and error taxonomy preservation.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from confiq import MemorySource
from confiq import ResolutionSpec
from confiq import SchemalessConfig
from confiq import load
from confiq import spec_with
from confiq.exceptions import ConfigValidationError


class DbConfig(BaseModel):
    host: str
    port: int


class SinglePort(BaseModel):
    port: int


def test_load_convenience_and_spec_forms_produce_identical_instances() -> None:
    sources = [MemorySource({"host": "localhost", "port": 5432})]

    convenience = load(DbConfig, sources)
    spec_form = load(ResolutionSpec(DbConfig, sources))

    assert convenience == spec_form


def test_load_with_multiple_sources_lets_highest_precedence_win() -> None:
    low = MemorySource({"port": 1}, name="low")
    high = MemorySource({"port": 2}, name="high")

    result = load(SinglePort, [low, high])

    assert isinstance(result, SinglePort)
    assert result.port == 2


def test_load_with_none_schema_returns_schemaless_config_with_nested_subscript() -> None:
    result = load(None, [MemorySource({"a": {"b": 5}})])

    assert isinstance(result, SchemalessConfig)
    assert result["a"]["b"] == 5


def test_load_with_schemaless_spec_returns_schemaless_config_with_nested_subscript() -> None:
    result = load(ResolutionSpec.schemaless([MemorySource({"a": {"b": 5}})]))

    assert isinstance(result, SchemalessConfig)
    assert result["a"]["b"] == 5


def test_load_with_matching_profile_includes_profiled_source() -> None:
    unprofiled = MemorySource({"port": 1}, name="base")
    profiled = MemorySource({"port": 99}, name="prod-src", profile="prod")

    result = load(SinglePort, [unprofiled, profiled], profile="prod")

    assert isinstance(result, SinglePort)
    assert result.port == 99


def test_load_with_mismatched_profile_excludes_profiled_source() -> None:
    unprofiled = MemorySource({"port": 1}, name="base")
    profiled = MemorySource({"port": 99}, name="prod-src", profile="prod")

    result = load(SinglePort, [unprofiled, profiled], profile="dev")

    assert isinstance(result, SinglePort)
    assert result.port == 1


def test_load_with_spec_with_splice_lets_override_win_over_base_sources() -> None:
    base = ResolutionSpec(SinglePort, (MemorySource({"port": 1}, name="base"),))

    result = load(spec_with(base, {"port": 2}))

    assert isinstance(result, SinglePort)
    assert result.port == 2


def test_load_with_invalid_field_raises_validation_error_naming_field_and_source() -> None:
    source = MemorySource({"host": "localhost", "port": "not-a-port"}, name="primary")

    with pytest.raises(ConfigValidationError) as exc_info:
        load(DbConfig, [source])

    error = exc_info.value
    assert error.field_path == "port"
    assert error.sources == ("primary",)
    assert "primary" in str(error)
