"""Module defining a JSON loader for configuration data."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class JsonLoader:
    """Parses JSON bytes via stdlib json (no extra required)."""

    suffixes: frozenset[str] = frozenset({".json"})

    def parse(self, raw: bytes) -> Mapping[str, Any]: ...
