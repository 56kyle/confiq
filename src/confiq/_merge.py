"""Module containing deep-merge and immutable-freeze utilities used throughout the confiq package."""
from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any


def deep_merge(base: dict, overlay: Mapping) -> dict:  # type: ignore[type-arg]
    result: dict[str, Any] = dict(base)
    for key, overlay_value in overlay.items():
        base_value: Any = result.get(key)
        if isinstance(base_value, Mapping) and isinstance(overlay_value, Mapping):
            result[key] = deep_merge(dict(base_value), overlay_value)
        else:
            result[key] = overlay_value
    return result


def _freeze(obj: Any) -> Any:
    if isinstance(obj, dict):
        return MappingProxyType({k: _freeze(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return tuple(_freeze(item) for item in obj)
    return obj
