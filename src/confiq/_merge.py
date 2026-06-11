"""Module containing merge logic for combining configuration sources."""
from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from confiq._types import MergeMode
from confiq._types import Provenance


@dataclass(frozen=True)
class FetchedEntry:
    name: str
    data: Mapping[str, Any]
    mode: MergeMode


@dataclass(frozen=True)
class ResolvedSnapshot:
    merged: dict[str, Any]
    provenance: Provenance


def deep_merge(
    base: Mapping[str, Any],
    overlay: Mapping[str, Any],
    *,
    mode: MergeMode = MergeMode.OVERRIDE,
    source_name: str = "",
    provenance: dict[str, str] | None = None,
    path_prefix: str = "",
) -> dict[str, Any]: ...


def merge_sources(
    fetched: Sequence[FetchedEntry],
) -> ResolvedSnapshot: ...
