---
status: accepted
date: 2026-06-07
---
# Refactor Source/AsyncSource into Source/SyncSource/AsyncSource

## Context and Problem Statement

The current protocol hierarchy has two flat, structurally identical protocols
that duplicate three attribute declarations:

```python
class Source(Protocol):
    name: str
    mode: ListFillBehavior
    profile: str | None
    def fetch(self) -> Mapping[str, Any]: ...

class AsyncSource(Protocol):
    name: str
    mode: ListFillBehavior
    profile: str | None
    async def fetch_async(self) -> Mapping[str, Any]: ...
```

The duplication is a minor readability issue in the protocol file itself, but
its downstream effects are more significant. Every resolver helper that accepts
a mixed source list — `_filter_by_profile`, `resolve_async`, and any future
helper — must annotate its parameter as `Sequence[Source | AsyncSource]`. This
union is not expressive: there is no single type that means "any source,
regardless of delivery mode". It also means `isinstance(x, Source)` currently
implies "this source is synchronous", which is a footgun once the refactor is
complete and `Source` acquires a new meaning.

## Decision Drivers

- Eliminate the duplicated attribute declarations (`name`, `mode`, `profile`)
  from two separate protocols.
- Provide a single base type that covers both sync and async sources, removing
  `Source | AsyncSource` unions from call sites.
- Make `isinstance(x, SyncSource)` and `isinstance(x, AsyncSource)` each
  statically imply a specific `fetch` contract, with no ambiguity about which
  entry point (`load()` vs `load_async()`) applies.
- Reinforce the `load()` signature (`Sequence[SyncSource]`) as a static
  guarantee rather than solely a runtime assertion.

## Considered Options

- **Option A: Three-level hierarchy — `Source` (shared attrs), `SyncSource(Source)`, `AsyncSource(Source)`**
- **Option B: Status quo — flat `Source` (sync) + `AsyncSource`, attributes duplicated**
- **Option C: Flat rename only — `SyncSource` + `AsyncSource`, no shared base**

## Decision Outcome

Chosen option: **Option A**, because it provides the shared base type needed to
annotate mixed-source collections without union types, and captures the shared
contract in a single place.

### Protocol shape

```python
@runtime_checkable
class Source(Protocol):
    """Attribute-only base for all configuration sources."""
    name: str
    mode: ListFillBehavior
    profile: str | None

@runtime_checkable
class SyncSource(Source, Protocol):
    """A source that delivers data synchronously."""
    def fetch(self) -> Mapping[str, Any]: ...

@runtime_checkable
class AsyncSource(Source, Protocol):
    """A source that delivers data asynchronously."""
    async def fetch_async(self) -> Mapping[str, Any]: ...
```

### Impact on call sites

| Location | Before | After |
|---|---|---|
| `resolve()` | `Sequence[Source]` | `Sequence[SyncSource]` |
| `resolve_async()` | `Sequence[Source \| AsyncSource]` | `Sequence[Source]` |
| `_filter_by_profile()` | `Sequence[Source \| AsyncSource]` | `Sequence[Source]` |
| `_assert_no_async_sources()` | runtime guard | replaced by static type |

The `_assert_no_async_sources()` guard is removed from the static type
signature of `resolve()`, which now accepts `Sequence[SyncSource]`. A
lightweight dynamic check at the public `load()` boundary is retained for
source lists constructed without static type annotations.

### Migration

`Source` currently means "has `fetch()`". After this change it means "has
`name`/`mode`/`profile` only". Any code that:

- Implements `Source` as a sync source → annotate as `SyncSource` instead.
- Uses `isinstance(x, Source)` to guard the sync path → use
  `isinstance(x, SyncSource)` instead.
- Annotates mixed-source parameters as `Source | AsyncSource` → replace with
  `Source`.

### Consequences

**Positive:**
- Shared attribute contract in one place; adding a future attribute requires
  one edit in `Source`, not two.
- `resolve_async()` and `_filter_by_profile()` accept `Sequence[Source]` —
  the union is gone.
- `isinstance(x, SyncSource)` / `isinstance(x, AsyncSource)` unambiguously
  classify any source.

**Negative:**
- `Source` is a breaking rename for the sync contract. Existing source
  implementations must update their annotation from `Source` to `SyncSource`.
  Since the project is pre-release and in design_d, this is acceptable.
- `isinstance(x, Source)` is now true for both sync and async sources. Callers
  who expect the old `Source`-means-sync semantics need to update to
  `isinstance(x, SyncSource)`.

## Pros and Cons of the Options

### Option A: Three-level hierarchy (chosen)

- Good, because the shared attribute contract is defined once — no drift
  between sync and async protocol declarations.
- Good, because `Source` is a sound base type for mixed-source collections
  (`Sequence[Source]`), eliminating the `Source | AsyncSource` union
  everywhere.
- Good, because `SyncSource` and `AsyncSource` are specific — each name
  implies the exact fetch contract.
- Bad, because `Source` acquires a new meaning relative to the current
  codebase. The rename is mechanical but touches every source implementation's
  type annotation.

### Option B: Status quo

- Good, because no churn — nothing needs to be renamed.
- Bad, because the three shared attributes are duplicated. Adding a field
  requires editing two protocols.
- Bad, because `Sequence[Source | AsyncSource]` is verbose and non-obvious as
  a parameter type.
- Bad, because `isinstance(x, Source)` misleadingly implies "sync" when used
  as a mixed-source guard.

### Option C: Flat rename only (SyncSource + AsyncSource, no shared base)

- Good, because naming improves (`SyncSource` is more explicit than `Source`),
  and the rename scope is identical to Option A.
- Good, because no new base protocol is introduced.
- Bad, because without a shared base, mixed-source parameters must still use
  `SyncSource | AsyncSource` unions. The verbosity problem is not solved.
- Bad, because adding a shared attribute still requires editing both protocols.