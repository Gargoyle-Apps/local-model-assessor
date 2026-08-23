#!/usr/bin/env python3
"""
Import hardware-profile.yaml and software-profile.yaml into model-assessor.db.
Run from repo root: ./scripts/py scripts/import-profiles.py [--allow-mock]

Resolves files via scripts/lma_paths.py (optional LMO sidecar, else local
computer-profile/, else templates). Stores YAML in hardware_profile and
software_profile. LMA works without LMO.

Mock/dry-run profiles require an explicit --allow-mock flag or
LMA_ALLOW_MOCK=1. Their declaration is preserved in the stored YAML.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import lma_paths  # noqa: E402


def main():
    parser = argparse.ArgumentParser(
        description="Import resolved LMA hardware/software profiles"
    )
    parser.add_argument(
        "db", nargs="?", type=Path, help="database path (default: resolved LMA DB)"
    )
    parser.add_argument(
        "--allow-mock",
        action="store_true",
        default=None,
        help="allow profiles explicitly marked as mock/dry-run inventory",
    )
    args = parser.parse_args()

    if args.db is not None:
        db_path = args.db
    else:
        try:
            db_path = lma_paths.require_db_path()
        except lma_paths.PathResolutionError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    if not db_path.exists():
        print(f"Error: {db_path} not found. Run init-db.sh first.", file=sys.stderr)
        sys.exit(1)

    try:
        hw = lma_paths.hardware_profile_path(allow_mock=args.allow_mock)
        sw = lma_paths.software_profile_path(allow_mock=args.allow_mock)
    except lma_paths.PathResolutionError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    c = conn.cursor()

    try:
        if hw.path and hw.path.is_file():
            try:
                content = hw.path.read_text(encoding="utf-8")
            except OSError as e:
                print(f"Error reading {hw.path}: {e}", file=sys.stderr)
                sys.exit(1)
            c.execute(
                "INSERT OR REPLACE INTO hardware_profile (id, yaml_content, updated_at) VALUES (1, ?, datetime('now'))",
                (content,),
            )
            kind = ", mock" if hw.mock else ""
            print(f"Imported hardware profile from {hw.path} ({hw.source}{kind})")
        else:
            print("Skip: no hardware profile found")

        if sw.path and sw.path.is_file():
            try:
                content = sw.path.read_text(encoding="utf-8")
            except OSError as e:
                print(f"Error reading {sw.path}: {e}", file=sys.stderr)
                sys.exit(1)
            c.execute(
                "INSERT OR REPLACE INTO software_profile (id, yaml_content, updated_at) VALUES (1, ?, datetime('now'))",
                (content,),
            )
            kind = ", mock" if sw.mock else ""
            print(f"Imported software profile from {sw.path} ({sw.source}{kind})")
        else:
            print("Skip: no software profile found")

        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}", file=sys.stderr)
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
