"""Tests for optional LMO sidecar path resolution and snapshot export."""

import importlib.util
import sqlite3
import sys
import zipfile
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import lma_paths  # noqa: E402


def _load_export_mod():
    spec = importlib.util.spec_from_file_location(
        "export_lmo_snapshot", SCRIPTS_DIR / "export-lmo-snapshot.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


export_lmo_snapshot = _load_export_mod()


@pytest.fixture
def isolated_roots(tmp_path, monkeypatch):
    lma = tmp_path / "lma"
    lmo = tmp_path / "lmo"
    (lma / "computer-profile").mkdir(parents=True)
    (lma / "model-data").mkdir()
    (lma / "integrations" / "lmo").mkdir(parents=True)
    (lmo / "inventory").mkdir(parents=True)
    monkeypatch.setenv("LMA_ROOT", str(lma))
    monkeypatch.delenv("LMA_DB", raising=False)
    monkeypatch.delenv("LMA_HARDWARE_PROFILE", raising=False)
    monkeypatch.delenv("LMA_SOFTWARE_PROFILE", raising=False)
    monkeypatch.delenv("LMO_ROOT", raising=False)
    return lma, lmo


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class TestHardwareSoftwareResolution:
    def test_local_yaml_beats_template(self, isolated_roots):
        lma, _ = isolated_roots
        _write(lma / "computer-profile" / "hardware-profile.template.yaml", "template: true\n")
        local = _write(lma / "computer-profile" / "hardware-profile.yaml", "local: true\n")
        resolved = lma_paths.hardware_profile_path()
        assert resolved.path == local.resolve()
        assert resolved.source == "local"

    def test_template_when_no_local(self, isolated_roots):
        lma, _ = isolated_roots
        template = _write(
            lma / "computer-profile" / "software-profile.template.yaml", "template: true\n"
        )
        resolved = lma_paths.software_profile_path()
        assert resolved.path == template.resolve()
        assert resolved.source == "template"

    def test_env_override(self, isolated_roots, tmp_path, monkeypatch):
        outside = _write(tmp_path / "from-lmo" / "hw.yaml", "from: env\n")
        monkeypatch.setenv("LMA_HARDWARE_PROFILE", str(outside))
        resolved = lma_paths.hardware_profile_path()
        assert resolved.path == outside.resolve()
        assert resolved.source == "env"

    def test_env_missing_raises(self, isolated_roots, monkeypatch):
        monkeypatch.setenv("LMA_SOFTWARE_PROFILE", str(isolated_roots[0] / "nope.yaml"))
        with pytest.raises(lma_paths.PathResolutionError):
            lma_paths.software_profile_path()

    def test_link_file_relative_to_lmo_root(self, isolated_roots):
        lma, lmo = isolated_roots
        hw = _write(lmo / "inventory" / "hardware-profile.yaml", "from: lmo-link\n")
        _write(
            lma / "integrations" / "lmo" / "paths.yaml",
            f"lmo_root: {lmo}\nhardware_profile: inventory/hardware-profile.yaml\n",
        )
        resolved = lma_paths.hardware_profile_path()
        assert resolved.path == hw.resolve()
        assert resolved.source == "lmo-link"

    def test_lmo_root_conventional_path(self, isolated_roots, monkeypatch):
        _, lmo = isolated_roots
        sw = _write(lmo / "inventory" / "software-profile.yaml", "from: lmo-root\n")
        monkeypatch.setenv("LMO_ROOT", str(lmo))
        resolved = lma_paths.software_profile_path()
        assert resolved.path == sw.resolve()
        assert resolved.source == "lmo-root"

    def test_lmo_root_absent_files_fall_back_to_local(self, isolated_roots, monkeypatch):
        lma, lmo = isolated_roots
        local = _write(lma / "computer-profile" / "hardware-profile.yaml", "local: true\n")
        monkeypatch.setenv("LMO_ROOT", str(lmo))
        resolved = lma_paths.hardware_profile_path()
        assert resolved.path == local.resolve()
        assert resolved.source == "local"


class TestDbPath:
    def test_lma_db_env(self, isolated_roots, monkeypatch, tmp_path):
        db = tmp_path / "custom.db"
        db.write_bytes(b"")
        monkeypatch.setenv("LMA_DB", str(db))
        resolved = lma_paths.db_path()
        assert resolved.path == db.resolve()
        assert resolved.source == "env"

    def test_default_missing_keeps_path(self, isolated_roots):
        resolved = lma_paths.db_path()
        assert resolved.source == "missing"
        assert resolved.path == (isolated_roots[0] / "model-data" / "model-assessor.db").resolve()


class TestSnapshotExport:
    def test_zip_contains_profiles_and_db(self, isolated_roots, tmp_path):
        lma, _ = isolated_roots
        hw = _write(lma / "computer-profile" / "hardware-profile.yaml", "system:\n  name: test\n")
        sw = _write(lma / "computer-profile" / "software-profile.yaml", "ide:\n  name: test\n")
        schema_src = REPO_ROOT / "scripts" / "schema.sql"
        schema_dest = lma / "scripts" / "schema.sql"
        schema_dest.parent.mkdir(parents=True)
        schema_dest.write_text(schema_src.read_text(encoding="utf-8"), encoding="utf-8")
        db = lma / "model-data" / "model-assessor.db"
        sqlite3.connect(str(db)).close()
        conn = sqlite3.connect(str(db))
        conn.executescript(schema_src.read_text(encoding="utf-8"))
        conn.close()

        out = tmp_path / "snap.zip"
        written = export_lmo_snapshot.export_snapshot(out)
        assert written == out.resolve()
        with zipfile.ZipFile(out) as zf:
            names = set(zf.namelist())
        assert "MANIFEST.md" in names
        assert "model-assessor.db" in names
        assert "hardware-profile.yaml" in names
        assert "software-profile.yaml" in names
        assert "schema.sql" in names
        assert zf_read_ok(out, "hardware-profile.yaml") == hw.read_text(encoding="utf-8")
        assert zf_read_ok(out, "software-profile.yaml") == sw.read_text(encoding="utf-8")


def zf_read_ok(zip_path: Path, member: str) -> str:
    with zipfile.ZipFile(zip_path) as zf:
        return zf.read(member).decode("utf-8")
