# `design_c` → Architecture Delta

`docs/confiq_architecture.md` and `docs/config_design_axes.md` are the authoritative
design. `docs/design_c.md` is the superseded spec. This document records every place they
diverge so that `design_c` — and any code derived from it — can be brought into line.

**Direction is not neutral.** Each entry states what must change in `design_c`/the code,
not what might be reconsidered.

**Illustrative vs decided.** The architecture doc's code sketches encode agreed contracts
but are not prescriptive signatures. Raw signature-level differences therefore need
classification before acting on them. This doc splits them accordingly:

- **Group A** — Substantive design changes. Authoritative; reconcile `design_c` and the
  code to match.
- **Group B** — Incidental sketch differences. Confirm the intended form before changing
  anything.

---

## Group A — Reconcile (authoritative)

### A1. Sync `load()` rejects async sources

**`design_c` says** (§5.5):

> `load()` is synchronous. For async sources, it gathers their results by running
> `asyncio.gather()` inside a `ThreadPoolExecutor` worker via `asyncio.run()` — this
> avoids conflict with any running event loop in the caller's thread.

The signature accepts both:

```python
def load(
    schema: type[T] | None = None,
    *,
    sources: list[Source | AsyncSource],
    ...
) -> T | SchemalessConfig: ...
```

**New docs say** (architecture §7; Axis 8):

> Async is a clean second entry point, not a colored twin of everything. `load_async()`
> drives `AsyncSource`s natively; sync `load()` accepts only sync sources and raises a
> clear error if handed an `AsyncSource`.

Axis 8 lists the `ThreadPoolExecutor + asyncio.run()` bridge under **Rejected**.

**Action.** Change `load()`'s `sources` parameter type to `list[Source]`. Add a guard
that raises a clear `TypeError` (or `ConfiqError` subclass) if an `AsyncSource` is
passed. `load_async()` retains `list[Source | AsyncSource]`.

---

### A2. `python-dotenv` and `typer` are not mandatory core deps

**`design_c` says** (§10):

> `pydantic`, `pluggy`, `fsspec`, `python-dotenv`, and `typer` are the mandatory runtime
> dependencies. … `python-dotenv` and `typer` are mandatory because they are used in
> confiq's core CLI and `.env` support.

**New docs say** (architecture §11; Axis 11):

> The governing rule is dependency discipline borrowed from Koanf: **the core depends on
> nothing optional.** CLI frameworks, dotenv parsing, and cloud SDKs all sit behind
> extras; a user who only reads environment variables installs none of them. (This is also
> the fix for the earlier inconsistency in which Typer and `python-dotenv` were treated as
> mandatory core dependencies.)

**Action.** Remove `python-dotenv` and `typer` from `[project.dependencies]` in
`pyproject.toml`. Move each behind an appropriate optional extra (e.g., `[dotenv]`,
`[cli]`). Any built-in code that imports them at module level must be moved behind a
lazy-import or optional guard.

---

### A3. `on_reload` — sync-only → sync+async via blinker signals

**`design_c` says** (§12, Decision 3):

> `on_reload` accepts only sync callables in v1. Async users bridge via
> `loop.call_soon_threadsafe(asyncio.ensure_future, coro, loop=loop)` inside their sync
> subscriber.

The subscriber signature (§5.6, verbatim):

```python
def on_reload(
    self, fn: Callable[[T, T], None]
) -> Callable[[T, T], None]: ...
```

`fn` receives `(old: T, new: T)`; `on_reload` returns `fn` unchanged for decorator use.

**New docs say** (architecture §7; Axis 7):

> **Notifications use blinker.** `on_reload` is modeled on a blinker signal, giving
> weak-referenced subscribers and documented connect/disconnect semantics.
>
> **Subscribers may be sync or async, by design.** `reload_async()` drives async
> subscribers on the running loop (gathered and awaited); sync subscribers run inline
> after the swap. `reload()` runs sync subscribers on a daemon thread outside the lock.
> An async subscriber attached to a handle driven by sync `reload()` requires an
> explicitly provided loop reference at `create()` time and is scheduled with
> `call_soon_threadsafe`.

