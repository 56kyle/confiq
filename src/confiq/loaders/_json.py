"""Module containing the JSON file loader used throughout the confiq loaders subpackage."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any

from confiq.exceptions import SourceParseError


if TYPE_CHECKING:
    from pathlib import Path


class JsonLoader:
    def load(self, path: Path) -> dict[str, Any] | None:
        if path.suffix != ".json":
            return None
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise SourceParseError(f"JSON parse error in {path}: {exc}") from exc
        except FileNotFoundError:
            return None
