---
status: accepted
date: 2026-07-13
---
# `load()` Takes `schema`/`sources` Positional-or-Keyword, Not Keyword-Only

## Context and Problem Statement

design_d §14.1 #2 recorded a provisional signature call: `load()`'s convenience form takes
`schema` and `sources` positionally, with `profile`/`plugins` keyword-only, and named
keyword-only `sources` as "the more defensive alternative." Stage 5 fills `load()`, so the call
becomes concrete.

Two facts forced the decision:

1. The signature design_d §7.2 *writes* is
   `def load(schema, sources, *, profile=None, plugins=())` — no `/`, so `schema` and `sources`
   are positional-or-keyword. Every example (§8.3, §10.6) calls it as
   `load(Settings, sources=[...])` — i.e. `sources` passed by keyword.
2. The signature-only skeleton, however, marked `schema` and `sources` **positional-only** (a
   `/` after `sources`). That directly forbids `load(Settings, sources=[...])` — the exact form
   the examples use. The skeleton was internally inconsistent with the spec it stubs.

So the `/` had to go regardless. The remaining live choice was the one §14.1 #2 named: leave
`sources` positional-or-keyword (matching §7.2), or make it keyword-only for defensiveness.

## Decision Drivers

- **Match the written design and its examples.** §7.2's signature and every call site in the
  doc are positional-or-keyword; diverging would make the reference examples wrong.
- **Least surprise.** Positional arguments are ordinary Python; `load(Settings, [env])` reads
  fine and `load(Settings, sources=[env])` reads better — both should work, as they do for any
  normal two-arg function.
- **The defensive win is marginal here.** Keyword-only `sources` guards against positional
  argument soup, but `load` has only two leading positionals (`schema`, `sources`) with
  obviously different types; transposition is not a real hazard.
- **Overload dispatch is unaffected.** The spec form `load(spec, /)` stays positional-only and
  is distinguished at runtime by `isinstance(arg, ResolutionSpec)`; the convenience form's
  argument-passing style is orthogonal to that.

## Considered Options

- **Option A (chosen): positional-or-keyword `schema`/`sources`.**
  `def load(schema, sources, *, profile=None, plugins=())`. Both `load(Settings, [env])` and
  `load(Settings, sources=[env])` work.
- **Option B: keyword-only `sources`.** `def load(schema, *, sources, profile=None, plugins=())`.
  Forces `load(Settings, sources=[env])`; forbids the bare-positional shorthand.

## Decision Outcome

Chosen option: **Option A**. The convenience overloads and the implementation drop the
skeleton's positional-only `/` after `sources`; `profile`/`plugins` stay keyword-only (`*`); the
spec-only overload `load(spec, /)` keeps its positional-only `/`. `load_async` is aligned to the
same shape so the two entry points do not diverge (a user moving from `load(Settings,
sources=[...])` to `load_async(Settings, sources=[...])` must not hit a signature error).

### Consequences

**Positive:**
- The public signature matches design_d §7.2 and every documented example verbatim.
- Both the shorthand and the self-documenting keyword form are available; callers choose.
- `load` and `load_async` share one calling convention.

**Negative:**
- No compile-time guard against `load(Settings, [env])` being written positionally where a
  reader might have preferred the explicit `sources=`. Accepted: the two positionals are
  distinctly typed and the keyword form remains available for those who want it. Re-adding
  keyword-only `sources` later would be a breaking change, but the risk it guards against is
  low.

## Relationship to design_d §14.1 #2

Resolves §14.1 #2: positional-or-keyword is kept; the keyword-only-`sources` alternative is
declined. §14.1 #2 is annotated RESOLVED with this ADR. The skeleton's positional-only `/` is
recorded as a bug fixed here, not a design change.
