"""Module containing the shared import-requirement guard used throughout the confiq cloud subpackage."""

from __future__ import annotations

import importlib


def _require(package: str, extra: str) -> None:
    try:
        importlib.import_module(package)
    except ImportError:
        raise ImportError(
            f"confiq[{extra}] extra is required. Install it with: pip install confiq[{extra}]"
        ) from None
