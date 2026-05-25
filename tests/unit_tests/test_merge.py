from types import MappingProxyType

import pytest

from confiq._merge import _freeze, deep_merge


def test_scalar_overlay_wins():
    assert deep_merge({"a": 1}, {"a": 2}) == {"a": 2}


def test_missing_key_added():
    assert deep_merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}


def test_nested_dicts_recurse():
    base = {"db": {"host": "old", "port": 5432}}
    overlay = {"db": {"host": "new"}}
    result = deep_merge(base, overlay)
    assert result == {"db": {"host": "new", "port": 5432}}


def test_lists_are_replaced_not_concatenated():
    base = {"hosts": ["a", "b"]}
    overlay = {"hosts": ["c"]}
    result = deep_merge(base, overlay)
    assert result["hosts"] == ["c"]


def test_deep_nested():
    base = {"a": {"b": {"c": 1, "d": 2}}}
    overlay = {"a": {"b": {"c": 99}}}
    result = deep_merge(base, overlay)
    assert result == {"a": {"b": {"c": 99, "d": 2}}}


def test_empty_base():
    assert deep_merge({}, {"x": 1}) == {"x": 1}


def test_empty_overlay():
    assert deep_merge({"x": 1}, {}) == {"x": 1}


def test_mappingproxy_overlay_merges():
    base = {"a": {"b": 1}}
    overlay = MappingProxyType({"a": MappingProxyType({"c": 2})})
    result = deep_merge(base, overlay)
    assert result == {"a": {"b": 1, "c": 2}}


class TestFreeze:
    def test_dict_becomes_mappingproxy(self):
        result = _freeze({"a": 1})
        assert isinstance(result, MappingProxyType)

    def test_list_becomes_tuple(self):
        result = _freeze([1, 2, 3])
        assert result == (1, 2, 3)
        assert isinstance(result, tuple)

    def test_nested_dict(self):
        result = _freeze({"a": {"b": 2}})
        assert isinstance(result["a"], MappingProxyType)

    def test_nested_list(self):
        result = _freeze({"a": [1, 2]})
        assert result["a"] == (1, 2)

    def test_scalar_passthrough(self):
        assert _freeze(42) == 42
        assert _freeze("hello") == "hello"
        assert _freeze(None) is None
