"""Unit tests pinning the Stage 7 bind step (`confiq._resolve` binding helpers, ADR 0027, 0049).

The bind step maps a binding source's raw parameter names to config paths against the schema
path table. These pin `_resolve_binding` (one raw name → path | None | error) directly, and the
`_bind_sources` seam through a test-local BindingSource that yields RawBindings — the honest way
to exercise binding without standing up a live Click context (that lives in test_cli_sources.py).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel

from confiq import ConfigBind
from confiq._merge import FetchedEntry
from confiq._resolve import ContributedEntry
from confiq._resolve import _bind_sources
from confiq._resolve import _resolve_binding
from confiq.adapter._path_table import build_path_table
from confiq.adapter._path_table import leaf_paths
from confiq.exceptions import AmbiguousBindingError
from confiq.exceptions import IntermediateBindTargetError
from confiq.exceptions import SchemaError
from confiq.exceptions import UnknownBindTargetError
from confiq.source._source import RawBinding


if TYPE_CHECKING:
    from collections.abc import Sequence

    from confiq._types import FieldAnnotations


class Database(BaseModel):
    host: str
    port: int


class AppSchema(BaseModel):
    database: Database
    debug: bool


class Inner(BaseModel):
    b: int


class AmbiguousSchema(BaseModel):
    """A schema where the name 'a_b' dots to two distinct leaves: 'a.b' and 'a_b'."""

    a: Inner
    a_b: int


class _FakeBindingSource:
    """A minimal BindingSource yielding fixed RawBindings (test-local, no Click context)."""

    def __init__(self, bindings: Sequence[RawBinding]) -> None:
        self._bindings = tuple(bindings)
        self.profile: str | None = None

    @property
    def name(self) -> str:
        return "cli:fake"

    def raw_bindings(self) -> Sequence[RawBinding]:
        return self._bindings


@pytest.fixture
def app_metadata() -> FieldAnnotations:
    return build_path_table(AppSchema)


@pytest.fixture
def app_leaves(app_metadata: FieldAnnotations) -> frozenset[str]:
    return leaf_paths(app_metadata)


def test__resolve_binding_with_convention_binds_underscore_name_to_nested_leaf(
    app_leaves: frozenset[str],
    app_metadata: FieldAnnotations,
) -> None:
    binding = RawBinding("database_host", "somewhere", None)

    assert _resolve_binding(binding, app_leaves, app_metadata) == "database.host"


def test__resolve_binding_with_exact_top_level_name_binds(
    app_leaves: frozenset[str],
    app_metadata: FieldAnnotations,
) -> None:
    binding = RawBinding("debug", True, None)

    assert _resolve_binding(binding, app_leaves, app_metadata) == "debug"


def test__resolve_binding_with_explicit_bind_overrides_convention(
    app_leaves: frozenset[str],
    app_metadata: FieldAnnotations,
) -> None:
    binding = RawBinding("database_host", "somewhere", ConfigBind("database.port"))

    assert _resolve_binding(binding, app_leaves, app_metadata) == "database.port"


def test__resolve_binding_with_bind_none_opts_out_even_when_name_matches_leaf(
    app_leaves: frozenset[str],
    app_metadata: FieldAnnotations,
) -> None:
    binding = RawBinding("debug", True, ConfigBind(None))

    assert _resolve_binding(binding, app_leaves, app_metadata) is None


def test__resolve_binding_with_zero_matches_does_not_participate(
    app_leaves: frozenset[str],
    app_metadata: FieldAnnotations,
) -> None:
    binding = RawBinding("verbose", True, None)

    assert _resolve_binding(binding, app_leaves, app_metadata) is None


def test__resolve_binding_with_ambiguous_name_raises_naming_parameter_and_candidates() -> None:
    metadata = build_path_table(AmbiguousSchema)
    leaves = leaf_paths(metadata)
    binding = RawBinding("a_b", 1, None)

    with pytest.raises(AmbiguousBindingError) as exc_info:
        _resolve_binding(binding, leaves, metadata)

    assert exc_info.value.parameter == "a_b"
    assert exc_info.value.candidates == ("a.b", "a_b")


def test__resolve_binding_ambiguity_is_still_catchable_as_schema_error() -> None:
    metadata = build_path_table(AmbiguousSchema)
    leaves = leaf_paths(metadata)
    binding = RawBinding("a_b", 1, None)

    with pytest.raises(SchemaError) as exc_info:
        _resolve_binding(binding, leaves, metadata)

    assert isinstance(exc_info.value, AmbiguousBindingError)


def test__resolve_binding_with_explicit_unknown_path_raises_unknown_bind_target(
    app_leaves: frozenset[str],
    app_metadata: FieldAnnotations,
) -> None:
    binding = RawBinding("whatever", "x", ConfigBind("database.nope"))

    with pytest.raises(UnknownBindTargetError) as exc_info:
        _resolve_binding(binding, app_leaves, app_metadata)

    assert exc_info.value.target == "database.nope"


def test__resolve_binding_with_explicit_intermediate_path_raises_intermediate_bind_target(
    app_leaves: frozenset[str],
    app_metadata: FieldAnnotations,
) -> None:
    binding = RawBinding("whatever", "x", ConfigBind("database"))

    with pytest.raises(IntermediateBindTargetError) as exc_info:
        _resolve_binding(binding, app_leaves, app_metadata)

    assert exc_info.value.target == "database"


def test__bind_sources_rewrites_binding_source_into_nested_config_path_shape(
    app_metadata: FieldAnnotations,
) -> None:
    source = _FakeBindingSource(
        [
            RawBinding("database_host", "localhost", None),
            RawBinding("debug", True, None),
        ],
    )

    entries = _bind_sources([ContributedEntry(source, None)], app_metadata)

    assert entries == [FetchedEntry("cli:fake", {"database": {"host": "localhost"}, "debug": True})]


def test__bind_sources_drops_non_participating_bindings(app_metadata: FieldAnnotations) -> None:
    source = _FakeBindingSource(
        [
            RawBinding("verbose", True, None),
            RawBinding("debug", True, ConfigBind(None)),
        ],
    )

    entries = _bind_sources([ContributedEntry(source, None)], app_metadata)

    assert entries == [FetchedEntry("cli:fake", {})]
