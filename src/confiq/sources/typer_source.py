"""Config source that reads typed parameter values from a Typer command's locals."""

from __future__ import annotations

from typing import Any

from confiq.sources._coerce import set_nested_path
from confiq.sources.base import PRIORITY_CLI
from confiq.sources.base import AbstractConfigSource


class TyperSource(AbstractConfigSource):
    """Reads typed parameter values from a Typer command's local namespace.

    Pass ``locals()`` from inside a Typer command function. Private names
    (starting with ``_``) are skipped. Keys are split on `delimiter`
    (default ``__``) to produce nested config structure.
    ``None``-valued parameters (un-set Typer options) are silently skipped.
    """

    protocol = "typer"
    priority = PRIORITY_CLI

    def __init__(
        self,
        params: dict[str, Any],
        *,
        delimiter: str = "__",
        priority: int | None = None,
    ) -> None:
        super().__init__(priority=priority)
        self._params = {k: v for k, v in params.items() if not k.startswith("_")}
        self._delimiter = delimiter

    def load(self) -> dict[str, Any]:
        """Return Typer parameters as a nested dict, split on the configured delimiter."""
        out: dict[str, Any] = {}
        for k, v in self._params.items():
            if v is None:
                continue
            parts = k.split(self._delimiter) if self._delimiter else [k]
            set_nested_path(out, [p.lower() for p in parts], v)
        return out
