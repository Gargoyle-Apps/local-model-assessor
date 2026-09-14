---
name: lma-model-prune
description: "Supersede a model with a newer generation, mark inventory_status=removed with optional when/confidence, OR queue a model for deletion via user_flag_for_deletion, then remove from Ollama and clean up clones."
triggers:
  - prune model
  - supersede model
  - replace model
  - remove old model
  - retire model
  - model cleanup
  - drop model
  - flag for deletion
  - free up space
  - delete queue
  - what can I delete
  - deletion candidates
  - reconcile inventory
  - mark removed
dependencies:
  - lma-db-core
  - lma-ide-config
version: "1.3.0"
---

# LMA Model Prune

## When to use this skill

Two distinct cleanup paths share this skill:

1. **Supersede** (immediate full prune) — a newer dot release or major release of a model family makes an older entry redundant. There is a direct successor. Run §A "Supersede a model" end-to-end.
2. **Soft-delete queue** (deferred cleanup) — the user wants to mark a model for future removal because they're freeing space, retiring a niche specialist, or otherwise want it gone but **without** a replacement model taking its slot. Run §B "Queue for deletion" to set the flag, and §C "Process the deletion queue" later when the user explicitly asks to clean up.

> **Hard rule:** Never set or act on `user_flag_for_deletion` proactively. The flag is set ONLY when the user explicitly asks ("flag X for deletion", "queue X for removal"). The flag is acted on ONLY when the user explicitly asks to clean up flagged models ("free up space", "process the deletion queue", "actually delete what I flagged"). Do not assume.

## Concepts

- **`models.superseded_by`** — stores the `model_id` of the replacement. `NULL` = no successor recorded; non-NULL = superseded.
- **`models.inventory_status`** — `present` (default, still in the catalog) or `removed` (gone from the local fleet; row kept). Orthogonal to `superseded_by`: a model can be superseded and still installed, or removed with no successor.
- **`models.removed_at`** — optional UTC timestamp (`%Y-%m-%d %H:%M:%S`). NULL means "removed, when unknown".
- **`models.removed_at_confidence`** — `authoritative` (observed missing in `ollama list` or `ollama rm` just ran) | `best_guess` (reconstructed from git/docs) | NULL.
- **`models.removal_notes`** — short provenance for the guess or the rm.
- **`models.user_flag_for_deletion`** — `INTEGER 0/1`. Set by the user; **does not** hide the model from selection, export, or IDE config (still usable until you actually clean it up). It is purely a queue marker.
- **`models.user_flag_for_deletion`** — `INTEGER 0/1`. Set by the user; **does not** hide the model from selection, export, or IDE config (still usable until you actually clean it up). It is purely a queue marker.
- **`provisioned_models.user_flag_for_deletion`** — same semantics, applied to clones. When the user flags a base model, also flag all of its clones unless they specify otherwise.
- **`superseded_by` is honored automatically only in `export-assessed-models.py`** (superseded rows are omitted from the markdown export). **`inventory_status=removed` is also omitted** from that export. Role selection queries and `generate-ide-config.py` do **not** filter on `superseded_by` unless you complete the prune steps in §A.3/§A.4 (repoint roles, regenerate IDE config). Prefer `WHERE COALESCE(inventory_status,'present')='present'` in selection SQL. **Flagged-only** models (no supersede, still `present`) are NOT excluded anywhere until deletion is processed in §C.
- Rows are never `DELETE`d from `models` on supersede or inventory-removed — provenance stays. After §C you may keep the row with `inventory_status=removed` (recommended) or hard-delete only on explicit confirmation. `provisioned_models` rows for a deleted base may be hard-deleted only as part of §C.
- The `user_flag_for_deletion` flag is preserved across YAML re-imports (`add-model-from-yaml.py` UPSERT does not touch it) — confirmed by `tests/test_ingestion_end_to_end.py::test_user_flag_for_deletion_preserved_across_reimport`.

## Change-management rules (mandatory)

Every direct SQL write here must update the provenance trio on each touched row:

- `updated_at` → current UTC timestamp (`%Y-%m-%d %H:%M:%S`).
- `updated_by` → assessor name (CLI: model id or person; default `human` if unattributed).
- `updated_by_type` → one of `local` | `cloud` | `human`.

