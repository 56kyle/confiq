"""Module defining an argparse-backed configuration source."""
from __future__ import annotations

import argparse
from collections.abc import Mapping
from typing import Any

from confiq._types import ListFillBehavior
from confiq.source._base_source import BaseSource


class ArgparseSource(BaseSource):
    """Consumes an already-parsed argparse.Namespace (design_d §5.4, §10.3).

    Only explicitly-set arguments contribute.  Detection: if parser is supplied,
    values equal to parser.get_default() are skipped; otherwise all non-None
    values are included.  bind_map maps param names to dotted config paths.
    """

    def __init__(
        self,
        namespace: argparse.Namespace,
        parser: argparse.ArgumentParser | None = None,
        bind_map: dict[str, str] | None = None,
        *,
        mode: ListFillBehavior = "override",
        profile: str | None = None,
    ) -> None: ...

    @property
    def name(self) -> str: ...

    def fetch(self) -> Mapping[str, Any]: ...
