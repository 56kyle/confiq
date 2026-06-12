---
status: accepted
date: 2026-06-07
---
# `MergeMode` StrEnum Replaces `ListFillBehavior` Literal

## Context and Problem Statement

`_types.py` currently defines:

```python
ListFillBehavior: TypeAlias = Literal["override", "fill"]
```

This type has two independent problems.

**Naming.** `ListFillBehavior` reads as "how lists are merged/filled." The
type actually governs whether a source's keys override already-present values
or only fill in missing ones — a source-precedence concept, not a list-merge
concept. List replacement behaviour is a separate concern (§6.3 of the design
document). The name creates a false mental model.

**Form.** An ad-hoc string `Literal` loses the benefits of an enum: no
exhaustive `match` support, no namespaced reference (`MergeMode.OVERRIDE` vs
the bare string `"override"`), and weaker Rust-alignment (ADR 0021).

## Decision Drivers

- The replacement name `MergeMode` with values `OVERRIDE` and `FILL` reflects
  what the type actually controls: the precedence mode of a source's
  contribution to the merged result.
- `enum.StrEnum` (Python 3.11+) preserves string equality:
  `MergeMode.OVERRIDE == "override"` is `True`. JSON/TOML serialisation
  round-trips without manual conversion.
- **String-compatibility sub-decision (settled):** enum-only. Call sites pass
  `MergeMode.OVERRIDE` / `MergeMode.FILL`. Bare strings are a type error. A
  `(str, Enum)` mixin does not make strings acceptable under a strict type
  checker; coercion at any boundary would defeat the type-safety goal.
- **Scope guard.** This is not "enum-ify every `Literal`." `MergeMode`
  qualifies because it names a domain variant with a clear behavioural contract
  and exactly two members. Not every `Literal` meets this bar.
- Maps directly to a Rust `enum MergeMode { Override, Fill }` with exhaustive
  `match` if ported (ADR 0021 tiebreaker).

## Considered Options

- **Option A: `MergeMode(enum.StrEnum)`, enum-only call sites** — no bare-
  string acceptance at any boundary.
- **Option B: `MergeMode(enum.StrEnum)`, `MergeMode | str` at the public
  boundary** — thin coercion converts `"override"` to `MergeMode.OVERRIDE` at
  source construction.
- **Option C: Keep `ListFillBehavior` as-is** — no change.

## Decision Outcome

Chosen option: **Option A**, because enum-only is consistent with the type-
safety goal and there is no compelling ergonomic argument for accepting bare
strings at the public boundary: callers already import confiq symbols, so
importing `MergeMode` alongside `SyncSource` is not a meaningful burden.

### Shape

```python
import enum

class MergeMode(enum.StrEnum):
    OVERRIDE = "override"
    FILL = "fill"
```

**Python 3.10 floor amendment (2026-06-12).** `enum.StrEnum` requires Python 3.11; on
the project's 3.10 floor the implementation is a `(str, enum.Enum)` mixin. The mixin is
*not* semantically identical: `str(member)` and f-string formatting yield
`"MergeMode.OVERRIDE"` for the mixin but `"override"` for `StrEnum`. The implementation
therefore sets `__str__ = str.__str__` on the mixin to restore StrEnum-equivalent
formatting:

```python
class MergeMode(str, enum.Enum):
    OVERRIDE = "override"
    FILL = "fill"

    __str__ = str.__str__
```

If the floor is later raised to 3.11+, the class reverts to plain `enum.StrEnum`.

All previous `mode: ListFillBehavior` annotations become `mode: MergeMode`.
`ResolutionSpec`, `Source`, `SyncSource`, `AsyncSource`, and `FetchedEntry`
(ADR 0023) all use `MergeMode`.

### Consequences

**Positive:**
- `mode=MergeMode.OVERRIDE` is self-documenting and IDE-completable.
- Exhaustive `match` on `MergeMode` is possible; a bare `Literal` offers no
  equivalent.
- `MergeMode.OVERRIDE == "override"` keeps existing serialised configs
  readable without conversion.
- The scope guard prevents the enum pattern from proliferating to `Literal`
  types that do not warrant it.

**Negative:**
- Call sites that construct sources must import `MergeMode`. This is a one-
  time cost per file.
- `ListFillBehavior` is a breaking rename. Since the project is pre-release
  and in `design_d`, this is acceptable.

## Pros and Cons of the Options

### Option A: `MergeMode(enum.StrEnum)`, enum-only (chosen)

- Good, because `MergeMode.OVERRIDE` is unambiguous and IDE-discoverable.
- Good, because strict type checkers reject bare strings — the type system
  enforces the domain vocabulary.
- Good, because `StrEnum` equality keeps serialisation simple.
- Good, because it maps directly to an exhaustively matchable Rust enum.

### Option B: `MergeMode | str` at public boundary

- Good, because callers can pass `mode="override"` without importing
  `MergeMode`.
- Bad, because the coercion layer must live somewhere; it is either hidden
  in the constructor (surprising) or explicit (defeating the ergonomic
  argument).
- Bad, because a `(str, Enum)` mixin does not satisfy strict type checkers —
  `str` is still rejected as `MergeMode` by basedpyright/mypy strict.
- Bad, because coercion at the boundary contradicts the type-safety goal that
  motivates introducing the enum in the first place.

### Option C: Keep `ListFillBehavior` as-is

- Good, because no call-site churn.
- Bad, because the misleading name (`ListFillBehavior`) persists and creates
  confusion with the actual list-replacement feature.
- Bad, because the ad-hoc string literal loses exhaustive-match support and
  Rust-alignment.
