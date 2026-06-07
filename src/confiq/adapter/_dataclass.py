"""Module defining a stdlib dataclass schema adapter for confiq."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from confiq._types import T
from confiq.adapter._schema_adapter import SchemaAdapter


class DataclassAdapter(SchemaAdapter[T]):
    """SchemaAdapter for stdlib @dataclass types (design_d §4.4).

    field_metadata() uses get_type_hints(include_extras=True) to read Annotated
    metadata. This carries PEP 563 / forward-reference fragility; it is
    accepted because it is confined to this adapter.

    validate() uses TypeAdapter(schema).validate_python(merged) (§4.5).
    """

    def __init__(self, schema: type[T]) -> None: ...

    def field_metadata(self) -> Mapping[str, list[Any]]: ...

    def validate(self, data: Mapping[str, Any]) -> T: ...
