from __future__ import annotations

import pytest

from confiq._snapshot import ResolvedSnapshot


def test_frozen() -> None:
    snap = ResolvedSnapshot(merged={}, provenance={})
    with pytest.raises(Exception):
        snap.merged = {}  # type: ignore[misc]


def test_holds_provenance() -> None:
    snap = ResolvedSnapshot(merged={"host": "pg"}, provenance={"host": "env"})
    assert snap.provenance["host"] == "env"


def test_holds_merged() -> None:
    snap = ResolvedSnapshot(merged={"host": "pg", "port": 5432}, provenance={})
    assert snap.merged == {"host": "pg", "port": 5432}


def test_empty_snapshot() -> None:
    snap = ResolvedSnapshot(merged={}, provenance={})
    assert snap.merged == {}
    assert snap.provenance == {}


def test_provenance_dotted_key() -> None:
    snap = ResolvedSnapshot(
        merged={"database": {"host": "pg"}},
        provenance={"database.host": "file"},
    )
    assert snap.provenance["database.host"] == "file"
