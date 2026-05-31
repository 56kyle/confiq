"""Module containing the INI/CFG file loader used throughout the confiq loaders subpackage."""
from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any


if TYPE_CHECKING:
    from pathlib import Path


class IniLoader:
    def load(self, path: Path) -> dict[str, Any] | None:
        if path.suffix not in {".ini", ".cfg"}:
            return None
        if not path.exists():
            return None
        import configparser

        cp: configparser.ConfigParser = configparser.ConfigParser()
        cp.read(path)
        return {s: dict(cp[s]) for s in cp.sections()}
