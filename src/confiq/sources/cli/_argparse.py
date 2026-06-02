"""Module containing the argparse framework source adapter used throughout the confiq package."""
from __future__ import annotations

import argparse
from collections.abc import Callable
from typing import Annotated
from typing import Any
from typing import get_args
from typing import get_origin
from typing import get_type_hints

from confiq.schema._bind import ConfigBind
from confiq.sources.cli._bind import CLI_SOURCE_NAME
from confiq.sources.cli._bind import _set_nested


class ArgparseSource:
    """Config source that reads explicitly-set argparse CLI arguments.

    Parameters annotated with ConfigBind("dotted.path") in the command function
    contribute their values to the config when their parsed value differs from the
    parser's registered default.
    """

    def __init__(
        self,
        namespace: argparse.Namespace,
        parser: argparse.ArgumentParser,
        command: Callable[..., Any],
    ) -> None:
        self.name: str = CLI_SOURCE_NAME
        self._namespace: argparse.Namespace = namespace
        self._parser: argparse.ArgumentParser = parser
        self._command: Callable[..., Any] = command

    def fetch(self) -> dict[str, Any]:
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
            if not hasattr(self._namespace, param_name):
                continue
            actual: Any = getattr(self._namespace, param_name)
            default: Any = self._parser.get_default(param_name)
            if actual == default:
                continue
            _set_nested(result, bind.path, actual)

        return result
