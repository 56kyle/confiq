"""Module containing the ConfigField annotation descriptor used throughout the confiq package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Any
from typing import Literal


if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True)
class ConfigField:
    """Annotation metadata for a config schema field."""
    env: str | None = None
    file_key: str | None = None
    secret: bool = False
    parser: Callable[[str], Any] | None = None
    sources: tuple[str, ...] | None = None
    on_source_violation: Literal["raise", "warn_and_skip"] = "raise"
    description: str | None = None
    deprecated: str | None = None
