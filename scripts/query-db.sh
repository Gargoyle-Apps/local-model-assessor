#!/usr/bin/env bash
# Run SQL against model-assessor.db. Env: LMA_DB overrides the default path.
# Examples:
#   ./scripts/query-db.sh "SELECT model_id, vram, class FROM models ORDER BY vram"
#   ./scripts/query-db.sh "SELECT role, variant, model_id FROM role_model WHERE role='coding'"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# LMA_DB: absolute path override (LMO sidecar or tests). Same as Python scripts.
DB="${LMA_DB:-${REPO_ROOT}/model-data/model-assessor.db}"

# Optional read-only access for explanatory workflows; existing callers retain
# their original SQL behavior. Never create a missing database during a query.
SQLITE_OPTIONS=(-header -column)
if [ "${1:-}" = "--readonly" ]; then
  SQLITE_OPTIONS+=(-readonly)
  shift
fi

if [ ! -f "$DB" ]; then
  echo "Error: $DB not found. Run ./scripts/init-db.sh first." >&2
  exit 1
fi

if [ $# -eq 0 ]; then
  sqlite3 "${SQLITE_OPTIONS[@]}" "$DB"
elif [ $# -eq 1 ]; then
  sqlite3 "${SQLITE_OPTIONS[@]}" "$DB" "$1"
else
  echo "Error: pass SQL as a single quoted string." >&2
  echo "  Good: ./scripts/query-db.sh \"SELECT * FROM models\"" >&2
  echo "  Bad:  ./scripts/query-db.sh SELECT * FROM models" >&2
  exit 2
fi
