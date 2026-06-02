from __future__ import annotations

import pytest

from confiq.exceptions import SourceParseError
from confiq.loaders import IniLoader
from confiq.loaders import JsonLoader
from confiq.loaders import Loader
from confiq.loaders import default_loaders


class TestLoaderProtocol:
    def test_json_loader_satisfies_protocol(self) -> None:
        assert isinstance(JsonLoader(), Loader)

    def test_ini_loader_satisfies_protocol(self) -> None:
        assert isinstance(IniLoader(), Loader)

    def test_default_loaders_all_satisfy_protocol(self) -> None:
        for loader in default_loaders():
            assert isinstance(loader, Loader)


class TestJsonLoader:
    def test_extensions(self) -> None:
        assert ".json" in JsonLoader().extensions()

    def test_wants_bytes_is_false(self) -> None:
        assert JsonLoader().wants_bytes() is False

    def test_parses_valid_json(self) -> None:
        assert JsonLoader().parse('{"key": "value"}') == {"key": "value"}

    def test_raises_source_parse_error_on_bad_json(self) -> None:
        with pytest.raises(SourceParseError):
            JsonLoader().parse("not json")


class TestIniLoader:
    def test_extensions(self) -> None:
        exts = IniLoader().extensions()
        assert ".ini" in exts
        assert ".cfg" in exts

    def test_wants_bytes_is_false(self) -> None:
        assert IniLoader().wants_bytes() is False

    def test_parses_ini_string(self) -> None:
        result = IniLoader().parse("[section]\nkey = value\n")
        assert isinstance(result, dict)
        assert result["section"]["key"] == "value"

    def test_parses_cfg_data(self) -> None:
        result = IniLoader().parse("[database]\nhost = localhost\n")
        assert result is not None
        assert result["database"]["host"] == "localhost"


class TestYamlLoader:
    def test_extensions(self) -> None:
        pytest.importorskip("yaml")
        from confiq.loaders._yaml import YamlLoader

        exts = YamlLoader().extensions()
        assert ".yaml" in exts
        assert ".yml" in exts

    def test_wants_bytes_is_false(self) -> None:
        pytest.importorskip("yaml")
        from confiq.loaders._yaml import YamlLoader

        assert YamlLoader().wants_bytes() is False

    def test_parses_valid_yaml(self) -> None:
        pytest.importorskip("yaml")
        from confiq.loaders._yaml import YamlLoader

        assert YamlLoader().parse("key: value\n") == {"key": "value"}

    def test_raises_source_parse_error_on_bad_yaml(self) -> None:
        pytest.importorskip("yaml")
        from confiq.loaders._yaml import YamlLoader

        with pytest.raises(SourceParseError):
            YamlLoader().parse(":\t\tinvalid: yaml: [")


class TestTomlLoader:
    def test_extensions(self) -> None:
        pytest.importorskip("confiq.loaders._toml", reason="tomllib/tomli not available")
        from confiq.loaders._toml import TomlLoader

        assert ".toml" in TomlLoader().extensions()

    def test_wants_bytes_is_true(self) -> None:
        pytest.importorskip("confiq.loaders._toml", reason="tomllib/tomli not available")
        from confiq.loaders._toml import TomlLoader

        assert TomlLoader().wants_bytes() is True

    def test_parses_valid_toml_bytes(self) -> None:
        pytest.importorskip("confiq.loaders._toml", reason="tomllib/tomli not available")
        from confiq.loaders._toml import TomlLoader

        assert TomlLoader().parse(b'key = "value"\n') == {"key": "value"}

    def test_raises_source_parse_error_on_bad_toml(self) -> None:
        pytest.importorskip("confiq.loaders._toml", reason="tomllib/tomli not available")
        from confiq.loaders._toml import TomlLoader

        with pytest.raises(SourceParseError):
            TomlLoader().parse(b"not = valid = toml\n")


class TestDefaultLoaders:
    def test_returns_non_empty_list(self) -> None:
        assert len(default_loaders()) >= 2

    def test_all_satisfy_protocol(self) -> None:
        for loader in default_loaders():
            assert isinstance(loader, Loader)
