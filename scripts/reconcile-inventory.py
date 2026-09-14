#!/usr/bin/env python3
"""Reconcile models.inventory_status with the local Ollama inventory.

Keeps historical rows. Marks a model ``removed`` when its base tag and all
provisioned clones are absent from ``ollama list``. Restores ``present`` when
any of those names reappear. Does not DELETE from ``models``.

mlx-lm rows (runtime=mlx) are skipped for Ollama-based sync.

Usage (from repo root):
  ./scripts/py scripts/reconcile-inventory.py --dry-run
  ./scripts/py scripts/reconcile-inventory.py --from-ollama
  ./scripts/py scripts/reconcile-inventory.py --seed-history
  ./scripts/py scripts/reconcile-inventory.py --from-ollama --seed-history
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import lma_paths  # noqa: E402

VALID_STATUS = frozenset({"present", "removed"})
VALID_CONFIDENCE = frozenset({"authoritative", "best_guess"})

# Last git-tracked Granite 4.0 specs: commit 72427cb (2026-01-07).
# Removal date is a best guess: local DB rewrite 2026-08-20 no longer had
# Granite, and Continue still named granite4:3b after it had left ollama list.
_GRANITE4_ASSESSED_AT = "2026-01-07 00:00:00"
_GRANITE4_REMOVED_AT = "2026-08-20 00:00:00"
_GRANITE4_REMOVAL_NOTES = (
    "Granite 4.0 family dropped from the local fleet without superseded_by. "
    "Last git-tracked specs: 72427cb (2026-01-07). Last Continue reference: "
    "granite4:3b in ref/config.yaml (1a33547, 2026-02-28). Confirmed absent "
    "from ollama list during the 2026-08-20 hardware/Continue sweep. Former "
    "roles were not restored (would look like current assignments)."
)

_GRANITE4_HISTORY = (
    {
        "model_id": "granite4:350m",
        "vram": 0.7,
        "ctx": 32768,
        "class": "Speedster",
        "tps": 200,
        "fim": 1,
        "install": "ollama pull granite4:350m",
        "url": "https://ollama.com/library/granite4",
        "description": (
            "IBM's tiniest Granite 4. 350M parameters with native "
            "Fill-In-the-Middle support for code completions."
        ),
        "best_for": (
            "Code autocomplete (FIM), inline suggestions, ultra-low-latency responses"
        ),
        "caveats": (
            "Limited reasoning. Use only for quick completions, not complex "
            "generation. Historical row: inventory_status=removed."
        ),
        "former_roles": "autocomplete fastest",
    },
    {
        "model_id": "granite4:1b",
        "vram": 3.3,
        "ctx": 128000,
        "class": "Speedster",
        "tps": 100,
        "fim": 1,
        "install": "ollama pull granite4:1b",
        "url": "https://ollama.com/library/granite4",
        "description": (
            "IBM Granite 4 at 1B parameters. Higher precision (fp16) for "
            "precision-sensitive tasks."
        ),
        "best_for": (
            "Quick Q&A, simple text formatting, precision-sensitive small tasks"
        ),
        "caveats": (
            "Larger file size than 3B due to less aggressive quantization. "
            "Historical row: inventory_status=removed."
        ),
        "former_roles": None,
    },
    {
        "model_id": "granite4:3b",
        "vram": 2.1,
        "ctx": 128000,
        "class": "Speedster",
        "tps": 83,
        "fim": 1,
        "tools": 1,
        "install": "ollama pull granite4:3b",
        "url": "https://ollama.com/library/granite4",
        "description": (
            'IBM Granite 4 "Micro" with FIM support, tool calling, and 128K '
            "context. Multilingual (12 languages)."
        ),
        "best_for": (
            "Code autocomplete with long context, lightweight function calling, JSON output"
        ),
        "caveats": (
            "Enterprise-focused; can feel dry for creative tasks. Was the "
            "recommended-fleet Speedster and Continue autocomplete tag. "
            "Historical row: inventory_status=removed."
        ),
        "former_roles": "autocomplete balanced; coding quick; formatting quick",
    },
    {
        "model_id": "granite4:7b-a1b-h",
        "vram": 4.2,
        "ctx": 128000,
        "class": "Middleweight",
        "tps": 58,
        "fim": 1,
        "tools": 1,
        "moe": 1,
        "install": "ollama pull granite4:7b-a1b-h",
        "url": "https://ollama.com/library/granite4",
        "description": (
            "IBM Granite 4.0 hybrid model using Mamba-2 sparse architecture. "
            "Only ~1B parameters active at inference."
        ),
        "best_for": (
            "Autocomplete/FIM, RAG pipelines, multilingual tasks, tool-calling agents"
        ),
        "caveats": (
            "Mamba-2 hybrid arch may differ from transformer models. Historical "
            "row: inventory_status=removed."
        ),
        "former_roles": None,
    },
    {
        "model_id": "granite4:14b",
        "vram": 10.0,
        "ctx": 32768,
        "class": "Middleweight",
        "tps": 45,
        "tools": 1,
        "structured": 1,
        "install": "ollama pull granite4:14b",
        "url": "https://ollama.com/library/granite4",
        "description": (
            "IBM's 4th generation Granite at 14B. Enterprise-focused with strict "
            "instruction adherence."
        ),
        "best_for": (
            "JSON/XML formatting, SQL generation, legal text summarization, structured output"
        ),
        "caveats": (
            "Not a conversationalist. Lacks personality. Don't use for creative "
            "writing. Historical row: inventory_status=removed."
        ),
        "former_roles": (
            "formatting primary; technical_writer primary; contract_reviewer "
            "primary; executive_summarizer structured; quiz_generator primary"
        ),
    },
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _normalize_ollama_tag(tag: str) -> str:
    tag = tag.strip()
    if ":" not in tag:
        return f"{tag}:latest"
    name, _, rev = tag.partition(":")
    return f"{name}:{rev or 'latest'}"


def ollama_aliases() -> Optional[set[str]]:
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print(f"Error: could not run ollama list ({exc})", file=sys.stderr)
        return None
    if result.returncode != 0:
        print("Error: ollama list failed.", file=sys.stderr)
        return None
    aliases: set[str] = set()
    for line in result.stdout.strip().splitlines()[1:]:
        line = line.strip()
        if line:
            aliases.add(_normalize_ollama_tag(line.split()[0]))
    return aliases


def _has_column(conn: sqlite3.Connection, table: str, col: str) -> bool:
    row = conn.execute(
        f"SELECT COUNT(*) FROM pragma_table_info('{table}') WHERE name=?",
        (col,),
    ).fetchone()
    return bool(row and row[0])


def _require_inventory_columns(conn: sqlite3.Connection) -> None:
    if not _has_column(conn, "models", "inventory_status"):
        raise SystemExit(
            "models.inventory_status is missing. Run ./scripts/migrate-schema.sh first."
        )


def mark_removed(
    conn: sqlite3.Connection,
    model_id: str,
    *,
    removed_at: Optional[str],
    confidence: Optional[str],
    notes: Optional[str],
    assessor: str,
    assessor_type: str,
    now: str,
) -> None:
    if confidence is not None and confidence not in VALID_CONFIDENCE:
        raise ValueError(f"invalid removed_at_confidence: {confidence!r}")
    conn.execute(
        """
        UPDATE models SET
          inventory_status='removed',
          removed_at=?,
          removed_at_confidence=?,
          removal_notes=?,
          updated_at=?,
          updated_by=?,
          updated_by_type=?
        WHERE model_id=?
        """,
        (removed_at, confidence, notes, now, assessor, assessor_type, model_id),
    )


def mark_present(
    conn: sqlite3.Connection,
    model_id: str,
    *,
    assessor: str,
    assessor_type: str,
    now: str,
) -> None:
    conn.execute(
        """
        UPDATE models SET
          inventory_status='present',
          removed_at=NULL,
          removed_at_confidence=NULL,
          removal_notes=NULL,
          updated_at=?,
          updated_by=?,
          updated_by_type=?
        WHERE model_id=?
        """,
        (now, assessor, assessor_type, model_id),
    )


def _clone_aliases(conn: sqlite3.Connection, model_id: str) -> list[str]:
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='provisioned_models'"
    ).fetchone():
        return []
    rows = conn.execute(
        "SELECT alias FROM provisioned_models WHERE base_model_id=?",
        (model_id,),
    ).fetchall()
    return [r[0] for r in rows]


def model_is_installed(
    conn: sqlite3.Connection,
    model_id: str,
    installed: set[str],
) -> bool:
    if _normalize_ollama_tag(model_id) in installed:
        return True
    for alias in _clone_aliases(conn, model_id):
        if _normalize_ollama_tag(alias) in installed:
            return True
    return False


def sync_from_ollama(
    conn: sqlite3.Connection,
    installed: set[str],
    *,
    dry_run: bool,
    assessor: str,
    assessor_type: str,
    now: str,
) -> tuple[int, int, int]:
    """Return (marked_removed, restored_present, skipped_mlx)."""
    rows = conn.execute(
        "SELECT model_id, runtime, inventory_status FROM models"
    ).fetchall()
    marked = restored = skipped_mlx = 0
    notes = "Not in ollama list (base tag or provisioned clones) during reconcile-inventory.py."
    for row in rows:
        model_id = row["model_id"]
        runtime = (row["runtime"] or "ollama").strip() or "ollama"
        status = row["inventory_status"] or "present"
        if runtime == "mlx":
            skipped_mlx += 1
            continue
        found = model_is_installed(conn, model_id, installed)
        if found and status == "removed":
            print(f"  restore present: {model_id} (found in ollama list)")
            restored += 1
            if not dry_run:
                mark_present(
                    conn, model_id,
                    assessor=assessor, assessor_type=assessor_type, now=now,
                )
        elif (not found) and status == "present":
            print(f"  mark removed: {model_id} (authoritative, {now})")
            marked += 1
            if not dry_run:
                mark_removed(
                    conn, model_id,
                    removed_at=now,
                    confidence="authoritative",
                    notes=notes,
                    assessor=assessor,
                    assessor_type=assessor_type,
                    now=now,
                )
    return marked, restored, skipped_mlx


def seed_granite4_history(
    conn: sqlite3.Connection,
    *,
    dry_run: bool,
    assessor: str,
    assessor_type: str,
    now: str,
) -> tuple[int, int]:
    """Insert missing Granite 4.0 rows as removed history. Never overwrite existing."""
    inserted = skipped = 0
    for spec in _GRANITE4_HISTORY:
        model_id = spec["model_id"]
        existing = conn.execute(
            "SELECT inventory_status FROM models WHERE model_id=?",
            (model_id,),
        ).fetchone()
        if existing:
            print(f"  seed skip (already in DB, status={existing[0]}): {model_id}")
            skipped += 1
            continue
        notes = _GRANITE4_REMOVAL_NOTES
        if spec.get("former_roles"):
            notes = f"{notes} Former roles: {spec['former_roles']}."
        print(
            f"  seed removed (best_guess {_GRANITE4_REMOVED_AT}): {model_id}"
        )
        inserted += 1
        if dry_run:
            continue
        conn.execute(
            """
            INSERT INTO models (
              model_id, vram, ctx, class, tps, url, install, runtime,
              vision, tools, reasoning, moe, fim, structured,
              multilingual, rag, no_corun,
              inventory_status, removed_at, removed_at_confidence, removal_notes,
              assessed_at, created_at, created_by, created_by_type,
              updated_at, updated_by, updated_by_type
            ) VALUES (
              ?,?,?,?,?,?,?, 'ollama',
              0,?,?,?,?,?,
              0,0,0,
              'removed', ?, 'best_guess', ?,
              ?, ?,?,?,
              ?,?,?
            )
            """,
            (
                model_id, spec["vram"], spec["ctx"], spec["class"], spec["tps"],
                spec["url"], spec["install"],
                spec.get("tools", 0), spec.get("reasoning", 0), spec.get("moe", 0),
                spec.get("fim", 0), spec.get("structured", 0),
                _GRANITE4_REMOVED_AT, notes,
                _GRANITE4_ASSESSED_AT, _GRANITE4_ASSESSED_AT, assessor, assessor_type,
                now, assessor, assessor_type,
            ),
        )
        conn.execute(
            """
            INSERT INTO model_docs (
              model_id, description, best_for, caveats,
              created_at, created_by, created_by_type,
              updated_at, updated_by, updated_by_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                model_id, spec["description"], spec["best_for"], spec["caveats"],
                _GRANITE4_ASSESSED_AT, assessor, assessor_type,
                now, assessor, assessor_type,
            ),
        )
    return inserted, skipped


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile models.inventory_status with ollama list; seed historical removals.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print actions; do not write")
    parser.add_argument(
        "--from-ollama",
        action="store_true",
        help="Mark missing Ollama models removed (authoritative now); restore if found",
    )
    parser.add_argument(
        "--seed-history",
        action="store_true",
        help="Insert missing Granite 4.0 rows as removed (best-guess removed_at)",
    )
    parser.add_argument("--assessor", default=os.environ.get("LMA_ASSESSOR", "human"))
    parser.add_argument(
        "--assessor-type",
        default=os.environ.get("LMA_ASSESSOR_TYPE", "human"),
        choices=("local", "cloud", "human"),
    )
    args = parser.parse_args(argv)

    if not args.from_ollama and not args.seed_history:
        parser.error("specify --from-ollama and/or --seed-history (add --dry-run to preview)")

    try:
        db_path = lma_paths.require_db_path()
    except lma_paths.PathResolutionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    now = _now()
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        _require_inventory_columns(conn)

        if args.from_ollama:
            installed = ollama_aliases()
            if installed is None:
                return 1
            print(f"Ollama tags: {len(installed)}")
            marked, restored, skipped_mlx = sync_from_ollama(
                conn, installed,
                dry_run=args.dry_run,
                assessor=args.assessor,
                assessor_type=args.assessor_type,
                now=now,
            )
            print(
                f"from-ollama: removed={marked} restored={restored} skipped_mlx={skipped_mlx}"
            )
            if not args.dry_run:
                conn.execute(
                    "INSERT OR REPLACE INTO meta (key, value) VALUES ('last_inventory_reconcile', ?)",
                    (now,),
                )

        if args.seed_history:
            inserted, skipped = seed_granite4_history(
                conn,
                dry_run=args.dry_run,
                assessor=args.assessor,
                assessor_type=args.assessor_type,
                now=now,
            )
            print(f"seed-history: inserted={inserted} skipped={skipped}")

        if not args.dry_run:
            conn.commit()

    if args.dry_run:
        print("Dry run: no writes.")
    else:
        print(f"Wrote {db_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
