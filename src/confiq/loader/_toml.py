"""Module defining a TOML loader for configuration data."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class TomlLoader:
    """Parses TOML bytes using stdlib tomllib (Python 3.11+) or tomli (confiq[toml]).

    On Python < 3.11, raises ImportError with install instructions if tomli
    is absent.
    """

    suffixes: frozenset[str] = frozenset({".toml"})

    def parse(self, raw: bytes) -> Mapping[str, Any]: ...
