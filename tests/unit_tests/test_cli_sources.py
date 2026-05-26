"""Tests for ClickSource and TyperSource."""
from __future__ import annotations

import pytest

from confiq.sources.click_source import ClickSource
from confiq.sources.typer_source import TyperSource
from confiq.sources.base import PRIORITY_CLI


class TestClickSource:
    def test_flat_params_returned(self):
        src = ClickSource({"host": "pg", "port": 5432})
        assert src.load() == {"host": "pg", "port": 5432}

    def test_none_values_skipped(self):
        src = ClickSource({"host": "pg", "debug": None})
        assert "debug" not in src.load()

    def test_delimiter_splits_to_nested(self):
        src = ClickSource({"database__host": "pg"})
        assert src.load() == {"database": {"host": "pg"}}

    def test_custom_delimiter(self):
        src = ClickSource({"db_host": "pg"}, delimiter="_")
        assert src.load() == {"db": {"host": "pg"}}

    def test_no_delimiter(self):
        src = ClickSource({"database__host": "pg"}, delimiter="")
        assert src.load() == {"database__host": "pg"}

    def test_keys_lowercased(self):
        src = ClickSource({"HOST": "pg"})
        assert "host" in src.load()

    def test_priority_is_cli(self):
        assert ClickSource({}).priority == PRIORITY_CLI

    def test_custom_priority(self):
        src = ClickSource({}, priority=99)
        assert src.priority == 99

    def test_accepts_context_duck_type(self):
        class FakeCtx:
            params = {"name": "myapp"}

        src = ClickSource(FakeCtx())
        assert src.load() == {"name": "myapp"}

    def test_protocol(self):
        assert ClickSource.protocol == "click"

    def test_supports_watch_false(self):
        assert not ClickSource({}).supports_watch()

    def test_config_add_click(self):
        from confiq._core import Config

        cfg = Config()
        cfg.add_click({"name": "from_click"})
        assert cfg.get("name") == "from_click"

    def test_click_overrides_env(self, monkeypatch):
        from confiq._core import Config

        monkeypatch.setenv("MYAPP_NAME", "from_env")
        cfg = Config()
        cfg.add_env(prefix="MYAPP_")
        cfg.add_click({"name": "from_click"})
        assert cfg.get("name") == "from_click"


class TestTyperSource:
    def test_flat_params_returned(self):
        src = TyperSource({"host": "pg", "port": 5432})
        assert src.load() == {"host": "pg", "port": 5432}

    def test_none_values_skipped(self):
        src = TyperSource({"host": "pg", "debug": None})
        assert "debug" not in src.load()

    def test_private_names_skipped(self):
        src = TyperSource({"host": "pg", "_ctx": "private"})
        assert "_ctx" not in src.load()
        assert "host" in src.load()

    def test_delimiter_splits_to_nested(self):
        src = TyperSource({"database__host": "pg"})
        assert src.load() == {"database": {"host": "pg"}}

    def test_priority_is_cli(self):
        assert TyperSource({}).priority == PRIORITY_CLI

    def test_protocol(self):
        assert TyperSource.protocol == "typer"

    def test_supports_watch_false(self):
        assert not TyperSource({}).supports_watch()

    def test_config_add_typer(self):
        from confiq._core import Config

        cfg = Config()
        cfg.add_typer({"name": "from_typer"})
        assert cfg.get("name") == "from_typer"

    def test_typer_nested_delimiter(self):
        from confiq._core import Config

        cfg = Config()
        cfg.add_typer({"database__host": "pg"})
        assert cfg.get("database.host") == "pg"
