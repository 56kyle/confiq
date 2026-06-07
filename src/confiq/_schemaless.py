"""Module containing the SchemalessConfig read-only mapping wrapper."""
from __future__ import annotations

from collections.abc import Iterator
from collections.abc import Mapping
from typing import Any


class SchemalessConfig(Mapping[str, Any]):
    """Read-only mapping that wraps nested dicts recursively."""

    def __init__(self, data: Mapping[str, Any]) -> None: ...

    def __getitem__(self, key: str) -> Any: ...

    def __iter__(self) -> Iterator[str]: ...

    def __len__(self) -> int: ...

    def __repr__(self) -> str: ...
