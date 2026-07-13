"""Module defining an environment variable configuration source."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any
from typing import cast

from confiq.source._base_source import BaseSource


class EnvSource(BaseSource):
    """Maps PREFIX__NESTED__KEY env vars to nested config paths (design_d §5.4).

    Values are raw strings; coercion via ConfigField.parser happens in resolver
    step 5.
    """

    def __init__(
        self,
        prefix: str,
        delimiter: str = "__",
        *,
        profile: str | None = None,
    ) -> None:
        self._prefix = prefix
        self._delimiter = delimiter
        self.profile = profile

    @property
    def name(self) -> str:
        return f"env:{self._prefix}"

    def fetch(self) -> Mapping[str, Any]:
        """Nest every env var whose name starts with prefix + delimiter."""
        boundary = f"{self._prefix}{self._delimiter}"
        result: dict[str, Any] = {}
        for key, value in os.environ.items():
            if not key.startswith(boundary):
                continue
            remainder = key[len(boundary) :]
            if not remainder:
                continue
            segments = [segment.lower() for segment in remainder.split(self._delimiter)]
            _insert_nested(result, segments, value)
        return result


def _insert_nested(root: dict[str, Any], segments: list[str], value: str) -> None:
    """Assign value at the nested path, replacing non-dict intermediates as needed."""
    cursor = root
    for segment in segments[:-1]:
        existing: object = cursor.get(segment)
        if isinstance(existing, dict):
            branch = cast("dict[str, Any]", existing)
        else:
            branch = {}
            cursor[segment] = branch
        cursor = branch
    cursor[segments[-1]] = value
