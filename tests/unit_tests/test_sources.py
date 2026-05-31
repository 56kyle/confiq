from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any

import pytest

from confiq.exceptions import SourceParseError
from confiq.exceptions import SourceUnavailableError
from confiq.sources import CliSource
from confiq.sources import EnvSource
from confiq.sources import FileSource
from confiq.loaders import default_loaders
from confiq.sources import MemorySource


if TYPE_CHECKING:
    from pathlib import Path


class TestMemorySource:
    def test_fetch_returns_data(self) -> None:
        src = MemorySource({"key": "value"})
        assert src.fetch() == {"key": "value"}

    def test_fetch_returns_same_dict(self) -> None:
        src = MemorySource({"key": "value"})
        assert src.fetch() is src.fetch()

    def test_default_name(self) -> None:
        src = MemorySource({})
        assert src.name == "memory"

    def test_custom_name(self) -> None:
        src = MemorySource({}, name="defaults")
        assert src.name == "defaults"

    def test_nested_data(self) -> None:
        data = {"db": {"host": "localhost", "port": 5432}}
        src = MemorySource(data)
        assert src.fetch()["db"]["host"] == "localhost"


class TestEnvSource:
    def test_prefix_filtering(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_HOST", "myhost")
        monkeypatch.setenv("OTHER_VAR", "ignore")
        src = EnvSource(prefix="APP_")
        result = src.fetch()
        assert "host" in result
        assert "other_var" not in result

    def test_delimiter_nesting(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_DATABASE__HOST", "db.local")
        src = EnvSource(prefix="APP_")
        result = src.fetch()
        assert result["database"]["host"] == "db.local"

    def test_no_prefix_includes_all(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UNIQUE_CONFIQ_TEST_VAR", "hello")
        src = EnvSource()
        result = src.fetch()
        assert "unique_confiq_test_var" in result

    def test_bool_coercion_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_FLAG", "true")
        src = EnvSource(prefix="APP_")
        result = src.fetch()
        assert result["flag"] is True

    def test_bool_coercion_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_FLAG", "false")
        src = EnvSource(prefix="APP_")
        result = src.fetch()
        assert result["flag"] is False

    def test_int_coercion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_PORT", "5432")
        src = EnvSource(prefix="APP_")
        result = src.fetch()
        assert result["port"] == 5432

    def test_default_name(self) -> None:
        src = EnvSource()
        assert src.name == "env"

    def test_custom_name(self) -> None:
        src = EnvSource(name="environment")
        assert src.name == "environment"

    def test_fetch_method_exists(self) -> None:
        src = EnvSource()
        assert callable(src.fetch)


class TestFileSource:
    def test_fetch_loads_json(self, tmp_path: Path) -> None:
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"host": "localhost", "port": 5432}))
        src = FileSource(cfg)
        result = src.fetch()
        assert result == {"host": "localhost", "port": 5432}

    def test_missing_required_raises_source_unavailable(self, tmp_path: Path) -> None:
        src = FileSource(tmp_path / "missing.json", required=True)
        with pytest.raises(SourceUnavailableError):
            src.fetch()

    def test_missing_optional_returns_empty(self, tmp_path: Path) -> None:
        src = FileSource(tmp_path / "missing.json", required=False)
        assert src.fetch() == {}

    def test_unsupported_extension_raises_source_parse_error(self, tmp_path: Path) -> None:
        f = tmp_path / "config.xyz"
        f.write_text("data")
        src = FileSource(f)
        with pytest.raises(SourceParseError):
            src.fetch()

    def test_default_name(self, tmp_path: Path) -> None:
        src = FileSource(tmp_path / "x.json")
        assert src.name == "file"

    def test_custom_name(self, tmp_path: Path) -> None:
        src = FileSource(tmp_path / "x.json", name="base_config")
        assert src.name == "base_config"

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"k": "v"}))
        src = FileSource(str(cfg))
        assert src.fetch() == {"k": "v"}

    def test_custom_loader_called_first(self, tmp_path: Path) -> None:
        class UpperLoader:
            def load(self, path: Path) -> dict[str, Any] | None:
                if path.suffix != ".json":
                    return None
                return {"injected": True}

        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"injected": False}))
        src = FileSource(cfg, loaders=[UpperLoader(), *default_loaders()])
        assert src.fetch() == {"injected": True}

    def test_custom_loader_only_no_default(self, tmp_path: Path) -> None:
        from typing import Any

        class CustomLoader:
            def load(self, path: Path) -> dict[str, Any] | None:
                if path.suffix != ".custom":
                    return None
                return {"custom": True}

        f = tmp_path / "config.custom"
        f.write_text("irrelevant")
        src = FileSource(f, loaders=[CustomLoader()])
        assert src.fetch() == {"custom": True}


class TestCliSource:
    def test_key_equals_value(self) -> None:
        src = CliSource(["--host=localhost"])
        assert src.fetch() == {"host": "localhost"}

    def test_key_space_value(self) -> None:
        src = CliSource(["--host", "localhost"])
        assert src.fetch() == {"host": "localhost"}

    def test_flag_boolean_true(self) -> None:
        src = CliSource(["--debug"])
        assert src.fetch() == {"debug": True}

    def test_dotted_key_nesting(self) -> None:
        src = CliSource(["--database.host=pg"])
        assert src.fetch() == {"database": {"host": "pg"}}

    def test_sentinel_stops_parsing(self) -> None:
        src = CliSource(["--host=a", "--", "--host=b"])
        result = src.fetch()
        assert result == {"host": "a"}

    def test_empty_key_raises(self) -> None:
        src = CliSource(["--=value"])
        with pytest.raises(ValueError):
            src.fetch()

    def test_empty_segment_raises(self) -> None:
        src = CliSource(["--a..b=value"])
        with pytest.raises(ValueError):
            src.fetch()

    def test_path_conflict_scalar_over_dict_raises(self) -> None:
        src = CliSource(["--db.host=pg", "--db=flat"])
        with pytest.raises(ValueError):
            src.fetch()

    def test_path_conflict_dict_over_scalar_raises(self) -> None:
        src = CliSource(["--db=flat", "--db.host=pg"])
        with pytest.raises(ValueError):
            src.fetch()

    def test_default_name(self) -> None:
        src = CliSource([])
        assert src.name == "cli"

    def test_custom_name(self) -> None:
        src = CliSource([], name="args")
        assert src.name == "args"

    def test_multiple_keys(self) -> None:
        src = CliSource(["--host=pg", "--port=5432"])
        result = src.fetch()
        assert result == {"host": "pg", "port": 5432}

    def test_empty_argv_returns_empty(self) -> None:
        src = CliSource([])
        assert src.fetch() == {}
