from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml  # raises ImportError if confiq[yaml] not installed

from confiq._hookspecs import hookimpl


@hookimpl
def confiq_load_file(path: Path, suffix: str) -> dict[str, Any] | None:
    if suffix in (".yaml", ".yml"):
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return None
