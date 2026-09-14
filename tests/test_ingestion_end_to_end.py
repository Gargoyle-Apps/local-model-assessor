"""End-to-end ingestion: seed YAML → add-model-from-yaml.py → verify DB rows."""

import importlib.util
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
SCHEMA_SQL = SCRIPTS_DIR / "schema.sql"


def _load_script(name: str):
    module_name = name.replace("-", "_").removesuffix(".py")
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


mod = _load_script("add-model-from-yaml.py")

SEED_YAML = """\
models:
  test-model:7b:
    vram: 8
    ctx: 32768
    class: Middleweight
    tps: 45
    url: https://example.com
    install: ollama pull test-model:7b
    provisioning:
      - alias: "test-model:7b_coding_8k"
        role: coding
        variant: primary
        num_ctx: 8192
        temperature: 0.2
        num_predict: 1536
        repeat_penalty: 1.18
        repeat_last_n: 256

by_role:
  coding:
    primary: test-model:7b

by_constraint:
  has_tools: [test-model:7b]

model_docs:
  test-model:7b:
    description: "Test model."
    best_for: "Testing"
    caveats: "None"

by_task_category:
  writing:
    - creative
    - generalist
  analysis:
    - reasoning

decision_tree:
  need_vision: "vision → generalist"
  need_speed: "autocomplete → coding"

rag_pipeline:
  default:
    embedding_model: "test-embed:latest"
    generation_model: "test-model:7b"
    notes: "Test pipeline"
"""


@pytest.fixture
def seeded_db(tmp_path, _isolate_lma_env):
    db_path = _isolate_lma_env
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_SQL.read_text())
    conn.close()
    return db_path


def _run_ingestion(db_path: Path, yaml_content: str = SEED_YAML):
    yaml_file = db_path.parent / "seed.yaml"
    yaml_file.write_text(yaml_content)

    old_argv = sys.argv[:]
    sys.argv = ["add-model-from-yaml.py", str(yaml_file)]
    try:
        mod.main()
    finally:
        sys.argv = old_argv


def test_models_inserted(seeded_db):
    _run_ingestion(seeded_db)
    conn = sqlite3.connect(str(seeded_db))
    c = conn.cursor()
    c.execute("SELECT model_id, vram, class FROM models WHERE model_id='test-model:7b'")
    row = c.fetchone()
    assert row is not None
    assert row[1] == 8.0
    assert row[2] == "Middleweight"
    conn.close()


def test_role_model_inserted(seeded_db):
    _run_ingestion(seeded_db)
    conn = sqlite3.connect(str(seeded_db))
    c = conn.cursor()
    c.execute("SELECT model_id FROM role_model WHERE role='coding' AND variant='primary'")
    row = c.fetchone()
    assert row is not None
    assert row[0] == "test-model:7b"
    conn.close()


def test_task_category_inserted(seeded_db):
    _run_ingestion(seeded_db)
    conn = sqlite3.connect(str(seeded_db))
    c = conn.cursor()
    c.execute("SELECT role_name FROM task_category WHERE category='writing' ORDER BY sort_order")
    rows = [r[0] for r in c.fetchall()]
    assert rows == ["creative", "generalist"]
    conn.close()


def test_decision_tree_inserted(seeded_db):
    _run_ingestion(seeded_db)
    conn = sqlite3.connect(str(seeded_db))
    c = conn.cursor()
    c.execute("SELECT chain_text FROM decision_tree WHERE need_key='need_vision'")
    row = c.fetchone()
    assert row is not None
    assert "vision" in row[0]
    conn.close()


def test_user_flag_for_deletion_preserved_across_reimport(seeded_db):
    """Flag is operator-managed; YAML re-import must NOT reset it on either table."""
    _run_ingestion(seeded_db)
    conn = sqlite3.connect(str(seeded_db))
    c = conn.cursor()
    c.execute(
        "UPDATE models SET user_flag_for_deletion=1 WHERE model_id='test-model:7b'"
    )
    c.execute(
        "UPDATE provisioned_models SET user_flag_for_deletion=1 "
        "WHERE alias='test-model:7b_coding_8k'"
    )
    conn.commit()
    conn.close()

    _run_ingestion(seeded_db)

    conn = sqlite3.connect(str(seeded_db))
    c = conn.cursor()
    c.execute("SELECT user_flag_for_deletion FROM models WHERE model_id='test-model:7b'")
    assert c.fetchone()[0] == 1, "models flag must survive re-import"
    c.execute(
        "SELECT user_flag_for_deletion FROM provisioned_models "
        "WHERE alias='test-model:7b_coding_8k'"
    )
    assert c.fetchone()[0] == 1, "provisioned_models flag must survive re-import"
    conn.close()


