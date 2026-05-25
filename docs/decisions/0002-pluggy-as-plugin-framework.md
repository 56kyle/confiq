---
status: accepted
date: 2026-05-25
decision-makers: [Kyle Oliver]
consulted: []
informed: []
---
# Use pluggy as the plugin framework for stateless extension points

## Context and Problem Statement

`confiq` needs stateless multi-participant extension points: file-format dispatch (`confiq_load_file`), schema-adapter selection (`confiq_get_schema_adapter`), lifecycle hooks (`before_load`, `after_merge`, `before_publish`, `on_reload`). These extension points must be discoverable by third-party packages, introspectable, and orderable (some hooks have a natural priority — e.g., a custom loader that handles a format before the built-in).

## Decision Drivers

* Third-party plugins should require zero user-code changes to activate (entry-point discovery).
* Plugin ordering must be explicit and controllable (`tryfirst`, `trylast`).
* The framework should be introspectable (`pm.list_name_plugin()`, `pm.list_blocked()`).
* Adding transitive dependencies is undesirable; zero-transitive-dep options are preferred.
* Developers familiar with pytest plugin authorship should find `confiq` plugins immediately familiar.

## Considered Options

* **pluggy** (chosen)
* **Roll a custom callback registry** (list of callables, registered explicitly)
* **`stevedore`** (OpenStack's plugin library)

## Decision Outcome

Chosen option: "pluggy", because it is battle-tested (powers pytest, tox, devpi), has zero transitive dependencies, and provides exactly the semantics needed — `firstresult`, all-results, `tryfirst`/`trylast`, `hookwrapper`, entry-point discovery — without requiring a custom implementation of any of those primitives.

### Consequences

* Good, because any developer who has written a pytest plugin already knows how to extend `confiq`.
* Good, because pluggy handles entry-point discovery (`pm.load_setuptools_entrypoints("confiq")`) out of the box.
* Good, because pluggy's introspection (`pm.list_name_plugin()`, `pm.list_blocked()`) is available for diagnostics.
* Good, because the dependency is tiny (~1500 SLOC) and maintained by the pytest core team.
* Bad, because pluggy is a hard dependency. Users who refuse it are out of luck. Acceptable: pluggy is not controversial, and the alternative — a custom callback registry — duplicates a solved problem.
* Bad, because pluggy's `firstresult=True` semantics (first non-None wins) mean plugin order matters. Documented convention: use `tryfirst=True` on hookimpl to claim priority.

## Pros and Cons of the Options

### pluggy

* Good, because zero transitive dependencies.
* Good, because semantics (`firstresult`, `tryfirst`, `trylast`, `hookwrapper`) cover every hook pattern `confiq` needs.
* Good, because network effect: pytest plugin authors are an existing audience.
* Bad, because one additional mandatory dependency (small and justified).

### Roll a custom callback registry

* Good, because no new dependency.
* Bad, because reimplements ordering, introspection, entry-point discovery, and exception handling — all things pluggy provides.
* Bad, because the result is a worse version of pluggy without the network effect.

### `stevedore`

* Good, because mature and widely used in the OpenStack ecosystem.
* Bad, because brings in `pbr` and other OpenStack-adjacent dependencies.
* Bad, because less familiar to general Python developers than pluggy.
* Bad, because designed primarily for driver-style single-impl-per-namespace plugins, not pluggy's multi-participant hook model.