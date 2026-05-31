"""Module containing the file-based config source used throughout the confiq package."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from confiq.exceptions import SourceParseError
from confiq.exceptions import SourceUnavailableError
from confiq.loaders import Loader
from confiq.loaders import default_loaders


class FileSource:
    def __init__(
        self,
        path: Path | str,
        *,
        required: bool = True,
        name: str = "file",
        loaders: list[Loader] | None = None,
    ) -> None:
        self.name: str = name
        self._path: Path = Path(path)
        self._required: bool = required
        self._loaders: list[Loader] = loaders if loaders is not None else default_loaders()

    def fetch(self) -> dict[str, Any]:
        loader: Loader
        for loader in self._loaders:
            result: dict[str, Any] | None = loader.load(self._path)
            if result is not None:
                return result
        if not self._path.exists():
            if self._required:
                raise SourceUnavailableError(
                    f"Config file not found: {self._path!r}"
                )
            return {}
        raise SourceParseError(f"No handler for {self._path.suffix!r}")
