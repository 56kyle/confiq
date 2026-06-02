"""Module containing the Loader protocol used throughout the confiq loaders subpackage."""
from __future__ import annotations

from typing import Any
from typing import Protocol
from typing import runtime_checkable


@runtime_checkable
class Loader(Protocol):
    """Pure format parser for a config file's bytes or text content.

    Raises SourceParseError if content is syntactically invalid for the format.
    FileSource is responsible for all I/O; loaders receive pre-read data only.
    """

    def extensions(self) -> frozenset[str]:
        """Return the file suffixes this loader handles (e.g. frozenset({'.json'}))."""
        ...

    def wants_bytes(self) -> bool:
        """Return True if parse() expects bytes, False if it expects a decoded str."""
        ...

    def parse(self, data: bytes | str) -> dict[str, Any]:
        """Parse pre-read file content and return the config dict.

        Raises SourceParseError on malformed content.
        """
        ...
