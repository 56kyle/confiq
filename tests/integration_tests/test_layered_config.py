"""Integration tests verifying source precedence and layered merging."""

import json

import pytest
from pydantic import BaseModel

from confiq._core import Config
from confiq.sources.base import PRIORITY_ENV, PRIORITY_FILE


class AppSettings(BaseModel):
    host: str = "localhost"
    port: int = 8080
    debug: bool = False
    name: str = "default"


def test_env_overrides_file(tmp_path, monkeypatch):
    f = tmp_path / "base.json"
    f.write_text(json.dumps({"host": "file-host", "port": 9090}))

    monkeypatch.setenv("APP_HOST", "env-host")

    cfg = Config()
    cfg.bind(AppSettings)
    cfg.add_file(f)
    cfg.add_env(prefix="APP_")

    s = cfg.get()
    assert s.host == "env-host"  # env wins
    assert s.port == 9090  # file value kept (no env override)


def test_layered_files_with_priority(tmp_path):
    base = tmp_path / "base.json"
    base.write_text(json.dumps({"name": "base", "host": "base-host"}))

    override = tmp_path / "prod.json"
    override.write_text(json.dumps({"name": "prod"}))

    cfg = Config()
    cfg.bind(AppSettings)
    cfg.add_file(base)
    cfg.add_file(override, priority=PRIORITY_FILE + 1)

    s = cfg.get()
    assert s.name == "prod"  # higher-priority file wins
    assert s.host == "base-host"  # base value kept


def test_dict_overrides_file(tmp_path):
    f = tmp_path / "cfg.json"
    f.write_text(json.dumps({"name": "from-file"}))

    cfg = Config()
    cfg.bind(AppSettings)
    cfg.add_file(f)
    cfg.add_dict({"name": "from-dict"}, priority=PRIORITY_FILE + 1)

    assert cfg.get().name == "from-dict"


def test_defaults_lowest_priority(tmp_path):
    f = tmp_path / "cfg.json"
    f.write_text(json.dumps({"host": "file-host"}))

    cfg = Config()
    cfg.bind(AppSettings)
    cfg.add_defaults_from_schema()
    cfg.add_file(f)

    s = cfg.get()
    assert s.host == "file-host"  # file wins over defaults
    assert s.port == 8080  # schema default applied


def test_reprioritize_reverses_order():
    cfg = Config()
    cfg.bind(AppSettings)
    cfg.add_dict({"name": "first"}, priority=PRIORITY_FILE)
    cfg.add_dict({"name": "second"}, priority=PRIORITY_FILE + 1)

    assert cfg.get().name == "second"

    cfg.reprioritize_sources(key=lambda s: -s.priority)
    assert cfg.get().name == "first"


def test_three_file_layering(tmp_path):
    base = tmp_path / "base.json"
    base.write_text(json.dumps({"name": "base", "host": "base", "debug": False}))

    env_file = tmp_path / "env.json"
    env_file.write_text(json.dumps({"name": "env"}))

    local = tmp_path / "local.json"
    local.write_text(json.dumps({"debug": True}))

    cfg = Config()
    cfg.bind(AppSettings)
    cfg.add_file(base)
    cfg.add_file(env_file, priority=PRIORITY_FILE + 1)
    cfg.add_file(local, priority=PRIORITY_FILE + 2)

    s = cfg.get()
    assert s.name == "env"
    assert s.host == "base"
    assert s.debug is True
