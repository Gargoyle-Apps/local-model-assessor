"""Tests for reconcile-inventory.py: status ledger, ollama sync, history seed."""

import importlib.util
import sqlite3
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
SCHEMA_SQL = SCRIPTS_DIR / "schema.sql"


def _load_script(name: str):
    module_name = name.replace("-", "_").removesuffix(".py")
    if module_name in sys.modules:
        del sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


mod = _load_script("reconcile-inventory.py")
export_mod = _load_script("export-assessed-models.py")


def _fresh(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL.read_text())
    return conn


def _insert_model(conn, model_id: str, *, runtime="ollama", status="present"):
    conn.execute(
        """
        INSERT INTO models (
          model_id, vram, ctx, class, tps, install, runtime, inventory_status
        ) VALUES (?, 8, 8192, 'Middleweight', 40, ?, ?, ?)
        """,
        (model_id, f"ollama pull {model_id}", runtime, status),
    )


def test_sync_marks_missing_authoritative(tmp_path):
    db = tmp_path / "t.db"
    conn = _fresh(db)
    _insert_model(conn, "gone:7b")
    _insert_model(conn, "here:7b")
    conn.commit()
    marked, restored, skipped = mod.sync_from_ollama(
        conn,
        {"here:7b"},
        dry_run=False,
        assessor="human",
        assessor_type="human",
        now="2026-09-13 22:00:00",
    )
    conn.commit()
    assert (marked, restored, skipped) == (1, 0, 0)
    gone = conn.execute(
        "SELECT inventory_status, removed_at, removed_at_confidence FROM models WHERE model_id='gone:7b'"
    ).fetchone()
    here = conn.execute(
        "SELECT inventory_status, removed_at FROM models WHERE model_id='here:7b'"
    ).fetchone()
    conn.close()
    assert gone["inventory_status"] == "removed"
    assert gone["removed_at"] == "2026-09-13 22:00:00"
    assert gone["removed_at_confidence"] == "authoritative"
    assert here["inventory_status"] == "present"
    assert here["removed_at"] is None


def test_sync_restores_present_when_found(tmp_path):
    db = tmp_path / "t.db"
    conn = _fresh(db)
    _insert_model(conn, "back:7b", status="removed")
    conn.execute(
        "UPDATE models SET removed_at='2026-01-01 00:00:00', "
        "removed_at_confidence='best_guess', removal_notes='old' "
        "WHERE model_id='back:7b'"
    )
    conn.commit()
    marked, restored, skipped = mod.sync_from_ollama(
        conn,
        {"back:7b"},
        dry_run=False,
        assessor="human",
        assessor_type="human",
        now="2026-09-13 22:00:00",
    )
    conn.commit()
    assert (marked, restored, skipped) == (0, 1, 0)
    row = conn.execute(
        "SELECT inventory_status, removed_at, removed_at_confidence, removal_notes "
        "FROM models WHERE model_id='back:7b'"
    ).fetchone()
    conn.close()
    assert row["inventory_status"] == "present"
    assert row["removed_at"] is None
    assert row["removed_at_confidence"] is None
    assert row["removal_notes"] is None


def test_sync_treats_clone_as_installed(tmp_path):
    db = tmp_path / "t.db"
    conn = _fresh(db)
    _insert_model(conn, "base:7b")
    conn.execute(
        """
        INSERT INTO provisioned_models (
          alias, base_model_id, role, variant, num_ctx,
          modelfile_content, modelfile_path, create_command, pull_command, is_active
        ) VALUES (
          'base:7b_coding_8k', 'base:7b', 'coding', 'primary', 8192,
          'FROM base:7b', 'x.mf', 'ollama create x', 'ollama pull base:7b', 1
        )
        """
    )
    conn.commit()
    marked, restored, skipped = mod.sync_from_ollama(
        conn,
        {"base:7b_coding_8k"},
        dry_run=False,
        assessor="human",
        assessor_type="human",
        now="2026-09-13 22:00:00",
    )
    status = conn.execute(
        "SELECT inventory_status FROM models WHERE model_id='base:7b'"
    ).fetchone()[0]
    conn.close()
    assert (marked, restored, skipped) == (0, 0, 0)
    assert status == "present"


def test_sync_skips_mlx_runtime(tmp_path):
    db = tmp_path / "t.db"
    conn = _fresh(db)
    _insert_model(conn, "mlx-community/Foo-4bit", runtime="mlx")
    conn.commit()
    marked, restored, skipped = mod.sync_from_ollama(
        conn,
        set(),
        dry_run=False,
        assessor="human",
        assessor_type="human",
        now="2026-09-13 22:00:00",
    )
    status = conn.execute(
        "SELECT inventory_status FROM models WHERE model_id='mlx-community/Foo-4bit'"
    ).fetchone()[0]
    conn.close()
    assert skipped == 1
    assert marked == 0
    assert status == "present"


def test_seed_history_inserts_once(tmp_path):
    db = tmp_path / "t.db"
    conn = _fresh(db)
    ins, skip = mod.seed_granite4_history(
        conn, dry_run=False, assessor="human", assessor_type="human",
        now="2026-09-13 22:00:00",
    )
    conn.commit()
    assert ins == 5
    assert skip == 0
    row = conn.execute(
        "SELECT inventory_status, removed_at, removed_at_confidence FROM models "
        "WHERE model_id='granite4:3b'"
    ).fetchone()
    assert row["inventory_status"] == "removed"
    assert row["removed_at"] == "2026-08-20 00:00:00"
    assert row["removed_at_confidence"] == "best_guess"
    ins2, skip2 = mod.seed_granite4_history(
        conn, dry_run=False, assessor="human", assessor_type="human",
        now="2026-09-13 23:00:00",
    )
    conn.commit()
    conn.close()
    assert ins2 == 0
    assert skip2 == 5


def test_export_excludes_removed(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    out = tmp_path / "assessed.md"
    conn = _fresh(db)
    _insert_model(conn, "live:7b")
    _insert_model(conn, "dead:7b", status="removed")
    conn.commit()
    conn.close()
    monkeypatch.setenv("LMA_DB", str(db))
    monkeypatch.setattr(sys, "argv", ["export-assessed-models.py", str(out)])
    export_mod.main()
    text = out.read_text(encoding="utf-8")
    assert "live:7b" in text
    assert "dead:7b" not in text
