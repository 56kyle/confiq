# `confiq` — Architecture Proposal

A modern, type-safe, thread-safe, plugin-extensible configuration management package for Python.

---

## 1. Philosophy & Design Goals

`confiq` exists in a crowded space (pydantic-settings, dynaconf, hydra, omegaconf, python-decouple), so its identity needs to be sharp. The thesis: **configuration is a typed, layered, observable value built from sources, and the library should make every one of those words real**.

The guiding principles, in order of priority when they conflict:

1. **Typed at the edges, typed in the middle.** A `Config` is a strongly typed object — at definition time, at load time, and at access time. Internal data structures are typed too; there is no `dict[str, Any]` floating around the public API.
2. **Explicit failure, at the boundary.** Borrowed from Rust in spirit but not in syntax: parsing, validation, and resolution can fail, and they fail loudly at the moment of `load()`. Once a `Config` exists, attribute access cannot raise a config error. No `Result[T, E]` wrappers — Python's `raise`/`return` is sufficient, but we use it deliberately. Internal helpers prefer total functions over partial ones.
3. **Safe by default.** Thread-safety and async-safety are properties of the library, not user homework. The pattern is loguru's: the user doesn't think about it because it just works.
4. **Composable sources, not a monolith.** Sources are first-class, pluggable, and lazy. The core ships with a small set; everything else is an extra or a plugin.
5. **Override mechanism is data, not magic.** The precedence order is an ordered list of sources passed at load time. There is no global mutable registry that mysteriously changes precedence based on import order.
6. **Annotated metadata is the override knob.** Per-field behavior (env name, CLI flag, secret marking, custom parser) is attached via `typing.Annotated` — the same pattern Typer uses. No decorators on individual fields, no class-level `Field(env=...)` calls that fight with type checkers.

---

## 2. Package Name & Layout

```
confiq/
├── pyproject.toml
├── src/
│   └── confiq/
│       ├── __init__.py          # public re-exports only
│       ├── _core/               # underscore = internal, not for import by users
│       │   ├── snapshot.py      # immutable resolved-config container
│       │   ├── resolver.py      # source merging & precedence
│       │   ├── locks.py         # threading + asyncio sync primitives
│       │   └── sentinel.py      # UNSET marker
│       ├── schema/
│       │   ├── settings.py      # the Settings base class
│       │   ├── field.py         # ConfigField metadata (the Annotated payload)
│       │   └── annotations.py   # helpers for reading Annotated[...]
│       ├── sources/
│       │   ├── base.py          # Source Protocol / ABC
│       │   ├── env.py           # built-in: environment variables
│       │   ├── memory.py        # built-in: in-memory dict
│       │   ├── file.py          # built-in: local file (toml/json/yaml gated by extras)
│       │   ├── cli.py           # built-in: argparse-backed CLI source
│       │   └── _registry.py     # source registration via entry points
│       ├── plugin/
│       │   ├── hookspecs.py     # pluggy hookspecs
│       │   ├── manager.py       # PluginManager wrapper
│       │   └── builtins.py      # internal plugins shipped by default
│       ├── errors.py            # exception hierarchy
│       └── py.typed             # PEP 561 marker
├── tests/
└── docs/
```

Two conventions worth calling out. First, `_core` is underscored to communicate "library internals" — the public surface lives in `confiq.__init__`, `confiq.schema`, `confiq.sources`, `confiq.plugin`, and `confiq.errors`. Second, every source module is independently importable: `confiq.sources.env` does not transitively pull in YAML parsers or boto3.

---

## 3. The Public API in One Glance

Before going deep on each subsystem, here is what end-user code looks like, so the rest of the proposal has a reference point.

