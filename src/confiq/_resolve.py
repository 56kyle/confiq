"""Module defining the primary config resolution logic for the confiq package."""
from __future__ import annotations

import asyncio
from collections.abc import Iterator
from collections.abc import Mapping
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from typing import TypeVar
from typing import cast

from pydantic import ValidationError

from confiq._field import ConfigField
from confiq._hookspecs import make_plugin_manager
from confiq._hookspecs import resolve_schema_adapter
from confiq._merge import FetchedEntry
from confiq._merge import ResolvedSnapshot
from confiq._merge import merge_sources
from confiq._schemaless import SchemalessConfig
from confiq._types import FieldAnnotations
from confiq._types import Provenance
from confiq._types import T
from confiq.adapter import enforce_secret_masking
from confiq.adapter._path_table import leaf_paths
from confiq.adapter._schema_adapter import SchemaAdapter
from confiq.exceptions import AmbiguousBindingError
from confiq.exceptions import ConfigValidationError
from confiq.exceptions import ConfiqError
from confiq.exceptions import ErrorContext
from confiq.exceptions import IntermediateBindTargetError
from confiq.exceptions import MissingConfigError
from confiq.exceptions import UnknownBindTargetError
from confiq.exceptions import join_loc
from confiq.source._source import AliasedSource
from confiq.source._source import AsyncSource
from confiq.source._source import BindingSource
from confiq.source._source import RawBinding
from confiq.source._source import Source
from confiq.source._source import SyncCapable
from confiq.source._source import SyncSource


_SourceT = TypeVar("_SourceT", bound=Source)


@dataclass(frozen=True)
class ContributedEntry:
    """A source paired with its fetched output, the fetch→bind boundary (design_d §6.5, ADR 0049).

    data is the fetched config-path mapping for a normal source; None for a BindingSource,
    whose config-path contribution the bind step computes from its raw bindings. Binding needs
    the producing source, not just its name, so this widens the old fetch→merge unit rather
    than collapsing to a FetchedEntry at fetch time.
    """

    source: Source
    data: Mapping[str, Any] | None


def resolve(
    schema: type[T] | None,
    sources: Sequence[SyncCapable],
    *,
    profile: str | None = None,
    plugins: tuple[object, ...] = (),
) -> T | SchemalessConfig:
    """Execute the sync resolver (design_d §6.2, ADR 0049).

    Steps: profile filter → fetch → adapter → bind → merge+provenance → coerce → validate → return.
    """
    _assert_no_async_sources(sources)
    filtered = _filter_by_profile(sources, profile)
    contributed = [_contribute_sync(source) for source in filtered]
    value, _snapshot = _resolve_from_fetched(schema, contributed, plugins)
    return value


async def resolve_async(
    schema: type[T] | None,
    sources: Sequence[Source],
    *,
    profile: str | None = None,
    plugins: tuple[object, ...] = (),
) -> T | SchemalessConfig:
    """Execute the async resolver, sharing the color-agnostic core with resolve() (ADR 0035).

    Only step 2 (fetch) differs by color: AsyncSources are awaited concurrently via
    asyncio.gather while sync sources run inline. Steps 3-7 run through _resolve_from_fetched
    exactly as in resolve(), so the two colors cannot drift (design_d §9.4).
    """
    filtered = _filter_by_profile(sources, profile)
    contributed = await _fetch_all_async(filtered)
    value, _snapshot = _resolve_from_fetched(schema, contributed, plugins)
    return value


def _contribute_sync(source: Source) -> ContributedEntry:
    """Pair a sync source with its fetched data; a binding source contributes via the bind step (ADR 0049).

    A BindingSource's config paths depend on the schema, so no data is fetched here — its
    contribution is computed later from raw_bindings() against the path table. A malformed object
    that is neither shape is refused by name, mirroring the async fetch path.
    """
    if isinstance(source, BindingSource):
        return ContributedEntry(source, None)
    if isinstance(source, SyncSource):
        return ContributedEntry(source, source.fetch())
    raise ConfiqError(
        f"{source.name}: source implements neither fetch() nor raw bindings; "
        f"implement fetch() or expose it as a binding source.",
    )


async def _fetch_all_async(sources: Sequence[Source]) -> list[ContributedEntry]:
    """Fetch every source concurrently, preserving list order for precedence (§14.2 #3, ADR 0047).

    asyncio.gather is unbounded: concurrency bounding is the source's or client's responsibility
    (ADR 0047). Order is preserved regardless of which sources are async, so the downstream merge
    sees the same precedence the caller listed.
    """
    coros = [_fetch_one_async(source) for source in sources]
    return list(await asyncio.gather(*coros))


