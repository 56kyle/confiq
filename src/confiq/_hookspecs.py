"""Module defining pluggy hookspecs and the plugin manager factory for confiq."""
from __future__ import annotations

from typing import Any

import pluggy

from confiq.adapter._schema_adapter import SchemaAdapter


hookspec = pluggy.HookspecMarker("confiq")
hookimpl = pluggy.HookimplMarker("confiq")


class ConfiqSpec:
    @hookspec(firstresult=True)
    def confiq_get_schema_adapter(
        self,
        schema: type[Any] | None,
    ) -> SchemaAdapter[Any] | None: ...


def make_plugin_manager(
    extra_plugins: tuple[object, ...] = (),
) -> pluggy.PluginManager: ...
