"""Unit tests pinning the Stage 3 in-process source (`confiq.source._memory`)."""

from __future__ import annotations

from confiq.source._memory import MemorySource


def test_memory_source_fetch_returns_the_data() -> None:
    source = MemorySource({"host": "localhost", "db": {"port": 5432}})

    assert source.fetch() == {"host": "localhost", "db": {"port": 5432}}


def test_memory_source_fetch_returns_snapshot_isolated_from_returned_mutation() -> None:
    source = MemorySource({"db": {"port": 5432}})

    snapshot = source.fetch()
    snapshot["db"]["port"] = 9999

    assert source.fetch() == {"db": {"port": 5432}}


def test_memory_source_fetch_isolated_from_top_level_mutation_of_original() -> None:
    original = {"host": "localhost"}
    source = MemorySource(original)

    original["host"] = "changed"

    assert source.fetch() == {"host": "localhost"}


def test_memory_source_fetch_isolated_from_nested_mutation_of_original() -> None:
    original = {"db": {"port": 5432}}
    source = MemorySource(original)

    original["db"]["port"] = 9999

    assert source.fetch() == {"db": {"port": 5432}}


def test_memory_source_exposes_default_name_and_profile() -> None:
    source = MemorySource({})

    assert source.name == "memory"
    assert source.profile is None


def test_memory_source_exposes_custom_name_and_profile() -> None:
    source = MemorySource({}, name="fixtures", profile="test")

    assert source.name == "fixtures"
    assert source.profile == "test"
