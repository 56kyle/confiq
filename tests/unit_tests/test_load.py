"""Unit tests pinning the Stage 5 loading surface (`confiq._load`).

Covers the ResolutionSpec bundle, the spec_with splice, and load()'s dispatch and
guards. The end-to-end resolver behaviour is pinned in the integration suite.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel

from confiq import MemorySource
from confiq import ResolutionSpec
from confiq import load
from confiq import spec_with
from confiq._load import _SPEC_WITH_SOURCE_NAME
from confiq.exceptions import ConfiqError


if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Mapping
    from typing import Any


class SinglePort(BaseModel):
    port: int


class _AsyncOnlySource:
    """Fake async-only source (implements fetch_async but not fetch)."""

    def __init__(self, name: str = "async-only", profile: str | None = None) -> None:
        self.name = name
        self.profile = profile

    async def fetch_async(self) -> Mapping[str, Any]:
        return {}


def test_resolution_spec_is_frozen() -> None:
    spec = ResolutionSpec(SinglePort, (MemorySource({"port": 1}),))

    with pytest.raises(FrozenInstanceError):
        spec.schema = None  # pyright: ignore[reportAttributeAccessIssue]  # asserting the frozen guard fires


def test_resolution_spec_coerces_sources_to_tuple() -> None:
    spec = ResolutionSpec(SinglePort, [MemorySource({"port": 1})])

    assert isinstance(spec.sources, tuple)


def test_resolution_spec_does_not_alias_the_passed_source_list() -> None:
    sources = [MemorySource({"port": 1})]
    spec = ResolutionSpec(SinglePort, sources)

    sources.append(MemorySource({"port": 2}))

    assert len(spec.sources) == 1


def test_resolution_spec_defaults_profile_and_plugins() -> None:
    spec = ResolutionSpec(SinglePort, (MemorySource({"port": 1}),))

    assert spec.profile is None
    assert spec.plugins == ()


def test_resolution_spec_schemaless_leaves_schema_none() -> None:
    spec = ResolutionSpec.schemaless([MemorySource({"port": 1})])

    assert spec.schema is None


def test_resolution_spec_schemaless_coerces_sources_to_tuple() -> None:
    spec = ResolutionSpec.schemaless([MemorySource({"port": 1})])

    assert isinstance(spec.sources, tuple)


def test_resolution_spec_schemaless_carries_profile_and_plugins() -> None:
    plugin = object()
    spec = ResolutionSpec.schemaless([MemorySource({"port": 1})], profile="prod", plugins=(plugin,))

    assert spec.profile == "prod"
    assert spec.plugins == (plugin,)


def test_spec_with_returns_a_new_spec_leaving_the_original_unchanged() -> None:
    base = ResolutionSpec(SinglePort, (MemorySource({"port": 1}),))

    spliced = spec_with(base, {"port": 2})

    assert spliced is not base
    assert len(base.sources) == 1


def test_spec_with_appends_exactly_one_source_at_highest_precedence() -> None:
    base = ResolutionSpec(SinglePort, (MemorySource({"port": 1}, name="base"),))

    spliced = spec_with(base, {"port": 2})

    assert len(spliced.sources) == 2
    assert spliced.sources[-1].name == _SPEC_WITH_SOURCE_NAME


def test_spec_with_appended_source_carries_the_overrides() -> None:
    base = ResolutionSpec(SinglePort, (MemorySource({"port": 1}),))

    spliced = spec_with(base, {"port": 2})

    appended = spliced.sources[-1]
    assert isinstance(appended, MemorySource)
    assert appended.fetch() == {"port": 2}


def test_spec_with_preserves_schema_profile_and_plugins() -> None:
    plugin = object()
    base = ResolutionSpec(SinglePort, (MemorySource({"port": 1}),), profile="prod", plugins=(plugin,))

    spliced = spec_with(base, {"port": 2})

    assert spliced.schema is SinglePort
    assert spliced.profile == "prod"
    assert spliced.plugins == (plugin,)


def test_load_with_spec_form_routes_through_resolve() -> None:
    spec = ResolutionSpec(SinglePort, (MemorySource({"port": 8080}),))

    result = load(spec)

    assert isinstance(result, SinglePort)
    assert result.port == 8080


def test_load_with_convenience_positional_sources_routes_through_resolve() -> None:
    result = load(SinglePort, [MemorySource({"port": 8080})])

    assert isinstance(result, SinglePort)
    assert result.port == 8080


def test_load_with_convenience_keyword_sources_routes_through_resolve() -> None:
    result = load(SinglePort, sources=[MemorySource({"port": 8080})])

    assert isinstance(result, SinglePort)
    assert result.port == 8080


@pytest.mark.parametrize(
    "misuse",
    [
        pytest.param(lambda spec: load(spec, sources=[MemorySource({"port": 2})]), id="sources"),
        pytest.param(lambda spec: load(spec, profile="prod"), id="profile"),  # pyright: ignore[reportCallIssue]  # spec form takes the spec alone; guard under test
        pytest.param(lambda spec: load(spec, plugins=(object(),)), id="plugins"),  # pyright: ignore[reportCallIssue]  # spec form takes the spec alone; guard under test
    ],
)
def test_load_with_spec_and_extra_argument_raises_type_error(
    misuse: Callable[[ResolutionSpec[SinglePort]], object],
) -> None:
    spec = ResolutionSpec(SinglePort, (MemorySource({"port": 1}),))

    with pytest.raises(TypeError):
        misuse(spec)


def test_load_with_convenience_form_missing_sources_raises_type_error_naming_sources() -> None:
    with pytest.raises(TypeError, match="sources"):
        load(SinglePort)  # pyright: ignore[reportArgumentType]  # convenience form requires sources; guard under test


def test_load_with_async_only_source_refuses_pointing_to_load_async() -> None:
    with pytest.raises(ConfiqError) as exc_info:
        load(SinglePort, [_AsyncOnlySource(name="vault")])  # pyright: ignore[reportCallIssue, reportArgumentType]  # async-only source deliberately violates SyncSource to exercise the guard

    message = str(exc_info.value)
    assert "vault" in message
    assert "load_async" in message
