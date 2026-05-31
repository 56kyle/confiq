"""Module containing the TOML file loader used throughout the confiq loaders subpackage."""
from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

from confiq.exceptions import SourceParseError


if TYPE_CHECKING:
    from pathlib import Path


class TomlLoader:
    def load(self, path: Path) -> dict[str, Any] | None:
        if path.suffix != ".toml":
            return None
        try:
            with path.open("rb") as f:
                return tomllib.load(f)
        except tomllib.TOMLDecodeError as exc:
            raise SourceParseError(f"TOML parse error in {path}: {exc}") from exc
        except FileNotFoundError:
            return None
