"""Module containing merge logic for combining configuration sources."""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from typing import cast

from confiq._types import Provenance


@dataclass(frozen=True)
class FetchedEntry:
    name: str
    data: Mapping[str, Any]


@dataclass(frozen=True)
class ResolvedSnapshot:
    merged: Mapping[str, Any]
    provenance: Provenance


def merge_sources(fetched: Sequence[FetchedEntry]) -> ResolvedSnapshot:
    """Fold fetched sources low → high into a single snapshot (ADR 0023, 0037).

    Later entries win on collision; provenance records the winning source per
    leaf (ADR 0003).
    """
    merged: dict[str, Any] = {}
    provenance: dict[str, str] = {}
    for entry in fetched:
        _deep_merge(merged, entry.data, entry.name, provenance, "")
    return ResolvedSnapshot(merged=merged, provenance=provenance)


def _deep_merge(
    base: dict[str, object],
    overlay: Mapping[str, object],
    source_name: str,
    provenance: dict[str, str],
    path_prefix: str,
) -> None:
    """Recursively merge overlay into base, co-producing provenance (ADR 0037).

    Uniform overwrite: type conflicts replace wholesale and never raise;
    validation downstream is the refusal locus. Lists replace wholesale with no
    per-element paths (ADR 0026). None overwrites.
    """
    for key, incoming in overlay.items():
        path = f"{path_prefix}.{key}" if path_prefix else key
        current = base.get(key)
        if isinstance(incoming, Mapping):
            if isinstance(current, dict):
                target = cast("dict[str, object]", current)
            else:
                target = {}
                base[key] = target
                _ = provenance.pop(path, None)
            _deep_merge(target, cast("Mapping[str, object]", incoming), source_name, provenance, path)
        else:
            base[key] = incoming
            provenance[path] = source_name
            _purge_descendants(provenance, path)


def _purge_descendants(provenance: dict[str, str], path: str) -> None:
    """Drop stale provenance entries for a subtree replaced by a leaf (ADR 0037)."""
    prefix = f"{path}."
    stale = [key for key in provenance if key.startswith(prefix)]
    for key in stale:
        del provenance[key]
