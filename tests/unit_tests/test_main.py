"""Test cases for the __main__ module."""
from __future__ import annotations

import json
import sys
import types

import pytest
from typer.testing import CliRunner

from confiq import __main__
from confiq.__main__ import app


@pytest.fixture
def runner() -> CliRunner:
    """Fixture for invoking command-line interfaces."""
    return CliRunner()


def test_main_succeeds(runner: CliRunner) -> None:
    """Invoking --help exits 0 and shows usage text."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "show" in result.output or "confiq" in result.output


class TestShowCommand:
    def test_show_prints_json(self, runner, tmp_path):
        f = tmp_path / "cfg.json"
        f.write_text(json.dumps({"host": "pg", "port": 5432}))
        result = runner.invoke(app, ["show", str(f)])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["host"] == "pg"
        assert parsed["port"] == 5432

    def test_show_file_not_found(self, runner, tmp_path):
        result = runner.invoke(app, ["show", str(tmp_path / "missing.json")])
        assert result.exit_code == 1

    def test_show_nested_config_serializes_correctly(self, runner, tmp_path):
        f = tmp_path / "cfg.json"
        f.write_text(json.dumps({"database": {"host": "pg"}}))
        result = runner.invoke(app, ["show", str(f)])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["database"]["host"] == "pg"


class TestValidateCommand:
    def test_validate_parseable_file_exits_ok(self, runner, tmp_path):
        f = tmp_path / "cfg.json"
        f.write_text('{"name": "alice"}')
        result = runner.invoke(app, ["validate", str(f)])
        assert result.exit_code == 0
        assert "ok" in result.output

    def test_validate_file_not_found(self, runner, tmp_path):
        result = runner.invoke(app, ["validate", str(tmp_path / "missing.json")])
        assert result.exit_code == 1

    def test_validate_bad_schema_format_exits_1(self, runner, tmp_path):
        f = tmp_path / "cfg.json"
        f.write_text("{}")
        result = runner.invoke(app, ["validate", str(f), "--schema", "no-colon-here"])
        assert result.exit_code == 1

    def test_validate_unknown_module_exits_1(self, runner, tmp_path):
        f = tmp_path / "cfg.json"
        f.write_text("{}")
        result = runner.invoke(app, ["validate", str(f), "--schema", "nonexistent.module:Settings"])
        assert result.exit_code == 1

    def test_validate_with_valid_schema_exits_ok(self, runner, tmp_path, monkeypatch):
        from pydantic import BaseModel

        class Settings(BaseModel):
            name: str

        fake_mod = types.ModuleType("_test_confiq_schema")
        fake_mod.Settings = Settings  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "_test_confiq_schema", fake_mod)

        f = tmp_path / "cfg.json"
        f.write_text('{"name": "alice"}')
        result = runner.invoke(app, ["validate", str(f), "--schema", "_test_confiq_schema:Settings"])
        assert result.exit_code == 0
        assert "ok" in result.output

    def test_validate_schema_mismatch_exits_1(self, runner, tmp_path, monkeypatch):
        from pydantic import BaseModel

        class Settings(BaseModel):
            name: str

        fake_mod = types.ModuleType("_test_confiq_schema2")
        fake_mod.Settings = Settings  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "_test_confiq_schema2", fake_mod)

        f = tmp_path / "cfg.json"
        f.write_text('{"wrong_field": 1}')
        result = runner.invoke(app, ["validate", str(f), "--schema", "_test_confiq_schema2:Settings"])
        assert result.exit_code == 1