async def _fetch_one_async(source: Source) -> ContributedEntry:
    """Fetch one source by color: await an AsyncSource, else call a SyncSource inline (ADR 0013).

    Each path prefers its own native fetch when a source implements both: resolve() takes fetch(),
    resolve_async() takes fetch_async(). A sync fetch runs inline rather than in to_thread:
    offloading would drop ContextVars, the exact ADR 0013 hazard. A binding source fetches no
    data (its contribution is bound from raw_bindings() in the shared core), so it is
    color-invariant and skipped here.
    """
    if isinstance(source, BindingSource):
        return ContributedEntry(source, None)
    if isinstance(source, AsyncSource):
        data = await source.fetch_async()
    elif isinstance(source, SyncSource):
        data = source.fetch()
    else:
        raise ConfiqError(
            f"{source.name}: source implements neither fetch() nor fetch_async(); "
            f"implement fetch() or fetch_async().",
        )
    return ContributedEntry(source, data)


def _resolve_from_fetched(
    schema: type[T] | None,
    contributed: list[ContributedEntry],
    plugins: tuple[object, ...],
) -> tuple[T | SchemalessConfig, ResolvedSnapshot]:
    """Run the color-agnostic core: adapt, bind, merge, coerce, validate (ADR 0035, 0049).

    The adapter resolves from schema + plugins only, so it moves ahead of merge to expose the
    path table binding needs. Binding rewrites binding-source contributions into config-path
    shape before merge, so a CLI-bound leaf collides with a file leaf at the same path and
    provenance names the binding source naturally. Returns the validated value alongside the
    raw merged snapshot, retained at this seam for a future explain() projection (ADR 0043).
    """
    manager = make_plugin_manager(plugins)
    adapter = resolve_schema_adapter(manager, schema)
    enforce_secret_masking(adapter)
    metadata = adapter.field_metadata()
    bound = _bind_sources(contributed, metadata)
    snapshot = merge_sources(bound)
    coerced = _apply_parsers(snapshot.merged, metadata, snapshot.provenance)
    value = cast("T | SchemalessConfig", _validate(adapter, coerced, snapshot.provenance))
    return value, snapshot


def _bind_sources(
    contributed: Sequence[ContributedEntry],
    metadata: FieldAnnotations,
) -> list[FetchedEntry]:
    """Rewrite binding-source contributions into config-path shape; validate alias targets (ADR 0048, 0049).

    A binding source's raw names are resolved to config paths against the path table so its
    entry occupies the same leaves as any other source before merge. Non-binding entries keep
    their already-config-path-shaped data unchanged. An aliased source's declared alias targets
    are validated against the path table here (translation itself stays source-side, ADR 0048).
    """
    leaves = leaf_paths(metadata)
    entries: list[FetchedEntry] = []
    for entry in contributed:
        source = entry.source
        if isinstance(source, AliasedSource):
            _validate_alias_targets(source, leaves, metadata)
        if isinstance(source, BindingSource):
            entries.append(_bind_binding_source(source, leaves, metadata))
        else:
            entries.append(FetchedEntry(source.name, entry.data if entry.data is not None else {}))
    return entries


def _validate_alias_targets(
    source: AliasedSource,
    leaves: frozenset[str],
    metadata: FieldAnnotations,
) -> None:
    """Refuse an alias whose declared target is not a schema leaf, naming it (ADR 0048)."""
    for target in source.alias_targets:
        _ = _require_leaf_path(target, leaves, metadata)


def _bind_binding_source(
    source: BindingSource,
    leaves: frozenset[str],
    metadata: FieldAnnotations,
) -> FetchedEntry:
    """Resolve each raw binding to a config path and nest its value into a config-path entry (ADR 0027)."""
    nested: dict[str, Any] = {}
    for binding in source.raw_bindings():
        path = _resolve_binding(binding, leaves, metadata)
        if path is None:
            continue
        _insert_path(nested, path.split("."), binding.value)
    return FetchedEntry(source.name, nested)


def _resolve_binding(
    binding: RawBinding,
    leaves: frozenset[str],
    metadata: FieldAnnotations,
) -> str | None:
    """Resolve a raw binding to a config path, or None when it does not participate (ADR 0027).

    An explicit ConfigBind wins: a non-None path binds after leaf validation, ConfigBind(None)
    opts out. With no marker, the name↔path convention intersects the name's candidate dottings with
    the leaf paths — exactly one binds, more than one raises AmbiguousBindingError naming the
    candidates, none skips (an ordinary flag).
    """
    marker = binding.bind
    if marker is not None:
        if marker.path is None:
            return None
        return _require_leaf_path(marker.path, leaves, metadata)
    matches = sorted(set(_convention_candidates(binding.name)) & leaves)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise AmbiguousBindingError(binding.name, tuple(matches))
    return None


def _convention_candidates(name: str) -> Iterator[str]:
    """Yield every dotted path from replacing a subset of name's underscores with dots (ADR 0027).

    The zero-replacement case (name unchanged) is included, so an exact top-level match
    participates like any other candidate.
    """
    positions = [index for index, char in enumerate(name) if char == "_"]
    for mask in range(1 << len(positions)):
        chars = list(name)
        for bit, position in enumerate(positions):
            if mask & (1 << bit):
                chars[position] = "."
        yield "".join(chars)


