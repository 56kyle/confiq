from __future__ import annotations

import warnings
from collections.abc import Mapping
from typing import Any
from typing import get_type_hints

from confiq._merge import deep_merge
from confiq._snapshot import ResolvedSnapshot
from confiq.errors import ConflictingSourceError
from confiq.schema._meta import field_meta


def resolve(
    fetched: list[tuple[str, Mapping[str, Any]]],
    schema: type | None,
    *,
    strict: bool = True,
) -> ResolvedSnapshot:
    """Merge fetched source pairs and apply schema-level field checks."""
    merged: dict[str, Any] = {}
    provenance: dict[str, str] = {}

    for source_name, mapping in fetched:
        merged = deep_merge(merged, mapping)
        _collect_leaves(mapping, "", provenance, source_name)

    if schema is not None:
        hints = get_type_hints(schema, include_extras=True)

        for field_name, _annotated_type in hints.items():
            field = field_meta(schema, field_name)
            if field is None:
                continue

            lookup_key = field.file_key if field.file_key else field_name
            actual_source = provenance.get(lookup_key)

            if field.sources is not None and actual_source is not None:
                if actual_source not in field.sources:
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
                        stacklevel=2,
                    )
                    merged.pop(field_name, None)
                    continue

            if field.parser is not None and field_name in merged:
                merged[field_name] = field.parser(merged[field_name])

            if field.deprecated is not None and lookup_key in provenance:
                warnings.warn(
                    f"Config field '{field_name}' is deprecated: {field.deprecated}",
                    DeprecationWarning,
                    stacklevel=2,
                )

        if strict:
            schema_keys = set(hints.keys())
            for key in merged:
                if key not in schema_keys:
                    warnings.warn(
                        f"Source key '{key}' is not present in schema '{schema.__name__}' "
                        "and will be ignored.",
                        UserWarning,
                        stacklevel=2,
                    )

    return ResolvedSnapshot(merged=merged, provenance=provenance)


def _collect_leaves(
    mapping: Mapping[str, Any],
    prefix: str,
    provenance: dict[str, str],
    source_name: str,
) -> None:
    for key, value in mapping.items():
        dotted = f"{prefix}.{key}" if prefix else key
        if isinstance(value, Mapping):
            _collect_leaves(value, dotted, provenance, source_name)
        else:
            provenance[dotted] = source_name