```python
from typing import Annotated
from confiq import Settings, ConfigField, load
from confiq.sources import EnvSource, FileSource, CliSource

class DatabaseConfig(Settings):
    host: Annotated[str, ConfigField(env="DB_HOST")] = "localhost"
    port: Annotated[int, ConfigField(env="DB_PORT")] = 5432
    password: Annotated[str, ConfigField(env="DB_PASSWORD", secret=True)]

class AppConfig(Settings):
    debug: Annotated[bool, ConfigField(cli="--debug")] = False
    log_level: Annotated[str, ConfigField(env="LOG_LEVEL")] = "INFO"
    database: DatabaseConfig   # nested config — works transparently

config = load(
    AppConfig,
    sources=[
        FileSource("config.toml"),     # lowest precedence
        EnvSource(prefix="APP_"),
        CliSource(),                   # highest precedence
    ],
)

# `config` is a fully-typed, frozen AppConfig instance.
print(config.database.host)            # mypy/pyright know this is str
```

That's the steady-state. Everything else in this document explains how it works underneath.

---

## 4. Core Abstractions

The library is built on five concepts. Keeping the list this short is the point.

**`Source`** is anything that can produce a flat or nested mapping of values. Sources are lazy — `EnvSource(prefix="APP_")` is cheap; the actual `os.environ` scan happens at load time. Sources declare what keys they *could* provide but don't have to materialize them until asked. Sources can be sync or async; the resolver knows how to drive both.

**`Settings`** is the user-defined schema. It is a pydantic `BaseModel` subclass with one customization: it knows how to read `Annotated[..., ConfigField(...)]` metadata off its own fields and expose that to the resolver. Users get pydantic's validation, serialization, and editor support for free.

**`Resolver`** is the engine that takes a `Settings` class plus an ordered list of `Source` instances and produces a validated `Settings` instance. The resolver is where precedence rules, deep-merge semantics, and per-field overrides all meet. It is the only piece that does I/O.

**`Snapshot`** is the immutable result. Once a snapshot exists, it cannot be mutated. Reloads produce new snapshots; the current snapshot is replaced atomically. This is the heart of the thread-safety story.

**`PluginManager`** wraps pluggy and exposes the hook surface (described in §9). Internal subsystems call hooks at well-defined points so external code can extend behavior without subclassing.

---

## 5. Type Safety from Top to Bottom

Three layers of typing, each enforced by a different mechanism.

At **definition time**, `Settings` subclasses are pydantic models, which means mypy and pyright see the field types directly. `Annotated[str, ConfigField(...)]` does not change the public type of the field — it's still `str` to type checkers — but the metadata is reachable at runtime via `typing.get_type_hints(..., include_extras=True)`.

At **load time**, the resolver coerces raw values from sources through pydantic's validation pipeline. Type coercion failures produce a `ConfigValidationError` with the offending field path, the source that supplied the bad value, and the expected type. Failure is loud; failure is at the edge.

At **access time**, the returned object is just an instance of the user's `Settings` class. No `__getattr__` trickery, no string keys, no `.get("database.host")` calls unless the user explicitly opts in. Type checkers see `config.database.host: str` because that is literally what it is.

The `ConfigField` metadata class itself is a `@dataclass(frozen=True)` with typed fields — there is no `**kwargs: Any` escape hatch.

---

## 6. The `Annotated` Metadata System (Typer-style)

`ConfigField` is where per-key behavior is configured without polluting the class body or fighting type checkers. The shape:

```python
@dataclass(frozen=True)
class ConfigField:
    env: str | None = None              # explicit env var name
    cli: str | None = None              # explicit CLI flag
    file_key: str | None = None         # explicit dotted path in file sources
    secret: bool = False                # mask in repr, exclude from logs
    parser: Callable[[str], Any] | None = None   # custom string-to-value parser
    sources: tuple[str, ...] | None = None       # restrict which sources may set this
    deprecated: str | None = None       # warning message on use
    description: str | None = None      # for --help generation
```

Three things to notice. First, every field is typed; there is no `Any`. Second, the `sources` field lets a user say "this value only comes from env, never from files" — useful for secrets. Third, `parser` is a per-field escape hatch for when pydantic's coercion is wrong (e.g., comma-separated lists in env vars).

