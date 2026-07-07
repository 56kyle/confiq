"""Module defining a convenience base class for synchronous configuration sources."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class BaseSource:
    """Convenience base class for synchronous sources (design_d §5.1).

    Supplies a profile=None default so subclasses only need to declare name and
    fetch().
    """

    profile: str | None = None

    @property
    def name(self) -> str: ...

    def fetch(self) -> Mapping[str, Any]: ...
