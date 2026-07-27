---
status: accepted
date: 2026-06-12
---
# Canonical Schema Path Table Keyed by Dotted Path

## Context and Problem Statement

The resolver pipeline is connected by "a dotted field path," but no artifact owns the path
key space, and four subsystems currently use incompatible keys:

- `Provenance` is keyed by dotted path (`"database.host"`) — design_d §6.5.
- `FieldAnnotations` (the return of `SchemaAdapter.field_metadata`) is keyed by **bare
  top-level field name**. For the design's own canonical example —
  `Database.password: Annotated[str, ConfigField(secret=True)]` nested inside `Settings` —
  the metadata is unreachable: `field_metadata()` on `Settings` yields entries for
  `database` and `debug` only.
- CLI parameters are underscored identifiers mapped to paths by a convention (ADR 0027).
- `ErrorContext.field_path` (ADR 0025) has no stated format.

Three advertised features consume per-field metadata by path and silently fail for nested
fields as currently specified: `ConfigField.parser` coercion (resolver step 5),
secret masking in `repr` and error output (§3, §13), and `ConfigField.env` name overrides
(§6.2 step 2). The key-space mismatch also leaves `_apply_parsers(merged, metadata,
provenance)` with no way to join its two mappings.

## Decision Drivers

- One key space must serve metadata lookup, provenance, env/CLI binding, parser
  application, secret masking, and error reporting — these are the same address, viewed
  from different steps.
- Adapters already hold the schema class; recursing into nested schema types is local to
  each adapter and requires no new protocol surface beyond the key-space change.
- The path table is the artifact ADR 0027's CLI convention and the env `prefix+delimiter`
  mapping validate against; without it those mappings are guesswork.
- Retrofitting a key space after sources, adapters, and the error API ship against
  divergent ad-hoc versions is prohibitively expensive; deciding it pre-implementation is
  nearly free.
- Maps to a Rust `BTreeMap<FieldPath, FieldEntry>` (ADR 0021 tiebreaker).

## Considered Options

- **Option A: `FieldAnnotations` keyed by dotted path; adapters recurse** — one canonical
  table per schema covering all fixed nested paths.
- **Option B: Keep flat keys; resolve nested metadata ad hoc per consumer** — each
  consumer (parsers, masking, env overrides) walks the schema itself.
- **Option C: Nested mapping mirroring the schema tree** — `Mapping[str, FieldNode]` with
  child nodes.

## Decision Outcome

Chosen option: **Option A**, because a single dotted-path-keyed table unifies the key
space with `Provenance` and `ErrorContext.field_path`, gives every consumer one lookup,
and makes the CLI/env binding conventions checkable against a concrete set of valid paths.

### Shape

```python
FieldAnnotations: TypeAlias = Mapping[str, list[Any]]
# keys are dotted paths: {"database": [...], "database.host": [...],
#  "database.password": [ConfigField(secret=True)], "debug": [...]}
```

`SchemaAdapter.field_metadata()` returns entries for **every fixed path** reachable from
the schema root, recursing through nested pydantic models, pydantic dataclasses, stdlib
dataclasses, and `TypedDict`s. Intermediate paths (e.g. `"database"`) appear with their
own annotations (possibly empty), so the table doubles as the set of valid paths.

**Fixed paths only.** Metadata recursion stops at collection element types and union
branches: a `list[Model]` field contributes its own path but not per-element paths, and a
`A | B` field contributes only the field's path. Per-element addressing has no stable
dotted form and is out of scope.

The table is computed once per adapter instance (the adapter is constructed with the
schema and may cache).

### Consequences

**Positive:**
- Nested `ConfigField` metadata — `secret`, `parser`, `env` — works, fixing the design's
  own §4.2 example.
- `Provenance`, `FieldAnnotations`, `ErrorContext.field_path`, the env mapping, and the
  CLI convention (ADR 0027) share one key space; `_apply_parsers` can join its inputs.
- "The set of valid paths" becomes a queryable artifact, enabling ADR 0027's
  longest-match disambiguation and future tooling (e.g. a provenance-dump command).

**Negative:**
- Adapter implementations must recurse and must detect nested schema kinds (a pydantic
  model containing a stdlib dataclass crosses adapter families); the recursion contract
  lives in each adapter.
- Tables are larger than flat maps. Config schemas are small; computed once per adapter,
  this is negligible.

## Pros and Cons of the Options

### Option A: Dotted-path keys with adapter recursion (chosen)

- Good, because one lookup serves every consumer and one key space spans the pipeline.
- Good, because the valid-path set becomes explicit and checkable.
- Good, because `Mapping[str, list[Any]]` is flat and trivially serialisable (and maps to
  a Rust map keyed by a path newtype).
- Neutral, because intermediate paths carry mostly-empty annotation lists.

### Option B: Flat keys, ad hoc per-consumer resolution

- Good, because adapters stay simple.
- Bad, because every consumer reimplements schema walking — three implementations of the
  same recursion with three sets of edge-case bugs.
- Bad, because the PEP 563 / forward-reference fragility §4.4 confines to specific
  adapters would leak into every consumer.

### Option C: Nested tree mirroring the schema

- Good, because structure mirrors the schema exactly.
- Bad, because every consumer needs tree traversal where the address it holds (provenance
  key, error path, env var) is already a flat dotted string.
- Bad, because it diverges from `Provenance`'s established flat key space.