This is exactly the Typer pattern. The class hierarchy reads naturally to humans and to type checkers, and the metadata travels with the field instead of living in a separate registry.

For users who want even more control, `ConfigField` is intentionally subclassable. A `SecretField` shortcut, an `EnvOnlyField` shortcut, etc., can be ten-line wrappers.

---

## 7. The Source System (fsspec-style)

Sources are the I/O boundary. The contract is small:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Source(Protocol):
    name: str                              # for error messages
    def load(self) -> Mapping[str, Any]: ...

@runtime_checkable
class AsyncSource(Protocol):
    name: str
    async def load(self) -> Mapping[str, Any]: ...
```

The returned mapping uses dotted keys for nesting (`database.host`) or nested dicts; the resolver normalizes both. Sources do not validate — they just produce raw values. Validation is the schema's job.

**Built-in sources** (always available, no extras needed): `EnvSource`, `MemorySource`, `CliSource`. These three have zero non-stdlib dependencies.

**Bundled-but-gated sources** (in `confiq.sources` but require extras): `TomlFileSource`, `YamlFileSource`, `JsonFileSource`. The first two raise an informative `ImportError` at instantiation if the extra isn't installed, pointing to the right `pip install` command. JSON works out of the box.

**Optional sources via extras** (fsspec-style):

```toml
# pyproject.toml [project.optional-dependencies]
toml   = ["tomli; python_version<'3.11'"]
yaml   = ["pyyaml>=6"]
remote = ["fsspec>=2024.1"]               # generic remote file support
s3     = ["confiq[remote]", "s3fs"]
gcs    = ["confiq[remote]", "gcsfs"]
vault  = ["hvac>=2"]
consul = ["python-consul2"]
cli    = ["click>=8"]                     # richer CLI than stdlib argparse
all    = ["confiq[toml,yaml,remote,s3,gcs,vault,consul,cli]"]
```

The `[remote]` extra brings in `fsspec` itself, after which `FileSource("s3://bucket/key.toml")` Just Works for any protocol the user's installed filesystem backends support. This is precisely fsspec's own optionality story, applied to `confiq` one layer up.

**Third-party sources via entry points.** Sources are discoverable through `confiq.sources` entry points:

```toml
[project.entry-points."confiq.sources"]
aws_appconfig = "confiq_aws:AppConfigSource"
```

The registry lazy-loads these on first access. A user installs `confiq-aws` and `from confiq.sources import AppConfigSource` works without `confiq` itself needing to know about AWS.

---

## 8. Precedence & Resolution

The resolver takes an ordered list of sources. **Later sources override earlier ones, key by key**. This is the simplest rule that works, and it matches the mental model of "layered overrides."

```python
sources = [
    FileSource("/etc/myapp/config.toml"),    # base
    FileSource("~/.config/myapp.toml"),      # user override
    EnvSource(prefix="MYAPP_"),              # env override
    CliSource(),                             # cli wins
]
```

For nested values, the default merge strategy is **deep merge for mappings, replace for scalars and lists**. Lists are tricky — concatenation is sometimes wanted, replacement is sometimes wanted — so the merge strategy is configurable per load and overridable per field via `ConfigField`. Default is replace, because it's the least surprising.

The resolver walks the schema, not the sources. For each field, in order:

1. Determine the field's effective key in each source (using `ConfigField` metadata or the field name as fallback).
2. Ask each source for that key, in precedence order; the last one to provide a value wins.
3. If the field is a nested `Settings`, recurse.
4. If no source provided a value, use the pydantic default.
5. If there is no default and no value, raise `MissingConfigError` with the full field path and the sources that were consulted.

This walk-the-schema design means **the schema is the authority on what config exists**. Sources can provide extra unused keys; by default they are ignored, optionally warned about via a plugin hook.

Per-field source restriction (`ConfigField(sources=("env",))`) is enforced during this walk: a value supplied by a disallowed source is silently skipped (with a debug log), so a leaked-into-file secret doesn't accidentally take effect.

---

## 9. Thread & Async Safety (loguru-style "just works")

The user never touches a lock. The mechanism behind that:

**Loaded configs are immutable.** A `Settings` instance returned by `load()` is frozen (`model_config = ConfigDict(frozen=True)`). Reading any field is safe from any thread or any task because immutable objects cannot tear.

**Reloads are atomic snapshot swaps.** For users who want hot-reload behavior, `confiq` provides a `ConfigHandle[T]`:

```python
handle = ConfigHandle.create(AppConfig, sources=[...])
config = handle.current()         # cheap; returns the current snapshot
handle.reload()                   # builds a new snapshot, atomically swaps
config_async = await handle.reload_async()
```

Internally, `ConfigHandle.current()` returns a reference to an immutable snapshot. `reload()` builds the new snapshot off to the side, then assigns it under a short-held lock. Readers never block; they always see either the old snapshot or the new one, never a half-built one.

**Async sources are first-class.** The resolver detects `AsyncSource` instances and drives them via `asyncio.gather`. Sync and async sources can be mixed; sync sources run in a thread pool when called from `load_async`. The `load`/`load_async` split is explicit because async-detection-by-introspection is the kind of magic that backfires.

**File watching is optional.** A `WatchedFileSource` extra integrates with `watchdog` to trigger `handle.reload()` on file change. It uses an internal event-driven debounce so a rapid burst of editor saves produces one reload, not ten.

The combination — immutable snapshots, atomic swap, lazy lock acquisition only at swap time — is the loguru contract: the user does nothing, and concurrent access is correct.

---

## 10. Error Handling Philosophy

No `Result[T, E]`, no `Either`, no monadic wrappers. Python has exceptions; we use them well.

The rules:

Failures during `load()` raise. The exception hierarchy is shallow and informative:

```
ConfiqError                          # base, never raised directly
├── ConfigLoadError                  # something went wrong getting raw values
│   ├── SourceUnavailableError       # file missing, network failed
│   └── SourceParseError             # YAML/TOML/JSON malformed
├── ConfigValidationError            # value was wrong type / failed pydantic check
├── MissingConfigError               # required field had no source and no default
├── ConflictingConfigError           # sources disagree where conflict isn't allowed
└── PluginError                      # plugin hook raised
```

Every exception carries the field path (when applicable), the source name(s) involved, and the underlying cause. `__cause__` is set when wrapping a lower-level exception.

After `load()` succeeds, no `confiq` method on the returned config raises a `ConfiqError`. Reading `config.database.host` is exactly as safe as any other attribute access — because that's what it is.

Internal helpers prefer "total" signatures. Instead of a private `_lookup(key) -> Any | None` where `None` is ambiguous, we use `_lookup(key) -> LookupHit | LookupMiss` with discriminated dataclasses, or `_lookup(key, default: T) -> T`. This is the Rust influence applied at the layer where it pays off — internal correctness — without inflicting `Result`-style wrappers on users.

**One important nuance.** The user requirement was "no `Result`-based ideas" — I read that as: don't make users unwrap things. Internally, when we have a value-or-error situation, we use whatever Python idiom is clearest (often a small dataclass, sometimes a sentinel, sometimes a thrown-and-caught exception across a narrow boundary). The point is *deliberate* error handling, not a particular type-level encoding.

---

## 11. Plugin System (pluggy)

`confiq` ships with a `pluggy.PluginManager` and a defined hook surface. Plugins are discovered via the `confiq` entry-point group:

```toml
[project.entry-points."confiq"]
my_plugin = "my_package.plugin"
```

The hookspecs:

```python
import pluggy
hookspec = pluggy.HookspecMarker("confiq")

