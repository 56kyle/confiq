---
status: accepted
date: 2026-06-06
supersedes: "0012"
amended-by: "0051"
---
# ConfigHandle Constructor Revision: Spec-Only, No Loop, Inline Subscribers

> **Amended by ADR 0051** on three points reconciled when `ConfigHandle` was implemented at
> Stage 8: `reload()`/`reload_async()` return `-> T` (not `-> None`); the frozen-schema
> rejection raises `SchemaError` (not `ValueError`); and the async-subscriber refusal moves from
> registration time (an unknowable condition) to a `reload()`-time `RuntimeError`. The
> constructor shape below (spec-only, no loop, inline sync subscribers, `[reload]` extra,
> construction-time frozen enforcement) stands unchanged.

## Context and Problem Statement

design_d §8.2, §9.3, §12.4.

ADR 0012 chose a `ConfigHandle.create()` classmethod that accepted a `loop`
parameter so that async subscribers could be scheduled via
`loop.call_soon_threadsafe` when driven by sync `reload()`. Sync subscribers
ran on a daemon thread after the swap.

Three issues emerged with that design:

1. **The `loop` parameter races.** In frameworks like FastAPI / asyncio, the
   event loop is created at application startup — after module-level code runs.
   Passing the loop to the handle at construction time requires the caller to
   ensure the loop exists at that moment, which is not always controllable.

2. **The daemon thread is unnecessary.** Reload is a deliberate, infrequent
   operation — not a hot path. Running sync subscribers inline in the caller's
   thread is simpler and produces a more predictable call stack with no
   observable difference in practice.

3. **Blinker in core.** ADR 0012's chosen option pulled `blinker` into the core
   dependency list. Every user — including those who only ever call `load()`
   once — installs a library they never use.

Additionally, with `ResolutionSpec` now the shared load surface (ADR 0017),
the `create()` classmethod shape is redundant: `ConfigHandle(spec)` is the
natural constructor, matching `load(spec)`.

## Decision Drivers

- Reload subscribers run inline: simpler, easier to test, no daemon thread to
  reason about.
- Async subscribers are dispatched unambiguously by `reload_async()` on its
  running loop. There is no ambiguous "async subscriber, sync entry point" case
  to bridge.
- A caller who registers an async subscriber on a handle they only ever drive
  with sync `reload()` has made a usage error. Failing clearly at registration
  time is better than failing silently or requiring a `loop` parameter to paper
  over it.
- Blinker, `ConfigHandle`, and all reload notification machinery belong behind
  `confiq[reload]`, not in the core. Load-once users pay for nothing they do
  not use.
- The frozen-schema requirement — which underpins the lock-free-read guarantee
  (§9.1) — should be enforced at construction time, not documented as a caller
  responsibility.

## Considered Options

- **Option A (ADR 0012):** `create()` classmethod; `loop` parameter; async
  subscribers scheduled via `loop.call_soon_threadsafe` from sync `reload()`;
  sync subscribers on a daemon thread.
- **Option B (this ADR):** `__init__(spec)` directly; no `loop`; sync
  subscribers inline in caller's thread; async subscriber on a sync-only handle
  is a usage error at registration time; reload machinery behind `[reload]`
  extra.
- **Option C: Async-only `ConfigHandle`** — `reload_async()` only; no sync
  `reload()`.

## Decision Outcome

Chosen option: **Option B**.

### API shape

```python
class ConfigHandle(Generic[T]):
    def __init__(self, spec: ResolutionSpec[T]) -> None: ...
        # raises ValueError if spec.schema is not a frozen type

    @property
    def current(self) -> T: ...

    def reload(self) -> None: ...
    async def reload_async(self) -> None: ...

    def on_reload(self, fn: Callable[[T, T], Any]) -> Callable[[], None]: ...
        # fn may be sync or async; async fn raises at registration time if
        # only sync reload() will be used
```

### Dispatch rules

| Entry point | Sync subscriber | Async subscriber |
|---|---|---|
| `reload()` | inline, caller's thread | usage error at `on_reload()` call |
| `reload_async()` | inline after swap | gathered and awaited, running loop |

`ReentrancyGuard` fast-fails any subscriber that calls `reload()` synchronously.

### Frozen-schema requirement

`ConfigHandle.__init__` rejects a non-frozen schema. Its lock-free-read
guarantee — `current` is a single atomic attribute read with no torn-read hazard
under CPython — holds only when every snapshot is immutable. Enforcement at
construction time surfaces the contract violation immediately rather than
silently offering a guarantee the handle cannot keep. Plain `load()` still
accepts non-frozen schemas per the ADR 0014 gradient; only the live,
shared-snapshot path is constrained.

### The `[reload]` extra

`ConfigHandle`, `blinker`, and all reload notification machinery are distributed
as `confiq[reload]`. The core runtime depends only on `pydantic` (≥2) and
`pluggy`. A user who only calls `load()` installs neither `blinker` nor any
reload infrastructure. This corrects ADR 0012's treatment of `blinker` as a
mandatory core dependency.

### Consequences

**Positive:**
- No `loop` parameter to manage. No loop-existence race at construction time.
- Sync subscribers run inline: straightforward call stack, easy to observe in
  tests.
- Async subscriber on a sync-only handle fails at `on_reload()` time with a
  clear error, not silently at dispatch time.
- Blinker moves to `[reload]` extra; load-once users carry no reload dependency.
- `ConfigHandle(spec)` constructor mirrors `load(spec)`; the `create()`
  classmethod is removed.

**Negative:**
- Callers who relied on async subscriber support from sync `reload()` must
  restructure — switch to `reload_async()` or convert their subscriber to sync.
  This breaks the provisional ADR 0012 API; no shipped code is affected.
- Sync subscribers no longer run on a daemon thread. Any call site that relied
  on the subscriber executing off the reload caller's thread must add its own
  threading if that property is required.

## Pros and Cons of the Options

### Option A: `create()` with `loop` (ADR 0012)

- Good, because async subscribers work from sync `reload()` — no restructuring
  required.
- Bad, because `loop` at construction time races with framework startup and is
  awkward to supply when the framework hides its loop.
- Bad, because sync subscribers on a daemon thread add scheduling indirection
  and complicate test observability.
- Bad, because `blinker` in core increases the mandatory install for all users.

### Option B: `__init__(spec)`, inline subscribers (this ADR)

- Good, because no loop management.
- Good, because inline subscribers produce a predictable, testable call stack.
- Good, because the core dependency surface shrinks.
- Neutral, because callers who need async-from-sync must use `reload_async()`
  or convert to sync subscribers. This is an explicit trade-off, not a
  regression in capability.

### Option C: Async-only

- Good, because dispatch is uniform across subscriber kinds.
- Bad, because sync callers are forced into an async `ConfigHandle` lifecycle
  with no benefit.
