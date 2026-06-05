"""Module defining per field configuration metadata."""

from dataclasses import dataclass
from typing import Any
from typing import Callable


@dataclass(frozen=True)
class ConfigField:
    """Data structure used for tracking a configuration field's metadata."""
    env: str | None = None
    secret: bool = False
    parser: Callable[[str], Any] | None = None
