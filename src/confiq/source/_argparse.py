"""Module defining an argparse-backed binding source (design_d §10.3, ADR 0027)."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from collections.abc import Sequence

from confiq._cli import ConfigBind
from confiq.source._base_source import BaseSource
from confiq.source._source import RawBinding


class ArgparseSource(BaseSource):
    """Reads explicitly-set arguments from a parsed argparse.Namespace as raw bindings (ADR 0027).

    A binding source (ADR 0049): it surfaces raw argument names + markers, which the resolver maps
    to config paths against the schema path table. Only explicitly-set arguments participate. The
    preferred detection is argparse's SUPPRESS default (an unset argument is simply absent from the
    namespace); passing parser enables the degraded fallback of skipping any value equal to the
    parser's default. bind_map is argparse's marker channel: a {arg_name: "dotted.path"} entry
    becomes that argument's explicit ConfigBind; unmapped names fall to the name↔path convention.
    """

    def __init__(
        self,
        namespace: argparse.Namespace,
        parser: argparse.ArgumentParser | None = None,
        bind_map: Mapping[str, str] | None = None,
        *,
        profile: str | None = None,
    ) -> None:
        self._bindings: tuple[RawBinding, ...] = _argparse_bindings(namespace, parser, bind_map or {})
        self.profile = profile

    @property
    def name(self) -> str:
        return "cli:argparse"

    def raw_bindings(self) -> Sequence[RawBinding]:
        return self._bindings


def _argparse_bindings(
    namespace: argparse.Namespace,
    parser: argparse.ArgumentParser | None,
    bind_map: Mapping[str, str],
) -> tuple[RawBinding, ...]:
    """Snapshot each explicitly-set namespace argument as a RawBinding (ADR 0027)."""
    values: dict[str, object] = vars(namespace)
    bindings: list[RawBinding] = []
    for name, value in values.items():
        if parser is not None:
            default: object = parser.get_default(name)  # pyright: ignore[reportAny]  # argparse get_default is Any
            if value == default:
                continue
        marker = ConfigBind(bind_map[name]) if name in bind_map else None
        bindings.append(RawBinding(name, value, marker))
    return tuple(bindings)
