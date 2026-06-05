"""Module defining a base class for configuration sources."""

from typing import Any
from typing import Mapping

from typing_extensions import Protocol
from typing_extensions import runtime_checkable

from confiq._types import ListFillBehavior


@runtime_checkable
class Source(Protocol):
    """Defines a configuration Source."""
    name: str
    mode: ListFillBehavior
    profile: str | None

    def fetch(self) -> Mapping[str, Any]:
        ...


@runtime_checkable
class AsyncSource(Protocol):
    """Defines an async configuration Source."""
    name: str
    mode: ListFillBehavior
    profile: str | None

    async def fetch_async(self) -> Mapping[str, Any]:
        ...
