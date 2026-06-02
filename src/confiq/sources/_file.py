"""Module containing the file-based config source used throughout the confiq package."""
from __future__ import annotations

from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

import fsspec

from confiq.exceptions import SourceParseError
from confiq.exceptions import SourceUnavailableError
from confiq.loaders import Loader
from confiq.loaders import default_loaders


class FileSource:
    def __init__(
        self,
        path: str | Path,
        *,
        required: bool = True,
        name: str = "file",
        loaders: list[Loader] | None = None,
    ) -> None:
        self.name: str = name
        self._path: str = str(path)
        self._required: bool = required
        self._loaders: list[Loader] = loaders if loaders is not None else default_loaders()

    def fetch(self) -> dict[str, Any]:
        clean: str = self._path.split("?")[0]
        suffix: str = (
            PurePosixPath(clean).suffix.lower()
            if "://" in clean
            else Path(clean).suffix.lower()
        )
        loader: Loader | None = next(
            (l for l in self._loaders if suffix in l.extensions()), None
        )
        if loader is None:
            raise SourceParseError(f"No handler for {suffix!r}")

        raw_bytes: bytes
        try:
            with fsspec.open(self._path, "rb") as f:
                raw_bytes = f.read()
        except FileNotFoundError:
            if self._required:
                raise SourceUnavailableError(
                    f"Config file not found: {self._path!r}"
                ) from None
            return {}

        data: bytes | str = raw_bytes if loader.wants_bytes() else raw_bytes.decode("utf-8")
        return loader.parse(data)
