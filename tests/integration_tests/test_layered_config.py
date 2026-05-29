from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from confiq._load import load
from confiq.sources._env import EnvSource
from confiq.sources._file import FileSource
from confiq.sources._memory import MemorySource


class AppSettings(BaseModel, frozen=True):
    host: str = "localhost"
    port: int = 8080
    debug: bool = False
    name: str = "default"


def test_env_overrides_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"host": "file-host", "port": 9090}))
    monkeypatch.setenv("APP_HOST", "env-host")

    result = load(
        AppSettings,
        sources=[FileSource(cfg), EnvSource(prefix="APP_")],
        strict=False,
    )
    assert result.host == "env-host"
    assert result.port == 9090


def test_later_source_wins() -> None:
    result = load(
        AppSettings,
        sources=[
            MemorySource({"name": "first"}),
            MemorySource({"name": "second"}),
        ],
    )
    assert result.name == "second"


def test_three_source_layering(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"host": "file-host", "port": 7777, "name": "from-file"}))
    monkeypatch.setenv("APP_HOST", "env-host")

    result = load(
        AppSettings,
        sources=[
            FileSource(cfg),
            MemorySource({"name": "from-memory", "debug": True}),
            EnvSource(prefix="APP_"),
        ],
        strict=False,
    )
    assert result.host == "env-host"
    assert result.port == 7777
    assert result.name == "from-memory"
    assert result.debug is True


def test_schema_defaults_used_for_missing_keys() -> None:
    result = load(AppSettings, sources=[MemorySource({})])
    assert result.host == "localhost"
    assert result.port == 8080
    assert result.debug is False
    assert result.name == "default"


def test_memory_then_env_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "env-name")
    result = load(
        AppSettings,
        sources=[
            MemorySource({"name": "memory-name", "host": "memory-host"}),
            EnvSource(prefix="APP_"),
        ],
        strict=False,
    )
    assert result.name == "env-name"
    assert result.host == "memory-host"
