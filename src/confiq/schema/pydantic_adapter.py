from __future__ import annotations

from typing import Any


class PydanticAdapter:
    def __init__(self, model_cls: type) -> None:
        from pydantic import BaseModel

        if not (isinstance(model_cls, type) and issubclass(model_cls, BaseModel)):
            raise TypeError(f"{model_cls!r} is not a pydantic BaseModel")
        self.model_cls = model_cls

    def validate(self, data: dict[str, Any]) -> Any:
        return self.model_cls.model_validate(data)

    def defaults(self) -> dict[str, Any]:
        try:
            return self.model_cls().model_dump()
        except Exception:
            return self.model_cls.model_construct().model_dump()
