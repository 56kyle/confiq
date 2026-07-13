---
status: accepted
date: 2026-07-13
---
# Resolver Retains the `ResolvedSnapshot` at the Color-Agnostic Seam; `explain()` Deferred

## Context and Problem Statement

design_d §14.2 #4 leaves resolution observability open: an `explain()`-style dump (the merged
config + per-leaf source attribution, secrets masked) would attack the "config breaks
invisibly" problem on the *success* path, not only in error messages (§6.4). It is a
candidate feature, not committed for v1.

Stage 4 fills the sync resolver (`_resolve.py`, design_d §6.2). The resolver already builds a
`ResolvedSnapshot(merged, provenance)` at the merge step because error messages need the
provenance. The one decision that is expensive to defer is **structural**: does the pipeline
keep the snapshot reachable after validation succeeds, or discard it? If `resolve()` is
written as a straight `sources → value` funnel that drops the snapshot once validation passes,
a future `explain()` forces re-plumbing the pipeline to thread the snapshot back out — exactly
the kind of retrofit the §14.2 #4 note flags as costly. The plan therefore gates this at
Stage 4: decide the *retention shape* now, without committing the `explain()` *surface*.

## Decision Drivers

- **Auditable magic (ADR 0034, design_d §2).** Success-path observability is squarely in the
  project's identity; keeping it cheaply reachable is worth a small structural cost now.
- **Retrofit asymmetry.** Retaining the snapshot at an internal seam is nearly free today;
  re-threading it through an already-shipped pipeline later is not.
- **No premature surface.** `explain()` needs its own ADR (where it lives — API, CLI, or both;
  masking rules; output shape). Shipping the *plumbing* must not smuggle in an unversioned
  *API*.
- **The color-agnostic seam already exists (ADR 0035).** Stage 4 factors a shared inner core
  so Stage 6's `resolve_async` is a shell. That same seam is the natural, single place to
  surface a snapshot for both colors at once.

## Considered Options

- **Option A (chosen): retain the snapshot at the inner seam; keep the public return
  unchanged.** The color-agnostic core returns `(value, ResolvedSnapshot)`; `resolve()`
  projects to just the value. No public observability surface ships.
- **Option B: build `explain()` now.** Add the observability API in Stage 4.
- **Option C: discard after validation.** `resolve()` uses the snapshot only for error
  provenance and drops it on success.

## Decision Outcome

Chosen option: **Option A**. The shared core
`_resolve_from_fetched(schema, fetched, plugins) -> tuple[T | SchemalessConfig, ResolvedSnapshot]`
produces and returns the snapshot; `resolve()` binds `value, _snapshot = ...` and returns only
`value`, so the **public return is unchanged** — `resolve()` still yields `T | SchemalessConfig`.

- The retained snapshot holds the **raw merged view** (pre-coercion). `_apply_parsers`
  deep-copies before coercing so parser output never leaks into the snapshot; "which source
  supplied each leaf" stays faithful to what the sources actually contributed.
- A future `explain()` becomes a **projection** of an already-available value (mask secrets,
  format `merged` + `provenance`), not a pipeline change. Its API/CLI locus, masking, and
  output shape are deferred to their own ADR when the feature is scheduled.
- The seam is color-agnostic, so if async entry points ship (§14.2 #3), `resolve_async`
  surfaces the identical snapshot for free.

### Consequences

**Positive:**
- Success-path observability is a cheap projection away; no re-plumbing cost was locked in.
- `resolve()`'s contract and the `load()` surface above it are untouched — Stage 5 builds on a
  stable return type.
- Sync and async share one snapshot-producing seam; observability cannot drift by color.

**Negative:**
- The core returns a two-tuple whose second element has exactly one current consumer (nobody)
  — a whisker of unused structure carried for a not-yet-scheduled feature. Justified by the
  retrofit asymmetry; the alternative (Option C) trades this for a costlier future change.
- Retaining the raw merged mapping keeps it alive for the call's duration. Negligible for
  config-sized data; noted for completeness.

## Relationship to design_d §14.2 #4

This ADR resolves only the *structural* half of §14.2 #4. `explain()` as a first-class surface
remains a candidate feature with its own future ADR; §14.2 #4 is updated to record that the
resolver now retains the snapshot at the seam, so the remaining decision is purely the surface,
not the plumbing.
