"""Schema adapter for pydantic BaseModel subclasses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class PydanticAdapter:
    """Validates config dicts against a pydantic BaseModel and extracts its defaults."""

    def __init__(self, model_cls: type) -> None:
        """Raises `TypeError` if `model_cls` is not a pydantic BaseModel subclass."""
        if not (isinstance(model_cls, type) and issubclass(model_cls, BaseModel)):
            raise TypeError(f"{model_cls!r} is not a pydantic BaseModel")
        self.model_cls = model_cls

    def validate(self, data: dict[str, Any]) -> Any:
        """Call `model_validate` and return the validated model instance."""
        return self.model_cls.model_validate(data)

    def defaults(self) -> dict[str, Any]:
        """Return the model's default values via `model_dump()`. Falls back to `model_construct()` for models with required fields."""
        try:
            return self.model_cls().model_dump()
        except Exception:
            return self.model_cls.model_construct().model_dump()
