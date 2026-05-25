from __future__ import annotations

from typing import Any


class TypedDictAdapter:
    def __init__(self, td_cls: type) -> None:
        self.td_cls = td_cls

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        return data

    def defaults(self) -> dict[str, Any]:
        return {}
