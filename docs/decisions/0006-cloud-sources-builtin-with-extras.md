---
status: accepted
date: 2026-05-29
---
# Cloud Sources Ship as Built-in Implementations with Optional Extras

## Context and Problem Statement

confiq needs to support secrets and config fetched from cloud backends: AWS
Secrets Manager, GCP Secret Manager, Azure Key Vault, HashiCorp Vault, and
Consul KV. Each backend has a Python SDK that is large, cloud-specific, and
should not be a mandatory dependency.

The question is where these source implementations live and how users opt into
their SDK dependencies.

## Decision Drivers

- A user installing `confiq` for file-based config should not pull in boto3,
  the GCP client library, or hvac transitively.
- Source implementations must satisfy the same `Source` protocol
  (`name: str`, `fetch() -> Mapping[str, Any]`) regardless of backend.
- The `confiq.sources` entry-point group already exists for truly external
  sources; it should remain available for enterprise or custom backends.
- Maintenance burden grows with the number of separate distribution packages.
- Import ergonomics: users should not need to know which PyPI package contains
  `AwsSecretsManagerSource` — a single `from confiq.sources import
  AwsSecretsManagerSource` should always work once the extra is installed.

## Considered Options

- **Option A: Built-in source classes with `[aws]`, `[gcp]`, `[azure]`,
  `[vault]`, `[consul]` extras** — implementations live in
  `confiq.sources._aws`, `._gcp`, etc.; SDK imports are deferred to
  instantiation time; missing extras surface as `ImportError` at instantiation
  with a `pip install confiq[X]` message.
- **Option B: Separate PyPI packages** — `confiq-aws`, `confiq-gcp`, etc., each
  registering their source class via the `confiq.sources` entry-point group.

## Decision Outcome

Chosen option: **Option A: Built-in source classes with optional extras**,
because it minimises friction for the common case (one install command, one
import path, one place to maintain protocol compatibility) while keeping the
lazy-import boundary that prevents SDK bleed for users who do not use cloud
sources.

### Consequences

- `confiq`'s `sources/` subpackage grows by one module per cloud provider.
  The growth is bounded and each module is small (one class, one `_require`
  helper, deferred SDK imports).
- `import confiq` never triggers boto3, hvac, or any cloud SDK import. Only
  constructing a cloud source class will attempt the import.
- Users who need a backend confiq does not provide natively still reach for the
  `confiq.sources` entry-point group — Option A does not close that door.
- Each cloud source module independently checks its dependency at instantiation
  time. There is no shared `MissingDependencyError` type in `errors.py` for
  this category of failure; the raised `ImportError` message is sufficient for
  the install-guidance use case. If a typed `MissingDependencyError` is needed
  in a future version, it belongs in `errors.py` and the cloud sources should
  be updated to raise it.

## Pros and Cons of the Options

### Option A: Built-in Sources with Extras

- Good, because `from confiq.sources import AwsSecretsManagerSource` always
  resolves to the same module path, regardless of which extras are installed.
  No entry-point discovery required for the built-in backends.
- Good, because protocol compatibility is enforced in one repository with one
  test suite.
- Good, because `import confiq` carries zero cloud SDK weight — lazy imports
  are deferred to the first constructor call.
- Neutral, because `confiq`'s source tree grows with each new provider. The
  growth is one small file per provider and is bounded by the set of providers
  worth supporting centrally.
- Bad, because adding a new built-in backend requires a confiq release.
  Third-party backends still use the entry-point group.

### Option B: Separate PyPI Packages

- Good, because each cloud package releases independently and carries no
  confiq-release dependency for new features.
- Bad, because users must know which package to install for each backend
  (`pip install confiq-aws` vs. `pip install confiq[aws]`).
- Bad, because each package maintainer must track and satisfy the `Source`
  protocol independently — protocol drift becomes possible across packages.
- Bad, because the entry-point registration path adds startup latency and a
  failure mode (entry point not yet installed, stale distribution metadata)
  that the built-in path does not have.
