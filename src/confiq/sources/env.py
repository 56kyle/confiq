from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from confiq.sources.base import AbstractConfigSource, PRIORITY_ENV
from confiq.sources._coerce import parse_env_value, set_nested_path


class EnvSource(AbstractConfigSource):
    protocol = "env"
    priority = PRIORITY_ENV

    def __init__(
        self,
        *,
        prefix: str = "",
        delimiter: str = "__",
        dotenv: Any = None,
        priority: int | None = None,
    ) -> None:
        super().__init__(priority=priority)
        self.prefix = prefix
        self.delimiter = delimiter
        self.dotenv = dotenv

    def load(self) -> dict[str, Any]:
        env = dict(os.environ)
        if self.dotenv is not None:
            env = {**_parse_dotenv_file(self.dotenv), **env}
        out: dict[str, Any] = {}
        plen = len(self.prefix)
        for k, v in env.items():
            if self.prefix and not k.startswith(self.prefix):
                continue
            key_body = k[plen:]
            parts = key_body.lower().split(self.delimiter)
            set_nested_path(out, parts, parse_env_value(v))
        return out


def _parse_dotenv_file(dotenv: Any) -> dict[str, str]:
    try:
        from dotenv import dotenv_values
    except ImportError:
        from dotenv import dotenv_values  # python-dotenv is a hard dep
    path = Path(dotenv) if not isinstance(dotenv, Path) else dotenv
    return dict(dotenv_values(path))
