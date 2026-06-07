# `confiq` — Rust-idiomatic Architecture

> A structural design companion to `design_d.md`. Describes how confiq's internals
> should be organised when the guiding constraint is the Rust discipline: named data
> structs, explicit trait protocols, typed pipeline stages, and enum variants rather
> than magic strings. Nothing here requires Rust; the constraint is a lens, not a
> target language.

---

## 1. Guiding principles

Three Rust habits drive every decision in this document:

1. **Data and behaviour are separate.** A struct holds state; a trait describes
   what you can do with that state. In Python terms: frozen dataclasses carry data,
   Protocol classes carry behaviour. They do not live in the same type.

2. **Every intermediate state is named.** A raw `tuple` or `dict` flowing through
   a pipeline has no type identity, no field names, and no documentation. If a value
   exists at a boundary between two steps, it gets a name.

3. **Variants are enums, not strings.** A `Literal["a", "b"]` is just a string with
   extra annotation. An `Enum` is a first-class type with exhaustive dispatch, a
   canonical `repr`, and no typo hazard.

---

## 2. Core type vocabulary

These types live in `_types.py` and are imported throughout the package. They are
the vocabulary on which everything else is expressed.

### 2.1 `MergeMode`

```python
class MergeMode(str, enum.Enum):
    OVERRIDE = "override"
    FILL = "fill"
```

`OVERRIDE` is the normal precedence rule: a source's value replaces any prior value
for the same key. `FILL` is the defaults rule: a source contributes a key only if no
higher-precedence source has already supplied it.

Using `str` as the mixin base makes `MergeMode` backward-compatible at call sites
that pass the string form — `mode="override"` is accepted wherever
`mode: MergeMode` is declared.

### 2.2 `SourceMeta`

```python
@dataclass(frozen=True)
class SourceMeta:
    name: str
    mode: MergeMode = MergeMode.OVERRIDE
    profile: str | None = None
```

The three attributes common to every source form a single cohesive value. A
`SourceMeta` can be constructed once, stored, compared, hashed, and passed without
risk of its fields drifting. In Rust this would be a struct; here it is a frozen
dataclass. It is the *data half* of a source; the *behaviour half* is a Protocol
(§3).

### 2.3 `FetchedEntry`

```python
@dataclass(frozen=True)
class FetchedEntry:
    name: str
    data: Mapping[str, Any]
    mode: MergeMode
```

The unit of work handed to the merge step. One `FetchedEntry` per source, produced
after fetch and before merge. Field names eliminate the positional-tuple encoding
hazard and serve as documentation of what the merge step expects.

### 2.4 `Provenance`

```python
class Provenance(Mapping[str, str]):
    """Read-only map: dotted config path → source name that last set that path."""
    def __init__(self, data: Mapping[str, str]) -> None: ...
```

A named, read-only type for the provenance map produced by the merge step. `Mapping`
semantics — lookup, iteration, `len` — are preserved. Mutation is not: once
constructed, a `Provenance` is an immutable record. It is what `ResolvedSnapshot`
carries and what `_apply_parsers` consults for error messages.

### 2.5 `ErrorContext`

```python
@dataclass(frozen=True)
class ErrorContext:
    field_path: str
    sources: Sequence[str]
```

The diagnostic payload shared by the two field-level error variants. Extracting it as
a named struct makes the structure of errors explicit: both `MissingConfigError` and
`ConfigValidationError` are "an error kind plus a context", not two classes that
happen to carry the same fields independently.

### 2.6 `FieldAnnotations`

```python
FieldAnnotations: TypeAlias = Mapping[str, Sequence[Any]]
```

The return type of `SchemaAdapter.field_metadata()`. A named alias — rather than a
bare `Mapping[str, list[Any]]` — gives the type a domain identity and a single place
to tighten if the element type is ever narrowed (e.g. `Sequence[ConfigField | Any]`).

### 2.7 `PluginList`

```python
PluginList: TypeAlias = tuple[object, ...]
```

A named alias for the heterogeneous collection of pluggy plugin objects. A bare
`tuple[object, ...]` communicates nothing about what the objects are expected to be.
The alias names the role. If a `ConfiqPlugin` Protocol is introduced, the alias is
the single place to update.

---

## 3. Source abstraction

