"""Module defining a stdlib dataclass schema adapter for confiq."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import TypeAdapter

from confiq._types import FieldAnnotations
from confiq._types import T
from confiq.adapter._path_table import build_path_table
from confiq.adapter._schema_adapter import SchemaAdapter


class DataclassAdapter(SchemaAdapter[T]):
    """SchemaAdapter for stdlib @dataclass types (design_d §4.4).

    field_metadata() reads Annotated metadata via get_type_hints(include_extras=True).
    This carries PEP 563 / forward-reference fragility; it is accepted because it is
    confined to this adapter. validate() uses a TypeAdapter cached on the instance (§4.5).
    """

    masks_secrets: bool = True
    kind: str = "stdlib dataclass"

    def __init__(self, schema: type[T]) -> None:
        self._schema = schema
        self._type_adapter = TypeAdapter(schema)

    def field_metadata(self) -> FieldAnnotations:
        """Returns the schema's dotted-path table read via get_type_hints (ADR 0026)."""
        return build_path_table(self._schema)

    def validate(self, data: Mapping[str, Any]) -> T:
        """Validates and coerces the merged mapping into the declared type via TypeAdapter (§4.5)."""
        return self._type_adapter.validate_python(data)
