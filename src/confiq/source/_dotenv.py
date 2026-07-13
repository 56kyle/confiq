"""Module defining a .env file configuration source."""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from typing import cast

from confiq._imports import import_optional
from confiq.exceptions import SourceError
from confiq.exceptions import SourceNotFoundError
from confiq.source._base_source import BaseSource
from confiq.source._env_mapping import flat_to_nested


_DELIMITER = "__"


class DotenvSource(BaseSource):
    """Reads a .env file via python-dotenv (confiq[dotenv]).

    A .env file is env-shaped, so its keys nest by the same delimiter convention as EnvSource
    (KEY__NESTED); an aliases map reads a specifically-named var into a declared config path,
    winning over the convention at that path (ADR 0048). A missing file yields an empty mapping
    unless required (ADR 0040); the [dotenv] extra is imported only when the file is present.
    Values are raw strings; coercion via ConfigField.parser happens in the resolver's step 5.
    """

    def __init__(
        self,
        path: str | Path = ".env",
        *,
        aliases: Mapping[str, str] | None = None,
        required: bool = False,
        profile: str | None = None,
    ) -> None:
        self._path = Path(path)
        self._aliases: dict[str, str] = dict(aliases or {})
        self._required = required
        self.profile = profile

    @property
    def name(self) -> str:
        return f"dotenv:{self._path}"

    @property
    def alias_targets(self) -> Sequence[str]:
        return tuple(self._aliases)

    def fetch(self) -> Mapping[str, Any]:
        """Read the .env file into a nested mapping, wrapping IO errors in SourceError.

        Raises SourceNotFoundError when a required file is missing, and lets the missing
        [dotenv] extra's ImportError propagate.
        """
        if not self._path.exists():
            if self._required:
                raise SourceNotFoundError(self.name, f"file not found: {self._path}")
            return {}
        dotenv = import_optional("dotenv", extra="dotenv")
        try:
            values = cast(
                "dict[str, str | None]",
                dotenv.dotenv_values(self._path),  # pyright: ignore[reportAny]  # optional-dep module attr is Any
            )
        except OSError as error:
            raise SourceError(self.name, str(error)) from error
        return flat_to_nested(values, prefix="", delimiter=_DELIMITER, aliases=self._aliases)
