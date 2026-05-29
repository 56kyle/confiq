from __future__ import annotations

from typing import Any


class MemorySource:
    def __init__(self, data: dict[str, Any], *, name: str = "memory") -> None:
        self.name: str = name
        self._data: dict[str, Any] = dict(data)

    def fetch(self) -> dict[str, Any]:
        return self._data
