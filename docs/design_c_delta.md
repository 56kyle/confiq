# Plan (corrected): `design_c.md` → agreed-design delta document

## Purpose & framing

`design_c.md` is the prior specification (and the shape any existing code follows).
`confiq_architecture.md` and the per-axis decision reference are the **agreed design** and
are authoritative. The delta document therefore is not a neutral "two views" inventory —
it is an **actionable reconciliation**: for each divergence it should state which side wins
(the agreed design, unless noted) and what `design_c`/the code must change to.

## Files involved

- `docs/design_c.md` — prior spec, to be updated (or retired) to match the agreed design.
- `docs/confiq_architecture.md` — agreed narrative design (authoritative).
- `docs/confiq_design_axes.md` — agreed per-axis decisions (authoritative). *Confirm the
  exact filename in the repo: the original plan referred to `config_design_axes.md`; the
  file produced was `confiq_design_axes.md`.*
- New file: `docs/design_c_delta.md`.

## Framing correction that drives the whole structure

The architecture document's code sketches were delivered as **illustrative, not
prescriptive** — they encode the agreed *contracts*, but exact signatures (argument order,
property-vs-method, whether a given parameter appears) are placeholders. Diffing those
sketches line-by-line against `design_c` risks recording incidental presentation as if it
were a deliberate decision. The delta doc must therefore separate:

- **Part 1 — substantive design changes** (real decisions; the agreed design wins; update
  `design_c`/code).
- **Part 2 — signature/sketch differences to confirm** (verify against `design_c`'s exact
  text and confirm intent before recording as decisions).

---

## Part 1 — Substantive design changes (agreed design authoritative)

Each entry in the delta doc gets: *design_c says* / *agreed design says* / *resolution* /
*note*.

**1. CLI binding & generation (was entirely missing from the original plan — the largest
divergence).**
- *design_c:* explicit `ConfigBind` on every CLI parameter, with the field default
  **restated** on the param (`= "localhost"`); `ArgparseSource` detects explicit-set by
  comparing against `parser.get_default()`.
- *Agreed design:* consumer-by-default (confiq reads only explicitly-set params and folds
  them in as highest-precedence); **defaults declared only in the schema** (CLI options omit
  them); **convention auto-binding** so `ConfigBind` is needed only on divergence; an
  **opt-in generator** (`options_from(schema)`); argparse explicit-set via
  `default=argparse.SUPPRESS` with a `bind={...}` dict; documented consume/generate
  framework asymmetry (Click easy both sides, Typer awkward to generate, argparse awkward to
  consume).
- This should be the longest section; it has five independent sub-differences.

**2. Async sources in sync `load()`.**
- *design_c (§5.5):* `load()` accepts sync and async sources and drives async via
  `ThreadPoolExecutor` + `asyncio.run()`.
- *Agreed design (arch §7, Axis 8):* `load()` accepts sync sources only and raises a clear
  error on an `AsyncSource`; `load_async()` drives async sources. The bridge is explicitly
  rejected.

**3. Mandatory vs optional dependencies.**
- *design_c (§10):* `python-dotenv` and `typer` are mandatory core dependencies.
- *Agreed design (arch §11, Axis 11):* the core depends on nothing optional; CLI frameworks,
  dotenv, and cloud SDKs all sit behind extras. (design_c's stance is named as the earlier
  inconsistency.)

**4. Return type & the immutability guarantee (split out from the old "multi-schema" item;
it is a safety-semantics change, not just a validation-call swap).**
- *design_c:* returns a frozen pydantic model, so the result is **unconditionally
  immutable**.
- *Agreed design (arch §8, Axis 2/9):* `load()` returns an instance of the **declared type**
  (Pole A); `isinstance` holds. Immutability is therefore **conditional on the schema being
  frozen** — a non-frozen dataclass yields mutable config, a `TypedDict` yields a mutable
  dict — and guarantees form a documented gradient (mutability and secret-masked `repr`
  strongest on frozen pydantic, degrading toward `TypedDict`/schemaless).

**5. Multi-schema support & validation engine.**
- *design_c:* pydantic `BaseModel` is the primary schema; resolver step 4 calls
  `schema.model_validate(merged)` (model-specific).
- *Agreed design (arch §5.3, Axis 2):* first-class support for pydantic `BaseModel`, pydantic
  dataclass, stdlib dataclass, `TypedDict`, and schemaless; **all** validated via pydantic
  `TypeAdapter` (not `model_validate`); the `SchemaAdapter` is the spine. The
  `model_validate` resolver step must change.

**6. Metadata reading strategy.**
- *design_c (§2.6, §6):* `typing.get_type_hints(schema, include_extras=True)` for all schema
  types, **including pydantic**.
