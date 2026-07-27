---
status: accepted
date: 2026-07-14
---
# Async Reload Ships: `reload_async` In-Scope, Thin Shell Over `load_async`

## Context and Problem Statement

design_d §14.2 #3 left async support open, split into a *fetch* half and a *reload* half.
ADR 0047 resolved the fetch half at Stage 6 (`AsyncSource`/`load_async` ship). Stage 8 fills
the live-reload lifecycle (`ConfigHandle`), so the reload half must now be decided: does
confiq's problem include an async-native `reload_async`, or does the handle offer only a
blocking sync `reload()`?

The decision is made under the project's settled scoping discipline (ADR 0047): no "v1 vs
later", scope to the problem's full reasonable range on the information at hand, and deferral is
legitimate only on a genuine information gap.

## Decision Drivers

- **A blocking re-fetch parks the loop under traffic.** `ConfigHandle` lives in long-running
  services and reloads *while serving requests* — the exact under-traffic context ADR 0047
  flagged as a reload matter deferred to this stage. A sync `reload()` that re-fetches every
  source inline blocks the event loop for the duration of the slowest source's I/O. For an
  async service that is a defect, not an inconvenience: the workaround (`run_in_executor`) drops
  ContextVars, the ADR 0013 hazard.
- **The architecture already carries it.** `load_async` exists (ADR 0047) as a thin shell over
  the color-agnostic `_resolve_from_fetched` core (ADR 0035). `reload_async` is a near-free
  increment: the same recompute-swap-notify skeleton as `reload()`, differing only at the
  recompute call (`await load_async(spec)` vs `load(spec)`) and an async-subscriber tail. The
  Stage 6 factoring pre-paid it.
- **No-drift between colors.** Both reload colors call the *same* `_swap` and `_notify_sync`
  helpers; only the recompute and the async-subscriber gather differ. This mirrors the
  `resolve`/`resolve_async` color-agnostic factoring (§9.4, ADR 0035) so the two reload paths
  cannot drift.

## Considered Options

- **Option A (chosen): ship `reload_async`** as a thin shell over `load_async`, sharing the
  swap/notify helpers with `reload()`.
- **Option B: defer**, offer only sync `reload()`. Rejected: the sole argument — "no consumer
  yet" — is the struck burden argument (ADR 0035); a blocking reload in an async service is
  in-range and completely blocking, and the information to build it correctly is on hand.

## Decision Outcome

`reload_async` ships. It runs the same skeleton as `reload()` under the shared
`ReentrancyGuard`: recompute `new = await load_async(spec)`, `old = _swap(new)`,
`_notify_sync(old, new)` (sync subscribers inline, exactly as under `reload()`), then
`await asyncio.gather(*[receiver(old, new) for receiver in live_async_receivers])`. The swap
and sync-notify steps are the single `_swap`/`_notify_sync` helpers both colors call — the
no-drift seam.

The async-subscriber dispatch rule (an async subscriber commits the handle to `reload_async`;
`reload()` refuses when one is live) is decided in ADR 0051.

### Consequences

**Positive:**
- Async services reload without parking the loop; the corrupting `run_in_executor` workaround is
  closed.
- `reload`/`reload_async` share `_swap`/`_notify_sync` — no twin, no drift.
- Concurrent re-fetch (via `load_async`'s `gather`) is delivered for free.

**Negative:**
- Holding the sync `ReentrancyGuard` across `await` keeps the reentry detector single-thread and
  single-task scoped. Accepted under the infrequent, deliberate reload contract (§9.2); a
  subscriber re-entering `reload_async` still fast-fails.
- `reload_async` runs sync subscribers inline, so a slow sync subscriber briefly blocks the loop.
  Accepted: same inline-subscriber trade-off as `reload()` (ADR 0018), and offloading would drop
  ContextVars (ADR 0013).

## Relationship to design_d §14.2 #3

Resolves the **reload** half of §14.2 #3: async reload ships. With ADR 0047 (fetch half),
§14.2 #3 is now fully resolved and annotated accordingly.
