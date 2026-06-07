"""Module defining the primary config resolution logic for the confiq package."""
from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Sequence
from typing import Any

from confiq._schemaless import SchemalessConfig
from confiq._types import T
from confiq.source._source import AsyncSource
from confiq.source._source import Source


def resolve(
    schema: type[T] | None,
    sources: Sequence[Source],
    *,
    profile: str | None = None,
    plugins: tuple[object, ...] = (),
) -> T | SchemalessConfig:
    """Execute the 7-step sync resolver (design_d §6.2).

    Raises ConfiqError immediately if any source implements AsyncSource.
    Steps: profile filter → fetch → merge+provenance → adapter → coerce → validate → return.
    """
    ...


async def resolve_async(
    schema: type[T] | None,
    sources: Sequence[Source | AsyncSource],
    *,
    profile: str | None = None,
    plugins: tuple[object, ...] = (),
) -> T | SchemalessConfig:
    """Same 7 steps; AsyncSources are gathered concurrently via asyncio.gather."""
    ...


def _filter_by_profile(
    sources: Sequence[Source | AsyncSource],
    profile: str | None,
) -> list[Source | AsyncSource]: ...


def _apply_parsers(
    merged: dict[str, Any],
    metadata: Mapping[str, list[Any]],
    provenance: dict[str, str],
) -> dict[str, Any]: ...


def _assert_no_async_sources(sources: Sequence[Source | AsyncSource]) -> None: ...
