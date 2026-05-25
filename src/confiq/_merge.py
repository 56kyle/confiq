from __future__ import annotations

from types import MappingProxyType
from typing import Any

_MAP = (dict, MappingProxyType)


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Right-wins deep merge. Lists are replaced, not concatenated.

    Mirrors pydantic's deep_update semantics. See ADR 0004.
    """
    out = dict(base)
    for k, v in overlay.items():
        if k in out and isinstance(out[k], _MAP) and isinstance(v, _MAP):
            out[k] = deep_merge(dict(out[k]), dict(v))
        else:
            out[k] = v
    return out


def _freeze(d: Any) -> Any:
    """Deeply-frozen view: dicts → MappingProxyType, lists → tuples."""
    if isinstance(d, dict):
        return MappingProxyType({k: _freeze(v) for k, v in d.items()})
    if isinstance(d, list):
        return tuple(_freeze(x) for x in d)
    return d
