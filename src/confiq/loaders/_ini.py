"""Module containing the INI/CFG file loader used throughout the confiq loaders subpackage."""
from __future__ import annotations

import configparser
import io
from typing import Any

from confiq.exceptions import SourceParseError


class IniLoader:
    def extensions(self) -> frozenset[str]:
        return frozenset({".ini", ".cfg"})

    def wants_bytes(self) -> bool:
        return False

    def parse(self, data: bytes | str) -> dict[str, Any]:
        text: str = data.decode("utf-8") if isinstance(data, bytes) else data
        cp: configparser.ConfigParser = configparser.ConfigParser()
        try:
            cp.read_string(text)
            return {s: dict(cp[s]) for s in cp.sections()}
        except configparser.Error as exc:
            raise SourceParseError(f"INI parse error: {exc}") from exc
