"""TyperSource: reads explicitly-set Typer parameters (design_d §10.3, ADR 0027)."""

from __future__ import annotations

from typing import ClassVar

from confiq.source._click import ClickSource


class TyperSource(ClickSource):
    """Reads explicitly-set Typer parameters as raw bindings, sharing ClickSource's mechanism.

    A Typer command's context is structurally a Click context, so this subclass reuses ClickSource's
    snapshot capture verbatim (ADR 0035, no drift) and differs only in where it looks for the active
    context, the extra it requires, and its provenance name.

    Requires typer (confiq[typer]).
    """

    _NAME: ClassVar[str] = "cli:typer"
    _FRAMEWORK: ClassVar[str] = "Typer"
    _EXTRA_MODULE: ClassVar[str] = "typer"
    _INSTALL_EXTRA: ClassVar[str] = "typer"
    # typer>=0.26 vendors Click at the private, unstable typer._click; older typer pushes onto the
    # real click stack, so both are tried in that order.
    _CONTEXT_STACK_MODULES: ClassVar[tuple[str, ...]] = ("typer._click.globals", "click.globals")
