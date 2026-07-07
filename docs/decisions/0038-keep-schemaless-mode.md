---
status: accepted
date: 2026-07-07
---
# Keep Schemaless Mode (`schema=None`)

## Context and Problem Statement

design_d §14.2 (open question #2) asks whether schemaless mode — `load(schema=None)`
returning a read-only `SchemalessConfig` mapping (design_d §7.4) — should exist at all,
noting that pydantic `ConfigDict(extra="allow")` or an explicit `extra: dict` field might
cover the use case. This ADR resolves that open question as Stage 2 (adapters) reaches the
`SchemalessAdapter` and the `schema=None` resolution branch.

## Decision Drivers

- **`extra="allow"` is not a substitute for the stated ask.** `extra="allow"` still
  requires the user to *declare a BaseModel*; it delivers a typed core with a permissive
  tail and attribute access (the §4.6 "typed-open middle ground"). Schemaless is a
  different product: *no schema at all*, subscript access, zero pydantic surface — the
  §7.4 "I have no schema; hand me the merged mapping" case (quick scripts, exploration,
  dynamic/unknown-shape config). §14.2's own test ("is any real user hard-blocked?") cuts
  toward keeping, because "define an empty permissive model" is a different product, not
  the same one.
- **A committed ADR already depends on it.** ADR 0037 leans on `load(schema=None)` as "a
  reliable debugging view that faithfully reflects the same merged shape the schema'd path
  produces." Removing schemaless now would strand an affordance a ratified decision relies
  on.
- **Inherence, not burden (ADR 0035).** "Give me the merged config, untyped" is inherent to
  the configuration problem (design_d §1's config corner), not accidental structure. The
  membership question is decided on that, not on the maintenance of the branch.
- **The cost is contained.** The `SchemalessAdapter` is trivial (empty `field_metadata`,
  wrap-in-`SchemalessConfig` `validate`). The real ongoing tax is the
  `T | SchemalessConfig` return union threading through `resolve()` and `load()`, but the
  public API hides it behind overloads (`load(schema: type[T]) -> T` vs
  `load(None) -> SchemalessConfig`), so callers see clean types; the union is an internal,
  bounded concern.

## Considered Options

- **Option A: Keep schemaless mode.** Implement `SchemalessConfig`, `SchemalessAdapter`,
  and the `schema=None` resolution branch; retain the `T | SchemalessConfig` internal union
  behind public overloads.
- **Option B: Remove schemaless mode.** Delete `_schemaless.py` and `SchemalessAdapter`;
  users wanting permissive config declare a BaseModel with `extra="allow"`.

## Decision Outcome

Chosen option: **Option A**. Schemaless serves a genuine config use case that
`extra="allow"` does not cover, ADR 0037 already depends on it, and under inherence-not-
burden the untyped-merged-config capability belongs to the problem. The union tax is real
but bounded and invisible at the public surface.

### Consequences

**Positive:**
- The "no schema, just the merged mapping" case is a first-class, typed-at-the-edge path.
- ADR 0037's debugging-view property has a home.

**Negative:**
- The `T | SchemalessConfig` union persists internally through the resolver and load
  surface; every internal consumer must account for the schemaless branch. Mitigated by
  public overloads so callers never see the union.
- Schemaless opts out of type safety and secret masking entirely (it has no fields, so the
  ADR 0033 refusal is structurally unreachable there); this is the accepted trade of the
  opt-out (design_d §2.9/§4.6), not a defect.

Resolves design_d §14.2 open question #2.
