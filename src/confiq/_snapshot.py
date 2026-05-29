from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ResolvedSnapshot:
    """Intermediate result of source merging, passed to pydantic validation."""

    merged: dict[str, Any]
    provenance: dict[str, str]
