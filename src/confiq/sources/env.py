"""Config source that reads environment variables."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from confiq.sources._coerce import parse_env_value
from confiq.sources._coerce import set_nested_path
from confiq.sources.base import PRIORITY_ENV
from confiq.sources.base import AbstractConfigSource


class EnvSource(AbstractConfigSource):
    """Reads `os.environ`, strips the configured prefix, and splits on `delimiter` to produce nested keys.

    When `dotenv` is given, its values are merged under the live environment (live env wins).
    """

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
        """Return env-var values as a nested dict after prefix-stripping and delimiter-splitting."""
        env: dict[str, str] = dict(os.environ)
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
    path: Path = Path(dotenv) if not isinstance(dotenv, Path) else dotenv
    return dict(dotenv_values(path))
