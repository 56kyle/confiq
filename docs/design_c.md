# `confiq` — Design C: The Synthesis

> Audience: a technically sophisticated Python author. This document is the
> recommended direction for `confiq` after evaluating Design A, Design B, and
> an exhaustive interface analysis. It is written to guide implementation, not
> to introduce philosophy.

---

## 1. TL;DR

- **Config is a value you compute and hold, not an object with ambient identity.**
  `load()` returns a frozen pydantic `BaseModel`. Once it returns, attribute
  access cannot raise a config error. `ConfigHandle[T]` is the explicit opt-in
  for reload scenarios.
- **The schema file has no confiq import.** Plain `BaseModel` with
  `model_config = ConfigDict(frozen=True)` — confiq reads `Annotated` metadata
  via `typing.get_type_hints(model, include_extras=True)` without requiring a
  confiq base class. `ConfigField` is imported only where metadata is declared.
- **Precedence is data, not magic.** The ordered source list passed to `load()`
  is the complete precedence specification. Last-higher. No implicit environment
  switching, no hidden discovery, no convention-based priority escalation.

---

## 2. Philosophy & Guiding Principles

### 2.1 Config is a value, not an object with identity

`load()` returns a frozen model instance. There is no `config.get(...)` on the
primary path — reading config is attribute access on a plain Python object. This
makes the config value identical in character to any other domain value: you can
pass it to functions, store it in a dataclass, compare two instances structurally,
and test it without monkeypatching.

### 2.2 Typed at every layer

Definition time: pydantic field types, enforced by the type checker. Load time:
pydantic `model_validate()` coerces and validates raw source data. Access time:
`config.database.host` is `str` because the model says so — no `Any` on the
read path. `ConfigField` is a `@dataclass(frozen=True)` with no `**kwargs: Any`
escape hatch.

### 2.3 Fail loudly at the boundary

All config errors — missing required fields, malformed source data, type
coercion failures — raise during `load()` or `handle.reload()`. After `load()`
returns, attribute access cannot raise a `ConfiqError`. The boundary is the
function call, not the attribute read.

### 2.4 Precedence is data, not magic

The `sources` argument to `load()` is an ordered list. Later sources override
earlier ones. "First-higher vs. last-higher" is a parameter, not a convention:
reverse the list if you want first-higher semantics. There is no implicit
priority integer, no environment-variable-driven source discovery, and no magic
`config/{env}.yaml` discovery path unless the user puts it in the list.

### 2.5 Metadata travels with the field

`Annotated[T, ConfigField(...)]` is the pattern Typer uses for CLI parameters.
confiq adopts it for the same reason: per-field behavior (env name, CLI flag,
secret marking, custom parser, source restriction) is attached to the field
declaration, not stored in a separate registry or a class-level `Field(env=...)`
call that fights type checkers. The `ConfigField` type is imported from
`confiq.schema`; everything else is stdlib `typing`.

### 2.6 The schema file has no confiq import

A `Settings` class is a plain `pydantic.BaseModel` with
`model_config = ConfigDict(frozen=True)`. confiq reads field metadata at load
time via `typing.get_type_hints(schema, include_extras=True)` — this works on
any class; no confiq base class is required. Users who use no `ConfigField`
annotations at all get convention-based key mapping for free. Users who import
confiq in their schema file have made a choice, not satisfied a requirement.

### 2.7 Testing is hermetic by construction

A fresh `load()` call with `MemorySource` is the canonical test pattern. There
is no global state to reset, no monkeypatch needed, no `before_each` fixture
that tears down a singleton. Each test receives a value computed from known
inputs, and tests do not interfere with each other even when run in parallel.
`confiq.context.override()` exists for the narrow case of per-task divergence in
async environments, not as the testing story.

### 2.8 Singleton ergonomics without singleton ownership

confiq does not own a global `config` variable. Users who want module-level
singleton ergonomics (`from myapp.config import config`) create that variable
themselves in their own `myapp/config.py`. The pattern is documented, the cost
is one file, and confiq makes no assumptions about how many `Settings` instances
exist in a process.

### What we are explicitly not doing

- No `config.get("dotted.key")` on the primary path. String key access exists
  only in schemaless mode, where there is no alternative.
- No confiq-owned global singleton. `from confiq import config` will not work.
- No required confiq base class. `class Settings(confiq.Settings)` is not the
  pattern.
- No YAML interpolation DSL (`${...}` resolution). OmegaConf is not thread-safe
  per its maintainer; interpolation turns config evaluation into a stateful graph
  problem that fights the immutable-snapshot design.
- No implicit environment switching (`[development]` / `[production]` blocks).
  Multi-environment layering is explicit source composition.

---

## 3. Package Layout

```
confiq/
├── __init__.py          # exports: load, load_async, ConfigBind, ConfigField, ConfigHandle, SchemalessConfig, MemorySource, hookimpl
├── _load.py             # load(), load_async(), and ConfigHandle[T]
├── _resolver.py         # merges sources, walks schema, applies ConfigField metadata
├── _snapshot.py         # ResolvedSnapshot: merged field values with per-key source provenance, used between source collection and pydantic validation
├── _hookspecs.py        # pluggy hookspecs
├── _plugins.py          # plugin manager + built-in hookimpls
├── _locks.py            # ReentrancyGuard
├── schema/
│   ├── __init__.py      # exports: ConfigField, ConfigBind
│   ├── _field.py        # ConfigField dataclass definition
│   ├── _bind.py         # ConfigBind dataclass — Annotated marker for CLI parameters
│   └── _meta.py         # field_meta(): reads Annotated metadata from a model class
├── sources/
│   ├── __init__.py      # exports: Source, AsyncSource, MemorySource, EnvSource, FileSource
│   ├── _protocol.py     # Source and AsyncSource protocols
│   ├── _memory.py       # MemorySource
│   ├── _env.py          # EnvSource
│   ├── _file.py         # FileSource — fsspec-backed; delegates parsing to Loader instances
│   └── cli/
│       ├── __init__.py  # exports: ClickSource, TyperSource, ArgparseSource
│       ├── _bind.py     # _set_nested() utility
│       ├── _click.py    # ClickSource / TyperSource (alias for Click/Typer frameworks)
│       └── _argparse.py # ArgparseSource
├── cloud/
│   ├── __init__.py      # exports: VaultSource, AwsSecretsManagerSource,
│   │                    #          GcpSecretManagerSource, AzureKeyVaultSource, ConsulSource
│   ├── _require.py      # shared _require() helper for optional-dependency guard
│   ├── _aws.py          # AwsSecretsManagerSource (requires [aws] extra)
│   ├── _gcp.py          # GcpSecretManagerSource (requires [gcp] extra)
│   ├── _azure.py        # AzureKeyVaultSource (requires [azure] extra)
│   ├── _vault.py        # VaultSource (requires [vault] extra)
│   └── _consul.py       # ConsulSource (requires [consul] extra)
├── loaders/
│   ├── __init__.py
│   ├── _protocol.py     # Loader protocol: extensions(), wants_bytes(), parse()
│   ├── _json.py
│   ├── _yaml.py         # requires [yaml] extra
│   ├── _toml.py         # requires [toml] extra; falls back to stdlib tomllib on 3.11+
│   └── _ini.py
├── helpers.py           # from_env_and_file() convenience constructor
├── context.py           # override() context manager (ContextVar-based per-task override)
└── errors.py            # exception hierarchy
```