The architecture §6 sketch shows the new signature:

```python
def on_reload(self, fn: Callable[[T], Any]) -> Callable[[], None]: ...  # returns a disconnect
```

**Decided parts (reconcile now):**
- Subscribers may be **sync or async** — `design_c`'s sync-only decision is reversed.
- Notification uses **blinker signals** with weak references — not a plain callback list
  on a daemon thread.

**Sketch-level parts (see B4 below):** The arity shift `(old, new)` → `(new)` and the
return type shift `fn` → disconnect callable follow from the blinker choice but were not
separately deliberated. Confirm before recording as intentional.

**Action (decided part).** Replace the bespoke subscriber list with a blinker signal.
Implement async-subscriber support in `reload_async()`. Wire the `loop` parameter from
`create()` (A13) for scheduling async subscribers under sync `reload()`. Resolve B4
before finalizing the arity and return type.

---

### A4. `SchemaAdapter` — return semantics, not just names

**`design_c` says** (§9, verbatim):

```python
class SchemaAdapter(Protocol):
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

`field_hints` returns `Mapping[str, object]` — name → full annotated *type*.
`validate` returns `object`.

**New docs say** (architecture §5.3, verbatim sketch):

```python
class SchemaAdapter(Protocol):
    def field_metadata(self) -> Mapping[str, list[Any]]: ...  # Annotated extras (incl. ConfigField)
    def validate(self, data: Mapping[str, Any]) -> T: ...      # returns an instance of the declared type
