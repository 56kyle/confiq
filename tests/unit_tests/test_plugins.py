from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from confiq._plugins import _make_plugin_manager


if TYPE_CHECKING:
    from pathlib import Path


def test_make_plugin_manager_with_defaults() -> None:
    import pluggy

    pm = _make_plugin_manager()
    assert isinstance(pm, pluggy.PluginManager)


def test_load_file_with_json_path(tmp_path: Path) -> None:
    pm = _make_plugin_manager()
    f = tmp_path / "cfg.json"
    f.write_text(json.dumps({"key": "value"}))
    result = pm.hook.confiq_load_file(path=f)
    assert result == {"key": "value"}


def test_load_file_with_ini_path(tmp_path: Path) -> None:
    pm = _make_plugin_manager()
    f = tmp_path / "cfg.ini"
    f.write_text("[section]\nkey = value\n")
    result = pm.hook.confiq_load_file(path=f)
    assert isinstance(result, dict)
    assert result["section"]["key"] == "value"


def test_load_file_with_yaml_path(tmp_path: Path) -> None:
    pytest.importorskip("yaml")
    pm = _make_plugin_manager()
    f = tmp_path / "cfg.yaml"
    f.write_text("key: value\n")
    result = pm.hook.confiq_load_file(path=f)
    assert result == {"key": "value"}


def test_load_file_with_unknown_suffix(tmp_path: Path) -> None:
    pm = _make_plugin_manager()
    f = tmp_path / "cfg.xyz"
    f.write_text("data")
    result = pm.hook.confiq_load_file(path=f)
    assert result is None


def test_load_file_with_missing_json(tmp_path: Path) -> None:
    pm = _make_plugin_manager()
    f = tmp_path / "missing.json"
    result = pm.hook.confiq_load_file(path=f)
    assert result is None


def test_load_file_with_cfg_extension(tmp_path: Path) -> None:
    pm = _make_plugin_manager()
    f = tmp_path / "cfg.cfg"
    f.write_text("[database]\nhost = localhost\n")
    result = pm.hook.confiq_load_file(path=f)
    assert isinstance(result, dict)
    assert result["database"]["host"] == "localhost"
