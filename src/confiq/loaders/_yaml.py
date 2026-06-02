"""Module containing the YAML file loader used throughout the confiq loaders subpackage."""
from __future__ import annotations

from typing import Any

import yaml

from confiq.exceptions import SourceParseError


class YamlLoader:
    def extensions(self) -> frozenset[str]:
        return frozenset({".yaml", ".yml"})

    def wants_bytes(self) -> bool:
        return False

    def parse(self, data: bytes | str) -> dict[str, Any]:
        try:
            return yaml.safe_load(data)
        except yaml.YAMLError as exc:
            raise SourceParseError(f"YAML parse error: {exc}") from exc
