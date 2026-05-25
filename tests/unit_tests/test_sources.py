import json
import os

import pytest

from confiq.sources._coerce import parse_env_value, set_nested_path
from confiq.sources.argparse_source import ArgparseSource, _parse_dotted
from confiq.sources.dict_source import DictSource
from confiq.sources.env import EnvSource


class TestDictSource:
    def test_load_returns_copy(self):
        data = {"a": 1}
        src = DictSource(data)
        result = src.load()
        assert result == {"a": 1}
        result["a"] = 99
        assert src.load()["a"] == 1  # original unchanged

    def test_custom_priority(self):
        src = DictSource({}, priority=99)
        assert src.priority == 99

    def test_default_priority(self):
        from confiq.sources.base import PRIORITY_FILE
        assert DictSource({}).priority == PRIORITY_FILE

    def test_supports_watch_false(self):
        assert not DictSource({}).supports_watch()


class TestEnvSource:
    def test_prefix_filter(self, monkeypatch):
        monkeypatch.setenv("MYAPP_HOST", "pg")
        monkeypatch.setenv("OTHER_VAR", "ignored")
        src = EnvSource(prefix="MYAPP_")
        result = src.load()
        assert "host" in result
        assert "other_var" not in result

    def test_delimiter_nesting(self, monkeypatch):
        monkeypatch.setenv("APP_DATABASE__HOST", "db.local")
        src = EnvSource(prefix="APP_", delimiter="__")
        result = src.load()
        assert result["database"]["host"] == "db.local"

    def test_no_prefix_includes_all(self, monkeypatch):
        monkeypatch.setenv("CONFIQ_TEST_VAR_XYZ", "hello")
        src = EnvSource()
        result = src.load()
        assert "confiq_test_var_xyz" in result

    def test_bool_coercion(self, monkeypatch):
        monkeypatch.setenv("MYAPP_DEBUG", "true")
        src = EnvSource(prefix="MYAPP_")
        assert src.load()["debug"] is True

    def test_int_coercion(self, monkeypatch):
        monkeypatch.setenv("MYAPP_PORT", "5432")
        src = EnvSource(prefix="MYAPP_")
        assert src.load()["port"] == 5432


class TestArgparseSource:
    def test_explicit_argv(self):
        src = ArgparseSource(argv=["--host", "localhost", "--port", "8080"])
        result = src.load()
        assert result["host"] == "localhost"
        assert result["port"] == 8080

    def test_dotted_key(self):
        src = ArgparseSource(argv=["--database.host=pg.local"])
        result = src.load()
        assert result["database"]["host"] == "pg.local"

    def test_boolean_flag(self):
        src = ArgparseSource(argv=["--debug"])
        assert src.load()["debug"] is True

    def test_empty_argv(self):
        src = ArgparseSource(argv=[])
        assert src.load() == {}

    def test_namespace_passed_directly(self):
        import argparse
        ns = argparse.Namespace(host="remote", port=9090)
        src = ArgparseSource(namespace=ns)
        result = src.load()
        assert result.get("host") == "remote" or result.get("port") is not None


class TestCoerce:
    def test_true(self):
        assert parse_env_value("true") is True
        assert parse_env_value("True") is True

    def test_false(self):
        assert parse_env_value("false") is False

    def test_int(self):
        assert parse_env_value("42") == 42
        assert isinstance(parse_env_value("42"), int)

    def test_float(self):
        assert parse_env_value("3.14") == pytest.approx(3.14)

    def test_string_passthrough(self):
        assert parse_env_value("hello") == "hello"

    def test_set_nested_path(self):
        d: dict = {}
        set_nested_path(d, ["a", "b", "c"], 99)
        assert d == {"a": {"b": {"c": 99}}}


class TestFileSource:
    def test_load_json(self, tmp_path):
        from confiq._plugins import _make_plugin_manager, _register_optional_loaders
        from confiq.sources.file import FileSource

        pm = _make_plugin_manager()
        _register_optional_loaders(pm)

        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps({"key": "value", "port": 3000}))

        src = FileSource(cfg_file, plugin_manager=pm)
        result = src.load()
        assert result == {"key": "value", "port": 3000}

    def test_missing_required_raises(self, tmp_path):
        from confiq._plugins import _make_plugin_manager
        from confiq.sources.file import FileSource

        pm = _make_plugin_manager()
        src = FileSource(tmp_path / "nope.json", required=True, plugin_manager=pm)
        with pytest.raises(FileNotFoundError):
            src.load()

    def test_missing_optional_returns_empty(self, tmp_path):
        from confiq._plugins import _make_plugin_manager
        from confiq.sources.file import FileSource

        pm = _make_plugin_manager()
        src = FileSource(tmp_path / "nope.json", required=False, plugin_manager=pm)
        assert src.load() == {}
