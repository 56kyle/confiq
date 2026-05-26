"""Base protocol and abstract class for all config sources."""
from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import Any
from typing import ClassVar
from typing import Protocol
from typing import runtime_checkable


JSONDict = dict[str, Any]

PRIORITY_DEFAULTS: int = 0
PRIORITY_FILE: int = 10
PRIORITY_CLOUD: int = 15
PRIORITY_ENV: int = 20
PRIORITY_CLI: int = 30


@runtime_checkable
class ConfigSource(Protocol):
    """Anything that can produce a dict of config values."""

    protocol: ClassVar[str]
    priority: int

    def load(self) -> JSONDict:
        """Return the config values this source provides as a flat or nested dict."""
        ...

    def supports_watch(self) -> bool:
        """Return True if this source can push change notifications."""
        ...

    def watch(self, on_change: Any) -> Any:
        """Begin watching for changes; call `on_change()` on each detected change."""
        ...


class AbstractConfigSource(ABC):
    """Reference implementation, analogous to fsspec.AbstractFileSystem."""

    protocol: ClassVar[str] = "abstract"
    priority: int = PRIORITY_FILE

    def __init__(self, *, priority: int | None = None) -> None:
        """Override `priority` for this instance when `priority` is not None."""
        if priority is not None:
            self.priority = priority

    @abstractmethod
    def load(self) -> JSONDict:
        """Return this source's config values; must be overridden by subclasses."""
        raise NotImplementedError

    def supports_watch(self) -> bool:
        """Returns False; override to enable filesystem or remote watching."""
        return False

    def watch(self, on_change: Any) -> None:
        """No-op; override alongside `supports_watch` to implement watching."""
        return
