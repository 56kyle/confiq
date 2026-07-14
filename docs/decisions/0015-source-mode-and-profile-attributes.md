---
status: accepted
date: 2026-06-05
amended-by: "0036"
---
# Source `mode` and `profile` Attributes for Declarative Layering and Filtering

> **Amended by ADR 0036.** The source **`mode`** attribute proposed here was removed for v1 (it
> paired with `MergeMode.FILL`, also removed). **`profile` stands** and is implemented as
> described. Do not implement a source `mode` attribute.

## Context and Problem Statement

design_d §5.5–5.6.

Two common config-layering patterns require capabilities beyond basic
ordered-list precedence:

1. **Defaults that cannot overwrite real values.** A caller often wants a
   fallback layer — values used only when no other source supplies them. With
   pure list ordering, the only way to express this is to put the defaults
   source first (lowest precedence). But that assumes the caller controls every
   source above it. In a composed system, a "defaults cannot win" guarantee is
   stronger than a position guarantee.

2. **Environment-specific sources.** Applications running in different
   environments (dev, staging, prod) want to include some sources conditionally.
   The naive approach is to construct a different source list per environment.
   A declarative tag on each source is more readable and less error-prone.

The question is where these attributes live and how they are applied.

## Decision Drivers

- Both behaviors are declarative properties of a source, not properties of the
  merge algorithm or the `load()` call site.
- The composition should be visible at source-list construction time — a reader
  who sees the list should understand what each source contributes and when.
- Profiles must not introduce auto-discovery or implicit environment detection;
  the explicit list and the explicit `profile=` argument to `load()` are the
  complete specification.

## Considered Options

- **Option A: Attributes on the `Source` protocol** — `mode` and `profile` are
  fields on `Source` (and `AsyncSource`), set at source construction time, read
  by the resolver before and during merge.
- **Option B: Parameters on `load()`** — callers pass `defaults=[...]` and
  `profile_map={...}` to `load()` rather than tagging individual sources.
- **Option C: Wrapper types** — `FillSource(inner)` and `ProfiledSource(inner, profile="prod")`
  wrap existing sources to add behavior.

## Decision Outcome

Chosen option: **Option A**, because attributes on the source are visible at the
list construction site, compose with any source type without an extra wrapper
class, and make the resolver's behaviour unambiguous from the source list alone.

### `mode`

```
mode: Literal["override", "fill"]  # default "override"
```

- `"override"` (default): the source contributes all its keys, overwriting
  prior values on collision. Normal precedence.
- `"fill"`: the source contributes only keys *not already present* in the
  merged result so far. A fill source is a defaults layer that cannot
  accidentally overwrite a value from any higher-precedence source.

Lists are replaced, not merged, under both modes: a source's list value
replaces a lower source's list value rather than concatenating.

### `profile`

```
profile: str | None  # default None
```

A source with `profile=None` always participates. A source with `profile="prod"`
participates only when `load(..., profile="prod")` is called. Sources with a
non-matching profile are dropped before fetching (step 1 of the resolver
algorithm).

Profiles are syntactic sugar over explicit list composition. The same outcome is
expressible by constructing a different list per environment; profiles just
avoid that repetition. They do not add a new precedence level.

### `BaseSource` convenience class

`BaseSource` is a concrete base that supplies the defaults (`mode="override"`,
`profile=None`) so concrete source implementations need only declare `name`
and `fetch()`. Conforming to the `Source` protocol directly (without inheriting)
is also valid.

### Consequences

- The resolver's profile filter step (step 1) is a straightforward list
  comprehension: drop sources whose `profile` is set and does not match.
- The merge loop reads `source.mode` before applying each source's mapping.
  No special casing in `_merge.py` — the mode check is in the resolver's
  iteration, which already owns the merge loop.
- Fill sources that come first in the list act as defaults; fill sources that
  come last act as "fill only what everything else left empty." Both are valid
  and their semantics follow directly from position + mode.
- There is no auto-detected "environment" — the caller passes `profile=` to
  `load()` explicitly or not at all.

## Pros and Cons of the Options

### Option A: Attributes on `Source` (chosen)

- Good, because the full behavior of a source is visible at construction time,
  co-located with the source itself in the list.
- Good, because no new types or wrappers are needed — existing source classes
  add `mode` and `profile` fields.
- Good, because the resolver algorithm is straightforward: filter by profile,
  then merge with mode.

### Option B: Parameters on `load()`

- Good, because the source list stays clean — no extra fields per source.
- Bad, because the relationship between a source and its mode or profile is
  expressed at the `load()` call site rather than the list construction site,
  requiring callers to maintain a parallel data structure.
- Bad, because it makes dynamic list construction (building the list
  conditionally) harder to reason about.

### Option C: Wrapper types

- Good, because it avoids adding fields to the `Source` protocol.
- Bad, because `FillSource(inner)` obscures the source type in error messages
  and provenance output.
- Bad, because it requires a wrapper class per behavior, multiplying the type
  surface for a small gain.
