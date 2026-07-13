"""Unit tests pinning the Stage 4 resolver helpers (`confiq._resolve`)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from confiq import MemorySource
from confiq._field import ConfigField
from confiq._resolve import _apply_parsers
from confiq._resolve import _assert_no_async_sources
from confiq._resolve import _filter_by_profile
from confiq.exceptions import ConfigValidationError
from confiq.exceptions import ConfiqError


if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any


class _AsyncOnlySource:
    """Fake source implementing only the async fetch (an AsyncSource that is not a SyncSource)."""

    def __init__(self, name: str = "async-only", profile: str | None = None) -> None:
        self.name = name
        self.profile = profile

    async def fetch_async(self) -> Mapping[str, Any]:
        return {}


class _DualSource:
    """Fake source implementing both fetch and fetch_async (async guard must let it pass)."""

    def __init__(self, name: str = "dual", profile: str | None = None) -> None:
        self.name = name
        self.profile = profile

    def fetch(self) -> Mapping[str, Any]:
        return {}

    async def fetch_async(self) -> Mapping[str, Any]:
        return {}


def test__filter_by_profile_with_none_keeps_all_including_profiled() -> None:
    sources = [
        MemorySource({}, name="plain"),
        MemorySource({}, name="prod-scoped", profile="prod"),
        MemorySource({}, name="dev-scoped", profile="dev"),
    ]

    assert _filter_by_profile(sources, None) == sources


def test__filter_by_profile_with_profile_keeps_unset_and_matching_drops_mismatched() -> None:
    unset = MemorySource({}, name="unset")
    matching = MemorySource({}, name="matching", profile="prod")
    mismatched = MemorySource({}, name="mismatched", profile="dev")

    assert _filter_by_profile([unset, matching, mismatched], "prod") == [unset, matching]


def test__apply_parsers_with_str_leaf_coerces_through_parser() -> None:
    coerced = _apply_parsers({"port": "8080"}, {"port": [ConfigField(parser=int)]}, {})

    assert coerced == {"port": 8080}


def test__apply_parsers_with_non_str_leaf_passes_through_untouched() -> None:
    coerced = _apply_parsers({"port": 8080}, {"port": [ConfigField(parser=int)]}, {})

    assert coerced == {"port": 8080}


def test__apply_parsers_with_absent_path_is_skipped() -> None:
    coerced = _apply_parsers({}, {"port": [ConfigField(parser=int)]}, {})

    assert coerced == {}


def test__apply_parsers_with_nested_path_coerces_leaf() -> None:
    coerced = _apply_parsers({"db": {"port": "5432"}}, {"db.port": [ConfigField(parser=int)]}, {})

    assert coerced == {"db": {"port": 5432}}


def test__apply_parsers_does_not_mutate_input_mapping() -> None:
    merged = {"db": {"port": "5432"}}

    _apply_parsers(merged, {"db.port": [ConfigField(parser=int)]}, {})

    assert merged == {"db": {"port": "5432"}}


def test__apply_parsers_with_raising_parser_raises_validation_error_with_provenance() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        _apply_parsers(
            {"db": {"port": "notanint"}},
            {"db.port": [ConfigField(parser=int)]},
            {"db.port": "primary"},
        )

    error = exc_info.value
    assert error.field_path == "db.port"
    assert error.sources == ("primary",)
    assert isinstance(error.original, ValueError)


def test__assert_no_async_sources_with_sync_sources_passes_silently() -> None:
    _assert_no_async_sources([MemorySource({}, name="a"), _DualSource()])


def test__assert_no_async_sources_with_async_only_source_raises_naming_source_and_load_async() -> None:
    with pytest.raises(ConfiqError) as exc_info:
        _assert_no_async_sources([_AsyncOnlySource(name="vault")])

    message = str(exc_info.value)
    assert "vault" in message
    assert "load_async" in message


def test__assert_no_async_sources_with_dual_source_does_not_raise() -> None:
    _assert_no_async_sources([_DualSource(name="dual")])
