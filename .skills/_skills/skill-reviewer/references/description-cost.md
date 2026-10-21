# Description cost and routing

Load for Q1/Q7 when descriptions change or discovery cost warrants a finding. Review only changed skills; aggregate warnings may justify a separate **skill-catalog-maintainer** audit, not edits to siblings.

## Review procedure

1. Read the description without harness `triggers`, prefix conventions, index notes, or body text. Confirm that it states the outcome, selection context, and distinctions needed to avoid near misses.
2. Identify removable procedure, repeated outcome lists, or body summaries. Keep natural language, environmental requirements that affect selection, necessary exclusions, and routing-relevant safety boundaries. Do not weaken body approval or execution gates.
3. Propose a concrete alternative only when it preserves that selection contract. Measure the decoded description string in characters, excluding YAML quotes; show before/after counts. If aggregate native metadata is available, report its scope and counting method separately. Neither the 1,024-character spec cap nor a configurable warning is a target length.
4. Run the same positive and near-miss prompts against the original and proposed descriptions, with expected answers hidden. Supply the same competing skill metadata and host/model settings to both runs. Test native matching without harness-only hints; record selected skill or no match, expected outcome, and regressions. Keep descriptions self-sufficient even if fallback tests also pass.
5. Accept shortening only when routing outcomes are preserved. Explain why any longer description remains necessary. If no routing runner is available, provide fixtures and label the result as an unexecuted evaluation plan or manual assessment; JSON parsing is not a routing evaluation.

A finding needs the removable text, a safe concrete replacement, character counts, and routing evidence. A warning or long description alone does not fail review. Treat a proposed rewrite with regressions as a rejected candidate, not an improvement with acceptable token savings.

## Worked examples

These synthetic examples illustrate review decisions, not changes to downstream skills. The exact strings and expected cases are in `references/description-evals.json`; use that file when running these examples. Counts below exclude the surrounding quotation marks.

### Safe shortening: 252 → 131 characters

Before: “Reviews deployment configuration changes for Kubernetes services. Use when reviewing a Kubernetes deployment diff. Reads manifests, checks resource requests, examines probes, compares replica settings, and reports deployment risks with suggested fixes.”

After: “Reviews Kubernetes deployment configuration diffs for deployment risks. Use when reviewing changes to Kubernetes service manifests.”

The removed manifest-reading and inspection sequence belongs in the body. Both descriptions select a Kubernetes deployment-diff review, exclude a Docker Compose review, and exclude a request to deploy an already approved release. Validate those outcomes in the target host before accepting an actual rewrite.

### Necessary longer description: keep 312 characters

“Previews restoration of PostgreSQL backups in a disposable staging database and, after explicit confirmation, performs that restore. Use when testing backup recoverability in staging. Requires a disposable PostgreSQL staging target; excludes production recovery, backup creation, and database migration planning.”

Database type, disposable staging, the preview/confirmation contract, and neighboring workflow exclusions affect selection. Keep these distinctions even under aggregate pressure. The positive case is a staging recoverability test; production restore, backup creation, and migration planning are near misses. Length alone does not justify a finding or require preserving every word if a verified alternative exists.

### Over-compressed regression: reject 312 → 44 characters

Replacing the preceding description with “Restores database backups. Use for recovery.” loses PostgreSQL, disposable staging, confirmation context, and exclusions. It now invites production PostgreSQL or MySQL recovery requests. Restore the missing scope in discovery text and preserve the full body gates; adding keywords to `triggers` cannot repair native discovery.

## Separate the measurements

Native names/descriptions, activated bodies/dependencies/references, and fallback reads are different costs. Count each with its own unit and provenance; do not claim an index reduction lowers native metadata. The downstream consumer motivating this guidance estimated 15,890 native-metadata characters while its fallback index shrank from 52,833 to 38,441 bytes. Those are consumer measurements, not this kit's baseline or host token limits.
