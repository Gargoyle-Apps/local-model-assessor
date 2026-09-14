---
name: lma-db-core
description: "Init, migrate, and query the LMA SQLite database; inventory present/removed ledger; data flow map and key queries."
triggers:
  - init database
  - migrate schema
  - query db
  - database setup
  - schema
  - db missing
  - migrate
  - schema error
  - data flow
  - key queries
  - inventory status
  - reconcile inventory
  - removed models
dependencies: []
version: "1.3.0"
---

# LMA Database Core

## When to use this skill

Load when the user needs to initialize, migrate, or query the database; when a script reports a missing DB or column; when inventory is out of date vs `ollama list`; or when you need to understand the data flow between scripts.

## Instructions

### 1. Database location

- **Path:** `model-data/model-assessor.db` under the resolved LMA root (SQLite).
- **Env overrides:** `LMA_DB` selects an explicit DB for every consumer. Without it, `LMA_ROOT` relocates the default for Python scripts, `query-db.sh`, `init-db.sh`, and `migrate-schema.sh`.
- **Optional LMO:** LMO may consume this DB via `LMA_DB` / `LMA_ROOT`. Hardware and software YAML may live in LMO; resolve with `./scripts/py scripts/lma_paths.py`. See `lma-lmo-sidecar` and `integrations/lmo/lma-lmo-contract.md`.

### 2. Init and migrate

| Command | Purpose |
|---------|---------|
| `./scripts/init-db.sh` | Create an empty DB from `scripts/schema.sql`. |
| `./scripts/migrate-schema.sh` | Apply schema migrations (adds `assessed_at`, provenance, inventory_status, `provisioned_models` if missing). |

If a script errors with "no such table" or "no such column," run `./scripts/migrate-schema.sh`.

### 3. Query the database

```bash
./scripts/query-db.sh "SQL"
```

Always pass the SQL as a quoted string argument. No args opens an interactive shell (avoid in agent workflows).

### 4. Key queries

```bash
./scripts/query-db.sh "SELECT model_id, vram, class, tps FROM models WHERE COALESCE(inventory_status,'present')='present' ORDER BY vram"
./scripts/query-db.sh "SELECT model_id FROM role_model WHERE role='coding' AND variant='primary'"
./scripts/query-db.sh "SELECT model_id FROM constraint_model WHERE constraint_name='has_vision'"
./scripts/query-db.sh "SELECT value FROM meta WHERE key='last_ollama_scan'"
./scripts/query-db.sh "SELECT model_id, inventory_status, removed_at, removed_at_confidence FROM models WHERE inventory_status='removed' ORDER BY model_id"
./scripts/query-db.sh "SELECT alias, base_model_id, role, num_ctx, is_active FROM provisioned_models ORDER BY role"
./scripts/query-db.sh "SELECT chain_text FROM decision_tree WHERE need_key='need_vision'"
./scripts/query-db.sh "SELECT * FROM rag_pipeline"
./scripts/query-db.sh "SELECT role_name FROM task_category WHERE category='writing'"
```

### 5. Data flow map

| Script / Prompt | Inputs | Outputs |
|-----------------|--------|---------|
| `init-db.sh` | `scripts/schema.sql` | `model-data/model-assessor.db` |
| `import-profiles.py` | resolved hardware/software YAML (`lma_paths.py`; LMO or local) | DB (`hardware_profile`, `software_profile`) |
| `add-model-from-yaml.py` | `model-data/new-models.yaml` | DB (`models`, `role_model`, `constraint_model`, `model_docs`, `provisioned_models`); writes `model-data/modelfile/*.mf` |
| `reconcile-inventory.py` | DB + `ollama list` | `models.inventory_status` / `removed_at` / `removed_at_confidence`; optional Granite 4.0 history seed |
| `export-assessed-models.py` | DB | `model-data/assessed-models.md` (omits superseded and `inventory_status=removed`) |
| `generate-ide-config.py` | DB (`provisioned_models`, `models`) | `integrations/IDE-model-management/<app>/` config files |
| `sweep-ide-config.py` | DB + `ollama list` + `software-profile.yaml` | Sync `is_active`, regenerate IDE configs, deploy Continue to `~/.continue/config.yaml` |
| `generate-stack-handoff.py` | DB (`provisioned_models` or `role_model` for `embedding`) | `integrations/embed-retrieval-stack/out/` |
| `ollama-search.md` → `model-assessment-prompt.yaml` → `add-model-from-yaml.py` | Ollama popular page, `hardware-profile.yaml` | DB, `assessed-models.md` |

### 6. Architecture one-liners

- **Scripts (flags):** `query-db.sh "SQL"` — always pass SQL string. `init-db.sh` / `migrate-schema.sh` — empty DB / schema migrations. `reconcile-inventory.py --from-ollama` / `--seed-history` / `--dry-run`.
- **Python:** `./scripts/py scripts/<name>.py` (see `lma-python-env` skill). `add-model-from-yaml.py` — provenance via args or env. `export-assessed-models.py [path]`. `import-profiles.py [db] [--allow-mock]`. `generate-ide-config.py --target continue|cline [--active-only] [--dry-run]`. `sweep-ide-config.py` — run after model add/remove or clone create (see `lma-ide-config` skill). `generate-stack-handoff.py [--output-dir DIR]`.
- **Env:** `LMA_DB` overrides the DB path for every consumer. Without it, `LMA_ROOT` relocates the default DB for Python scripts and DB shell wrappers. `LMA_HARDWARE_PROFILE`, `LMA_SOFTWARE_PROFILE`, and `LMO_ROOT` are optional LMO sidecar overrides. `LMA_ALLOW_MOCK=1` is an explicit per-process opt-in for mock/dry-run profiles; do not set it globally.

### 7. Hardware budget and co-run rule

```bash
./scripts/py scripts/lma_paths.py
```

Effective budget ≈ `total_available - os_headroom_gb` on the resolved hardware YAML.

**Co-run rule:** `(model_vram + concurrency_reserve) < total_available` → can co-run. Heavy Lifters (30–48 GB) run solo.

## Notes

- The DB file is **gitignored** — never commit it.
- Schema source of truth is `scripts/schema.sql`; see provenance column comments at the top.
- **Inventory:** `models.inventory_status` is `present` (default) or `removed`. Removed rows stay in the DB. `removed_at` is optional; `removed_at_confidence` is `authoritative` (seen missing in `ollama list` now) or `best_guess` (reconstructed from git/docs). YAML import does not touch these columns. Run `./scripts/py scripts/reconcile-inventory.py --from-ollama` after `migrate-schema.sh`. Add `--seed-history` only to insert known-dropped Granite 4.0 rows.