class ConfiqHooks:
    @hookspec
    def confiq_register_sources(self, registry: "SourceRegistry") -> None:
        """Called once at PluginManager init. Plugins register new Source classes."""

    @hookspec
    def confiq_pre_load(self, schema: type[Settings], sources: list[Source]) -> None:
        """Called before resolution begins. Plugins may mutate `sources` in place."""

    @hookspec(firstresult=True)
    def confiq_transform_value(
        self, field_path: str, value: Any, field_info: "FieldInfo"
    ) -> Any:
        """Transform a raw value before pydantic validation. Return value unchanged
        if not interested. First non-default return wins."""

    @hookspec
    def confiq_post_load(self, config: Settings) -> None:
        """Called after a successful load. Read-only; the config is frozen."""

    @hookspec
    def confiq_on_reload(self, old: Settings, new: Settings) -> None:
        """Called after a ConfigHandle reload. Useful for invalidating caches."""

    @hookspec
    def confiq_on_error(self, error: ConfiqError) -> None:
        """Called when load fails. Plugins may log, metric, or re-raise."""
```

A handful of internal subsystems are themselves implemented as plugins — the TOML parser, the secret-masking repr, the deprecation-warning emitter — which forces the hook surface to be expressive enough for real work. This is the same dogfooding move pytest makes with pluggy.

Plugins can also be passed explicitly to `load(..., plugins=[my_plugin])` for testing and for opt-in-only behavior, avoiding the "I installed a package and my config changed" footgun that entry-point-only discovery sometimes produces. A `confiq.disable_plugin("name")` knob exists for the same reason.

---

## 12. Optional Dependencies — The Full Picture

Recapping the extras strategy from §7 in one place, because this is something users will hit early:

The `confiq` core install has **zero non-stdlib runtime dependencies** beyond `pydantic` and `pluggy`. Everything else is opt-in. The extras are flat (not hierarchical, except `[all]`), named after the capability rather than the underlying library, and documented with the exact `ImportError` message a user will see if they forget. The `ImportError` includes the suggested `pip install confiq[xxx]` command, copy-pasteable.

This is fsspec's pattern: a small core, broad reach through extras, third-party packages plug in via entry points without forking. The capability words (`toml`, `yaml`, `remote`, `s3`) match user mental models; nobody types `pip install confiq[tomli]`.

---

## 13. Nesting & Storage Variety

Two requirements collapse into one mechanism. Nesting is just composition of `Settings` classes — a field whose type is another `Settings` is loaded recursively, with all the same source-precedence rules applying to its sub-keys. Storage variety is the source system — any backend that can be expressed as "give me a mapping" is a source.

The combination handles the realistic cases: app config in TOML, secrets from env, dev overrides on CLI; a `database: DatabaseConfig` nested model whose `password` field is `ConfigField(sources=("env",))`, so even if someone commits the file, the password can't come from it; a `features: FeatureFlags` nested model that reloads independently because it's wired to a separate `ConfigHandle` watching a different file.

For users who want a single flat config without nesting, the schema can be a flat `Settings` class — nothing forces nesting. For users who want extreme nesting (Hydra-style composition), `MemorySource` plus a small helper that loads multiple files into a layered dict is enough; we don't need a separate compositional sub-language.

---

## 14. CLI Integration

The built-in `CliSource` uses `argparse` and generates flags from the schema automatically. Each field with `ConfigField(cli=...)` gets a flag; the `description` populates the help text; the type drives the parser. For users who want richer CLI (subcommands, prompts, colors), the `confiq[cli]` extra brings in `click`, and `ClickSource` exposes the same automatic-generation behavior on top of click.

Crucially, the CLI source does **not** call `sys.exit()` on `--help`. It's a config source, not a program. Users who want `--help` integrated with their program's argparse use `confiq.cli.attach(parser, AppConfig)`, which adds the right arguments to *their* parser and returns a source that reads from the parsed namespace.

For Typer users specifically, an adapter ships under `confiq.cli.typer` so an existing Typer command can yield a `Settings` instance with one decorator.

---

## 15. Testing & Mocking Story

Two patterns make tests painless.

**`MemorySource` for hermetic tests.** Any test that needs a specific config just builds it:

```python
config = load(AppConfig, sources=[MemorySource({"database": {"host": "test-db"}})])
```

**`confiq.testing.override(config_handle, **overrides)`** as a context manager swaps in a modified snapshot for the duration of the block and restores it on exit. The snapshot model makes this trivially correct, even with concurrent readers.

Plugins can be enabled per-test by passing `plugins=[...]` to `load()`, sidestepping the entry-point auto-discovery. This is the same pattern pytest uses for its own plugins and it works well.

---

## 16. Non-Goals & Deliberate Omissions

A few things `confiq` is choosing **not** to do, because every one of them is a tradeoff and clarity now saves arguments later.

No interpolation/templating syntax (no `${VAR}` inside config files). Sources handle their own interpolation if they want; the resolver doesn't. This keeps the merge semantics predictable.

No schema migration / versioning built in. Users who need it write a `confiq_pre_load` plugin. The library shouldn't pick a migration framework for users.

No automatic secret-fetching from cloud KMS at field-access time. Secrets are loaded at `load()` time like everything else; users who want lazy fetching write a custom source. This keeps the "after load, attribute access never raises" invariant intact.

No global "default config" singleton. Users who want one write `CONFIG = load(...)` at module top level. The library will not own that variable.

---

## 17. Open Questions / Decisions for Discussion

These are the spots where I have a leaning but the call is worth explicit agreement before any code gets written.

**Pydantic v2 only, or v1+v2?** Recommendation: v2 only. v1 is in maintenance mode, and the v2 `Annotated` story is materially better. This rules out a small population of legacy users, but supporting both doubles the test matrix.

**`Settings` as a pydantic `BaseModel` subclass, or composition?** Recommendation: subclass. Composition (wrapping a model) hides editor support and breaks `isinstance`. Subclassing is what pydantic-settings does and users expect.

**Async-first or sync-first internals?** Recommendation: sync-first with an async adapter. Most config loading is at startup where sync is fine; the async path is for hot-reload and remote sources. Building async-first and adapting to sync is more code for marginal benefit.

**Should `ConfigHandle` be the default, or `load()` returning a bare `Settings`?** Recommendation: `load()` returns a bare `Settings` (90% case), `ConfigHandle` is opt-in for reload scenarios. The two-function API is small.

**Plugin auto-discovery on by default?** Recommendation: on, but with `CONFIQ_DISABLE_AUTOLOAD=1` env var and a `disable_plugin()` API. Matches pytest. Users who are surprised by behavior changes from installed packages can audit with `confiq.list_plugins()`.

---

## 18. Roadmap Sketch

A reasonable order of implementation, smallest-first:

1. Core: `Settings`, `ConfigField`, `MemorySource`, `EnvSource`, the resolver, the exception hierarchy. This alone is a usable library.
2. File sources: `JsonFileSource`, `TomlFileSource`, `YamlFileSource` (extras-gated).
3. `ConfigHandle` and the snapshot/reload mechanism.
4. Pluggy integration and the first internal plugins.
5. CLI source (argparse).
6. Async sources and `load_async`.
7. fsspec integration for remote files.
8. Watching, click adapter, typer adapter.
9. The first external-plugin reference implementation (Vault or AWS AppConfig).

Each step is independently shippable. The `1.0` line is somewhere around step 5 — once plugins exist, the public contract is stable.

---

## Summary

`confiq` is a pydantic-settings-shaped library with fsspec-shaped optionality, loguru-shaped safety, typer-shaped per-field metadata, and pluggy-shaped extensibility. The Rust influence shows up as: explicit failure at the edge, immutable values once constructed, total functions where possible internally — but the *interface* stays Pythonic. No `Result`, no `Either`, no monads — just well-typed Python with deliberate error handling.

The core stays small. The extras do the heavy lifting. The plugin surface lets third parties extend without forking. And — because configuration is the kind of code that lives forever once shipped — every public commitment in this proposal is one we should be willing to keep for years.