Underscore-prefixed modules are library internals; the public surface is
`confiq.__init__`, `confiq.schema`, `confiq.sources`, `confiq.sources.cli`,
`confiq.cloud`, `confiq.context`, `confiq.helpers`, and `confiq.errors`.
Cloud sources (`VaultSource`, `AwsSecretsManagerSource`, etc.) live in
`confiq.cloud` and are guarded by optional extras. Third-party backends that
confiq does not bundle register via the `confiq.sources` entry-point group.

---

## 4. Public API — From Hello World to Full Power

### 4.1 Minimal — schemaless, env-only

Twelve-factor apps that need no structured schema:

```python
from confiq import load
from confiq.sources import EnvSource

config = load(sources=[EnvSource(prefix="MYAPP_")])
host = config["database__host"]   # subscript — the only case where string keys appear
port = config["database__port"]   # values are strings; caller coerces
```

Schemaless mode is the only case where string-key subscript access is
appropriate. There is no pydantic validation, no type coercion, and no
`ConfigField` metadata. The returned object supports `[]` but not attribute
access beyond what `dict` provides.

### 4.2 With a pydantic schema (recommended)

```python
from pydantic import BaseModel, ConfigDict, Field

class Database(BaseModel):
    model_config = ConfigDict(frozen=True)

    host: str = "localhost"
    port: int = Field(5432, ge=1, le=65535)
    password: str

class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    debug: bool = False
    log_level: str = "INFO"
    database: Database
```

```python
from confiq import load
from confiq.sources import FileSource, EnvSource
from myapp.schema import Settings

config: Settings = load(
    Settings,
    sources=[
        FileSource("config.yaml"),          # lowest precedence
        EnvSource(prefix="MYAPP_"),         # MYAPP_DATABASE__HOST → database.host
    ],
)

print(config.database.host)               # str — IDE autocomplete works
print(config.debug)                       # bool
```

`load()` returns a fully-validated, frozen `Settings` instance. No string keys,
no `Any`, no runtime surprises after the call returns.

CLI integration is handled separately via `ClickSource`, `TyperSource`, or
`ArgparseSource` in `confiq.sources.cli` — see §4.4.

### 4.3 With ConfigField metadata

The same schema, annotated to control source mapping:

```python
from typing import Annotated
from pydantic import BaseModel, ConfigDict
from confiq.schema import ConfigField

class Database(BaseModel):
    model_config = ConfigDict(frozen=True)

    host: Annotated[str, ConfigField(env="DB_HOST")] = "localhost"
    port: Annotated[int, ConfigField(env="DB_PORT")] = 5432
    password: Annotated[
        str,
        ConfigField(env="DB_PASSWORD", secret=True, sources=("env",)),
    ]

class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    debug: Annotated[bool, ConfigField(env="DEBUG")] = False
    log_level: Annotated[str, ConfigField(env="LOG_LEVEL")] = "INFO"
    database: Database
```

`ConfigField` is the only confiq import in the schema file. The model itself
is still a plain `BaseModel`. Type checkers see `host: str`, not
`host: Annotated[str, ...]` — the `Annotated` wrapper is transparent to the
type system for purposes of field type resolution.

`sources=("env",)` on `password` means confiq will refuse to set that field
from a file or CLI source even if the value is present — useful for secrets that
must never land in a config file.

### 4.4 CLI framework binding

`ConfigBind("dotted.path")` is an `Annotated` marker placed on a CLI function's
parameters — not on schema fields. Framework-specific sources collect only
parameters that carry a `ConfigBind` marker *and* were explicitly set on the
command line.

```python
# myapp/cli.py
import typer
from typing import Annotated
from confiq import ConfigBind, load
from confiq.sources import FileSource, EnvSource
from confiq.sources.cli import TyperSource
from myapp.schema import Settings

app = typer.Typer()

@app.command()
def main(
    ctx: typer.Context,
    db_host: Annotated[str, typer.Option(), ConfigBind("database.host")] = "localhost",
    debug: Annotated[bool, typer.Option(), ConfigBind("debug")] = False,
) -> None:
    config: Settings = load(
        Settings,
        sources=[
            FileSource("config.yaml"),
            EnvSource(prefix="MYAPP_"),
            TyperSource(ctx),      # only params the user explicitly typed contribute
        ],
    )
```

`TyperSource(ctx)` — which is an alias for `ClickSource(ctx)` since Typer is built on
Click — uses `ctx.get_parameter_source()` to skip parameters that have
`ParameterSource.DEFAULT` or `ParameterSource.DEFAULT_MAP`. A parameter the user did not
type on the command line does not enter the config merge chain, so file and env values
are not silently overridden by framework defaults.

The argparse equivalent uses `ArgparseSource`, which compares each parsed value against
`parser.get_default()` to make the same determination:

```python
import argparse
from confiq.sources.cli import ArgparseSource

parser = argparse.ArgumentParser()
parser.add_argument("--db-host", dest="db_host")
# Annotate the dest name with ConfigBind at fetch time by passing a bindings dict:
args = parser.parse_args()

config = load(
    Settings,
    sources=[
        FileSource("config.yaml"),
        EnvSource(prefix="MYAPP_"),
        ArgparseSource(parser, args),
    ],
)
```

