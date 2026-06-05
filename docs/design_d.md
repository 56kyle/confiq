# `confiq` — Design Specification (`design_d`)

> A configuration library for Python that treats configuration as an immutable, typed
> value computed from an explicit, ordered list of sources — and treats the command line
> and the test suite as first-class parts of that computation rather than afterthoughts.

This is a complete, standalone specification. It supersedes `design_c.md`. Companion
documents: `confiq_architecture.md` (narrative) and the design-axes record. A small number
of signature-level choices are marked **(provisional)** and collected in §14; everything
else is settled.

---

## 1. Purpose and scope

`confiq` reconciles three things that are normally wired together by hand and break
independently: **configuration**, the **command line**, and the **test suite**.

The motivating pain is concrete: building an application with `pydantic-settings` and a CLI
framework means maintaining the state relationship between config and CLI by hand, and then
fighting that same global state in `pytest` — rebuilding fixtures, leaking environment
variables between tests, monkeypatching settings into shape. Each corner is individually
solved; the seams are where the time goes.

`confiq` treats the triangle as one problem. Configuration is computed once into an ordinary
typed value; the CLI is just another source feeding that computation; and because the result
is a plain value with no global identity, testing it means constructing values, not mutating
and restoring shared state.

---

## 2. Design principles

1. **Configuration is a value, not an object with identity.** `load()` returns an instance
   of the schema you declared. There is no ambient `confiq.config` and no library-owned
   singleton.
2. **Precedence is data, not magic.** The order in which sources win is the order of the
   list you pass to `load()`. No hidden priority, no implicit environment discovery.
3. **The schema is yours.** No base class is required. A schema may be a pydantic
   `BaseModel`, a pydantic dataclass, a stdlib dataclass, a `TypedDict`, or nothing
   (schemaless).
4. **Type safety by default, opt-out on purpose.** The common path is fully typed with no
   `Any` on reads. Every relaxation is an explicit, named choice.
5. **Immutability is the basis of safety.** Thread safety falls out of returning an
   immutable value; the only mutation is opt-in live reload.
6. **No DSL in the values.** No string interpolation, computed expressions, or object
   instantiation inside config values. Computed values are the job of a *source*.

---

## 3. The configuration value

`load(schema, sources) -> T` returns an instance of the **declared type** — not a library
wrapper, not a forced pydantic value. `isinstance(config, YourType)` holds; the `-> T`
annotation is honest; the type checker sees your exact type.

Because the returned type is the one you declared, `confiq`'s guarantees form an explicit
**gradient** rather than a constant. This is intentional:

| Schema type | Access | Mutability | Secret-masked `repr` | Rich serialization |
|---|---|---|---|---|
| `BaseModel(frozen=True)` | attribute | immutable | full | full (`model_dump`) |
| `BaseModel` (default) | attribute | mutable | full | full |
| `@dataclass(frozen=True)` | attribute | immutable | invasive¹ | via `TypeAdapter` |
| `@dataclass` | attribute | mutable | invasive¹ | via `TypeAdapter` |
| `TypedDict` | subscript | mutable dict | none² | already a dict |
| schemaless | subscript | read-only `Mapping` | none | none |

¹ Masking a secret on a stdlib dataclass requires `confiq` to generate a custom `__repr__`.
² A `TypedDict` resolves to a plain dict with nowhere to hang a masked repr.

Two consequences are stated loudly, not buried:

- **The immutability pillar holds only when the schema is frozen.** Frozen pydantic is the
  safe default; a non-frozen dataclass yielding mutable config is a legitimate informed
  choice. The lock-free-read guarantee in §9 applies only to frozen schemas.
- **Richer per-field features — secret masking in particular — are pydantic-strong** and
  degrade on other schema types.

The honest pitch: bring any structure; frozen pydantic is where every guarantee is on, and
each step away trades one named guarantee for one named convenience, visibly.

---

## 4. Schemas

### 4.1 Accepted schema types

`BaseModel`, pydantic dataclass, stdlib dataclass, `TypedDict`, and schemaless (`schema=None`).
No `confiq` base class is required. An existing dataclass or `TypedDict` is accepted without
rewriting it as a pydantic model.

### 4.2 Field annotations

Per-field configuration metadata travels in `Annotated[...]` as a frozen `ConfigField`:

```python
@dataclass(frozen=True)
class ConfigField:
    env: str | None = None                     # explicit env var name (overrides the convention)
    secret: bool = False                       # mask in repr and in error output
    parser: Callable[[str], Any] | None = None # pre-validation coercion from a raw string
```

