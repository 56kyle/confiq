"""Schema adapter for TypedDict classes (pass-through; no runtime validation)."""

from __future__ import annotations

from typing import Any


class TypedDictAdapter:
    """Lightweight pass-through adapter for TypedDict — returns the dict unchanged since TypedDict has no runtime validation."""

    def __init__(self, td_cls: type) -> None:
        """Store `td_cls` for introspection; no validation performed."""
        self.td_cls = td_cls

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """Return `data` unchanged."""
        return data

    def defaults(self) -> dict[str, Any]:
        """Return `{}` — TypedDict provides no runtime default values."""
        return {}