### 3.1 The trait hierarchy

The three-level hierarchy separates the *shared metadata contract* (data) from the
*fetch contracts* (behaviour):

```python
@runtime_checkable
class Source(Protocol):
    """Attribute-only base. The data half of a source lives in meta."""
    meta: SourceMeta

@runtime_checkable
class SyncSource(Source, Protocol):
    """A source that delivers data synchronously."""
    def fetch(self) -> Mapping[str, Any]: ...

@runtime_checkable
class AsyncSource(Source, Protocol):
    """A source that delivers data asynchronously."""
    async def fetch_async(self) -> Mapping[str, Any]: ...
```

`Source` is the base type for mixed-source collections. `SyncSource` and
`AsyncSource` each add exactly one method. Neither re-declares the shared metadata
attributes — those live once, in `SourceMeta`, accessed via `source.meta`.

### 3.2 `BaseSource`

A convenience base class for synchronous sources. It constructs and stores a
`SourceMeta`, then exposes `name`, `mode`, and `profile` as forwarding properties so
the flat-attribute access pattern (`source.name`) is available without re-declaring
anything.

```python
class BaseSource:
    def __init__(
        self,
        *,
        name: str,
        mode: MergeMode = MergeMode.OVERRIDE,
        profile: str | None = None,
    ) -> None:
        self.meta = SourceMeta(name=name, mode=mode, profile=profile)

    @property
    def name(self) -> str: return self.meta.name

    @property
    def mode(self) -> MergeMode: return self.meta.mode

    @property
    def profile(self) -> str | None: return self.meta.profile

    def fetch(self) -> Mapping[str, Any]: ...
```

Concrete sources (`EnvSource`, `FileSource`, `MemorySource`, etc.) subclass
`BaseSource` and pass their constructor arguments to `super().__init__()`. They
satisfy the `SyncSource` Protocol structurally without declaring a single attribute
themselves.

### 3.3 External source implementors

A third party implementing the `Source` protocol directly — without subclassing
`BaseSource` — must expose a `meta: SourceMeta` attribute. The forwarding properties
(`name`, `mode`, `profile`) are not required by the protocol; they are a convenience
supplied by `BaseSource`. Code that reads `src.meta.name` works against any
conforming source; code that reads `src.name` works only against `BaseSource`
subclasses (or sources that choose to add the property themselves).

---

## 4. Loader abstraction

```python
@runtime_checkable
class Loader(Protocol):
    def parse(self, raw: bytes) -> Mapping[str, Any]: ...
```

A `Loader` is stateless and has no metadata of its own. Built-in loaders carry a
`suffixes: frozenset[str]` class attribute used by `FileSource` for auto-selection,
but this is not part of the protocol. A `Loader` is the minimal thing: bytes in,
mapping out.

---

## 5. Schema adapter abstraction

```python
@runtime_checkable
class SchemaAdapter(Protocol[T]):
    def field_metadata(self) -> FieldAnnotations: ...
    def validate(self, data: Mapping[str, Any]) -> T: ...
```

Two operations, named precisely: read the per-field `Annotated` metadata
(`field_metadata`), and coerce a merged mapping into the schema type (`validate`).
The return type of `field_metadata` is `FieldAnnotations` (§2.6) rather than an
anonymous `Mapping[str, list[Any]]`.

---

## 6. Resolution pipeline

The resolver drives six named stages. Each stage has explicit input and output types;
no raw `dict` or tuple crosses a stage boundary anonymously.

### 6.1 Stage types

```
Stage 1  profile filter:  Sequence[Source]    → Sequence[Source]
Stage 2  fetch:           Sequence[Source]    → Sequence[FetchedEntry]
Stage 3  merge:           Sequence[FetchedEntry] → ResolvedSnapshot
Stage 4  adapter:         schema + plugins    → SchemaAdapter[T]
Stage 5  coerce:          ResolvedSnapshot + FieldAnnotations → dict[str, Any]
Stage 6  validate:        dict[str, Any]      → T | SchemalessConfig
```

### 6.2 `ResolvedSnapshot`

```python
@dataclass(frozen=True)
class ResolvedSnapshot:
    merged: dict[str, Any]
    provenance: Provenance
```

