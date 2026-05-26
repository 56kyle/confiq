from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from confiq.sources._coerce import set_nested_path
from confiq.sources.base import PRIORITY_CLI
from confiq.sources.base import AbstractConfigSource


if TYPE_CHECKING:
    import click


class ClickSource(AbstractConfigSource):
    """Reads typed parameter values from a Click Context or params dict.

    Keys are split on `delimiter` (default ``__``) to produce nested config structure.
    ``None``-valued parameters (un-set Click options) are silently skipped.
    """

    protocol = "click"
    priority = PRIORITY_CLI

    def __init__(
        self,
        ctx_or_params: click.Context | dict[str, Any],
        *,
        delimiter: str = "__",
        priority: int | None = None,
    ) -> None:
        super().__init__(priority=priority)
        if hasattr(ctx_or_params, "params"):
            self._params: dict[str, Any] = dict(ctx_or_params.params)
        else:
            self._params = dict(ctx_or_params)
        self._delimiter = delimiter

    def load(self) -> dict[str, Any]:
        """Return Click parameters as a nested dict, split on the configured delimiter."""
        out: dict[str, Any] = {}
        for k, v in self._params.items():
            if v is None:
                continue
            parts = k.split(self._delimiter) if self._delimiter else [k]
            set_nested_path(out, [p.lower() for p in parts], v)
        return out
