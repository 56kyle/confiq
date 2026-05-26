"""Immutable config state container published after each rebuild."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any
from typing import Generic
from typing import TypeVar


T = TypeVar("T")

_MISSING = object()


def _to_dict(obj: Any) -> Any:
    if isinstance(obj, MappingProxyType):
        return {k: _to_dict(v) for k, v in obj.items()}
    if isinstance(obj, tuple):
        return [_to_dict(x) for x in obj]
    return obj


@dataclass(frozen=True, slots=True)
class ConfigSnapshot(Generic[T]):
    """Immutable, fully-built config state. Readers get one of these; no lock needed.

    See ADR 0001 for the atomic reference-swap design.
    """

    model: T | None
    raw: MappingProxyType  # type: ignore[type-arg]
    version: int
    sources: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return raw config data as a plain, JSON-serializable dict."""
        return _to_dict(self.raw)

    def get(
        self,
        dotted: str,
        default: Any = _MISSING,
        *,
        cast: Any = None,
    ) -> Any:
        """Traverse `raw` by dotted path and return the leaf, applying `cast` if given. Raises `KeyError` when the path is absent and no `default` is provided."""
        node: Any = self.raw
        for part in dotted.split("."):
            if isinstance(node, (dict, MappingProxyType)) and part in node:
                node = node[part]
            else:
                if default is _MISSING:
                    raise KeyError(dotted)
                return default
        return cast(node) if cast is not None else node
