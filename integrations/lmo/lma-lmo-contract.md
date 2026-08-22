# LMA ↔ LMO sidecar contract (optional)

Local Model Assessor (LMA) and Local Model Orchestrator (LMO) may share
**absolute local paths** when both repos are cloned and activated on the same
machine. Neither repo is required for the other to function.

This document is the **LMA-side** commitment. LMO should mirror it in its own
tree once the sister issue is resolved.

## Ownership

| Artifact | Owner | Consumer | Standalone LMA fallback |
|----------|-------|----------|-------------------------|
| Hardware inventory YAML | LMO (when linked) | LMA | `computer-profile/hardware-profile.yaml` (from template) |
| Software inventory YAML | LMO (when linked) | LMA | `computer-profile/software-profile.yaml` (from template) |
| Model catalog SQLite | LMA | LMO | `model-data/model-assessor.db` |

LMA does not write LMO files. LMO does not write the LMA database. After LMO
updates hardware or software YAML, re-run `./scripts/py scripts/import-profiles.py`
so the last snapshot in SQLite matches the live files. LMO should read the live
LMA DB path; it does not need a copy.

## Path passing (no copies as source of truth)

Both sides pass **absolute filesystem paths** (env preferred; gitignored link
file as a convenience). Do not sync these artifacts over the network, and do
not treat a zip snapshot as live state.

### Environment

| Variable | Set by | Read by | Meaning |
|----------|--------|---------|---------|
| `LMA_ROOT` | operator / LMO | LMA, LMO | Absolute path to the LMA clone |
| `LMO_ROOT` | operator / LMA | LMA, LMO | Absolute path to the LMO clone |
| `LMA_DB` | operator / LMO | LMA, LMO | Absolute path to `model-assessor.db` |
| `LMA_HARDWARE_PROFILE` | operator / LMO | LMA | Absolute path to hardware YAML |
| `LMA_SOFTWARE_PROFILE` | operator / LMO | LMA | Absolute path to software YAML |

Explicit env paths must exist; a missing override is an error (misconfigured
link), not a silent fallback.

### Link files (gitignored)

LMA: copy `integrations/lmo/paths.template.yaml` → `integrations/lmo/paths.yaml`.

Proposed LMO mirror (LMO decides the directory name):

```yaml
lma_root: /absolute/path/to/Local-Model-Assessor
model_db: model-data/model-assessor.db   # relative to lma_root, or absolute
```

### Conventional LMO inventory (proposal)

Until LMO publishes its own layout, LMA looks under `LMO_ROOT` for:

- `inventory/hardware-profile.yaml`
- `inventory/software-profile.yaml`

If those files are absent, LMA keeps using its local `computer-profile/` files
or templates. Linking is opportunistic, not required.

## Formats LMO should preserve

Hardware and software YAML schemas are the tracked templates:

- `computer-profile/hardware-profile.template.yaml` – `vram_budget`, classes, concurrency, `context_strategy`
- `computer-profile/software-profile.template.yaml` – `ide`, agents, `model_runtime`

LMA assessment, IDE sweep, and VRAM gates expect those keys. Extra LMO-only
keys are fine; do not rename the keys LMA already documents.

The model catalog schema is `scripts/schema.sql`. Well-known tables for
orchestration: `models`, `role_model`, `constraint_model`, `provisioned_models`,
`hardware_profile`, `software_profile` (YAML snapshots from the last import).

## LMA resolver

```bash
./scripts/py scripts/lma_paths.py
./scripts/py scripts/lma_paths.py --format json
./scripts/py scripts/lma_paths.py --format env
```

Resolution order: env → `integrations/lmo/paths.yaml` → `LMO_ROOT` conventional
files → LMA local YAML/DB → templates (hardware/software only).

## Study snapshot (not the live contract)

```bash
./scripts/py scripts/export-lmo-snapshot.py
```

Writes gitignored `ref/lma-lmo-snapshot.zip` (hardware YAML, software YAML,
SQLite catalog, schema, templates, this contract). Use it to inspect formats.
Use path passing for day-to-day work.

## Standalone rule

If `LMO_ROOT` and `integrations/lmo/paths.yaml` are unset, and the `LMA_*`
profile env vars are unset, LMA behavior is unchanged from pre-sidecar
releases: local profiles plus `LMA_DB` / default `model-data/model-assessor.db`.
