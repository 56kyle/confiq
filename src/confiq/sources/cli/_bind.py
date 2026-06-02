"""Module containing shared utilities for CLI framework source adapters used throughout the confiq package."""
from __future__ import annotations

from typing import Any


def _set_nested(d: dict[str, Any], path: str, value: Any) -> None:
    """Set a value at a dotted path in a nested dict, creating intermediate dicts as needed."""
    parts: list[str] = path.split(".")
    node: dict[str, Any] = d
    for part in parts[:-1]:
        if part not in node or not isinstance(node[part], dict):
            node[part] = {}
        node = node[part]
    node[parts[-1]] = value