`ConfigBind` is imported from `confiq` or `confiq.schema`; it is framework-agnostic.
The same `ConfigBind("database.host")` declaration works whether the CLI is Click,
Typer, or argparse.

### 4.5 The singleton pattern (user-owned)

```python
# myapp/config.py
from confiq import load
from confiq.sources import FileSource, EnvSource
from myapp.schema import Settings

config: Settings = load(
    Settings,
    sources=[FileSource("config.yaml"), EnvSource(prefix="MYAPP_")],
)
```

```python
# myapp/database.py
from myapp.config import config

def connect() -> Connection:
    return engine.connect(config.database.host, config.database.port)
```

confiq does not own this variable. `myapp/config.py` does. The pattern is
import-time module initialization — the same pattern Python uses for loggers,
registries, and application objects. There is no thread-safety question because
`config` is assigned once at module import time and is immutable thereafter.

### 4.6 Testing — hermetic, no monkeypatching

```python
from confiq import load
from confiq.sources import MemorySource
from myapp.schema import Settings

def test_uses_test_database():
    config = load(
        Settings,
        sources=[MemorySource({"database": {"host": "test-db", "password": "pw"}})],
    )
    assert run_query(config).rowcount > 0
```

`MemorySource` wraps a plain `dict`. The `load()` call is the test fixture. No
shared state, no cleanup, no `monkeypatch`. Tests can run in any order and in
parallel.

### 4.7 Per-task override (async-safe)

```python
from confiq.context import override

async def handle(request: Request) -> Response:
    with override(config, database__host=request.tenant_db):
        return await process(config)
```

`override()` uses `contextvars.ContextVar` internally — see
`docs/decisions/0001-lock-free-reads-via-immutable-snapshots.md`. The override
is visible to `process()` and to any coroutine it awaits within this task,
but not to concurrent tasks. Per PEP 567, `ContextVar` values are inherited
by child tasks and restored when the `with` block exits, making this safe
across `await` boundaries.

This is for exceptional per-task divergence — multi-tenant routing, test
fixtures for async tests — not the primary testing pattern.

### 4.8 Live reload with ConfigHandle

```python
from confiq import ConfigHandle
from confiq.sources import FileSource, EnvSource
from myapp.schema import Settings

handle: ConfigHandle[Settings] = ConfigHandle.create(
    Settings,
    sources=[
        FileSource("config.yaml", watch=True),
        EnvSource(prefix="MYAPP_"),
    ],
)

cfg: Settings = handle.current()   # lock-free; single attribute read

@handle.on_reload
def on_change(old: Settings, new: Settings) -> None:
    if old.database != new.database:
        pool.reconfigure(new.database)
```

`load()` and `ConfigHandle.create()` share the same source list and resolution
logic. `ConfigHandle` adds three things on top: a reference to the current
snapshot, a short write-lock for atomic swaps, and a subscriber mechanism.
`current()` is lock-free. `reload()` builds the new snapshot under the lock and
publishes via a single `STORE_ATTR`. Subscribers run on a daemon thread outside
the lock — see Section 7.

### 4.9 Cloud sources

```python
from confiq import load
from confiq.cloud import VaultSource, AwsSecretsManagerSource
from confiq.sources import EnvSource
from myapp.schema import Settings

config = load(
    Settings,
    sources=[
        VaultSource(addr="https://vault.example.com", path="secret/data/myapp"),
        AwsSecretsManagerSource(secret_id="prod/myapp", region="us-east-1"),
        EnvSource(prefix="MYAPP_"),
    ],
)
```

Common cloud sources ship as built-in implementations in `confiq.cloud`, each
guarded by an optional dependency extra. `pip install confiq[vault]` enables
`VaultSource`; `pip install confiq[aws]` enables `AwsSecretsManagerSource`.
Instantiation raises `MissingDependencyError` if the required extra is not
installed, pointing to the correct `pip install` command.

Sources remain lazy — `VaultSource(...)` is cheap; the network call happens at
`load()` time. For backends confiq does not bundle (enterprise systems, internal
custom sources), the `confiq.sources` entry-point group is still available —
see §9.

### 4.10 Third-party plugin (pluggy hookimpl)

```python
# confiq_audit/plugin.py
from confiq import hookimpl

class AuditPlugin:
    @hookimpl
    def confiq_post_load(self, config: object) -> None:
        audit_log.record_load(type(config).__name__)

    @hookimpl
    def confiq_on_reload(self, old: object, new: object) -> None:
        audit_log.record_reload(type(new).__name__)
```

```toml
# confiq_audit/pyproject.toml
[project.entry-points.confiq]
audit = "confiq_audit.plugin:AuditPlugin"
```

`pm.load_setuptools_entrypoints("confiq")` runs once at plugin manager
initialization. `pip install confiq-audit` is the complete user-facing install
step; no confiq configuration change is needed.

---

## 5. Core Abstractions

### 5.1 The Source protocol

```python
# confiq/sources/_protocol.py
from typing import Any, Mapping, Protocol, runtime_checkable


@runtime_checkable
class Source(Protocol):
    name: str

    def fetch(self) -> Mapping[str, Any]: ...


@runtime_checkable
class AsyncSource(Protocol):
    name: str

    async def fetch(self) -> Mapping[str, Any]: ...
```

Sources are lazy. Instantiation is cheap — no I/O. The `fetch()` call is where
I/O happens, and it runs exactly once per `load()` or `handle.reload()` call.
Sources do not validate; they return raw mappings. Nested structure is expressed
as nested dicts; the resolver normalizes.

`name` appears in error messages (`SourceUnavailableError`, `MissingConfigError`)
so the user can tell which source failed. It is also matched against
`ConfigField.sources` values at load time to enforce per-field source
restrictions — see §5.2.

### 5.2 ConfigField

```python
# confiq/schema/_field.py
from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class ConfigField:
    env: str | None = None
    file_key: str | None = None
    secret: bool = False
    parser: Callable[[str], Any] | None = None
    sources: tuple[str, ...] | None = None
    on_source_violation: Literal["raise", "warn_and_skip"] = "raise"
    description: str | None = None
    deprecated: str | None = None
```

`env` — explicit environment variable name. When absent, the resolver derives
it from field path and `EnvSource.prefix` + `EnvSource.delimiter`.

