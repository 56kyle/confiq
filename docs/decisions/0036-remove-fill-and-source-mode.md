---
status: accepted
date: 2026-07-06
amends: "0015, 0024"
---
# Remove `MergeMode.FILL` and the Source `mode` Concept for v1

## Context and Problem Statement

design_d §14.2 (open question #1) asks whether to keep or remove `MergeMode.FILL`.
§5.5 already records the tension: a `FILL` source "adds no expressive power over list
position — value is enforced intent." This ADR resolves that open question as
implementation reaches the merge core (Stage 1 of the implementation plan).

A source tagged `mode=FILL` contributes a key only when that key is still absent from
everything merged so far; `OVERRIDE` (the default) contributes all its keys, winning over
lower-precedence sources. The claimed redundancy is that a `FILL` source placed anywhere
behaves like the same source placed at the **bottom** of the list under `OVERRIDE` —
everything above wins, so it only shows through for keys nobody else set.

Two facts sharpen the decision:

- The single-source equivalence holds cleanly, including for nested dicts (an `OVERRIDE`
  deep-merge with the source relocated to lowest precedence reproduces both the merged
  values and the per-leaf provenance).
- It does **not** hold for multiple overlapping `FILL` sources: their gap-fill cascade
  depends on an inter-`FILL` precedence that design_d never defines. Keeping `FILL` would
  force us to invent and pin that ordering now.

## Decision Drivers

- **Reconciliation comes first (ADR 0034).** `FILL` serves none of the config/CLI/tests
  triangle. It is a guard rail against a *source-list authoring mistake* (a maintainer
  reordering sources and silently turning a defaults layer into an override layer), not a
  capability the triangle needs.
- **The guard rail is already diagnosable.** Provenance (ADR 0003, design_d §6.4) surfaces
  the winning source for every leaf, so a reordered-defaults bug is visible in any
  inspection or error without `FILL`.
- **No expressive power is lost.** Every `FILL` arrangement is expressible by ordering
  sources under `OVERRIDE`; §14.2 itself calls `FILL` "position-redundant."
- **Degenerate scaffolding is accidental complexity (ADR 0035).** With `FILL` gone,
  `MergeMode` collapses to a single value and `Source.mode`/`FetchedEntry.mode` become
  always-`OVERRIDE` dead attributes. Carrying that machinery "to make a future re-add
  cheap" is the deferral hedge ADR 0035 corollary 4 explicitly strikes.

## Considered Options

- **Option A: Remove `FILL` and the entire `mode` concept.** Delete `MergeMode`, drop
  `mode` from the source protocols, `BaseSource`, `FetchedEntry`, `deep_merge`, and every
  source constructor.
- **Option B: Remove the `FILL` value only, keep a single-value `MergeMode` + `mode`
  attribute.** Preserves the plumbing so re-adding `FILL` is one enum value.
- **Option C: Keep `FILL`.** Define inter-`FILL` precedence, retain the merge branch and
  its declined-key provenance bookkeeping.

## Decision Outcome

Chosen option: **Option A**. `FILL` earns no place under reconciliation-first, and once it
is gone the `mode` surface is pure accidental complexity that ADR 0035 forbids carrying on
a "cheap to re-add" rationale. Option B keeps a one-valued enum and an always-`OVERRIDE`
attribute — legibility cost for zero present capability. Option C obligates a permanent
branch in the pure merge core plus an ordering design for a feature we judge redundant.

If a real user later hits the reorder footgun `FILL` guarded against, re-adding it is
additive: sources gain an optional `mode` kwarg defaulting to override, `MergeMode` and
the merge branch return, and no existing valid usage breaks. ADR 0035's capacity-sequences
principle records that outcome as "later," not a permanent "no."

### Consequences

**Positive:**
- The merge core has a single behaviour (later-wins overwrite); no `mode` branch, no
  declined-key provenance bookkeeping, no undefined inter-`FILL` ordering to pin.
- The `Source` protocol shrinks to `name` + `profile`; `FetchedEntry` to `name` + `data`.

**Negative:**
- Removes the enforced-intent guard rail that let a source declare itself a
  position-independent fallback. Mitigated by provenance-based diagnosability.
- Re-adding `FILL` later re-threads a `mode` kwarg through every source — more work than
  restoring one enum value, though still additive and non-breaking for users.

### Blast radius

Removes `MergeMode` from `_types.py`; drops `mode` from `Source`/`SyncSource`/`AsyncSource`
(`source/_source.py`), `BaseSource` (`source/_base_source.py`), `FetchedEntry`
(`_merge.py`), the `deep_merge` signature (`_merge.py`), and the `mode=` kwarg on every
concrete source (`_env`, `_file`, `_memory`, `_dotenv`, `_argparse`, `_click`, `_typer`);
removes the `MergeMode` re-export from `confiq/__init__.py`. Source `fetch()`/`name` bodies
remain stubbed — only the `mode` surface is touched. `profile` is a separate concern
(ADR 0015) and is unaffected.

This amends **ADR 0024** (which introduced `MergeMode`) and **ADR 0015** (the source
`mode`/`profile` pair — `profile` survives, `mode` is removed), and resolves design_d
§14.2 open question #1.