def _require_leaf_path(path: str, leaves: frozenset[str], metadata: FieldAnnotations) -> str:
    """Return path if it names a leaf in the path table, else raise SchemaError (ADR 0027, 0048).

    Shared by explicit ConfigBind targets and env/dotenv alias targets: a bind target must name a
    schema leaf. An unknown path and a path landing on an intermediate nested-model node raise
    distinct SchemaError subtypes so callers can tell them apart without parsing the message.
    """
    if path in leaves:
        return path
    if path in metadata:
        raise IntermediateBindTargetError(path)
    raise UnknownBindTargetError(path)


def _insert_path(data: dict[str, Any], parts: Sequence[str], value: object) -> None:
    """Write value at a dotted path, creating intermediate dicts so merge sees config-path shape."""
    current = data
    for part in parts[:-1]:
        existing = current.get(part)
        if not isinstance(existing, dict):
            existing = {}
            current[part] = existing
        current = cast("dict[str, Any]", existing)
    current[parts[-1]] = value


def _filter_by_profile(sources: Sequence[_SourceT], profile: str | None) -> list[_SourceT]:
    """Keep every source when profile is None; else drop only mismatched profiled sources (design_d §6.2 step 1)."""
    if profile is None:
        return list(sources)
    return [source for source in sources if source.profile is None or source.profile == profile]


def _apply_parsers(
    merged: Mapping[str, Any],
    metadata: FieldAnnotations,
    provenance: Provenance,
) -> dict[str, Any]:
    """Coerce str leaves through their ConfigField parser over a deep copy of the merged view.

    The copy keeps snapshot.merged raw so retained provenance stays faithful (ADR 0043).
    Non-str and absent leaves pass through untouched.

    Every parser exception is collected and reported together as one ConfigValidationError
    (ADR 0029), not fail-fast. Coerce precedes validate, so a parser-failed load reports the
    parser errors rather than the downstream validation errors those fields would have caused.
    """
    coerced: dict[str, Any] = deepcopy(dict(merged))
    failures: list[tuple[str, Exception]] = []
    for path, extras in metadata.items():
        field = _config_field(extras)
        if field is None:
            continue
        if field.parser is None:
            continue
        parts = path.split(".")
        present, value = _read_path(coerced, parts)
        if present and isinstance(value, str):
            try:
                parsed: object = field.parser(value)  # pyright: ignore[reportAny]  # user parser returns Any
            except Exception as exc:  # noqa: BLE001  # arbitrary user parser; BaseException still propagates
                failures.append((path, exc))
                continue
            _write_path(coerced, parts, parsed)
    if failures:
        contexts = tuple(
            ErrorContext(field_path=path, sources=_sources_for(provenance, path)) for path, _ in failures
        )
        raise ConfigValidationError(contexts, original=failures[0][1])
    return coerced


def _validate(
    adapter: SchemaAdapter[Any],
    coerced: Mapping[str, Any],
    provenance: Provenance,
) -> object:
    """Validate through the adapter, translating pydantic failures into confiq errors (ADR 0029).

    An all-missing failure raises MissingConfigError; any other failure raises
    ConfigValidationError. Both carry one ErrorContext per pydantic error, annotated with the
    winning source from provenance.
    """
    try:
        return adapter.validate(coerced)  # pyright: ignore[reportAny]  # schema-erased adapter (SchemaAdapter[Any])
    except ValidationError as exc:
        errors = exc.errors()
        contexts = tuple(
            ErrorContext(
                field_path=join_loc(detail["loc"]),
                sources=_sources_for(provenance, join_loc(detail["loc"])),
            )
            for detail in errors
        )
        if all(detail["type"] == "missing" for detail in errors):
            raise MissingConfigError(contexts) from exc
        raise ConfigValidationError(contexts, original=exc) from exc


def _assert_no_async_sources(sources: Sequence[Source]) -> None:
    """Refuse an async-only source in the sync path, naming it and pointing to load_async (design_d §13)."""
    for source in sources:
        if isinstance(source, AsyncSource) and not isinstance(source, SyncSource):
            raise ConfiqError(
                f"{source.name}: source is async-only and cannot be resolved synchronously; "
                f"call load_async() instead.",
            )


def _config_field(extras: list[Any]) -> ConfigField | None:
    """Return the first ConfigField in an Annotated path's extras, or None."""
    for extra in cast("list[object]", extras):
        if isinstance(extra, ConfigField):
            return extra
    return None


def _read_path(data: Mapping[str, Any], parts: Sequence[str]) -> tuple[bool, object]:
    """Return (present, value) for a dotted path; present is False on any missing segment."""
    current: object = data
    for part in parts:
        if not isinstance(current, Mapping):
            return False, None
        mapping = cast("Mapping[str, object]", current)
        if part not in mapping:
            return False, None
        current = mapping[part]
    return True, current


def _write_path(data: dict[str, Any], parts: Sequence[str], value: object) -> None:
    """Set a dotted path already known to be present via a prior _read_path."""
    current: dict[str, object] = cast("dict[str, object]", data)
    for part in parts[:-1]:
        current = cast("dict[str, object]", current[part])
    current[parts[-1]] = value


def _sources_for(provenance: Provenance, field_path: str) -> tuple[str, ...]:
    origin = provenance.get(field_path)
    return () if origin is None else (origin,)
