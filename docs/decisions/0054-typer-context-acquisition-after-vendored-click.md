---
status: accepted
date: 2026-07-20
---
# `TyperSource` Acquires Its Context From Typer's Vendored Click, With a Fallback

## Context and Problem Statement

ADR 0032 built `ClickSource`/`TyperSource` on a premise it stated in one clause: `TyperSource`
"shares the mechanism since Typer's context is a Click context." Typer ran on Click, so
`click.get_current_context()` returned the live context in either framework, and `TyperSource` could
be three `ClassVar`s over an inherited constructor (ADR 0035: no drift between two sources whose
behavior is genuinely identical).

**Typer 0.26.0 falsified that premise deliberately.** It vendored Click — copying the source into a
private internal package, `typer._click` — and dropped click as a declared dependency, so Typer can
evolve independently. The vendored fork carries its own thread-local context stack. A Typer
invocation now pushes onto `typer._click.globals`, while the installed `click.globals` stack stays
empty. Under typer >= 0.26, `TyperSource()` inside a live Typer command raised confiq's branded
`RuntimeError` ("must be constructed inside an active Typer command invocation") — a hard failure of
a documented, tested path. Upstream is explicit that Click-specific interop is no longer supported.

Two properties of the break shape the response. First, it is invisible to any environment pinned
below typer 0.26: the repo's own `.venv` (typer 0.25.1) passed the integration test throughout,
while a fresh resolve (typer 0.27.0) failed it. Second, it is *narrow*: `typer._click.core.Context`
is not a `click.Context` subclass, but is structurally identical for everything the snapshot step
reads — `.params`, `.get_parameter_source(name).name`, `.command.params`, `.command.callback`. Only
context **acquisition** diverged; the capture mechanism did not.

## Decision Drivers

- ADR 0032's contract (eager snapshot, ambient grab confined to the constructor) is unaffected and
  must survive intact — this is a change of *where the context is found*, not of what is done with
  it.
- ADR 0035's no-drift sharing remains correct for capture; the divergence should be as small as the
  actual difference between the frameworks, and no smaller.
- confiq declares `typer>=0.15.4`. Both sides of the 0.26 boundary are in the supported range, and
  users do not choose their typer to suit us.
- The only route to the vendored stack is a private module. That coupling cannot be avoided, so it
  must be *contained and visible* rather than diffused.
- The failure mode must stay loud. A silently-empty binding set would be worse than the
  `RuntimeError` this replaces.

## Considered Options

- **Option A: Ordered provider list, vendored first, real click as fallback.**
- **Option B: Target `typer._click` only; raise the floor to `typer>=0.26`.**
- **Option C: Abandon ambient acquisition for Typer; require the user to pass typer's documented
  `ctx: typer.Context` callback parameter.**

## Decision Outcome

Chosen option: **Option A**. Each source class declares an ordered tuple of context-stack provider
modules; acquisition tries them in order and takes the first live context.

- `ClickSource._CONTEXT_STACK_PROVIDERS = ("click.globals",)`
- `TyperSource._CONTEXT_STACK_PROVIDERS = ("typer._click.globals", "click.globals")`

Three conditions mean "try the next provider" — the module is not importable, it has no
`get_current_context`, or that call raises `RuntimeError` because nothing is active. Any other
exception propagates. When every provider is exhausted, the branded `RuntimeError` is raised,
message unchanged.

The fallback is not defensive padding: for typer 0.15–0.25 the real click stack is *exactly* where a
Typer context lives, so the second entry is the pre-0.26 support path, and it is what makes the
declared version range honest. The ordering matters in only one direction — vendored first — because
under typer >= 0.26 both stacks can be live (a Typer command nested under click tooling), and the
framework the user named is the one whose invocation they meant.

**Terminus for the fallback entry.** `"click.globals"` in `TyperSource`'s tuple exists solely to
serve typer 0.15–0.25. It is removed when — and only when — the `[typer]` extra's floor moves to
`>=0.26`. Until then it is end-state, not a stepping stone with an unnamed horizon.

### Sub-decision: optional-dependency surfaces are typed structurally, not nominally

`click.Context`/`click.Parameter` were true annotations and are now lies under Typer, so the
snapshot helpers take narrow module-private `Protocol`s declaring only what they read. This is what
lets one capture path serve two unrelated `Context` lineages, and it is the honest type where a
nominal one would be false.

