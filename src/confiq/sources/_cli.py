"""Module containing the CLI argument config source used throughout the confiq package."""

from __future__ import annotations

import sys
from typing import Any

from confiq.sources._coerce import coerce_env_value
from confiq.sources._coerce import set_nested


class CliSource:
    def __init__(
        self,
        argv: list[str] | None = None,
        *,
        name: str = "cli",
    ) -> None:
        self.name: str = name
        self._argv: list[str] | None = argv

    def fetch(self) -> dict[str, Any]:
        raw: list[str] = self._argv if self._argv is not None else sys.argv[1:]
        tokens: list[str] = []
        for token in raw:
            if token == "--":
                break
            tokens.append(token)

        result: dict[str, Any] = {}
        i: int = 0
        while i < len(tokens):
            token: str = tokens[i]
            if not token.startswith("--"):
                i += 1
                continue

            body: str = token[2:]

            key: str
            value_str: str
            coerced_value: Any
            if "=" in body:
                key, value_str = body.split("=", 1)
                coerced_value = coerce_env_value(value_str)
            elif (
                i + 1 < len(tokens)
                and not tokens[i + 1].startswith("--")
            ):
                key = body
                coerced_value = coerce_env_value(tokens[i + 1])
                i += 1
            else:
                key = body
                coerced_value = True

            if not key:
                raise ValueError("empty key")

            parts: list[str] = key.split(".")
            for part in parts:
                if not part:
                    raise ValueError("empty segment in key")

            _check_path_conflict(result, parts)
            set_nested(result, parts, coerced_value)
            i += 1

        return result


def _check_path_conflict(d: dict[str, Any], parts: list[str]) -> None:
    node: Any = d
    for _depth, part in enumerate(parts[:-1]):
        if part not in node:
            return
        node = node[part]
        if not isinstance(node, dict):
            raise ValueError("path conflict")
    if parts[-1] in node and isinstance(node[parts[-1]], dict):
        raise ValueError("path conflict")
