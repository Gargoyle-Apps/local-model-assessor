#!/usr/bin/env bash
# Initialize the Local Model Assessor SQLite database from schema
# Run from repo root: ./scripts/init-db.sh

set -e
SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="${LMA_ROOT:-$SCRIPT_ROOT}"
# LMA_DB overrides the path; otherwise LMA_ROOT relocates the default.
DB_PATH="${LMA_DB:-$REPO_ROOT/model-data/model-assessor.db}"
SCHEMA="${SCRIPT_ROOT}/scripts/schema.sql"

mkdir -p "$(dirname "$DB_PATH")"
if [ -f "$DB_PATH" ]; then
  echo "Database exists at $DB_PATH — run 'rm $DB_PATH' first to recreate."
  exit 1
fi
sqlite3 "$DB_PATH" < "$SCHEMA"
echo "Created $DB_PATH"
