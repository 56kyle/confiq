---
status: accepted
date: 2026-05-25
decision-makers: [Kyle Oliver]
consulted: []
informed: []
---
# pydantic v2 as a required (non-optional) dependency

## Context and Problem Statement

`confiq` validates merged config dicts against a user-supplied schema. Schema validation, coercion, and IDE autocomplete are first-class features, not optional add-ons. The question is whether pydantic should be a hard dependency or whether a schema-free mode should be supported, with pydantic as one optional adapter among several.

## Decision Drivers

* Validation without a schema is a footgun: users get `dict[str, Any]` where any key might be absent or wrongly typed.
* `confiq`'s generic `Config[T]` API — `config.get()` returning a typed `Settings` instance with IDE autocomplete — requires a validation layer that understands Python types at runtime.
* pydantic v2's Rust core makes per-reload validation negligible in performance terms.
* pydantic is extremely widely installed in the Python ecosystem (it is a transitive dependency of FastAPI, SQLModel, LangChain, and many others).
* Going schema-free would require duplicating roughly 80% of pydantic-settings' validation and coercion logic.

## Considered Options

* **pydantic v2 as a hard dependency** (chosen)
* **Schema-free mode with pydantic as an optional adapter**
* **Support multiple first-class schema libraries (attrs, msgspec) at the same level as pydantic**

## Decision Outcome

Chosen option: "pydantic v2 as a hard dependency", because omitting it requires reimplementing validation and coercion poorly, and because the cost (one ubiquitous dependency) is trivial relative to the benefit (full typed config with IDE support).

`dataclass` and `TypedDict` schemas are supported via built-in adapters registered through pluggy. Third-party adapters for attrs, msgspec, or marshmallow can be registered as hookimpls on `confiq_get_schema_adapter`. pydantic itself is not optional, but pydantic is not the only schema type.

### Consequences

* Good, because `Config[T]` delivers full IDE autocomplete and runtime type safety out of the box.
* Good, because pydantic v2's `model_validate` handles nested models, field aliases, validators, and coercion — none of which need to be reimplemented.
* Good, because pydantic is already installed in most environments where `confiq` will be used.
* Bad, because users who explicitly refuse pydantic cannot use `confiq`. Accepted: the typed configuration story that motivates `confiq` requires a validation layer; a pydantic-free mode would deliver neither the typed API nor the validation guarantees that justify the library's existence.

## Pros and Cons of the Options

### pydantic v2 as a hard dependency (chosen)

* Good, because full IDE autocomplete and runtime validation.
* Good, because pydantic v2's Rust core is fast; validation overhead per reload is negligible.
* Good, because pydantic is ubiquitous — most users already have it.
* Bad, because users who refuse pydantic cannot use `confiq`.

### Schema-free mode with pydantic as an optional adapter

* Good, because looser coupling; users can opt out of pydantic.
* Bad, because schema-free config is a footgun the library is explicitly designed to prevent.
* Bad, because the `Config[T]` generic API only makes sense with a validation layer; a schema-free mode would deliver `Config[Any]` with no runtime guarantees.

### Support multiple first-class schema libraries (attrs, msgspec) at the same level as pydantic

* Good, because broader appeal.
* Bad, because maintaining three or more first-class adapter implementations requires ongoing work and cross-library test matrices.
* Bad, because pydantic is the clear community standard for typed config; elevating alternatives to first-class status adds complexity without proportional benefit. The pluggy `confiq_get_schema_adapter` hook already provides a clean path for third parties to add their own adapters.