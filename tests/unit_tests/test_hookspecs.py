"""Unit tests pinning the Stage 2 adapter resolution surface (`confiq._hookspecs`, ADR 0030)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Any

import pytest
import typing_extensions
from pydantic import BaseModel

from confiq._hookspecs import hookimpl
from confiq._hookspecs import make_plugin_manager
from confiq._hookspecs import resolve_schema_adapter
from confiq.adapter._dataclass import DataclassAdapter
from confiq.adapter._pydantic import PydanticAdapter
from confiq.adapter._schemaless import SchemalessAdapter
from confiq.adapter._typeddict import TypedDictAdapter
from confiq.exceptions import SchemaError
from confiq.exceptions import SecretMaskingError


if TYPE_CHECKING:
    from confiq.adapter._schema_adapter import SchemaAdapter


class PydanticSchema(BaseModel):
    value: int


@dataclass
class DataclassSchema:
    value: int


class TypedDictSchema(typing_extensions.TypedDict):
    value: int


class BareClass:
    pass


@pytest.mark.parametrize(
    ("schema", "expected_adapter"),
    [
        pytest.param(PydanticSchema, PydanticAdapter, id="pydantic"),
        pytest.param(DataclassSchema, DataclassAdapter, id="stdlib dataclass"),
        pytest.param(TypedDictSchema, TypedDictAdapter, id="TypedDict"),
        pytest.param(None, SchemalessAdapter, id="schemaless"),
    ],
)
def test_resolve_schema_adapter_selects_built_in(
    schema: type[object] | None,
    expected_adapter: type[SchemaAdapter[Any]],
) -> None:
    adapter = resolve_schema_adapter(make_plugin_manager(), schema)

    assert isinstance(adapter, expected_adapter)


@pytest.mark.parametrize("schema", [pytest.param(int, id="scalar type"), pytest.param(BareClass, id="bare class")])
def test_resolve_schema_adapter_with_unclaimed_schema_raises_plain_schema_error(schema: type[object]) -> None:
    with pytest.raises(SchemaError) as exc_info:
        resolve_schema_adapter(make_plugin_manager(), schema)

    assert not isinstance(exc_info.value, SecretMaskingError)


class _OverridingPlugin:
    @hookimpl
    def confiq_get_schema_adapter(self, schema: type[Any] | None) -> SchemaAdapter[Any] | None:
        if schema is PydanticSchema:
            return SchemalessAdapter()
        return None


def test_resolve_schema_adapter_with_user_plugin_overrides_built_in() -> None:
    manager = make_plugin_manager((_OverridingPlugin(),))

    adapter = resolve_schema_adapter(manager, PydanticSchema)

    assert isinstance(adapter, SchemalessAdapter)
