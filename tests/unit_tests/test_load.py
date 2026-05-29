from __future__ import annotations

import asyncio
import json
import warnings
from pathlib import Path

import pytest
from pydantic import BaseModel

from confiq._load import SchemalessConfig
from confiq._load import load
from confiq._load import load_async
from confiq.exceptions import ConfigValidationError
from confiq.sources._env import EnvSource
from confiq.sources._file import FileSource
from confiq.sources._memory import MemorySource


class DB(BaseModel, frozen=True):
    host: str = "localhost"
    port: int = 5432


class Settings(BaseModel, frozen=True):
    debug: bool = False
    database: DB = DB()
    name: str = "app"


def test_schemaless_load_returns_schemaless_config() -> None:
    result = load(sources=[MemorySource({"key": "value"})])
    assert isinstance(result, SchemalessConfig)


def test_schemaless_load_subscript_access() -> None:
    result = load(sources=[MemorySource({"key": "value"})])
    assert result["key"] == "value"


def test_schema_load_returns_model_instance() -> None:
    result = load(Settings, sources=[MemorySource({"name": "myapp"})])
    assert isinstance(result, Settings)
    assert result.name == "myapp"


def test_defaults_preserved_when_not_in_sources() -> None:
    result = load(Settings, sources=[MemorySource({})])
    assert result.debug is False
    assert result.database.host == "localhost"
    assert result.database.port == 5432


def test_source_precedence_last_wins() -> None:
    result = load(
        Settings,
        sources=[
            MemorySource({"name": "first"}),
            MemorySource({"name": "second"}),
        ],
    )
    assert result.name == "second"


def test_env_source_integration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "env-app")
    result = load(Settings, sources=[EnvSource(prefix="APP_")])
    assert result.name == "env-app"


def test_file_source_integration(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"name": "file-app"}))
    result = load(Settings, sources=[FileSource(cfg)])
    assert result.name == "file-app"


def test_strict_mode_unknown_key_emits_user_warning() -> None:
    with pytest.warns(UserWarning, match="not present in schema"):
        load(Settings, sources=[MemorySource({"unknown_key": "value"})], strict=True)


def test_non_strict_mode_suppresses_warning() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        load(Settings, sources=[MemorySource({"unknown_key": "value"})], strict=False)


def test_wrong_type_raises_config_validation_error() -> None:
    with pytest.raises(ConfigValidationError):
        load(Settings, sources=[MemorySource({"debug": "not_a_bool_or_coercible"})])


def test_load_async_returns_model_instance() -> None:
    result = asyncio.run(
        load_async(Settings, sources=[MemorySource({"name": "x"})])
    )
    assert isinstance(result, Settings)
    assert result.name == "x"


def test_load_async_defaults_preserved() -> None:
    result = asyncio.run(load_async(Settings, sources=[MemorySource({})]))
    assert result.debug is False
    assert result.name == "app"
