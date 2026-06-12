---
status: accepted
date: 2026-06-12
---
# CLI Name↔Path Convention: Underscore-Joined Paths Validated Against the Path Table

## Context and Problem Statement

design_d §10.2 makes convention binding the default — "a parameter maps to its config
path by name" — with `ConfigBind` needed only on divergence, and §10.4 promises the
consumer path and the generator run the *same* convention in opposite directions. But the
convention itself was never specified as a deterministic function, and the spec's own
example claimed `db_host` ↔ `database.host`, which no delimiter rule can derive
(`db` ≠ `database`). Python identifiers cannot contain dots, and a single underscore is
ambiguous against field names that themselves contain underscores (`log_level` could be
`log.level` or a top-level `log_level` field).

Separately, ADR 0011 specified the opposite participation model — only parameters
carrying a `ConfigBind` marker enter the merge — and described `TyperSource` as a
module-level alias of `ClickSource`. design_d §10.2 and the current skeleton
(`source/_typer.py` is its own class) contradict it on both points.

## Decision Drivers

- The convention must be a deterministic, documented function or the consumer and
  generator paths cannot be guaranteed to agree (§10.4).
- The schema-derived path table (ADR 0026) provides the set of valid dotted paths, making
  schema-aware validation of a parameter name possible.
- Convention-over-annotation is the design's stated default; the annotation burden should
  fall only on genuinely divergent names (abbreviations, reserved words).
- Unmarked parameters silently entering the config merge is a surprise hazard that needs
  an explicit collision rule and an opt-out.

## Considered Options

- **Option A: Exact underscore-joined path, longest-match against the path table** —
  `database_host` ↔ `database.host`; ambiguity resolved by matching real schema paths.
- **Option B: Double-underscore delimiter mirroring `EnvSource`** — `database__host`,
  schema-free and unambiguous.
- **Option C: Convention binds top-level fields only** — any nested path requires
  `ConfigBind`.

## Decision Outcome

Chosen option: **Option A**, because it gives natural parameter names
(`--database-host`, not `--database--host`), is deterministic once checked against the
path table, and keeps the annotation burden on genuine divergence only. This supersedes
ADR 0011's participation model.

### The convention, precisely

For a parameter named `p` (snake_case identifier):

1. Compute every dotted path obtainable by replacing some subset of `p`'s underscores
   with dots.
2. Intersect with the schema's path table (ADR 0026), considering only **leaf** paths.
3. Exactly one match → the parameter is convention-bound to it. The exact-name top-level
   match (zero replacements) participates like any other candidate.
4. More than one match → ambiguity error at binding time (`SchemaError`), naming the
   candidates; the user resolves it with `ConfigBind`.
5. Zero matches → the parameter does not participate in config (an ordinary CLI flag).

`ConfigBind("dotted.path")` overrides the convention entirely; `ConfigBind(None)` opts a
parameter out even when its name matches a schema path. The generator (§10.4,
`options_from`) runs the same function backward: path → underscore-joined parameter name,
which round-trips by construction.

Participation remains gated on **explicitly set** (ADR 0011's `get_parameter_source()` /
sentinel mechanics carry forward unchanged).

### Consequences

**Positive:**
- The convention is a total function checkable at startup; consumer and generator cannot
  disagree.
- §10.2's example is corrected: `database_host` is the convention case; `db_host` (an
  abbreviation) requires `ConfigBind("database.host")`.
- Ambiguity is loud (an error naming candidates), never a silent wrong binding.
- Accidental capture has an escape hatch (`ConfigBind(None)`), and zero-match parameters
  are simply ignored, so most non-config flags need nothing.

**Negative:**
- Convention-bound CLI sources need the path table, so name resolution happens in the
  resolver (which holds the adapter), not inside `fetch()` — CLI sources surface raw
  parameter names plus binding markers; the resolver maps them. This is a fetch/resolve
  split the implementation must respect.
- A parameter that *coincidentally* matches a schema leaf participates by default. The
  rule is documented, deterministic, and opt-out-able; the alternative (opt-in
  everywhere) was ADR 0011's model and contradicts §10.2's ergonomics.

## Pros and Cons of the Options

### Option A: Underscore-join with path-table validation (chosen)

- Good, because parameter and flag names stay idiomatic (`--database-host`).
- Good, because ambiguity is detected against real paths instead of guessed.
- Good, because the generator round-trips exactly.
- Bad, because it requires schema knowledge at binding time (available via ADR 0026).

### Option B: Double-underscore delimiter

- Good, because it is schema-free and mirrors `EnvSource`.
- Bad, because Click converts `database__host` to the flag `--database-host` anyway —
  the disambiguating information survives only in the Python identifier, while help text
  and flag names show the collapsed form, re-importing the ambiguity for users.
- Bad, because idiomatic existing commands (the consumer path's whole audience) do not
  name their parameters with double underscores; the convention would bind almost
  nothing without rewrites.

### Option C: Top-level only

- Good, because it is the simplest possible rule.
- Bad, because nested schemas are the norm (the design's own example is nested), so most
  real bindings would need annotations — convention in name only.
