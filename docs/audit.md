# confiq Code Audit

Qualitative review against the `python-dev` / `python-reviewer` ethos.
Scope: all source modules under `src/confiq/` and all test files under `tests/`.
Not a ruff or basedpyright pass — style and type errors caught by those tools are excluded.

---

## Critical

### [resource-leak] `src/confiq/_plugins.py:114`

`tomllib.load(path.open("rb"))` opens a file handle with no context manager. The handle leaks on every TOML load.

```python
# fix
with path.open("rb") as f:
    return tomllib.load(f)
```

---

## Stepping stones without a terminus

Both items below require either a new ADR documenting the intended wiring and timeline, or removal until the feature is needed.

### [stepping-stone] `src/confiq/_hookspecs.py:53-59` + `src/confiq/_load.py:96-97`

`confiq_transform_value` is fully specified in the hook system but never called anywhere in the implementation. The inline comment on `_load.py:96-97` reads `# not driven inline in v1` — that is not a stated terminus. No ADR exists documenting when, how, or under what conditions this hook will be wired. The comment on lines 96–97 exists solely because of this gap and disappears when the gap is resolved.

### [stepping-stone] `src/confiq/_merge.py:20-25`

`_freeze()` is implemented and tested but never called in production code. Same resolution required: an ADR that names the terminus, or removal until it is needed.

---

## Naming subverts expectations

### [naming] `src/confiq/_resolver.py:89`

`_collect_leaves()` reads like a pure function that returns collected leaves. Its actual contract is to mutate the `provenance` dict passed as an argument, returning `None`. A reader who follows the name will miss the side effect entirely.

Rename to `_record_provenance()` or `_index_leaves_into()`, or refactor to return the provenance updates and merge at the call site.

---

## Type-hint gaps

### [type-hint] `src/confiq/_load.py:45`

`SchemalessConfig.__iter__` returns `Any`. The `Mapping[str, Any]` protocol requires the iterator to yield keys; the return type should be `Iterator[str]`.

### [type-hint] `src/confiq/_load.py:85`

`_resolve_config(..., pm: Any)` — `pluggy.PluginManager` is already imported under `TYPE_CHECKING` at line 25. Use it.

### [type-hint] `src/confiq/_merge.py:9`

`deep_merge(base: dict, overlay: Mapping) -> dict` with `# type: ignore[type-arg]` papers over missing generic args. Change to `dict[str, Any]` / `Mapping[str, Any]` and remove the suppression.

---

## Consistency gap in error handling

### [consistency] `src/confiq/_plugins.py:34-43`

`_JsonLoader` explicitly catches `FileNotFoundError` and returns `None` (line 30). `_IniLoader` does not. For `_IniLoader`, a missing file causes `configparser.read()` to silently return an empty parser, which is a different failure mode rather than a raised exception. The two loaders behave differently when a file disappears at race-condition timing. The handling should be made explicit and uniform: either all loaders catch `FileNotFoundError` and return `None`, or none do.

---

## Comment smell

### [comment] `src/confiq/_load.py:96-97`

Directly caused by the `confiq_transform_value` stepping-stone issue. Resolves with it.

### [comment] `src/confiq/_load.py:188-189`

`pass  # daemon thread; swallow to avoid killing the thread` — `pass` with an explanatory comment is a smell. Either add a `noqa` annotation that makes the intent machine-readable, or extract a named helper that absorbs the exception internally, making the `_notify` loop body comment-free.

---

## Private-module imports in tests

### [private-import] `tests/unit_tests/test_sources.py:10-13`

Imports `CliSource`, `EnvSource`, `FileSource`, `MemorySource` directly from `confiq.sources._cli`, `._env`, `._file`, `._memory`. All four are re-exported from `confiq.sources` (the public package). Importing from `_`-prefixed modules couples tests to the implementation layout; any internal refactor breaks these tests without the public API changing.

