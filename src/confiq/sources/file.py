from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from confiq.sources.base import AbstractConfigSource, PRIORITY_FILE

if TYPE_CHECKING:
    import pluggy


class FileSource(AbstractConfigSource):
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
        if not self.path.exists():
            if self.required:
                raise FileNotFoundError(self.path)
            return {}
        suffix = (self.file_format or self.path.suffix).lower()
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
        return self.watch_enabled

    def watch(self, on_change: Any) -> Any:
        from confiq._watch import watch_path
        return watch_path(self.path, on_change)
