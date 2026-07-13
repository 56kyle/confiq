---
status: accepted
date: 2026-07-13
---
# `ConfigField(env=...)` Per-Field Override Deferred to the CLI/Binding Stage; Refused Loudly Until Then

## Context and Problem Statement

`ConfigField(env="DATABASE_URL")` lets a field be populated from an env var whose name is fixed
externally (Heroku/Docker/cloud conventions like `DATABASE_URL`, `PORT`, `REDIS_URL`),
bypassing an `EnvSource`'s `prefix + delimiter` convention. design_d §6.2 step 2 names it
alongside CLI `ConfigBind` as a per-field override applied during the fetch/coerce region.

Stage 3 made `EnvSource` deliberately **schema-blind**: it maps `PREFIX__NESTED__KEY` onto a
nested dict and has never seen the schema (project status, ADR 0026 key space). Honoring a
custom-name override therefore requires the **path table** (dotted path → `Annotated` extras),
which only the resolver holds together with the sources. So the override is structurally a
resolver concern — the question Stage 4 must answer is *which stage* grows that capability, and
what happens to a populated `env=` in the meantime.

Two facts shape the answer:

1. `ConfigField(env=...)` and CLI `ConfigBind("database.host")` are the **same operation** — a
   per-field name override validated against the path table (candidate dottings ∩ leaf paths;
   ambiguity → `SchemaError`, ADR 0027). Stage 7 builds exactly that machinery for CLI.
2. Implementing env override in Stage 4 means the resolver calls `os.environ.get(...)` itself,
   which would fire **even when no `EnvSource` is present** — env vars bleeding in through a
   back door, against the "the source list is the complete precedence specification"
   principle (design_d §6.1).

## Decision Drivers

- **One mechanism, one implementation (ADR 0035, corollary 2).** Env override and `ConfigBind`
  are twins; building a bespoke env-only version in Stage 4 that Stage 7 then reconciles is
  the drift-prone duplication that corollary explicitly rejects.
- **Keep env coupling at the source boundary.** The resolver reaching into `os.environ`
  couples the pipeline to process env and violates §6.1's "sources are the whole precedence
  list."
- **Refusal over degradation (design_d §2, ADR 0034).** A declared annotation that silently
  does nothing is the exact failure mode the project refuses. If the capability is not yet
  wired, a populated `env=` must *fail loudly*, not no-op.
- **Sequencing, not scope (ADR 0035, capacity vs membership).** Deferral here is a "later,"
  driven by shared-machinery sequencing — not a claim that env override is out of scope.

## Considered Options

- **Option A (chosen): defer to Stage 7, refuse loudly now.** Stage 4's coerce step does
  parser application only; a populated `ConfigField(env=...)` raises `SchemaError` naming the
  field and pointing to the binding stage. The override machinery is written once in Stage 7,
  path-table-validated, shared with `ConfigBind`.
- **Option B: defer to Stage 7, silent gap.** Same deferral, but `env=` simply does nothing
  until Stage 7 — a documented tracking note, no refusal. Rejected: declared-but-unhonored
  annotation, directly against §2.
- **Option C: implement in Stage 4.** Resolver reads `os.environ` for each `ConfigField(env=X)`
  during coerce. Rejected: couples the resolver to `os.environ` (fires with no `EnvSource`
  present) and duplicates machinery Stage 7 rebuilds for `ConfigBind`.

## Decision Outcome

Chosen option: **Option A**. In Stage 4, `_apply_parsers` (the coerce step) scans the path
table; when a field carries a populated `ConfigField(env=...)`, it raises `SchemaError` naming
the field path and directing the caller to remove `env=` or use the source's naming
convention. Parser application (`ConfigField.parser` on present `str` leaves) is the only
coerce behavior Stage 4 ships.

- The refusal message is the remediation-naming refusal design_d §13 requires: it states the
  field, the reason (not yet supported), and the fix.
- When Stage 7 lands the path-table override machinery, this refusal is replaced by the real
  binding; env and CLI overrides share that single implementation.

### Consequences

**Positive:**
- The resolver stays decoupled from `os.environ`; env precedence stays entirely in the source
  list (§6.1).
- Env override and `ConfigBind` will share one path-table-validated implementation — no twin
  to keep in sync (ADR 0035 corollary 2).
- A populated `env=` fails at load with an actionable message, honoring §2 — no silent gap.

**Negative:**
- `ConfigField(env=...)` is unusable until Stage 7; a user who wants it today is blocked, not
  degraded. Acceptable under capacity-sequences-essential-work (ADR 0035): the capability is
  in scope, just later, and the interim refusal is honest.
- A schema that merely *declares* `env=` cannot be resolved at all until Stage 7, even if that
  field is otherwise satisfied by another source. This is the deliberate loud-refusal cost;
  the alternative (silent no-op) was rejected as worse.

## Relationship to design_d

Updates §6.2 step 5 to record that per-field env override lands with `ConfigBind` (Stage 7) and
is refused with `SchemaError` until then. The §6.2 step 2 mention of `ConfigField.env` /
`ConfigBind` overrides during fetch remains the eventual design; this ADR sequences *when* it
is honored and specifies the interim refusal.
