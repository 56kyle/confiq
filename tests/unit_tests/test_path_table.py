"""Unit tests pinning the Stage 2 schema path-table builder (`confiq.adapter._path_table`)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
from typing import Optional

import pytest
import typing_extensions
from pydantic import BaseModel

from confiq._field import ConfigField
from confiq.adapter._path_table import build_path_table
from confiq.exceptions import SchemaError


class PydanticEndpoint(BaseModel):
    host: str
    port: int


class PydanticSettings(BaseModel):
    debug: bool
    database: PydanticEndpoint
    token: Annotated[str, ConfigField(secret=True)]
    replicas: list[PydanticEndpoint]
    fallback: Optional[PydanticEndpoint]


@dataclass
class DataclassEndpoint:
    host: str
    port: int


@dataclass
class DataclassSettings:
    debug: bool
    database: DataclassEndpoint
    token: Annotated[str, ConfigField(secret=True)]
    replicas: list[DataclassEndpoint]
    fallback: Optional[DataclassEndpoint]


class TypedDictEndpoint(typing_extensions.TypedDict):
    host: str
    port: int


class TypedDictSettings(typing_extensions.TypedDict):
    debug: bool
    database: TypedDictEndpoint
    token: Annotated[str, ConfigField(secret=True)]
    replicas: list[TypedDictEndpoint]
    fallback: Optional[TypedDictEndpoint]


ALL_KINDS = [
    pytest.param(PydanticSettings, id="pydantic"),
    pytest.param(DataclassSettings, id="stdlib dataclass"),
    pytest.param(TypedDictSettings, id="TypedDict"),
]


def _config_fields(extras: list[object]) -> list[ConfigField]:
    return [extra for extra in extras if isinstance(extra, ConfigField)]


def _is_leaf(path: str, table: object) -> bool:
    prefix = f"{path}."
    return not any(other.startswith(prefix) for other in table)  # type: ignore[union-attr]


@pytest.mark.parametrize("schema", ALL_KINDS)
def test_build_path_table_with_nested_field_produces_dotted_paths(schema: type[object]) -> None:
    table = build_path_table(schema)

    assert "database.host" in table
    assert "database.port" in table


@pytest.mark.parametrize("schema", ALL_KINDS)
def test_build_path_table_includes_intermediate_nested_node(schema: type[object]) -> None:
    table = build_path_table(schema)

    assert "database" in table


def test_build_path_table_leaf_is_recoverable_by_prefix() -> None:
    table = build_path_table(PydanticSettings)

    assert _is_leaf("database.host", table)
    assert not _is_leaf("database", table)


@pytest.mark.parametrize("schema", ALL_KINDS)
def test_build_path_table_captures_config_field_extra(schema: type[object]) -> None:
    table = build_path_table(schema)

    assert _config_fields(table["token"]) == [ConfigField(secret=True)]


@pytest.mark.parametrize("schema", ALL_KINDS)
def test_build_path_table_with_list_of_models_stops_at_field_leaf(schema: type[object]) -> None:
    table = build_path_table(schema)

    assert "replicas" in table
    assert not any(path.startswith("replicas.") for path in table)


@pytest.mark.parametrize("schema", ALL_KINDS)
def test_build_path_table_with_optional_model_stops_at_field_leaf(schema: type[object]) -> None:
    table = build_path_table(schema)

    assert "fallback" in table
    assert not any(path.startswith("fallback.") for path in table)


class CrossFamilyLeaf(typing_extensions.TypedDict):
    value: str


@dataclass
class CrossFamilyMid:
    leaf: CrossFamilyLeaf
    count: int


class CrossFamilyRoot(BaseModel):
    mid: CrossFamilyMid
    top: str


def test_build_path_table_with_cross_family_nesting_resolves_deep_paths() -> None:
    table = build_path_table(CrossFamilyRoot)

    assert "mid" in table
    assert "mid.leaf" in table
    assert "mid.leaf.value" in table
    assert "mid.count" in table
    assert "top" in table


class OptionalNestedLeaf(typing_extensions.TypedDict):
    host: str
    port: int


class NotRequiredNestedSettings(typing_extensions.TypedDict):
    sub: typing_extensions.NotRequired[OptionalNestedLeaf]


def test_build_path_table_with_not_required_nested_schema_recurses() -> None:
    table = build_path_table(NotRequiredNestedSettings)

    assert "sub" in table
    assert "sub.host" in table
    assert "sub.port" in table


class MixedWrapSettings(typing_extensions.TypedDict):
    not_required_then_annotated: typing_extensions.NotRequired[Annotated[int, ConfigField(secret=True)]]
    annotated_then_not_required: Annotated[typing_extensions.NotRequired[int], ConfigField()]


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        pytest.param("not_required_then_annotated", ConfigField(secret=True), id="NotRequired[Annotated]"),
        pytest.param("annotated_then_not_required", ConfigField(), id="Annotated[NotRequired]"),
    ],
)
def test_build_path_table_with_mixed_wrap_order_preserves_config_field(path: str, expected: ConfigField) -> None:
    table = build_path_table(MixedWrapSettings)

    assert _config_fields(table[path]) == [expected]


@dataclass
class DanglingDataclass:
    value: "DoesNotExist"  # type: ignore[name-defined]  # noqa: F821


class DanglingTypedDict(typing_extensions.TypedDict):
    value: "AlsoDoesNotExist"  # type: ignore[name-defined]  # noqa: F821


@pytest.mark.parametrize(
    "schema",
    [
        pytest.param(DanglingDataclass, id="stdlib dataclass"),
        pytest.param(DanglingTypedDict, id="TypedDict"),
    ],
)
def test_build_path_table_with_unresolvable_forward_ref_raises_schema_error(schema: type[object]) -> None:
    with pytest.raises(SchemaError) as exc_info:
        build_path_table(schema)

    assert not isinstance(exc_info.value, NameError)
