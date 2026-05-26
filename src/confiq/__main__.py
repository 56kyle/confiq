"""Command-line interface for confiq."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer

from confiq._core import Config


app: typer.Typer = typer.Typer(help="confiq — inspect and validate config files.")


@app.command()
def show(
    path: Path = typer.Argument(..., help="Config file to display (JSON, YAML, TOML, INI)."),
    output_format: str = typer.Option("json", "--format", "-f", help="Output format: json."),
) -> None:
    """Pretty-print a config file's merged content."""
    cfg = Config()
    try:
        cfg.add_file(path)
    except FileNotFoundError:
        typer.echo(f"error: file not found: {path}", err=True)
        raise typer.Exit(1)
    except ValueError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1)

    snap = cfg.snapshot()
    typer.echo(json.dumps(dict(snap.raw), indent=2, default=str))


@app.command()
def validate(
    path: Path = typer.Argument(..., help="Config file to validate."),
    schema: Optional[str] = typer.Option(
        None,
        "--schema",
        "-s",
        help="Dotted import path to a pydantic BaseModel, e.g. myapp.config:Settings.",
    ),
) -> None:
    """Validate a config file, optionally against a pydantic schema.

    Without --schema, confirms the file is parseable. With --schema, also
    validates all required fields and types.
    """
    cfg = Config()
    try:
        cfg.add_file(path)
    except FileNotFoundError:
        typer.echo(f"error: file not found: {path}", err=True)
        raise typer.Exit(1)
    except ValueError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1)

    if schema is not None:
        module_path, _, class_name = schema.rpartition(":")
        if not module_path or not class_name:
            typer.echo(
                f"error: --schema must be in 'module.path:ClassName' form, got {schema!r}",
                err=True,
            )
            raise typer.Exit(1)
        try:
            import importlib
            mod = importlib.import_module(module_path)
            schema_cls = getattr(mod, class_name)
        except (ImportError, AttributeError) as exc:
            typer.echo(f"error: could not import schema {schema!r}: {exc}", err=True)
            raise typer.Exit(1)

        try:
            cfg.bind(schema_cls)
        except Exception as exc:
            typer.echo(f"validation failed: {exc}", err=True)
            raise typer.Exit(1)

    typer.echo("ok")


if __name__ == "__main__":
    app()  # pragma: no cover
