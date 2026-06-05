---
status: accepted
date: 2026-06-05
supersedes: 0005
---
# `ConfigHandle.on_reload` Uses Blinker-Style Signals with Sync and Async Subscriber Support

## Context and Problem Statement

ADR 0005 deferred async subscriber support to "v1.1" on the grounds that
dispatching async callbacks requires taking a position on event-loop ownership,
and that position was premature without real usage patterns. The design_d
revision revisits this deferral with a concrete mechanism that solves the
loop-ownership problem without locking confiq to a specific async framework.

The problem `on_reload` solves: subscribers registered on a `ConfigHandle` must
be notified after each successful reload with access to both the old and new
config values. The notification mechanism must be memory-safe (a subscriber
should not prevent garbage collection of the handler object), and it must
support async subscribers in a way that works from both sync `reload()` and
async `reload_async()`.

## Decision Drivers

- Weak-referenced subscribers: a handler object that holds a `ConfigHandle`
  subscriber should not be kept alive by that subscription. Python's
  `weakref.WeakMethod` pattern — popularised by Django signals and the blinker
  library — solves this.
- `reload_async()` has a running event loop available; async subscribers can be
  gathered and awaited directly.
- `reload()` does not have a running event loop. Async subscribers registered on
  a handle driven only by sync `reload()` must be scheduled via a loop reference
  supplied at `ConfigHandle.create()` time.
- No subscriber may call `reload()` synchronously — this must be detected and
  fast-failed by the `ReentrancyGuard`.

## Considered Options

- **Option A: Blinker signals, sync and async subscribers, `loop` parameter at
  `create()`** — `on_reload` is modeled on a blinker signal. Weak-referenced
  by default. Sync subscribers run inline (from daemon thread after the swap).
  Async subscribers are gathered on the running loop from `reload_async()`, or
  scheduled via `loop.call_soon_threadsafe` from `reload()` if `loop` was
  provided at create time.
- **Option B: Sync only, with manual bridge (ADR 0005's choice)** — `on_reload`
  accepts only `Callable[[T, T], None]`; async callers write the bridge
  themselves.
- **Option C: Async only** — requires the entire `ConfigHandle` lifecycle to be
  async; breaks sync callers.

## Decision Outcome

Chosen option: **Option A**, because the `loop` parameter at `create()` time
solves the event-loop ownership problem cleanly — the caller supplies the loop
once, not per-subscriber — and blinker's weak-reference semantics prevent the
common mistake of keeping handler objects alive indefinitely via subscription.

### API shape

```python
class ConfigHandle(Generic[T]):
    @classmethod
    def create(
        cls,
        schema: type[T],
        sources: Sequence[Source | AsyncSource],
        *,
        loop: AbstractEventLoop | None = None,
        plugins: list[object] | None = None,
    ) -> "ConfigHandle[T]": ...

    def on_reload(
        self, fn: Callable[[T, T], Any]
    ) -> Callable[[], None]: ...
        # fn receives (old, new); returns a disconnect callable
```

- `fn` may be a plain callable or a coroutine function. confiq detects via
  `asyncio.iscoroutinefunction`.
- The disconnect callable returned by `on_reload` removes the subscription.
  Returning the callable (rather than `fn` itself) suits blinker's weak-ref
  model, where the subscription handle is distinct from the subscriber.

### Dispatch rules

| Reload entry point | Sync subscriber | Async subscriber |
|---|---|---|
| `reload_async()` | run inline after swap | gathered and awaited on running loop |
| `reload()` | run on daemon thread after swap | `loop.call_soon_threadsafe(...)` if `loop` provided; raises if not |

### Consequences

- Subscribers are weak-referenced. A method subscriber on an object that has
  no other references will silently stop firing when the object is collected.
  This is the correct behaviour: a dead observer should not keep firing.
- `loop` is supplied once at `create()` time. Applications running inside an
  async framework pass the framework's running loop; sync-only applications
  omit `loop` and cannot register async subscribers (an error is raised at
  registration time if attempted without a `loop`).
- `on_reload` returns a disconnect callable. Callers who want to unsubscribe
  hold the return value; callers who never unsubscribe can discard it.
- No subscriber may call `reload()` synchronously. `ReentrancyGuard` detects
  this and raises immediately.

## Pros and Cons of the Options

### Option A: Blinker-style with `loop` at `create()` (chosen)

- Good, because weak references prevent accidental object lifetime extension
  via subscription — a common, hard-to-debug memory pattern.
- Good, because the loop-ownership question is answered once at `create()` time,
  not per-subscriber or per-call.
- Good, because `reload_async()` can gather and await async subscribers
  directly, with no thread hand-off required.
- Neutral, because sync-only handles that want async subscribers must provide
  `loop` at `create()` — one extra argument that makes the dependency explicit.

### Option B: Sync only (ADR 0005)

- Good, because no event-loop ownership decision is made by confiq.
- Bad, because async-framework callers must write `loop.call_soon_threadsafe`
  boilerplate in every subscriber that wants to trigger async work.
- Bad, because the manual bridge is error-prone — stale loop references,
  forgotten `ensure_future` wrappers.

### Option C: Async only

- Good, because the dispatch model is uniform.
- Bad, because it forces sync callers into an async `ConfigHandle` lifecycle
  with no benefit.
