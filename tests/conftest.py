"""Shared pytest configuration for LMA tests."""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _isolate_lma_env(tmp_path, monkeypatch):
    """Pin LMA_DB and modelfile dir to temp paths for every test."""
    db_path = tmp_path / "lma-test.db"
    mf_dir = tmp_path / "modelfiles"
    mf_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LMA_DB", str(db_path))
    monkeypatch.setenv("LMA_MODELFILE_DIR", str(mf_dir))
    monkeypatch.setenv("LMA_ALLOW_MOCK", "0")
    yield db_path
