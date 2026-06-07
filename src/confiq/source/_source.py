"""Module defining a base class for configuration sources."""

from typing import Any
from typing import Mapping

from typing_extensions import Protocol
from typing_extensions import runtime_checkable

from confiq._types import ListFillBehavior


@runtime_checkable
class Source(Protocol):
    """Attribute-only base protocol for all configuration sources."""
    name: str
    mode: ListFillBehavior
    profile: str | None


@runtime_checkable
class SyncSource(Source, Protocol):
    """A configuration source that delivers data synchronously."""

    def fetch(self) -> Mapping[str, Any]:
        ...


@runtime_checkable
class AsyncSource(Source, Protocol):
    """A configuration source that delivers data asynchronously."""

    async def fetch_async(self) -> Mapping[str, Any]:
        ...
