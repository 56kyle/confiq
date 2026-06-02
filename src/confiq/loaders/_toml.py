"""Module containing the TOML file loader used throughout the confiq loaders subpackage."""
from __future__ import annotations

from typing import Any


try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

from confiq.exceptions import SourceParseError


class TomlLoader:
    def extensions(self) -> frozenset[str]:
        return frozenset({".toml"})

    def wants_bytes(self) -> bool:
        return True

    def parse(self, data: bytes | str) -> dict[str, Any]:
        raw: str = data.decode("utf-8") if isinstance(data, bytes) else data
        try:
            return tomllib.loads(raw)
        except tomllib.TOMLDecodeError as exc:
            raise SourceParseError(f"TOML parse error: {exc}") from exc
