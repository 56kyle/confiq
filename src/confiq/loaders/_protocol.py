"""Module containing the Loader protocol used throughout the confiq loaders subpackage."""
from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import Protocol
from typing import runtime_checkable


if TYPE_CHECKING:
    from pathlib import Path


@runtime_checkable
class Loader(Protocol):
    """Attempts to parse a file; returns its dict or None if this format is not handled."""

    def load(self, path: Path) -> dict[str, Any] | None: ...