Set them as session vars at the top of each prune run:

```bash
DB=model-data/model-assessor.db
NOW=$(date -u +"%Y-%m-%d %H:%M:%S")
BY="human"            # or the model id that decided the prune
BYT="human"           # human | local | cloud
```

Then include them in every `UPDATE`. Example:

```sql
UPDATE models SET superseded_by='<new>', updated_at='$NOW', updated_by='$BY', updated_by_type='$BYT'
  WHERE model_id='<old>';
```

`created_at` / `created_by` / `created_by_type` are write-once — never overwrite them.

## §A. Supersede a model (direct replacement exists)

### 1. Identify the pair

Confirm the **old** model and the **new** model that replaces it. They should overlap on:
- Similar parameter count / VRAM footprint.
- Same or superset of capabilities (vision, tools, reasoning).
- Same family lineage or direct successor on the upstream card.

```bash
./scripts/query-db.sh "SELECT model_id, vram, class, vision, tools, reasoning FROM models WHERE superseded_by IS NULL AND COALESCE(inventory_status,'present')='present' ORDER BY model_id"
```

### 2. Mark superseded

```bash
sqlite3 "$DB" "UPDATE models SET superseded_by='<new_model_id>',
  updated_at='$NOW', updated_by='$BY', updated_by_type='$BYT'
  WHERE model_id='<old_model_id>'"
```

Verify:

```bash
./scripts/query-db.sh "SELECT model_id, superseded_by FROM models WHERE superseded_by IS NOT NULL"
```

### 3. Deactivate and remove provisioned clones

List clones for the old base:

```bash
./scripts/query-db.sh "SELECT alias, role, variant FROM provisioned_models WHERE base_model_id='<old_model_id>'"
```

Remove each clone from Ollama and mark inactive in the DB:

```bash
ollama rm <alias>
sqlite3 "$DB" "UPDATE provisioned_models SET is_active=0,
  updated_at='$NOW', updated_by='$BY', updated_by_type='$BYT'
  WHERE base_model_id='<old_model_id>'"
```

### 4. Clean up role and constraint assignments

