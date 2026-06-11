"""Module defining the schemaless adapter for confiq."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from confiq._schemaless import SchemalessConfig
from confiq._types import FieldAnnotations


class SchemalessAdapter:
    """SchemaAdapter selected when schema=None (design_d §7.4).

    field_metadata() returns an empty mapping.
    validate() wraps the merged dict in SchemalessConfig.
    """

    def field_metadata(self) -> FieldAnnotations: ...

    def validate(self, data: Mapping[str, Any]) -> SchemalessConfig: ...
