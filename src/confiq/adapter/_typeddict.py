"""Module defining a TypedDict schema adapter for confiq."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from confiq._types import FieldAnnotations
from confiq._types import T
from confiq.adapter._schema_adapter import SchemaAdapter


class TypedDictAdapter(SchemaAdapter[T]):
    """SchemaAdapter for TypedDict types (design_d §4.4).

    field_metadata() uses get_type_hints(include_extras=True).
    validate() uses TypeAdapter(schema).validate_python(merged) (§4.5).
    """

    def __init__(self, schema: type[T]) -> None: ...

    def field_metadata(self) -> FieldAnnotations: ...

    def validate(self, data: Mapping[str, Any]) -> T: ...
