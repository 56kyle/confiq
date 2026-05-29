# `confiq` Design C — Open Question Analysis

Pro/con analysis for the five open questions from `docs/design_c.md` §12.

---

## Q1 — Should `load()` accept a `prefix` shortcut for auto-discovery?

`load(Settings, prefix="MYAPP_")` vs. always requiring `sources=[...]`

**Pros of the shortcut**
- Zero boilerplate for the 90% case (file + env + no CLI). Better first impression.
- Makes confiq competitive with pydantic-settings on "time to hello world."
- The twelve-factor pattern is so common it arguably deserves first-class expression.
- Reduces the "scary wall of imports" in getting-started docs.

**Cons of the shortcut**
- Directly contradicts principle 2.4 ("precedence is data, not magic"). The implicit source list and its discovery order become a hidden convention.
- Debugging gets harder: "why is it reading this value?" has a non-obvious answer when sources aren't visible at the call site.
- Discovery rules need to be specified and stable: which files? which directory? what order? These become forever-commitments.
- Test isolation is at risk if `load(Settings, prefix="MYAPP_")` silently reads whatever is in the environment at test time.
- If someone adds a `config.yaml` to their project later, behavior changes without a code change.

**Better alternative:** a `confiq.helpers` convenience function (`from_env_and_file(schema, prefix, path)`) that constructs the explicit source list and hands it to `load()`. The user sees the sources — no magic in `load()` itself.

---

## Q2 — Should `confiq.context.patch()` double as a pytest fixture?

Should `confiq` ship a `confiq_patch` fixture alongside the context manager?

**Pros of a pytest fixture**
- Reduces boilerplate in suites that use `patch()` pervasively — fixture injection is cleaner than a `with` block on every test.
- Fixture scoping (function / class / module / session) gives more control than the context manager.
- Other testing utilities (freezegun, respx, time-machine) ship pytest fixtures alongside their context managers — it is an expected pattern.
- Autouse is possible for suites that want a global isolation guarantee.

**Cons of a pytest fixture**
- Introduces pytest as a dependency on `confiq.context`, or forces a separate `confiq.pytest` subpackage — either adds structural complexity.
- The primary test story is `MemorySource` + fresh `load()` per test — that pattern never needs `patch()` at all. The fixture would serve a secondary use case.
- `def test_x(confiq_patch):` is implicit in a way `with patch(config, ...)` is not — you have to know the fixture exists and what it does.
- Fixture injection semantics differ subtly from context manager semantics in edge cases (exception propagation, early exit).

**Leaning:** Ship only the context manager in v1. A `pytest-confiq` package (a proper pytest plugin, separate from `confiq` itself) is a planned post-v1 deliverable — not contingent on user demand. The fixture is a convenience on top of something that already works, so it does not belong in the v1 scope, but it will ship.

---

## Q3 — Should `ConfigHandle.on_reload` support async callbacks in v1?

`handle.on_reload_async(async_fn)` vs. documenting `loop.call_soon_threadsafe()` as the bridge.

**Pros of first-class async callbacks**
- FastAPI / Starlette / asyncio-heavy apps will want async reload hooks — the sync daemon thread is an awkward seam.
- Avoids users copying a non-obvious `loop.call_soon_threadsafe()` pattern from the docs and getting it wrong.
- If the motivation for `ConfigHandle` is async-first usage, stopping at sync subscribers is inconsistent.
- The pattern is well-established: `watchfiles`, `starlette`, and others accept async callbacks and schedule them via a known loop.

**Cons of first-class async callbacks**
- confiq must own or accept a loop reference. `asyncio.get_running_loop()` only works from within a running loop; `asyncio.get_event_loop()` is deprecated in 3.10+. There is no clean way to get the loop from a sync reload trigger without the user handing it over.
- Accepting a `loop` argument on `ConfigHandle.create()` ties a handle to one event loop for its lifetime — a significant design commitment.
- Adds an async/sync impedance mismatch: `reload()` is sync, but it would need to schedule coroutines onto an external loop. The interaction with `reload_async()` doubles the combinations.
- Can be added cleanly in v1.1 once the sync surface is stable and user demand is known. The cost of waiting is low.