- *Agreed design (arch §5.3, Axis 4):* per-adapter — pydantic reads `ConfigField` from
  `FieldInfo.metadata` (no second introspection path); `get_type_hints` is used only for
  stdlib dataclasses and `TypedDict`s, where it is unavoidable.

**7. `SchemaAdapter` protocol shape** (substantive because it is the contract enabling #4–#6;
exact method name is still a placeholder — see Part 2).
- *design_c (§9):* `field_hints() -> Mapping[str, object]` (name → annotated type);
  `validate(data: dict[str, Any]) -> object`.
- *Agreed design (arch §5.3):* `field_metadata() -> Mapping[str, list[Any]]` (Annotated
  extras only); `validate(data: Mapping[str, Any]) -> T`.

**8. `Source` protocol gains `mode` and `profile`.**
- *design_c (§5.1):* `name` + `fetch()` only.
- *Agreed design (arch §5.1):* adds `mode: Literal["override","fill"] = "override"` and
  `profile: str | None = None` as first-class protocol attributes.

**9. Merge semantics: fill mode + provenance in errors** (consequence of #8; the original
plan caught the attribute but not the behavior).
- *design_c:* deep-merge, list-replace, override-only; provenance tracked internally.
- *Agreed design (arch §5.4, Axis 6):* deep-merge, list-replace, **plus a per-source fill
  mode** (contribute only keys not already set); provenance **surfaced in error messages**.

**10. Profiles.**
- *design_c:* none — no `profile` parameter, no source tagging.
- *Agreed design (arch §5.5):* sources may carry a `profile` tag; `load(..., profile=...)`
  filters which tagged sources participate; thin, opt-in, explicit, nothing auto-discovered.

**11. Typed-open middle ground (Axis 9 — a feature added this round; not in design_c).**
- *design_c:* schemaless mode is the only relaxation.
- *Agreed design (arch §8, Axis 9):* typed core + permissive `extra` — `ConfigDict(extra=
  "allow")` on pydantic (extras in `__pydantic_extra__`), or an explicit `extra: dict[str,
  Any]` field on dataclasses/`TypedDict`s — in addition to schemaless.

**12. `on_reload` subscriber model** (substantive parts: async support + blinker; the exact
arity and return value are contract details — see Part 2).
- *design_c (§5.6):* sync-only subscribers (async deferred); plain callback list; daemon
  thread after swap.
- *Agreed design (arch §6–7, Axis 7):* sync **and** async subscribers (async driven on the
  loop by `reload_async()`, or via an explicitly provided loop under sync `reload()`);
  modeled on **blinker** signals with weak-referenced subscribers; `ConfigHandle.create()`
  gains a `loop` parameter for that scheduling.

---

## Part 2 — Signature/sketch differences to confirm, not record as decisions

These come from illustrative sketches. The delta doc should list them as **pending
confirmation**, verified against `design_c`'s exact text, before any are written up as
intentional changes.

1. **`plugins` removed from `ConfigHandle.create()`** — most likely a sketch omission, **not**
   a decision. We never discussed dropping per-handle plugin registration. Confirm intent
   before recording.
2. **`ConfigHandle.current` property vs method** — cosmetic; confirm the intended form.
3. **`create()` `sources` positional vs keyword-only** — cosmetic; confirm.
4. **`on_reload` exact arity (`(new)` vs `(old, new)`) and return value (disconnect callable
   vs the function unchanged)** — verify `design_c`'s exact signature verbatim; lock the
   intended contract. (The decision to support async + blinker is real; the precise
   signature is a detail to settle.)
5. **Exact `SchemaAdapter` method name (`field_metadata`)** — the conceptual change is decided
   (#7); the literal name is a placeholder to confirm.

---

## Proposed delta document structure

1. One opening paragraph: what the doc is, that the agreed design is authoritative, and that
   it is an actionable reconciliation (what `design_c`/code must change to).
2. **Part 1 — substantive changes**, one entry each, in the *design_c / agreed design /
   resolution / note* form above.
3. **Part 2 — pending confirmation**, listed plainly as open items, not decisions.
4. A summary table: column for the item, one-line `design_c`, one-line agreed design, and a
   status column (`change design_c` vs `confirm intent`).

## Verification

- Quote `design_c`'s signatures **verbatim** rather than paraphrasing — especially the
  `on_reload` arity/return and `create()` signature — so no contract detail is
  mischaracterized.
- Cross-check every "agreed design says" against the cited section in
  `confiq_architecture.md` / `confiq_design_axes.md`.
- Confirm the axes filename in the repo.
- Walk Part 2 with the design owner before finalizing; move any confirmed item into Part 1,
  drop any that turn out to be sketch noise.
