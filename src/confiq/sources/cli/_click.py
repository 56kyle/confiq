"""Module containing the Click and Typer framework source adapters used throughout the confiq package."""
from __future__ import annotations

from collections.abc import Callable
from typing import Annotated
from typing import Any
from typing import get_args
from typing import get_origin
from typing import get_type_hints

from confiq.schema._bind import ConfigBind
from confiq.sources.cli._bind import _set_nested


class ClickSource:
    """Config source that reads explicitly-set Click/Typer CLI parameters.

    Parameters annotated with ConfigBind("dotted.path") in the command function
    contribute their values to the config when set on the command line (not when
    using the parameter default).
    """

    def __init__(self, ctx: Any, command: Callable[..., Any]) -> None:
        try:
            import click  # noqa: F401
        except ImportError:
            raise ImportError(
                "confiq[click] extra is required for ClickSource. "
                "Install it with: pip install confiq[click]"
            ) from None
        self.name: str = "cli"
        self._ctx: Any = ctx
        self._command: Callable[..., Any] = command

    def fetch(self) -> dict[str, Any]:
        from click.core import ParameterSource

        hints: dict[str, Any] = get_type_hints(self._command, include_extras=True)
        result: dict[str, Any] = {}

        for param_name, annotated_type in hints.items():
            if param_name == "return":
                continue
            if get_origin(annotated_type) is not Annotated:
                continue
            bind: ConfigBind | None = next(
                (m for m in get_args(annotated_type)[1:] if isinstance(m, ConfigBind)),
                None,
            )
            if bind is None:
                continue
            if param_name not in self._ctx.params:
                continue
            source = self._ctx.get_parameter_source(param_name)
            if source in (ParameterSource.DEFAULT, ParameterSource.DEFAULT_MAP):
                continue
            _set_nested(result, bind.path, self._ctx.params[param_name])

        return result


TyperSource = ClickSource
