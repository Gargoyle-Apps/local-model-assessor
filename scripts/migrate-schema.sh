#!/usr/bin/env bash
# Add schema columns introduced after initial release (assessed_at, etc.)
# and the provisioned_models table if missing.
# Run from repo root: ./scripts/migrate-schema.sh
# Safe to run multiple times; skips if column already exists.
#
# Env: LMA_DB overrides the SQLite file. Without it, LMA_ROOT relocates the
#   default model-data/model-assessor.db. Same contract as Python scripts.

set -e
SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="${LMA_ROOT:-$SCRIPT_ROOT}"
DB_PATH="${LMA_DB:-$REPO_ROOT/model-data/model-assessor.db}"

if [ ! -f "$DB_PATH" ]; then
  echo "No database at $DB_PATH — nothing to migrate."
  exit 0
fi

add_col_if_missing() {
  local table="$1"
  local col="$2"
  local def="$3"
  local exists
  exists=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM pragma_table_info('$table') WHERE name='$col'")
  if [ "$exists" -gt 0 ]; then
    echo "  $table.$col already exists"
  else
    echo "  Adding $table.$col"
    sqlite3 "$DB_PATH" "ALTER TABLE $table ADD COLUMN $col $def"
  fi
}

add_provenance() {
  local table="$1"
  echo "  Provenance columns for $table..."
  add_col_if_missing "$table" "created_at" "TEXT"
  add_col_if_missing "$table" "created_by" "TEXT"
  add_col_if_missing "$table" "created_by_type" "TEXT"
  add_col_if_missing "$table" "updated_at" "TEXT"
  add_col_if_missing "$table" "updated_by" "TEXT"
  add_col_if_missing "$table" "updated_by_type" "TEXT"
}

echo "Migrating schema..."
add_col_if_missing "models" "assessed_at" "TEXT"
add_col_if_missing "models" "runtime" "TEXT DEFAULT 'ollama'"
add_col_if_missing "models" "superseded_by" "TEXT"
add_col_if_missing "models" "user_flag_for_deletion" "INTEGER DEFAULT 0"

add_provenance "models"
add_provenance "role_model"
add_provenance "constraint_model"
add_provenance "task_category"
add_provenance "model_docs"

echo "  provisioned_models table..."
sqlite3 "$DB_PATH" <<'EOSQL'
CREATE TABLE IF NOT EXISTS provisioned_models (
  alias             TEXT PRIMARY KEY,
  base_model_id     TEXT NOT NULL,
  role              TEXT NOT NULL,
  variant           TEXT NOT NULL DEFAULT 'primary',
  num_ctx           INTEGER NOT NULL,
  temperature       REAL,
  num_predict       INTEGER,
  repeat_penalty    REAL,
  repeat_last_n     INTEGER,
  system_prompt     TEXT,
  modelfile_content TEXT NOT NULL,
  modelfile_path    TEXT NOT NULL,
  create_command    TEXT NOT NULL,
  pull_command      TEXT NOT NULL,
  is_active         INTEGER DEFAULT 0,
  created_at        TEXT DEFAULT (datetime('now')),
  created_by        TEXT,
  created_by_type   TEXT,
  updated_at        TEXT DEFAULT (datetime('now')),
  updated_by        TEXT,
  updated_by_type   TEXT,
  FOREIGN KEY (base_model_id) REFERENCES models(model_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_provisioned_base_role_variant
  ON provisioned_models(base_model_id, role, variant);
CREATE INDEX IF NOT EXISTS idx_provisioned_role
  ON provisioned_models(role);
EOSQL

# Anti-loop sampling columns (added after provisioned_models was first introduced).
add_col_if_missing "provisioned_models" "repeat_penalty" "REAL"
add_col_if_missing "provisioned_models" "repeat_last_n" "INTEGER"

# Soft-delete queue: set ONLY on explicit user request via lma-model-prune skill.
add_col_if_missing "provisioned_models" "user_flag_for_deletion" "INTEGER DEFAULT 0"

echo "Done."
