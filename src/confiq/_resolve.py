"""Module defining the primary config resolution logic for the confiq package."""
from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Sequence
from copy import deepcopy
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
from confiq.adapter._schema_adapter import SchemaAdapter
from confiq.exceptions import ConfigValidationError
from confiq.exceptions import ConfiqError
from confiq.exceptions import ErrorContext
from confiq.exceptions import MissingConfigError
from confiq.exceptions import SchemaError
from confiq.source._source import AsyncSource
from confiq.source._source import Source
from confiq.source._source import SyncSource


_SourceT = TypeVar("_SourceT", bound=Source)


def resolve(
    schema: type[T] | None,
    sources: Sequence[SyncSource],
    *,
    profile: str | None = None,
    plugins: tuple[object, ...] = (),
) -> T | SchemalessConfig:
    """Execute the 7-step sync resolver (design_d §6.2).

    Steps: profile filter → fetch → merge+provenance → adapter → coerce → validate → return.
    """
    _assert_no_async_sources(sources)
    filtered = _filter_by_profile(sources, profile)
    fetched = [FetchedEntry(source.name, source.fetch()) for source in filtered]
    value, _snapshot = _resolve_from_fetched(schema, fetched, plugins)
    return value


async def resolve_async(
    schema: type[T] | None,
    sources: Sequence[Source],
    *,
    profile: str | None = None,
    plugins: tuple[object, ...] = (),
) -> T | SchemalessConfig:
    """Same 7 steps; AsyncSources are gathered concurrently via asyncio.gather."""
    ...


def _resolve_from_fetched(
    schema: type[T] | None,
    fetched: list[FetchedEntry],
    plugins: tuple[object, ...],
) -> tuple[T | SchemalessConfig, ResolvedSnapshot]:
    """Run the color-agnostic core (steps 3-7): merge, adapt, coerce, validate (ADR 0035).

    Returns the validated value alongside the raw merged snapshot, which is retained at
    this seam for a future explain() projection (ADR 0043).
    """
    snapshot = merge_sources(fetched)
    manager = make_plugin_manager(plugins)
    adapter = resolve_schema_adapter(manager, schema)
    enforce_secret_masking(adapter)
    metadata = adapter.field_metadata()
    coerced = _apply_parsers(snapshot.merged, metadata, snapshot.provenance)
    value = cast("T | SchemalessConfig", _validate(adapter, coerced, snapshot.provenance))
    return value, snapshot


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
    A populated ConfigField(env=...) is refused here; env override lands with ConfigBind in
    a later stage (ADR 0044). Non-str and absent leaves pass through untouched.

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
        if field.env is not None:
            raise SchemaError(
                f"{path}: ConfigField(env=...) per-field environment override is not yet "
                f"supported; it lands with CLI binding (ConfigBind) in a later stage. Remove "
                f"env= or set the value via the source's naming convention.",
            )
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
                field_path=_join_loc(detail["loc"]),
                sources=_sources_for(provenance, _join_loc(detail["loc"])),
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


def _join_loc(loc: Sequence[str | int]) -> str:
    return ".".join(str(part) for part in loc)


def _sources_for(provenance: Provenance, field_path: str) -> tuple[str, ...]:
    origin = provenance.get(field_path)
    return () if origin is None else (origin,)
