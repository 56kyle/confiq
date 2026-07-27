"""Integration tests pinning the Stage 8 ambient proxy (`confiq.LazyConfig` + `_LazyProxy`).

These drive real bind()/load() plus the context.override snapshot overlay (ADR 0031): a
nested read under an override proves the merge is applied through the whole snapshot, not
just the first hop. Async override paths run via asyncio.run inside sync tests, matching the
repo convention (no pytest-asyncio).
"""

from __future__ import annotations

import asyncio
import copy
import re
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel

from confiq import LazyConfig
from confiq import MemorySource
from confiq import ResolutionSpec
from confiq._lazy import _NOT_BOUND_MESSAGE
from confiq._lazy import _UnboundConfigError
from confiq.context import async_override
from confiq.context import override
from confiq.exceptions import ConfigValidationError


if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any

    from confiq.source._source import SyncSource


class DbConfig(BaseModel):
    host: str
    port: int


class AppConfig(BaseModel):
    database: DbConfig
    name: str


_BASE_DATA: dict[str, Any] = {
    "database": {"host": "base-host", "port": 5432},
    "name": "base-name",
}


def _base_spec(*, cli: SyncSource | None = None) -> ResolutionSpec[AppConfig]:
    return ResolutionSpec(AppConfig, [MemorySource(_BASE_DATA)])


def _bound_lazy() -> LazyConfig[AppConfig]:
    lazy: LazyConfig[AppConfig] = LazyConfig(_base_spec)
    lazy.bind()
    return lazy


def test_value_returns_a_stable_proxy_that_does_not_raise_before_bind() -> None:
    lazy: LazyConfig[AppConfig] = LazyConfig(_base_spec)

    first = lazy.value
    second = lazy.value

    assert first is second


def test_deref_before_bind_raises_the_not_bound_error() -> None:
    lazy: LazyConfig[AppConfig] = LazyConfig(_base_spec)
    config = lazy.value

    with pytest.raises(_UnboundConfigError, match=re.escape(_NOT_BOUND_MESSAGE)) as exc_info:
        _ = config.name

    assert isinstance(exc_info.value, AttributeError)


def test_nested_read_after_bind_returns_the_base_value() -> None:
    config = _bound_lazy().value

    assert config.database.host == "base-host"
    assert config.name == "base-name"


def test_nested_read_under_override_reflects_the_override_and_merges_siblings() -> None:
    config = _bound_lazy().value

    with override({"database": {"host": "overridden-host"}}):
        assert config.database.host == "overridden-host"
        assert config.database.port == 5432
        assert config.name == "base-name"


def test_override_is_validated_once_per_install(monkeypatch: pytest.MonkeyPatch) -> None:
    lazy = _bound_lazy()
    config = lazy.value
    calls: list[Mapping[str, Any]] = []
    original = lazy._adapter.validate  # pyright: ignore[reportOptionalMemberAccess]

    def _counting(data: Mapping[str, Any]) -> AppConfig:
        calls.append(data)
        return original(data)  # pyright: ignore[reportAny]

    monkeypatch.setattr(lazy._adapter, "validate", _counting)

    with override({"database": {"host": "overridden-host"}}):
        _ = config.database.host
        _ = config.name

    assert len(calls) == 1


def test_invalid_override_raises_validation_error_naming_the_override() -> None:
    config = _bound_lazy().value

    with override({"database": {"port": "not-a-port"}}), pytest.raises(ConfigValidationError) as exc_info:
        _ = config.database.port

    error = exc_info.value
    assert error.sources == ("override",)
    assert error.field_path == "database.port"


def test_isinstance_forwards_to_the_bound_type_but_identity_does_not() -> None:
    config = _bound_lazy().value

    assert isinstance(config, AppConfig)
    assert type(config) is not AppConfig


def test_reset_clears_the_cache_and_reverts_to_not_bound() -> None:
    lazy = _bound_lazy()
    config = lazy.value

    with override({"database": {"host": "overridden-host"}}):
        _ = config.database.host
    assert lazy._cache

    lazy.reset()

    assert lazy._cache == {}
    with pytest.raises(AttributeError, match=re.escape(_NOT_BOUND_MESSAGE)):
        _ = config.name


def test_failed_rebind_leaves_prior_bound_state_intact() -> None:
    good_spec = ResolutionSpec(AppConfig, [MemorySource(_BASE_DATA)])
    bad_spec = ResolutionSpec(AppConfig, [MemorySource({"database": {"host": "x", "port": "nope"}, "name": "n"})])
    specs = [good_spec, bad_spec]

    def _switching_builder(*, cli: SyncSource | None = None) -> ResolutionSpec[AppConfig]:
        return specs.pop(0)

    lazy: LazyConfig[AppConfig] = LazyConfig(_switching_builder)
    lazy.bind()

    with pytest.raises(ConfigValidationError):
        lazy.bind()

    assert lazy.bound is True
    assert lazy.value.database.host == "base-host"


def test_async_override_flows_through_the_proxy_identically() -> None:
    config = _bound_lazy().value

    async def scenario() -> str:
        async with async_override({"database": {"host": "async-host"}}):
            return config.database.host

    assert asyncio.run(scenario()) == "async-host"


def test_probe_on_unbound_proxy_degrades_but_direct_read_still_raises() -> None:
    sentinel = object()
    config = LazyConfig(_base_spec).value

    assert hasattr(config, "anything") is False
    assert getattr(config, "anything", sentinel) is sentinel
    with pytest.raises(AttributeError, match=re.escape(_NOT_BOUND_MESSAGE)):
        _ = config.name


def test_probe_on_bound_proxy_does_not_mask_the_real_read() -> None:
    config = _bound_lazy().value

    assert hasattr(config, "name") is True
    assert getattr(config, "name", None) == "base-name"


def test_setattr_on_proxy_is_refused_and_leaves_the_bound_read_intact() -> None:
    config = _bound_lazy().value

    with pytest.raises(AttributeError, match="read-only"):
        config.name = "mutated"

    assert config.name == "base-name"


def test_deepcopy_of_proxy_is_refused() -> None:
    bound = _bound_lazy().value
    unbound = LazyConfig(_base_spec).value

    with pytest.raises(TypeError, match="not copyable"):
        copy.deepcopy(bound)
    with pytest.raises(TypeError, match="not copyable"):
        copy.deepcopy(unbound)


def test_copy_of_proxy_is_refused() -> None:
    bound = _bound_lazy().value
    unbound = LazyConfig(_base_spec).value

    with pytest.raises(TypeError, match="not copyable"):
        copy.copy(bound)
    with pytest.raises(TypeError, match="not copyable"):
        copy.copy(unbound)
