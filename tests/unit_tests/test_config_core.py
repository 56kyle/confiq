import json

import pytest
from pydantic import BaseModel

from confiq._core import Config


class DB(BaseModel):
    host: str = "localhost"
    port: int = 5432


class Settings(BaseModel):
    debug: bool = False
    database: DB = DB()
    name: str = "app"


class TestBind:
    def test_bind_pydantic_schema(self):
        cfg = Config()
        cfg.bind(Settings)
        result = cfg.get()
        assert isinstance(result, Settings)

    def test_bind_returns_self(self):
        cfg = Config()
        result = cfg.bind(Settings)
        assert result is cfg

    def test_bind_unsupported_raises(self):
        cfg = Config()
        with pytest.raises(TypeError):
            cfg.bind(int)  # type: ignore[arg-type]


class TestAddDict:
    def test_values_accessible_via_get(self):
        cfg = Config()
        cfg.bind(Settings)
        cfg.add_dict({"name": "myapp"})
        assert cfg.get().name == "myapp"

    def test_dotted_get_on_raw(self):
        cfg = Config()
        cfg.add_dict({"db": {"host": "pg"}})
        assert cfg.get("db.host") == "pg"

    def test_default_returned_for_missing(self):
        cfg = Config()
        assert cfg.get("nonexistent", "fallback") == "fallback"

    def test_layered_dicts_merge(self):
        cfg = Config()
        cfg.bind(Settings)
        cfg.add_dict({"database": {"host": "first"}})
        cfg.add_dict({"name": "second"})
        s = cfg.get()
        assert s.database.host == "first"
        assert s.name == "second"


class TestAddEnv:
    def test_env_overrides_dict(self, monkeypatch):
        monkeypatch.setenv("MYAPP_NAME", "from_env")
        cfg = Config()
        cfg.bind(Settings)
        cfg.add_dict({"name": "from_dict"})
        cfg.add_env(prefix="MYAPP_")
        assert cfg.get().name == "from_env"


class TestAddFile:
    def test_json_file_loaded(self, tmp_path):
        f = tmp_path / "config.json"
        f.write_text(json.dumps({"name": "fromfile"}))
        cfg = Config()
        cfg.bind(Settings)
        cfg.add_file(f)
        assert cfg.get().name == "fromfile"

    def test_optional_missing_file_no_error(self, tmp_path):
        cfg = Config()
        cfg.bind(Settings)
        cfg.add_file(tmp_path / "missing.json", required=False)
        assert cfg.get() is not None


class TestOverride:
    def test_override_returns_overridden_value(self):
        cfg = Config()
        cfg.bind(Settings)
        cfg.add_dict({"name": "base"})
        with cfg.override(name="overridden") as c:
            assert c.get("name") == "overridden"

    def test_override_reverts_after_context(self):
        cfg = Config()
        cfg.add_dict({"name": "base"})
        with cfg.override(name="temp"):
            pass
        assert cfg.get("name") == "base"

    def test_nested_override(self):
        cfg = Config()
        cfg.add_dict({"db": {"host": "base"}})
        with cfg.override(db={"host": "override"}):
            assert cfg.get("db.host") == "override"


class TestFreeze:
    def test_frozen_prevents_add_source(self):
        cfg = Config()
        cfg.freeze()
        with pytest.raises(RuntimeError, match="frozen"):
            cfg.add_dict({"x": 1})

    def test_frozen_prevents_bind(self):
        cfg = Config()
        cfg.freeze()
        with pytest.raises(RuntimeError, match="frozen"):
            cfg.bind(Settings)

    def test_frozen_reads_still_work(self):
        cfg = Config()
        cfg.add_dict({"x": 42})
        cfg.freeze()
        assert cfg.get("x") == 42


class TestSnapshot:
    def test_version_increments(self):
        cfg = Config()
        v0 = cfg.snapshot().version
        cfg.add_dict({"a": 1})
        v1 = cfg.snapshot().version
        assert v1 > v0

    def test_sources_tuple_populated(self):
        cfg = Config()
        cfg.add_dict({"a": 1})
        assert "dict" in cfg.snapshot().sources


class TestReload:
    def test_reload_rebuilds_snapshot(self):
        cfg = Config()
        cfg.bind(Settings)
        cfg.add_dict({"name": "initial"})
        v1 = cfg.snapshot().version
        cfg.reload()
        v2 = cfg.snapshot().version
        assert v2 > v1


class TestOnReload:
    def test_on_reload_called(self):
        import time

        cfg = Config()
        cfg.bind(Settings)
        called: list[tuple] = []

        @cfg.on_reload
        def handler(old, new):
            called.append((old, new))

        cfg.add_dict({"name": "x"})
        time.sleep(0.05)  # daemon thread
        assert len(called) >= 1
