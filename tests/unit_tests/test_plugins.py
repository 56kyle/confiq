from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from confiq._plugins import _make_plugin_manager


if TYPE_CHECKING:
    from pathlib import Path


def test_make_plugin_manager_returns_plugin_manager() -> None:
    import pluggy

    pm = _make_plugin_manager()
    assert isinstance(pm, pluggy.PluginManager)


def test_json_loading(tmp_path: Path) -> None:
    pm = _make_plugin_manager()
    f = tmp_path / "cfg.json"
    f.write_text(json.dumps({"key": "value"}))
    result = pm.hook.confiq_load_file(path=f)
    assert result == {"key": "value"}


def test_ini_loading(tmp_path: Path) -> None:
    pm = _make_plugin_manager()
    f = tmp_path / "cfg.ini"
    f.write_text("[section]\nkey = value\n")
    result = pm.hook.confiq_load_file(path=f)
    assert isinstance(result, dict)
    assert result["section"]["key"] == "value"


def test_yaml_loading(tmp_path: Path) -> None:
    pytest.importorskip("yaml")
    pm = _make_plugin_manager()
    f = tmp_path / "cfg.yaml"
    f.write_text("key: value\n")
    result = pm.hook.confiq_load_file(path=f)
    assert result == {"key": "value"}


def test_unknown_suffix_returns_none(tmp_path: Path) -> None:
    pm = _make_plugin_manager()
    f = tmp_path / "cfg.xyz"
    f.write_text("data")
    result = pm.hook.confiq_load_file(path=f)
    assert result is None


def test_json_missing_file_returns_none(tmp_path: Path) -> None:
    pm = _make_plugin_manager()
    f = tmp_path / "missing.json"
    result = pm.hook.confiq_load_file(path=f)
    assert result is None


def test_cfg_extension_loaded_as_ini(tmp_path: Path) -> None:
    pm = _make_plugin_manager()
    f = tmp_path / "cfg.cfg"
    f.write_text("[database]\nhost = localhost\n")
    result = pm.hook.confiq_load_file(path=f)
    assert isinstance(result, dict)
    assert result["database"]["host"] == "localhost"
