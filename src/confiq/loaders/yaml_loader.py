"""Optional YAML file loader hookimpl (requires PyYAML or ruamel.yaml)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

import yaml  # raises ImportError if confiq[yaml] not installed

from confiq._hookspecs import hookimpl


if TYPE_CHECKING:
    from pathlib import Path


@hookimpl
def confiq_load_file(path: Path, suffix: str) -> dict[str, Any] | None:
    """Parse a YAML file and return its contents as a dict. Returns `None` for non-`.yaml`/`.yml` suffixes."""
    if suffix in (".yaml", ".yml"):
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return None
