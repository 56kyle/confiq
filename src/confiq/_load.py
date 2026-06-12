"""Module defining how configuration loading occurs throughout the confiq package."""
from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from typing import Generic
from typing import overload

from confiq._schemaless import SchemalessConfig
from confiq._types import PluginList
from confiq._types import T
from confiq.source._source import Source
from confiq.source._source import SyncSource


@dataclass(frozen=True)
class ResolutionSpec(Generic[T]):
    """Immutable bundle of everything needed to resolve a configuration (design_d §7.1).

    ``sources`` is stored as a tuple (any Sequence passed in is coerced in
    ``__post_init__``) so the frozen spec cannot be mutated through a shared list.
    """

    schema: type[T] | None
    sources: tuple[Source, ...]
    profile: str | None = None
    plugins: PluginList = ()

    def __post_init__(self) -> None: ...

    @classmethod
    def schemaless(
        cls,
        sources: Sequence[Source],
        *,
        profile: str | None = None,
        plugins: PluginList = (),
    ) -> ResolutionSpec[SchemalessConfig]:
        """Build a schemaless spec with the value type solved as SchemalessConfig.

        A bare ResolutionSpec(None, sources) leaves T unsolved for load(spec); this
        factory pins it.
        """
        ...


def spec_with(spec: ResolutionSpec[T], overrides: Mapping[str, Any]) -> ResolutionSpec[T]:
    """Return a new spec with a MemorySource(overrides) appended at highest precedence.

    The "splice one key into an existing source list" operation (design_d §11.2,
    ADR 0028) as explicit data flow; pytest-confiq's layering helpers are sugar over
    this.
    """
    ...


@overload
def load(spec: ResolutionSpec[T], /) -> T: ...
@overload
def load(
    schema: type[T],
    sources: Sequence[SyncSource],
    /,
    *,
    profile: str | None = None,
    plugins: PluginList = (),
) -> T: ...
@overload
def load(
    schema: None,
    sources: Sequence[SyncSource],
    /,
    *,
    profile: str | None = None,
    plugins: PluginList = (),
) -> SchemalessConfig: ...
def load(
    schema: type[T] | ResolutionSpec[T] | None,
    sources: Sequence[SyncSource] | None = None,
    /,
    *,
    profile: str | None = None,
    plugins: PluginList = (),
) -> T | SchemalessConfig:
    """Synchronous load entry point (design_d §7.2).

    Accepts a ResolutionSpec as the sole argument, or the convenience form
    (schema, sources, *, profile, plugins).  Raises ConfiqError if any source
    is an AsyncSource — use load_async() for mixed lists.
    """
    ...


@overload
async def load_async(spec: ResolutionSpec[T], /) -> T: ...
@overload
async def load_async(
    schema: type[T],
    sources: Sequence[Source],
    /,
    *,
    profile: str | None = None,
    plugins: PluginList = (),
) -> T: ...
@overload
async def load_async(
    schema: None,
    sources: Sequence[Source],
    /,
    *,
    profile: str | None = None,
    plugins: PluginList = (),
) -> SchemalessConfig: ...
async def load_async(
    schema: type[T] | ResolutionSpec[T] | None,
    sources: Sequence[Source] | None = None,
    /,
    *,
    profile: str | None = None,
    plugins: PluginList = (),
) -> T | SchemalessConfig:
    """Asynchronous load entry point (design_d §7.3).

    Drives AsyncSources natively (gathered on the running loop); sync Sources
    run inline.
    """
    ...