`file_key` — explicit dotted path within file-backed sources. Allows a schema
field named `database_host` to map to `database.host` in YAML without renaming.

`secret` — when `True`, the value is masked in `repr`, excluded from log output,
and redacted in the `confiq_post_load` hook's arguments. Resolution is
unaffected.

`parser` — per-field coercion before pydantic validation. Useful for
comma-separated lists in env vars (`lambda s: s.split(",")`), which pydantic
cannot infer from an env string alone.

`sources` — restricts which source types may set this field. Values are matched
against `source.name` for each source in the `sources` list passed to `load()`.
A field with `sources=("env",)` ignores values from any source whose `name` is
not `"env"`. At load time the resolver validates that every name in
`ConfigField.sources` matches at least one source in the call — an unmatched
name raises `ConfigurationError` immediately rather than silently passing.

Violation behavior is split by `secret`. For `secret=True` fields, violations
always raise `ConflictingSourceError` — source restriction on a secret is a
security boundary and `on_source_violation` is ignored. For `secret=False`
fields, `on_source_violation` controls the outcome: `"raise"` (the default)
raises `ConflictingSourceError`; `"warn_and_skip"` emits a `RuntimeWarning` and
skips the value.

`on_source_violation` — controls what happens when a `secret=False` field
receives a value from a source not listed in `sources`. Has no effect when
`secret=True`. See `sources` description above.

`deprecated` — when set, `load()` emits a `DeprecationWarning` if any source
supplies a value for this field. Carry the reason in the string
(`deprecated="Use new_field instead. Removed in v2."`).

### 5.3 ConfigBind

```python
# confiq/schema/_bind.py
from dataclasses import dataclass


@dataclass(frozen=True)
class ConfigBind:
    path: str
```

`ConfigBind` is an `Annotated` marker placed on **CLI function parameters**, not on
config schema fields. It carries the dotted config path that the parameter maps to.

```python
db_host: Annotated[str, typer.Option(), ConfigBind("database.host")] = "localhost"
```

Framework-specific sources (`ClickSource`, `TyperSource`, `ArgparseSource`) inspect
the command function's type hints at `fetch()` time, collect parameters annotated
with `ConfigBind`, filter to only those explicitly set on the command line, and build
a nested dict keyed by the `path` values.

`ConfigBind` is framework-agnostic — the same annotation works with any of the three
adapters. It is exported from both `confiq` and `confiq.schema`.

### 5.4 The Loader protocol

```python
# confiq/loaders/_protocol.py
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Loader(Protocol):
    def extensions(self) -> frozenset[str]: ...
    def wants_bytes(self) -> bool: ...
    def parse(self, data: bytes | str) -> dict[str, Any]: ...
```

Loaders are pure format parsers. They never touch the filesystem.

`extensions()` — returns the set of file suffixes this loader handles
(e.g. `frozenset({".json"})`). `FileSource` uses this to select the right loader
for a given path.

`wants_bytes()` — returns `True` if `parse()` expects `bytes`, `False` if it
expects a decoded `str`. Lets `FileSource` read the file in the appropriate mode via
`fsspec`.

`parse(data)` — parses pre-read content and returns the config dict. Raises
`SourceParseError` on malformed input.

`FileSource` is responsible for all I/O via `fsspec` (supporting local paths,
`s3://`, `gs://`, Azure Data Lake, and any other fsspec-registered filesystem). It
reads the file, detects the suffix, selects the matching `Loader`, calls
`parse()` with the content, and returns the resulting dict.

Built-in loaders handle `.json` and `.ini` with stdlib only. `.yaml` requires the
`[yaml]` extra; `.toml` uses stdlib `tomllib` on Python 3.11+ or the `[toml]` extra
on 3.10.

### 5.5 The load() function

```python
# confiq/_load.py
from collections.abc import Mapping
from typing import Any, TypeVar, overload

from confiq.sources._protocol import AsyncSource, Source

T = TypeVar("T")


class SchemalessConfig(Mapping[str, Any]):
    """Read-only subscript-access result of a schemaless load() call."""


@overload
def load(
    schema: type[T],
    *,
    sources: list[Source | AsyncSource],
    plugins: list[object] | None = ...,
    strict: bool = ...,
) -> T: ...


@overload
def load(
    schema: None = ...,
    *,
    sources: list[Source | AsyncSource],
    plugins: list[object] | None = ...,
    strict: bool = ...,
) -> SchemalessConfig: ...


def load(
    schema: type[T] | None = None,
    *,
    sources: list[Source | AsyncSource],
    plugins: list[object] | None = None,
    strict: bool = True,
) -> T | SchemalessConfig:
    ...


async def load_async(
    schema: type[T] | None = None,
    *,
    sources: list[Source | AsyncSource],
    plugins: list[object] | None = None,
    strict: bool = True,
) -> T | SchemalessConfig:
    ...
```

`schema` — a pydantic `BaseModel` subclass. When `None`, schemaless mode:
returns a `SchemalessConfig` with subscript access only. The `@overload`
signatures ensure type checkers infer `T` when a schema is provided and
`SchemalessConfig` when it is not.

`sources` — ordered list; later entries override earlier ones. The order is the
complete precedence specification.

`plugins` — per-call plugin injection. A plugin is any object with one or more
`@hookimpl`-decorated methods; confiq uses pluggy to discover them by
inspection. Useful in tests to avoid entry-point auto-discovery side effects:
`load(Settings, sources=[...], plugins=[MyPlugin()])` loads `MyPlugin` for this
call only. Entry-point plugins still load; `plugins` is additive, not exclusive.

`strict` — when `True` (default), source keys not present in the schema emit a
`UserWarning`. When `False`, unrecognized keys are silently ignored. Useful
during schema migration when sources are ahead of the schema. `strict` controls
unknown-key behavior only; per-field source restriction violations are governed
by `ConfigField.on_source_violation`, which is orthogonal.

`load()` is synchronous. For async sources, it gathers their results by
running `asyncio.gather()` inside a `ThreadPoolExecutor` worker via
`asyncio.run()` — this avoids conflict with any running event loop in the
caller's thread and is compatible with Python 3.10+.

`load_async()` is the async variant for callers already inside an event loop.
It drives async sources natively with `await` and does not use the thread
executor. Both `load()` and `load_async()` share the same resolver and produce
identical results; the difference is only in how `AsyncSource.fetch()` calls
are scheduled.

