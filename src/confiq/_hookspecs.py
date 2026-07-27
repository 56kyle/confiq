"""Module defining pluggy hookspecs and the plugin manager factory for confiq."""

from __future__ import annotations

from typing import Any
from typing import cast

import pluggy

from confiq.adapter._dataclass import DataclassAdapter
from confiq.adapter._kinds import is_pydantic_schema
from confiq.adapter._kinds import is_stdlib_dataclass
from confiq.adapter._kinds import is_typed_dict
from confiq.adapter._pydantic import PydanticAdapter
from confiq.adapter._schema_adapter import SchemaAdapter
from confiq.adapter._schemaless import SchemalessAdapter
from confiq.adapter._typeddict import TypedDictAdapter
from confiq.exceptions import SchemaError


hookspec = pluggy.HookspecMarker("confiq")
hookimpl = pluggy.HookimplMarker("confiq")


class ConfiqSpec:
    """Hookspecs for confiq's plugin surface."""

    @hookspec(firstresult=True)
    def confiq_get_schema_adapter(self, schema: type[Any] | None) -> SchemaAdapter[Any] | None:
        """Returns a SchemaAdapter claiming the schema, or None to decline (ADR 0030)."""
        ...


class _BuiltinAdapters:
    """Built-in adapter resolution with positive, mutually-exclusive detection (ADR 0030)."""

    @hookimpl
    def confiq_get_schema_adapter(self, schema: type[Any] | None) -> SchemaAdapter[Any] | None:
        """Claims a built-in schema kind, or returns None for an unclaimed schema."""
        if schema is None:
            return SchemalessAdapter()
        if is_pydantic_schema(schema):
            return PydanticAdapter(schema)
        if is_stdlib_dataclass(schema):
            return DataclassAdapter(schema)
        if is_typed_dict(schema):
            return TypedDictAdapter(schema)
        return None


def make_plugin_manager(extra_plugins: tuple[object, ...] = ()) -> pluggy.PluginManager:
    """Builds the confiq plugin manager: built-in adapters first, spec plugins last (ADR 0030).

    Under pluggy's LIFO call order, registering built-ins first and extra_plugins last
    means user plugins are consulted first and can override any built-in adapter.
    """
    manager = pluggy.PluginManager("confiq")
    manager.add_hookspecs(ConfiqSpec)
    manager.register(_BuiltinAdapters())
    for plugin in extra_plugins:
        manager.register(plugin)
    return manager


def resolve_schema_adapter(manager: pluggy.PluginManager, schema: type[Any] | None) -> SchemaAdapter[Any]:
    """Runs the resolution hook, refusing with SchemaError when no adapter claims the schema (ADR 0030)."""
    adapter = cast("SchemaAdapter[Any] | None", manager.hook.confiq_get_schema_adapter(schema=schema))
    if adapter is None:
        raise SchemaError(f"no schema adapter claims schema type {schema!r}")
    return adapter
