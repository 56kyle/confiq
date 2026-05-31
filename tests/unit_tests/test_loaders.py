from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from confiq.exceptions import SourceParseError
from confiq.loaders import IniLoader
from confiq.loaders import JsonLoader
from confiq.loaders import Loader
from confiq.loaders import default_loaders


if TYPE_CHECKING:
    from pathlib import Path


class TestLoaderProtocol:
    def test_json_loader_satisfies_protocol(self) -> None:
        assert isinstance(JsonLoader(), Loader)

    def test_ini_loader_satisfies_protocol(self) -> None:
        assert isinstance(IniLoader(), Loader)

    def test_default_loaders_all_satisfy_protocol(self) -> None:
        for loader in default_loaders():
            assert isinstance(loader, Loader)


class TestJsonLoader:
    def test_loads_json_file(self, tmp_path: Path) -> None:
        f = tmp_path / "cfg.json"
        f.write_text(json.dumps({"key": "value"}))
        assert JsonLoader().load(f) == {"key": "value"}

    def test_returns_none_for_wrong_suffix(self, tmp_path: Path) -> None:
        f = tmp_path / "cfg.yaml"
        f.write_text("{}")
        assert JsonLoader().load(f) is None

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        assert JsonLoader().load(tmp_path / "missing.json") is None

    def test_raises_source_parse_error_on_bad_json(self, tmp_path: Path) -> None:
        f = tmp_path / "cfg.json"
        f.write_text("not json")
        with pytest.raises(SourceParseError):
            JsonLoader().load(f)


class TestIniLoader:
    def test_loads_ini_file(self, tmp_path: Path) -> None:
        f = tmp_path / "cfg.ini"
        f.write_text("[section]\nkey = value\n")
        result = IniLoader().load(f)
        assert isinstance(result, dict)
        assert result["section"]["key"] == "value"

    def test_loads_cfg_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "cfg.cfg"
        f.write_text("[database]\nhost = localhost\n")
        result = IniLoader().load(f)
        assert result is not None
        assert result["database"]["host"] == "localhost"

    def test_returns_none_for_wrong_suffix(self, tmp_path: Path) -> None:
        f = tmp_path / "cfg.json"
        f.write_text("{}")
        assert IniLoader().load(f) is None

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        assert IniLoader().load(tmp_path / "missing.ini") is None


class TestYamlLoader:
    def test_loads_yaml_file(self, tmp_path: Path) -> None:
        pytest.importorskip("yaml")
        from confiq.loaders._yaml import YamlLoader

        f = tmp_path / "cfg.yaml"
        f.write_text("key: value\n")
        assert YamlLoader().load(f) == {"key": "value"}

    def test_loads_yml_extension(self, tmp_path: Path) -> None:
        pytest.importorskip("yaml")
        from confiq.loaders._yaml import YamlLoader

        f = tmp_path / "cfg.yml"
        f.write_text("key: value\n")
        assert YamlLoader().load(f) == {"key": "value"}

    def test_returns_none_for_wrong_suffix(self, tmp_path: Path) -> None:
        pytest.importorskip("yaml")
        from confiq.loaders._yaml import YamlLoader

        f = tmp_path / "cfg.json"
        f.write_text("{}")
        assert YamlLoader().load(f) is None

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        pytest.importorskip("yaml")
        from confiq.loaders._yaml import YamlLoader

        assert YamlLoader().load(tmp_path / "missing.yaml") is None


class TestTomlLoader:
    def test_loads_toml_file(self, tmp_path: Path) -> None:
        pytest.importorskip("confiq.loaders._toml", reason="tomllib/tomli not available")
        from confiq.loaders._toml import TomlLoader

        f = tmp_path / "cfg.toml"
        f.write_bytes(b'key = "value"\n')
        assert TomlLoader().load(f) == {"key": "value"}

    def test_returns_none_for_wrong_suffix(self, tmp_path: Path) -> None:
        pytest.importorskip("confiq.loaders._toml", reason="tomllib/tomli not available")
        from confiq.loaders._toml import TomlLoader

        f = tmp_path / "cfg.json"
        f.write_text("{}")
        assert TomlLoader().load(f) is None

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        pytest.importorskip("confiq.loaders._toml", reason="tomllib/tomli not available")
        from confiq.loaders._toml import TomlLoader

        assert TomlLoader().load(tmp_path / "missing.toml") is None

    def test_raises_source_parse_error_on_bad_toml(self, tmp_path: Path) -> None:
        pytest.importorskip("confiq.loaders._toml", reason="tomllib/tomli not available")
        from confiq.loaders._toml import TomlLoader

        f = tmp_path / "cfg.toml"
        f.write_bytes(b"not = valid = toml\n")
        with pytest.raises(SourceParseError):
            TomlLoader().load(f)


class TestDefaultLoaders:
    def test_returns_non_empty_list(self) -> None:
        assert len(default_loaders()) >= 2

    def test_unknown_suffix_returns_none_from_all(self, tmp_path: Path) -> None:
        f = tmp_path / "cfg.xyz"
        f.write_text("data")
        for loader in default_loaders():
            assert loader.load(f) is None
