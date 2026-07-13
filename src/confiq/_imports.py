"""Module containing the optional-dependency import guard used across the confiq package."""

from __future__ import annotations

import importlib
from types import ModuleType


def import_optional(module_name: str, *, extra: str) -> ModuleType:
    """Import a module backing an optional extra, or raise a guiding ImportError.

    The raised ImportError names the extra so the caller can install it; this is a
    programmer install-time error, deliberately not a SourceError (ADR 0006).
    """
    try:
        return importlib.import_module(module_name)
    except ImportError as error:
        raise ImportError(
            f"confiq requires the '{extra}' extra for this feature: pip install confiq[{extra}]",
        ) from error
