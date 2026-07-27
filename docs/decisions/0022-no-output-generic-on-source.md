---
status: accepted
date: 2026-06-07
---
# `Source` Carries No Output Generic

## Context and Problem Statement

With three protocol levels — `Source` (shared attributes), `SyncSource`
(adds `fetch()`), `AsyncSource` (adds `fetch_async()`) — a natural question
arises: should the fetch methods carry a generic output type `T`?

```python
# Hypothetical
class SyncSource(Source, Protocol[T]):
    def fetch(self) -> T: ...
```

This ADR records the deliberate rejection of that shape and the reasoning
behind it, so the question is not re-opened without new evidence.

## Decision Drivers

- Sources produce partial, schema-agnostic `Mapping[str, Any]` fragments. The
  merge step collapses heterogeneous fragments from all sources into a single
  `Mapping[str, Any]`. Validation is post-merge by necessity: a required field
  absent from source A may be supplied by source B, so partial fragments cannot
  be validated individually.
- A `Source[X]` output type would never connect to the schema generic `T`.
  `T` enters at `SchemaAdapter` after the merge; the per-source output type is
  erased at the merge boundary. The generic would be ornamental.
- The genuine distinction between str-valued sources (environment variables,
  dotenv) and native-valued sources (TOML, JSON, in-memory dicts) is a
  category difference handled largely by Pydantic coercion, not a type
  parameter to propagate through the pipeline.
- The intended architectural shape is "typed at the edges (schema via `T`),
  dynamic in the middle (sources + merge)." A source-level generic breaches
  that boundary without benefit.

## Considered Options

- **Option A: `SyncSource[T]` / `AsyncSource[T]`** — generic output type
  propagated from each source through the pipeline.
- **Option B: Ungeneric `Source` hierarchy** — `T` lives only at the typing
  edge (`load`, `SchemaAdapter`, `ResolutionSpec`, `ConfigHandle`,
  `LazyConfig`).

## Decision Outcome

Chosen option: **Option B**, because the output type of a source never
connects to the schema generic and would be erased at the merge. The generic
adds no static guarantees and complicates every source implementation and
every call site that passes sources.

### Consequences

**Positive:**
- Source implementations are simpler: no type parameter to declare or
  propagate.
- `ResolutionSpec[T]` keeps `T` cleanly at the schema level; sources are
  `Sequence[Source]`, not `Sequence[Source[???]]`.
- The "typed at edges, dynamic in middle" contract is explicit and enforced.

**Negative:**
- The str-valued vs native-valued category difference has no static
  representation. This is acceptable because Pydantic coercion handles the
  conversion at validation time.

## Pros and Cons of the Options

### Option A: `SyncSource[T]` / `AsyncSource[T]`

- Good, because it signals at the type level what kind of data a source
  produces.
- Bad, because the `T` parameter is erased at the merge — it never flows to
  the schema-level `T`. The generic is purely decorative.
- Bad, because every source implementation must declare a type parameter, and
  every `Sequence[SyncSource]` parameter must decide what `T` to use. The
  answer is always `Mapping[str, Any]`, making the annotation ceremony without
  value.
- Bad, because it implies a guarantee (typed output connected to schema
  validation) that the architecture cannot provide.

### Option B: Ungeneric `Source` hierarchy (chosen)

- Good, because source implementations have no type parameter to manage.
- Good, because `Sequence[Source]` and `Sequence[SyncSource]` are clean,
  unambiguous parameter types.
- Good, because the schema generic `T` lives exclusively at the validation
  boundary, where it is meaningful.
- Neutral, because the str-valued vs native-valued distinction is not
  statically typed. This is handled by Pydantic coercion and is not a gap
  that warrants a generic.