Fix: `from confiq.sources import CliSource, EnvSource, FileSource, MemorySource`.

### [private-import] `tests/unit_tests/test_handle.py:8-9`

Imports `hookimpl` from `confiq._hookspecs` and `ConfigHandle` from `confiq._load`. Both are re-exported from the `confiq` root.

Fix: `from confiq import ConfigHandle, hookimpl`.

---

## ADR gaps

### [adr-gap] `src/confiq/_load.py:64-76`

`_fetch_sources()` bridges async sources for sync callers via `ThreadPoolExecutor(max_workers=1)`. The alternatives — raise if async sources are passed to `load()`, require callers to use `load_async()`, or use `asyncio.run()` directly — each carry meaningful trade-offs. No ADR documents why the thread-executor bridge was chosen or whether it is permanent. Warrants an ADR entry in `docs/decisions/`.

### [adr-gap] `src/confiq/_hookspecs.py:53-59`

Same as the `confiq_transform_value` stepping-stone item above. If the hook is intentional future work, an ADR is required to document the intended trigger, wiring path, and timeline.

---

## Unfrozen pydantic test fixtures

### [frozen-pydantic] `tests/unit_tests/test_resolver.py`

`SecretModel`, `WarnModel`, `DeprecatedModel`, `ParsedModel`, `SimpleModel` — all value-shaped pydantic models used as fixtures but not `frozen=True`. Value-shaped fixtures should be frozen to make the immutability contract explicit and to catch accidental mutation.

### [frozen-pydantic] `tests/unit_tests/test_meta.py:11`

`MyModel` — same issue.

---

## Test naming convention

The project standard is `test_<function>_with_<axis>`. Most tests in several files use `test_<something>_returns_<x>` or `test_<something>_is_<y>` instead. Representative examples requiring rename:

| File | Current | Should be |
|------|---------|-----------|
| `test_load.py:35` | `test_schemaless_load_returns_schemaless_config` | `test_load_with_no_schema` |
| `test_handle.py:17` | `test_create_returns_config_handle` | `test_create_with_valid_sources` |
| `test_handle.py:39` | `test_on_reload_subscriber_called` | `test_on_reload_with_registered_subscriber` |
| `test_context.py:10` | `test_no_override_returns_none` | `test_get_override_with_no_active_context` |
| `test_cloud_sources.py:13` | `test_fetch_returns_dict` | `test_fetch_with_valid_credentials` |

A full rename pass is needed across `test_load.py`, `test_handle.py`, `test_context.py`, `test_plugins.py`, and `test_cloud_sources.py`.

---

## No issues found

`src/confiq/_locks.py`, `src/confiq/context.py`, `src/confiq/helpers.py`, `src/confiq/exceptions.py`,
`src/confiq/__init__.py`, `src/confiq/__main__.py`, `src/confiq/schema/_field.py`,
`src/confiq/schema/_meta.py`, `src/confiq/sources/_protocol.py`, `src/confiq/sources/_env.py`,
`src/confiq/sources/_memory.py`, `src/confiq/sources/_cli.py`, `src/confiq/sources/_aws.py`,
`src/confiq/sources/_gcp.py`, `src/confiq/sources/_azure.py`, `src/confiq/sources/_vault.py`,
`src/confiq/sources/_consul.py`, `tests/unit_tests/test_errors.py`, `tests/unit_tests/test_locks.py`,
`tests/unit_tests/test_merge.py`, `tests/unit_tests/test_field.py`,
`tests/integration_tests/test_layered_config.py`.

---

## Issue summary

| Severity | Count |
|----------|-------|
| Critical (resource leak) | 1 |
| Stepping stones without terminus | 2 |
| Naming subverts expectation | 1 |
| Type-hint gaps | 3 |
| Error handling consistency | 1 |
| Comment smell | 2 |
| Private-module imports | 2 |
| ADR gaps | 2 |
| Unfrozen pydantic fixtures | 7 |
| Test naming violations | widespread |
