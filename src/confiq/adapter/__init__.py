"""Subpackage defining schema adapters used throughout the confiq package."""

from __future__ import annotations

from confiq.adapter._dataclass import DataclassAdapter
from confiq.adapter._pydantic import PydanticAdapter
from confiq.adapter._schema_adapter import SchemaAdapter
from confiq.adapter._schemaless import SchemalessAdapter
from confiq.adapter._secret_masking import enforce_secret_masking
from confiq.adapter._typeddict import TypedDictAdapter


__all__: list[str] = [
    "DataclassAdapter",
    "PydanticAdapter",
    "SchemaAdapter",
    "SchemalessAdapter",
    "TypedDictAdapter",
    "enforce_secret_masking",
]