### 5.6 ConfigHandle[T]

```python
# confiq/_load.py (continued)
from collections.abc import Callable
from typing import Generic

T = TypeVar("T")


class ConfigHandle(Generic[T]):
    @classmethod
    def create(
        cls,
        schema: type[T],
        *,
        sources: list[Source | AsyncSource],
        plugins: list[object] | None = None,
    ) -> ConfigHandle[T]: ...

    def current(self) -> T: ...
    def reload(self) -> T: ...
    async def reload_async(self) -> T: ...
    def on_reload(
        self, fn: Callable[[T, T], None]
    ) -> Callable[[T, T], None]: ...
```

`create()` — classmethod factory rather than `__init__` because construction
performs an initial `load()` call: I/O that may raise. A `ConfigHandle(...)`
constructor would carry the same cost but conceal it from readers of the call
site. The factory name makes the side effect explicit — see Section 12,
decision 7.

`current()` — lock-free; reads a single attribute (`self._current`). Cost is
one `LOAD_ATTR`.

`reload()` — acquires the write lock, runs all sources and the resolver, builds
a new frozen snapshot, and publishes via a single `STORE_ATTR`. Returns the
new snapshot. `ReentrancyGuard` raises loudly if the same thread re-enters
`reload()` synchronously — see `_locks.py` and
`docs/decisions/0001-lock-free-reads-via-immutable-snapshots.md`.

`reload_async()` — the async variant. Drives async sources natively. Acquires
an asyncio-compatible lock for the swap step.

`on_reload(fn)` — decorator/call that registers `fn` as a subscriber. `fn`
receives `(old: T, new: T)`. Subscribers run on a daemon thread outside the
write lock after the atomic swap completes. `on_reload` returns `fn` unchanged
so it can be used as a decorator.

`ConfigHandle` is the explicit opt-in for reload scenarios. The default path —
`load()` returning a bare `T` — has no `ConfigHandle` in the picture.

---

## 6. Resolution & Precedence

The resolver — `confiq/_resolver.py` — is the only place where sources and
schema meet. The algorithm:

1. Call `source.fetch()` for each source in order. Accumulate as a list of
   `(source_name, mapping)` pairs.
2. Deep-merge the pairs left-to-right, tracking provenance. This step produces
   two parallel structures stored together in `ResolvedSnapshot` (`_snapshot.py`):
   - `merged: dict[str, Any]` — the resolved values, later entries winning on
     collision.
   - `provenance: dict[str, str]` — maps each dotted key path to the `name` of
     the last source that set it. Updated whenever a source overrides a value.
   Lists are replaced, not concatenated — see
   `docs/decisions/0004-deep-merge-list-replacement-semantics.md`.
3. Walk the schema's fields via
   `typing.get_type_hints(schema, include_extras=True)`. For each field:
   a. Read `ConfigField` metadata from the `Annotated` wrapper, if present.
   b. Determine the effective lookup key: `ConfigField.file_key`, or the
      field name, or the dotted path for nested fields.
   c. Apply `sources` restriction: look up the field's dotted path in
      `provenance`. If the recorded source name does not appear in
      `ConfigField.sources`, apply `on_source_violation`. For `secret=True`
      fields always raise `ConflictingSourceError`. The resolver also validates
      at this point that every name in `ConfigField.sources` matches at least
      one source in the call; a mismatch raises `ConfigurationError` immediately.
   d. Apply `parser` if set, before pydantic sees the value.
   e. Emit `DeprecationWarning` if `deprecated` is set and a value was found.
4. Validate through `schema.model_validate(merged)`.
5. On `MissingConfigError`, report the full field path and the names of all
   sources that were consulted.

**Precedence table.** Given `sources=[A, B, C]`:

| Source | Precedence |
|--------|-----------|
| A      | lowest — provides defaults / base values |
| B      | middle — overrides A |
| C      | highest — overrides A and B |

Reversing the list reverses precedence. There is no other mechanism.

**Convention-based key mapping.** When `ConfigField` is absent, the resolver
derives the lookup key from the field's position in the schema:
- `Settings.database.host` → nested key path `["database", "host"]`
- `EnvSource(prefix="MYAPP_", delimiter="__")` maps `MYAPP_DATABASE__HOST`
  to `{"database": {"host": "..."}}` — the field resolves to the right value
  without any `ConfigField` annotation.

**Nested model fields.** A field typed as a nested `BaseModel` causes the
resolver to recurse into that model's fields. Source restriction, parser, and
deprecation metadata on nested fields work identically to top-level fields.

---

## 7. Thread Safety

### Design choice

Immutable snapshot + atomic reference swap + reentrancy fast-fail. See
`docs/decisions/0001-lock-free-reads-via-immutable-snapshots.md` for the full
argument. The short version:

`load()` returns a frozen model — there is nothing to protect. A value cannot
be mutated after construction.

`ConfigHandle` is the only object with mutable internal state (the current
snapshot reference). It uses the same pattern as Design A:

1. `current()` reads `self._current` — one `LOAD_ATTR`, no lock.
2. `reload()` takes a short non-reentrant `threading.Lock`, builds the new
   snapshot entirely under the lock, then publishes via `self._current = new`.
3. Subscribers run on a daemon thread after the lock is released.

### Locking table

| Operation | Lock | Reason |
|-----------|------|--------|
| `load()` return value attribute access | none | frozen model; immutable |
| `handle.current()` | none | single `LOAD_ATTR` |
| `handle.reload()` | `threading.Lock` | serializes snapshot construction |
| `confiq_pre_load`, `confiq_post_load` hooks | inside lock | run as part of build |
| `confiq_on_reload` subscribers | none (daemon thread, outside lock) | prevents reentrancy deadlock |
| `override()` context | none (`ContextVar`) | async-safe; no shared state |

### ReentrancyGuard

`_locks.ReentrancyGuard` is modeled on loguru's `_protected_lock`
(`loguru/_handler.py`). If a subscriber or hookimpl attempts to call
`handle.reload()` synchronously from within the `on_reload` dispatch, the guard
raises:

```
RuntimeError: confiq: re-entered the config write lock from the same thread
(deadlock avoided). A hookimpl or subscriber tried to trigger reload
synchronously. Move that work to a separate thread or schedule it on the
event loop.
```