```

**Decided semantic shifts:**
- The metadata accessor returns **`Annotated` extras only** (`list[Any]`) — not the full
  type including the bare annotation. Callers that need the type have the schema class
  directly.
- `validate(...)` is typed to return `T` (the declared schema type), not `object`.

The method name `field_hints` → `field_metadata` is sketch-level and may be confirmed
either way; the semantic content of the return value is the authoritative change.

**Action.** Update `SchemaAdapter.field_hints` to return extras only (`Mapping[str,
list[Any]]`). Update `validate` return annotation to `T`. Update all call sites that
assumed the full annotated type was in the return value.

---

### A5. Metadata reading — per-adapter, not universal `get_type_hints`

**`design_c` says** (§2.6 and §6, step 3):

> confiq reads field metadata at load time via
> `typing.get_type_hints(schema, include_extras=True)` — this works on any class.

And in the resolver algorithm:

> Walk the schema's fields via `typing.get_type_hints(schema, include_extras=True)`.

**New docs say** (architecture §5.3; Axis 4):

> **Metadata is read the right way per type.** For pydantic schemas, `ConfigField` is
> read from pydantic's own `FieldInfo.metadata` — the same view the validator uses, with
> no second introspection path and none of the PEP 563 / forward-reference fragility that
> comes from calling `get_type_hints` independently. For stdlib dataclasses and
> `TypedDict`s, which have no `FieldInfo`, the adapter reads `Annotated` metadata via
> `get_type_hints(include_extras=True)` — unavoidable for those types, and acceptable
> because it is confined to them.

**Action.** Split the pydantic adapter to read from `FieldInfo.metadata` instead of
`get_type_hints`. Keep `get_type_hints` only in the dataclass and `TypedDict` adapters.

---

### A6. Multi-schema support and `TypeAdapter` validation

**`design_c` says** (§6, step 4):

> Validate through `schema.model_validate(merged)`.

The implied scope is pydantic `BaseModel` only; the resolver calls the model's own
`model_validate` method.

**New docs say** (architecture §5.3; Axis 2; cross-cutting validation engine):

> First-class support for `BaseModel`, pydantic dataclass, stdlib dataclass, `TypedDict`,
> and schemaless, all validated and coerced through pydantic's `TypeAdapter`, which
> natively handles models, pydantic and stdlib dataclasses, and `TypedDict`s. One engine,
> one set of validation semantics.

**Action.** Replace `schema.model_validate(merged)` with `TypeAdapter(schema).validate_python(merged)`.
Add adapters for pydantic dataclass, stdlib dataclass, `TypedDict`, and schemaless. The
`SchemaAdapter` pluggy hook (A4) is the extension point for additional schema types.

---

### A7. `load()` return type — declared type, not forced pydantic, with an immutability gradient

**`design_c` says** (§1):

> `load()` returns a frozen pydantic `BaseModel`. Once it returns, attribute access cannot
> raise a config error.

The thread-safety narrative (§7) rests on unconditional immutability: the frozen model
is the basis of lock-free reads.

**New docs say** (architecture §8; Axis 2; Axis 9):

> `load(schema: type[T], ...) -> T` returns an instance of the type you declared — not a
> library wrapper and not a forced pydantic value.

And they document the gradient explicitly:

| Schema type | Mutability | Secret-masked `repr` |
|---|---|---|
| `BaseModel(frozen=True)` | immutable | full |
| `BaseModel` (default) | mutable | full |
| `@dataclass(frozen=True)` | immutable | invasive |
| `@dataclass` | mutable | invasive |
| `TypedDict` | mutable dict | none |
| schemaless | read-only `Mapping` | none |

> **The immutability pillar holds only when the schema is frozen** — frozen pydantic is
> the safe default, and a non-frozen dataclass yielding mutable config is a legitimate
> informed choice.

**Action.** The thread-safety guarantee in `design_c` §7 must be qualified: lock-free
reads are safe only when the schema is frozen. Update documentation of `ConfigHandle` and
`load()` to reflect the gradient. The table above should appear in the public docs.

---

### A8. Typed-open middle ground (`extra` section)

**`design_c` says:** schemaless mode (`SchemalessConfig`) is the only relaxation of the
fully-typed default. There is no middle-ground mode.

**New docs say** (architecture §8; Axis 9):

> The typed-open middle ground — a fully typed core plus a permissive `extra` section —
> is available via `ConfigDict(extra="allow")` on pydantic schemas (extras land in
> `__pydantic_extra__`) and via an explicit `extra: dict[str, Any]` field on dataclasses
> and `TypedDict`s.

**Action.** Document the typed-open pattern in public docs and examples. No resolver
changes required — `TypeAdapter` already handles `extra="allow"` — but the pattern needs
to be explicitly documented as a supported choice, not an undocumented side effect.

---

### A9. `Source` protocol gains `mode` and `profile`

**`design_c` says** (§5.1, verbatim):

```python
@runtime_checkable
class Source(Protocol):
    name: str

    def fetch(self) -> Mapping[str, Any]: ...
```

Two attributes only: `name` and `fetch()`.

**New docs say** (architecture §5.1, verbatim sketch):

```python
class Source(Protocol):
    name: str
    mode: Literal["override", "fill"] = "override"
    profile: str | None = None
    def fetch(self) -> Mapping[str, Any]: ...
