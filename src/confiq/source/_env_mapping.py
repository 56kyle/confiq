"""Module containing the shared flat→nested translation used by the env-shaped sources (ADR 0048)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from typing import cast


def flat_to_nested(
    flat: Mapping[str, str | None],
    *,
    prefix: str,
    delimiter: str,
    aliases: Mapping[str, str],
) -> dict[str, Any]:
    """Translate a flat KEY=VALUE mapping into a nested config-path dict (ADR 0048).

    Prefix-convention keys (those under prefix + delimiter, or all keys when prefix is empty) are
    split on the delimiter into lowercased segments and nested. Aliases are applied afterwards, so
    an alias-targeted value wins over a prefix-convention value at the same path: an alias reads the
    flat var it names and places its value at the declared dotted config path verbatim.
    """
    result: dict[str, Any] = {}
    boundary = f"{prefix}{delimiter}" if prefix else ""
    for key, value in flat.items():
        if prefix and not key.startswith(boundary):
            continue
        remainder = key[len(boundary) :]
        if not remainder:
            continue
        segments = [segment.lower() for segment in remainder.split(delimiter)]
        _insert_nested(result, segments, value)
    for target_path, flat_name in aliases.items():
        if flat_name in flat:
            _insert_nested(result, target_path.split("."), flat[flat_name])
    return result


def _insert_nested(root: dict[str, Any], segments: list[str], value: str | None) -> None:
    """Assign value at the nested path, replacing non-dict intermediates as needed."""
    cursor = root
    for segment in segments[:-1]:
        existing: object = cursor.get(segment)
        if isinstance(existing, dict):
            branch = cast("dict[str, Any]", existing)
        else:
            branch = {}
            cursor[segment] = branch
        cursor = branch
    cursor[segments[-1]] = value
