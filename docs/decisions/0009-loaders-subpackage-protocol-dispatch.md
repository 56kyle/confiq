# 9. Loaders subpackage with protocol dispatch

Date: 2026-05-31

## Status

Accepted; superseded in part by ADR 0042 (the `Loader` protocol becomes
`parse(raw: bytes)`, and `FileSource` takes a single `loader` with suffix dispatch rather
than a `loaders: list`). The subpackage structure and plugin-decoupling rationale stand.

## Context

`confiq._plugins` previously served two distinct roles:

1. **Plugin infrastructure** — the pluggy `PluginManager` factory, hookspec registration, and lifecycle hook implementations.
2. **File format implementations** — `_JsonLoader`, `_IniLoader`, `_YamlLoader`, `_TomlLoader`, each decorated with `@hookimpl` for the `confiq_load_file` hookspec.

These are different abstraction levels in the same module. More concretely, `confiq_load_file` used `firstresult=True`, making it a chain-of-responsibility where the first loader whose suffix matched would win. This is structurally distinct from the fan-out lifecycle hooks (`confiq_pre_load`, `confiq_post_load`, `confiq_on_error`, `confiq_on_reload`) and the discovery hook (`confiq_get_schema_adapter`) that genuinely benefit from pluggy's broadcast model.

The mixing produced a concrete coupling problem: `FileSource` imported and called `_make_plugin_manager()` directly to obtain a plugin manager for file loading. When a user passed `plugins=[MyCustomLoader()]` to `load()`, those plugins were registered on the `_load.py` plugin manager but not on the separate one `FileSource` created — silently ignoring custom `confiq_load_file` implementations.

Optional loaders (`_YamlLoader`, `_TomlLoader`) were also defined as inner classes inside a function (`_register_optional_loaders`), making them untestable in isolation.

## Decision

Introduce a `confiq.loaders` subpackage that mirrors the structure of `confiq.sources`:

- `_protocol.py` — a `runtime_checkable` `Loader` protocol with a single `load(path) -> dict | None` method.
- `_json.py`, `_ini.py`, `_yaml.py`, `_toml.py` — one class per file, each a top-level name.
- `__init__.py` — exports `Loader`, the concrete built-in loaders, and `default_loaders()`.

`FileSource` accepts a `loaders: list[Loader] | None` parameter (defaults to `default_loaders()` resolved at construction time) and dispatches file loading as a simple forward-iteration list, returning on the first non-`None` result. It no longer imports from `_plugins`.

`confiq_load_file` is removed from `_hookspecs.py`. `_plugins.py` retains only the schema adapter (`_PydanticAdapterProvider`) and the lifecycle plugin infrastructure.

## Consequences

**Positive:**
- `FileSource` is self-contained; it has no dependency on the plugin system.
- Loaders are independently testable and directly importable.
- Custom file format support is explicit — `FileSource("x.custom", loaders=[MyLoader(), *default_loaders()])` — rather than implicit via a global plugin manager.
- The `confiq_load_file` silently-ignored-custom-plugins bug is eliminated by design.
- Optional loaders (`YamlLoader`, `TomlLoader`) guard their imports at module level; `ImportError` is handled at the `default_loaders()` callsite.

**Negative:**
- Custom file loaders can no longer be registered via `load(plugins=[...])`. They must be passed per `FileSource`. This is a breaking change for any code using `confiq_load_file` hookimpl plugins.
- The `plugin_manager` parameter previously accepted by `FileSource.__init__` is removed. Any code injecting a custom plugin manager for file loading must migrate to the `loaders` parameter.
