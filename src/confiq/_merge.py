"""Module containing merge logic for combining configuration sources."""
from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from confiq._types import ListFillBehavior


@dataclass(frozen=True)
class ResolvedSnapshot:
    merged: dict[str, Any]
    provenance: dict[str, str]


def deep_merge(
    base: Mapping[str, Any],
    overlay: Mapping[str, Any],
    *,
    mode: ListFillBehavior = "override",
    source_name: str = "",
    provenance: dict[str, str] | None = None,
    path_prefix: str = "",
) -> dict[str, Any]: ...


def merge_sources(
    fetched: Sequence[tuple[str, Mapping[str, Any], ListFillBehavior]],
) -> ResolvedSnapshot: ...
