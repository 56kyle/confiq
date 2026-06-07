"""Module defining an environment variable configuration source."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from confiq._types import ListFillBehavior
from confiq.source._base_source import BaseSource


class EnvSource(BaseSource):
    """Maps PREFIX__NESTED__KEY env vars to nested config paths (design_d §5.4).

    Values are raw strings; coercion via ConfigField.parser happens in resolver
    step 5.
    """

    def __init__(
        self,
        prefix: str,
        delimiter: str = "__",
        *,
        mode: ListFillBehavior = "override",
        profile: str | None = None,
    ) -> None: ...

    @property
    def name(self) -> str: ...

    def fetch(self) -> Mapping[str, Any]: ...