Fast-fail over silent deadlock. The error message includes the remedy.

### async compatibility

`override()` uses `ContextVar` — see §4.6. Per PEP 567, `ContextVar` values are
inherited by child asyncio tasks at creation and restored on exit from the
`with` block. No `threading.local`, no bleed between concurrent tasks.

`handle.reload_async()` uses an asyncio-compatible lock for the swap step,
allowing it to be called from a coroutine without blocking the event loop.

`confiq_pre_load` receives a **shallow copy** of the `sources` list. Mutations
in a hook are local to that load call and do not affect the handle's source
list for subsequent reloads. This prevents a race when two threads call
`handle.reload()` concurrently — they do not share a mutable list reference.

Free-threaded CPython (PEP 703): the atomic-swap argument holds for reference
assignment under the new memory model, but the merge path (dict reads and
writes during source collection) may require explicit protection in 3.13+ no-GIL
builds. This is deferred to a post-1.0 audit — see Section 12, question 4.

---

## 8. Error Handling

```
ConfiqError
├── ConfigLoadError
│   ├── SourceUnavailableError    # file missing, network unreachable, auth failed
│   └── SourceParseError          # malformed YAML, TOML, or JSON
├── ConfigValidationError         # pydantic validation failure; carries field path
│                                 # and the name of the source that supplied the value
├── MissingConfigError            # required field; no source provided a value; no default
├── ConflictingSourceError        # field has sources restriction; a forbidden source
│                                 # attempted to set it. Always raised for secret=True
│                                 # fields; raised for secret=False only when strict=True
└── PluginError                   # a hookimpl raised; wraps the original exception
```

All confiq errors are raised during `load()` or `handle.reload()`. `__cause__`
is set when wrapping a lower-level exception (e.g., `SourceParseError.__cause__`
is the `yaml.YAMLError`).

`ConfigValidationError` carries `field_path: str` (dotted),
`source_names: list[str]` (names of the sources that contributed to the field's
value — there may be more than one after deep-merge where nested sub-fields came
from different sources), and `pydantic_errors: list[InitErrorDetails]` (the raw
pydantic error detail). This is enough to write a single-line error message that
tells the user which sources were involved and where the bad value was expected
to go.

After `load()` returns, no confiq method on the returned model raises a
`ConfiqError`. Reading `config.database.host` is exactly as safe as reading any
other attribute — because it is.

---

## 9. Plugin System

confiq ships pluggy and exposes a hookspec surface. Internal subsystems — the
YAML loader, TOML loader, secret-masking repr, deprecation warning emitter — are
themselves pluggy plugins registered at plugin manager initialization. This
dogfooding forces the hookspecs to be expressive enough for real work before any
external plugins are written.

### Hookspecs

```python
# confiq/_hookspecs.py
import pluggy

hookspec = pluggy.HookspecMarker("confiq")
hookimpl = pluggy.HookimplMarker("confiq")


class ConfiqSpecs:
    @hookspec(firstresult=True)
    def confiq_get_schema_adapter(self, schema: type) -> "SchemaAdapter | None":
        """Return a SchemaAdapter for this schema type, or None if unrecognized."""

    @hookspec
    def confiq_pre_load(
        self, schema: type, sources: "list[Source | AsyncSource]"
    ) -> None:
        """Called before resolution begins with a shallow copy of the sources list.
        Mutations affect only this load call."""

    @hookspec
    def confiq_post_load(self, config: object) -> None:
        """Called after a successful load. Config is frozen; read-only."""

    @hookspec
    def confiq_on_reload(self, old: object, new: object) -> None:
        """Called after ConfigHandle reload. Runs on daemon thread outside the lock."""

    @hookspec
    def confiq_on_error(self, error: "ConfiqError") -> None:
        """Called when load() fails. Plugin may log or record metrics; not for recovery."""
```

`confiq_get_schema_adapter` — `firstresult=True`; allows third-party schema
types (attrs classes, msgspec structs) to be supported without modifying confiq.
The built-in adapter handles pydantic `BaseModel`. A `SchemaAdapter` must
implement the following protocol:

```python
# confiq/_hookspecs.py (continued)
from collections.abc import Mapping
from typing import Any, Protocol


class SchemaAdapter(Protocol):
    """Adapts a schema class to confiq's resolver interface."""

    def field_hints(self) -> Mapping[str, object]:
        """Return field name → annotated type (including Annotated wrappers).

        For pydantic: typing.get_type_hints(schema, include_extras=True).
        """
        ...

    def validate(self, data: dict[str, Any]) -> object:
        """Validate and coerce the merged data dict into the schema type.

        For pydantic: schema.model_validate(data).
        """
        ...
```

`confiq_pre_load` — receives a shallow copy of the `sources` list; mutations
are local to this load call and do not affect the handle's source list. Use
case: injecting a `MemorySource` with computed defaults, or removing a source
based on an environment condition.

`confiq_post_load` — read-only. Use case: audit logging, metrics, validation
that requires cross-field logic outside pydantic's model validators.

`confiq_on_reload` — runs on a daemon thread outside the write lock. Subscribers
should not call `handle.reload()` synchronously.

`confiq_on_error` — informational; not a recovery hook. The exception still
propagates to the caller of `load()`.

### Two extension surfaces

Following the insight in `docs/decisions/0003-dual-extension-surfaces.md`:

**Source classes via `confiq.sources` entry-point group** — for stateful
backends that confiq does not bundle: enterprise systems, internal custom
sources, or providers added before confiq ships built-in support. Each is an
instance with its own connection, credentials, and lifecycle. Registered as:

```toml
[project.entry-points."confiq.sources"]
consul_enterprise = "mycompany_confiq.source:ConsulEnterpriseSource"
```

Common cloud providers (AWS, GCP, Azure, Vault, Consul) are built-in and do
not need entry-point registration — see §4.9 and §10.

**Hookimpls via `confiq` entry-point group** — for stateless transforms (secret
redaction, audit logging, schema migration hooks). Registered as:

```toml
[project.entry-points.confiq]
redact = "confiq_redact.plugin:RedactPlugin"
```

The rule: if your extension is an instance you configure, it's a source class.
If your extension participates in a coordinated event, it's a hookimpl.

---

## 10. Optional Dependencies