The output of the merge stage. `merged` is the deep-merged config dict; `provenance`
is the read-only record of which source last set each leaf. Passing a
`ResolvedSnapshot` — rather than two loose values — into the coerce and validate
stages makes the boundary explicit and prevents `merged` and `provenance` from
drifting apart.

### 6.3 The fetch → merge transition

The fetch stage transforms `Sequence[Source]` into `Sequence[FetchedEntry]`. The
construction is explicit:

```python
entries = [
    FetchedEntry(name=src.meta.name, data=src.fetch(), mode=src.meta.mode)
    for src in sync_sources
]
```

`FetchedEntry` is the only thing that crosses into `merge_sources`. `merge_sources`
knows nothing about the original source objects — only the three values it needs to
perform the merge.

### 6.4 `merge_sources` and `deep_merge`

```python
def merge_sources(fetched: Sequence[FetchedEntry]) -> ResolvedSnapshot: ...

def deep_merge(
    base: Mapping[str, Any],
    overlay: Mapping[str, Any],
    *,
    mode: MergeMode,
    source_name: str,
    provenance: dict[str, str] | None = None,
    path_prefix: str = "",
) -> dict[str, Any]: ...
```

`deep_merge` keeps a mutable `dict[str, str]` accumulator for provenance
internally. `merge_sources` wraps the completed accumulator in `Provenance` before
returning — the mutable accumulation is an implementation detail of the merge step,
invisible outside it.

---

## 7. Error design

### 7.1 Hierarchy

```
ConfiqError                     # base
├── SourceError                 # a source's fetch() raised
├── SchemaError                 # no adapter found, or schema misconfigured
├── MissingConfigError          # a required field is absent from all sources
└── ConfigValidationError       # coercion or validation failed
```

### 7.2 `ErrorContext`

`MissingConfigError` and `ConfigValidationError` both carry an `ErrorContext`
(§2.5) as their primary payload:

```python
class MissingConfigError(ConfiqError):
    context: ErrorContext

    def __init__(self, context: ErrorContext) -> None: ...

    @property
    def field_path(self) -> str: return self.context.field_path

    @property
    def sources(self) -> Sequence[str]: return self.context.sources


class ConfigValidationError(ConfiqError):
    context: ErrorContext
    original: Exception | None

    def __init__(
        self,
        context: ErrorContext,
        *,
        original: Exception | None = None,
    ) -> None: ...

    @property
    def field_path(self) -> str: return self.context.field_path

    @property
    def sources(self) -> Sequence[str]: return self.context.sources
```

The forwarding properties on both classes preserve the flat `err.field_path` and
`err.sources` access pattern at the call site. The underlying structure — both errors
carrying a common inner value — is reflected in the types, not hidden by it.

### 7.3 Rationale

`ErrorContext` is extracted because `field_path` and `sources` are not coincidentally
the same on two unrelated classes — they are the same because both errors carry
identical diagnostic context about *which field failed* and *which sources were
involved*. Naming that context makes the shared identity explicit and provides a
single place to evolve it (e.g., adding source-level values, secret-masking logic).

---

## 8. Resolution spec and entry points

### 8.1 `ResolutionSpec`

```python
@dataclass(frozen=True)
class ResolutionSpec(Generic[T]):
    schema: type[T] | None
    sources: Sequence[Source]
    profile: str | None = None
    plugins: PluginList = ()
```

`PluginList` (§2.7) replaces the bare `tuple[object, ...]`. `sources` is typed as
`Sequence[Source]` (the base protocol) so both sync and async sources are expressible
without a union type.

### 8.2 Entry points

```python
def load(
    schema: type[T] | ResolutionSpec[T] | None,
    sources: Sequence[SyncSource] | None = None,
    *,
    profile: str | None = None,
    plugins: PluginList = (),
) -> T | SchemalessConfig: ...

async def load_async(
    schema: type[T] | ResolutionSpec[T] | None,
    sources: Sequence[Source] | None = None,
    *,
    profile: str | None = None,
    plugins: PluginList = (),
) -> T | SchemalessConfig: ...
```

`load()` accepts `Sequence[SyncSource]` — the type system enforces the sync-only
contract statically. `load_async()` accepts `Sequence[Source]` (the base, covering
both sync and async sources). There is no union in either signature.