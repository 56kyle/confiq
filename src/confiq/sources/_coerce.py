from __future__ import annotations

import json
from typing import Any


def _decode_json(text: str) -> dict[str, Any]:
    """JSON-decode text; wrap non-dict results as {"value": result}."""
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
        return {"value": result}
    except json.JSONDecodeError:
        return {"value": text}


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
    cur: dict[str, Any] = d
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
        if not isinstance(cur, dict):
            raise ValueError(
                f"Cannot nest under key {part!r}: existing value is {type(cur).__name__!r}, not a dict"
            )
    cur[parts[-1]] = val
