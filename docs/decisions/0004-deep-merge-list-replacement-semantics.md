---
status: accepted
date: 2026-05-25
decision-makers: [Kyle Oliver]
consulted: []
informed: []
---

# Deep merge replaces lists rather than concatenating them

## Context and Problem Statement

When merging two config layers (e.g., a base file and an env-var override), dict-valued keys are recursively merged. List-valued keys require a policy decision: replace the lower-priority list entirely with the higher-priority one, or concatenate them.

## Decision Drivers

- Predictability: users should be able to reason about what value a key holds after merging without needing to know how many layers contributed to a list.
- Consistency with existing prior art: pydantic's `deep_update` replaces lists.
- Override semantics: if a higher-priority source sets `allowed_hosts: [prod.example.com]`, it should _replace_ the base list, not extend it. The intent is substitution, not accumulation.
- Append semantics are available as an escape hatch via the `confiq_after_merge` hookimpl without being the default.

## Considered Options

- **Replace lists entirely** (chosen) — higher-priority value wins, base list is discarded.
- **Concatenate lists** — higher-priority values are appended to (or prepended before) the base list.
- **Dynaconf's `@merge` marker** — default is replace; `@merge` in the value opts into concatenation per-key.

## Decision Outcome

Chosen option: "Replace lists entirely", because it is predictable and consistent with pydantic's `deep_update` semantics. A user setting `allowed_hosts` in an env-var override expects to _replace_ the file-based list, not extend it.

Users who need concatenation can implement it in an `confiq_after_merge` hookimpl, or in their schema's `model_validator`, without contaminating the merge engine's semantics for all other users.

### Consequences

- Good, because merge behavior is predictable: the highest-priority source that specifies a key owns its value entirely.
- Good, because pydantic users already have this mental model from `deep_update`.
- Bad, because there is no built-in way to append to a base list from an override layer. Users who need this must implement it themselves.

## Pros and Cons of the Options

### Replace lists entirely (chosen)

- Good, because predictable: one source owns each list value.
- Good, because consistent with pydantic's `deep_update`.
- Bad, because no built-in accumulation for users who want it.

### Concatenate lists

- Good, because some use cases (e.g., `extra_allowed_hosts`) benefit from accumulation.
- Bad, because unpredictable: the final list value depends on how many sources contributed, in what order.
- Bad, because breaks the override contract: a high-priority source cannot clear a list set by a lower-priority one without knowing what the lower-priority list contains.

### Dynaconf's `@merge` marker

- Good, because opt-in concatenation is available without changing the default.
- Bad, because it requires a DSL inside config values — `allowed_hosts: "@merge [extra.example.com]"` — which introduces string parsing at the config layer and breaks plain YAML/TOML values.
- Bad, because it adds complexity to the merge engine for an edge case that `confiq_after_merge` already handles.
