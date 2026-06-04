# `confiq` — Design Axes

Companion reference to `confiq_architecture.md`. Where the architecture document is the
narrative, this is the index of the independent design decisions the library is made of.
Every axis is settled; each entry states what the axis is, the position `confiq` takes,
the alternatives it rejects, and what the choice costs.

Each entry reads:

- **Definition** — the degree of freedom the axis names.
- **Position** — `confiq`'s concrete, final choice, in terms of real types and behavior.
- **Rejected** — the realistic alternatives not taken.
- **Cost** — what the chosen position gives up.

Numbering matches the architecture document's decision summary (§12). Axes 3 and 10 are
one decision and are stated together.

---

### Axis 1 — Config identity

**Definition.** What `load()` returns and who owns it: a value, an object with identity, or
a reloadable handle.

**Position.** `load(schema, sources) -> T` returns an immutable value — an instance of the
declared schema, with no library identity. `ConfigHandle[T]` is the explicit opt-in for
runtime reload. There is no `confiq`-owned global; an application that wants ambient access
constructs its own singleton over `load()` or a handle.

**Rejected.** A library-owned process singleton (`from confiq import config`); a
registry/object-with-identity model.

**Cost.** Callers pass the value through explicitly; there is no import-and-use ambient
config out of the box.

---

### Axis 2 — Schema types, coupling & return type

**Definition.** What may serve as a schema, whether `confiq` owns the class, and what type
`load()` hands back.

**Position.** No base class is required. Accepted schemas: pydantic `BaseModel`, pydantic
dataclass, stdlib dataclass, `TypedDict`, and schemaless. `load()` returns an instance of
the *declared* type — `isinstance(config, YourType)` holds and the `-> T` annotation is
honest. Existing structures are accepted without rewriting them into pydantic.

**Rejected.** Requiring a `confiq.Settings` base class; always coercing to a uniform frozen
pydantic value; wrapping the result in a generic `Config[T]` view (both of the latter put a
library object back on the read path).

**Cost.** Guarantees become a gradient rather than a constant — see Axis 9.

---

### Axes 3 + 10 — CLI binding & generation

**Definition.** Whether `confiq` owns, generates, or consumes the CLI command, and how CLI
parameters map onto config paths.

**Position.** `confiq` is a **consumer** by default: it reads only the parameters the user
explicitly set on their existing Typer/Click/argparse command and folds them in as the
highest-precedence source, with defaults declared only in the schema. An **opt-in
generator** can emit options from the schema for a single declaration site. Both obey one
name↔path convention (dotted path plus delimiter); an explicit `ConfigBind` annotation — or,
for argparse, a `bind={...}` dict — is needed only when the CLI name and the config path
diverge.

**Rejected.** `confiq` generating and owning the command (schema-is-CLI); declaring CLI
metadata on schema fields via `ConfigField.cli`.

**Cost.** The consumer path restates a field's *type* (not its default) in the command
signature; generator ergonomics are clean for Click and argparse but awkward for Typer,
which is signature-driven and cannot accept injected parameters.

---

### Axis 4 — Metadata reading

**Definition.** How per-field metadata (`ConfigField` and other `Annotated` extras) is read
from a schema.

**Position.** Per adapter. pydantic schemas read metadata from pydantic's own
`FieldInfo.metadata` — the same view the validator uses, with no second introspection path.
dataclass and `TypedDict` adapters read `Annotated` metadata via
`get_type_hints(include_extras=True)`, which those types require.

**Rejected.** A single `get_type_hints` path for all schema types; a separate custom
metadata registry.

**Cost.** The `get_type_hints` path keeps its PEP 563 / forward-reference fragility, but
confined to the dataclass and `TypedDict` adapters.

---

### Axis 5 — Precedence

**Definition.** How sources are ranked against one another.

**Position.** The explicit ordered source list, last-higher. The list is the complete
precedence specification.

**Rejected.** Fixed per-source priority integers; convention- or environment-driven
discovery of which sources apply.

**Cost.** The caller writes the order out explicitly each time, mitigated by composition
helpers.

---

### Axis 6 — Merge & provenance

**Definition.** How overlapping data from multiple sources combines, and whether the origin
of each value is tracked.

**Position.** Deep-merge with list-replacement. Each source declares `mode="override"`
(default) or `mode="fill"` (contribute only keys not already supplied by a
higher-precedence source). A parallel provenance map records the winning source for each
leaf and is surfaced in error messages.

**Rejected.** Shallow merge; list-concatenation across layers; discarding provenance.

**Cost.** List-replacement means lists cannot be accumulated across sources — a deliberate,
legible default rather than an accident.

---

### Axis 7 — Concurrency & mutation

**Definition.** How concurrent reads and runtime updates are made safe.

