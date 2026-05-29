from __future__ import annotations

from pathlib import Path
from typing import Any

import pluggy

from confiq._plugins import _make_plugin_manager
from confiq.errors import SourceParseError
from confiq.errors import SourceUnavailableError


class FileSource:
    def __init__(
        self,
        path: Path | str,
        *,
        required: bool = True,
        name: str = "file",
        plugin_manager: pluggy.PluginManager | None = None,
    ) -> None:
        self.name: str = name
        self._path: Path = Path(path)
        self._required: bool = required
        self._plugin_manager: pluggy.PluginManager | None = plugin_manager

    def fetch(self) -> dict[str, Any]:
        pm: pluggy.PluginManager = (
            self._plugin_manager if self._plugin_manager is not None else _make_plugin_manager()
        )
        result: dict[str, Any] | None = pm.hook.confiq_load_file(path=self._path)
        if result is not None:
            return result
        if not self._path.exists():
            if self._required:
                raise SourceUnavailableError(
                    f"Config file not found: {self._path!r}"
                )
            return {}
        raise SourceParseError(f"No handler for {self._path.suffix!r}")
