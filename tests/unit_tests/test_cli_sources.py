from __future__ import annotations

import argparse
import dataclasses
from typing import Annotated
from unittest.mock import MagicMock

import pytest

from confiq.schema._bind import ConfigBind
from confiq.sources.cli._argparse import ArgparseSource
from confiq.sources.cli._bind import CLI_SOURCE_NAME
from confiq.sources.cli._bind import _set_nested


class TestConfigBind:
    def test_stores_path(self) -> None:
        bind = ConfigBind("database.host")
        assert bind.path == "database.host"

    def test_frozen(self) -> None:
        bind = ConfigBind("x")
        with pytest.raises(dataclasses.FrozenInstanceError):
            bind.path = "y"  # type: ignore[misc]


class TestSetNested:
    def test_empty_path_raises(self) -> None:
        with pytest.raises(ValueError):
            _set_nested({}, "", "x")


class TestClickSource:
    def test_extracts_explicitly_set_param(self) -> None:
        click = pytest.importorskip("click")

        def command(host: Annotated[str, ConfigBind("database.host")] = "localhost") -> None:
            pass

        ctx = MagicMock()
        ctx.params = {"host": "pg"}
        ctx.get_parameter_source.return_value = click.core.ParameterSource.COMMANDLINE

        from confiq.sources.cli._click import ClickSource
        src = ClickSource(ctx, command)
        result = src.fetch()
        assert result == {"database": {"host": "pg"}}

    def test_skips_default_param(self) -> None:
        click = pytest.importorskip("click")

        def command(host: Annotated[str, ConfigBind("database.host")] = "localhost") -> None:
            pass

        ctx = MagicMock()
        ctx.params = {"host": "localhost"}
        ctx.get_parameter_source.return_value = click.core.ParameterSource.DEFAULT

        from confiq.sources.cli._click import ClickSource
        src = ClickSource(ctx, command)
        result = src.fetch()
        assert result == {}

    def test_skips_param_with_no_bind(self) -> None:
        click = pytest.importorskip("click")

        def command(host: str = "localhost") -> None:
            pass

        ctx = MagicMock()
        ctx.params = {"host": "pg"}
        ctx.get_parameter_source.return_value = click.core.ParameterSource.COMMANDLINE

        from confiq.sources.cli._click import ClickSource
        src = ClickSource(ctx, command)
        result = src.fetch()
        assert result == {}

    def test_nested_path_produces_nested_dict(self) -> None:
        click = pytest.importorskip("click")

        def command(port: Annotated[int, ConfigBind("server.port")] = 8080) -> None:
            pass

        ctx = MagicMock()
        ctx.params = {"port": 9090}
        ctx.get_parameter_source.return_value = click.core.ParameterSource.COMMANDLINE

        from confiq.sources.cli._click import ClickSource
        src = ClickSource(ctx, command)
        result = src.fetch()
        assert result == {"server": {"port": 9090}}

    def test_default_name(self) -> None:
        pytest.importorskip("click")
        from confiq.sources.cli._click import ClickSource
        ctx = MagicMock()
        src = ClickSource(ctx, lambda: None)
        assert src.name == CLI_SOURCE_NAME


class TestArgparseSource:
    def test_extracts_explicitly_set_param(self) -> None:
        def command(host: Annotated[str, ConfigBind("database.host")] = "localhost") -> None:
            pass

        parser = argparse.ArgumentParser()
        parser.add_argument("--host", default="localhost")
        namespace = parser.parse_args(["--host", "pg"])

        src = ArgparseSource(namespace, parser, command)
        assert src.fetch() == {"database": {"host": "pg"}}

    def test_skips_default_value(self) -> None:
        def command(host: Annotated[str, ConfigBind("database.host")] = "localhost") -> None:
            pass

        parser = argparse.ArgumentParser()
        parser.add_argument("--host", default="localhost")
        namespace = parser.parse_args([])

        src = ArgparseSource(namespace, parser, command)
        assert src.fetch() == {}

    def test_multiple_params_mixed(self) -> None:
        def command(
            host: Annotated[str, ConfigBind("database.host")] = "localhost",
            port: Annotated[int, ConfigBind("database.port")] = 5432,
        ) -> None:
            pass

        parser = argparse.ArgumentParser()
        parser.add_argument("--host", default="localhost")
        parser.add_argument("--port", type=int, default=5432)
        namespace = parser.parse_args(["--host", "pg"])  # port stays default

        src = ArgparseSource(namespace, parser, command)
        result = src.fetch()
        assert result == {"database": {"host": "pg"}}
        assert "port" not in result.get("database", {})

    def test_default_name(self) -> None:
        parser = argparse.ArgumentParser()
        namespace = parser.parse_args([])
        src = ArgparseSource(namespace, parser, lambda: None)
        assert src.name == CLI_SOURCE_NAME