**Position.** Immutability is the basis of safety: reads are a single atomic attribute read
of an immutable snapshot, with no lock. `ConfigHandle.reload()` computes a fresh snapshot
off to the side and atomically swaps the reference under a short write lock, with a
re-entrancy guard. `on_reload` notifications are blinker signals (weak-referenced
subscribers). Subscribers may be sync or async; `reload_async()` drives async subscribers on
the running loop, and an async subscriber under sync `reload()` is scheduled via an
explicitly provided loop.

**Rejected.** A mutable store protected by locks; copy-on-write without an immutable result.

**Cost.** The immutability guarantee holds only for frozen schemas (Axis 9); all concurrency
complexity is concentrated in the opt-in reload path.

---

### Axis 8 — Async

**Definition.** How asynchronous sources are supported without forcing the whole call chain
to be async.

**Position.** Sync core plus async adapters. `load_async()` drives `AsyncSource`
implementations natively; sync `load()` accepts only sync sources and raises a clear error
if handed an `AsyncSource`. `Source` and `AsyncSource` are separate protocols rather than a
colored pair on every method.

**Rejected.** Sync-only; async-only; a sync/async twin of every method; driving async
sources from sync `load()` via a `ThreadPoolExecutor` + `asyncio.run()` bridge.

**Cost.** An async source requires the async entry point; there is no implicit bridging from
the sync path.

---

### Axis 9 — Type safety & typed-open

**Definition.** How strict the read path is, and what relaxations are available.

**Position.** Fully typed by default, with no `Any` on reads. A typed-open middle ground
allows extra keys via `ConfigDict(extra="allow")` on pydantic schemas (extras in
`__pydantic_extra__`) or an explicit `extra: dict[str, Any]` field on dataclasses and
`TypedDict`s. Schemaless mode returns a read-only `Mapping`. Guarantees form an explicit,
documented gradient across schema types: immutability and secret-masked `repr` are full on
frozen pydantic and degrade step-by-step toward `TypedDict` and schemaless, with each step
trading one named guarantee for one named convenience.

**Rejected.** A dict-with-`Any` model with no typing; strict-only with no escape hatch.

**Cost.** Dynamic or unknown-key configuration must use the typed-open or schemaless path,
and not every guarantee is on for every schema type.

---

### Axis 11 — Extension & packaging

**Definition.** How backends and transforms extend the system, and what the core depends on.

**Position.** Built-in cloud sources ship behind optional extras (`confiq[aws]`, …); a
`confiq.sources` entry-point group lets third parties publish sources without a pull
request; pluggy hookimpls cover stateless transforms and schema-adapter resolution. The core
depends on nothing optional — CLI frameworks, dotenv parsing, and cloud SDKs all sit behind
extras.

**Rejected.** Shipping every backend as a separate package; a batteries-in-core model that
pulls heavy dependencies into every install.

**Cost.** In-tree backends release in coordination with the `Source` protocol contract.

---

### Cross-cutting — Validation engine

**Definition.** What validates and coerces merged data into the typed result.

**Position.** pydantic's `TypeAdapter`, for every accepted schema type — models, pydantic and
stdlib dataclasses, and `TypedDict`s. One engine, one set of validation semantics.

**Rejected.** Per-type bespoke validators; trusting the merged dict without validation.

**Cost.** pydantic is a genuine, mandatory core dependency — accepted deliberately.

---

### Cross-cutting — Profiles

**Definition.** How environment or variant selection is expressed, if at all.

**Position.** Thin, opt-in, and explicit. A source may carry a `profile` tag; selecting a
profile at load time filters which tagged sources participate. Nothing is auto-discovered —
the user still composes the source list and names the profile.

**Rejected.** Magic auto-selected environments (inspecting the runtime to choose files or
profiles); no profile concept whatsoever.

**Cost.** Minimal; the same outcome is also expressible by composing different source lists,
so profiles are sugar over the explicit list rather than a new precedence mechanism.

---

## At a glance

| # | Axis | Position |
|---|---|---|
| 1 | Config identity | Immutable value default; `ConfigHandle` opt-in; user-owned singleton |
| 2 | Schema types & return | Any of model / dataclass / `TypedDict` / schemaless; returns the declared type |
| 3+10 | CLI | Consumer by default; opt-in generator; one name↔path convention |
| 4 | Metadata reading | pydantic via `FieldInfo.metadata`; others via `get_type_hints` |
| 5 | Precedence | Explicit ordered list, last-higher |
| 6 | Merge & provenance | Deep-merge, list-replace, per-source `override`/`fill`, provenance in errors |
| 7 | Concurrency | Immutable reads; COW atomic-swap reload; blinker signals; sync+async subscribers |
| 8 | Async | Sync core + async adapters; `load_async`; sync `load` rejects async sources |
| 9 | Type safety | Typed by default; typed-open `extra`; schemaless escape; guarantee gradient |
| 11 | Extension & packaging | Extras + `confiq.sources` entry points + pluggy; core depends on nothing optional |
| — | Validation engine | pydantic `TypeAdapter` for all schema types |
| — | Profiles | Thin, opt-in, explicit; nothing auto-discovered |