**Leaning:** Defer to v1.1. Document `loop.call_soon_threadsafe(asyncio.ensure_future, coro, loop)` as the v1 bridge. The cost is verbosity in a niche case; the benefit is a simpler v1 surface.

---

## Q4 — Should free-threaded CPython (PEP 703) support be a v1 requirement?

Audit and guarantee correctness on no-GIL builds before shipping v1, vs. treat it as a post-v1 item.

**Pros of auditing in v1**
- 3.13 ships free-threaded builds as an opt-in today; 3.14 makes them more prominent. Design now, not later.
- The risk surface is narrow — only the dict-merge path needs attention. A targeted lock there is a small, backward-compatible change.
- A concurrent configuration library that silently has a data race in the merge path on no-GIL is an embarrassing failure mode given the library's thread-safety claims.
- If the fix is one lock around one code path, the cost is low.

**Cons of auditing in v1**
- No-GIL builds are still opt-in and experimental. The real-world user population running confiq on `--enable-experimental-free-threading` is effectively zero today.
- A rushed audit risks introducing subtle bugs in the common GIL path while trying to fix the no-GIL path.
- The atomic-swap for the reference (`self._current = new_snap`) is still safe under no-GIL per the Python data model. The risk is narrowly in `deep_merge` when a source mutates a shared dict concurrently — an unusual scenario that requires user-side misbehavior to trigger.
- Declaring support is a commitment: any future regression in no-GIL behavior becomes a bug report.

**Leaning:** Not a v1 blocker, but perform the audit before declaring no-GIL compatibility. The fix is small; the right moment is when 3.14 stabilizes the no-GIL build guarantee.

---

## Q5 — `ConfigField.sources` violation: hard error or warning?

When `sources=("env",)` and a `FileSource` tries to set the field, what happens?

**Pros of hard error (`ConflictingSourceError`)**
- Consistent with principle 2.3 ("fail loudly at the boundary"). If you declared a restriction, violating it should be loud.
- For `secret=True` fields specifically, a hard error is the only correct behavior — silently ignoring a leaked secret in a file creates a false sense of security.
- Explicit contract: the restriction either works or it tells you it is being violated.
- Easier to audit: "did my source restriction actually fire?" has a clear yes/no answer.

**Cons of hard error**
- Breaks migration: teams adding `ConfigField` annotations to existing configs may have secrets in files during a transition period. A hard error forces a big-bang migration.
- Dev/test environments that have `DB_PASSWORD` in `config.local.yaml` for convenience will hard-fail even when no security intent was present.
- Makes adoption more painful for teams with complex legacy configs.
- `strict=False` mitigates this, but requires the user to know to pass it.

**Pros of warning + skip**
- Non-breaking during migration. Teams get the warning, then fix the config file at their own pace.
- The security guarantee still holds: the restricted value is not used regardless. A warning is honest about what happened.
- Matches Python's cultural norm — `DeprecationWarning` and `RuntimeWarning` exist precisely for "this is wrong but we will let you through."

**Cons of warning + skip**
- Warnings are easy to miss in production. A suppressed warning means a team may never know their source restriction is not working.
- Silent skip on a `secret=True` field means a misconfigured environment (missing the required env var) silently falls through to a default or raises `MissingConfigError` from an unrelated path — harder to diagnose.

**Leaning:** Split the behavior by `secret`:
- `secret=True` → always hard error. Source restriction on a secret is a security boundary, not a style preference.
- `secret=False` → warning + skip when `strict=False`, hard error when `strict=True` (the default). This lets teams migrate without a big bang while keeping the strict default for new codebases.