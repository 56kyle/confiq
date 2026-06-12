---
status: accepted
date: 2026-06-12
---
# Complexity Is Judged by Inherence to the Problem, Not by Maintenance Burden

## Context and Problem Statement

During the async scope discussion (2026-06-12), the cons of supporting async were argued
partly from maintainer burden: doubled test matrix, doubled documentation, "maintenance
drag on every future feature." The project owner rejected that class of argument:

> "Complexity is fine. The problem is complexity that is not inherent to the problem we
> are solving."

This is the essential-vs-accidental complexity distinction (Brooks). The question a
capability must answer is not "how much work does this create?" but "is the structure it
implies part of the problem confiq solves?" Conflating the two lets effort-avoidance
masquerade as design judgment — and conversely, lets genuinely accidental complexity in
when it happens to be cheap.

## Decision Drivers

- Burden arguments are unfalsifiable in the same way raw UX arguments are (ADR 0034):
  everything is more work; the frame must distinguish work worth doing.
- The same artifact can be essential or accidental depending on the problem definition —
  so this filter deliberately relocates scope disputes to the problem statement (§1),
  which is where the project owner wants the battle fought.
- A concrete instance proved the redirect productive: the twin `load`/`load_async`
  overload bug was cited as doubled-maintenance evidence; under this frame it is a
  *representation* defect (hand-maintained duplicates that can drift), fixed by sharing
  the pipeline, not by deleting a capability.

## The principle

**Whether a capability belongs in confiq is decided by whether its complexity is
inherent to the problem being solved. Maintenance burden never decides membership; at
most, capacity sequences the order in which essential work is done.**

### Corollaries

1. **Burden arguments are struck.** "More tests/docs/code to maintain" is not an
   admissible reason to refuse a capability. If the complexity is essential, the
   maintenance is simply the work of solving the problem.
2. **Duplication pain is a representation smell, not a scope argument.** When supporting
   something forces hand-maintained twins, the answer is a representation where the
   twins cannot drift (shared pipeline, single source of truth), not removal of the
   capability. Concrete commitment: the resolver pipeline (§6.2) is color-agnostic
   except at the fetch step; sync and async entry points are thin shells over the same
   steps (§9.4).
3. **Argument classes that survive the filter** (because they claim the complexity is
   *accidental*):
   - **False structure** — an interface asserting a property its implementations lack
     (e.g. built-in `AsyncSource`s wrapping sync-only SDKs: async clothing on blocking
     calls).
   - **Out-of-problem structure** — capability serving users outside the §1 triangle
     without an explicit case (§15's concept-cost orientation; the user-side tax is
     legitimate exactly when the concept is accidental *for the user*).
   - **Defects against the problem itself** — e.g. a recommended workaround that
     corrupts provenance undermines §1 criterion 4 directly.
   - **Inherent-to-environment costs are accepted, not litigated** — Python's colored
     functions mean two entry points for two calling colors; that is the language's
     essential complexity, not the design's.
4. **Deferral/irreversibility arguments are hedges, not costs.** "Adding later is
   additive; shipping now is permanent" carries weight only while the problem boundary
   is genuinely undecided. Once a capability is judged essential, reversibility
   asymmetry carries none.

### Capacity vs membership

"We have to prioritize what we support" remains legitimate: finite capacity sequences
*when* essential work happens. It never converts essential complexity into a refusal —
the recorded outcome of capacity pressure is "later," not "no."

## Considered Options

- **Option A: Inherence decides membership; capacity sequences; burden inadmissible.**
- **Option B: Conventional cost-benefit** — maintenance burden weighed as a co-equal
  factor alongside user value.
- **Option C: Capability maximalism** — support everything plausibly useful; complexity
  managed as it arrives.

## Decision Outcome

Chosen option: **Option A**, because it keeps scope disputes where they belong (the
problem definition), makes effort-avoidance arguments visible as such, and productively
redirects duplication pain into representation work.

### Consequences

**Positive:**
- Scope arguments must be phrased as claims about the problem ("async fetch is not a
  shape our users' config takes today") rather than about effort — claims that can be
  checked against evidence and revisited when the ecosystem changes.
- The §14.2 async question is reframed accordingly: a problem-boundary call per
  capability (async reload = essential complexity of the optional `[reload]`
  sub-problem; async fetch = currently false structure for built-ins, real only for
  async-native custom sources), with burden off the table.
- Representation quality becomes a first-class obligation: accepting essential
  complexity obliges factoring that prevents drift.

**Negative:**
- Essential complexity, once admitted, is genuinely more work — and this ADR forbids
  using that work as a brake. The brake must come from honest problem-boundary
  judgment, which is harder to argue than effort.
- "Is it inherent?" is itself a judgment call dependent on a contestable problem
  definition; two reasonable people can still disagree. That is intended — the filter
  frames the argument, it does not replace it (ADR 0034's anti-systematization caveat
  applies here too).

## Pros and Cons of the Options

### Option A: Inherence filter (chosen)

- Good, because it separates "is this our problem?" from "do we feel like it?" — only
  the first is a design question.
- Good, because it disciplines both directions: cheap-but-accidental structure is
  refused as readily as expensive-but-essential structure is accepted.
- Bad, because it removes the most convenient brake on scope; problem-boundary
  discipline (§1, §15) must carry the entire load.

### Option B: Burden as co-equal factor

- Good, because it reflects how capacity-constrained teams actually feel.
- Bad, because burden arguments are always available against everything, so they
  systematically bias toward under-supporting the problem — and they hide the real
  question (membership) behind a proxy (effort).

### Option C: Capability maximalism

- Good, because no user is ever turned away.
- Bad, because it is how config libraries become the illegible everything-tools (§15)
  this project exists to escape; accidental complexity compounds into the user's
  concept tax.
