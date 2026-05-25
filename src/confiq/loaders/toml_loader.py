from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

from confiq._hookspecs import hookimpl


@hookimpl
def confiq_load_file(path: Path, suffix: str) -> dict[str, Any] | None:
    if suffix == ".toml":
        return tomllib.loads(path.read_text(encoding="utf-8"))
    return None
