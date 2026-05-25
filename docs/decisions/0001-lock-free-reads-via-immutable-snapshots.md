---
status: accepted
date: 2026-05-25
decision-makers: [Kyle Oliver]
consulted: []
informed: []
---
# Lock-free reads via immutable snapshots and atomic reference swap

## Context and Problem Statement

`confiq` exposes a single global `config` object. `config.get(...)` is on the hot path — called in request handlers, tight loops, and coroutines. It must be safe from concurrent writes (bind, reload, add_source) without penalising the far more frequent reads.

The naive solution is a reader-writer lock. The question is whether the cost is justified.

## Decision Drivers

* `config.get()` is expected to be called orders of magnitude more often than writes (reload, bind, add_source).
* Reads must be safe under concurrent writes without blocking.
* Deadlocks during reload (a subscriber re-entering the write path) must be loud, not silent hangs.
* The implementation must behave correctly on CPython today; free-threaded builds (PEP 703) are a future concern to audit but not a blocker.

## Considered Options

* **Immutable snapshot + atomic reference swap** (chosen)
* **`threading.RLock` on the hot read path**
* **`readerwriterlock` RWLock** (Éric Larivière's `elarivie/pyReaderWriterLock`)

## Decision Outcome

Chosen option: "Immutable snapshot + atomic reference swap", because it makes reads entirely lock-free at the cost of a slightly heavier write path, which is the right trade for this workload.

`ConfigSnapshot` is a `@dataclass(frozen=True, slots=True)`. A write acquires `threading.Lock`, builds a new snapshot under the lock, then publishes via a single `STORE_ATTR` on `Config._current`. Readers do one `LOAD_ATTR`. The GIL serialises individual bytecodes on CPython, so the reference swap is atomic without an explicit lock.

A non-reentrant `threading.Lock` (not `RLock`) is paired with a `ReentrancyGuard` (`threading.local` fast-fail) so that a hookimpl that attempts to re-enter the write path raises immediately — the same pattern loguru uses in `loguru/_handler.py` — rather than deadlocking.

### Consequences

* Good, because `config.get()` has zero lock overhead.
* Good, because deadlocks are surfaced loudly (RuntimeError) rather than silently hanging.
* Good, because frozen snapshots are safe to share across threads and asyncio tasks without copying.
* Bad, because a single-field update requires building and publishing a full new snapshot. Mitigated by `config.patch(model)`.
* Bad, because the atomicity argument relies on the GIL. A free-threaded Python build (PEP 703, optional in 3.13+) still makes the reference swap safe (single reference stores are atomic per the Python data model), but the broader assumption that other bytecodes are atomic loosens. A free-threading audit is deferred to v1.1.

## Pros and Cons of the Options

### Immutable snapshot + atomic reference swap

* Good, because reads are lock-free — a single attribute load.
* Good, because the snapshot is fully constructed before publication; readers never see a partially-built value.
* Good, because the pattern mirrors Python's own `logging` module (per the Real Python logging source walkthrough), which protects configuration mutation with a lock but not the hot log call.
* Bad, because writes pay more: sort sources, call `before_load` hooks, load all sources, merge, validate, call `before_publish` hooks — all under the lock. Acceptable for a workload where writes are rare.

### `threading.RLock` on the hot read path

* Good, because implementation is straightforward and familiar.
* Bad, because every `config.get()` call acquires and releases a lock, adding overhead to the hot path even when there is no contention.
* Bad, because `RLock` allows the same thread to re-acquire, which hides the bug we want to surface (a hookimpl re-entering the write lock during reload).

### `readerwriterlock` RWLock

* Good, because it allows multiple concurrent readers with exclusive writes.
* Bad, because Éric Larivière's own README notes a theoretical ~20% performance penalty for downgradable classes. For a path that only loads one attribute, even an uncontended reader lock acquisition is wasted work.
* Bad, because adding an external dependency for a problem the atomic-swap pattern already solves at zero cost is not justified.