```

**Action.** Add `mode` and `profile` to the `Source` protocol and all built-in source
implementations. `mode` defaults to `"override"` (preserving current behavior).
`profile` defaults to `None` (source participates in all loads by default).

---

### A10. Merge semantics gain fill mode

**`design_c` says** (§6):

> Deep-merge the pairs left-to-right, tracking provenance. Later entries winning on
> collision. Lists are replaced, not concatenated.

Override-only: every source clobbers prior values for keys it supplies.

**New docs say** (architecture §5.4; Axis 6):

> Each source declares `mode="override"` (default) or `mode="fill"` (contribute only
> keys not already supplied by a higher-precedence source).

**Action.** Update the merge algorithm to honor `source.mode`. For `mode="fill"`,
contribute a key only if it is not already present in the merged mapping at that point.
Provenance for fill-mode keys is recorded the same way as override-mode keys.

---

### A11. Provenance surfaced in errors as a named design goal

**`design_c` says** (§6, step 2):

> tracking provenance … `provenance: dict[str, str]` — maps each dotted key path to the
> name of the last source that set it.

And (§8):

> `ConfigValidationError` carries … `source_names: list[str]` (names of the sources that
> contributed to the field's value).

Provenance is tracked and partially surfaced, but it is framed as an implementation
detail of the resolver.

**New docs say** (architecture §5.4):

> Provenance is not internal bookkeeping only: it is surfaced in error messages, so a
> validation failure can say exactly where the offending value came from — the single
> cheapest high-value feature borrowed from Figment.

**Action.** Minor framing change only. Ensure that provenance is surfaced in
`MissingConfigError` and `ConfigValidationError` error messages — not just carried in
structured fields — so the human-readable error text names the source. Verify that
fill-mode sources appear correctly in provenance (A10 dependency).

---

### A12. Profiles — absent in `design_c`, first-class in new docs

**`design_c` says:** no profiles, no `profile` parameter on `load()`, no source tagging.
Section 2.4 states sources are selected solely by their position in the list.

**New docs say** (architecture §5.5; `config_design_axes.md` cross-cutting profiles):

> A source may tag itself with a profile name; selecting a profile at load time filters
> which tagged sources participate. Nothing is auto-discovered — the user still composes
> the list and names the profile explicitly — so this preserves the "no magic" principle.

`load()` in the architecture §6 sketch:

```python
def load(schema: type[T], sources: Sequence[Source], *, profile: str | None = None) -> T: ...
```

**Action.** Add `profile: str | None = None` to `load()` and `load_async()`. Update the
fetch step: when `profile` is not `None`, skip any source where `source.profile is not
None and source.profile != profile`. Sources with `profile=None` always participate.

---

### A13. `ConfigHandle.create()` — `loop` parameter added

**`design_c` says** (§5.6, verbatim):

```python
@classmethod
def create(
    cls,
    schema: type[T],
    *,
    sources: list[Source | AsyncSource],
    plugins: list[object] | None = None,
) -> ConfigHandle[T]: ...
```

No loop parameter.

**New docs say** (architecture §6 sketch):

```python
@classmethod
def create(cls, schema: type[T], sources: Sequence[Source],
           *, loop: AbstractEventLoop | None = None) -> "ConfigHandle[T]": ...
