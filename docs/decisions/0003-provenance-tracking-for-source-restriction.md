---
status: accepted
date: 2026-05-29
---
# Enforce Source Restrictions via Provenance Tracking, Not Pre-Merge Filtering

## Context and Problem Statement

`ConfigField.sources` restricts which source names may supply a value for a
given field. The resolver must detect and act on violations. Two structural
approaches are available for this detection, and the choice determines how
cleanly the merge phase and the schema-aware phase stay separated.

## Decision Drivers

- The merge phase (`deep_merge`) should remain generic: no schema knowledge,
  no per-field logic. It is a pure data operation on ordered mappings.
- The schema-walk phase should be the single place where `ConfigField` metadata
  is read and acted on.
- Violation detection must be accurate after all sources have been applied —
  detecting that the *last* source to set a key was a forbidden one is the
  semantically correct check, matching the "later sources win" precedence model.

## Considered Options

- **Pre-merge filtering** — before merging each source's mapping into `merged`,
  drop any key that `ConfigField.sources` forbids for that source.
- **Provenance tracking** — merge all sources normally, recording which source
  last wrote each dotted leaf key. Check `provenance[field]` against
  `ConfigField.sources` during the schema walk.

## Decision Outcome

Chosen option: **provenance tracking**, because it preserves the clean
separation between the merge phase (generic, schema-agnostic) and the
schema-walk phase (schema-aware, metadata-driven).

`ResolvedSnapshot` carries both `merged` and `provenance` as a unit between
the two phases, making the data flow explicit: merge produces the snapshot,
the schema walk consumes it.

### Consequences

- `_merge.py` has no knowledge of `ConfigField` or schema types. It remains
  a pure structural operation that can be tested and reasoned about
  independently.
- `_resolver.py` is the single location where `ConfigField.sources` is
  evaluated. Violations (raise or warn-and-skip) are handled there.
- Provenance records the *last* source to set a key, consistent with the
  "later sources win" merge semantics. A value filtered pre-merge from an
  earlier source would have been overridden anyway; the semantically relevant
  check is whether the winning source is permitted.
- `ResolvedSnapshot.provenance` is available to callers of `resolve()` for
  diagnostics — error messages can report exactly which source supplied the
  offending value.

## Pros and Cons of the Options

### Pre-merge filtering

- Good, because filtering happens close to the source that supplied the value,
  before it enters the merged dict.
- Bad, because it requires schema metadata during the merge phase, coupling
  two concerns that are cleanest when kept separate.
- Bad, because filtering must be applied per-source, meaning the schema walk
  is distributed across the merge loop rather than located in one place.
- Bad, because it cannot accurately handle the case where an allowed source
  later overrides a forbidden one — the filtering would have already removed
  the forbidden value, but the merge outcome is correct and should not be
  rejected.

### Provenance tracking

- Good, because the merge phase remains a pure structural operation: no schema
  imports, no per-field branching, no `ConfigField` reads.
- Good, because violation checking is co-located with all other `ConfigField`
  metadata evaluation, making the schema-walk phase the single authoritative
  location for field-level policy.
- Good, because `provenance` accurately reflects the last-wins merge outcome,
  matching the semantics users reason about when they order the `sources` list.
- Good, because `provenance` is reusable for diagnostics: `MissingConfigError`
  and `ConflictingSourceError` can report which source was responsible.
- Neutral, because it requires carrying a `provenance` dict alongside `merged`
  through the resolution pipeline. `ResolvedSnapshot` encapsulates this pair
  cleanly.
