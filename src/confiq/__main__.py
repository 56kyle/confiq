"""Command-line interface for confiq."""
from __future__ import annotations

import importlib
import json
from typing import TYPE_CHECKING

import typer

from confiq._load import load
from confiq.exceptions import SourceParseError
from confiq.exceptions import SourceUnavailableError
from confiq.sources._file import FileSource


if TYPE_CHECKING:
    from pathlib import Path


app: typer.Typer = typer.Typer(help="confiq — inspect and validate config files.")

@app.command()
def show(
    path: Path = typer.Argument(..., help="Config file to display (JSON, YAML, TOML, INI)."),
) -> None:
    """Pretty-print a config file's merged content."""
    try:
        cfg = load(sources=[FileSource(path)])
    except SourceUnavailableError:
        typer.echo(f"error: file not found: {path}", err=True)
        raise typer.Exit(1)
    except SourceParseError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(dict(cfg), indent=2))

@app.command()
def validate(
    path: Path = typer.Argument(..., help="Config file to validate."),
    schema: str | None = typer.Option(
        None, "--schema", "-s",
        help="Dotted import path to a pydantic BaseModel, e.g. myapp.config:Settings.",
    ),
) -> None:
    """Validate a config file, optionally against a pydantic schema."""
    try:
        source = FileSource(path)
        if schema is None:
            load(sources=[source])
        else:
            module_path, _, class_name = schema.rpartition(":")
            if not module_path or not class_name:
                typer.echo(
                    f"error: --schema must be 'module.path:ClassName', got {schema!r}",
                    err=True,
                )
                raise typer.Exit(1)
            try:
                mod = importlib.import_module(module_path)
                schema_cls = getattr(mod, class_name)
            except (ImportError, AttributeError) as exc:
                typer.echo(f"error: could not import schema {schema!r}: {exc}", err=True)
                raise typer.Exit(1)
            load(schema_cls, sources=[source])
    except SourceUnavailableError:
        typer.echo(f"error: file not found: {path}", err=True)
        raise typer.Exit(1)
    except SourceParseError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1)
    except Exception as exc:
        typer.echo(f"validation failed: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo("ok")

if __name__ == "__main__":
    app()  # pragma: no cover
