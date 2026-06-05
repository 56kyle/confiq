---
status: accepted
date: 2026-06-05
supersedes: 0008
---
# Sync `load()` Rejects Async Sources; No Sync→Async Bridge

## Context and Problem Statement

ADR 0008 decided to bridge async sources in the sync `load()` path via a
single-worker `ThreadPoolExecutor` + `asyncio.run()`. The motivation was
transparent mixing: callers should not need to know whether their sources are
sync or async.

Design_d rejects that decision. The bridge introduces two correctness hazards:

1. **Event-loop hazard.** While the executor-thread approach avoids the
   `asyncio.run()` nested-loop `RuntimeError`, it still creates an interaction
   surface between the executor thread's loop and any `ContextVar`s, tasks, or
   framework state in the caller's environment.

2. **`ContextVar` propagation loss.** Python's `contextvars` module copies the
   calling context to a new thread, but mutations inside the executor thread do
   not propagate back. Any async source that reads or writes `ContextVar`s
   (common in async web frameworks for request-scoped state) will behave
   differently in the executor thread than in the caller's context.

The cleaner invariant: sync and async are separate entry points with a hard
boundary between them.

## Decision Drivers

- `ContextVar` mutations inside a worker thread do not propagate to the caller.
  Any async source that relies on context propagation will silently misbehave
  when run via an executor bridge.
- The bridge adds a thread per `load()` call that includes async sources. This
  is an invisible cost that callers cannot opt out of.
- The "transparency" argument in ADR 0008 assumed callers do not know or care
  whether their sources are async. In practice, a caller who adds an
  `AsyncSource` to a source list has already made a design decision; pointing
  them to `load_async()` is a clear, correct response.
- The clean separation — `load()` is sync, `load_async()` is async, they do
  not cross — is easier to reason about, test, and maintain.

## Considered Options

- **Option A: Raise `ConfiqError` if an `AsyncSource` is passed to `load()`**
  — clear error with a message pointing to `load_async()`.
- **Option B: `ThreadPoolExecutor(max_workers=1)` bridge (ADR 0008's choice)**
  — transparent but introduces `ContextVar` hazards.
- **Option C: `asyncio.run()` directly** — fails with `RuntimeError` when
  called from inside a running event loop.

## Decision Outcome

Chosen option: **Option A**, because the hazards of the executor bridge
outweigh the convenience of transparent mixing, and the corrective action
(use `load_async()`) is unambiguous and easy to apply.

### Behaviour

`load()` inspects the source list before fetching. If any element implements
`AsyncSource` (i.e., has `fetch_async` rather than `fetch`), it raises
immediately with a message like:

```
ConfiqError: AsyncSource 'my_source' was passed to load(); use load_async() instead.
```

`load_async()` accepts both `Source` and `AsyncSource` elements and drives them
correctly: async sources via `await fetch_async()`, sync sources inline.

### Consequences

- `load()` is a purely synchronous function with no threading or event-loop
  machinery. It can be called safely from anywhere — inside or outside a
  running event loop — with no hidden hazards.
- `load_async()` is the authoritative entry point for any source list that
  includes an async source. The two entry points are not interchangeable by
  design.
- Applications that discover at runtime whether their sources are sync or async
  must choose their entry point conditionally. This is an explicit, visible
  decision rather than a hidden executor thread.
- `ContextVar` semantics are correct in both paths: sync sources run in the
  caller's context; async sources in `load_async()` run on the caller's event
  loop with full context propagation.

## Pros and Cons of the Options

### Option A: Raise on async source in `load()` (chosen)

- Good, because `load()` carries zero event-loop or threading machinery.
- Good, because `ContextVar` semantics are correct — no cross-thread context
  copy that loses mutations.
- Good, because the error message directly names the fix.
- Neutral, because callers who mix source types must use `load_async()`.
  This is a one-word change and the correct call.

### Option B: ThreadPoolExecutor bridge (ADR 0008)

- Good, because callers need no knowledge of which sources are async.
- Bad, because `ContextVar` mutations in the executor thread do not propagate
  back to the caller — a silent correctness hazard.
- Bad, because one hidden thread is created per `load()` call with async
  sources. Callers cannot inspect or control this.
- Bad, because reasoning about thread interactions between the executor and
  the caller's event loop is subtle and framework-dependent.

### Option C: `asyncio.run()` directly

- Good, because it is the simplest implementation.
- Bad, because it raises `RuntimeError` when called from inside a running
  event loop, which is common in async web frameworks and async test harnesses.
