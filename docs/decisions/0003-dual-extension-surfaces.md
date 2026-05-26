---
status: accepted
date: 2026-05-25
decision-makers: [Kyle Oliver]
consulted: []
informed: []
---

# Two distinct extension surfaces: source class registry and pluggy hookimpls

## Context and Problem Statement

`confiq` has two qualitatively different kinds of third-party extension:

1. **Config sources** — things with state and lifecycle that the user constructs and configures (a Redis client, a Vault session, an HTTP poller). Each instance is a `ConfigSource` with its own connection, credentials, and priority.
2. **Stateless participants** — logic that participates in a shared event without per-instance state (transform the merged dict, validate a snapshot, dispatch to the right file loader). Multiple participants may all need to run.

Both could theoretically be expressed through one mechanism. The question is whether they should be.

## Decision Drivers

- Sources are _configured instances_: the user passes constructor arguments (`url=`, `secret_id=`, `region=`). A plugin framework that only registers classes cannot carry those arguments without awkward factory hookspecs.
- Stateless hooks are _events_: multiple participants may run, order may matter, and no per-hook state is needed.
- The chosen model for sources (fsspec's `known_implementations` + `entry_points`) and for hooks (pluggy) are both well-established in the Python ecosystem and serve their respective purposes well.
- A single mechanism forces a worse fit on at least one of the two use cases.

## Considered Options

- **Two surfaces: fsspec-style registry for source classes + pluggy for stateless hooks** (chosen)
- **Everything through pluggy** (factory hookspecs for source creation)
- **Everything through a class registry** (callable registry with no pluggy)

## Decision Outcome

Chosen option: "Two surfaces", because sources and hooks are fundamentally different problems and the established solutions for each are the right tools.

The rule of thumb:

| You want to...                                                  | Use                                                      |
| --------------------------------------------------------------- | -------------------------------------------------------- |
| Add a new config source (Redis, REST endpoint, custom KV store) | source class + `confiq.sources` entry point              |
| Add a new file format (JSON5, HCL, properties files)            | hookimpl on `confiq_load_file`                           |
| Add a new schema type (attrs, msgspec, marshmallow)             | hookimpl on `confiq_get_schema_adapter`                  |
| Transform the merged dict before validation                     | hookimpl on `confiq_after_merge`                         |
| Validate or log every config change                             | hookimpl on `confiq_before_publish` / `confiq_on_reload` |

Two separate entry-point groups reflect this: `confiq.sources` registers source classes; `confiq` registers hookimpl plugins.

The mental model mirrors pytest: there are _fixtures_ (instances you compose, with state) and there are _hooks_ (events you participate in, stateless). They are different tools for different problems.

### Consequences

- Good, because source classes carry constructor arguments naturally; no awkward factory hookspec needed.
- Good, because pluggy's ordering (`tryfirst`, `trylast`) applies cleanly to the stateless hook cases.
- Good, because the two patterns are already familiar from fsspec and pytest respectively.
- Bad, because users must learn two distinct extension mechanisms. Mitigated by a clear rule of thumb (above) and a tutorial that frames the distinction explicitly.
- Bad, because two entry-point groups (`confiq.sources` and `confiq`) may surprise users who expect one. Named clearly in the documentation.

## Pros and Cons of the Options

### Two surfaces (chosen)

- Good, because each surface matches its use case precisely.
- Good, because both underlying patterns (fsspec registry, pluggy hooks) are widely understood.
- Bad, because two mechanisms to learn rather than one.

### Everything through pluggy

- Good, because a single extension model.
- Bad, because source creation requires a factory hookspec (`confiq_create_source(protocol, **opts) -> ConfigSource | None`) for every source type, just to disambiguate which plugin handles which protocol. This is exactly the fsspec problem that `known_implementations` solves.
- Bad, because pluggy's `firstresult` semantics apply cleanly to "which loader handles .yaml" but awkwardly to "create a source from these constructor args."

### Everything through a class registry

- Good, because simple mental model.
- Bad, because stateless hooks (after_merge, on_reload) need ordering, multiple participants, and entry-point discovery — all things pluggy provides. Rolling this from a class registry duplicates pluggy without the ecosystem.
