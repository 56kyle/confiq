from __future__ import annotations

from types import MappingProxyType

from confiq._merge import _freeze
from confiq._merge import deep_merge


def test_scalar_overlay() -> None:
    result = deep_merge({"a": 1}, {"a": 2})
    assert result == {"a": 2}


def test_new_key_added() -> None:
    result = deep_merge({"a": 1}, {"b": 2})
    assert result == {"a": 1, "b": 2}


def test_nested_recursion() -> None:
    base = {"db": {"host": "localhost", "port": 5432}}
    overlay = {"db": {"host": "remotehost"}}
    result = deep_merge(base, overlay)
    assert result == {"db": {"host": "remotehost", "port": 5432}}


def test_list_replacement() -> None:
    result = deep_merge({"items": [1, 2]}, {"items": [3, 4, 5]})
    assert result["items"] == [3, 4, 5]


def test_scalar_over_nested_dict() -> None:
    result = deep_merge({"a": {"b": 1}}, {"a": "flat"})
    assert result == {"a": "flat"}


def test_nested_dict_over_scalar() -> None:
    result = deep_merge({"a": "flat"}, {"a": {"b": 1}})
    assert result == {"a": {"b": 1}}


def test_base_unchanged() -> None:
    base: dict = {"a": {"b": 1}}
    overlay: dict = {"a": {"c": 2}}
    deep_merge(base, overlay)
    assert base == {"a": {"b": 1}}


def test_freeze_dict_to_mapping_proxy() -> None:
    frozen = _freeze({"a": 1})
    assert isinstance(frozen, MappingProxyType)
    assert frozen["a"] == 1


def test_freeze_list_to_tuple() -> None:
    frozen = _freeze([1, 2, 3])
    assert frozen == (1, 2, 3)
    assert isinstance(frozen, tuple)


def test_freeze_nested() -> None:
    frozen = _freeze({"a": [1, {"b": 2}]})
    assert isinstance(frozen, MappingProxyType)
    assert isinstance(frozen["a"], tuple)
    assert isinstance(frozen["a"][1], MappingProxyType)
    assert frozen["a"][1]["b"] == 2
