"""Integration tests pinning the Stage 7 CLI binding sources against REAL frameworks (ADR 0027, 0032).

These drive click / typer / argparse end to end: a real command is invoked, a real CLI source is
constructed inside it (grabbing the ambient context per ADR 0032), and load() resolves the binding
against a nested schema's path table. No mocks — the seam under test is the framework ↔ binding-source
↔ resolver chain, so the frameworks are driven for real via their own CliRunners.
"""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

import click
import pytest
import typer
from click.testing import CliRunner
from pydantic import BaseModel
from typer.testing import CliRunner as TyperCliRunner
from typing_extensions import Annotated
from typing_extensions import Protocol

from confiq import ArgparseSource
from confiq import ClickSource
from confiq import ConfigBind
from confiq import MemorySource
from confiq import TyperSource
from confiq import load
from confiq import options_from
from confiq._cli import _confiq_option_type
from confiq.exceptions import ConfigValidationError


if TYPE_CHECKING:
    from collections.abc import Mapping


class Database(BaseModel):
    host: str
    port: int


class Schema(BaseModel):
    database: Database


class _OptionView(Protocol):
    """Typed view over a generated ConfiqOption (its click base is Any at the boundary)."""

    @property
    def confiq_path(self) -> str: ...
    @property
    def default(self) -> object: ...
    @property
    def opts(self) -> list[str]: ...


_BASE: Mapping[str, Any] = {"database": {"host": "base-host", "port": 1}}


def test_click_source_lets_explicitly_set_options_win_at_their_bound_paths() -> None:
    captured: dict[str, Schema] = {}

    @click.command()
    @click.option("--database-host")
    @click.option("--db-port")
    @click.option("--verbose", is_flag=True)
    def cmd(
        database_host: str,
        db_port: Annotated[str, ConfigBind("database.port")],
        verbose: bool,
    ) -> None:
        captured["cfg"] = load(Schema, [MemorySource(_BASE), ClickSource()])

    result = CliRunner().invoke(cmd, ["--database-host", "cli-host", "--db-port", "8080"])

    assert result.exit_code == 0, result.output
    assert captured["cfg"].database.host == "cli-host"
    assert captured["cfg"].database.port == 8080


def test_click_source_with_unset_option_does_not_contribute_leaving_base_intact() -> None:
    captured: dict[str, Schema] = {}

    @click.command()
    @click.option("--database-host")
    @click.option("--db-port")
    def cmd(database_host: str, db_port: Annotated[str, ConfigBind("database.port")]) -> None:
        captured["cfg"] = load(Schema, [MemorySource(_BASE), ClickSource()])

    result = CliRunner().invoke(cmd, ["--db-port", "8080"])

    assert result.exit_code == 0, result.output
    assert captured["cfg"].database.host == "base-host"
    assert captured["cfg"].database.port == 8080


def test_click_source_bad_cli_value_provenance_names_cli_click() -> None:
    @click.command()
    @click.option("--db-port")
    def cmd(db_port: Annotated[str, ConfigBind("database.port")]) -> None:
        load(Schema, [MemorySource(_BASE), ClickSource()])

    result = CliRunner().invoke(cmd, ["--db-port", "notanum"])

    assert isinstance(result.exception, ConfigValidationError)
    assert result.exception.field_path == "database.port"
    assert result.exception.sources == ("cli:click",)


def test_click_source_replays_a_frozen_snapshot_without_a_live_context() -> None:
    captured: dict[str, ClickSource] = {}

    @click.command()
    @click.option("--db-port")
    def cmd(db_port: Annotated[str, ConfigBind("database.port")]) -> None:
        captured["source"] = ClickSource()

    result = CliRunner().invoke(cmd, ["--db-port", "8080"])

    assert result.exit_code == 0, result.output
    source = captured["source"]
    assert list(source.raw_bindings()) == list(source.raw_bindings())


def test_click_source_constructed_outside_an_invocation_raises_runtime_error() -> None:
    with pytest.raises(RuntimeError, match="Click"):
        ClickSource()


def test_typer_source_binds_via_convention_and_config_bind_through_typer_wrapping() -> None:
    captured: dict[str, Schema] = {}
    app = typer.Typer()

    @app.command()
    def main(
        database_host: Annotated[str, typer.Option()] = "unset",
        db_port: Annotated[str, typer.Option(), ConfigBind("database.port")] = "unset",
    ) -> None:
        captured["cfg"] = load(Schema, [MemorySource(_BASE), TyperSource()])

    result = TyperCliRunner().invoke(app, ["--database-host", "typer-host", "--db-port", "8080"])

    assert result.exit_code == 0, result.output
    assert captured["cfg"].database.host == "typer-host"
    assert captured["cfg"].database.port == 8080


def test_argparse_source_with_suppress_defaults_only_contributes_set_args() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-host", dest="database_host", default=argparse.SUPPRESS)
    parser.add_argument("--db-port", dest="db_port", default=argparse.SUPPRESS)
    namespace = parser.parse_args(["--db-port", "8080"])

    result = load(
        Schema,
        [MemorySource(_BASE), ArgparseSource(namespace, bind_map={"db_port": "database.port"})],
    )

    assert isinstance(result, Schema)
    assert result.database.host == "base-host"
    assert result.database.port == 8080


def test_argparse_source_with_parser_skips_values_equal_to_default() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-host", dest="database_host", default="base-host")
    unset = parser.parse_args([])
    set_arg = parser.parse_args(["--database-host", "cli-host"])

    unset_bindings = ArgparseSource(unset, parser=parser).raw_bindings()
    set_bindings = ArgparseSource(set_arg, parser=parser).raw_bindings()

    assert unset_bindings == ()
    assert [binding.name for binding in set_bindings] == ["database_host"]


def test_argparse_source_binds_unmapped_arg_via_convention() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-host", dest="database_host", default=argparse.SUPPRESS)
    namespace = parser.parse_args(["--database-host", "cli-host"])

    result = load(Schema, [MemorySource(_BASE), ArgparseSource(namespace)])

    assert isinstance(result, Schema)
    assert result.database.host == "cli-host"
    assert result.database.port == 1


def test_options_from_emits_one_confiq_option_per_leaf_with_path_and_unset_default() -> None:
    option_type = cast("type[object]", _confiq_option_type())
    options = cast("list[_OptionView]", options_from(Schema))

    assert all(isinstance(option, option_type) for option in options)
    assert {option.confiq_path for option in options} == {"database.host", "database.port"}
    assert all(option.default is None for option in options)


def test_options_from_flag_round_trips_the_name_path_convention() -> None:
    options = cast("list[_OptionView]", options_from(Schema))

    flags = {option.confiq_path: option.opts[0] for option in options}

    assert flags["database.host"] == "--database-host"
    assert flags["database.port"] == "--database-port"


def test_options_from_generated_command_binds_end_to_end() -> None:
    captured: dict[str, Schema] = {}

    def callback(**_kwargs: object) -> None:
        captured["cfg"] = load(Schema, [MemorySource(_BASE), ClickSource()])

    command = click.Command("gen", params=options_from(Schema), callback=callback)

    result = CliRunner().invoke(command, ["--database-host", "cli-host"])

    assert result.exit_code == 0, result.output
    assert captured["cfg"].database.host == "cli-host"
    assert captured["cfg"].database.port == 1
