"""Module containing the Source and AsyncSource protocols used throughout the confiq package."""

from __future__ import annotations

from typing import Any
from typing import Mapping
from typing import Protocol
from typing import runtime_checkable


@runtime_checkable
class Source(Protocol):
    name: str

    def fetch(self) -> Mapping[str, Any]: ...


@runtime_checkable
class AsyncSource(Protocol):
    name: str

    async def fetch(self) -> Mapping[str, Any]: ...
