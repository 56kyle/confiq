"""Module defining the schemaless adapter for confiq."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from confiq._schemaless import SchemalessConfig
from confiq._types import FieldAnnotations


class SchemalessAdapter:
    """SchemaAdapter selected when schema=None (design_d §7.4).

    Deliberately asymmetric with the schema'd adapters — it holds no schema and takes no
    constructor argument — yet satisfies SchemaAdapter[SchemalessConfig] structurally.
    masks_secrets is False, but with no fields the refusal is structurally unreachable
    (ADR 0033/0038).
    """

    masks_secrets: bool = False
    kind: str = "schemaless"

    def field_metadata(self) -> FieldAnnotations:
        """Returns an empty path table; schemaless mode has no fixed fields (§7.4)."""
        return {}

    def validate(self, data: Mapping[str, Any]) -> SchemalessConfig:
        """Wraps the merged mapping in a read-only SchemalessConfig (§7.4)."""
        return SchemalessConfig(data)