```toml
[project]
name = "confiq"
requires-python = ">=3.10"
dependencies = [
    "fsspec>=2026.4.0",
    "pluggy>=1.5",
    "pydantic>=2.5",
    "python-dotenv>=1.2.2",
    "typer>=0.15.4",
]

[project.optional-dependencies]
yaml   = ["pyyaml>=6.0"]
toml   = ["tomli>=2.0; python_version<'3.11'"]
watch  = ["watchdog>=4.0"]
click  = ["click>=8.1"]
aws    = ["boto3>=1.34"]
gcp    = ["google-cloud-secret-manager>=2.18"]
azure  = ["azure-identity>=1.15", "azure-keyvault-secrets>=4.7"]
vault  = ["hvac>=2.0"]
consul = ["py-consul>=1.7"]
s3     = ["s3fs>=2026.4.0"]
gcs    = ["gcsfs>=2026.4.0"]
adl    = ["adlfs>=2024.7.0"]
common = ["confiq[yaml,toml,watch]"]
all    = ["confiq[yaml,toml,watch,click,aws,gcp,azure,vault,consul,s3,gcs,adl]"]
dev    = ["pytest>=8", "pytest-asyncio>=0.23", "mypy>=1.10", "ruff>=0.5"]
```

`pydantic`, `pluggy`, `fsspec`, `python-dotenv`, and `typer` are the mandatory
runtime dependencies. `pydantic>=2.5` is the minimum version that has stable
`model_validate()` with `include_extras=True` support in `get_type_hints`.
`pluggy>=1.5` for `load_setuptools_entrypoints` reliability across Python versions.
`fsspec>=2026.4.0` is used directly by `FileSource` for all file I/O — it ships
no filesystem backends by default; `[s3]`, `[gcs]`, and `[adl]` install
`s3fs`, `gcsfs`, and `adlfs` to enable `s3://`, `gs://`, and Azure Data Lake URLs
respectively. `python-dotenv` and `typer` are mandatory because they are used in
confiq's core CLI and `.env` support.

TOML on Python 3.10: stdlib `tomllib` arrived in 3.11; on 3.10 the `[toml]`
extra installs `tomli`. The built-in TOML loader plugin (`_plugins.py`) tries
`tomllib` first, falls back to `tomli` if available. Neither triggers an import
error on 3.10 without the extra — the plugin simply does not register itself.

`[watch]` brings in `watchdog`. `FileSource(path, watch=True)` raises
`MissingDependencyError` at instantiation if `watchdog` is not installed,
pointing to `pip install confiq[watch]`.

Built-in cloud sources defer their SDK imports to instantiation time — `import
confiq` never imports boto3, hvac, or similar. Only the source classes the user
actually instantiates will attempt the import. If the required extra is absent,
instantiation raises `MissingDependencyError` pointing to
`pip install confiq[extra-name]`. See Section 12, decision 9.

---

## 11. Comparison with Design A and Design B

| Axis | Design A | Design B | Design C (this) |
|------|----------|----------|-----------------|
| Entry point | `from confiq import config` singleton | `load()` function | `load()` function |
| Schema | Any pydantic `BaseModel` | Required `confiq.Settings` subclass | Plain pydantic `BaseModel`; no confiq import required |
| Read API | `config.get("dotted.key")` returns `Any` | Attribute access on `Settings` instance | Attribute access on `BaseModel` instance |
| Per-field metadata | Not specified | `Annotated[T, ConfigField(...)]` | `Annotated[T, ConfigField(...)]` — same as B |
| Singleton | confiq-owned global `config` | Not specified; banned as a footgun | User-owned module variable; documented pattern |
| Testing | Fresh `Config()` instance | `MemorySource` + fresh `load()` | `MemorySource` + fresh `load()` — same as B |
| Thread safety | Immutable snapshot + atomic swap | Immutable snapshot | Immutable snapshot + atomic swap — same as A |
| Reload | `config.reload()` on mutable `Config` | `ConfigHandle[T]` | `ConfigHandle[T]` — same as B |
| Plugin system | pluggy (full) | pluggy (full) | pluggy (full) — same as A and B |

**What Design C gives up relative to Design A:**

- `from confiq import config` singleton convenience. The user re-creates this
  in their own module — one file, two lines, no framework support needed.
- `config.get("dotted.key")` escape hatch on the primary path. Schemaless mode
  retains string-key subscript access; structured mode does not offer it.

**What Design C gives up relative to Design B:**

- Nothing material. The only substantive Design B decision Design C does not
  adopt is the required `Settings` base class.

**What Design C gains over Design A:**

- No `Any` on the read path. `config.get("x")` returns `Any`; attribute access
  on a typed model does not.
- Hermetic testing without fresh `Config()` construction. `MemorySource` +
  `load()` is simpler than building a configured `Config` instance per test.
- Frozen values at the call site, not eventually frozen after `.freeze()`.

**What Design C gains over Design B:**

- No confiq import required in the schema file. The schema file imports only
  `pydantic`. This matters for codebase separation — a `schema/` directory
  can be shared with code that has no confiq dependency.
- Singleton ergonomics documented and supported, not banned. Design B's
  §16 listed "no global default config singleton" as a non-goal without
  offering a documented alternative pattern.

---

## 12. Resolved Design Decisions

These questions were open at the time Section 1 was written. Each is now
resolved. The decisions below supersede any conditional language elsewhere in
this document.

**1. No convenience prefix shortcut on `load()`.**

`load()` will not accept a `prefix` shortcut that auto-discovers files and env
vars. Implicit source lists violate principle 2.4 and make debugging harder.
Instead, `confiq.helpers` ships a `from_env_and_file(schema, prefix, path)`
convenience constructor that builds the explicit source list and delegates to
`load()`. Users see the sources; no magic lives in `load()` itself.

**2. `confiq.context.override()` ships as a context manager only in v1.**

No `confiq_override` pytest fixture in v1. The primary testing story —
`MemorySource` plus a fresh `load()` per test — never needs `override()`. A
`pytest-confiq` package (a separate PyPI package, not part of `confiq` itself)
is a planned post-v1 deliverable that will ship the fixture and any other pytest
integration. Keeping the pytest dependency out of `confiq` itself remains the
right boundary; the plugin follows the same separate-package model as cloud
sources.

**3. Async callbacks on `ConfigHandle.on_reload` deferred to v1.1.**

