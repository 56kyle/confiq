---
status: accepted
date: 2026-07-13
supersedes: "0044"
---
# confiq Is a Positional Layer Cascade: Sources Translate Their Key Space; Fields Do Not Bind

## Context and Problem Statement

Stage 7 (CLI integration) forced the deferred `ConfigField(env=...)` override (ADR 0044) to
become concrete, and doing so exposed a model ambiguity at the core of what confiq *is*.

Two coherent mental models exist for a config reconciler:

- **Model 1 — positional layer cascade.** Each source produces a complete picture (a nested
  dict). Merge combines them by list position. Precedence is one-dimensional and uniform —
  "higher source wins on collision," the same rule for every field. Fields are passive. This
  is design_d §6.1 verbatim ("the list is the complete precedence specification") and §6.3.
- **Model 2 — field-level binding.** Fields declare where they come from ("this field from env
  var X; that one never from the file"). Precedence becomes a two-dimensional source × field
  matrix, unreadable from the source list alone.

confiq committed to Model 1 everywhere except `ConfigField(env=...)`, which is a Model-2
intrusion: a field reaching *out* to grab a specific external value with no natural position in
the layer stack. That single intrusion is the source of the precedence-undefined and
provenance-undefined problems ADR 0044 deferred and never resolved (its own §6.1 objection to
its "Option C" reapplies to its chosen path — both read `os.environ` mid-resolver).

The owner raised the deeper question directly: should schema fields be able to alter how they
are read — self-define precedence, or opt out of a source (e.g. to avoid a colliding key from a
foreign config file whose schema the user does not control)?

## Decision Drivers

- **Legibility is the reconciler's spine.** The single most legible property of a positional
  cascade is that precedence *is the list you wrote* — readable top-to-bottom, for every field,
  without consulting the schema. Per-field precedence destroys that (design_d §2 "precedence is
  data, not magic"; the "auditable magic" ideal refuses invisible coupling).
- **Refusal over degradation.** A silent per-field rule is exactly the invisible coupling the
  project refuses.
- **The foreign-key-collision hazard has a Model-1 answer: visibility, not per-field walls.**
  Provenance already records which source won each leaf; an `explain()` dump (§14.2 #4, whose
  snapshot the resolver already retains, ADR 0043) makes a surprising collision a one-line
  answer on the success path. Source *composition* (which sources you include) and *profiles*
  already reach the "don't let that source feed this" goal without making precedence unreadable.
- **No-concession scoping.** `ConfigField(env=...)` already exists, but preserving a
  mis-scoped feature is not a reason to keep it; the information to place it correctly is on
  hand now.

## Decision Outcome

**confiq is Model 1. Precedence is positional and uniform; fields never alter precedence or opt
out of a source.** The mechanism for a source whose native key space is not config-paths is
**key-space translation owned by the source**, not a field-level override.

### Source taxonomy (the clarifying consequence)

- **Flat-namespace sources** — `EnvSource`, `DotenvSource`, and the CLI sources. Native keys are
  a flat list of external names (`APP__DATABASE__URL`, `DATABASE_URL`, `--database-host`)
  translated to config paths by a **naming convention** plus an **explicit override map** for
  divergent names. `ConfigBind` is already the CLI's override map; env/dotenv gain an `aliases`
  map. Env and dotenv are the *same* flat shape (differing only in input — `os.environ` vs a
  parsed `.env`) and share one flat→nested translation helper.
- **Structured sources** — `FileSource` (TOML/YAML/JSON), `MemorySource`. Native keys are
  already config-path-shaped; they need no translation. **Aliases do not extend to them** —
  remapping a nested structure is *transforming* (restructuring subtrees), a different and
  heavier concern that belongs to a future transforms surface, not to naming.

### What changes

- **`ConfigField(env=...)` is removed** (the `env` field leaves `ConfigField`). The custom
  external-var-name need it served (`DATABASE_URL`, `PORT`) moves to **`EnvSource`/`DotenvSource`
  `aliases={config_path: ENV_VAR_NAME}`** — a source-side, positional contribution at the
  source's own slot, with natural provenance. Stage 4's `_apply_parsers` refusal of a populated
  `env=` is removed with the field.
- **Per-field precedence and per-field source opt-out are refused** (not deferred). The goals
  they would serve are met by source composition, profiles, and collision visibility
  (provenance/`explain()`).

This **supersedes ADR 0044's** framing (env override as a CLI-binding twin implemented as a
resolver-side field injection).

### Consequences

**Positive:**
- The reconciler's central legibility guarantee — precedence is the source list — holds without
  exception.
- The source taxonomy is clean and closed: flat sources translate, structured sources don't.
- Env override's precedence and provenance stop being undefined: it is a normal positional
  layer at the `EnvSource`/`DotenvSource` slot.

**Negative:**
- `ConfigField` loses a field and `ConfigField(env=...)` code paths are removed — a real
  (non-shipped) API change.
- The foreign-key-collision case has no per-field fix; the answer is visibility + source
  scoping. A user reading a source they do not control accepts its keys by including it.
- Custom var names now live on the source, one step from the field. Accepted: it keeps env
  logic in one legible place at one precedence slot.

## Considered Options

- **Option A (chosen): Model 1; sources translate, fields don't bind.**
- **Option B: admit Model 2** — per-field precedence / source opt-out. Rejected: destroys the
  precedence-is-the-list legibility that is the package's spine; invisible coupling.
- **Option C: keep `ConfigField(env=...)` as-is** (resolver-side field injection). Rejected: the
  Model-2 intrusion whose precedence/provenance never resolve; ADR 0044's own §6.1 objection.

## Relationship to design_d and other ADRs

Supersedes ADR 0044. Reinforces §6.1/§6.3 (positional cascade) and the "auditable magic" ideal.
Strengthens the case for `explain()` (§14.2 #4) as the Model-1 answer to collision visibility.
The CLI binding of §10/ADR 0027 is the *same family* as env aliases (flat-namespace
translation) but is schema-aware and therefore resolver-side (ADR 0049); env/dotenv aliases are
schema-blind and source-side.
