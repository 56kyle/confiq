"""TyperSource: reads explicitly-set Typer parameters (design_d §10.3, ADR 0027)."""

from __future__ import annotations

from typing import ClassVar

from confiq.source._click import ClickSource


class TyperSource(ClickSource):
    """Reads explicitly-set Typer parameters as raw bindings, sharing ClickSource's mechanism.

    Typer runs on Click, so a Typer command's context is a Click context; this subclass reuses
    ClickSource's snapshot capture verbatim (ADR 0035, no drift) and differs only in the extra it
    requires and its provenance name.

    Requires typer (confiq[cli]).
    """

    _NAME: ClassVar[str] = "cli:typer"
    _FRAMEWORK: ClassVar[str] = "Typer"
    _EXTRA_MODULE: ClassVar[str] = "typer"