`on_reload` accepts only sync callables in v1. Async users bridge via
`loop.call_soon_threadsafe(asyncio.ensure_future, coro, loop=loop)` inside their
sync subscriber — this pattern is documented in the `ConfigHandle` reference.
First-class async subscribers require confiq to own or accept a loop reference,
which is a significant design commitment deferred until the sync surface is stable
and demand is confirmed.

**4. Free-threaded CPython (PEP 703) audit is not a v1 blocker.**

The atomic-swap argument (`self._current = new`) holds under the new memory model.
The narrow risk is in `deep_merge` when a source mutates a shared dict concurrently
under a no-GIL build — an unusual scenario that requires user-side misbehavior.
The audit will be performed before confiq declares no-GIL compatibility; the right
moment is when CPython 3.14 stabilizes the no-GIL build guarantee.

**5. `ConfigField.sources` violation behavior is split by `secret` and
`on_source_violation`.**

`secret=True` fields always raise `ConflictingSourceError` on a source violation.
Source restriction on a secret is a security boundary: silently skipping a
leaked value while leaving the field unset produces a confusing
`MissingConfigError` from an unrelated path. `on_source_violation` is ignored
for secret fields.

`secret=False` fields use `on_source_violation` to control the outcome per
field: `"raise"` (the default) raises `ConflictingSourceError`; `"warn_and_skip"`
emits a `RuntimeWarning` and skips the value. This is a per-field decision, not
a global `load()` parameter — a team migrating a legacy source wants lax
behavior on specific fields, not on the entire config. `strict` in `load()` is
orthogonal: it controls whether unknown source keys (keys with no matching schema
field) emit a warning. See Section 5.2 and Section 8.

**6. Source protocol method is named `fetch()`, not `load()`.**

`load()` is the name of the public function that orchestrates full config
resolution and returns a validated model. A source method with the same name
collides at the reader level — identical word, entirely different abstraction.
`fetch()` is unambiguous: it means "retrieve raw data from this backend."
`read()` was considered but implies file I/O; `fetch()` is neutral on transport.

**7. Source restriction is enforced via provenance tracking, not pre-merge
filtering.**

The resolver deep-merges all sources into `merged` while simultaneously
populating a parallel `provenance: dict[str, str]` that records, for each
dotted key path, the name of the last source to set it. Source restrictions
(`ConfigField.sources`) are checked in the field-walking step by consulting this
provenance dict.

The alternative — filtering each source's mapping before merge based on field
restrictions — requires schema metadata to be available during the merge phase,
coupling two concerns that are cleanest when kept separate. Provenance tracking
preserves the clean separation: merge is generic, restriction enforcement is
schema-aware. `ResolvedSnapshot` (`_snapshot.py`) carries both `merged` and
`provenance` as a unit between the two phases.

**8. `confiq.context.override()`, not `patch()`.**

In the Python ecosystem `patch` is the canonical name for monkeypatching
(unittest.mock.patch, pytest's monkeypatch fixture). This design explicitly
rejects monkeypatching as a testing pattern (§2.7). Using `patch` for a
production-facing `ContextVar`-based override would import the wrong mental
model into every call site. `override()` names what the function does — install
a scoped context-local override — without the monkeypatching connotation.

**9. Common cloud sources ship as built-in implementations with optional extras,
following the fsspec model.**

`VaultSource`, `AwsSecretsManagerSource`, and similar live in `confiq.sources`
and are importable from a single package. This gives users one install command
(`pip install confiq[aws]`), one import path, and one place where the Source
protocol contract is maintained. The alternative — separate packages like
`confiq-aws` — distributes that surface across independently versioned packages,
requiring coordinated releases whenever the `Source` protocol or `ConfigField`
API changes.

Built-in cloud sources use lazy SDK imports: `boto3`, `hvac`, and similar are
imported at instantiation time, not at module import time. `import confiq`
carries none of their weight. If a required extra is absent, instantiation
raises `MissingDependencyError` with an actionable hint rather than a bare
`ImportError` buried in a stack trace.

The `confiq.sources` entry-point group remains available for sources that
confiq has no reason to bundle: enterprise systems, internal custom backends,
or providers not yet in the built-in set.

**10. ConfigHandle owns a persistent PluginManager.**

`ConfigHandle.create()` builds the plugin manager once and stores it as `self._pm`.
All subsequent `reload()` and `reload_async()` calls use internal `_load_with_pm()` /
`_load_with_pm_async()` helpers that accept a pre-built PM, preserving user-registered
plugins across the lifetime of the handle.

Previously, `reload()` delegated to the public `load()`, which called
`_make_plugin_manager()` internally on every invocation. Plugins passed via
`plugins=[...]` to `ConfigHandle.create()` were registered on the first PM and then
discarded — the PM constructed for subsequent reloads had no knowledge of them.
`confiq_on_reload` was also never called; the hookspec was dead code.

After this change: user-registered plugins survive across reload cycles;
`confiq_on_reload` fires on the same daemon thread as subscriber notifications, before
the subscriber callbacks. The public `ConfigHandle.create()` signature is unchanged.
See `docs/decisions/0010-confighandle-persistent-plugin-manager.md`.

**11. CLI-to-config binding via ConfigBind annotation on command parameters.**

`CliSource`, `ConfigField.cli`, and the `cli` entry-point in `pyproject.toml` are
removed. Replaced by framework-specific adapters in `confiq.sources.cli`:
`ClickSource` / `TyperSource` for Click/Typer, `ArgparseSource` for argparse.

Binding is declared with `ConfigBind("dotted.path")` as an `Annotated` marker on
the CLI function's parameters — not on schema fields. Only parameters the user
explicitly typed on the command line enter the config merge chain. `ClickSource`
uses `ctx.get_parameter_source()` to skip `DEFAULT` and `DEFAULT_MAP` values;
`ArgparseSource` compares the parsed value against `parser.get_default()`.

This removes `cli` from `ConfigField`, shrinking the schema surface and eliminating
the coupling between config schema and CLI framework. It also solves the
default-precedence problem: CLI framework defaults no longer silently override
lower-priority sources.

`TyperSource` is a module-level alias for `ClickSource` — Typer is built on Click
and its `Context` is a Click `Context`. See
`docs/decisions/0011-configbind-cli-binding-model.md`.