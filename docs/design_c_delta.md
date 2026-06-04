# Plan: Document differences between the new architecture docs and `design_c.md`

## Context

The agreed design now lives in two documents:
- `docs/confiq_architecture.md` — narrative architecture doc
- `docs/confiq_design_axes.md` — per-axis decision record (confirm exact filename in the
  repo; the prior plan referenced `config_design_axes.md`)

These supersede `design_c.md`. The task is a delta document that surfaces where `design_c`
diverges from the agreed design so `design_c` (and any code built from it) can be brought
into line or retired. **Direction is not neutral:** the new docs are authoritative; each
entry should state what `design_c`/the code must change to.

**One caveat that shapes the whole doc.** The architecture doc's code sketches were
delivered as *illustrative, not prescriptive* — they encode the agreed contracts but the
exact signatures are placeholders. So a raw signature-level diff will mix genuine design
decisions with incidental sketch choices. The delta doc must separate the two, or it will
record sketch artifacts as deliberate changes.

## Files involved

- `docs/design_c.md` — the superseded spec
- `docs/confiq_architecture.md` — authoritative narrative
- `docs/confiq_design_axes.md` — authoritative per-axis record (verify filename)
- New file to create: `docs/design_c_delta.md`

## Guiding principle

For each difference, distinguish the **decided semantics** (authoritative, must be
reconciled) from **illustrative naming/signatures** (may be sketch-level; confirm before
recording as an intentional change). Group the doc accordingly.

---

## Group A — Substantive design changes (authoritative; reconcile `design_c`/code)

### A1. Async sources in sync `load()` — direct contradiction
- `design_c` §5.5: `load()` accepts sync *and* async sources, driving async ones via an
  `asyncio.gather()` inside a `ThreadPoolExecutor` + `asyncio.run()` bridge.
- New docs (architecture §7; Axis 8): `load()` accepts only sync sources and raises a
  clear error on an `AsyncSource`. The thread-executor bridge is explicitly rejected.

