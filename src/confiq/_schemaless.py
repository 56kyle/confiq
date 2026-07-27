"""Module containing the SchemalessConfig read-only mapping wrapper."""

from __future__ import annotations

from collections.abc import Iterator
from collections.abc import Mapping
from typing import Any
from typing import cast


class SchemalessConfig(Mapping[str, Any]):
    """Read-only mapping that wraps nested mappings recursively (design_d §7.4)."""

    def __init__(self, data: Mapping[str, Any]) -> None:
        self._data = data

    def __getitem__(self, key: str) -> Any:  # pyright: ignore[reportAny]  # §7.4 opt-out: subscript is untyped by design
        value = cast("object", self._data[key])
        if isinstance(value, Mapping):
            return SchemalessConfig(cast("Mapping[str, Any]", value))
        return value

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({dict(self._data)!r})"
