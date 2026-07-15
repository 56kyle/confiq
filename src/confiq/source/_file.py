"""Module defining a file-based configuration source."""

from __future__ import annotations

import urllib.parse
from collections.abc import Mapping
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

from confiq._imports import import_optional
from confiq.exceptions import SourceError
from confiq.exceptions import SourceNotFoundError
from confiq.loader._loader import Loader
from confiq.loader._registry import loader_for_suffix
from confiq.source._base_source import BaseSource


_REMOTE_BACKENDS: dict[str, tuple[str, str]] = {
    "s3": ("s3fs", "s3"),
    "s3a": ("s3fs", "s3"),
    "gs": ("gcsfs", "gcs"),
    "gcs": ("gcsfs", "gcs"),
    "abfs": ("adlfs", "adl"),
    "abfss": ("adlfs", "adl"),
    "adl": ("adlfs", "adl"),
    "az": ("adlfs", "adl"),
}


class FileSource(BaseSource):
    """Reads a local or remote file and parses it via a Loader (design_d §5.3–5.4).

    Local paths use stdlib pathlib; remote URIs (multi-character scheme) delegate
    to fsspec (confiq[remote]), with cloud backends routed to their extra. If loader
    is None, a loader is selected by file suffix. A missing file raises
    SourceNotFoundError when required, else yields an empty mapping (ADR 0040, 0052).
    """

    def __init__(
        self,
        path: str | Path,
        loader: Loader | None = None,
        *,
        required: bool = True,
        profile: str | None = None,
        storage_options: Mapping[str, Any] | None = None,
    ) -> None:
        self._path = Path(path)
        self._raw = str(path)
        self._loader = loader
        self._required = required
        self.profile = profile
        self._storage_options = storage_options
        if storage_options is not None and not self._is_remote(self._raw):
            raise ValueError(
                "storage_options applies only to remote URIs (fsspec backends); "
                f"{self._raw!r} is a local path.",
            )

    @property
    def name(self) -> str:
        return f"file:{self._raw}"

    def fetch(self) -> Mapping[str, Any]:
        """Read and parse the file, wrapping malformed content in SourceError.

        Raises SourceNotFoundError when a required file is missing, SourceError for an
        unknown suffix or wrapped IO/decode failure, and lets a missing loader or
        remote-backend extra's ImportError propagate.
        """
        if self._is_remote(self._raw):
            raw = self._read_remote(self._raw)
            if raw is None:
                return {}
            return self._decode(raw, suffix=self._remote_suffix(self._raw))
        try:
            raw = self._read_local(self._path)
        except FileNotFoundError as error:
            if self._required:
                raise SourceNotFoundError(self.name, f"file not found: {self._path}") from error
            return {}
        except OSError as error:
            raise SourceError(self.name, str(error)) from error
        return self._decode(raw)

    def _decode(self, raw: bytes, *, suffix: str | None = None) -> Mapping[str, Any]:
        resolved_suffix = suffix if suffix is not None else self._path.suffix
        loader = self._loader if self._loader is not None else loader_for_suffix(resolved_suffix)
        if loader is None:
            raise SourceError(self.name, f"no loader for suffix {resolved_suffix!r}")
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
    def _remote_suffix(uri: str) -> str:
        """Loader suffix from the URI path, immune to Windows Path mangling and query strings."""
        return PurePosixPath(urllib.parse.urlsplit(uri).path).suffix

    @staticmethod
    def _read_local(path: Path) -> bytes:
        return path.read_bytes()

    def _read_remote(self, uri: str) -> bytes | None:
        """Read remote bytes via fsspec; None means a missing optional object (ADR 0052).

        Routes known cloud schemes through their extra so a missing backend raises the
        confiq-branded ImportError before fsspec is touched. Raises SourceNotFoundError for
        a missing required object and wraps operational failures in SourceError.
        """
        scheme = urllib.parse.urlsplit(uri).scheme
        backend = _REMOTE_BACKENDS.get(scheme)
        if backend is not None:
            module_name, extra = backend
            _ = import_optional(module_name, extra=extra)
        fsspec = import_optional("fsspec", extra="remote")
        try:
            with fsspec.open(uri, "rb", **(self._storage_options or {})) as handle:  # pyright: ignore[reportAny]  # optional-dep module attr is Any
                return handle.read()  # pyright: ignore[reportAny]  # optional-dep handle is Any
        except FileNotFoundError as error:
            if self._required:
                raise SourceNotFoundError(self.name, f"remote object not found: {uri}") from error
            return None
        except Exception as error:
            raise SourceError(self.name, str(error)) from error