There is no `cli` member: CLI binding lives on the CLI parameter (see §10), not on the
schema field. Example schema, with no `confiq` import required for the types themselves:

```python
class Database(BaseModel):
    host: str = "localhost"
    port: int = 5432
    password: Annotated[str, ConfigField(secret=True)] = ""

class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)
    database: Database = Database()
    debug: bool = False
```

### 4.3 The `SchemaAdapter`

A `SchemaAdapter` abstracts the two operations the rest of the system needs from a schema:
reading per-field metadata, and validating a mapping into an instance of the declared type.
It is the load-bearing wall behind multi-schema support.

```python
class SchemaAdapter(Protocol[T]):
    def field_metadata(self) -> Mapping[str, list[Any]]: ...
        # field name → the Annotated *extras* for that field (incl. ConfigField). Not the
        # bare type — callers that need the type hold the schema class directly.
    def validate(self, data: Mapping[str, Any]) -> T: ...
        # validate/coerce the merged mapping into an instance of the declared type.
```

Adapters are resolved through a pluggy hook (`confiq_get_schema_adapter`), so new schema
kinds can be added without touching the core.

### 4.4 Metadata reading is per-adapter

- **pydantic** schemas read `ConfigField` from pydantic's own `FieldInfo.metadata` — the
  same view the validator uses, with no second introspection path and none of the PEP 563 /
  forward-reference fragility that comes from calling `get_type_hints` independently.
- **stdlib dataclass and `TypedDict`** adapters read `Annotated` metadata via
  `get_type_hints(include_extras=True)`, which those types require. The fragility is
  accepted because it is confined to them.

### 4.5 Validation engine

All schema types validate and coerce through pydantic's **`TypeAdapter`**, which natively
handles models, pydantic and stdlib dataclasses, and `TypedDict`s
(`TypeAdapter(schema).validate_python(merged)`). One engine, one set of validation
semantics. There is no per-type bespoke validator and no use of `model_validate` as the
universal path. pydantic is therefore a genuine, mandatory core dependency.

### 4.6 Type safety and the typed-open middle ground

The default is fully typed with no `Any` on reads. The typed-open middle ground — a typed
core plus a permissive extra section — is available via `ConfigDict(extra="allow")` on
pydantic schemas (extras land in `__pydantic_extra__`) and via an explicit
`extra: dict[str, Any]` field on dataclasses and `TypedDict`s. Schemaless mode (§7.3) is the
full opt-out.

---

## 5. Sources and loaders

### 5.1 `Source`

A source is *where* configuration comes from. It yields a mapping and carries two pieces of
declarative behavior beyond fetching:

```python
@runtime_checkable
class Source(Protocol):
    name: str                                   # for provenance and error messages
    mode: Literal["override", "fill"]           # default "override" (see §5.5)
    profile: str | None                         # default None (see §5.6)
    def fetch(self) -> Mapping[str, Any]: ...
```

A `BaseSource` convenience class supplies the defaults (`mode="override"`, `profile=None`)
so concrete sources need only implement `name` and `fetch`.

### 5.2 `AsyncSource`

Async sources implement a separate protocol rather than coloring the sync one:

```python
@runtime_checkable
class AsyncSource(Protocol):
    name: str
    mode: Literal["override", "fill"]
    profile: str | None
    async def fetch_async(self) -> Mapping[str, Any]: ...
```

### 5.3 `Loader`

A loader is *what format* raw bytes are in. The split (Koanf-style) means a new file format
is one small object and a new backend is another, with no combinatorial explosion.

```python
class Loader(Protocol):
    def parse(self, raw: bytes) -> Mapping[str, Any]: ...
```

### 5.4 Built-in sources and their extras

| Source | Purpose | Dependency / extra |
|---|---|---|
| `EnvSource(prefix=..., delimiter="__")` | environment variables | core (stdlib) |
| `DotenvSource(path)` | `.env` files | `[dotenv]` (python-dotenv) |
| `FileSource(path, loader=...)` | local files | core for local I/O; `[remote]` (fsspec) for remote URIs |
| `MemorySource(mapping)` | in-process data; the testing workhorse | core |
| `ClickSource` / `TyperSource` | consume an existing Click/Typer command | `[cli]` (click/typer) |
| `ArgparseSource` | consume an argparse namespace | core (argparse is stdlib) |
| cloud secret/param stores | AWS/GCP/Vault | `[aws]`, `[gcp]`, `[vault]` |

Loaders: JSON (core), YAML (`[yaml]`), TOML (stdlib `tomllib` on 3.11+, `[toml]` otherwise).

### 5.5 `mode`: override vs fill

