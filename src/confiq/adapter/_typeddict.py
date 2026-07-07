"""Module defining a TypedDict schema adapter for confiq."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from typing import Any

from pydantic import PydanticUserError
from pydantic import TypeAdapter

from confiq._types import FieldAnnotations
from confiq._types import T
from confiq.adapter._path_table import build_path_table
from confiq.adapter._schema_adapter import SchemaAdapter
from confiq.exceptions import SchemaError


_MIN_TYPING_TYPEDDICT_VERSION = (3, 12)


class TypedDictAdapter(SchemaAdapter[T]):
    """SchemaAdapter for TypedDict types (design_d §4.4).

    field_metadata() reads Annotated metadata via get_type_hints(include_extras=True).
    validate() returns the validated dict via a TypeAdapter cached on the instance (§4.5).
    masks_secrets is False: a TypedDict resolves to a plain dict with nowhere to hang a
    masked repr (ADR 0033/0039).
    """

    masks_secrets: bool = False
    kind: str = "TypedDict"

    def __init__(self, schema: type[T]) -> None:
        self._schema = schema
        self._type_adapter = _build_type_adapter(schema)

    def field_metadata(self) -> FieldAnnotations:
        """Returns the schema's dotted-path table read via get_type_hints (ADR 0026)."""
        return build_path_table(self._schema)

    def validate(self, data: Mapping[str, Any]) -> T:
        """Validates and coerces the merged mapping into the declared dict type via TypeAdapter (§4.5)."""
        return self._type_adapter.validate_python(data)


def _build_type_adapter(schema: type[T]) -> TypeAdapter[T]:
    try:
        return TypeAdapter(schema)
    except PydanticUserError as exc:
        schema_name = getattr(schema, "__name__", repr(schema))
        if sys.version_info < _MIN_TYPING_TYPEDDICT_VERSION:
            raise SchemaError(
                f"could not adapt TypedDict schema {schema_name}: use "
                f"typing_extensions.TypedDict instead of typing.TypedDict on Python < 3.12",
            ) from exc
        raise SchemaError(f"could not adapt TypedDict schema {schema_name}") from exc
