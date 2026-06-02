"""Module containing the JSON file loader used throughout the confiq loaders subpackage."""
from __future__ import annotations

import json
from typing import Any

from confiq.exceptions import SourceParseError


class JsonLoader:
    def extensions(self) -> frozenset[str]:
        return frozenset({".json"})

    def wants_bytes(self) -> bool:
        return False

    def parse(self, data: bytes | str) -> dict[str, Any]:
        try:
            return json.loads(data)
        except json.JSONDecodeError as exc:
            raise SourceParseError(f"JSON parse error: {exc}") from exc
