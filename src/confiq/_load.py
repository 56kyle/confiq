"""Module defining how configuration loading occurs throughout the confiq package."""
from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import replace
from typing import Any
from typing import Generic
from typing import cast
from typing import overload

from confiq._resolve import resolve
from confiq._resolve import resolve_async
from confiq._schemaless import SchemalessConfig
from confiq._types import PluginList
from confiq._types import T
from confiq.source._memory import MemorySource
from confiq.source._source import Source
from confiq.source._source import SyncCapable


_SPEC_WITH_SOURCE_NAME = "spec_with"


@dataclass(frozen=True)
class ResolutionSpec(Generic[T]):
    """Immutable bundle of everything needed to resolve a configuration (design_d §7.1).

    ``sources`` is accepted as any Sequence and stored immutably as a tuple (coerced in
    ``__post_init__``) so the frozen spec cannot be mutated through a shared list.
    """

    schema: type[T] | None
    sources: Sequence[Source]
    profile: str | None = None
    plugins: PluginList = ()

    def __post_init__(self) -> None:
        """Store sources as a tuple so a frozen spec cannot be mutated through a shared list."""
        object.__setattr__(self, "sources", tuple(self.sources))

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
        return cast(
            "ResolutionSpec[SchemalessConfig]",
            cls(None, sources, profile, plugins),
        )


def spec_with(spec: ResolutionSpec[T], overrides: Mapping[str, Any]) -> ResolutionSpec[T]:
    """Return a new spec with a MemorySource(overrides) appended at highest precedence.

    The "splice one key into an existing source list" operation (design_d §11.2,
    ADR 0028) as explicit data flow; pytest-confiq's layering helpers are sugar over
    this.
    """
    return replace(spec, sources=(*spec.sources, MemorySource(overrides, name=_SPEC_WITH_SOURCE_NAME)))


@overload
def load(spec: ResolutionSpec[T], /) -> T: ...
@overload
def load(
    schema: type[T],
    sources: Sequence[SyncCapable],
    *,
    profile: str | None = None,
    plugins: PluginList = (),
) -> T: ...
@overload
def load(
    schema: None,
    sources: Sequence[SyncCapable],
    *,
    profile: str | None = None,
    plugins: PluginList = (),
) -> SchemalessConfig: ...
def load(
    schema: type[T] | ResolutionSpec[T] | None,
    sources: Sequence[SyncCapable] | None = None,
    *,
    profile: str | None = None,
    plugins: PluginList = (),
) -> T | SchemalessConfig:
    """Synchronous load entry point (design_d §7.2).

    Accepts a ResolutionSpec as the sole argument, or the convenience form
    (schema, sources, *, profile, plugins).  Raises ConfiqError if any source
    is an AsyncSource — use load_async() for mixed lists.  Propagates
    ConfigValidationError / MissingConfigError from resolve() on invalid or missing config.
    """
    spec = _spec_from_args(schema, sources, profile, plugins)
    return resolve(
        spec.schema,
        cast("Sequence[SyncCapable]", spec.sources),
        profile=spec.profile,
        plugins=spec.plugins,
    )


def _spec_from_args(
    schema: type[T] | ResolutionSpec[T] | None,
    sources: Sequence[Source] | None,
    profile: str | None,
    plugins: PluginList,
) -> ResolutionSpec[T]:
    """Build the ResolutionSpec for either load entry point (design_d §7.1).

    The spec form takes the spec alone; the convenience form requires sources. This is the
    color-agnostic dispatch shared by load() and load_async(); the async-only rejection lives
    in resolve(), not here (ADR 0035 corollary 2).
    """
    if isinstance(schema, ResolutionSpec):
        if sources is not None or profile is not None or plugins != ():
            raise TypeError(
                "the spec form takes the spec alone; pass sources/profile/plugins through "
                "the ResolutionSpec, or use the convenience form (schema, sources, ...).",
            )
        return schema
    if sources is None:
        raise TypeError("the convenience form requires sources.")
    return ResolutionSpec(schema, sources, profile, plugins)


@overload
async def load_async(spec: ResolutionSpec[T], /) -> T: ...
@overload
async def load_async(
    schema: type[T],
    sources: Sequence[Source],
    *,
    profile: str | None = None,
    plugins: PluginList = (),
) -> T: ...
@overload
async def load_async(
    schema: None,
    sources: Sequence[Source],
    *,
    profile: str | None = None,
    plugins: PluginList = (),
) -> SchemalessConfig: ...
async def load_async(
    schema: type[T] | ResolutionSpec[T] | None,
    sources: Sequence[Source] | None = None,
    *,
    profile: str | None = None,
    plugins: PluginList = (),
) -> T | SchemalessConfig:
    """Asynchronous load entry point (design_d §7.3).

    Accepts a ResolutionSpec as the sole argument, or the convenience form
    (schema, sources, *, profile, plugins).  Drives AsyncSources natively
    (gathered on the running loop) and runs sync Sources inline; unlike load(),
    async-only sources are accepted rather than rejected.  Propagates
    ConfigValidationError / MissingConfigError from resolve_async() on invalid or missing config.
    """
    spec = _spec_from_args(schema, sources, profile, plugins)
    return await resolve_async(
        spec.schema,
        spec.sources,
        profile=spec.profile,
        plugins=spec.plugins,
    )
