"""Controlled Git-index regressions; no user artifacts are read or staged."""

from pathlib import Path
import os
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "scripts/check-local-only.py"


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    # Avoid ambient Git configuration or index overrides in the isolated repo.
    for key in tuple(os.environ):
        if key.startswith("GIT_"):
            monkeypatch.delenv(key)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    git(tmp_path, "init", "--quiet")
    (tmp_path / ".gitignore").write_text((ROOT / ".gitignore").read_text())
    git(tmp_path, "add", ".gitignore")
    return tmp_path


def stage(repo, path):
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("deliberately synthetic regression fixture\n")
    git(repo, "add", "--force", "--", path)


def check(repo):
    return subprocess.run([sys.executable, str(CHECK), "--repo", str(repo)], capture_output=True, text=True)


@pytest.mark.parametrize("path", [
    "computer-profile/hardware-profile.yaml", "computer-profile/software-profile.yaml",
    "model-data/model-assessor.db", "model-data/model-assessor.db-wal",
    "model-data/new-models.yaml", "model-data/assessed-models.md",
    "model-data/model-lookup.json", "model-data/modelfile/synthetic.mf",
    "integrations/mcp/scout/synthetic-field-guide.md",
    "integrations/embed-retrieval-stack/out/synthetic.json",
    "integrations/IDE-model-management/pi/models.json",
    "integrations/IDE-model-management/goose/config.yaml",
    "integrations/IDE-model-management/continue/generated/synthetic.yaml",
    "ref/synthetic.md", ".agents/synthetic.md",
    "odd name\nwith newline.log",
])
def test_force_added_local_or_ignored_file_fails(repo, path):
    stage(repo, path)
    result = check(repo)
    assert result.returncode == 1
    assert repr(path) in result.stdout


def test_documented_paths_still_fail_when_ignore_rule_removed(repo):
    (repo / ".gitignore").write_text("")
    stage(repo, "integrations/mcp/scout/synthetic-field-guide.md")
    result = check(repo)
    assert result.returncode == 1
    assert "documented local-only path" in result.stdout


def test_templates_placeholders_and_synthetic_fixtures_pass(repo):
    for path in (
        "computer-profile/hardware-profile.template.yaml",
        "model-data/new-models.template.yaml",
        "model-data/modelfile/.gitkeep", "integrations/mcp/scout/.gitkeep",
        "integrations/IDE-model-management/continue/generated/.gitkeep",
        "tests/fixtures/field_guide_contexts.json",
    ):
        stage(repo, path)
    assert check(repo).returncode == 0


def test_nested_ignore_rules_and_negation(repo):
    (repo / "examples").mkdir()
    (repo / "examples/.gitignore").write_text("*.secret\n!public.secret\n")
    stage(repo, "examples/public.secret")
    assert check(repo).returncode == 0
    stage(repo, "examples/private.secret")
    assert check(repo).returncode == 1


def test_git_error_fails_closed(tmp_path):
    assert check(tmp_path).returncode == 2
