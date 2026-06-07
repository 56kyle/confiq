# Rust-idiomatic Restructuring Proposals

This document proposes a set of Python architectural changes to make confiq's
type structure more Rust-idiomatic — named data structs, clean trait protocols,
explicit pipeline stages, and enum variants instead of magic strings. The goal
is not 1:1 Rust translation; it is to apply Rust's discipline of separating
data from behaviour, and naming every intermediate state.

Proposals are ordered by dependency. Earlier ones unblock later ones and are
the safest to land first. Proposals 1–3 and 6 are zero-to-soft-breaking
internal changes. Proposals 4 and 5 touch the public `Source` protocol and
error constructors respectively.

---

## 1. `ListFillBehavior` → `MergeMode` StrEnum

**File:** `_types.py` + 9 consumers

### Problem

`ListFillBehavior: TypeAlias = Literal["override", "fill"]` is a string alias
with no runtime identity, no exhaustive dispatch, and no `repr`. Its name is
also misleading — the behavior governs how any key-value overlay is applied,
not just lists.

### Proposed shape

```python
# _types.py
import enum

class MergeMode(str, enum.Enum):
    OVERRIDE = "override"
    FILL = "fill"

ListFillBehavior: TypeAlias = MergeMode  # transition alias
```

All `mode: ListFillBehavior = "override"` call sites continue to work because
`StrEnum` accepts string literals. Internal usages migrate to `MergeMode.OVERRIDE`.

### Breaking? No.

---

## 2. `FetchedEntry` — named struct for the merge input

**Files:** `_merge.py`, `_resolve.py`

### Problem

```python
def merge_sources(
    fetched: Sequence[tuple[str, Mapping[str, Any], ListFillBehavior]],
) -> ResolvedSnapshot: ...
```

The 3-tuple is positional. Callers must know the ordering by convention.
There is no named field, no IDE completion, and no place to add documentation.
In Rust this would be a struct.

### Proposed shape

```python
# _merge.py
@dataclass(frozen=True)
class FetchedEntry:
    name: str
    data: Mapping[str, Any]
    mode: MergeMode

def merge_sources(fetched: Sequence[FetchedEntry]) -> ResolvedSnapshot: ...
```

Construction in `_resolve.py`:

```python
# before
entries = [(src.name, src.fetch(), src.mode) for src in sources]

# after
entries = [FetchedEntry(name=src.name, data=src.fetch(), mode=src.mode) for src in sources]
```

### Breaking? No — `_merge` is internal.

---

## 3. `Provenance` — named read-only mapping type

**Files:** `_types.py`, `_merge.py`, `_resolve.py`

### Problem

`provenance: dict[str, str]` (dotted path → source name) is passed as a mutable
bare dict into `deep_merge`, accumulated, then stored in the frozen
`ResolvedSnapshot`. The type carries no domain meaning and is semantically
immutable by convention, not by enforcement.

### Proposed shape

```python
# _types.py
class Provenance(Mapping[str, str]):
    """Read-only map: dotted config path → source name that last set it."""
    def __init__(self, data: Mapping[str, str]) -> None: ...
    # standard Mapping ABC implementations

# _merge.py
@dataclass(frozen=True)
class ResolvedSnapshot:
    merged: dict[str, Any]
    provenance: Provenance   # was dict[str, str]
```

`deep_merge` keeps a mutable `dict[str, str]` accumulator internally and wraps
it in `Provenance` at the boundary. `_apply_parsers` receives `Provenance`
(read access only — which is the actual access pattern there).

### Breaking? Soft.

`snapshot.provenance["key"]` and iteration continue to work. Direct mutation
was already blocked by `frozen=True` on `ResolvedSnapshot`; this just enforces
it on the value itself.

---

## 4. `SourceMeta` — separate source data from source traits

**Files:** `source/_source.py`, `source/_base_source.py`, all source subclasses

### Problem

The `Source` Protocol mixes three data attributes (`name`, `mode`, `profile`)
directly into the trait. In Rust: `struct SourceMeta` holds the data; the
traits carry the behaviour. The three fields form a cohesive, re-usable struct —
but are currently scattered as independent Protocol attributes that every
concrete class must independently satisfy.

### Proposed shape

```python
# _types.py (or source/_source.py)
@dataclass(frozen=True)
class SourceMeta:
    name: str
    mode: MergeMode = MergeMode.OVERRIDE
    profile: str | None = None

# source/_source.py
@runtime_checkable
class Source(Protocol):
    """Attribute-only base. Data lives in meta; traits carry behaviour."""
    meta: SourceMeta

@runtime_checkable
class SyncSource(Source, Protocol):
    def fetch(self) -> Mapping[str, Any]: ...

@runtime_checkable
class AsyncSource(Source, Protocol):
    async def fetch_async(self) -> Mapping[str, Any]: ...
```