The cost is explicit: there is no `isinstance` guard (a `runtime_checkable` check here would be a
false assurance — it verifies attribute presence, not behaviour), so a single unchecked `cast` sits
at the dynamic-import boundary where the value is `Any` regardless, and the protocols could drift
against *two* upstreams without the type checker noticing. The runtime tests in both environments
are what actually cover that seam. Scope: this is the decision for this boundary, not yet a
project-wide policy — the other optional-dep boundaries (fsspec, boto3) keep nominal types because
they have exactly one upstream each. It generalizes if a second vendoring ever happens.

### Sub-decision: per-framework CLI extras, `cli` retained as an alias

`[cli]` is **split** into `click` and `typer`, with `cli` kept as an alias installing both, and the
branded install hints now name `confiq[click]` / `confiq[typer]`. Vendoring made the frameworks
genuinely independent — a Typer user has no reason to install click.

The alias is **permanent, with no removal date**: it costs one line of metadata, and dropping it
would break every existing `pip install confiq[cli]` to buy nothing. Recorded here so its retention
reads as a decision rather than an oversight.

### Consequences

**Positive:**
- The supported typer range works end to end, on both sides of the vendoring boundary, with one
  declarative line of divergence per class.
- ADR 0032's snapshot contract and ADR 0035's shared mechanism are preserved; the fix is contained
  to acquisition, matching the size of the upstream change.
- The extras now describe reality: two independent frameworks, separately installable.
- A future framework with its own context stack is a one-tuple addition.

**Negative:**
- confiq depends on `typer._click.globals`, a private module upstream may move or rename without
  notice. Contained to one `ClassVar` and marked with an external-constraint comment. A clean
  rename degrades to the branded `RuntimeError` — never to silently-empty bindings — while a
  module that exists but fails to import propagates its own `ImportError` untouched, because
  fallthrough is restricted to a `ModuleNotFoundError` naming the requested module itself. The nox
  session resolves dependencies unpinned, so CI meets such a change as a failing test rather than
  as a user's bug report.
- The vendored-over-real-click *preference order* is not pinned **behaviourally**. Exercising it
  requires two live context stacks at once, which is only fabricable by faking
  `typer._click.globals` in `sys.modules` — a mock of the exact boundary under test, and thus
  worthless as evidence. What is pinned instead: every `_context_from` outcome against real modules,
  fallthrough past an unavailable module, the end-to-end Typer invocation under whichever typer is
  installed, and a direct literal assertion on `TyperSource._CONTEXT_STACK_MODULES` — literal by
  intent, because the ordering and the exact private path *are* the fix, so a reorder or a
  well-meaning cleanup of the private coupling fails loudly. Stated rather than papered over.
- Two extras where there was one, plus an alias, is more surface to document.

## Pros and Cons of the Options

### Option A: Ordered provider list (chosen)

- Good, because the whole declared typer range works, with the divergence proportional to the
  real difference between the frameworks.
- Good, because it generalizes to any future vendoring without touching the capture path.
- Bad, because it carries a private-module dependency and a branch that only one side of the typer
  boundary exercises in any given environment.

### Option B: Vendored only, floor at `typer>=0.26`

- Good, because it is a single code path with no fallback branch to reason about.
- Bad, because it drops working support for typer 0.15–0.25 to avoid one tuple entry — trading
  users' working installs for our tidiness.
- Bad, because the private-module coupling remains regardless; the floor bump buys no safety.

### Option C: Require an explicit `ctx: typer.Context` parameter

- Good, because it uses only public, documented Typer API and cannot break on vendoring at all.
- Good, because it is more explicit, which the rest of confiq's ethos favors.
- Bad, because it breaks ADR 0032's contract and the published `TyperSource()` signature, making a
  dependency's internal reorganization into a confiq API break for every existing user.
- Bad, because ADR 0032 already judged the ambient grab worth its cost for exactly this ergonomic
  (`TyperSource()` with no arguments inside a command body); nothing about vendoring changes that
  judgment.

## Relationship to Prior ADRs

Amends **ADR 0032** — its "Typer's context is a Click context" premise and its step 1
(`click.get_current_context()`) are superseded by provider-ordered acquisition; the eager-snapshot
contract, the `RuntimeError`/`ImportError` failure modes, and the marker precedence are unchanged.
Refines **ADR 0035** — capture stays shared, acquisition does not; the no-drift principle is upheld
by keeping the divergence declarative. Applies **ADR 0006**'s branded-`import_optional` convention
to the newly split `[click]` / `[typer]` extras.
