"""Module defining a convenience base class for synchronous configuration sources."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from confiq._types import ListFillBehavior


class BaseSource:
    """Convenience base class for synchronous sources (design_d §5.1).

    Supplies mode="override" and profile=None defaults so subclasses only need
    to declare name and fetch().
    """

    mode: ListFillBehavior = "override"
    profile: str | None = None

    @property
    def name(self) -> str: ...

    def fetch(self) -> Mapping[str, Any]: ...
