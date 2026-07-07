"""Module defining a .env file configuration source."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from confiq.source._base_source import BaseSource


class DotenvSource(BaseSource):
    """Reads a .env file via python-dotenv (confiq[dotenv]).

    Raises ImportError with a helpful install message if python-dotenv is
    absent. Values are raw strings; coercion via ConfigField.parser happens in
    the resolver's step 5.
    """

    def __init__(
        self,
        path: str | Path = ".env",
        *,
        profile: str | None = None,
    ) -> None: ...

    @property
    def name(self) -> str: ...

    def fetch(self) -> Mapping[str, Any]: ...
