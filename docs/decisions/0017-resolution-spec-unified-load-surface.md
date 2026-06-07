---
status: accepted
date: 2026-06-06
supersedes: "0010"
---
# ResolutionSpec as the Unified Load Surface

## Context and Problem Statement

design_d §7.1.

`load()` and `ConfigHandle.create()` accepted the same four ingredients —
schema, sources, profile, plugins — as separate arguments on each function.
Keeping them in sync was a documentation discipline, not a structural guarantee.

Plugins were a deeper problem. ADR 0010 fixed a bug where user-registered
plugins were silently dropped on every reload by giving `ConfigHandle` a
persistent `PluginManager` (`self._pm`). That fix was correct for the
implementation that existed, but it modelled plugins as a handle concern rather
than a resolution concern. The result: the same plugin had to be registered in
two different places when both a one-shot `load()` and a `ConfigHandle` were
used in the same application, and nothing structural enforced that the two call
shapes produced the same resolution behaviour.

## Decision Drivers

- A `ConfigHandle` is "hold a load spec and re-run it on demand." That
  equivalence should be structural — one object that both functions accept —
  rather than described only in prose.
- Plugins describe *how to resolve* (which adapters, which transforms). They
  belong to the resolution description, not the reload lifecycle.
- If plugins are part of the spec, they persist across handle reloads because
  the spec persists. The handle-owned `PluginManager` and the `_load_with_pm()`
  internal split are no longer needed.
- A shared spec object makes drift between `load()` and `ConfigHandle`
  structurally impossible: both callers hand the same value to the same
  resolver.

## Considered Options

- **Option A: `ResolutionSpec[T]` frozen dataclass** — schema, sources,
  profile, plugins in one immutable value. Both `load()` and `ConfigHandle`
  accept it. Convenience overloads build it internally so callers who never
  name a spec are unaffected.
- **Option B: Keep per-parameter API; pass `PluginManager` explicitly** —
  ADR 0010's approach, extended. `load()` and `ConfigHandle` remain
  structurally separate; plugin persistence is the handle's responsibility.
- **Option C: Builder pattern** — `ResolutionBuilder(schema).add_source(...)`
  constructing the spec through method chaining.

## Decision Outcome

Chosen option: **Option A**, because the structural parity between `load()` and
`ConfigHandle` is the correct model, and plugins-in-spec follows directly from
that model.

### API shape

```python
@dataclass(frozen=True)
class ResolutionSpec(Generic[T]):
    schema: type[T] | None                      # None → schemaless resolution
    sources: Sequence[Source | AsyncSource]
    profile: str | None = None
    plugins: tuple[object, ...] = ()
```

`load()` and `load_async()` each expose two overloads: one that accepts a
`ResolutionSpec` directly, and one convenience overload that builds it
internally from separate arguments. Both forms run the same resolver.

### Why plugins belong in the spec

ADR 0010's persistent `PluginManager` was a correctness fix for a specific bug:
`load()` rebuilt its PM on every call, so plugins passed to
`ConfigHandle.create()` were registered on the first PM and then thrown away on
reload. The real fix is to give the spec — and therefore every call through it
— a stable set of plugins. That makes the handle-owned PM redundant. The handle
stores a spec and a snapshot; it carries no plugin machinery of its own.

### Consequences

**Positive:**
- `load(spec)` and `ConfigHandle(spec)` share one resolution surface and cannot
  drift. The "handle = re-run the load" equivalence is now in the type, not the
  docs.
- Plugin persistence is a property of the spec. A one-shot `load(spec)` and a
  long-lived `ConfigHandle(spec)` use the same plugins with no extra
  registration step.
- ADR 0010's `_load_with_pm()` internal split and `self._pm` on the handle are
  no longer needed.

**Negative:**
- `ResolutionSpec` is a new public type callers must learn. Mitigated by the
  convenience overloads: existing `load(schema, sources)` call shapes continue
  to work unchanged.
- Callers who registered plugins via `ConfigHandle.create(plugins=[...])` must
  move those to `ResolutionSpec(schema, sources, plugins=(MyPlugin(),))`. This
  is a breaking API change; `ConfigHandle` was provisional in design_d and no
  code has shipped.

## Pros and Cons of the Options

### Option A: `ResolutionSpec[T]` (chosen)

- Good, because the handle/load equivalence is structural.
- Good, because plugins-in-spec is semantically correct — they describe
  resolution, not lifecycle.
- Good, because the handle-owned `PluginManager` complexity is eliminated.
- Neutral, because one new public type is introduced. Convenience overloads
  keep the common call shapes unchanged.

### Option B: Per-parameter API with explicit PluginManager (ADR 0010)

- Good, because no new public type; existing call shapes are unchanged.
- Bad, because the handle-PM split is an implementation workaround for a design
  mismatch. Plugins belonging to the handle rather than the resolution is the
  wrong model.
- Bad, because `load()` and `ConfigHandle` remain structurally different;
  drift between them is possible and not caught by the type system.

### Option C: Builder pattern

- Good, because incremental construction is ergonomic for complex specs.
- Bad, because a mutable builder is harder to reason about than a frozen value
  type. Spec composition (combining two specs) becomes awkward.
- Bad, because the Python ecosystem precedent for configuration specifications
  (pydantic, dynaconf) favours named dataclasses over builder patterns.
