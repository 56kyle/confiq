---
status: accepted
date: 2026-05-30
---
# Bridge Async Sources in `load()` via a Single-Worker `ThreadPoolExecutor`

## Context and Problem Statement

confiq sources can implement either a synchronous `fetch()` or an asynchronous `fetch()`. The library
exposes two entry points: `load()` (sync) and `load_async()` (async). When a caller passes an async
source to `load()`, the sync path must drive the coroutine to completion. The question is how to do
that without breaking the caller's event loop or requiring them to use `load_async()`.

## Decision Drivers

- `load()` must remain usable from synchronous code that may or may not be inside an event loop.
- `asyncio.run()` called from a thread that is already running an event loop raises a `RuntimeError`.
  A `ThreadPoolExecutor` with `max_workers=1` creates a new thread that has no running loop, making
  `asyncio.run()` safe to call there.
- Requiring callers to use `load_async()` whenever any source is async is a leaky abstraction: callers
  should not need to know the internal fetch protocol of each source.
- Raising immediately if an async source is passed to `load()` would silently break callers who mix
  sync and async sources, and would remove the possibility of transparent mixing in the future.

## Considered Options

- **Option A: `asyncio.run()` directly in `_fetch_sources()`** — fails when called from inside a
  running event loop (e.g., in an async web framework handler that calls `load()` synchronously).
- **Option B: `ThreadPoolExecutor(max_workers=1)` + `asyncio.run()` in the worker** — the worker
  thread has no running loop, so `asyncio.run()` is always safe. The caller's event loop is not
  blocked.
- **Option C: Require callers to use `load_async()`** — shifts burden to callers; breaks transparent
  source mixing.

## Decision Outcome

Chosen option: "Option B: `ThreadPoolExecutor(max_workers=1)` + `asyncio.run()` in the worker",
because it keeps the public API coherent (sync callers need not reason about async sources) and avoids
the nested-event-loop pitfall of calling `asyncio.run()` directly.

### Consequences

- `_fetch_sources()` inspects the source list; if any source has an async `fetch()`, it submits
  `asyncio.run(_gather_async(sources))` to a single-worker executor and blocks until completion.
- The one-worker executor is created fresh per `load()` call; it is not a shared resource.
- This path adds one thread per `load()` call that mixes async sources. For applications where this
  is on the critical path, `load_async()` is the preferred entry point.
- If Python adds a standard `run_sync()` helper that works from within a running loop (analogous to
  Trio's `from_thread.run_sync`), this bridge can be simplified or removed at that point.

## Pros and Cons of the Options

### Option A: `asyncio.run()` directly

- Good, because it is the simplest implementation.
- Bad, because calling `asyncio.run()` from inside a running event loop raises `RuntimeError`. Any
  async web framework or test harness that calls `load()` synchronously would break.

### Option B: ThreadPoolExecutor bridge (chosen)

- Good, because the worker thread is guaranteed to have no running event loop, making `asyncio.run()`
  safe unconditionally.
- Good, because callers need no knowledge of whether their sources are sync or async.
- Neutral, because one extra thread is created per mixed-source `load()` call; acceptable for a
  configuration load that happens at startup or on reload.

### Option C: Raise if async source passed to `load()`

- Good, because the implementation of `load()` stays completely synchronous.
- Bad, because it leaks the fetch-protocol detail to callers and prevents transparent mixing of
  source types.
