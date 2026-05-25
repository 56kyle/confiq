from __future__ import annotations

from typing import TYPE_CHECKING, Any

from confiq.sources.base import AbstractConfigSource, PRIORITY_DEFAULTS

if TYPE_CHECKING:
    pass


class DefaultsSource(AbstractConfigSource):
    """Emits the schema's default values as the lowest-priority config layer."""

    protocol = "defaults"
    priority = PRIORITY_DEFAULTS

    def __init__(self, adapter: Any = None, *, priority: int | None = None) -> None:
        super().__init__(priority=priority)
        self._adapter = adapter

    def load(self) -> dict[str, Any]:
        if self._adapter is not None and hasattr(self._adapter, "defaults"):
            return self._adapter.defaults()
        return {}
