"""ClickSource: reads explicitly-set Click parameters."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from confiq.source._base_source import BaseSource


class ClickSource(BaseSource):
    """Reads explicitly-set Click parameters from the active Context (design_d §10.3).

    Uses Context.get_parameter_source() to distinguish user-supplied values from
    framework defaults. ConfigBind annotations on parameters override the
    name-convention mapping.

    Requires click (confiq[cli]).
    """

    def __init__(
        self,
        *,
        profile: str | None = None,
    ) -> None:
        """Capture the current Click Context at construction time.

        Raises ImportError if click is not installed.
        Raises RuntimeError if called outside a Click command invocation.
        """
        ...

    @property
    def name(self) -> str: ...

    def fetch(self) -> Mapping[str, Any]: ...