`mode="override"` (default) is normal precedence — the source clobbers prior values for keys
it supplies. `mode="fill"` contributes only keys *not already supplied* by a
higher-precedence source: a defaults layer that cannot accidentally overwrite real values.

### 5.6 `profile`

A source may carry a `profile` tag. When `load(..., profile="prod")` is called, a source
participates only if its `profile` is `None` (untagged sources always participate) or equals
the selected profile. Nothing is auto-discovered; the user composes the list and names the
profile explicitly. Profiles are sugar over the explicit list, not a new precedence
mechanism — the same outcome is expressible by composing different lists.

---

## 6. Composition and resolution

### 6.1 Precedence

Precedence is the source list, lowest first. The list is the complete precedence
specification. Higher-index sources win on collision.

### 6.2 The resolver algorithm

Given a schema (possibly `None`) and an ordered list of sources:

1. **Profile filter.** If `profile` is given, drop any source whose `profile` is set and
   does not equal it.
2. **Fetch.** Drive each remaining source in order. `Source.fetch()` returns a mapping;
   file-backed sources read bytes (stdlib for local paths, fsspec for remote) and pass them
   through their `Loader`. Env/CLI sources map their flat keys onto config paths using the
   name convention (prefix + delimiter), with `ConfigField.env` / `ConfigBind` overrides.
3. **Merge.** Deep-merge the mappings low → high. For `mode="override"` sources later wins;
   for `mode="fill"` sources a key is contributed only if absent so far. Lists are replaced,
   not concatenated. A parallel **provenance** map records the winning source name per leaf.
4. **Adapter.** Resolve the `SchemaAdapter` for the schema type via the pluggy hook
   (`schema=None` selects the schemaless adapter).
5. **Coerce.** Read `field_metadata`; apply each field's `ConfigField.parser` to raw string
   values before validation.
6. **Validate.** `adapter.validate(merged)` constructs the typed value. On failure, raise
   `ConfigValidationError` carrying the field path and the provenance (which source supplied
   the offending value) in the human-readable message.
7. **Return** the value.

### 6.3 Merge semantics

Deep-merge, list-replacement. List-replacement is deliberate and legible: a higher source's
list replaces a lower one's rather than accumulating, so "reset this list" is expressible.

### 6.4 Provenance

Provenance is tracked during the merge **and surfaced in error messages** — a validation or
missing-field error names the source responsible, rather than provenance being internal
bookkeeping only.

---

## 7. Loading API

### 7.1 `load` (synchronous)

```python
def load(schema: type[T], sources: Sequence[Source], *, profile: str | None = None) -> T: ...
```

`load()` accepts only synchronous sources. Handed an `AsyncSource`, it raises a clear error
directing the caller to `load_async()`. There is no `ThreadPoolExecutor` + `asyncio.run()`
bridge — that approach is explicitly rejected for its event-loop and `ContextVar`-propagation
hazards.

### 7.2 `load_async`

```python
async def load_async(schema: type[T],
                     sources: Sequence[Source | AsyncSource],
                     *, profile: str | None = None) -> T: ...
```

Drives `AsyncSource`s natively (gathered on the running loop) and sync sources inline.

### 7.3 Schemaless

`load(None, sources)` (and `load_async(None, sources)`) returns a `SchemalessConfig` — a
read-only `Mapping` supporting `config["a"]["b"]` subscript access. No types, no validation,
no nesting guarantees beyond the merged structure.

---

## 8. Configuration lifecycle: value vs handle

### 8.1 The default

Call `load()`, receive a value, use it. This covers the overwhelming majority of cases and
is what makes testing trivial.

### 8.2 `ConfigHandle`

For applications that must pick up configuration changes at runtime, `ConfigHandle[T]` is the
explicit opt-in. It owns a current snapshot, swaps it atomically on reload, and notifies
subscribers.

```python
class ConfigHandle(Generic[T]):
    @classmethod
    def create(cls, schema: type[T],
               sources: Sequence[Source | AsyncSource],   # positional (provisional, §14)
               *, loop: AbstractEventLoop | None = None,
               plugins: list[object] | None = None) -> "ConfigHandle[T]": ...

    @property
    def current(self) -> T: ...                            # property (provisional, §14)

    def reload(self) -> T: ...
    async def reload_async(self) -> T: ...

    def on_reload(self, fn: Callable[[T, T], Any]) -> Callable[[], None]: ...
        # fn receives (old, new); returns a disconnect callable (provisional, §14)
```

- `loop` is used to schedule async subscribers when the handle is driven by sync `reload()`
  (see §9.3).
- `plugins` registers per-handle plugins that persist across reload cycles (the handle owns a
  persistent `PluginManager`).

