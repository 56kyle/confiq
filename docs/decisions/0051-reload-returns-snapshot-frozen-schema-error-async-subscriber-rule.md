---
status: accepted
date: 2026-07-14
amends: "0018"
---
# Reload Reconciliation: Returns `T`, Refuses With `SchemaError`, Async-Subscriber Rule at `reload()`

## Context and Problem Statement

ADR 0018 fixed `ConfigHandle`'s constructor shape (spec-only, inline subscribers, `[reload]`
extra) and remains sound on those points. But three of its provisional details predate the later
design_d §8.2 shape and the §13 error taxonomy, and one — the async-subscriber dispatch rule —
was written against a fact the handle cannot actually know. Stage 8 implements `ConfigHandle`,
so these are reconciled now, alongside the code.

## Decision Drivers

- **Return shape should match `load()`.** ADR 0018 wrote `reload()`/`reload_async()` as
  `-> None`. The later design_d §8.2 and `load()`'s value-returning shape both hand back the
  fresh snapshot; a reload that recomputes a value and discards it forces the caller back through
  `handle.current` for the thing it just triggered.
- **Refusal names its remediation, in the taxonomy.** ADR 0018 refused a non-frozen schema with
  `ValueError`. The §13 taxonomy routes schema-shape refusals through `SchemaError`, and the
  refusal-names-remediation principle wants the message to point at "use a frozen schema" under
  the type callers already `except` for schema problems.
- **Dispatch on knowable facts.** ADR 0018's rule — "an async subscriber raises at registration
  time *if only sync `reload()` will be used*" — conditions on a fact unknowable at
  `on_reload()` time: a handle always *has* `reload_async`, so whether the caller will use it is
  not decidable there. The honest split is: at `on_reload()`, only the subscriber's color is
  known (never enough to refuse — the handle can always be driven async); at `reload()`, both
  facts are known (a live async subscriber exists AND the sync path is being taken), so that is
  where the refusal belongs.

## Considered Options

### Return type
- **Option A (chosen): `-> T`**, returning the new snapshot.
- **Option B: `-> None`** (ADR 0018). Rejected: forces a follow-up `.current` read and diverges
  from `load()`.

### Frozen-schema refusal type
- **Option A (chosen): `SchemaError`.**
- **Option B: `ValueError`** (ADR 0018). Rejected: outside the §13 taxonomy; callers catching
  `SchemaError` for schema-shape problems would miss it.

### Async-subscriber dispatch
- **Option A (chosen): `on_reload` never refuses an async subscriber; `reload()` raises
  `RuntimeError` when a live async subscriber exists.** Registering an async subscriber commits
  the handle to `reload_async()`.
- **Option B (ADR 0018): refuse the async subscriber at `on_reload()`** based on "only sync
  reload will be used". Rejected: that fact is not knowable at registration.
- **Option C: `reload()` silently skips async subscribers.** Rejected: a subscriber that
  silently never fires is a footgun.

## Decision Outcome

`reload()` and `reload_async()` return the new snapshot (`-> T`). `ConfigHandle.__init__`
refuses a non-frozen schema — a non-frozen pydantic model, non-frozen dataclass, TypedDict, or
schemaless spec — with `SchemaError` naming the frozen remediation. `on_reload` routes a
subscriber by color (`asyncio.iscoroutinefunction`) to a sync or async blinker signal and never
refuses; `reload()` raises `RuntimeError` (pointing at `reload_async()`) if a live async
subscriber is registered. Registering an async subscriber therefore commits the handle to
`reload_async()`.

The frozen-schema detection: `is_base_model` → `model_config.get("frozen", False)`;
`dataclasses.is_dataclass` → `__dataclass_params__.frozen` (covers stdlib and pydantic
dataclasses); TypedDict and schemaless are refused (they cannot express frozenness).

### Consequences

**Positive:**
- `reload()`/`reload_async()` hand back the snapshot they compute; no follow-up `.current` read.
- Frozen-schema refusal lives in the §13 taxonomy under `SchemaError`.
- Async-subscriber dispatch conditions only on facts knowable at each site; no silent no-fire.

**Negative:**
- Registering an async subscriber makes a later sync `reload()` raise. Accepted: it is a clear,
  early `RuntimeError` naming `reload_async()`, strictly better than ADR 0018's unknowable-fact
  refusal or a silent skip.

## Relationship to ADR 0018

Supersedes ADR 0018 on three points — return type (`-> None` → `-> T`), frozen-schema refusal
(`ValueError` → `SchemaError`), and async-subscriber dispatch (registration-time refusal → a
`reload()`-time `RuntimeError`). ADR 0018's constructor shape (spec-only, inline sync
subscribers, `[reload]` extra, construction-time frozen enforcement) stands unchanged.
