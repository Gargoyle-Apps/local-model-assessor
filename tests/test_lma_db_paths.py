"""Integration coverage for DB resolution across shell and Python consumers."""

import os
import sqlite3
import subprocess
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_SQL = REPO_ROOT / "scripts" / "schema.sql"


def _marker_db(path: Path, marker: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE marker (value TEXT NOT NULL)")
        conn.execute("INSERT INTO marker VALUES (?)", (marker,))
    return path


def _shell_env(*, lma_root: Path, lma_db: Optional[Path] = None) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("LMA_DB", None)
    env["LMA_ROOT"] = str(lma_root)
    if lma_db is not None:
        env["LMA_DB"] = str(lma_db)
    return env


def test_query_db_uses_lma_root_default(tmp_path):
    lma_root = tmp_path / "alternate-lma"
    _marker_db(lma_root / "model-data" / "model-assessor.db", "from-root")

    result = subprocess.run(
        [str(REPO_ROOT / "scripts" / "query-db.sh"), "SELECT value FROM marker"],
        cwd=REPO_ROOT,
        env=_shell_env(lma_root=lma_root),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "from-root" in result.stdout


def test_query_db_lma_db_overrides_lma_root(tmp_path):
    lma_root = tmp_path / "alternate-lma"
    _marker_db(lma_root / "model-data" / "model-assessor.db", "from-root")
    explicit = _marker_db(tmp_path / "explicit" / "catalog.db", "from-explicit")

    result = subprocess.run(
        [str(REPO_ROOT / "scripts" / "query-db.sh"), "SELECT value FROM marker"],
        cwd=REPO_ROOT,
        env=_shell_env(lma_root=lma_root, lma_db=explicit),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "from-explicit" in result.stdout
    assert "from-root" not in result.stdout


def test_init_db_uses_lma_root_default(tmp_path):
    lma_root = tmp_path / "new-lma-root"

    result = subprocess.run(
        [str(REPO_ROOT / "scripts" / "init-db.sh")],
        cwd=REPO_ROOT,
        env=_shell_env(lma_root=lma_root),
        capture_output=True,
        text=True,
        check=False,
    )

    db_path = lma_root / "model-data" / "model-assessor.db"
    assert result.returncode == 0, result.stderr
    assert db_path.is_file()
    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='models'"
        ).fetchone()[0] == 1


def test_add_model_uses_lma_root_default(tmp_path):
    lma_root = tmp_path / "alternate-lma"
    db_path = lma_root / "model-data" / "model-assessor.db"
    db_path.parent.mkdir(parents=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    yaml_path = tmp_path / "model.yaml"
    yaml_path.write_text(
        """models:
  root-model:1b:
    vram: 1
    ctx: 4096
    class: Utility
    tps: 100
""",
        encoding="utf-8",
    )
    env = _shell_env(lma_root=lma_root)
    env["LMA_MODELFILE_DIR"] = str(tmp_path / "modelfiles")

    result = subprocess.run(
        [
            str(REPO_ROOT / "scripts" / "py"),
            str(REPO_ROOT / "scripts" / "add-model-from-yaml.py"),
            str(yaml_path),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM models WHERE model_id='root-model:1b'"
        ).fetchone()[0] == 1
