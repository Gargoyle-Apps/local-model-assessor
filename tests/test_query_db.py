"""Query wrapper respects selected databases without touching real profiles."""

from pathlib import Path
import sqlite3
import subprocess


QUERY = Path(__file__).resolve().parents[1] / "scripts/query-db.sh"


def test_override_readonly_and_write_rejection(tmp_path, monkeypatch):
    db = tmp_path / "synthetic target.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE hardware_profile (id INTEGER, yaml_content TEXT)")
        conn.execute("INSERT INTO hardware_profile VALUES (1, 'synthetic profile')")
    monkeypatch.setenv("LMA_DB", str(db))
    before = db.read_bytes()
    result = subprocess.run([str(QUERY), "--readonly", "SELECT yaml_content FROM hardware_profile WHERE id = 1;"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "synthetic profile" in result.stdout
    result = subprocess.run([str(QUERY), "--readonly", "DELETE FROM hardware_profile;"], capture_output=True, text=True)
    assert result.returncode != 0
    assert db.read_bytes() == before


def test_missing_override_never_creates_or_falls_back(tmp_path, monkeypatch):
    db = tmp_path / "missing.db"
    monkeypatch.setenv("LMA_DB", str(db))
    result = subprocess.run([str(QUERY), "--readonly", "SELECT 1;"], capture_output=True, text=True)
    assert result.returncode != 0
    assert str(db) in result.stderr
    assert not db.exists()


def test_existing_single_argument_call_remains_supported(tmp_path, monkeypatch):
    db = tmp_path / "synthetic.db"
    sqlite3.connect(db).close()
    monkeypatch.setenv("LMA_DB", str(db))
    result = subprocess.run([str(QUERY), "SELECT 42 AS synthetic;"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "42" in result.stdout
