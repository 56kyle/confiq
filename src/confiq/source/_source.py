"""Module defining a base class for configuration sources."""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from typing import TypeAlias

from typing_extensions import Protocol
from typing_extensions import runtime_checkable

from confiq._cli import ConfigBind


@runtime_checkable
class Source(Protocol):
    """Read-only base protocol for all configuration sources."""

    @property
    def name(self) -> str: ...

    @property
    def profile(self) -> str | None: ...


@runtime_checkable
class SyncSource(Source, Protocol):
    """A configuration source that delivers data synchronously."""

    def fetch(self) -> Mapping[str, Any]: ...


@runtime_checkable
class AsyncSource(Source, Protocol):
    """A configuration source that delivers data asynchronously."""

    async def fetch_async(self) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class RawBinding:
    """A raw CLI parameter awaiting path resolution: external name, value, marker (design_d §6.5, ADR 0049).

    bind is the explicit binding marker. ConfigBind(path) forces a config path,
    ConfigBind(None) opts the parameter out, and None means no marker at all — the resolver
    then applies the name↔path convention against the schema path table (ADR 0027).
    """

    name: str
    value: object
    bind: ConfigBind | None


@runtime_checkable
class BindingSource(Source, Protocol):
    """A source contributing raw external names + binding markers, resolved by the resolver (ADR 0027, 0049).

    A normal source emits config-path data merged directly. A binding source instead surfaces
    raw parameter names whose config paths depend on the schema, so the resolver — which holds
    the path table — maps them during resolution. The resolver detects this capability
    structurally; normal sources do not implement it and are unaffected.
    """

    def raw_bindings(self) -> Sequence[RawBinding]: ...


@runtime_checkable
class AliasedSource(Source, Protocol):
    """A source whose fetch() writes user-declared alias targets the resolver must validate (ADR 0048).

    Env/dotenv aliases translate source-side (schema-blind), but their declared config-path targets
    are validated resolver-side against the path table so a typo'd target fails loudly rather than
    dropping under pydantic extra="ignore". alias_targets exposes those config paths for that check.
    """

    @property
    def alias_targets(self) -> Sequence[str]: ...


# Sources the sync entry points admit: a fetch() source or a binding source, both resolved
# synchronously; excludes AsyncSource, so load()/resolve() still statically reject it (ADR 0049).
SyncCapable: TypeAlias = SyncSource | BindingSource
