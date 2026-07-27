---
status: accepted
date: 2026-07-13
---
# Async Fetch Ships: `AsyncSource`/`load_async` In-Scope, Unbounded `gather`, No Thread Bridge

## Context and Problem Statement

design_d §14.2 #3 left async source support open, framed by ADR 0035 as a per-capability
problem-boundary question. Stage 6 fills the async entry points (`resolve_async`,
`load_async`), so the *fetch* half must be decided: does confiq's problem include the
async-native fetch shape, and if so, with what concurrency and threading semantics?

(The *reload* half of §14.2 #3 — `reload_async` — is decided separately at Stage 8; this ADR
covers async fetch only.)

The decision is made under the project's settled scoping discipline: there is no "v1 vs later"
— we scope to the problem's full *reasonable range* using the information on hand, because we
are the sole contributor and change only gets more expensive over time. Deferral is legitimate
only on a genuine information gap, and even then we build to *accommodate* the eventual
decision. "Ship it later once a first-party consumer appears" is the struck burden argument
(ADR 0035) wearing a schedule.

## Decision Drivers

- **Async-native fetch is within the problem's reasonable range.** confiq's identity is
  reconciling an *open, user-extensible* set of sources. Async-native I/O — an async secrets
  client, an async config service, an async HTTP backend — is a mainstream shape a config
  source takes in modern Python, not an exotic edge. Membership is decided by the shape being
  inside the problem, not by whether a *built-in* consumes it (ADR 0035: burden/"no consumer
  yet" is inadmissible).
- **The workarounds are defective, not merely inconvenient.** Awaiting an async fetch outside
  confiq and feeding the result through `MemorySource` *corrupts provenance* — the value's
  origin records as "memory", a defect against confiq's §1 provenance guarantee. Refusing async
  fetch does not remove the need; it forces a lossy workaround.
- **The architecture was already built for it.** The color-agnostic pipeline (§9.4, ADR 0035)
  exists precisely so async is a thin shell over the shared `_resolve_from_fetched` core, not a
  drift-prone twin. The `Source`/`SyncSource`/`AsyncSource` hierarchy and the
  `resolve_async`/`load_async` stubs already exist. Shipping is a near-free increment the Stage
  4 factoring pre-paid.
- **Honest colors (ADR 0013).** No `to_thread` bridge in either direction: it silently drops
  ContextVars (request-scoped state), the exact hazard ADR 0013 rejected for sync→async.

## Considered Options

### Whether to ship async fetch
- **Option A (chosen): ship** `AsyncSource` + `load_async` + `resolve_async`.
- **Option B: defer**, keep only `load()`'s async-rejection guard. Rejected: the sole argument
  for it — "no built-in needs it yet" — is the struck burden argument; the shape is in-range and
  the information to build it correctly is on hand.

### Concurrency of async fetch
- **Option A (chosen): unbounded `asyncio.gather`.** Concurrency bounding is the source's or
  client's responsibility.
- **Option B: a `max_concurrency` knob** on `ResolutionSpec` + a `Semaphore` in the fetch seam.
  Rejected (analysis below).

### Async built-in sources
- **Not shipped** — as a correctness call, not a deferral. Wrapping a sync-first SDK in
  `async def fetch_async` asserts a property the implementation lacks (false structure,
  ADR 0035). The extension point is provided; built-ins that do not do async I/O do not pretend
  to. A genuinely-async built-in (e.g. a remote `FileSource` over fsspec's `AsyncFileSystem`)
  will implement `AsyncSource` honestly when built; the protocol is already there to receive it.

## Decision Outcome

`resolve_async` and `load_async` ship as thin shells over the shared color-agnostic core.
`resolve_async` filters by profile, fetches, then runs the identical `_resolve_from_fetched`
that `resolve()` runs — fetch is the only color-bearing difference. In the fetch step
(`_fetch_all_async`): each source is fetched by its own color (`AsyncSource` awaited, preferred
when a source implements both; `SyncSource` run **inline**), and all are gathered with
**unbounded `asyncio.gather`**, which preserves list order so merge precedence is unaffected by
which sources are async. `load_async` builds its spec through the same `_spec_from_args` that
`load()` uses (a shared, drift-proof dispatch) and delegates to `resolve_async`; unlike
`load()`, it accepts async sources. No `to_thread` in either direction.

### Why no concurrency knob

Worked against the project's own test ("legitimate-but-uncommon *and completely blocking* →
we'd need a very high cost to refuse"):

- **Not blocking.** Concurrency bounding has a natural, idiomatic home one layer below `gather`:
  a shared client/connector cap (`aiohttp.TCPConnector(limit=N)`, an async pool `max_size`) —
  which is how async concurrency is bounded in Python anyway, for connection reuse — or a shared
  `asyncio.Semaphore` acquired inside `fetch_async`, or a ~5-line wrapper source for third-party
  sources the user cannot modify. The user is never blocked.
- **Correct location.** A confiq-level knob would bound only the *outermost* source fan-out and
  leave concurrency *inside* a source untouched — a leaky abstraction. The bound belongs at the
  resource contract (the source/client), where the real backend limit lives.
- **Uncommon.** Config loads pull from a small fixed source list (~2–6); the many-async-sources-
  against-one-limited-backend case is rare, and even then the client cap is the right tool.
- **Cost pulls the wrong way.** A knob pollutes the *hub* — `ResolutionSpec` is shared with sync
  `load()`, so the field would be meaningless on one of its two consumers — and adds a `Semaphore`
  to the one seam kept deliberately minimal.
- **Accommodated, not walled off.** Unbounded `gather` locks in nothing: adding `max_concurrency`
  later is a purely additive optional `ResolutionSpec` field defaulting to unbounded, a
  same-shaped edit whether done now or later. The accommodation shipped now is the documented
  semaphore-wrapper recipe, not code.

### Consequences

**Positive:**
- Async-native sources have an honest path that preserves provenance; the corrupting workaround
  is closed.
- Sync and async share `_resolve_from_fetched` and `_spec_from_args` — no twin, no drift (§9.4).
- Concurrent fetch (`gather`) is the real async win, delivered without a threading bridge.

**Negative:**
- `load_async` runs sync sources inline, so a slow sync source briefly blocks the loop. Accepted:
  at `load_async`'s startup-shaped context this is fine, and the alternative (`to_thread`) is
  false async that drops ContextVars (ADR 0013). The under-traffic version of this concern is a
  *reload* matter (Stage 8), handled there.
- Unbounded `gather` fans out N async fetches at once. Accepted: N is small and bounding belongs
  at the source/client; a knob is additive if ever needed.

## Relationship to design_d §14.2 #3

Resolves the **fetch** half of §14.2 #3: async fetch ships. The reload half (`reload_async`)
remains for Stage 8. §14.2 #3 is annotated accordingly.
