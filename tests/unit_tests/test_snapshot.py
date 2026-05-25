from types import MappingProxyType

import pytest

from confiq._snapshot import ConfigSnapshot


def _make_snap(raw: dict, model=None, version: int = 1) -> ConfigSnapshot:
    from confiq._merge import _freeze
    return ConfigSnapshot(model=model, raw=_freeze(raw), version=version, sources=())


class TestGet:
    def test_top_level_key(self):
        snap = _make_snap({"host": "localhost"})
        assert snap.get("host") == "localhost"

    def test_dotted_path(self):
        snap = _make_snap({"db": {"host": "pg"}})
        assert snap.get("db.host") == "pg"

    def test_deeply_nested(self):
        snap = _make_snap({"a": {"b": {"c": 42}}})
        assert snap.get("a.b.c") == 42

    def test_missing_raises_keyerror_without_default(self):
        snap = _make_snap({})
        with pytest.raises(KeyError):
            snap.get("missing")

    def test_missing_returns_default(self):
        snap = _make_snap({})
        assert snap.get("missing", "fallback") == "fallback"

    def test_cast_applied(self):
        snap = _make_snap({"port": "5432"})
        assert snap.get("port", cast=int) == 5432

    def test_intermediate_missing_uses_default(self):
        snap = _make_snap({"a": 1})
        assert snap.get("a.b.c", "nope") == "nope"


class TestSnapshotFields:
    def test_frozen(self):
        snap = _make_snap({})
        with pytest.raises(Exception):
            snap.version = 99  # type: ignore[misc]

    def test_version_monotonic(self):
        s1 = _make_snap({}, version=1)
        s2 = _make_snap({}, version=2)
        assert s2.version > s1.version
