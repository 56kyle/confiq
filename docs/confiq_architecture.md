# `confiq` — Architecture

> A configuration library for Python that treats configuration as an immutable,
> typed value computed from an explicit, ordered list of sources — and that treats
> the CLI and the test suite as first-class parts of that computation rather than
> afterthoughts.

This document describes the architecture and the reasoning behind it. Companion
documents: `confiq_design_axes.md` (the per-axis decision record) and
`confiq_config_landscape.md` (the cross-ecosystem survey that situates these choices).

---

## 1. Purpose

`confiq` exists to reconcile three things that are normally wired together by hand and
break independently: **configuration**, the **command line**, and the **test suite**.

The motivating pain is concrete: building an application with `pydantic-settings` and
Typer means maintaining the state relationship between config and CLI by hand, and then
fighting that same global state in `pytest` — rebuilding fixtures, leaking environment
variables between tests, and monkeypatching settings objects into the right shape. Each
of the three corners is individually solved by some library; the seams between them are
where the time goes.

`confiq` addresses the triangle as a single problem. Configuration is computed once into
an ordinary typed value; the CLI is just another source feeding that computation; and
because the result is a plain value with no global identity, testing it is a matter of
constructing values, not of mutating and restoring shared state.

---

## 2. Design principles

**Configuration is a value, not an object with identity.** `load()` returns an instance
of the schema you declared. There is no ambient `confiq.config` to import and no
library-owned singleton. If an application wants a process-wide config object, it
creates one in its own module. This is what makes the result trivial to pass around, to
compare, and above all to test.

**Precedence is data, not magic.** The order in which sources win is the order of the
list you pass to `load()`. There is no hidden priority table, no implicit environment
discovery, and no convention that silently changes which file is read. Reading the call
tells you the entire precedence story.

**The schema is yours.** `confiq` does not require a base class. A schema can be a
pydantic `BaseModel`, a pydantic dataclass, a stdlib dataclass, a `TypedDict`, or nothing
at all (schemaless). You never redefine an existing structure to use it here.

**Type safety by default, opt-out on purpose.** The common path is fully typed with no
`Any` on reads. Users who want less can have it — a wide-open `extra` section, or fully
schemaless — but every relaxation is an explicit choice with a named cost, never an
accident.

**Immutability is the basis of safety.** Thread safety is not bolted on with locks; it
falls out of returning an immutable value. The only place mutation exists is live reload,
and that is an opt-in wrapper, not the default.

**No DSL in the values.** `confiq` deliberately does not implement string interpolation,
computed expressions, or object instantiation inside config values. Those turn config
evaluation into a stateful graph, which is precisely what the immutable-value model
refuses. Computed values, when needed, are the job of a *source*, not of the value.

---

## 3. Where `confiq` sits

In the taxonomy of configuration libraries, `confiq` belongs to the family that
**composes providers and extracts a single typed value** — the same family as Rust's
Figment and, in Python, `pydantic-settings`. It is, in one line, *Figment for Python with
pydantic validation and a first-class testing story*, built on a Koanf-style separation
of "where config comes from" (sources) and "what format it's in" (loaders).

