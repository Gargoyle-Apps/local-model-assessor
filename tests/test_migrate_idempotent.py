"""Test that migrate-schema.sh is idempotent: running it twice produces identical schema."""

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATE_SCRIPT = REPO_ROOT / "scripts" / "migrate-schema.sh"
SCHEMA_SQL = REPO_ROOT / "scripts" / "schema.sql"

from tests.fixtures.pre_migration_schema import PRE_MIGRATION_SCHEMA


def _schema_snapshot(db_path: Path) -> str:
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY name")
    rows = [row[0] for row in c.fetchall()]
    conn.close()
    return "\n".join(rows)


def _column_names(db_path: Path, table: str) -> list[str]:
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    c.execute(f"SELECT name FROM pragma_table_info('{table}') ORDER BY cid")
    cols = [row[0] for row in c.fetchall()]
    conn.close()
    return cols


@pytest.fixture
def db_path(tmp_path, _isolate_lma_env):
    path = _isolate_lma_env
    conn = sqlite3.connect(str(path))
    conn.executescript(SCHEMA_SQL.read_text())
    conn.close()
    return path


@pytest.fixture
def old_schema_db(tmp_path, _isolate_lma_env):
    path = _isolate_lma_env
    conn = sqlite3.connect(str(path))
    conn.executescript(PRE_MIGRATION_SCHEMA)
    conn.close()
    return path


def test_migrate_idempotent(db_path):
    """Migrate must target LMA_DB only — never the repo default DB under test."""
    env = {
        **subprocess.os.environ,
        "PATH": subprocess.os.environ.get("PATH", ""),
        "LMA_DB": str(db_path.resolve()),
    }

    def run_migrate():
        return subprocess.run(
            ["bash", str(MIGRATE_SCRIPT)],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            env=env,
        )

    snap_before = _schema_snapshot(db_path)
    r1 = run_migrate()
    assert r1.returncode == 0, f"migrate stderr:\n{r1.stderr}\nstdout:\n{r1.stdout}"
    snap_after_1 = _schema_snapshot(db_path)
    r2 = run_migrate()
    assert r2.returncode == 0, f"migrate stderr:\n{r2.stderr}\nstdout:\n{r2.stdout}"
    snap_after_2 = _schema_snapshot(db_path)

    assert snap_after_1 == snap_after_2, "Schema changed between first and second migrate run"
    assert snap_before == snap_after_1, "Migrate should be no-op on current schema baseline"


def test_migrate_from_old_schema_matches_fresh_init(old_schema_db):
    """Migrate from a pre-release schema should reach structural parity with init-db."""
    env = {
        **subprocess.os.environ,
        "PATH": subprocess.os.environ.get("PATH", ""),
        "LMA_DB": str(old_schema_db.resolve()),
    }
    r = subprocess.run(
        ["bash", str(MIGRATE_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env,
    )
    assert r.returncode == 0, f"migrate stderr:\n{r.stderr}\nstdout:\n{r.stdout}"

    fresh_path = old_schema_db.parent / "fresh.db"
    conn = sqlite3.connect(str(fresh_path))
    conn.executescript(SCHEMA_SQL.read_text())
    conn.close()

    migrated_cols = {
        t: set(_column_names(old_schema_db, t))
        for t in ("models", "provisioned_models", "role_model", "model_docs")
        if _column_names(old_schema_db, t)
    }
    fresh_cols = {
        t: set(_column_names(fresh_path, t))
        for t in migrated_cols
    }
    assert migrated_cols == fresh_cols, "Column sets differ after migrate vs fresh init"
    assert "user_flag_for_deletion" in migrated_cols.get("provisioned_models", set())
    assert "inventory_status" in migrated_cols.get("models", set())
    assert "removed_at_confidence" in migrated_cols.get("models", set())
