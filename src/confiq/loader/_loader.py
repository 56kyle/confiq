"""Module defining the base for loading configuration data from bytes into mappings."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from typing_extensions import Protocol
from typing_extensions import runtime_checkable


@runtime_checkable
class Loader(Protocol):
    """Base class for loading configuration data from bytes into mappings."""

    suffixes: frozenset[str]

    def parse(self, raw: bytes) -> Mapping[str, Any]:
        """Parses the provided bytes into a mapping."""
        ...


_NON_MAPPING_MESSAGE: str = "top-level must be a mapping"


def ensure_mapping(value: object) -> dict[str, Any]:
    """Return value as a dict, refusing a non-mapping top level (ADR 0041).

    Raises ValueError on a non-mapping so the wrapping source names the file.
    """
    if not isinstance(value, Mapping):
        raise ValueError(f"{_NON_MAPPING_MESSAGE}, got {type(value).__name__}")
    return dict(value)
