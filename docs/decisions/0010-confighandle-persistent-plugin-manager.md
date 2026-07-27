# 10. ConfigHandle owns a persistent PluginManager

Date: 2026-06-02

## Status

Superseded by [0017](0017-resolution-spec-unified-load-surface.md)

## Context

`confiq_on_reload(old, new)` was defined in `ConfiqSpecs` and documented as running "on daemon thread outside the lock", but the hook was never called. `ConfigHandle.reload()` dispatched subscriber notifications on a daemon thread, but no plugin hook fired alongside them. The hookspec was dead code.

A separate but related issue: `ConfigHandle.create()` called the public `load()` function, and `reload()` called it again on each reload. `load()` calls `_make_plugin_manager()` internally on every invocation, which rebuilds the entire plugin registration from scratch — including `add_hookspecs`, `register(_PydanticAdapterProvider())`, and `load_setuptools_entrypoints`. Plugins passed via `plugins=[...]` to `ConfigHandle.create()` were registered on that first PM and then thrown away; the PM constructed for the second `load()` call on reload had no knowledge of them.

This meant user-registered plugins were silently dropped on every reload cycle.

## Decision

Extract `_load_with_pm()` and `_load_with_pm_async()` as internal functions that accept a pre-built `pluggy.PluginManager` and contain the core load logic. The public `load()` and `load_async()` functions are unchanged — they still construct a fresh PM per call.

`ConfigHandle` constructs its PM once in `create()` and stores it as `self._pm`. All subsequent `reload()` and `reload_async()` calls use `_load_with_pm()` / `_load_with_pm_async()` with the stored PM, preserving user-registered plugins across the lifetime of the handle.

A new `_notify_reload()` function fires `confiq_on_reload` before dispatching subscriber callbacks, both running on the same daemon thread that `reload()` starts after releasing the reentrancy guard. This matches the hookspec's stated contract.

`ConfigHandle.__init__` is updated to accept `pm: pluggy.PluginManager` instead of `plugins: list[object] | None`. The public `ConfigHandle.create()` signature is unchanged.

## Consequences

**Positive:**
- `confiq_on_reload` now fires correctly on every reload, on the same daemon thread as subscriber notifications. The hookspec is no longer dead code.
- User-registered plugins survive across reloads. `ConfigHandle.create(schema, sources=[...], plugins=[MyPlugin()])` behaves consistently between the initial load and all subsequent reloads.
- Plugin manager construction cost is paid once at `create()` time, not on every reload.

**Negative:**
- `reload()` no longer calls the public `load()` function. This is an internal change with no public API impact, but it means the two code paths (public `load()` vs `ConfigHandle.reload()`) now diverge in their PM lifecycle. This is intentional and the reason for the extraction.
- `ConfigHandle.__init__` now takes `pm` instead of `plugins`. Any code constructing `ConfigHandle` directly (bypassing `create()`) must be updated. `ConfigHandle.__init__` is not part of the public API.
