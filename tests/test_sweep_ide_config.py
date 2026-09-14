"""Unit tests for sweep-ide-config.py helpers."""

import importlib.util
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load_script(name: str):
    module_name = name.replace("-", "_").removesuffix(".py")
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


mod = _load_script("sweep-ide-config.py")


class TestDetectTargets:
    def test_continue_from_primary_agent(self):
        profile = {"primary_agent": {"name": "Continue"}}
        assert mod.detect_targets(profile) == ["continue"]

    def test_cline_and_roo(self):
        assert mod.detect_targets({"primary_agent": {"name": "Cline"}}) == ["cline"]
        assert mod.detect_targets({"primary_agent": {"name": "Roo Code"}}) == ["cline"]

    def test_optional_agents(self):
        profile = {
            "primary_agent": {"name": "Cursor"},
            "optional_agents": [{"name": "Continue"}],
        }
        assert mod.detect_targets(profile) == ["continue"]

    def test_explicit_override(self):
        profile = {"primary_agent": {"name": "Continue"}}
        assert mod.detect_targets(profile, explicit=["cline"]) == ["cline"]

    def test_fallback_all_when_unrecognized(self):
        profile = {"primary_agent": {"name": "Your Primary Agent"}}
        assert mod.detect_targets(profile) == ["continue", "cline"]


class TestMergeContinueConfig:
    def test_preserves_user_models_and_keys(self):
        existing = {
            "rules": ["stay"],
            "models": [
                {"name": "user model", "provider": "ollama", "model": "custom:7b"},
                {"name": "old lma", "provider": "ollama", "model": "old:1b", "lmaManaged": True},
            ],
        }
        generated = {
            "name": "Local Model Assessor",
            "models": [
                {"name": "new lma", "provider": "ollama", "model": "new:1b", "lmaManaged": True},
            ],
        }
        merged = mod.merge_continue_config(existing, generated)
        assert merged["rules"] == ["stay"]
        models = merged["models"]
        assert models[0]["model"] == "custom:7b"
        assert models[1]["model"] == "new:1b"


class TestNormalizeOllamaTag:
    def test_implicit_latest(self):
        assert mod._normalize_ollama_tag("llama3") == "llama3:latest"

    def test_explicit_tag(self):
        assert mod._normalize_ollama_tag("llama3:8b") == "llama3:8b"


class TestProvisionedAliases:
    def test_normalizes_and_skips_missing_table(self, tmp_path):
        db = tmp_path / "empty.db"
        import sqlite3

        sqlite3.connect(str(db)).close()
        assert mod.provisioned_aliases(db) == set()

        conn = sqlite3.connect(str(db))
        conn.execute(
            "CREATE TABLE provisioned_models (alias TEXT PRIMARY KEY, is_active INTEGER)"
        )
        conn.execute("INSERT INTO provisioned_models VALUES ('llama3', 0)")
        conn.execute("INSERT INTO provisioned_models VALUES ('qwen:7b', 0)")
        conn.commit()
        conn.close()
        assert mod.provisioned_aliases(db) == {"llama3:latest", "qwen:7b"}
