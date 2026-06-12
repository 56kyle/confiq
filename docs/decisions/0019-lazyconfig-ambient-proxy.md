---
status: accepted
date: 2026-06-06
---
# LazyConfig: Opt-In Lazy Ambient Proxy

> Amended by [ADR 0031](0031-lazyconfig-snapshot-overlay.md): the proxy's
> override-awareness is specified as a *snapshot overlay* — an active
> `context.override()` mapping is deep-merged over the bound base and validated into a
> fresh cached `T`, so nested access (`config.database.host`) sees overrides and every
> read stays typed. First-hop attribute substitution is rejected.

## Context and Problem Statement

design_d §8.3–8.4.

The value/accessor pattern is the default ambient-access story for confiq:
either a module-level `settings = load(Settings, sources=[...])` when no CLI
source is involved, or a `settings()` accessor function initialised in the
entry point when the CLI is a source. This pattern is maximally testable —
config is a plain value with no global identity.

Some applications, however, want a bare module-level name that (a) does not
require a function-call dereference at use sites and (b) is CLI-aware. The
accessor pattern satisfies (b) but not (a); the eager pattern satisfies (a) but
not (b). The gap is the motivation for a proxy.

The key constraint on any proxy design: `pytest-confiq`'s autouse isolation
(ADR 0016) works by installing a scoped `context.override()` ContextVar for
each test. If the proxy were cache-only — serving only the bound base value —
the ContextVar would not flow through it, and the plugin would need a separate
set/reset lifecycle for proxy-using code. That would be a second isolation
system for the same problem.

## Decision Drivers

- The proxy must be generic — `config` should be typed as `Settings`, not
  `Any` or `LazyConfig[Settings]`, at all call sites. No manual `cast`.
- Lifecycle controls (`bind`, `reset`, `bound`) must not shadow schema field
  names. A pydantic model with a field named `bind` is plausible.
- The proxy must be override-aware (consult `context.override()` on every
  access) so that `pytest-confiq`'s existing autouse fixture handles
  proxy-using code without proxy-specific set/reset machinery.
- The construct must be clearly opt-in and documented with its costs. The
  value/accessor path remains the recommended default.

## Considered Options

- **Option A: `LazyConfig[T]` — lifecycle controls on the handle, proxy via
  `handle.value`, override-aware.**
- **Option B: Lifecycle controls on the proxy, guarded by a reserved
  `__confiq__` dunder attribute** (`config.__confiq__.bind(...)`).
- **Option C: No proxy; document the accessor pattern only** (§8.3).

## Decision Outcome

Chosen option: **Option A**, because the handle/proxy split cleanly solves the
field-collision problem, and the override-aware design is what makes the testing
story coherent without a second isolation system.

### API shape

```python
class LazyConfig(Generic[T]):
    def __init__(self, spec_builder: Callable[..., ResolutionSpec[T]]) -> None: ...
    @property
    def value(self) -> T: ...        # the typed proxy; raises if not yet bound
    def bind(self, **kwargs) -> None: ...
    def reset(self) -> None: ...
    @property
    def bound(self) -> bool: ...
```

Typical usage:

```python
# myapp/config.py
config_handle = LazyConfig(settings_spec)   # lifecycle handle
config = config_handle.value                # proxy, typed Settings, for imports

# myapp/__main__.py
@app.callback()
def _bootstrap(...):
    config_handle.bind(cli=TyperSource())   # resolve once, post-parse

# anywhere
from myapp.config import config
host = config.database.host   # type-checked; CLI-aware after binding
```

### Why lifecycle controls on the handle, not the proxy

`value` forwards every attribute access to the wrapped config object. A method
named `bind` placed directly on the proxy would shadow any schema field also
named `bind`. Putting `bind`/`reset`/`bound` on the handle (`config_handle`)
gives them a clean, collision-free surface with no naming contortion.

### Why override-aware, not cache-only

On each access, `value` first checks the active `context.override()` ContextVar.
If an override is in scope it overlays it; otherwise it returns the bound base.
This is the same ContextVar path the non-proxy value path uses (ADR 0016), so
`pytest-confiq`'s existing autouse fixture handles proxy-using and non-proxy
code identically — no second isolation system is required.

`pytest-confiq`'s autouse fixture also calls `reset()` between tests, leaving
the proxy unbound by default. An accidental read of ambient `config` in a test
that did not establish one raises a clear "not bound" error rather than leaking
a production default.

### Named costs

These are documented as first-class trade-offs, not fine print:

1. **Raises before `bind()`** — any code that reads `config` before the app
   callback runs gets a clear `RuntimeError`. Mitigated by binding in the app
   callback, which runs before any command.
2. **No import-time dereference** — `from myapp.config import config; x =
   config.db_host` at module level (outside a function body) will raise. The
   proxy's "not bound" error is clear, but callers must be aware of the
   discipline.
3. **Identity edges** — `type(config) is Settings` is `False`; pickling and
   identity-dependent patterns are imperfect. `isinstance` works via
   `__class__` forwarding.
4. **ContextVar check on every access** — negligible in practice (the
   fast-path when no override is active is a single `ContextVar.get()` that
   returns the sentinel). Does not satisfy `ConfigHandle`'s lock-free-read
   guarantee (ADR 0018 §9.1); `LazyConfig` is therefore a sibling to
   `ConfigHandle`, not a subclass.

The value/accessor forms (§8.1, §8.3) remain the recommended, maximally-testable
defaults. `LazyConfig` is the ergonomic option for callers who accept the costs
above in exchange for a bare-name ambient import.

### Consequences

**Positive:**
- `from myapp.config import config` works as a static, typed ambient import
  after `bind()` runs.
- Override-aware design means `pytest-confiq` needs no proxy-specific fixture
  machinery. The same `context.override()` path covers both proxy and
  non-proxy code.
- `config_handle.value` returns the same stable proxy on every call; it can be
  imported and stored freely.

**Negative:**
- A proxy is an additional abstraction with the identity and pickling edge
  cases listed above. It is opt-in; non-proxy users are entirely unaffected.
- Two names (`config_handle` for lifecycle, `config` for use) appear in the
  app's config module. This is conventional (cf. `pytest-django`'s separation
  of test-client helpers from the settings object) but requires explanation in
  the project's own docs.

## Pros and Cons of the Options

### Option A: `LazyConfig[T]` with handle/proxy split (chosen)

- Good, because `bind`/`reset`/`bound` on the handle cannot shadow schema
  fields.
- Good, because the override-aware proxy unifies the testing story — no second
  isolation system.
- Good, because `LazyConfig` is generic in `T`; `value` and any re-exported
  alias are typed as the schema at all use sites, with no manual `cast`.
- Neutral, because two names appear in the app's config module. The split is
  explicit and the purpose of each name is clear.

### Option B: `__confiq__` dunder on the proxy

- Good, because a single name covers both access and lifecycle (`config.x`,
  `config.__confiq__.bind(...)`).
- Bad, because `__confiq__` has no precedent in Python's data model and reads
  as a framework internal rather than a first-class application control surface.
- Bad, because lifecycle discoverability drops: a reader of `config.database.host`
  does not know `config.__confiq__` exists without consulting the docs.

### Option C: Accessor pattern only (§8.3)

- Good, because no proxy surface, no identity or pickling edge cases.
- Bad, because the bare-name ambient import use case is not served. Applications
  that want it will write their own proxy, typically with less care and no
  testing integration.
