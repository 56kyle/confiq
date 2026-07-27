---
status: accepted
date: 2026-06-07
---
# Rust-Port Readiness as a Design Principle

> Amended by [ADR 0034](0034-design-ideals-clarification.md) (2026-06-12): the
> port-readiness framing is retired as a design principle. The structured/enum practices
> this ADR anchored (ADR 0023, ADR 0024) stand on their own legibility merits; port
> alignment is an acknowledged side benefit, and future ADRs must not cite the port as a
> decision driver. The layer-separation and non-commitment rules below remain good
> guidance if a port is ever actually pursued.

## Context and Problem Statement

confiq has a speculative future: a maturin/PyO3 Rust core with a thin Python
binding layer. The question is how much — if at all — that speculation should
influence day-to-day design choices.

Two failure modes exist. Ignoring the port entirely means that if it ever
happens, the Python internals will need a larger restructuring pass. Over-
indexing on it means contorting the Python API for a port that may never
happen — and paying that ergonomic cost on every caller today.

A third path: use the port as a tiebreaker for genuine design toss-ups, keep
the Python API Python-shaped, and place the reconciliation responsibility in a
PyO3 binding layer if and when the port occurs.

## Decision Drivers

- Structured and enum-typed forms are cheap in Python and map ~1:1 to Rust
  structs and enums. Where they are no worse than the alternatives, prefer
  them.
- The public Python API must remain ergonomic for Python callers. Port-aligned
  internals do not require a Rust-shaped public surface.
- The `confiq` crate name may be taken; external factors make the port
  speculative. Design decisions must not be held hostage to it.
- This principle serves as the rationale anchor for ADR 0023 (named boundary
  types) and ADR 0024 (MergeMode enum), where both decisions had viable Python
  alternatives and resolved toward the structured form.

## Considered Options

- **Option A: Port-aligned tiebreaker** — structured/enum forms win genuine
  toss-ups; Python ergonomic wins keep the Python form.
- **Option B: Python-idiomatic throughout** — no port consideration enters
  design decisions.
- **Option C: Explicit Rust-ready goal** — design the public Python API to
  match what a PyO3 binding would expose.

## Decision Outcome

Chosen option: **Option A**, because it captures the actual disposition:
speculative alignment where cheap, no contortion where costly.

### Rules of the principle

1. **Tiebreak rule.** When two designs are genuinely equivalent on Python
   grounds, resolve toward the structured/enum form. This is a tiebreaker, not
   a preference that overrides ergonomics.

2. **Layer separation.** Internal representation ≠ public contract. A
   Rust-aligned internal type does not imply a Rust-shaped Python API. The
   PyO3 binding layer is the right reconciliation point.

3. **Non-commitment.** The port is speculative. No decision should be framed
   as "because we will port to Rust." The frame is "this is no worse for Python
   callers and easier to port if we ever do."

### Consequences

**Positive:**
- Design decisions with no clear Python winner have an explicit, reproducible
  tiebreaker instead of being re-litigated each time.
- The rationale for structured internal types (ADR 0023, ADR 0024) is recorded
  once here rather than repeated.
- If a port happens, the binding layer has well-named, single-purpose types to
  wrap rather than anonymous tuples and ad-hoc strings.

**Negative:**
- The tiebreaker requires judgment about what constitutes a "genuine toss-up"
  vs a clear Python ergonomic win. Future contributors must read this ADR to
  apply it consistently.
- Structured forms can add ceremony for simple cases. The rule is a tiebreaker
  only; it does not justify ceremony where Python has a clearer idiom.

## Pros and Cons of the Options

### Option A: Port-aligned tiebreaker (chosen)

- Good, because it gives genuine toss-ups a consistent resolution without
  contorting clear Python ergonomic wins.
- Good, because the layer-separation principle keeps the public API Python-
  shaped regardless of internal alignment.
- Good, because the non-commitment clause prevents the port speculation from
  blocking or distorting design decisions.
- Neutral, because it requires judgment about toss-up vs clear winner. The
  judgment call is unavoidable regardless of which option is chosen.

### Option B: Python-idiomatic throughout

- Good, because no port consideration enters design decisions — simpler rule.
- Bad, because genuine toss-ups have no resolution mechanism and may be re-
  opened repeatedly.
- Bad, because if a port does happen, the migration cost is higher than it
  needed to be.

### Option C: Explicit Rust-ready goal

- Good, because port alignment is maximised.
- Bad, because it contorts the Python API. Python callers pay today for a port
  that is speculative.
- Bad, because PyO3 bindings already exist precisely to reconcile Rust types
  with Python ergonomics — there is no need to pre-solve that problem in Python.
