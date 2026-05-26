"""Config source that wraps a pre-built dict as a config layer."""

from __future__ import annotations

from typing import Any

from confiq.sources.base import PRIORITY_FILE
from confiq.sources.base import AbstractConfigSource


class DictSource(AbstractConfigSource):
    """Wraps a pre-built dict as a config layer; canonical test primitive."""

    protocol = "dict"
    priority = PRIORITY_FILE

    def __init__(self, data: dict[str, Any], *, priority: int | None = None) -> None:
        """Wrap `data`, optionally overriding the default priority."""
        super().__init__(priority=priority)
        self._data = data

    def load(self) -> dict[str, Any]:
        """Return the wrapped dict unchanged."""
        return dict(self._data)