### 8.3 The user-owned singleton

If an application wants ambient access, it builds its own module-level object over `load()`
or a `ConfigHandle`. `confiq` never owns it. Example:

```python
# myapp/config.py
settings = load(Settings, sources=[...])
```

---

## 9. Concurrency and async model

### 9.1 Lock-free reads

For a frozen schema the value is immutable, so `ConfigHandle.current` is a single atomic
attribute read under CPython with no torn-read hazard and no lock. Thread safety is a
property of immutability, not of a locking discipline. (For non-frozen schemas the value is
mutable; the lock-free guarantee does not apply — see §3.)

### 9.2 Reload is copy-on-write

`reload()` recomputes a fresh snapshot off to the side, then takes a short write lock only to
swap the reference. A `ReentrancyGuard` fast-fails if a reload triggers a reload. All
concurrency cost lives here, in the opt-in path — never in the common `load()` case.

### 9.3 Notifications

`on_reload` is modeled on a **blinker** signal: weak-referenced subscribers (a handler's
lifetime is not accidentally extended) and documented connect/disconnect semantics, instead
of a bespoke callback list.

Subscribers may be sync or async. `reload_async()` drives async subscribers on the running
loop (gathered and awaited); sync subscribers run inline after the swap. `reload()` runs sync
subscribers on a daemon thread outside the lock; an async subscriber attached to a handle
driven only by sync `reload()` requires the `loop` provided at `create()` time and is
scheduled via `loop.call_soon_threadsafe`. No subscriber may call `reload()` synchronously.

### 9.4 Async entry points

Async is a clean second entry point, not a colored twin of every method. `Source` and
`AsyncSource` are separate protocols; `load`/`reload` are sync; `load_async`/`reload_async`
are async. Sync entry points reject async sources rather than bridging them.

---

## 10. CLI integration

### 10.1 Philosophy

`confiq` is a **consumer** of whichever CLI framework the application already uses — Typer,
Click, or argparse. It never owns or generates the command by default. This keeps integration
seamless and keeps the framework's full option surface out of `confiq`'s maintenance burden.
The CLI is just another source, slotted into the precedence list at the position the
application chooses (typically highest).

### 10.2 Consumer path (default)

The application writes its command as normal. `confiq` reads only the parameters the user
**explicitly set** and folds them in as a source. Two rules make this painless:

- **Defaults live only in the schema.** Consumer-path CLI options omit their defaults (or use
  an unset sentinel), so a value is never declared in two places.
- **Convention binding.** A parameter maps to its config path by name (dotted path +
  delimiter, e.g. `db_host` ↔ `database.host`). An explicit `ConfigBind("database.host")`
  annotation (Typer/Click) — or a `bind={...}` dict entry (argparse) — is needed only when
  the CLI name and the config path diverge.

```python
@app.command()
def main(
    db_host: Annotated[str | None, typer.Option()] = None,            # convention-bound to database.host
    log_level: Annotated[str | None, typer.Option(), ConfigBind("logging.level")] = None,
) -> None:
    settings = load(Settings, sources=[
        EnvSource(prefix="APP"),
        TyperSource(),            # highest precedence; contributes only explicitly-set options
    ])
```

### 10.3 Explicit-set detection

- **Click/Typer:** use `Context.get_parameter_source()` to distinguish a user-supplied value
  from a framework default.
- **argparse:** prefer sentinel defaults — arguments declared with `default=argparse.SUPPRESS`
  are simply absent from the namespace when unspecified, which is unambiguous. Comparing
  against `parser.get_default()` is the degraded fallback (it cannot tell a user-supplied
  value that equals the default).

### 10.4 Opt-in generator

For applications that want a single declaration site (add a field → get a flag),
`confiq.cli.options_from(schema)` emits options from the schema. Because `confiq` controls the
generated options, it sets their defaults to the unset sentinel automatically, so the
"no duplicated default" property comes for free on this path. Both paths obey the same
name↔path convention — the consumer path runs it backward (parameter → path), the generator
runs it forward (path → parameter); they never disagree.

### 10.5 Framework support is asymmetric

| | Consume (read what the user set) | Generate (emit options from schema) |
|---|---|---|
| Click | easy — `Context` + `get_parameter_source()` | easy — imperative (`params=[...]`) |
| Typer | easy — Click underneath | awkward — signature-driven; params can't be injected |
| argparse | awkward — sentinel needed, no annotations | easy — imperative (`add_argument`) |

Each framework is hard on exactly one side; Click is easy on both. The generator therefore
lives most naturally at the Click layer; Typer generation needs a drop-to-Click path or a
Typer-aware command factory. This asymmetry is documented rather than hidden behind a promise
of symmetric behavior.

