"""Unit tests pinning the Stage 1 merge interface (`confiq._merge`)."""

from __future__ import annotations

from confiq._merge import FetchedEntry
from confiq._merge import ResolvedSnapshot
from confiq._merge import merge_sources


def test_merge_sources_with_no_sources() -> None:
    snapshot = merge_sources([])

    assert snapshot == ResolvedSnapshot(merged={}, provenance={})


def test_merge_sources_with_single_flat_source() -> None:
    snapshot = merge_sources([FetchedEntry("env", {"host": "localhost", "port": 5432})])

    assert snapshot.merged == {"host": "localhost", "port": 5432}
    assert snapshot.provenance == {"host": "env", "port": "env"}


def test_merge_sources_with_nested_source_records_dotted_leaf_paths() -> None:
    snapshot = merge_sources([FetchedEntry("file", {"db": {"host": "localhost", "port": 5432}})])

    assert snapshot.merged == {"db": {"host": "localhost", "port": 5432}}
    assert snapshot.provenance == {"db.host": "file", "db.port": "file"}


def test_merge_sources_with_nested_source_omits_internal_node_provenance() -> None:
    snapshot = merge_sources([FetchedEntry("file", {"db": {"host": "localhost"}})])

    assert "db" not in snapshot.provenance


def test_merge_sources_with_shared_key_lets_later_source_win() -> None:
    snapshot = merge_sources(
        [
            FetchedEntry("defaults", {"host": "default-host"}),
            FetchedEntry("env", {"host": "env-host"}),
        ],
    )

    assert snapshot.merged == {"host": "env-host"}
    assert snapshot.provenance == {"host": "env"}


def test_merge_sources_with_disjoint_nested_keys_unions_and_attributes_each_leaf() -> None:
    snapshot = merge_sources(
        [
            FetchedEntry("source_a", {"db": {"host": "a-host"}}),
            FetchedEntry("source_b", {"db": {"port": 5432}}),
        ],
    )

    assert snapshot.merged == {"db": {"host": "a-host", "port": 5432}}
    assert snapshot.provenance == {"db.host": "source_a", "db.port": "source_b"}


def test_merge_sources_with_list_value_replaces_wholesale_as_single_leaf() -> None:
    snapshot = merge_sources(
        [
            FetchedEntry("defaults", {"hosts": ["a", "b"]}),
            FetchedEntry("env", {"hosts": ["c"]}),
        ],
    )

    assert snapshot.merged == {"hosts": ["c"]}
    assert snapshot.provenance == {"hosts": "env"}


def test_merge_sources_with_none_overwrites_lower_non_none_value() -> None:
    snapshot = merge_sources(
        [
            FetchedEntry("defaults", {"host": "default-host"}),
            FetchedEntry("env", {"host": None}),
        ],
    )

    assert snapshot.merged == {"host": None}
    assert snapshot.provenance == {"host": "env"}


def test_merge_sources_with_scalar_over_dict_replaces_and_purges_descendants() -> None:
    snapshot = merge_sources(
        [
            FetchedEntry("defaults", {"db": {"host": "localhost", "port": 5432}}),
            FetchedEntry("env", {"db": "postgres://conn-string"}),
        ],
    )

    assert snapshot.merged == {"db": "postgres://conn-string"}
    assert snapshot.provenance == {"db": "env"}


def test_merge_sources_with_dict_over_scalar_replaces_and_attributes_descendants() -> None:
    snapshot = merge_sources(
        [
            FetchedEntry("defaults", {"db": "postgres://conn-string"}),
            FetchedEntry("env", {"db": {"host": "localhost", "port": 5432}}),
        ],
    )

    assert snapshot.merged == {"db": {"host": "localhost", "port": 5432}}
    assert snapshot.provenance == {"db.host": "env", "db.port": "env"}


def test_merge_sources_with_scalar_over_nested_dict_purges_deep_descendants() -> None:
    snapshot = merge_sources(
        [
            FetchedEntry("defaults", {"db": {"host": {"port": 5432}}}),
            FetchedEntry("env", {"db": {"host": "localhost"}}),
        ],
    )

    assert snapshot.merged == {"db": {"host": "localhost"}}
    assert snapshot.provenance == {"db.host": "env"}


def test_merge_sources_with_empty_mapping_over_scalar_drops_key_provenance() -> None:
    snapshot = merge_sources(
        [
            FetchedEntry("defaults", {"db": "scalar"}),
            FetchedEntry("env", {"db": {}}),
        ],
    )

    assert snapshot.merged == {"db": {}}
    assert "db" not in snapshot.provenance


def test_merge_sources_with_three_layers_folds_low_to_high() -> None:
    snapshot = merge_sources(
        [
            FetchedEntry("defaults", {"a": 1, "b": 1, "c": 1}),
            FetchedEntry("file", {"b": 2, "c": 2}),
            FetchedEntry("env", {"c": 3}),
        ],
    )

    assert snapshot.merged == {"a": 1, "b": 2, "c": 3}
    assert snapshot.provenance == {"a": "defaults", "b": "file", "c": "env"}