```

**Decided part:** `loop: AbstractEventLoop | None = None` is explicitly motivated by the
async-subscriber story (A3): an async subscriber attached to a handle driven by sync
`reload()` requires `call_soon_threadsafe`, which needs a loop reference.

**Sketch-level parts of `create()`:** `sources` positional vs keyword-only, and the
missing `plugins` parameter — see B2 and B3.

**Action (decided).** Add `loop` parameter to `ConfigHandle.create()`. Store as
`self._loop`. Use in `reload()` when scheduling async subscribers via
`call_soon_threadsafe`.

---

## Group B — Confirm before acting

These are real textual differences in the architecture doc relative to `design_c`, but
they likely reflect illustrative sketch choices rather than deliberate decisions. Do not
record them as intentional changes or update any code until the intended form is
confirmed.

### B1. `ConfigHandle.current` — property vs method

**`design_c`** (§5.6, verbatim): `def current(self) -> T: ...`

Used as a method call in §4.8: `cfg: Settings = handle.current()`

**Architecture doc** (§6): `@property def current(self) -> T: ...` (accessed as
`handle.current`)

**Question.** Should `current` be a property? A property reads more naturally for an
immutable snapshot and avoids the awkward `handle.current()` call syntax. If yes, this
is a real API change that affects all call sites.

---

### B2. `create()` — `sources` positional vs keyword-only

**`design_c`** (§5.6): `create(cls, schema: type[T], *, sources: list[...], ...)` —
`sources` is keyword-only.

**Architecture doc** (§6): `create(cls, schema: type[T], sources: Sequence[Source], ...)`
— `sources` is positional.

**Question.** Keyword-only is more defensive and matches `load()`'s existing convention.
Positional reads slightly lighter at the call site. Which form is the standard?

---

### B3. `create()` — `plugins` parameter absent from architecture sketch (likely omission)

**`design_c`** (§5.6, verbatim):

```python
@classmethod
def create(
    cls,
    schema: type[T],
    *,
    sources: list[Source | AsyncSource],
    plugins: list[object] | None = None,
) -> ConfigHandle[T]: ...
```

Per-handle plugin injection via `plugins` was an explicit design decision (`design_c`
§12, Decision 10): `ConfigHandle` owns a persistent `PluginManager` and user-registered
plugins survive across reload cycles.

**Architecture doc** (§6 sketch): no `plugins` parameter.

**Assessment.** Per-handle plugin registration was never discussed for removal. The
architecture doc §11 describes the extension mechanism (entry points + hookimpls) but
does not address `create()`'s `plugins` parameter. This is most likely a sketch omission,
not a decision.

**Question.** Keep `plugins` on `ConfigHandle.create()` (consistent with Decision 10 and
`load()`'s `plugins` parameter), or remove it and require all per-handle plugin
registration to go through entry points? If kept, the architecture doc §11 should
explicitly acknowledge per-handle injection as a supported extension path.

---

## Summary table

| # | Area | `design_c` | New docs (authoritative) | Kind |
|---|------|-----------|--------------------------|------|
| A1 | Async in sync `load()` | Drives `AsyncSource` via `asyncio.run()` in `ThreadPoolExecutor` | Raises error; `load_async()` for async sources | Decision |
| A2 | Mandatory deps | `python-dotenv`, `typer` mandatory core | All optional behind extras; core depends on nothing optional | Decision |
| A3 | `on_reload` subscriber sync/async | Sync only | Sync and async; blinker signals; weak refs | Decision |
| A3 | `on_reload` notification mechanism | Bespoke callback list on daemon thread | blinker signal | Decision |
| A4 | `SchemaAdapter` metadata return | `Mapping[str, object]` (name → annotated type) | `Mapping[str, list[Any]]` (extras only) | Decision |
| A4 | `SchemaAdapter.validate` return | `object` | `T` (declared type) | Decision |
| A5 | Metadata reading | `get_type_hints` for all schema types | Per-adapter; pydantic uses `FieldInfo.metadata` | Decision |
| A6 | Validation call | `schema.model_validate(merged)` | `TypeAdapter(schema).validate_python(merged)` | Decision |
| A6 | Supported schema types | pydantic `BaseModel` only | `BaseModel`, pydantic/stdlib dataclass, `TypedDict`, schemaless | Decision |
| A7 | `load()` return type | Frozen pydantic `BaseModel` | Instance of declared type `T`; immutability is a gradient | Decision |
| A8 | Typed-open middle ground | Not present | `ConfigDict(extra="allow")` or explicit `extra` field | Decision |
| A9 | `Source` protocol | `name` + `fetch()` | `name` + `mode` + `profile` + `fetch()` | Decision |
| A10 | Merge behavior | Override-only (deep-merge, list-replace) | Override + fill; fill never clobbers existing keys | Decision |
| A11 | Provenance in errors | Carried in structured error fields | Surfaced in human-readable error messages as a named goal | Reframing |
| A12 | Profiles | Absent | `profile` on `Source`; `profile=` on `load()`; filtered participation | Decision |
| A13 | `ConfigHandle.create()` `loop` param | Absent | `loop: AbstractEventLoop \| None = None` | Decision |
| B1 | `current` — property vs method | `def current(self) -> T` (method) | `@property current` | **Confirm** |
| B2 | `create()` `sources` arg style | Keyword-only (`*`) | Positional in sketch | **Confirm** |
| B3 | `create()` `plugins` param | Present; per-handle PM | Absent from sketch | **Confirm (likely omission)** |

---

## Filename note

The axes document is `docs/config_design_axes.md` — not `confiq_design_axes.md` as some
prior references stated. All cross-references should use the correct path.
