"""Module defining how configuration loading occurs throughout the confiq package."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Generic
from typing import overload

from confiq._schemaless import SchemalessConfig
from confiq._types import T
from confiq.source._source import Source
from confiq.source._source import SyncSource


@dataclass(frozen=True)
class ResolutionSpec(Generic[T]):
    """Immutable bundle of everything needed to resolve a configuration (design_d §7.1)."""

    schema: type[T] | None
    sources: Sequence[Source]
    profile: str | None = None
    plugins: tuple[object, ...] = ()


@overload
def load(spec: ResolutionSpec[T]) -> T: ...
@overload
def load(
    schema: type[T],
    sources: Sequence[SyncSource],
    *,
    profile: str | None = None,
    plugins: tuple[object, ...] = (),
) -> T: ...
@overload
def load(
    schema: None,
    sources: Sequence[SyncSource],
    *,
    profile: str | None = None,
    plugins: tuple[object, ...] = (),
) -> SchemalessConfig: ...
def load(
    schema: type[T] | ResolutionSpec[T] | None,
    sources: Sequence[SyncSource] | None = None,
    *,
    profile: str | None = None,
    plugins: tuple[object, ...] = (),
) -> T | SchemalessConfig:
    """Synchronous load entry point (design_d §7.2).

    Accepts a ResolutionSpec as the sole argument, or the convenience form
    (schema, sources, *, profile, plugins).  Raises ConfiqError if any source
    is an AsyncSource — use load_async() for mixed lists.
    """
    ...


@overload
async def load_async(spec: ResolutionSpec[T]) -> T: ...
@overload
async def load_async(
    schema: type[T],
    sources: Sequence[Source],
    *,
    profile: str | None = None,
    plugins: tuple[object, ...] = (),
) -> T: ...
@overload
async def load_async(
    schema: None,
    sources: Sequence[Source],
    *,
    profile: str | None = None,
    plugins: tuple[object, ...] = (),
) -> SchemalessConfig: ...
async def load_async(
    schema: type[T] | ResolutionSpec[T] | None,
    sources: Sequence[Source] | None = None,
    *,
    profile: str | None = None,
    plugins: tuple[object, ...] = (),
) -> T | SchemalessConfig:
    """Asynchronous load entry point (design_d §7.3).

    Drives AsyncSources natively (gathered on the running loop); sync Sources
    run inline.
    """
    ...
