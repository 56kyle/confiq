from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Protocol, runtime_checkable

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

    def load(self) -> JSONDict: ...
    def supports_watch(self) -> bool: ...
    def watch(self, on_change: Any) -> Any: ...


class AbstractConfigSource(ABC):
    """Reference implementation, analogous to fsspec.AbstractFileSystem."""

    protocol: ClassVar[str] = "abstract"
    priority: int = PRIORITY_FILE

    def __init__(self, *, priority: int | None = None) -> None:
        if priority is not None:
            self.priority = priority

    @abstractmethod
    def load(self) -> JSONDict:
        raise NotImplementedError

    def supports_watch(self) -> bool:
        return False

    def watch(self, on_change: Any) -> None:
        return None
