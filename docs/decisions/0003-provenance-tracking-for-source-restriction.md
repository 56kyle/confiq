---
status: accepted
date: 2026-05-29
---
# Track Merge Provenance to Surface Source Names in Error Messages

## Context and Problem Statement

When `confiq` raises `MissingConfigError` or `ConfigValidationError`, the error
message must name the source responsible for the offending value — not just the
field path. Without this, a user staring at a validation failure has no way to
know whether the bad value came from a `.env` file, an environment variable, a
remote config store, or a `MemorySource` in a test.

The question is how to make that source-attribution information available at
error-raise time, given that the merge phase and the schema-aware validation
phase are deliberately kept separate.

## Decision Drivers

- The merge phase (`deep_merge`) should remain generic: no schema knowledge,
  no per-field logic. It is a pure data operation on ordered mappings.
- The schema-walk and validation phase should be the single place where
  per-field metadata is read and acted on.
- Attribution must reflect the *winning* source — the last one to set a key
  under the "later sources win" merge semantics — not any intermediate source
  that was overridden.

## Considered Options

- **Pre-merge annotation** — tag each value with its source name at merge time
  by wrapping it in a `(value, source_name)` pair before entering `merged`.
- **Provenance tracking** — merge all sources normally into a plain `merged`
  dict, and maintain a parallel `provenance` dict recording which source last
  wrote each dotted leaf key. Pass both as a `ResolvedSnapshot` to the
  validation phase.

## Decision Outcome

Chosen option: **provenance tracking**, because it preserves the clean
separation between the merge phase (generic, schema-agnostic) and the
validation phase (schema-aware, metadata-driven), while accurately reflecting
last-wins merge semantics.

`ResolvedSnapshot` carries both `merged` and `provenance` as a unit between
the two phases, making the data flow explicit: merge produces the snapshot,
validation consumes it.

### Consequences

- `_merge.py` has no knowledge of `ConfigField` or schema types. It remains
  a pure structural operation that can be tested and reasoned about
  independently.
- `_resolver.py` reads `provenance` when constructing error objects.
  `MissingConfigError` and `ConfigValidationError` include the responsible
  source name in their human-readable message.
- Provenance records the *last* source to set a key, consistent with the
  "later sources win" merge semantics. This is the value the user will see;
  it is the source worth naming.
- `ResolvedSnapshot.provenance` is also available to callers of internal
  `resolve()` for diagnostics beyond error messages.

## Pros and Cons of the Options

### Pre-merge annotation

- Good, because the source name travels with the value through the entire
  pipeline — no separate dict to maintain.
- Bad, because it requires every consumer of `merged` to unwrap `(value, name)`
  pairs rather than operating on plain values. This couples the merge format
  to the provenance feature.
- Bad, because the merge phase can no longer treat values as plain Python
  objects; structural operations like deep-merge become more complex.

### Provenance tracking

- Good, because the merge phase remains a pure structural operation: no schema
  imports, no per-field branching, no `ConfigField` reads.
- Good, because `merged` is a plain nested dict — downstream consumers (pydantic
  `TypeAdapter`, schema adapters, tests) work with it directly.
- Good, because `provenance` accurately reflects the last-wins merge outcome,
  matching the semantics users reason about when they order the `sources` list.
- Good, because `provenance` is available for diagnostics beyond error messages
  without further plumbing changes.
- Neutral, because it requires carrying a `provenance` dict alongside `merged`
  through the resolution pipeline. `ResolvedSnapshot` encapsulates this pair
  cleanly.
