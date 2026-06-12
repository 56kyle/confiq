"""Module defining a base class for configuration sources."""

from collections.abc import Mapping
from typing import Any

from typing_extensions import Protocol
from typing_extensions import runtime_checkable

from confiq._types import MergeMode


@runtime_checkable
class Source(Protocol):
    """Read-only base protocol for all configuration sources."""

    @property
    def name(self) -> str:
        ...

    @property
    def mode(self) -> MergeMode:
        ...

    @property
    def profile(self) -> str | None:
        ...


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
