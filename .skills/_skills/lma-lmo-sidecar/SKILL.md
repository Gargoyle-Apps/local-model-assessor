---
name: lma-lmo-sidecar
description: "Resolves optional Local Model Orchestrator (LMO) sidecar paths for hardware and software profiles, keeps LMA standalone when LMO is absent, and exports a local snapshot zip for LMO to study. Load when linking LMO, passing local paths between the two clones, or packing hardware, software, and the model DB."
triggers:
  - link LMO
  - Local Model Orchestra
  - local-model-orchestrator
  - LMO sidecar
  - LMA LMO contract
  - export LMO snapshot
  - hardware from LMO
  - pass local paths to LMO
  - mock hardware profile
  - dry-run profile
dependencies:
  - lma-python-env
  - lma-db-core
version: "1.1.0"
---

# LMA LMO Sidecar

## When to use this skill

Load when the user wants LMA to optionally work with a locally cloned [Local Model Orchestrator](https://github.com/Gargoyle-Apps/local-model-orchestrator) (LMO), to resolve hardware/software/DB paths, or to export a study zip for LMO.

Do not load for ordinary model assessment, selection, or IDE config when LMO is not mentioned. LMA stays fully usable without LMO.

## Instructions

### 1. Confirm optional, local-path sharing

Both repos must be cloned on this machine. Share **absolute paths**, not copies, as the live source of truth. Read `integrations/lmo/lma-lmo-contract.md` before changing ownership or inventing new filenames.

| Artifact | Owner when linked | LMA standalone fallback |
|----------|-------------------|-------------------------|
| Hardware YAML | LMO | `computer-profile/hardware-profile.yaml` |
| Software YAML | LMO | `computer-profile/software-profile.yaml` |
| Model SQLite | LMA | `model-data/model-assessor.db` |

These are the only two owner-published domains: LMA publishes model assessment and management state for LMO to read; LMO publishes live hardware and software inventory for LMA to read. Cross-repo access is read-only.

Never require LMO. If `LMO_ROOT` and `integrations/lmo/paths.yaml` are absent, continue with local profiles.

Resolve path existence first. Batch remaining questions (LMO clone path, unlink vs fix) in one message.

Keep the boundary minimal. Do not turn the sidecar into a command or event bus, shared workflow/task database, deployment or upgrade handshake, telemetry channel, store for LMO agent/approval/orchestration state, or reason to add LMO-specific LMA schema fields. Downstream application configuration remains outside this contract.

### 2. Resolve live paths

```bash
./scripts/py scripts/lma_paths.py
./scripts/py scripts/lma_paths.py --format json
```

Resolution order: `LMA_HARDWARE_PROFILE` / `LMA_SOFTWARE_PROFILE` / `LMA_DB` → gitignored `integrations/lmo/paths.yaml` → `LMO_ROOT` + `inventory/*.yaml` → LMA local files → templates.

Mock inventory is opt-in. The resolver recognizes `profile.mode: dry_run|dry-run|mock|simulated`, `profile.mock: true`, or `profile.physical_hardware_present: false` and rejects that profile by default. Only when the user explicitly requests a simulation or planning run, use:

```bash
./scripts/py scripts/lma_paths.py --allow-mock --format json
```

For another profile-consuming command, pass its `--allow-mock` flag or prefix it with `LMA_ALLOW_MOCK=1`. Confirm the JSON reports `allow_mock: true` and `hardware_profile.mock: true`. Keep mock YAML gitignored/untracked, label every derived result **simulated**, do not describe it as this host, and do not turn estimated throughput into a benchmark claim.

### 3. Activate a link (only if LMO is cloned)

1. Confirm the LMO clone path exists.
2. If `integrations/lmo/paths.yaml` already exists, print its `lmo_root` and profile paths and confirm before replacing. Otherwise copy `integrations/lmo/paths.template.yaml` to `integrations/lmo/paths.yaml` (gitignored) and set `lmo_root` plus profile paths, **or** export `LMO_ROOT`, `LMA_HARDWARE_PROFILE`, and `LMA_SOFTWARE_PROFILE`.
3. Re-run `./scripts/py scripts/lma_paths.py --format json` and check `linked` is true, files exist, and `mock` is false. If the user explicitly chose mock inventory, add `--allow-mock` and preserve that status in the result.
4. Import the resolved YAML into the DB: `./scripts/py scripts/import-profiles.py`. For an explicit mock exercise use `./scripts/py scripts/import-profiles.py --allow-mock`; the mock declaration remains in the stored YAML snapshot.

If LMO has not created `inventory/` yet, leave LMA on local `computer-profile/` files. Do not invent hardware facts.

### 4. Export a study snapshot

```bash
./scripts/py scripts/export-lmo-snapshot.py
```

Add `--allow-mock` only for an explicitly requested mock study pack.

Writes `ref/lma-lmo-snapshot.zip` (gitignored): live hardware YAML, software YAML, `model-assessor.db`, `schema.sql`, templates, contract. Tell the user the zip path. Treat it as a local study pack, not a live feed. It contains the full DB and absolute local paths; do not upload it to GitHub or send it outside the machine.

### 5. What LMO should read

Give LMO `LMA_ROOT` (this clone) and `LMA_DB` (resolved DB path). LMO must not write the catalog. After LMA assesses or prunes models, LMO re-reads the same DB path.

## Failure modes

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `PathResolutionError` | Env or `paths.yaml` points at a missing file | Fix the path; do not delete the override to "try local" unless the user wants to unlink |
| `mock profile requires explicit opt-in` | Resolved YAML declares simulated inventory | Use real inventory, or obtain an explicit mock/planning request and rerun with `--allow-mock` |
| `linked` is false with `LMO_ROOT` set | LMO has no `inventory/` YAML yet | Keep using LMA local profiles until LMO writes them |
| DB missing | Never initialized | `./scripts/init-db.sh` (honors `LMA_DB`) |

Load `references/trigger-evals.json` only when validating routing (should-trigger / should-not-trigger), not during a sidecar link or export.
