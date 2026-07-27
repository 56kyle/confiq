---
status: accepted
date: 2026-07-06
---
# Deep-Merge Conflict Semantics: Uniform Overwrite, Validation as the Refusal Locus

## Context and Problem Statement

design_d §6.3 specifies deep-merge for dicts and wholesale replacement for lists, but is
silent on two cases `deep_merge` must handle deterministically:

1. **`None` as a value.** A higher-precedence layer maps `key: None` over a lower non-None
   value — does `None` overwrite, or is it skipped as "absent"?
2. **Type conflict across layers.** A higher layer supplies a scalar where a lower layer
   had a dict (or a dict where the lower had a scalar) — is deep-merge undefined here, and
   what happens?

The resolver applies the merge at step 3 of the pipeline (design_d §6.2), **before**
adapter resolution (step 4) and validation (step 6). The merge is therefore
schema-agnostic (ADR 0003): it cannot know whether a given shape is legal for the declared
schema.

## Decision Drivers

- **Refusal over degradation (ADR 0034)** pulls toward raising on a silent subtree
  clobber — a scalar quietly discarding a configured nested object is the invisible
  coupling the principle targets.
- **Declared guarantees are honored, never subverted.** A union field
  (`db: NestedModel | str`) makes a scalar-over-dict conflict *valid*: a defaults layer
  supplies the object form, a higher layer supplies the connection-string form. A
  merge-time raise would reject config the user's own schema permits.
- **Validation already refuses the genuinely-wrong case, with provenance.** In schema'd
  mode a wrong shape fails at step 6 as a `ConfigValidationError` naming the field and its
  winning source; a legitimate union validates against the matching branch. A merge-time
  raise cannot improve on this for the bad case and wrongly rejects the union case — it is
  strictly worse.
- **Keeping the merge schema-agnostic avoids a policy parameter.** Special-casing schema'd
  vs. schemaless at merge time would thread a coarse policy flag derived from schema
  presence into `deep_merge`, coupling the merge to a distinction it otherwise never makes.
- **`None`-as-unset lives in the sources, not the merge (design_d §10.3).** CLI/env express
  *unset* by omitting the key or via `argparse.SUPPRESS` sentinels, so a `None` that reaches
  the merge is an explicit null, not "I didn't touch this."

## Considered Options

- **Option A: Uniform overwrite; validation is the refusal locus.** `deep_merge` never
  raises on structure; the higher layer replaces on any type conflict; `None` overwrites.
  Schema'd mode refuses wrong shapes at validation; schemaless overwrites (consistent with
  the type-safety opt-out, design_d §2.9/§4.6).
- **Option B: Raise at merge on type conflict for schema'd mode, overwrite for
  schemaless.** Needs a policy parameter and over-refuses union fields.
- **Option C: Overwrite everywhere and treat `None` as absent.** Loses the ability to
  explicitly null a value and couples merge to a `None == unset` convention §10.3 places in
  the sources.

## Decision Outcome

Chosen option: **Option A**, with the two silent cases pinned as:

- **`None` is data.** A `None` in a higher layer overwrites a lower non-None value.
- **Type conflict overwrites wholesale.** The higher-precedence layer replaces whatever is
  below regardless of type; `deep_merge` never raises on structure. Refusal for schema'd
  mode happens at validation (step 6) with provenance attached; schemaless silently
  overwrites as an accepted consequence of opting out of type safety.

This keeps the merge genuinely schema-agnostic (ADR 0003 reaffirmed), preserves union
fields, and honors refusal-over-degradation where guarantees actually live — the schema'd
validation step, which refuses before any value is returned from `load()`.

### Consequences

**Positive:**
- One merge behaviour for both schema'd and schemaless modes; no policy parameter.
- `load(schema=None, ...)` faithfully reflects the same merged shape the schema'd path
  produces — a reliable debugging view.
- Union fields whose shape differs across layers resolve correctly.

**Negative:**
- The refusal for a subtree clobber is the validation message ("field `db`: expected
  `NestedModel`, got `str` [from source]") rather than a merge-time "source A's subtree was
  clobbered by source B's scalar." Less pointed, enrichable later if it bites.
- Schemaless mode has no safety net: a scalar clobbering a dict silently yields a
  `SchemalessConfig` where later nested access raises at read time. This is inherent to the
  type-safety opt-out, not a defect.

### Implementation note (provenance is co-produced, not post-computed)

Because a wholesale overwrite can replace a dict subtree with a scalar, provenance cannot
be computed by an independent post-merge leaf walk — the stale sub-path entries would
desync from the merged structure. `deep_merge` therefore co-produces provenance during the
merge, purging sub-path entries when a subtree is overwritten. `merge_sources` folds the
sources (lowest precedence first) and returns a single `ResolvedSnapshot` (ADR 0023);
`deep_merge` remains a module-private path-prefix worker, not part of the public surface.

Relates to design_d §6.3 and reaffirms ADR 0003 (schema-agnostic merge with provenance).
