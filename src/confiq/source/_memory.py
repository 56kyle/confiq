"""Module defining an in-process configuration source for testing."""

from __future__ import annotations

import copy
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
    ) -> None:
        self._data: dict[str, Any] = copy.deepcopy(dict(data))
        self._name = name
        self.profile = profile

    @property
    def name(self) -> str:
        return self._name

    def fetch(self) -> Mapping[str, Any]:
        """Return a deep-copied snapshot so neither caller nor input can corrupt the source."""
        return copy.deepcopy(self._data)