It deliberately is **not** in the global-mutable-accessor family (viper, dynaconf), the
interpolation-graph family (Hydra/OmegaConf), or the schema-owns-the-CLI family
(`pydantic-settings`' `CliApp`, clap-derive). Its closest incumbent is
`pydantic-settings`; the differences that justify its existence are the explicit ordered
source list (versus `settings_customise_sources`), pluggable sources and loaders, a real
testing story, and CLI integration that *consumes* the user's existing Typer/Click/argparse
command rather than owning a parser.

---

## 4. The load pipeline

A single pipeline underlies everything. Given a schema and an ordered list of sources:

```
sources (ordered, low → high precedence)
   │
   ▼
 fetch()  ──►  each source yields a Mapping[str, Any]
   │           (file/remote sources hand raw bytes to a Loader first)
   ▼
 merge    ──►  deep-merge in list order; lists replace; mode=fill never clobbers
   │           a parallel provenance map records the winning source per leaf
   ▼
 validate ──►  SchemaAdapter validates the merged mapping via pydantic TypeAdapter
   │           and constructs an instance of the declared schema type
   ▼
 value (T) ──► immutable when the schema is frozen; this is what load() returns
```

The pipeline is the same whether it runs synchronously (`load`) or asynchronously
(`load_async`); the only difference is how sources are driven. Live reload re-runs the
pipeline and atomically swaps the result.

---

## 5. Core abstractions

### 5.1 Sources

A **source** is *where* configuration comes from: a file, environment variables, CLI
flags, an in-memory mapping, or a remote store. Sources are plain objects that yield a
mapping. They carry two pieces of declarative behavior beyond fetching:

```python
class Source(Protocol):
    name: str                                  # for provenance and errors
    mode: Literal["override", "fill"] = "override"
    profile: str | None = None                 # participates only if this profile is selected
    def fetch(self) -> Mapping[str, Any]: ...
```

`mode="fill"` lets a source contribute only the keys not already supplied by a
higher-precedence source — a defaults layer that cannot accidentally clobber real values.
`profile` is the hook for explicit profiles (§5.5).

Asynchronous sources implement a separate protocol rather than coloring the sync one:

```python
class AsyncSource(Protocol):
    name: str
    async def fetch_async(self) -> Mapping[str, Any]: ...
```

### 5.2 Loaders

A **loader** is *what format* raw bytes are in — JSON, YAML, TOML. The split mirrors
Koanf: any source that produces bytes can be paired with any loader, so a new file format
is one small object and a new backend is another, with no combinatorial explosion.

```python
class Loader(Protocol):
    def parse(self, raw: bytes) -> Mapping[str, Any]: ...
```

### 5.3 The `SchemaAdapter` (the spine)

Because a schema can be any of several types, a `SchemaAdapter` abstracts two operations
the rest of the system needs: reading per-field metadata, and validating a mapping into
an instance of the declared type. This abstraction is the load-bearing wall that makes
multi-schema support coherent.

```python
class SchemaAdapter(Protocol):
    def field_metadata(self) -> Mapping[str, list[Any]]: ...  # Annotated extras (incl. ConfigField)
    def validate(self, data: Mapping[str, Any]) -> T: ...      # returns an instance of the declared type
```

Adapters are resolved through a pluggy hook (`confiq_get_schema_adapter`), so new schema
kinds can be added without touching the core. Two adapter-level rules are fixed:

- **Metadata is read the right way per type.** For pydantic schemas, `ConfigField` is
  read from pydantic's own `FieldInfo.metadata` — the same view the validator uses, with
  no second introspection path and none of the PEP 563 / forward-reference fragility that
  comes from calling `get_type_hints` independently. For stdlib dataclasses and
  `TypedDict`s, which have no `FieldInfo`, the adapter reads `Annotated` metadata via
  `get_type_hints(include_extras=True)` — unavoidable for those types, and acceptable
  because it is confined to them.
- **One validation engine.** All schema types are validated and coerced through pydantic's
  `TypeAdapter`, which natively handles models, pydantic and stdlib dataclasses, and
  `TypedDict`s. This keeps "typed by default" universal without writing four validators,
  and it means pydantic is a genuine core dependency.

### 5.4 Precedence and merging

Precedence is the source list, low to high. Merging is **deep** (nested mappings merge
recursively) and **list-replacing** (a higher source's list replaces a lower one's rather
than concatenating). Alongside the merged mapping, the pipeline builds a **provenance**
map recording which source supplied each winning leaf. Provenance is not internal
bookkeeping only: it is surfaced in error messages, so a validation failure can say
exactly where the offending value came from — the single cheapest high-value feature
borrowed from Figment.

### 5.5 Profiles

Profiles are a thin, opt-in convenience layered on the explicit source list, not a new
precedence mechanism. A source may tag itself with a profile name; selecting a profile at
load time filters which tagged sources participate. Nothing is auto-discovered — the user
still composes the list and names the profile explicitly — so this preserves the "no
magic" principle while giving a clean way to express environment variants. Applications
that prefer it can ignore profiles entirely and express the same thing by composing
different source lists.

---

## 6. Config identity and lifecycle

The default lifecycle is the simplest possible: call `load()`, receive a value, use it.

```python
def load(schema: type[T], sources: Sequence[Source], *, profile: str | None = None) -> T: ...
```

For applications that must pick up configuration changes at runtime, `ConfigHandle[T]` is
the explicit opt-in. It owns a current snapshot, swaps it atomically on reload, and
notifies subscribers.

```python
class ConfigHandle(Generic[T]):
    @classmethod
    def create(cls, schema: type[T], sources: Sequence[Source],
               *, loop: AbstractEventLoop | None = None) -> "ConfigHandle[T]": ...

    @property
    def current(self) -> T: ...          # lock-free read of the live snapshot

    def reload(self) -> T: ...           # re-run pipeline, atomically swap
    async def reload_async(self) -> T: ...

    def on_reload(self, fn: Callable[[T], Any]) -> Callable[[], None]: ...  # returns a disconnect
```

The process-level singleton, if an application wants one, is built by the application on
top of either `load()` or a `ConfigHandle` — `confiq` never owns it.

---

## 7. Concurrency and async model

**Reads are lock-free.** `ConfigHandle.current` is a single attribute read of an immutable
snapshot; under CPython that read is atomic, and because the snapshot cannot be mutated
there is no torn-read hazard. Thread safety is therefore a property of the immutable-value
design, not of a locking discipline.

**Reload is copy-on-write.** `reload()` computes a fresh snapshot off to the side, takes a
short write lock only to swap the reference, and is guarded against re-entrancy
(`ReentrancyGuard` fast-fails if a reload triggers a reload). The cost and complexity of
concurrency live entirely here, in the opt-in reload path — not in the common case.

**Notifications use blinker.** `on_reload` is modeled on a blinker signal, giving
weak-referenced subscribers (handlers do not have their lifetime accidentally extended)
and documented connect/disconnect semantics, rather than a bespoke subscriber list.

**Subscribers may be sync or async, by design.** `reload_async()` drives async subscribers
on the running loop (gathered and awaited); sync subscribers run inline after the swap.
`reload()` runs sync subscribers on a daemon thread outside the lock. An async subscriber
attached to a handle that is only ever driven by sync `reload()` requires an explicitly
provided loop reference at `create()` time, and is scheduled with `call_soon_threadsafe`.

**Async is a clean second entry point, not a colored twin of everything.** `load_async()`
drives `AsyncSource`s natively. Sync `load()` accepts only sync sources and raises a clear
error if handed an `AsyncSource`, rather than smuggling an event loop into a worker thread.
The `Source`/`AsyncSource` split keeps the protocol honest about which world a source
lives in.

---

## 8. Type safety and the return-type gradient

`load(schema: type[T], ...) -> T` returns an instance of the type you declared — not a
library wrapper and not a forced pydantic value. `isinstance(config, YourType)` holds, the
type checker sees your exact type, and the return annotation is honest. Accepting an
existing dataclass or `TypedDict` requires no rewrite into pydantic; that is handled by
the validation engine and is independent of the return type.

Choosing to return the declared type means `confiq`'s *guarantees* form an explicit
gradient rather than a constant. This is intentional and is documented so that no one
assumes a guarantee they did not opt into:

| Schema type | Access | Mutability | Secret-masked `repr` | Rich serialization |
|---|---|---|---|---|
| `BaseModel(frozen=True)` | attribute | immutable | full | full (`model_dump`) |
| `BaseModel` (default) | attribute | mutable | full | full |
| `@dataclass(frozen=True)` | attribute | immutable | invasive¹ | via `TypeAdapter` |
| `@dataclass` | attribute | mutable | invasive¹ | via `TypeAdapter` |
| `TypedDict` | subscript | mutable dict | none² | already a dict |
| schemaless | subscript | read-only `Mapping` | none | none |

¹ Masking a secret on a stdlib dataclass requires `confiq` to generate a custom `__repr__`.
² A `TypedDict` resolves to a plain dict with nowhere to hang a masked repr; wrapping it
would break type-honesty.

Two consequences are stated loudly rather than buried. **The immutability pillar holds only
when the schema is frozen** — frozen pydantic is the safe default, and a non-frozen
dataclass yielding mutable config is a legitimate informed choice. **The richer
`ConfigField` features, secret masking in particular, are pydantic-strong and degrade on
other schema types.** The honest pitch is: bring any structure; frozen pydantic is where
every guarantee is on, and each step away trades one specific guarantee for one specific
convenience, visibly.

The typed-open middle ground — a fully typed core plus a permissive `extra` section — is
available via `ConfigDict(extra="allow")` on pydantic schemas (extras land in
`__pydantic_extra__`) and via an explicit `extra: dict[str, Any]` field on dataclasses and
`TypedDict`s.

---

## 9. CLI integration

The CLI is treated as just another source feeding the load pipeline, and `confiq` is a
**consumer** of whichever CLI framework the application already uses — it never owns or
generates the command by default. This is what keeps integration seamless and keeps the
framework's full option surface (help, prompts, callbacks, custom types) out of `confiq`'s
maintenance burden.

**Consumer path (default).** The application writes its Typer, Click, or argparse command
as normal. `confiq` reads only the parameters the user *explicitly set* and folds them in
as the highest-precedence source. Distinguishing "the user typed this" from "this is the
framework default" is done through the framework's own facilities. Parameters map to config
paths by a single name convention (dotted path plus delimiter); an explicit `ConfigBind`
(or, for argparse, a `bind={...}` dict) is needed only when the CLI name and the config
path diverge. Crucially, defaults are declared **only** in the schema — consumer-path
options omit their defaults — so a value is never declared in two places.

**Generator path (opt-in).** For applications that want one declaration site — add a field,
get a flag — `confiq` can emit options from the schema. Because `confiq` controls the
generated options, it sets their defaults to the unset sentinel automatically, so the
"no duplicated default" property comes for free on this path.

**Shared convention invariant.** Both paths obey the same name↔path mapping. The consumer
path runs the convention backward (parameter → path); the generator runs it forward
(path → parameter). They must never disagree.

**Framework support is real but asymmetric.** Each supported framework is hard on exactly
one side of the consume/generate split, and the architecture acknowledges this rather than
papering over it:

| | Consume (read what the user set) | Generate (emit options from schema) |
|---|---|---|
| Click | easy — `Context` + `get_parameter_source()` | easy — imperative (`params=[...]`) |
| Typer | easy — Click underneath | awkward — signature-driven; params can't be injected |
| argparse | awkward — see below | easy — imperative (`add_argument`) |

Typer infers parameters from the function signature at decoration time, so the generator
lives most naturally at the Click layer; Typer generation needs either a drop-to-Click path
or a Typer-aware command factory. argparse has no parameter-source API, so the consumer
adapter detects explicit-set via sentinel defaults (`default=argparse.SUPPRESS` makes
unspecified arguments absent from the namespace, which is unambiguous); comparing against
`parser.get_default()` is the degraded fallback. argparse cannot carry an `Annotated`
binding, so its binding is convention-by-`dest` plus an explicit `bind` dict — the same
convention-default-plus-override shape as the other frameworks, expressed as data.

---

## 10. Testing architecture

The testing story is a first-class goal, not a consequence, and it is the differentiator
that no comparable Python library offers. Because configuration is a plain value with no
global identity, a test constructs the value it wants instead of mutating and restoring
shared state. The intended primitives, modeled on Figment's `Jail`, are delivered as a
`pytest-confiq` plugin:

- a `config` fixture that builds from an in-memory base source, overridable per test and
  per parametrization;
- an autouse isolation fixture so no environment or file source leaks into a test unless
  it is added explicitly — the thing `monkeypatch` otherwise forces you to do by hand;
- layering helpers so a test can say "the production sources, but with this one value
  overridden" without rebuilding the whole stack;
- async support via the same `context.override()` (a `ContextVar`) the library uses
  elsewhere, giving per-task config isolation in async tests for free.

Two implications fall back onto the core rather than the plugin: the in-memory source and
the override mechanism must be ergonomic enough that the plugin is a thin layer, and the
resolver must support cheaply splicing or overriding a single key in an existing source
list, because that is the operation every config test actually performs.

---

## 11. Extension and packaging

Backends extend the system through three coordinated mechanisms:

- **Built-in cloud sources behind optional extras** (`confiq[aws]`, and so on). These ship
  in-tree so they share one `Source` protocol contract and release in lockstep with it.
- **An entry-point group** (`confiq.sources`) so third parties can publish sources that are
  discovered without a pull request to `confiq`.
- **pluggy hookimpls** for stateless transforms and adapter resolution (including
  `confiq_get_schema_adapter`).

The governing rule is dependency discipline borrowed from Koanf: **the core depends on
nothing optional.** CLI frameworks, dotenv parsing, and cloud SDKs all live behind extras;
a user who only reads environment variables installs none of them. (This is also the fix
for the earlier inconsistency in which Typer and `python-dotenv` were treated as mandatory
core dependencies.)

---

## 12. Decision summary

Every architectural axis is settled. The table is the index; sections above carry the
reasoning.

| Axis | Decision |
|---|---|
| 1 — Config identity | Immutable value by default; `ConfigHandle` opt-in for reload; user-owned singleton |
| 2 — Schema types & coupling | No base class; accept `BaseModel`, pydantic/stdlib dataclass, `TypedDict`, schemaless; `load` returns the declared type |
| 3/10 — CLI binding & generation | Consumer of the user's command by default; opt-in generator; one shared name↔path convention |
| 4 — Metadata reading | Per-adapter: pydantic via `FieldInfo.metadata`; dataclass/`TypedDict` via `get_type_hints` |
| 5 — Precedence | Explicit ordered source list, last-higher |
| 6 — Merge | Deep-merge, list-replace, with provenance; per-source `override`/`fill` mode |
| 7 — Concurrency | Immutable value + copy-on-write atomic swap + blinker signals + reentrancy guard |
| 8 — Async | Sync core + async adapters; `load_async`; sync `load` rejects async sources |
| 9 — Type safety | Typed by default; typed-open `extra`; schemaless escape; guarantees as a documented gradient |
| 11 — Extension | Built-in extras + `confiq.sources` entry points + pluggy; core depends on nothing optional |
| Validation engine | pydantic `TypeAdapter` for all schema types |
| Profiles | Thin, opt-in, user-composed, nothing auto-discovered |

---

## 13. Non-goals

These are deliberate refusals, recorded so they do not quietly creep back in:

- **No value interpolation or expression DSL.** Computed values are the job of a source,
  not of the config value, which stays a plain immutable structure.
- **No magic environment discovery.** Nothing auto-selects files or profiles by inspecting
  the environment; precedence and profile selection are always explicit.
- **No library-owned global singleton.** Ambient access, if wanted, is built by the
  application.
- **`confiq` does not own the CLI command.** It consumes the user's command by default; the
  generator is additive and never a requirement.
- **No mandatory optional dependencies.** The core installs no CLI framework, dotenv parser,
  or cloud SDK.

---

## 14. Open implementation questions

These are matters of "how," not "what" — they do not reopen any axis, but they are the
detailed contracts to pin down when turning this design into an API:

- **Typer generation ergonomics** — drop to the Click layer, or provide a Typer-aware
  command factory, given Typer's signature-driven model.
- **The exact `SchemaAdapter` contract** — the precise shape of `field_metadata` and
  `validate`, and how the typed-open `extra` mechanism is surfaced uniformly across the
  four schema kinds.
- **Secret masking on non-pydantic schemas** — whether `confiq` generates a custom
  `__repr__` for frozen dataclasses carrying `secret=True` fields, or documents masking as
  a pydantic-only guarantee.
- **The `pytest-confiq` fixture surface** — the concrete fixture names and composition
  helpers realizing the testing architecture in §10.
