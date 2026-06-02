"""Module containing the source-merging and schema-field resolution logic used throughout the confiq package."""
from __future__ import annotations

import warnings
from collections.abc import Mapping
from typing import Any
from typing import TYPE_CHECKING
from typing import get_type_hints

from confiq._merge import deep_merge
from confiq._snapshot import ResolvedSnapshot
from confiq.exceptions import ConflictingSourceError
from confiq.schema._meta import field_meta


if TYPE_CHECKING:
    from confiq.schema._field import ConfigField


def resolve(
    fetched: list[tuple[str, Mapping[str, Any]]],
    schema: type | None,
    *,
    strict: bool = True,
) -> ResolvedSnapshot:
    """Merge fetched source pairs and apply schema-level field checks."""
    merged, provenance = _merge_with_provenance(fetched)
    if schema is not None:
        merged, provenance = _apply_aliases(merged, schema, provenance)
        merged = _enforce_source_restrictions(merged, schema, provenance)
        merged = _apply_parsers(merged, schema)
        _warn_deprecated(merged, schema, provenance)
        if strict:
            _warn_unknown_keys(merged, schema)
    return ResolvedSnapshot(merged=merged, provenance=provenance)


def _merge_with_provenance(
    fetched: list[tuple[str, Mapping[str, Any]]],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Merge all fetched source mappings and build a flat provenance map."""
    merged: dict[str, Any] = {}
    provenance: dict[str, str] = {}
    for source_name, mapping in fetched:
        merged = deep_merge(merged, mapping)
        _record_provenance(mapping, "", provenance, source_name)
    return merged, provenance


def _apply_aliases(
    merged: dict[str, Any],
    schema: type,
    provenance: dict[str, str],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Rename file_key entries in merged and provenance to their Python field names."""
    new_merged: dict[str, Any] = dict(merged)
    new_provenance: dict[str, str] = dict(provenance)
    hints: dict[str, Any] = get_type_hints(schema, include_extras=True)
    for field_name, _annotated_type in hints.items():
        field: ConfigField | None = field_meta(schema, field_name)
        if field is None or not field.file_key or field.file_key == field_name:
            continue
        if field.file_key in new_merged:
            new_merged[field_name] = new_merged.pop(field.file_key)
        if field.file_key in new_provenance:
            new_provenance[field_name] = new_provenance.pop(field.file_key)
    return new_merged, new_provenance


def _enforce_source_restrictions(
    merged: dict[str, Any],
    schema: type,
    provenance: dict[str, str],
) -> dict[str, Any]:
    """Remove fields that were provided by a disallowed source, raising or warning per field config."""
    new_merged: dict[str, Any] = dict(merged)
    hints: dict[str, Any] = get_type_hints(schema, include_extras=True)
    for field_name, _annotated_type in hints.items():
        field: ConfigField | None = field_meta(schema, field_name)
        if field is None or field.sources is None:
            continue
        actual_source: str | None = provenance.get(field_name)
        if actual_source is None or actual_source in field.sources:
            continue
        if field.secret or field.on_source_violation == "raise":
            raise ConflictingSourceError(
                f"Field '{field_name}' was set by source '{actual_source}', "
                f"which is not in the allowed sources {field.sources!r}.",
                field_path=field_name,
                source_name=actual_source,
                allowed_sources=field.sources,
            )
        warnings.warn(
            f"Field '{field_name}' was set by source '{actual_source}', "
            f"which is not in the allowed sources {field.sources!r}. "
            "Skipping value.",
            RuntimeWarning,
            stacklevel=4,
        )
        new_merged.pop(field_name, None)
    return new_merged


def _apply_parsers(
    merged: dict[str, Any],
    schema: type,
) -> dict[str, Any]:
    """Apply each field's parser to its value in merged, if present."""
    new_merged: dict[str, Any] = dict(merged)
    hints: dict[str, Any] = get_type_hints(schema, include_extras=True)
    for field_name, _annotated_type in hints.items():
        field: ConfigField | None = field_meta(schema, field_name)
        if field is None or field.parser is None or field_name not in new_merged:
            continue
        new_merged[field_name] = field.parser(new_merged[field_name])
    return new_merged


def _warn_deprecated(
    merged: dict[str, Any],
    schema: type,
    provenance: dict[str, str],
) -> None:
    """Emit DeprecationWarning for each deprecated field that is present in merged."""
    hints: dict[str, Any] = get_type_hints(schema, include_extras=True)
    for field_name, _annotated_type in hints.items():
        field: ConfigField | None = field_meta(schema, field_name)
        if field is None or field.deprecated is None:
            continue
        if field_name in merged:
            warnings.warn(
                f"Config field '{field_name}' is deprecated: {field.deprecated}",
                DeprecationWarning,
                stacklevel=4,
            )


def _warn_unknown_keys(
    merged: dict[str, Any],
    schema: type,
) -> None:
    """Emit UserWarning for each key in merged that has no corresponding schema field."""
    hints: dict[str, Any] = get_type_hints(schema, include_extras=True)
    schema_keys: set[str] = set(hints.keys())
    for key in merged:
        if key not in schema_keys:
            warnings.warn(
                f"Source key '{key}' is not present in schema '{schema.__name__}' "
                "and will be ignored.",
                UserWarning,
                stacklevel=4,
            )


def _record_provenance(
    mapping: Mapping[str, Any],
    prefix: str,
    provenance: dict[str, str],
    source_name: str,
) -> None:
    for key, value in mapping.items():
        dotted: str = f"{prefix}.{key}" if prefix else key
        if isinstance(value, Mapping):
            _record_provenance(value, dotted, provenance, source_name)
        else:
            provenance[dotted] = source_name
