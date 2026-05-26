from __future__ import annotations


"""Config source that reads from argparse namespaces or raw argv."""

import sys
from typing import Any

from confiq.sources._coerce import parse_env_value
from confiq.sources._coerce import set_nested_path
from confiq.sources.base import PRIORITY_CLI
from confiq.sources.base import AbstractConfigSource


class ArgparseSource(AbstractConfigSource):
    """Reads CLI arguments from a parsed `argparse.Namespace` or a raw `argv` list using `--key.sub.path=value` dot syntax.

    Defaults to `sys.argv[1:]` when both `namespace` and `argv` are None.
    """

    protocol = "argparse"
    priority = PRIORITY_CLI

    def __init__(
        self,
        namespace: Any = None,
        *,
        argv: list[str] | None = None,
        priority: int | None = None,
    ) -> None:
        super().__init__(priority=priority)
        self._ns = namespace
        self._argv = sys.argv[1:] if (namespace is None and argv is None) else argv

    def load(self) -> dict[str, Any]:
        """Return CLI arguments as a nested dict, using underscore-split for a namespace or dot-path parsing for raw argv."""
        if self._ns is not None:
            return _explode_dots(vars(self._ns))
        return _parse_dotted(self._argv or [])


def _explode_dots(ns_dict: dict[str, Any]) -> dict[str, Any]:
    """Convert {'database_host': 'x'} → {'database': {'host': 'x'}} using underscores."""
    out: dict[str, Any] = {}
    for k, v in ns_dict.items():
        if v is None:
            continue
        parts = k.split("_")
        set_nested_path(out, parts, v)
    return out


def _parse_dotted(argv: list[str]) -> dict[str, Any]:
    """Parse --key.sub.path=value or --key.sub.path value from an argv list."""
    out: dict[str, Any] = {}
    for i, arg in enumerate(argv):
        if arg == "--":
            break
        if not arg.startswith("--"):
            continue
        stripped = arg[2:]
        if "=" in stripped:
            key, value_str = stripped.split("=", 1)
            val: Any = parse_env_value(value_str)
        else:
            key = stripped
            next_arg = argv[i + 1] if i + 1 < len(argv) else None
            val = parse_env_value(next_arg) if next_arg is not None and not next_arg.startswith("--") else True
        if any(seg == "" for seg in key.split(".")):
            raise ValueError(f"invalid argument key: {arg!r}")
        try:
            set_nested_path(out, key.split("."), val)
        except (TypeError, AttributeError) as err:
            raise ValueError(f"argument '--{key}' conflicts with earlier value at an ancestor key") from err
    return out
