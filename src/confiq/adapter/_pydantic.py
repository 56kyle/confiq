"""Module defining a pydantic schema adapter for confiq."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import TypeAdapter

from confiq._types import FieldAnnotations
from confiq._types import T
from confiq.adapter._path_table import build_path_table
from confiq.adapter._schema_adapter import SchemaAdapter


class PydanticAdapter(SchemaAdapter[T]):
    """SchemaAdapter for pydantic BaseModel and pydantic dataclasses (design_d §4.4).

    field_metadata() reads ConfigField from FieldInfo.metadata — the same view the
    pydantic validator uses, avoiding a second get_type_hints() call. validate() uses
    a TypeAdapter cached on the instance (§4.5).
    """

    masks_secrets: bool = True
    kind: str = "pydantic"

    def __init__(self, schema: type[T]) -> None:
        self._schema = schema
        self._type_adapter = TypeAdapter(schema)

    def field_metadata(self) -> FieldAnnotations:
        """Returns the schema's dotted-path table read from pydantic field metadata (ADR 0026)."""
        return build_path_table(self._schema)

    def validate(self, data: Mapping[str, Any]) -> T:
        """Validates and coerces the merged mapping into the declared type via TypeAdapter (§4.5)."""
        return self._type_adapter.validate_python(data)