---

## 11. Testing

A first-class goal, not a consequence. Because configuration is a plain value with no global
identity, a test constructs the value it wants instead of mutating and restoring shared state.

The core provides the primitives the testing story rests on: `MemorySource` (in-process data)
and `context.override()` (a `ContextVar`-based scoped override, async-safe). A `pytest-confiq`
plugin — modeled on Rust Figment's `Jail` — delivers the fixtures:

- a `config` fixture that builds from a `MemorySource` base, overridable per test and per
  parametrization;
- an autouse isolation fixture so no environment or file source leaks into a test unless
  added explicitly — what `monkeypatch` otherwise forces you to do by hand;
- layering helpers so a test can say "the production sources, but with this one value
  overridden" without rebuilding the stack;
- async support via `context.override()`, giving per-task config isolation in async tests.

Two requirements fall back onto the core so the plugin stays thin: `MemorySource` and
`override()` must be ergonomic, and the resolver must support cheaply splicing or overriding a
single key in an existing source list.

---

## 12. Extension and packaging

### 12.1–12.3 Extension surfaces

- **Built-in cloud sources behind extras** (`confiq[aws]`, …) ship in-tree so they share one
  `Source` contract and release in lockstep with it.
- **A `confiq.sources` entry-point group** lets third parties publish sources discovered
  without a pull request.
- **pluggy hookimpls** cover stateless transforms and adapter resolution, including
  `confiq_get_schema_adapter`.
- **Per-handle plugins** may also be registered directly on a `ConfigHandle` via
  `create(plugins=...)`; the handle owns a persistent `PluginManager` whose registrations
  survive reloads (provisional, §14).

### 12.4 Dependency discipline

The governing rule (Koanf-style): **the core depends on nothing optional.** Core runtime
dependencies are `pydantic` (≥2), `pluggy`, and `blinker`. Everything else — CLI frameworks,
dotenv parsing, YAML/TOML loaders for non-stdlib formats, fsspec for remote filesystems, and
all cloud SDKs — sits behind an extra. A user who only reads environment variables installs
none of them. (This corrects `design_c`'s treatment of `typer`/`python-dotenv` as mandatory;
local file reading uses the stdlib so fsspec is needed only for remote URIs.)

---

## 13. Error handling

```
ConfiqError                     # base
├── SourceError                 # a source failed to fetch
├── SchemaError                 # no adapter for the schema type, or schema misconfigured
├── MissingConfigError          # a required field is absent from all sources
└── ConfigValidationError       # validation/coercion failed
```

`MissingConfigError` and `ConfigValidationError` carry the dotted field path and the
contributing source names (provenance) and surface them in the human-readable message, so a
failure says where the offending value came from. Secret fields (`ConfigField(secret=True)`)
are masked in all error output on pydantic schemas.

---

## 14. Provisional decisions

These signature-level points were not separately deliberated; the conservative call is
recorded here and is easy to override.

1. **`ConfigHandle.current` is a property** (not a method). Reads more naturally for an
   immutable snapshot and avoids `handle.current()`. Affects all call sites if reversed.
2. **`create()` takes `sources` positionally** (matching `load()`'s shape in this spec).
   Keyword-only is the more defensive alternative.
3. **`create()` retains `plugins`.** `design_c` Decision 10 made per-handle plugin
   registration a deliberate feature (persistent `PluginManager` across reloads); it is kept
   rather than silently dropped. Open question: keep it, or require all per-handle
   registration to go through entry points / hookimpls.
4. **`on_reload(fn)` passes `(old, new)` and returns a disconnect callable.** The `(old, new)`
   arity preserves `design_c`'s richer signature (useful for diffing); the disconnect return
   suits weak-referenced blinker subscribers better than returning `fn` for decorator use.
   Open question: is the old value needed, and should the return be a disconnect handle or the
   function itself.

---

## 15. Non-goals

Deliberate refusals, recorded so they do not creep back in:

- **No value interpolation or expression DSL.** Computed values are a source's job, not the
  value's.
- **No magic environment discovery.** Precedence and profile selection are always explicit.
- **No library-owned global singleton.** Ambient access is built by the application.
- **`confiq` does not own the CLI command.** It consumes the user's command by default; the
  generator is additive and never required.
- **No mandatory optional dependencies.** The core installs no CLI framework, dotenv parser,
  remote-filesystem layer, or cloud SDK.
- **No sync→async bridging.** Sync entry points reject async sources rather than smuggling an
  event loop into a worker thread.