def test_inventory_status_preserved_across_reimport(seeded_db):
    """Removal ledger is operator-managed; YAML re-import must not resurrect a removed row."""
    _run_ingestion(seeded_db)
    conn = sqlite3.connect(str(seeded_db))
    c = conn.cursor()
    c.execute(
        """
        UPDATE models SET
          inventory_status='removed',
          removed_at='2026-08-20 00:00:00',
          removed_at_confidence='best_guess',
          removal_notes='test'
        WHERE model_id='test-model:7b'
        """
    )
    conn.commit()
    conn.close()

    _run_ingestion(seeded_db)

    conn = sqlite3.connect(str(seeded_db))
    c = conn.cursor()
    c.execute(
        """
        SELECT inventory_status, removed_at, removed_at_confidence, removal_notes
          FROM models WHERE model_id='test-model:7b'
        """
    )
    status, when, conf, notes = c.fetchone()
    conn.close()
    assert status == "removed"
    assert when == "2026-08-20 00:00:00"
    assert conf == "best_guess"
    assert notes == "test"


def test_provisioned_anti_loop_columns(seeded_db):
    """repeat_penalty / repeat_last_n round-trip into provisioned_models and the Modelfile."""
    _run_ingestion(seeded_db)
    conn = sqlite3.connect(str(seeded_db))
    c = conn.cursor()
    c.execute(
        "SELECT num_predict, repeat_penalty, repeat_last_n, modelfile_content "
        "FROM provisioned_models WHERE alias='test-model:7b_coding_8k'"
    )
    row = c.fetchone()
    conn.close()
    assert row is not None
    num_predict, repeat_penalty, repeat_last_n, mf = row
    assert num_predict == 1536
    assert repeat_penalty == 1.18
    assert repeat_last_n == 256
    assert "PARAMETER num_predict 1536" in mf
    assert "PARAMETER repeat_penalty 1.18" in mf
    assert "PARAMETER repeat_last_n 256" in mf


def test_sparse_reimport_preserves_absent_fields(seeded_db):
    """Re-import with sparse YAML must not wipe columns omitted from the file."""
    _run_ingestion(seeded_db)
    conn = sqlite3.connect(str(seeded_db))
    c = conn.cursor()
    c.execute(
        "UPDATE model_docs SET description='keep me', best_for='coding' "
        "WHERE model_id='test-model:7b'"
    )
    c.execute("UPDATE models SET url='https://keep.example' WHERE model_id='test-model:7b'")
    conn.commit()
    conn.close()

    sparse = """\
models:
  test-model:7b:
    vram: 9
model_docs:
  test-model:7b:
    caveats: "updated caveat only"
"""
    _run_ingestion(seeded_db, sparse)

    conn = sqlite3.connect(str(seeded_db))
    c = conn.cursor()
    c.execute("SELECT vram, url FROM models WHERE model_id='test-model:7b'")
    vram, url = c.fetchone()
    assert vram == 9.0
    assert url == "https://keep.example"
    c.execute(
        "SELECT description, best_for, caveats FROM model_docs WHERE model_id='test-model:7b'"
    )
    desc, best_for, caveats = c.fetchone()
    assert desc == "keep me"
    assert best_for == "coding"
    assert caveats == "updated caveat only"
    conn.close()


def test_by_constraint_scalar_coerced(seeded_db):
    """Scalar by_constraint values must not iterate characters."""
    yaml_content = """\
models:
  solo:1b:
    vram: 2
    ctx: 4096
    class: Utility
    tps: 100
    url: https://example.com
    install: ollama pull solo:1b
by_constraint:
  has_tools: solo:1b
"""
    _run_ingestion(seeded_db, yaml_content)
    conn = sqlite3.connect(str(seeded_db))
    c = conn.cursor()
    c.execute("SELECT model_id FROM constraint_model WHERE constraint_name='has_tools'")
    rows = [r[0] for r in c.fetchall()]
    conn.close()
    assert rows == ["solo:1b"]


def test_rag_pipeline_inserted(seeded_db):
    _run_ingestion(seeded_db)
    conn = sqlite3.connect(str(seeded_db))
    c = conn.cursor()
    c.execute("SELECT embedding_model, generation_model FROM rag_pipeline WHERE pipeline_name='default'")
    row = c.fetchone()
    assert row is not None
    assert row[0] == "test-embed:latest"
    assert row[1] == "test-model:7b"
    conn.close()


def test_triple_quote_rejection_via_subprocess(seeded_db, tmp_path, monkeypatch):
    """Triple-quote in system_prompt should cause failure without DB changes."""
    monkeypatch.setenv("LMA_DB", str(seeded_db))
    bad_yaml = """\
models:
  bad:model:
    vram: 4
    ctx: 4096
    class: Speedster
    tps: 100
    url: https://example.com
    install: ollama pull bad:model
    provisioning:
      - alias: "bad:model_coding_4k"
        role: coding
        variant: primary
        num_ctx: 4096
        system_prompt: |
          Line one
          Contains triple \"\"\" quotes
          Line three
"""
    yaml_file = tmp_path / "bad.yaml"
    yaml_file.write_text(bad_yaml)
    conn = sqlite3.connect(str(seeded_db))
    before = conn.execute("SELECT COUNT(*) FROM models").fetchone()[0]
    conn.close()
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "add-model-from-yaml.py"), str(yaml_file)],
        capture_output=True, text=True,
        env={**os.environ, "LMA_DB": str(seeded_db)},
    )
    assert result.returncode != 0
    conn = sqlite3.connect(str(seeded_db))
    after = conn.execute("SELECT COUNT(*) FROM models").fetchone()[0]
    conn.close()
    assert after == before
