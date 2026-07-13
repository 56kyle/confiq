"""Module defining a YAML loader for configuration data."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from confiq._imports import import_optional
from confiq.loader._loader import ensure_mapping


class YamlLoader:
    """Parses YAML bytes via PyYAML (confiq[yaml]).

    Raises ImportError with a helpful message if PyYAML is not installed.
    """

    suffixes: frozenset[str] = frozenset({".yaml", ".yml"})

    def parse(self, raw: bytes) -> Mapping[str, Any]:
        """Parse YAML bytes, treating empty or null documents as an empty mapping.

        Lets PyYAML's error surface for the source to wrap; refuses a non-mapping
        top level.
        """
        yaml = import_optional("yaml", extra="yaml")
        parsed: object = yaml.safe_load(raw)  # pyright: ignore[reportAny]  # optional-dep module attr is Any
        if parsed is None:
            return {}
        return ensure_mapping(parsed)
