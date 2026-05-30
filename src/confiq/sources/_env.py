"""Module containing the environment variable config source used throughout the confiq package."""

from __future__ import annotations

import os
from typing import Any

from confiq.sources._coerce import coerce_env_value
from confiq.sources._coerce import set_nested


class EnvSource:
    def __init__(
        self,
        prefix: str = "",
        delimiter: str = "__",
        *,
        name: str = "env",
    ) -> None:
        self.name: str = name
        self._prefix: str = prefix
        self._delimiter: str = delimiter

    def fetch(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for raw_key, raw_value in os.environ.items():
            key: str
            if self._prefix:
                if not raw_key.startswith(self._prefix):
                    continue
                key = raw_key[len(self._prefix):]
            else:
                key = raw_key
            key = key.lower()
            parts: list[str] = key.split(self._delimiter)
            set_nested(result, parts, coerce_env_value(raw_value))
        return result
