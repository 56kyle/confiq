"""Integration tests pinning the assembled Stage 4 sync resolver (`confiq._resolve.resolve`)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Annotated

import pytest
import typing_extensions
from pydantic import BaseModel

from confiq import EnvSource
from confiq import MemorySource
from confiq._field import ConfigField
from confiq._resolve import resolve
from confiq._schemaless import SchemalessConfig
from confiq.exceptions import ConfigValidationError
from confiq.exceptions import ConfiqError
from confiq.exceptions import MissingConfigError
from confiq.exceptions import SchemaError
from confiq.exceptions import SecretMaskingError


if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any


class DbConfig(BaseModel):
    host: str
    port: int


class NestedAppConfig(BaseModel):
    name: str
    db: DbConfig


class DbWrapper(BaseModel):
    db: DbConfig


class SinglePort(BaseModel):
    port: int


class TwoInts(BaseModel):
    a: int
    b: int


class CoercedPort(BaseModel):
    port: Annotated[int, ConfigField(parser=int)]


class TwoCoerced(BaseModel):
    a: Annotated[int, ConfigField(parser=int)]
    b: Annotated[int, ConfigField(parser=int)]


class SecretSchema(typing_extensions.TypedDict):
    token: Annotated[str, ConfigField(secret=True)]


class EnvAliasSchema(BaseModel):
    url: str


class _AsyncOnlySource:
    """Fake async-only source (implements fetch_async but not fetch)."""

    def __init__(self, name: str = "async-only", profile: str | None = None) -> None:
        self.name = name
        self.profile = profile

    async def fetch_async(self) -> Mapping[str, Any]:
        return {}


def test_resolve_with_single_source_returns_validated_instance() -> None:
    result = resolve(DbConfig, [MemorySource({"host": "localhost", "port": 5432})])

    assert isinstance(result, DbConfig)
    assert result.host == "localhost"
    assert result.port == 5432


def test_resolve_with_multiple_sources_lets_higher_index_win_on_collision() -> None:
    low = MemorySource({"port": 1}, name="low")
    high = MemorySource({"port": 2}, name="high")

    result = resolve(SinglePort, [low, high])

    assert isinstance(result, SinglePort)
    assert result.port == 2


def test_resolve_with_nested_sources_deep_merges_rather_than_replaces() -> None:
    host_source = MemorySource({"db": {"host": "a-host"}}, name="host-src")
    port_source = MemorySource({"db": {"port": 5432}}, name="port-src")

    result = resolve(DbWrapper, [host_source, port_source])

    assert isinstance(result, DbWrapper)
    assert result.db.host == "a-host"
    assert result.db.port == 5432


def test_resolve_with_mismatched_profile_excludes_profiled_source() -> None:
    base = MemorySource({"port": 1}, name="base")
    profiled = MemorySource({"port": 99}, name="prod-src", profile="prod")

    result = resolve(SinglePort, [base, profiled], profile="dev")

    assert isinstance(result, SinglePort)
    assert result.port == 1


def test_resolve_with_matching_profile_includes_profiled_source() -> None:
    base = MemorySource({"port": 1}, name="base")
    profiled = MemorySource({"port": 99}, name="prod-src", profile="prod")

    result = resolve(SinglePort, [base, profiled], profile="prod")

    assert isinstance(result, SinglePort)
    assert result.port == 99


def test_resolve_applies_parser_coercion_before_validation() -> None:
    result = resolve(CoercedPort, [MemorySource({"port": "8080"})])

    assert isinstance(result, CoercedPort)
    assert result.port == 8080


def test_resolve_with_none_schema_returns_schemaless_config() -> None:
    result = resolve(None, [MemorySource({"service": {"port": 5432}})])

    assert isinstance(result, SchemalessConfig)
    assert result["service"]["port"] == 5432


def test_resolve_with_invalid_field_raises_validation_error_naming_field_and_source() -> None:
    source = MemorySource({"host": "localhost", "port": "not-a-port"}, name="primary")

    with pytest.raises(ConfigValidationError) as exc_info:
        resolve(DbConfig, [source])

    error = exc_info.value
    assert error.field_path == "port"
    assert error.sources == ("primary",)
    assert "port" in str(error)
    assert "primary" in str(error)


def test_resolve_with_two_invalid_fields_aggregates_into_one_error() -> None:
    source = MemorySource({"a": "x", "b": "y"}, name="src")

    with pytest.raises(ConfigValidationError) as exc_info:
        resolve(TwoInts, [source])

    field_paths = {context.field_path for context in exc_info.value.contexts}
    assert field_paths == {"a", "b"}


def test_resolve_with_all_fields_missing_raises_missing_config_error() -> None:
    with pytest.raises(MissingConfigError) as exc_info:
        resolve(TwoInts, [MemorySource({}, name="empty")])

    field_paths = {context.field_path for context in exc_info.value.contexts}
    assert field_paths == {"a", "b"}


def test_resolve_with_mixed_missing_and_invalid_raises_validation_error() -> None:
    source = MemorySource({"a": "not-an-int"}, name="src")

    with pytest.raises(ConfigValidationError):
        resolve(TwoInts, [source])


def test_resolve_with_unmaskable_secret_field_refuses_with_secret_masking_error() -> None:
    with pytest.raises(SecretMaskingError) as exc_info:
        resolve(SecretSchema, [MemorySource({"token": "s3cret"})])

    assert isinstance(exc_info.value, SchemaError)
    assert exc_info.value.field_paths == ("token",)


def test_resolve_with_env_alias_populates_field_from_named_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgres://x")

    result = resolve(EnvAliasSchema, [EnvSource("APP", aliases={"url": "DATABASE_URL"})])

    assert isinstance(result, EnvAliasSchema)
    assert result.url == "postgres://x"


def test_resolve_with_async_only_source_refuses_pointing_to_load_async() -> None:
    with pytest.raises(ConfiqError) as exc_info:
        resolve(SinglePort, [_AsyncOnlySource(name="vault")])  # pyright: ignore[reportArgumentType]  # async-only source deliberately violates the SyncSource contract to exercise the guard

    message = str(exc_info.value)
    assert "vault" in message
    assert "load_async" in message


def test_resolve_with_raising_parser_folds_into_validation_error_naming_source() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        resolve(CoercedPort, [MemorySource({"port": "notanint"}, name="primary")])

    error = exc_info.value
    assert error.field_path == "port"
    assert error.sources == ("primary",)
    assert "primary" in str(error)
    assert isinstance(error.original, ValueError)


def test_resolve_with_two_raising_parsers_aggregates_into_one_error() -> None:
    source = MemorySource({"a": "notanint", "b": "alsobad"}, name="src")

    with pytest.raises(ConfigValidationError) as exc_info:
        resolve(TwoCoerced, [source])

    contexts = exc_info.value.contexts
    assert len(contexts) == 2
    assert {context.field_path for context in contexts} == {"a", "b"}
    assert all(context.sources == ("src",) for context in contexts)
