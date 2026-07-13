"""Module defining an environment variable configuration source."""

from __future__ import annotations

import os
from collections.abc import Mapping
from collections.abc import Sequence
from typing import Any

from confiq.source._base_source import BaseSource
from confiq.source._env_mapping import flat_to_nested


class EnvSource(BaseSource):
    """Maps PREFIX__NESTED__KEY env vars to nested config paths (design_d §5.4, ADR 0048).

    Values are raw strings; coercion via ConfigField.parser happens in resolver step 5. An
    aliases map reads a specifically-named var into a declared config path, winning over the
    prefix convention at that path; the resolver validates alias targets against the schema.
    """

    def __init__(
        self,
        prefix: str,
        delimiter: str = "__",
        *,
        aliases: Mapping[str, str] | None = None,
        profile: str | None = None,
    ) -> None:
        self._prefix = prefix
        self._delimiter = delimiter
        self._aliases: dict[str, str] = dict(aliases or {})
        self.profile = profile

    @property
    def name(self) -> str:
        return f"env:{self._prefix}"

    @property
    def alias_targets(self) -> Sequence[str]:
        return tuple(self._aliases)

    def fetch(self) -> Mapping[str, Any]:
        """Nest every prefixed env var, then overlay alias-targeted values (ADR 0048)."""
        return flat_to_nested(
            dict(os.environ),
            prefix=self._prefix,
            delimiter=self._delimiter,
            aliases=self._aliases,
        )
