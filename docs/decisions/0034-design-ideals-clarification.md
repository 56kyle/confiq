---
status: accepted
date: 2026-06-12
---
# Design Ideals: Reconciliation First, Legibility, Refusal Over Degradation

## Context and Problem Statement

design_d §2 listed seven principles of equal apparent rank. A deliberate
ideals-clarification discussion (2026-06-12) re-derived them from the motivating problem
and found that several were surface expressions of deeper commitments, one was
misattributed (immutability framed as concurrency), one was doing double duty
("the schema is yours"), and the most consistently applied ideal in the design —
refusing loudly rather than degrading silently — was not stated at all. Meanwhile the
principles' *rank* was unstated, leaving no way to adjudicate when they conflict.

This ADR records the clarified ideals and their hierarchy so that §2 can state them
concisely. **These are judgment guides for arguing specific cases, not decision rules.**
Software development is as much an art as a science; everything depends on the
situation, and no principle here auto-decides a feature.

## The clarified ideals

1. **Reconciliation is the identity.** confiq exists to reconcile configuration, the
   command line, and the test suite — the triangle of §1. This is the number-one
   priority; the other ideals and the supporting habits below are in its service. A
   capability that serves none of the three corners must earn its place on other
   grounds, explicitly.

2. **User experience is the most important factor — weighed by severity, case by
   case.** A library has at least three user moments: writing the app, debugging a
   failure, and testing. When these conflict, the weighing is situational: the worse
   the potential failure, the more the failure-moment experience dominates (a leaked
   secret is not negotiable; a few parentheses of ceremony are). UX is never an excuse
   for poor development practice.

3. **Legibility: magic is permitted when auditable.** The enemy is not implicitness; it
   is *invisible coupling* — an effect with no traceable cause. Convention binding
   validated against the path table is acceptable magic: deterministic, documented,
   inspectable, and loud on ambiguity. A hidden priority integer or ambient mutation is
   not. Provenance (§6.4) is this ideal made executable. Explicitness remains the
   default strategy; auditable convention is the permitted exception, never a cover for
   sloppiness.

4. **Refusal over degradation.** The library never silently provides a weaker guarantee
   than the user believes they have. Where a promise cannot be kept, fail loudly at the
   earliest moment — and every refusal must name a remediation path in its message
   (`load()` rejecting an async source points to `load_async()`; that is the exemplar).
   A refusal without a "do this instead" is a bug against ideal 2. Edge cases may exist;
   none has been found yet, and the burden of proof is on degradation. ADR 0033 (secrets)
   is the first decision derived from this ideal.

## Restatements of existing principles

Same decisions, truer rationale:

- **"Configuration is a value, not an object with identity"** → the load-bearing claim
  is about liability: **the library never owns mutable state.** If ambient state exists
  (§8.3, §8.4), the application owns it knowingly; confiq supplies lifecycle tooling,
  never the global itself.
- **"Immutability is the basis of safety"** → in the common `load()` path, immutability's
  value is *reasoning*: test determinism, no aliasing surprises — **config is a fact,
  not a variable.** Concurrency safety is the special case that matters on the
  `ConfigHandle` path, not the general justification.
- **"The schema is yours"** → the sound core is **schema non-invasion**: confiq never
  appears in your domain types — no base class, no decorator; `Annotated` metadata is
  additive freight. This ideal does *not* by itself entail supporting N schema kinds;
  that is a separate scope question judged on its own costs.
- **Rust-port readiness (ADR 0021)** → retired as a framing. The named-boundaries and
  enum practices (ADR 0023, ADR 0024) stand on their own legibility merits. Port
  alignment is an acknowledged side benefit; it must not be cited as a decision driver.
  (ADR 0021 carries the corresponding amendment note.)

## Open questions tracked, not decided

Recorded in design_d §14 with their deciding criteria: `MergeMode.FILL`
(position-redundant; keep-as-guard-rail vs remove), schemaless mode (kept unless/until
no hard-blocked user exists; `extra="allow"` appears to cover the use case), async
source support (which user; core vs `[reload]`), and first-class resolution
observability (an `explain()`-style provenance surface). A culling pass was explicitly
declined; these resolve through discussion as implementation reaches them.

## Consequences

**Positive:**
- §2 can be short and ranked; conflicts between principles now have a stated (if
  judgment-mediated) way to be argued.
- The refusal ideal converts from implicit house style to citable principle, with the
  remediation-message obligation attached.
- Future ADRs stop citing a speculative port as rationale.

**Negative:**
- "Weighed by severity, case by case" is judgment, not mechanism — two reasonable people
  can still disagree. That is intended: the ideals frame the argument; they do not
  replace it.
- Existing ADRs (0023, 0024, 0025) cite ADR 0021's tiebreaker as a driver; they remain
  valid (their decisions stand on legibility merits) but their cited rationale is
  superseded in part by this ADR.
