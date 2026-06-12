---
status: accepted
date: 2026-06-12
---
# Secret Masking Refuses on Schema Kinds That Cannot Honor It

## Context and Problem Statement

`ConfigField(secret=True)` promises that a field's value is masked in `repr` and in
error output. The §3 gradient as previously written delivered that promise fully on
pydantic schemas, invasively-but-really on stdlib dataclasses (a generated `__repr__`),
and **not at all** on `TypedDict` and schemaless results — the gradient table said
"none" and the load proceeded.

That last cell is a silent broken promise in the worst possible place: a developer who
wrote `secret=True` believes the password is masked, and it is not. Logs, tracebacks,
and error messages then leak it. The failure is invisible until the leak.

The design-ideals discussion (2026-06-12, recorded in ADR 0034) named the governing
principle — never silently provide a weaker guarantee than the user believes they have —
and the project owner's verdict on this specific case was unequivocal: "the last thing I
would want is for a developer to not know that it wasn't actually a secret."

## Decision Drivers

- A secret leak is a maximum-severity failure; the failure-moment experience dominates
  any writing-moment convenience here.
- The user *explicitly requested* the guarantee by writing `secret=True` — this is not a
  capability quietly absent, it is a declared intent the library cannot honor.
- The gradient (§3) remains legitimate for capabilities the user did not ask for
  (rich serialization, attribute access); it must not extend to silently dropping
  guarantees the user asked for by name.
- Refusals must carry a remediation path (ADR 0034); the error must say what to do, not
  just no.

## Considered Options

- **Option A: Refuse at load** — `secret=True` on a schema kind that cannot honor
  masking raises `SchemaError` during resolution, naming the field path and schema kind.
- **Option B: Warn and proceed** — emit a `UserWarning`, load unmasked.
- **Option C: Document the gap** — keep the gradient table's "none" cell and rely on the
  user reading it (status quo).

## Decision Outcome

Chosen option: **Option A**, because a declared secret that silently is not one is the
canonical silent degradation, at the highest severity the library can encounter.

### Behavior

- During resolution (adapter/metadata step), if any path in the field metadata table
  (ADR 0026) carries `ConfigField(secret=True)` and the schema kind cannot honor
  masking, raise `SchemaError` before returning a value.
- The error names the field path, the schema kind, and the remediation: use a pydantic
  model or a stdlib/pydantic dataclass for that structure, or remove `secret=True` if
  the field is not actually secret.
- **Honored kinds:** pydantic `BaseModel` and pydantic dataclasses (native), stdlib
  dataclasses (confiq-generated `__repr__` — invasive but real, per §3 footnote).
- **Refused kinds:** `TypedDict` (resolves to a plain dict; nowhere to hang a masked
  repr). Schemaless mode has no fields and therefore no `ConfigField` at all — the
  refusal is structurally unreachable there, which the gradient note should state.
- Masking in *error output* is independent of repr and applies wherever metadata exists;
  the refusal is specifically about kinds where the value object itself cannot mask.

### Consequences

**Positive:**
- `secret=True` is now a guarantee or an error — never a decoration.
- The failure surfaces at load time on the developer's machine, not at leak time in
  production logs.

**Negative:**
- A `TypedDict` user with a secret field must restructure (or wrap that section in a
  dataclass/model) rather than proceed unmasked. That friction is the point, but it is
  friction.
- Adapters must be able to answer "can this schema kind honor masking?" — one more
  obligation on the adapter contract.

## Pros and Cons of the Options

### Option A: Refuse at load (chosen)

- Good, because the broken promise becomes impossible rather than documented.
- Good, because load-time is the cheapest possible moment to learn it.
- Bad, because it converts a previously-working (silently unsafe) configuration into an
  error — acceptable pre-release, and desirable even post-release.

### Option B: Warn and proceed

- Good, because nothing blocks.
- Bad, because warnings are routinely unseen in exactly the contexts (services, CI)
  where config loads — and an unseen warning about a secret is a leak with a paper trail.

### Option C: Document the gap

- Good, because zero code.
- Bad, because it relies on every future reader of `secret=True` also having read a
  table footnote; the declaration itself looks identical whether it works or not.
