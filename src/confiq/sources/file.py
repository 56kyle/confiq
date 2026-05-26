"""Config source that loads a single file via pluggy hook dispatch."""

from __future__ import annotations

from confiq._watch import watch_path

from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from confiq.sources.base import PRIORITY_FILE
from confiq.sources.base import AbstractConfigSource


if TYPE_CHECKING:
    import pluggy


class FileSource(AbstractConfigSource):
    """Loads a config file using the registered loader for its suffix.

    Suffix is resolved from `file_format` if given, otherwise from the path extension.
    Raises `ValueError` for unhandled suffixes; raises `FileNotFoundError` for missing required files.
    """

    protocol = "file"
    priority = PRIORITY_FILE

    def __init__(
        self,
        path: Any,
        *,
        required: bool = True,
        watch: bool = False,
        file_format: str | None = None,
        plugin_manager: pluggy.PluginManager | None = None,
        priority: int | None = None,
    ) -> None:
        super().__init__(priority=priority)
        self.path = Path(path)
        self.required = required
        self.watch_enabled = watch
        self.file_format = file_format
        self._pm = plugin_manager

    def load(self) -> dict[str, Any]:
        """Read and parse the file, returning its contents as a dict.

        Returns `{}` when the file is absent and `required=False`.
        """
        if not self.path.exists():
            if self.required:
                raise FileNotFoundError(self.path)
            return {}
        suffix: str = (self.file_format or self.path.suffix).lower()
        if not suffix.startswith("."):
            suffix = "." + suffix
        if self._pm is None:
            raise RuntimeError("FileSource requires a plugin_manager to load files.")
        result = self._pm.hook.confiq_load_file(path=self.path, suffix=suffix)
        if result is None:
            raise ValueError(
                f"No registered loader handles suffix {suffix!r}. "
                f"Install confiq[yaml] / confiq[toml] or register a custom loader plugin."
            )
        return result

    def supports_watch(self) -> bool:
        """Returns True when `watch=True` was passed at construction."""
        return self.watch_enabled

    def watch(self, on_change: Any) -> Any:
        """Attach a filesystem watcher; calls `on_change` whenever the file changes."""
        return watch_path(self.path, on_change)
