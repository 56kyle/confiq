"""Unit tests pinning the Stage 2 schema adapters (`confiq.adapter._pydantic`/`_dataclass`/`_typeddict`/`_schemaless`)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from dataclasses import is_dataclass
from typing import TYPE_CHECKING
from typing import TypedDict

import pytest
import typing_extensions
from pydantic import BaseModel
from pydantic import ValidationError

from confiq._schemaless import SchemalessConfig
from confiq.adapter._dataclass import DataclassAdapter
from confiq.adapter._path_table import build_path_table
from confiq.adapter._pydantic import PydanticAdapter
from confiq.adapter._schemaless import SchemalessAdapter
from confiq.adapter._typeddict import TypedDictAdapter
from confiq.exceptions import SchemaError


if TYPE_CHECKING:
    from confiq.adapter._schema_adapter import SchemaAdapter


class PydanticNested(BaseModel):
    host: str


class PydanticSchema(BaseModel):
    value: int
    nested: PydanticNested


@dataclass
class DataclassNested:
    host: str


@dataclass
class DataclassSchema:
    value: int
    nested: DataclassNested


class TypedDictNested(typing_extensions.TypedDict):
    host: str


class TypedDictSchema(typing_extensions.TypedDict):
    value: int
    nested: TypedDictNested


SCHEMAD_ADAPTERS = [
    pytest.param(PydanticAdapter(PydanticSchema), PydanticSchema, id="pydantic"),
    pytest.param(DataclassAdapter(DataclassSchema), DataclassSchema, id="stdlib dataclass"),
    pytest.param(TypedDictAdapter(TypedDictSchema), TypedDictSchema, id="TypedDict"),
]


@pytest.mark.parametrize(("adapter", "schema"), SCHEMAD_ADAPTERS)
def test_field_metadata_delegates_to_build_path_table(adapter: SchemaAdapter[object], schema: type[object]) -> None:
    assert adapter.field_metadata() == build_path_table(schema)


def test_field_metadata_with_schemaless_is_empty() -> None:
    assert SchemalessAdapter().field_metadata() == {}


def test_validate_with_pydantic_returns_model_instance() -> None:
    result = PydanticAdapter(PydanticSchema).validate({"value": 1, "nested": {"host": "localhost"}})

    assert isinstance(result, PydanticSchema)
    assert result.value == 1
    assert result.nested.host == "localhost"


def test_validate_with_dataclass_returns_dataclass_instance() -> None:
    result = DataclassAdapter(DataclassSchema).validate({"value": 1, "nested": {"host": "localhost"}})

    assert isinstance(result, DataclassSchema)
    assert is_dataclass(result)
    assert result.value == 1
    assert result.nested.host == "localhost"


def test_validate_with_typeddict_returns_plain_dict() -> None:
    result = TypedDictAdapter(TypedDictSchema).validate({"value": 1, "nested": {"host": "localhost"}})

    assert type(result) is dict
    assert result == {"value": 1, "nested": {"host": "localhost"}}


def test_validate_with_schemaless_returns_schemaless_config() -> None:
    result = SchemalessAdapter().validate({"value": 1})

    assert isinstance(result, SchemalessConfig)
    assert result["value"] == 1


@pytest.mark.parametrize(("adapter", "schema"), SCHEMAD_ADAPTERS)
def test_validate_with_invalid_data_raises_validation_error(
    adapter: SchemaAdapter[object],
    schema: type[object],
) -> None:
    with pytest.raises(ValidationError):
        adapter.validate({"value": "not-an-int", "nested": {"host": "localhost"}})


@pytest.mark.parametrize(
    ("adapter", "expected"),
    [
        pytest.param(PydanticAdapter(PydanticSchema), True, id="pydantic"),
        pytest.param(DataclassAdapter(DataclassSchema), True, id="stdlib dataclass"),
        pytest.param(TypedDictAdapter(TypedDictSchema), False, id="TypedDict"),
        pytest.param(SchemalessAdapter(), False, id="schemaless"),
    ],
)
def test_masks_secrets(adapter: SchemaAdapter[object], expected: bool) -> None:
    assert adapter.masks_secrets is expected


class PlainTypingTypedDict(TypedDict):
    value: int


@pytest.mark.skipif(sys.version_info >= (3, 12), reason="plain typing.TypedDict is adaptable on Python >= 3.12")
def test_typeddict_adapter_with_plain_typing_typeddict_below_312_raises_schema_error() -> None:
    with pytest.raises(SchemaError):
        TypedDictAdapter(PlainTypingTypedDict)


@pytest.mark.skipif(sys.version_info < (3, 12), reason="plain typing.TypedDict is unadaptable on Python < 3.12")
def test_typeddict_adapter_with_plain_typing_typeddict_at_312_constructs() -> None:
    adapter = TypedDictAdapter(PlainTypingTypedDict)

    assert adapter.validate({"value": 1}) == {"value": 1}


@pytest.mark.parametrize(
    ("adapter", "expected"),
    [
        pytest.param(PydanticAdapter(PydanticSchema), "pydantic", id="pydantic"),
        pytest.param(DataclassAdapter(DataclassSchema), "stdlib dataclass", id="stdlib dataclass"),
        pytest.param(TypedDictAdapter(TypedDictSchema), "TypedDict", id="TypedDict"),
        pytest.param(SchemalessAdapter(), "schemaless", id="schemaless"),
    ],
)
def test_kind(adapter: SchemaAdapter[object], expected: str) -> None:
    assert adapter.kind == expected
