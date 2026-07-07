"""Module defining an in-process configuration source for testing."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from confiq.source._base_source import BaseSource


class MemorySource(BaseSource):
    """In-process source for testing (design_d §5.4, §11.2)."""

    def __init__(
        self,
        data: Mapping[str, Any],
        *,
        name: str = "memory",
        profile: str | None = None,
    ) -> None: ...

    @property
    def name(self) -> str: ...

    def fetch(self) -> Mapping[str, Any]: ...
