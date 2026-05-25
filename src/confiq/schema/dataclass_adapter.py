"""Schema adapter for standard-library dataclasses."""

from __future__ import annotations

import warnings
from dataclasses import MISSING, fields, is_dataclass
from typing import Any


class DataclassAdapter:
    """Validates config dicts against a dataclass, ignoring and warning on unknown keys."""

    def __init__(self, dc_cls: type) -> None:
        """Raises `TypeError` if `dc_cls` is not a dataclass."""
        if not is_dataclass(dc_cls):
            raise TypeError(f"{dc_cls!r} is not a dataclass")
        self.dc_cls = dc_cls

    def validate(self, data: dict[str, Any]) -> Any:
        """Construct the dataclass from `data`, dropping unknown keys and emitting a `UserWarning` for each unknown key."""
        accepted = {f.name for f in fields(self.dc_cls)}
        unknown = set(data) - accepted
        if unknown:
            warnings.warn(
                f"Config keys {sorted(unknown)!r} are not fields of "
                f"{self.dc_cls.__name__!r} and will be ignored.",
                stacklevel=2,
            )
        return self.dc_cls(**{k: v for k, v in data.items() if k in accepted})

    def defaults(self) -> dict[str, Any]:
        """Return fields that have a non-`MISSING` default value."""
        return {f.name: f.default for f in fields(self.dc_cls) if f.default is not MISSING}
