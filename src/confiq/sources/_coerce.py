from __future__ import annotations

from typing import Any


def parse_env_value(v: str) -> Any:
    """Infer scalar type from a string env-var value."""
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    if v.lstrip("-").isdigit():
        return int(v)
    try:
        return float(v)
    except ValueError:
        pass
    return v


def set_nested_path(d: dict[str, Any], parts: list[str], val: Any) -> None:
    """Assign val into d at the nested key path described by parts."""
    cur = d
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = val
