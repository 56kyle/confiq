from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Generic, TypeVar

T = TypeVar("T")

_MISSING = object()


@dataclass(frozen=True, slots=True)
class ConfigSnapshot(Generic[T]):
    """Immutable, fully-built config state. Readers get one of these; no lock needed.

    See ADR 0001 for the atomic reference-swap design.
    """

    model: T | None
    raw: MappingProxyType  # type: ignore[type-arg]
    version: int
    sources: tuple[str, ...]

    def get(
        self,
        dotted: str,
        default: Any = _MISSING,
        *,
        cast: Any = None,
    ) -> Any:
        node: Any = self.raw
        for part in dotted.split("."):
            if isinstance(node, (dict, MappingProxyType)) and part in node:
                node = node[part]
            else:
                if default is _MISSING:
                    raise KeyError(dotted)
                return default
        return cast(node) if cast is not None else node
