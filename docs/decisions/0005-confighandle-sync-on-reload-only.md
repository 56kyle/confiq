---
status: accepted
date: 2026-05-29
---
# `ConfigHandle.on_reload` Accepts Sync Callables Only in v1

## Context and Problem Statement

`ConfigHandle.on_reload` registers subscriber functions that are called after a
successful `reload()` or `reload_async()` completes. Subscribers receive `(old: T,
new: T)` and are dispatched on a daemon thread outside the write lock.

Some callers will use confiq inside async frameworks (asyncio, trio, uvloop) and
may want to schedule async work in response to a reload — for example, pushing
the new config into a running coroutine or signalling an asyncio `Event`. The
question is whether `on_reload` should accept async callables in v1 or defer
that to a later version.

## Decision Drivers

- Async callbacks require a reference to a running event loop. The correct loop
  reference varies by framework — asyncio's default loop, trio's loop, a uvloop
  instance — and confiq has no opinion on which framework the caller uses.
- First-class async subscriber support would require confiq to either own a loop
  reference (tying it to a specific framework) or accept one at subscription time
  (introducing a per-subscriber parameter that has no sync analogue).
- The sync-to-async bridge for users who need it today is straightforward and
  well-documented: call `loop.call_soon_threadsafe(asyncio.ensure_future, coro)`
  inside a sync subscriber. This pushes the framework coupling to the caller,
  where it belongs.
- Locking in an async callback API before the sync surface has real-world usage
  means designing for an unknown pattern.

## Considered Options

- **Option A: Sync callables only in v1; async deferred to v1.1** — `on_reload`
  accepts `Callable[[T, T], None]`; async users bridge manually.
- **Option B: Async callables accepted alongside sync in v1** — `on_reload`
  detects whether `fn` is a coroutine function and schedules it via a stored
  loop reference.

## Decision Outcome

Chosen option: "Option A: Sync callables only in v1; async deferred to v1.1",
because async callback dispatch requires confiq to take a position on event-loop
ownership that is premature before real usage patterns are known. The manual
bridge is a single line and the coupling it expresses belongs at the call site.

### Consequences

- `on_reload` type signature is `Callable[[T, T], None]` — no `Coroutine` or
  `Awaitable` variant.
- Callers who need async notification in v1 use the sync bridge:
  ```python
  loop = asyncio.get_event_loop()

  @handle.on_reload
  def _notify_async(old: Settings, new: Settings) -> None:
      loop.call_soon_threadsafe(asyncio.ensure_future, _async_handler(old, new))
  ```
  This pattern is documented in the `ConfigHandle` reference.
- The v1.1 async callback surface will be designed with real usage patterns as
  input rather than speculative API design.

## Pros and Cons of the Options

### Option A: Sync Callables Only in v1

- Good, because confiq carries no opinion on which event loop framework the
  caller uses — asyncio, trio, and uvloop all work identically from confiq's
  perspective.
- Good, because the sync bridge pattern is short, explicit, and idiomatic for
  thread-to-async handoff.
- Good, because the v1.1 design can be informed by actual user feedback rather
  than speculation.
- Neutral, because callers who need async notification must write one extra line.
  The extra line makes the event-loop coupling explicit, which is arguably better
  than confiq hiding it.

### Option B: Async Callables in v1

- Good, because async-first callers get a cleaner registration surface without
  manual bridging.
- Bad, because confiq must store a loop reference — either taken at `create()`
  time, at `on_reload()` registration time, or obtained via
  `asyncio.get_event_loop()` at dispatch time. Each choice has a failure mode
  (stale reference, wrong loop, deprecation warning in Python 3.10+).
- Bad, because trio and uvloop do not use `asyncio.get_event_loop()`, making a
  universal async dispatch implementation non-trivial to get right.
- Bad, because the design locks in a loop-coupling decision before usage patterns
  justify the commitment.
