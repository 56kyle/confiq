# `confiq` — Proposed ADRs

Decisions to be written up as ADRs. Each gives the decision and what the ADR should capture.
Numbering is placeholder; assign your own.

---

## 1. Rust-port readiness as a design principle

**Decision.** confiq's internals and boundaries use structured, named, enum-typed forms (cheap
in Python, and aligned with a possible future maturin/PyO3 Rust core); the public Python surface
stays tuned for Python ergonomics. If a port happens, the PyO3 binding layer reconciles the
internal Rust representation with the Python surface.

**Capture:**
- Tiebreak rule: genuine toss-ups resolve toward the structured/enum form; clear Python
  ergonomic wins keep the Python form.
- Layer separation: internal representation ≠ public contract, so port-friendly internals do not
  require Rust-shaped Python APIs.
- Non-commitment: the port is speculative (the `confiq` crate name may be taken; factors outside
  our control). Do not contort the Python API for it.
- This principle is the rationale anchor for ADRs 3 and 4.

---

## 2. No output generic on `Source` (rejection)

**Decision.** `Source` stays ungeneric. The schema generic `T` lives only at the typing edge
(`load`, `SchemaAdapter`, `ResolutionSpec`, `ConfigHandle`, `LazyConfig`).

**Capture (the reasoning, since this is a deliberate "no"):**
- Sources produce partial, schema-agnostic `Mapping[str, Any]` fragments; the merge collapses
  heterogeneous fragments to `Mapping[str, Any]`; validation is post-merge by necessity (a
  required field absent from the top source may be supplied below; partial fragments can't be
  validated individually).
- A `Source[X]` output type never connects to `T` and is erased at the merge — ornamental.
- The genuine str-valued vs native-valued distinction is a category/capability, largely subsumed
  by pydantic coercion, not a generic to propagate.
- Intended shape: "typed at the edges (schema), dynamic in the middle (sources + merge)."

---

## 3. Named pipeline / boundary types

**Decision.** Introduce named types at the resolver's multi-value boundaries, plus a named
domain vocabulary.

**Touches:** §4.3, §6.2, §6.4, §7.1–7.3.

**Capture:**
- `FetchedEntry` (name + data + mode) — the fetch→merge unit; decouples merge from `Source`
  objects.
- `ResolvedSnapshot` (`merged` + `Provenance`) — the merge output; keeps `merged` and provenance
  from drifting apart through coerce/validate.
- `Provenance` (read-only `Mapping[str, str]`) — replaces the informal "parallel provenance map";
  the natural home for future error-formatting / secret-masking.
- `FieldAnnotations` alias — replaces the bare `Mapping[str, list[Any]]` return of
  `SchemaAdapter.field_metadata`.
- `PluginList` alias — replaces `tuple[object, ...]` in `ResolutionSpec` and the `load` overloads.
- Threshold to state: name boundaries carrying *multiple correlated values*; leave single values
  (e.g. the merged dict between coerce and validate) as a plain `dict`.
- These map ~1:1 to Rust structs (ADR 1), so naming them now is port-aligned at near-zero Python
  cost.

---

## 4. `MergeMode` enum (replaces `ListFillBehavior`)

**Decision.** Replace the `ListFillBehavior` type with a `MergeMode` enum (`enum.StrEnum` on
3.11+).

**Touches:** §5.1, §5.5.

**Capture:**
- Two fixes in one: the *naming* (`ListFillBehavior` reads as list-merge behavior, but it governs
  the source's override-vs-fill precedence mode; list replacement is a separate concern, §6.3)
  and the *form* (an enum over an ad-hoc string type).
- String-compatibility sub-decision to settle: enum-only (call sites pass `MergeMode.OVERRIDE`;
  fits the type-safety priority) vs `MergeMode | str` with coercion at the public boundary. A
  `(str, Enum)` mixin does not make strings acceptable under a strict type checker.
- Scope guard: this is not "enum-ify every `Literal`"; `MergeMode` qualifies as a named domain
  variant (and is Rust-aligned, ADR 1).
- Maps directly to a Rust enum with exhaustive `match` if ported.

---

## 5. Error structure (`ErrorContext`)

**Decision.** Extract `ErrorContext(field_path, sources)` as the shared payload of
`MissingConfigError` and `ConfigValidationError`, with forwarding properties preserving
`err.field_path` / `err.sources`.

**Touches:** §13.

**Capture:**
- The two errors share `field_path` + provenance *because* they carry the same diagnostic
  concept; a named context gives one place to evolve it.
- Adopt now because the payload is expected to grow (provenance-in-errors, secret-masking), so it
  is not ceremony.
- The most deferrable of the set; if the payload were frozen at two fields a shared mixin would
  suffice.
