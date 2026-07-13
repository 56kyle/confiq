"""Module defining a file-based configuration source."""

from __future__ import annotations

import urllib.parse
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from confiq.exceptions import SourceError
from confiq.exceptions import SourceNotFoundError
from confiq.loader._loader import Loader
from confiq.loader._registry import loader_for_suffix
from confiq.source._base_source import BaseSource


class FileSource(BaseSource):
    """Reads a local or remote file and parses it via a Loader (design_d §5.3–5.4).

    Local paths use stdlib pathlib; remote URIs (multi-character scheme) delegate
    to fsspec (confiq[remote]), which is not yet wired (ADR 0040). If loader is
    None, a loader is selected by file suffix. A missing local file raises
    SourceNotFoundError when required, else yields an empty mapping (ADR 0040).
    """

    def __init__(
        self,
        path: str | Path,
        loader: Loader | None = None,
        *,
        required: bool = True,
        profile: str | None = None,
    ) -> None:
        self._path = Path(path)
        self._loader = loader
        self._required = required
        self.profile = profile

    @property
    def name(self) -> str:
        return f"file:{self._path}"

    def fetch(self) -> Mapping[str, Any]:
        """Read and parse the file, wrapping malformed content in SourceError.

        Raises SourceNotFoundError when a required file is missing, SourceError for an
        unknown suffix or wrapped IO/decode failure, NotImplementedError for a remote URI,
        and lets a missing loader extra's ImportError propagate.
        """
        if self._is_remote(self._path):
            return self._decode(self._read_remote(str(self._path)))
        try:
            raw = self._read_local(self._path)
        except FileNotFoundError as error:
            if self._required:
                raise SourceNotFoundError(self.name, f"file not found: {self._path}") from error
            return {}
        except OSError as error:
            raise SourceError(self.name, str(error)) from error
        return self._decode(raw)

    def _decode(self, raw: bytes) -> Mapping[str, Any]:
        loader = self._loader if self._loader is not None else loader_for_suffix(self._path.suffix)
        if loader is None:
            raise SourceError(self.name, f"no loader for suffix {self._path.suffix!r}")
        try:
            return loader.parse(raw)
        except ImportError:
            raise
        except Exception as error:
            raise SourceError(self.name, str(error)) from error

    @staticmethod
    def _is_remote(path: str | Path) -> bool:
        """True for a multi-character URI scheme; a single-letter drive is local."""
        scheme = urllib.parse.urlsplit(str(path)).scheme
        return len(scheme) > 1

    @staticmethod
    def _read_local(path: Path) -> bytes:
        return path.read_bytes()

    @staticmethod
    def _read_remote(uri: str) -> bytes:
        """Remote file reads land in a later stage; raises NotImplementedError (ADR 0040)."""
        raise NotImplementedError(
            f"remote FileSource is not wired yet ({uri}); it lands in a later stage. "
            f"Install confiq[remote] once available.",
        )
