"""Module containing the Click and Typer framework source adapters used throughout the confiq package."""
from __future__ import annotations

from collections.abc import Callable
from typing import Annotated
from typing import Any
from typing import get_args
from typing import get_origin
from typing import get_type_hints

from confiq.schema._bind import ConfigBind
from confiq.sources.cli._bind import CLI_SOURCE_NAME
from confiq.sources.cli._bind import _set_nested


class ClickSource:
    """Config source that reads explicitly-set Click/Typer CLI parameters.

    Pass the Click command or group (or Typer app). At fetch time the source
    captures the active Click context from Click's internal stack and reads
    ConfigBind annotations from the currently-executing command's callback.
    """

    def __init__(self, app_or_command: Any) -> None:
        try:
            import click  # noqa: F401
        except ImportError:
            raise ImportError(
                "confiq[click] extra is required for ClickSource. "
                "Install it with: pip install confiq[click]"
            ) from None
        self.name: str = CLI_SOURCE_NAME
        self._app_or_command: Any = app_or_command

    def fetch(self) -> dict[str, Any]:
        import click
        from click.core import ParameterSource

        try:
            ctx: Any = click.get_current_context()
        except RuntimeError:
            return {}

        callback: Callable[..., Any] | None = ctx.command.callback
        if callback is None:
            return {}

        hints: dict[str, Any] = get_type_hints(callback, include_extras=True)
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
            if param_name not in ctx.params:
                continue
            source = ctx.get_parameter_source(param_name)
            if source in (ParameterSource.DEFAULT, ParameterSource.DEFAULT_MAP):
                continue
            _set_nested(result, bind.path, ctx.params[param_name])

        return result


TyperSource = ClickSource