`BaseSource` stores a `SourceMeta` and exposes shim properties so existing
subclasses need no immediate changes:

```python
# source/_base_source.py
class BaseSource:
    def __init__(
        self,
        *,
        name: str,
        mode: MergeMode = MergeMode.OVERRIDE,
        profile: str | None = None,
    ) -> None:
        self.meta = SourceMeta(name=name, mode=mode, profile=profile)

    # Shim properties — removable once all subclasses are migrated
    @property
    def name(self) -> str: return self.meta.name
    @property
    def mode(self) -> MergeMode: return self.meta.mode
    @property
    def profile(self) -> str | None: return self.meta.profile
```

All concrete subclasses pass constructor args to `super().__init__()` rather
than setting attributes directly. The resolver accesses `src.meta.name` /
`src.meta.mode` internally; `src.name` continues to work via the shim.

### Breaking?

Yes — for users who implement `Source` directly (not via `BaseSource`).
They must now expose `meta: SourceMeta` instead of three flat attributes.
All built-in sources are covered by the `BaseSource` shim. Requires an ADR.

---

## 5. `ErrorContext` — shared payload struct for field-level errors

**Files:** `_errors.py`, `_resolve.py`

### Problem

`MissingConfigError` and `ConfigValidationError` have identical constructor
arguments (`field_path: str`, `sources: Sequence[str]`). In Rust this is the
enum-variant-with-shared-inner-struct pattern:

```rust
enum ConfiqError {
    Missing(ErrorContext),
    ValidationFailed { ctx: ErrorContext, original: Option<Box<dyn Error>> },
}
```

### Proposed shape

```python
# _errors.py
@dataclass(frozen=True)
class ErrorContext:
    """Diagnostic payload shared by field-level config errors."""
    field_path: str
    sources: Sequence[str]

class MissingConfigError(ConfiqError):
    context: ErrorContext
    def __init__(self, context: ErrorContext) -> None: ...

    # Shim properties for backward compatibility
    @property
    def field_path(self) -> str: return self.context.field_path
    @property
    def sources(self) -> Sequence[str]: return self.context.sources

class ConfigValidationError(ConfiqError):
    context: ErrorContext
    original: Exception | None
    def __init__(self, context: ErrorContext, *, original: Exception | None = None) -> None: ...

    @property
    def field_path(self) -> str: return self.context.field_path
    @property
    def sources(self) -> Sequence[str]: return self.context.sources
```

### Breaking?

Yes at construction sites — callers that build these errors directly must wrap
the two fields in an `ErrorContext`. Read access via `.field_path` / `.sources`
is shimmed and backward-compatible. Requires an ADR.

---

## 6. `FieldAnnotations` + `PluginList` — named aliases

**File:** `_types.py` + consumers

### Problem

Two recurring types are opaque:

- `Mapping[str, list[Any]]` returned by `field_metadata()` — represents
  per-field `Annotated` metadata items, with no domain name.
- `tuple[object, ...]` used for `plugins` throughout `_load.py`, `_resolve.py`,
  `_hookspecs.py` — communicates nothing about what a plugin is or does.

### Proposed shape

```python
# _types.py
FieldAnnotations: TypeAlias = Mapping[str, Sequence[Any]]
PluginList: TypeAlias = tuple[object, ...]
```

`SchemaAdapter.field_metadata()` returns `FieldAnnotations`. `ResolutionSpec.plugins`
and all `resolve()` / `load()` signatures use `PluginList`. No runtime change —
these are anchors for future tightening (e.g. `PluginList` → `tuple[ConfiqPlugin, ...]`
once a `ConfiqPlugin` Protocol is defined).

### Breaking? No.

---

## Summary

| # | Change | New type | Breaking? |
|---|--------|----------|-----------|
| 1 | `ListFillBehavior` → StrEnum | `MergeMode` | No |
| 2 | Merge input 3-tuple → named struct | `FetchedEntry` | No |
| 3 | `provenance: dict[str,str]` → named type | `Provenance` | Soft |
| 4 | `Source` flat attrs → nested data struct | `SourceMeta` | Yes (protocol) |
| 5 | Shared error fields → inner struct | `ErrorContext` | Yes (constructors) |
| 6 | Opaque generic types → named aliases | `FieldAnnotations`, `PluginList` | No |

**Recommended implementation order:** 1 → 2 → 3 → 6 → 5 → 4.
Proposals 1–3 and 6 are safe to land in any order. Do 5 before 4 since error
raise sites live in `_resolve.py`, which is also touched by 4.