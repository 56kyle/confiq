"""Module defining a JSON loader for configuration data."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from confiq.loader._loader import ensure_mapping


class JsonLoader:
    """Parses JSON bytes via stdlib json (no extra required)."""

    suffixes: frozenset[str] = frozenset({".json"})

    def parse(self, raw: bytes) -> Mapping[str, Any]:
        """Parse JSON bytes, treating empty input as an empty mapping.

        Lets json.JSONDecodeError surface for the source to wrap; refuses a
        non-mapping top level.
        """
        if not raw.strip():
            return {}
        return ensure_mapping(json.loads(raw))  # pyright: ignore[reportAny]  # stdlib json returns Any
