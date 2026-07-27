---
status: accepted
date: 2026-06-07
---
# Named Types at Multi-Value Resolver Boundaries

## Context and Problem Statement

The resolver pipeline passes data between steps using bare composite forms:
anonymous tuples, parallel dicts, and bare `tuple[object, ...]` annotations.
These forms are adequate when there is one value to pass, but wherever a step
produces or consumes multiple correlated values, the absence of a name makes
the contract implicit and the code harder to follow.

Naming multi-value boundaries is near-zero cost in Python (a `@dataclass` or
`TypeAlias` line) and aligns with ADR 0021's tiebreaker: these types map ~1:1
to Rust structs, so naming them now makes a hypothetical port cheaper without
imposing any ergonomic cost on Python callers today.

## Decision Drivers

- **`FetchedEntry`** — the unit passed from the fetch step to the merge step.
  Currently the merge loop re-examines `Source` objects directly, coupling it
  to the source protocol. A named entry type (`name`, `data`, `mode`) decouples
  the two steps.
- **`ResolvedSnapshot`** — already exists as `@dataclass(frozen=True)` in
  `_merge.py` with `merged: dict[str, Any]` and `provenance: dict[str, str]`.
  It is the right shape; document it explicitly here so it is not removed by
  a future simplification pass.
- **`Provenance`** — a `TypeAlias` for `Mapping[str, str]` (dotted field path
  → source name). Currently the provenance dict appears as a bare `dict[str,
  str]` at several sites. Naming it gives the concept a single definition and
  makes it the natural attachment point for future enhancements: secret-
  masking, structured error output, provenance-in-errors.
- **`FieldAnnotations`** — a `TypeAlias` for `Mapping[str, list[Any]]`.
  Currently the return type of `SchemaAdapter.field_metadata` is annotated with
  the bare form; naming it communicates intent and makes the type easier to
  refer to in docs and error messages.
- **`PluginList`** — a `TypeAlias` for `tuple[object, ...]`. Currently appears
  bare in `ResolutionSpec.plugins` and the `load` overloads. A name documents
  that this is an ordered, immutable sequence of pluggy plugins, not an
  arbitrary tuple.
- **Threshold:** name boundaries that carry *multiple correlated values*.
  Single-value intermediates (e.g., the merged `dict[str, Any]` between the
  coerce and validate steps) remain as plain types — no ceremony.

## Considered Options

- **Option A: Named types for every multi-value boundary** — introduce the five
  types listed above; leave single-value intermediates as plain types.
- **Option B: Status quo** — bare dicts, tuples, and `Mapping` annotations
  throughout the pipeline.
- **Option C: Full struct-ify** — name every intermediate, including single-
  value pass-throughs.

## Decision Outcome

Chosen option: **Option A**, with the stated threshold. The five named types
are introduced; single-value intermediates are left as plain types.

### Named types

| Name | Kind | Fields / alias target | Location |
|------|------|-----------------------|----------|
| `FetchedEntry` | frozen dataclass | `name: str`, `data: Mapping[str, Any]`, `mode: MergeMode` | `_types.py` or `_merge.py` |
| `ResolvedSnapshot` | frozen dataclass | `merged: dict[str, Any]`, `provenance: Provenance` | `_merge.py` (existing) |
| `Provenance` | TypeAlias | `Mapping[str, str]` | `_types.py` |
| `FieldAnnotations` | TypeAlias | `Mapping[str, list[Any]]` | `_types.py` |
| `PluginList` | TypeAlias | `tuple[object, ...]` | `_types.py` |

`FetchedEntry.mode` uses `MergeMode` (ADR 0024); the two ADRs are
complementary.

### Threshold rule

A boundary type is named when it carries multiple correlated values whose
relationship constitutes a contract (e.g., `name + data + mode` are the three
attributes the merge step needs to process one source's contribution). A
boundary that passes a single value is left as a plain type annotation.

### Consequences

**Positive:**
- The merge step can accept `Sequence[FetchedEntry]` rather than re-examining
  `Source` objects. Fetch and merge are decoupled.
- `Provenance` is defined once; all sites that build, accept, or display
  provenance data use the same alias. Future enhancements (secret-masking,
  structured error output) have a natural attachment point.
- `ResolvedSnapshot` is explicitly documented as an intentional type rather
  than an implementation detail at risk of being inlined.
- `FieldAnnotations` and `PluginList` eliminate bare structural types from
  public-facing signatures.

**Negative:**
- `FetchedEntry` is a new dataclass import at every site that constructs one.
  The cost is one import line per source-fetch site.
- The threshold rule requires judgment. The rule ("multiple correlated values")
  is a guideline, not a formula.

## Pros and Cons of the Options

### Option A: Named types for multi-value boundaries (chosen)

- Good, because naming a multi-value boundary makes the contract explicit
  without adding runtime overhead.
- Good, because the five types map ~1:1 to Rust structs (ADR 0021 tiebreaker).
- Good, because `Provenance`, `FieldAnnotations`, and `PluginList` are
  aliases — zero runtime cost, pure readability gain.
- Neutral, because `FetchedEntry` adds a dataclass import. Acceptable for
  a type that crosses a step boundary.

### Option B: Status quo

- Good, because no new symbols are introduced.
- Bad, because the merge loop remains coupled to `Source` objects.
- Bad, because `Provenance` has no canonical home; provenance-related
  enhancements require finding and updating every `dict[str, str]` site.
- Bad, because bare `tuple[object, ...]` in `ResolutionSpec` and `load`
  overloads communicates nothing about what the tuple contains.

### Option C: Full struct-ify

- Good, because every intermediate has a name.
- Bad, because naming single-value pass-throughs adds ceremony with no
  readability benefit. A `CoercedConfig` wrapper around a `dict[str, Any]`
  is not more informative than the dict itself.
