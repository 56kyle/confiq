"""Module containing the ConfigBind annotation marker used throughout the confiq package."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConfigBind:
    """Annotation marker that binds a CLI parameter to a dotted config path.

    Used in CLI function parameter annotations alongside framework-specific option
    markers (typer.Option, click.option, etc.) to declare which config field the
    parameter feeds when explicitly set on the command line.
    """

    path: str
