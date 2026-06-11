"""TyperSource: reads explicitly-set Typer parameters."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from confiq._types import MergeMode
from confiq.source._base_source import BaseSource


class TyperSource(BaseSource):
    """Reads explicitly-set Typer parameters (design_d §10.3).

    Typer is Click underneath; this class delegates to ClickSource logic using
    the Click Context available during Typer command execution.

    Requires typer (confiq[cli]).
    """

    def __init__(
        self,
        *,
        mode: MergeMode = MergeMode.OVERRIDE,
        profile: str | None = None,
    ) -> None:
        """Raises ImportError if typer is not installed."""
        ...

    @property
    def name(self) -> str: ...

    def fetch(self) -> Mapping[str, Any]: ...
