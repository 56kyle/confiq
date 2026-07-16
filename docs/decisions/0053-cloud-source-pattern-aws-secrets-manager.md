---
status: accepted
date: 2026-07-15
---
# Cloud Sources: the Built-in Pattern, Established by AWS Secrets Manager

## Context and Problem Statement

ADR 0006 committed confiq to shipping cloud secret/param stores as built-in `SyncSource`s behind
extras (`confiq.source._aws` etc., SDK imported lazily). Stage 10 builds them — but research
showed the five backends' **local test methodologies differ sharply**: AWS has `moto` (a real
in-process mock), Vault/Consul have `-dev` server binaries, and **GCP + Azure have no local
emulator at all** (Azurite covers Blob/Queue/Table, *not* Key Vault; GCP ships no Secret Manager
emulator). So (project decision) Stage 10 is split into per-backend sub-stages, and **AWS is built
first** because its in-process test story is the strongest; the other four are deferred to a later
stage that will use real integration tests (live `-dev` servers / gated live creds), not
low-confidence hand-written fakes.

This ADR records the decisions made building the *first* cloud source — `AwsSecretsManagerSource` —
which establish the **reusable pattern** every later cloud source inherits.

## Decision Drivers

- One `Source` protocol regardless of backend (ADR 0006); the differences are addressing, auth,
  and payload shape, not the confiq-facing contract.
- The error taxonomy (ADR 0040/0041) and the flat-vs-structured source taxonomy (ADR 0048) already
  exist and must be applied, not re-invented, per backend.
- Sync-first built-ins (ADR 0035/0047): cloud SDKs are sync; an async built-in would be false
  structure.
- Test fidelity matters (the split's whole rationale) — the pattern must come with a real,
  low-infra test harness, not a self-referential fake.

## Decision Outcome

`AwsSecretsManagerSource(secret_id, *, region_name=None, profile_name=None, loader=None,
required=True, profile=None)`, and six decisions that generalize:

1. **Construction-time SDK import.** `import_optional("boto3", extra="aws")` runs in `__init__`,
   never at module top — so `import confiq.source` without boto3 stays fine (the class is imported
   eagerly, only construction imports the SDK), and a missing `[aws]` extra raises the branded
   `pip install confiq[aws]` `ImportError`, never a `SourceError` (ADR 0006/0041). **Pattern.**

2. **Secrets Manager is a *structured* source (ADR 0048).** `get_secret_value(SecretId=...)` →
   `SecretString` (one opaque string, conventionally a JSON config bundle) is parsed by **reusing a
   `Loader`** (default `JsonLoader`), inheriting `ensure_mapping`'s non-mapping refusal and
   empty→`{}` for free — exactly as `FileSource._decode` does. An optional `loader=` handles
   YAML/other secret bodies. Mapping-a-scalar-secret-to-one-field is out of scope (a secret models a
   *bundle*); no `aliases`. **Per-backend:** each cloud source declares structured vs flat.

3. **`SecretString` only.** A binary-only secret (`SecretBinary`, no `SecretString`) raises
   `SourceError` naming it — confiq can't model opaque bytes as a config bundle, and a silent
   base64 guess would be degradation over refusal (§2).

4. **The `profile` naming convention (binds ALL later cloud sources).** confiq's `Source` tag is
   `profile`; a backend's *credential* profile takes the SDK's own name — here `profile_name`
   (matching `boto3.session.Session(profile_name=...)`). No collision, and every future cloud source
   follows the same rule: `profile` = confiq tag, credential selectors = the SDK's native names.
   **Pattern.**

5. **Error taxonomy (ADR 0040/0041).** `except client.exceptions.ResourceNotFoundException` →
   `SourceNotFoundError`(if `required`) / `{}`; any other exception (other `ClientError`/
   `BotoCoreError`) → `SourceError(name, str(e)) from e`. `required=True` default (a secret pulled
   into config is normally critical; matches `FileSource`). **Pattern:** each backend maps its
   not-found exception to `SourceNotFoundError` and wraps the rest.

6. **AWS Parameter Store is deferred** to the flat-cloud batch — it's *flat*
   (`get_parameters_by_path` → many `/`-keyed params → `flat_to_nested` + `aliases`), a different
   ADR 0048 family from Secrets Manager's single structured blob. It will share `_aws.py` when built.

### Test methodology (the split's basis)
`AwsSecretsManagerSource` is tested with **`moto`** (`from moto import mock_aws`) — a real
in-process reimplementation of the service, the highest-fidelity option that needs no server or
container. The test tooling (`boto3` + `moto`) lives in a **dedicated `test-aws` dependency group**
(not `dev`), fsspec-style optional: the tests `pytest.importorskip` boto3/moto and skip when the
group isn't installed. Each later cloud backend gets its own test approach + tooling group
(GCP/Azure: gated live-integration tests, no local emulator; Vault/Consul: `-dev`-server subprocess
fixtures) — which is precisely why Stage 10 is split per backend rather than shipped as one.

### Consequences

**Positive:**
- The cloud-source pattern is concrete and proven against a real (mocked) backend; GCP/Azure/Vault/
  Consul instantiate the same five points with their own addressing/exception specifics.
- Reusing the `Loader` gives structured cloud secrets the same decode guarantees as files for free.
- The `profile`/credential-name convention prevents the collision from recurring per backend.

**Negative:**
- One structured backend (Secrets Manager) doesn't exercise the flat/`aliases` path — that lands
  with the first flat cloud source (Parameter Store / Consul). Accepted: establishing the structured
  pattern cleanly first keeps this ADR's statement uncluttered.
- The `test-aws` tooling is opt-in, so these tests skip in a bare environment (nox installs only
  `--group dev`). Consistent with how every other extra's tests already behave; a CI decision to
  install the extras/groups is separate.

## Relationship to prior ADRs
Instantiates ADR 0006 (built-in cloud sources + extras). Applies ADR 0040/0041 (error taxonomy) and
ADR 0048 (structured source, no aliases). Upholds ADR 0035/0047 (sync-only built-in). The `profile`
convention and the construction-time-import + Loader-decode template are the reusable core for the
remaining backends.
