"""Module defining a TOML loader for configuration data."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from typing import Any

from confiq._imports import import_optional
from confiq.loader._loader import ensure_mapping


class TomlLoader:
    """Parses TOML bytes using stdlib tomllib (Python 3.11+) or tomli (confiq[toml]).

    On Python < 3.11, raises ImportError with install instructions if tomli
    is absent.
    """

    suffixes: frozenset[str] = frozenset({".toml"})

    def parse(self, raw: bytes) -> Mapping[str, Any]:
        """Parse TOML bytes, treating empty input as an empty mapping.

        Lets the decoder's error surface for the source to wrap; refuses a
        non-mapping top level.
        """
        text = raw.decode("utf-8")
        if not text.strip():
            return {}
        if sys.version_info >= (3, 11):
            import tomllib

            module = tomllib
        else:
            module = import_optional("tomli", extra="toml")
        return ensure_mapping(module.loads(text))  # pyright: ignore[reportAny]  # optional-dep module attr is Any
