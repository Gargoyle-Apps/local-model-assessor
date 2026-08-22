#!/usr/bin/env python3
"""
Generate IDE-specific configuration files with role-appropriate timeouts.

Reads provisioned_models + models from model-assessor.db and emits config
fragments for supported IDEs (Continue, Cline, Roo Code).

Usage:
  ./scripts/py scripts/generate-ide-config.py                     # all targets
  ./scripts/py scripts/generate-ide-config.py --target continue    # Continue only
  ./scripts/py scripts/generate-ide-config.py --target cline       # Cline / Roo only
  ./scripts/py scripts/generate-ide-config.py --active-only        # skip is_active=0 rows
  ./scripts/py scripts/generate-ide-config.py --dry-run            # print, don't write
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    print(
        "Error: PyYAML is required (see requirements.txt).\n"
        "  ./scripts/bootstrap-python.sh\n"
        "  ./scripts/py scripts/generate-ide-config.py ...\n"
        "See lma-python-env skill.",
        file=sys.stderr,
    )
    sys.exit(1)

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import lma_paths  # noqa: E402

REPO_ROOT = _SCRIPTS.parent

OLLAMA_API_BASE = "http://localhost:11434"

# ---------------------------------------------------------------------------
# Timeout policy (ms) — integrations/IDE-model-management/IDE.md "Timeout Policy"
# ---------------------------------------------------------------------------
TIMEOUT_SNAPPY_MS = 60_000     # autocomplete, embedding, OCR
TIMEOUT_DEEP_MS = 300_000      # chat, coding, reasoning, vision, creative, heavy_lifter

SNAPPY_ROLES = frozenset({"autocomplete", "embedding", "ocr"})


def timeout_for_role(role: str) -> int:
    if role in SNAPPY_ROLES:
        return TIMEOUT_SNAPPY_MS
    return TIMEOUT_DEEP_MS


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def fetch_provisioned_with_models(db_path: Path, active_only: bool = False) -> list[dict]:
    """Return provisioned clones joined to base-model specs.

    Uses LEFT JOIN so rows with a missing base model are included (with
    NULLs for model columns) and flagged with a warning rather than silently
    dropped.
    """
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='provisioned_models'"
        )
        if not c.fetchone():
            return []

        where = "WHERE pm.is_active = 1" if active_only else ""
        c.execute(
            f"""
            SELECT pm.alias, pm.base_model_id, pm.role, pm.variant, pm.num_ctx,
                   pm.temperature, pm.is_active,
                   m.vram, m.class, m.tps, m.ctx AS native_ctx,
                   m.tools, m.vision, m.reasoning, m.fim
              FROM provisioned_models pm
              LEFT JOIN models m ON m.model_id = pm.base_model_id
             {where}
             ORDER BY pm.role, pm.alias
            """
        )
        rows = [dict(r) for r in c.fetchall()]

    skipped = 0
    kept: list[dict] = []
    for r in rows:
        if r.get("class") is None:
            print(
                f"Warning: provisioned alias {r['alias']!r} has no matching base model "
                f"({r['base_model_id']!r}) in the models table — skipped.",
                file=sys.stderr,
            )
            skipped += 1
            continue
        kept.append(r)

    inactive = sum(1 for r in kept if not r.get("is_active"))
    if inactive and not active_only:
        print(
            f"Note: {inactive} provisioned clone(s) have is_active=0 "
            f"(not yet built in Ollama). Use --active-only to exclude them.",
            file=sys.stderr,
        )

    return kept


# ---------------------------------------------------------------------------
# Continue.dev config generation (YAML)
# ---------------------------------------------------------------------------

_ROLE_TO_CONTINUE = {
    "coding":           {"roles": ["chat", "edit", "apply"]},
    "generalist":       {"roles": ["chat", "edit"]},
    "reasoning":        {"roles": ["chat", "edit"]},
    "heavy_lifter":     {"roles": ["chat", "edit", "apply"]},
    "creative":         {"roles": ["chat", "edit"]},
    "formatting":       {"roles": ["chat", "edit"]},
    "vision":           {"roles": ["chat"]},
    "visual_reasoning": {"roles": ["chat"]},
    "autocomplete":     {"roles": ["autocomplete"]},
    "embedding":        {"roles": ["embed"]},
    "ocr":              {"roles": ["embed"]},
}


def _continue_capabilities(row: dict) -> list[str]:
    caps = []
    if row.get("tools"):
        caps.append("tool_use")
    if row.get("vision"):
        caps.append("image_input")
    return caps


def _continue_model_entry(row: dict) -> dict:
    role = row["role"]
    mapping = _ROLE_TO_CONTINUE.get(role, {"roles": ["chat"]})
    timeout = timeout_for_role(role)

    entry: dict = {
        "name": f"{row['alias']} ({role})",
        "provider": "ollama",
        "model": row["alias"],
        "apiBase": OLLAMA_API_BASE,
        "roles": mapping["roles"],
        "lmaManaged": True,
    }

    caps = _continue_capabilities(row)
    if caps:
        entry["capabilities"] = caps

    entry["defaultCompletionOptions"] = {"contextLength": row["num_ctx"]}
    entry["requestOptions"] = {"timeout": timeout}

    if role == "autocomplete":
        entry["autocompleteOptions"] = {
            "debounceDelay": 250,
            "maxPromptTokens": 2048,
            "modelTimeout": timeout,
        }

    return entry


def build_continue_config(rows: list[dict]) -> dict:
    models = [_continue_model_entry(r) for r in rows]
    return {
        "name": "Local Model Assessor",
        "version": "1.0.0",
        "schema": "v1",
        "models": models,
    }


def write_continue_config(config: dict, dry_run: bool = False) -> Optional[Path]:
    out_path = (
        REPO_ROOT / "integrations" / "IDE-model-management" / "continue" / "generated" / "config.yaml"
    )
    text = yaml.dump(config, default_flow_style=False, sort_keys=False, allow_unicode=True)
    if dry_run:
        print(f"--- Continue config.yaml (would write to {out_path}) ---")
        print(text)
        return None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Cline / Roo Code config generation (JSON)
# ---------------------------------------------------------------------------

def _cline_provider_entry(row: dict) -> dict:
    timeout = timeout_for_role(row["role"])
    return {
        "apiConfiguration": {
            "apiProvider": "ollama",
            "ollamaModelId": row["alias"],
            "apiBaseUrl": OLLAMA_API_BASE,
            "requestTimeoutMs": timeout,
        },
    }


def build_cline_config(rows: list[dict]) -> dict:
    """Build a multi-profile Cline/Roo config keyed by sanitized alias.

    Keys are derived from the provisioned alias (colons replaced with
    dashes) so that multiple base models sharing the same (role, variant)
    never collide.
    """
    profiles: dict = {}
    for r in rows:
        key = r["alias"].replace(":", "-")
        profiles[key] = _cline_provider_entry(r)
    return profiles


def write_cline_config(config: dict, dry_run: bool = False) -> Optional[Path]:
    out_path = (
        REPO_ROOT / "integrations" / "IDE-model-management" / "cline" / "generated" / "provider-settings.json"
    )
    text = json.dumps(config, indent=2, ensure_ascii=False) + "\n"
    if dry_run:
        print(f"--- Cline/Roo provider-settings.json (would write to {out_path}) ---")
        print(text)
        return None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

TARGETS = {
    "continue": ("Continue.dev", build_continue_config, write_continue_config),
    "cline":    ("Cline / Roo Code", build_cline_config, write_cline_config),
}


def main():
    parser = argparse.ArgumentParser(
        description="Generate IDE configs with role-appropriate timeouts from model-assessor.db",
    )
    parser.add_argument(
        "--target", choices=list(TARGETS.keys()), action="append", default=None,
        help="IDE target(s) to generate (default: all)",
    )
    parser.add_argument("--active-only", action="store_true",
                        help="Only include provisioned clones with is_active=1")
    parser.add_argument("--dry-run", action="store_true", help="Print configs, don't write files")
    args = parser.parse_args()

    try:
        db_path = lma_paths.require_db_path()
    except lma_paths.PathResolutionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    rows = fetch_provisioned_with_models(db_path, active_only=args.active_only)
    if not rows:
        print(
            "No provisioned clones found. Assess models first (model-assessment-prompt.yaml) "
            "and run add-model-from-yaml.py, or run migrate-schema.sh if the table is missing.",
            file=sys.stderr,
        )
        sys.exit(1)

    targets = args.target or list(TARGETS.keys())

    for target_name in targets:
        label, builder, writer = TARGETS[target_name]
        config = builder(rows)
        path = writer(config, dry_run=args.dry_run)
        if path:
            print(f"Wrote {label} config to {path}")

    if not args.dry_run:
        print(
            "\nCopy the generated file(s) to the IDE's config location.\n"
            "See integrations/IDE-model-management/<app>/config-location.md for paths."
        )


if __name__ == "__main__":
    main()
