"""Module containing the shared schema path-table builder for the confiq adapter layer."""

from __future__ import annotations

from collections.abc import Iterator
from collections.abc import Mapping
from typing import Annotated
from typing import Any
from typing import cast
from typing import get_args
from typing import get_origin
from typing import get_type_hints

from pydantic.dataclasses import is_pydantic_dataclass
from pydantic.fields import FieldInfo
from typing_extensions import NotRequired
from typing_extensions import Required

from confiq._types import FieldAnnotations
from confiq.adapter._kinds import is_base_model
from confiq.adapter._kinds import is_supported_nested_kind
from confiq.exceptions import SchemaError


def leaf_paths(table: FieldAnnotations) -> frozenset[str]:
    """Return the path-table keys with no descendant key: the bindable leaves (ADR 0026, 0027).

    Intermediate nested-model nodes are present in the table but are dotted prefixes of deeper
    keys, so they are excluded; only true leaves are bindable by CLI name convention or an
    explicit ConfigBind target.
    """
    keys: set[str] = set(table)
    return frozenset(
        key for key in keys if not any(other != key and other.startswith(f"{key}.") for other in keys)
    )


def build_path_table(schema: type[Any]) -> FieldAnnotations:
    """Builds the dotted-path table for a schema, recursing through nested schema kinds (ADR 0026).

    Keys are dotted paths from the schema root, including intermediate nested-model nodes;
    values are the list of Annotated extras for that path (empty when the field is not
    Annotated). Recursion stops at scalars, collections, and unions — those contribute a
    single leaf entry and no per-element paths. Each nested type is dispatched by its own
    kind, so a pydantic model nesting a stdlib dataclass reads each subtree correctly.
    """
    table: dict[str, list[Any]] = {}
    _walk(schema, "", table)
    return table


def _walk(schema: object, prefix: str, table: dict[str, list[Any]]) -> None:
    for name, field_type, extras in _read_fields(schema):
        path: str = f"{prefix}.{name}" if prefix else name
        table[path] = extras
        if is_supported_nested_kind(field_type):
            _walk(field_type, path, table)


def _read_fields(schema: object) -> Iterator[tuple[str, object, list[Any]]]:
    if is_base_model(schema):
        yield from _read_field_infos(schema.model_fields)
    elif isinstance(schema, type) and is_pydantic_dataclass(schema):
        yield from _read_field_infos(schema.__pydantic_fields__)
    else:
        yield from _read_type_hint_fields(schema)


def _read_field_infos(fields: Mapping[str, FieldInfo]) -> Iterator[tuple[str, object, list[Any]]]:
    for name, info in fields.items():
        yield name, info.annotation, list(info.metadata)


def _read_type_hint_fields(schema: object) -> Iterator[tuple[str, object, list[Any]]]:
    try:
        hints: dict[str, object] = get_type_hints(schema, include_extras=True)
    except NameError as exc:
        schema_name: str = getattr(schema, "__name__", repr(schema))
        raise SchemaError(
            f"could not resolve type hints for schema {schema_name}: unresolved forward reference {exc.name!r}",
        ) from exc
    for name, hint in hints.items():
        field_type, extras = _unwrap_field_type(hint)
        yield name, field_type, extras


def _unwrap_field_type(hint: object) -> tuple[object, list[Any]]:
    """Strips Annotated (collecting extras) and Required/NotRequired wrappers in any order."""
    extras: list[Any] = []
    while True:
        origin: object = get_origin(hint)
        hint: object
        if origin is Annotated:
            args: tuple[object, ...] = get_args(hint)
            extras: list[Any] = list(args[1:]) + extras
            hint: object = args[0]
        elif origin is Required or origin is NotRequired:
            hint: object = cast("object", get_args(hint)[0])
        else:
            return hint, extras
