"""Module containing the YAML file loader used throughout the confiq loaders subpackage."""
from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

import yaml

from confiq.exceptions import SourceParseError


if TYPE_CHECKING:
    from pathlib import Path


class YamlLoader:
    def load(self, path: Path) -> dict[str, Any] | None:
        if path.suffix not in {".yaml", ".yml"}:
            return None
        try:
            return yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            raise SourceParseError(f"YAML parse error in {path}: {exc}") from exc
        except FileNotFoundError:
            return None
