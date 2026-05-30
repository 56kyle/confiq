from __future__ import annotations

import asyncio
import json
import warnings
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel

from confiq._load import SchemalessConfig
from confiq._load import load
from confiq._load import load_async
from confiq.exceptions import ConfigValidationError
from confiq.sources._env import EnvSource
from confiq.sources._file import FileSource
from confiq.sources._memory import MemorySource


if TYPE_CHECKING:
    from pathlib import Path


class DB(BaseModel, frozen=True):
    host: str = "localhost"
    port: int = 5432


class Settings(BaseModel, frozen=True):
    debug: bool = False
    database: DB = DB()
    name: str = "app"


def test_load_with_no_schema() -> None:
    result = load(sources=[MemorySource({"key": "value"})])
    assert isinstance(result, SchemalessConfig)


def test_load_with_no_schema_subscript_access() -> None:
    result = load(sources=[MemorySource({"key": "value"})])
    assert result["key"] == "value"


def test_load_with_schema() -> None:
    result = load(Settings, sources=[MemorySource({"name": "myapp"})])
    assert isinstance(result, Settings)
    assert result.name == "myapp"


def test_load_with_no_matching_source_keys() -> None:
    result = load(Settings, sources=[MemorySource({})])
    assert result.debug is False
    assert result.database.host == "localhost"
    assert result.database.port == 5432


def test_load_with_overlapping_sources() -> None:
    result = load(
        Settings,
        sources=[
            MemorySource({"name": "first"}),
            MemorySource({"name": "second"}),
        ],
    )
    assert result.name == "second"


def test_load_with_env_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "env-app")
    result = load(Settings, sources=[EnvSource(prefix="APP_")])
    assert result.name == "env-app"


def test_load_with_file_source(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"name": "file-app"}))
    result = load(Settings, sources=[FileSource(cfg)])
    assert result.name == "file-app"


def test_load_with_unknown_key_and_strict_mode() -> None:
    with pytest.warns(UserWarning, match="not present in schema"):
        load(Settings, sources=[MemorySource({"unknown_key": "value"})], strict=True)


def test_load_with_unknown_key_and_strict_disabled() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        load(Settings, sources=[MemorySource({"unknown_key": "value"})], strict=False)


def test_load_with_wrong_field_type() -> None:
    with pytest.raises(ConfigValidationError):
        load(Settings, sources=[MemorySource({"debug": "not_a_bool_or_coercible"})])


def test_load_async_with_schema() -> None:
    result = asyncio.run(
        load_async(Settings, sources=[MemorySource({"name": "x"})])
    )
    assert isinstance(result, Settings)
    assert result.name == "x"


def test_load_async_with_no_matching_source_keys() -> None:
    result = asyncio.run(load_async(Settings, sources=[MemorySource({})]))
    assert result.debug is False
    assert result.name == "app"