### A2. Mandatory vs optional dependencies
- `design_c` §10: `python-dotenv` and `typer` are mandatory core deps ("used in confiq's
  core CLI and .env support").
- New docs (architecture §11; Axis 11): the core depends on nothing optional — CLI
  frameworks, dotenv parsing, and cloud SDKs all sit behind extras. The architecture doc
  names the `design_c` arrangement as the inconsistency being corrected.

### A3. `on_reload` subscriber model
Decided parts (authoritative):
- Subscribers may be **sync and async** (`design_c` §5.6 / Decision 3: sync-only).
- Notification is via **blinker signals** with weak-referenced subscribers (`design_c`:
  plain callback list on a daemon thread).

Sketch-level parts (confirm — see Group B note): subscriber **arity** (`design_c`
`Callable[[T, T], None]` taking `(old, new)` → new docs `Callable[[T], Any]` taking the
new value only) and the **return of `on_reload`** (`design_c` returns `fn` for decorator
use → new docs return a disconnect callable). These follow from the blinker choice but
were not separately deliberated; confirm the intended arity and return before recording.

### A4. `SchemaAdapter` semantics
- `design_c` §9: `field_hints() -> Mapping[str, object]` (name → annotated *type*);
  `validate(data) -> object`.
- New docs (architecture §5.3): metadata accessor returns **Annotated extras only**
  (`Mapping[str, list[Any]]`), and `validate(...) -> T` returns the declared type.
- The method *name* (`field_hints` → `field_metadata`) is illustrative; the **semantic
  shift** (extras-only, typed return) is the decided part.

### A5. Metadata reading strategy
- `design_c` §6/§2.6: `get_type_hints(schema, include_extras=True)` for *all* schema
  types, including pydantic.
- New docs (architecture §5.3; Axis 4): per-adapter — pydantic reads `FieldInfo.metadata`
  (no second introspection path); `get_type_hints` is used only for stdlib dataclasses and
  `TypedDict`s, where it is unavoidable.

### A6. Multi-schema support scope
- `design_c`: pydantic `BaseModel` is the primary schema; resolver step 4 calls
  `schema.model_validate(merged)` (pydantic-model-specific).
- New docs (architecture §5.3; Axis 2): first-class support for `BaseModel`, pydantic
  dataclass, stdlib dataclass, `TypedDict`, and schemaless, all validated through pydantic
  `TypeAdapter`. The `model_validate` resolver step must change.

### A7. `load()` return-type contract and the immutability gradient (NEW — was missing)
- `design_c`: only frozen pydantic models, so the result is **unconditionally immutable**.
- New docs (architecture §8; Axis 2, Axis 9): `load()` returns an instance of the
  **declared type** (Pole A). Consequence: **immutability is now conditional on a frozen
  schema** — a non-frozen dataclass yields mutable config, a `TypedDict` yields a mutable
  dict — and secret-masking / rich serialization degrade by schema type (the documented
  gradient). This weakens the thread-safety guarantee from "always" to "opt-in" and is a
  semantic change, not just a validation-call swap. Give it its own entry.

### A8. Typed-open middle ground (NEW — was missing)
- `design_c`: schemaless is the only relaxation; no typed-core-plus-`extra` mode.
- New docs (Axis 9): a typed core may allow extra keys via `ConfigDict(extra="allow")`
  (pydantic) or an explicit `extra: dict[str, Any]` field (dataclass/`TypedDict`). This is
  a new feature added this round.

### A9. `Source` protocol gains `mode` and `profile`
- `design_c` §5.1: `name` + `fetch()` only.
- New docs (architecture §5.1): `mode: Literal["override", "fill"] = "override"` and
  `profile: str | None = None` are first-class protocol attributes.

### A10. Merge semantics gain fill mode (NEW — was only half-captured)
- `design_c`: deep-merge, list-replace, override-only.
- New docs (architecture §5.4; Axis 6): same deep-merge/list-replace, but the merge step
  now honors `mode="fill"` (contribute only keys not already set) in addition to override.
  This is the *behavioral* consequence of A9 and belongs in the merge entry, not only as a
  protocol-attribute note.

### A11. Provenance surfaced in errors (NEW — minor)
- `design_c`: provenance tracked internally.
- New docs (architecture §5.4; Axis 6): provenance is surfaced in error messages so a
  validation failure names the source of the offending value.

### A12. Profiles — absent vs present
- `design_c`: no profiles; no `profile` parameter; no source tagging.
- New docs (architecture §5.5; Axis cross-cutting): sources carry a `profile` tag,
  `load()` takes `profile: str | None = None`, and non-matching tagged sources are
  excluded. Thin, opt-in, explicit.

### A13. `ConfigHandle.create()` — `loop` parameter added
- New docs add `loop: AbstractEventLoop | None = None` to schedule async subscribers under
  sync `reload()`. This is the **decided** part of the `create()` changes (the rest is
  Group B).

---

## Group B — Incidental signature/sketch differences (confirm intent before recording)

These are real textual differences but likely reflect illustrative sketches rather than
deliberate decisions. Each should be confirmed; do not present as intentional changes
without checking.

### B1. `ConfigHandle.current` — property vs method
- `design_c` §5.6/§4.8: `current()` method (`handle.current()`).
- New docs (architecture §6): `current` property (`handle.current`).
- Real API difference but not separately deliberated. Recommend confirming (property reads
  cleaner for an immutable snapshot), then recording the chosen form.

### B2. `create()` — `sources` keyword-only vs positional
- `design_c`: keyword-only. New docs: positional. Cosmetic; confirm and standardize.

### B3. `create()` — `plugins` parameter removed (FLAG — likely unintended)
- `design_c` §5.6: `create(..., plugins: list[object] | None = None)`.
- New docs: no `plugins` parameter.
- **Per-handle plugin registration was never discussed for removal.** This is most likely
  an omission in the illustrative sketch, not a decision. Do **not** record it as an
  intentional change — flag it as an open question: keep `plugins`, or move plugin
  registration entirely to the pluggy/entry-point surface (Axis 11)?

---

## Proposed output: `docs/design_c_delta.md`

1. **Opening**: what the doc is, that the new docs are authoritative, and that entries are
   split into decided changes vs items to confirm.
2. **Group A — Reconcile**: one subsection per A-item, each as a
   `design_c says` / `new docs say (authoritative)` / `action` triple, where *action* is
   the concrete change to `design_c`/code.
3. **Group B — Confirm**: the three sketch-level items, each phrased as a question to
   resolve before changing anything.
4. **Summary table**: columns `Area | design_c | New docs (authoritative) | Kind
   (decision / confirm)`.

## Verification

- Read the produced delta doc against all three source files; confirm no difference is
  mischaracterized or omitted.
- **Quote `design_c` signatures verbatim** (especially `on_reload` arity, `current`, and
  `create()`), rather than paraphrasing — the arity and signature claims must be pinned to
  exact text.
- For every Group B item, confirm whether the new-doc form was a decision or a sketch
  artifact before it lands in Group A.
- Confirm the axes-doc filename referenced throughout.
-
