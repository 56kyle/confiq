"""CLI integration subpackage (design_d §10)."""
from __future__ import annotations

from confiq.cli._bind import ConfigBind
from confiq.cli._generate import options_from
from confiq.source._argparse import ArgparseSource  # re-export for convenience


__all__: list[str] = [
    "ConfigBind",
    "options_from",
    "ArgparseSource",
]
