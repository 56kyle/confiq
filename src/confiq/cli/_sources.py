"""Module defining Click and Typer sources for CLI-driven configuration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from confiq._types import ListFillBehavior
from confiq.source._base_source import BaseSource


class ClickSource(BaseSource):
    """Reads explicitly-set Click parameters from the active Context (design_d §10.3).

    Uses Context.get_parameter_source() to distinguish user-supplied values from
    framework defaults. ConfigBind annotations on parameters override the
    name-convention mapping.

    Requires click (confiq[cli]).
    """

    def __init__(
        self,
        *,
        mode: ListFillBehavior = "override",
        profile: str | None = None,
    ) -> None:
        """Capture the current Click Context at construction time.

        Raises ImportError if click is not installed.
        Raises RuntimeError if called outside a Click command invocation.
        """
        ...

    @property
    def name(self) -> str: ...

    def fetch(self) -> Mapping[str, Any]: ...


class TyperSource(BaseSource):
    """Reads explicitly-set Typer parameters (design_d §10.3).

    Typer is Click underneath; this class delegates to ClickSource logic using
    the Click Context available during Typer command execution.

    Requires typer (confiq[cli]).
    """

    def __init__(
        self,
        *,
        mode: ListFillBehavior = "override",
        profile: str | None = None,
    ) -> None:
        """Raises ImportError if typer is not installed."""
        ...

    @property
    def name(self) -> str: ...

    def fetch(self) -> Mapping[str, Any]: ...