If the new model is **not** already assigned to the role the old one held, **reassign first** (don't lose the slot):

```bash
sqlite3 "$DB" "UPDATE role_model SET model_id='<new_model_id>',
  updated_at='$NOW', updated_by='$BY', updated_by_type='$BYT'
  WHERE role='<role>' AND variant='<variant>' AND model_id='<old_model_id>'"
```

If the new model is **already** assigned to the same `(role, variant)` (PK conflict), use `UPDATE` on the existing row instead and `DELETE` the redundant variant pointing at the old model. Then drop any leftover rows for the old model:

```bash
sqlite3 "$DB" "DELETE FROM role_model WHERE model_id='<old_model_id>'"
sqlite3 "$DB" "DELETE FROM constraint_model WHERE model_id='<old_model_id>'"
```

`role_model` PK is `(role, variant)`. If you need to demote (not delete) the old model to a different variant, `INSERT` the new variant row first, then `UPDATE` the original.

### 5. Remove the base model from Ollama

```bash
ollama rm <old_model_id>
sqlite3 "$DB" "UPDATE models SET inventory_status='removed',
  removed_at='$NOW', removed_at_confidence='authoritative',
  removal_notes='ollama rm after supersede',
  updated_at='$NOW', updated_by='$BY', updated_by_type='$BYT'
  WHERE model_id='<old_model_id>'"
```

### 6. Remove stale Modelfiles

Delete `.mf` files for superseded clones from `model-data/modelfile/`:

```bash
rm model-data/modelfile/<old-alias-pattern>*.mf
```

### 7. Regenerate exports and sweep IDE config

```bash
./scripts/py scripts/export-assessed-models.py
./scripts/py scripts/sweep-ide-config.py
```

The export now prints a summary line listing superseded models that were excluded.

### Supersede checklist

- [ ] Old model confirmed as redundant (same size class, capabilities covered by successor).
- [ ] `models.superseded_by` set to the replacement `model_id`.
- [ ] Provisioned clones deactivated (`is_active=0`) and removed from Ollama.
- [ ] `role_model` / `constraint_model` rows cleaned or reassigned.
- [ ] Base `ollama rm` run **and** `inventory_status=removed` with `removed_at_confidence=authoritative`.
- [ ] Stale `.mf` files deleted from `model-data/modelfile/`.
- [ ] `assessed-models.md` regenerated; superseded models excluded.
- [ ] IDE config swept (`sweep-ide-config.py`).

---

## §B. Queue for deletion (no successor; deferred cleanup)

Use when the user explicitly asks to flag a model for future removal — typical phrasings: "flag X for deletion", "queue X to be cleaned up later", "I want to remove this when I free space". The flag is set, but **nothing else changes**: the model stays usable, stays in selection, stays in exports.

### 1. Confirm scope

Ask (or confirm from context) whether to flag:
- The **base** model only.
- The **clones** only.
- **Both** (typical — the user said "pulled and cloned"; default to both unless told otherwise).

```bash
./scripts/query-db.sh "SELECT model_id FROM models WHERE model_id LIKE '<pattern>%'"
./scripts/query-db.sh "SELECT alias, base_model_id FROM provisioned_models WHERE base_model_id LIKE '<pattern>%'"
```

### 2. Set the flag with provenance

```bash
DB=model-data/model-assessor.db
NOW=$(date -u +"%Y-%m-%d %H:%M:%S")
BY="<assessor>"   # model id or person; default 'human'
BYT="human"       # human | local | cloud

sqlite3 "$DB" "UPDATE models
  SET user_flag_for_deletion=1,
      updated_at='$NOW', updated_by='$BY', updated_by_type='$BYT'
  WHERE model_id='<model_id>'"

sqlite3 "$DB" "UPDATE provisioned_models
  SET user_flag_for_deletion=1,
      updated_at='$NOW', updated_by='$BY', updated_by_type='$BYT'
  WHERE base_model_id='<model_id>'"
```

### 3. Confirm

```bash
./scripts/query-db.sh "SELECT model_id, user_flag_for_deletion, updated_at, updated_by FROM models WHERE user_flag_for_deletion=1"
./scripts/query-db.sh "SELECT alias, base_model_id, user_flag_for_deletion FROM provisioned_models WHERE user_flag_for_deletion=1"
```

### Unflag

If the user changes their mind:

```bash
sqlite3 "$DB" "UPDATE models SET user_flag_for_deletion=0, updated_at='$NOW', updated_by='$BY', updated_by_type='$BYT' WHERE model_id='<model_id>'"
sqlite3 "$DB" "UPDATE provisioned_models SET user_flag_for_deletion=0, updated_at='$NOW', updated_by='$BY', updated_by_type='$BYT' WHERE base_model_id='<model_id>'"
```

---

## §C. Process the deletion queue (user explicitly asks to clean up)

Trigger phrases: "free up space", "clean up the flagged models", "process the deletion queue", "what can I delete?", "actually delete what I flagged".

### 1. Show the queue

Show both signals so the user sees the full picture before any destructive action:

```bash
./scripts/query-db.sh "SELECT model_id, vram, class, user_flag_for_deletion, superseded_by, updated_at, updated_by FROM models WHERE user_flag_for_deletion=1 OR superseded_by IS NOT NULL ORDER BY user_flag_for_deletion DESC, model_id"
./scripts/query-db.sh "SELECT alias, base_model_id, role, variant, is_active, user_flag_for_deletion FROM provisioned_models WHERE user_flag_for_deletion=1 ORDER BY base_model_id, role"
```

Show disk impact (Ollama base + clone manifests share layers, so this is conservative):

```bash
ollama list | rg -e '<model_id>'
```

### 2. Confirm with the user

Present the list and ask which entries to actually delete this round. **Do not** assume "all flagged means delete all flagged" without explicit confirmation — the flag is a queue, not a commitment.

### 3. For each confirmed model

#### a. Remove clones from Ollama and the DB

```bash
for ALIAS in $(sqlite3 "$DB" "SELECT alias FROM provisioned_models WHERE base_model_id='<model_id>' AND user_flag_for_deletion=1"); do
  ollama rm "$ALIAS" || true
done
sqlite3 "$DB" "DELETE FROM provisioned_models WHERE base_model_id='<model_id>' AND user_flag_for_deletion=1"
```

> **Why hard-delete clones here?** Unlike supersede (§A) where clones are kept inactive for audit, the flag-driven path means the user wants the slot gone. Provenance lives on the parent `models` row.

#### b. Remove role / constraint references

```bash
sqlite3 "$DB" "DELETE FROM role_model WHERE model_id='<model_id>'"
sqlite3 "$DB" "DELETE FROM constraint_model WHERE model_id='<model_id>'"
```

#### c. Remove the base model from Ollama

```bash
ollama rm <model_id>
```

#### d. Decide on the `models` row

Two options, surface both to the user:
- **Keep for history** (recommended): leave the row, clear the flag, set `inventory_status=removed` with `removed_at_confidence=authoritative`.
  ```bash
  sqlite3 "$DB" "UPDATE models SET user_flag_for_deletion=0,
    inventory_status='removed',
    removed_at='$NOW', removed_at_confidence='authoritative',
    removal_notes='processed deletion queue; ollama rm',
    updated_at='$NOW', updated_by='$BY', updated_by_type='$BYT'
    WHERE model_id='<model_id>'"
  ```
- **Hard delete**: only if the user explicitly says they want the assessment gone.
  ```bash
  sqlite3 "$DB" "DELETE FROM model_docs WHERE model_id='<model_id>'"
  sqlite3 "$DB" "DELETE FROM models WHERE model_id='<model_id>'"
  ```

#### e. Stale Modelfiles

```bash
rm -f model-data/modelfile/<base-pattern>*.mf
```

### 4. Regenerate the report and sweep IDE config

```bash
./scripts/py scripts/export-assessed-models.py
./scripts/py scripts/sweep-ide-config.py
```

### Cleanup checklist

- [ ] User confirmed which flagged entries to delete this round.
- [ ] Clones removed from Ollama (`ollama rm <alias>`) and from `provisioned_models`.
- [ ] `role_model` / `constraint_model` rows cleared for the base.
- [ ] `ollama rm <base>` run.
- [ ] `models` row either retained-with-flag-cleared or hard-deleted, per user choice.
- [ ] Stale `.mf` files removed from `model-data/modelfile/`.
- [ ] `assessed-models.md` regenerated.
- [ ] IDE config swept (`sweep-ide-config.py`).

---

## Querying history & the queue

```bash
# Superseded models
./scripts/query-db.sh "SELECT model_id, class, vram, superseded_by, updated_at, updated_by FROM models WHERE superseded_by IS NOT NULL ORDER BY updated_at"

# Removed from local inventory (history kept)
./scripts/query-db.sh "SELECT model_id, inventory_status, removed_at, removed_at_confidence, removal_notes FROM models WHERE inventory_status='removed' ORDER BY removed_at"

# Flagged-but-not-yet-deleted
./scripts/query-db.sh "SELECT model_id, class, vram, updated_at, updated_by FROM models WHERE user_flag_for_deletion=1 ORDER BY updated_at"
./scripts/query-db.sh "SELECT alias, base_model_id, role, variant, updated_at, updated_by FROM provisioned_models WHERE user_flag_for_deletion=1 ORDER BY updated_at"
```

To sync `inventory_status` from the live `ollama list` (authoritative `removed_at=now`) and/or seed known Granite 4.0 history (best-guess dates):

```bash
./scripts/py scripts/reconcile-inventory.py --dry-run --from-ollama --seed-history
./scripts/py scripts/reconcile-inventory.py --from-ollama --seed-history
```

## Notes

- Never `DELETE FROM models` for the supersede path — always use `superseded_by` to preserve history. For the flag-driven path, hard delete is allowed only on explicit user confirmation in §C.3.d.
- If a superseded model needs to come back (e.g. successor regresses), clear the column **and** inventory: `UPDATE models SET superseded_by=NULL, inventory_status='present', removed_at=NULL, removed_at_confidence=NULL, removal_notes=NULL, updated_at='$NOW', updated_by='$BY', updated_by_type='$BYT' WHERE model_id='...'`.
- `provisioned_models` rows for superseded bases are kept (with `is_active=0`) for audit; they will not appear in active config generation.
- `user_flag_for_deletion` is preserved across `add-model-from-yaml.py` re-imports, so re-running an assessment will not silently un-flag anything.
- Pure role reassignments (no supersede) follow the same provenance rules — every `UPDATE role_model` / `INSERT role_model` must stamp `updated_at/by/by_type`.
