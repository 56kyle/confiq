"""Module defining a YAML loader for configuration data."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class YamlLoader:
    """Parses YAML bytes via PyYAML (confiq[yaml]).

    Raises ImportError with a helpful message if PyYAML is not installed.
    """

    suffixes: frozenset[str] = frozenset({".yaml", ".yml"})

    def parse(self, raw: bytes) -> Mapping[str, Any]: ...
