"""Module defining how configuration loading occurs throughout the confiq package."""
from typing import Sequence

from confiq._types import T
from confiq.source import AsyncSource
from confiq.source import Source


def load(schema: type[T], sources: Sequence[Source], *, profile: str | None = None) -> T:
    """Loads a configuration from a given schema and sources."""
    ...


async def load_async(schema: type[T], sources: Sequence[Source | AsyncSource], *, profile: str | None = None) -> T:
    """Asynchronously loads a configuration from a given schema and sources."""
    ...

