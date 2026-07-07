"""Module defining a file-based configuration source."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from confiq.loader._loader import Loader
from confiq.source._base_source import BaseSource


class FileSource(BaseSource):
    """Reads a local or remote file and parses it via a Loader (design_d §5.3–5.4).

    Local paths use stdlib pathlib; remote URIs (non-empty scheme) delegate to
    fsspec which requires confiq[remote].  If loader is None, a loader is
    selected by file suffix.
    """

    def __init__(
        self,
        path: str | Path,
        loader: Loader | None = None,
        *,
        profile: str | None = None,
    ) -> None: ...

    @property
    def name(self) -> str: ...

    def fetch(self) -> Mapping[str, Any]: ...

    @staticmethod
    def _is_remote(path: str | Path) -> bool: ...

    @staticmethod
    def _read_local(path: Path) -> bytes: ...

    @staticmethod
    def _read_remote(uri: str) -> bytes:
        """Raises ImportError with helpful install message if fsspec is absent."""
        ...
