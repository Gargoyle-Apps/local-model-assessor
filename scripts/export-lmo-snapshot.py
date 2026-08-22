#!/usr/bin/env python3
"""Pack resolved hardware, software, and model catalog files for LMO to study.

Writes ref/lma-lmo-snapshot.zip (gitignored) unless --output is set.
Does not require LMO. Run from repo root:

  ./scripts/py scripts/export-lmo-snapshot.py
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import lma_paths  # noqa: E402


def _git_head(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _backup_db(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    src_conn = sqlite3.connect(str(src))
    try:
        dst_conn = sqlite3.connect(str(dest))
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()


def _db_stats(db_path: Path) -> dict:
    conn = sqlite3.connect(str(db_path))
    try:
        c = conn.cursor()

        def count(table: str) -> int:
            try:
                return int(c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            except sqlite3.Error:
                return -1

        return {
            "models": count("models"),
            "provisioned_models": count("provisioned_models"),
            "role_model": count("role_model"),
        }
    finally:
        conn.close()


def _manifest(info: dict, stats: dict, git_head: str) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"""# LMA → LMO sidecar snapshot

Generated: {generated}
LMA git: {git_head}
LMA root: {info['lma_root']}
LMO root: {info['lmo_root'] or '(not linked)'}
Linked: {info['linked']}

This zip is a **study pack**, not a live link. Production sharing uses absolute
local paths between two clones (see integrations/lmo/lma-lmo-contract.md).
It contains the full model database and absolute local paths. Keep it on this
machine; do not upload it to GitHub or send it to an external service.

## Ownership

| Artifact | Owner | This snapshot |
|----------|-------|---------------|
| hardware-profile.yaml | LMO when linked; else LMA local | hardware-profile.yaml (source={info['hardware_profile']['source']}) |
| software-profile.yaml | LMO when linked; else LMA local | software-profile.yaml (source={info['software_profile']['source']}) |
| model-assessor.db | LMA | model-assessor.db (source={info['db']['source']}) |
| schema.sql | LMA (tracked) | schema.sql |

## Catalog counts (this DB)

- models: {stats.get('models')}
- provisioned_models: {stats.get('provisioned_models')}
- role_model: {stats.get('role_model')}

## Live path contract (when both repos are cloned)

LMA reads:

- LMA_HARDWARE_PROFILE or LMO inventory YAML
- LMA_SOFTWARE_PROFILE or LMO inventory YAML

LMO reads:

- LMA_DB or LMA_ROOT/model-data/model-assessor.db

Do not copy these files across repos as the source of truth. Point at them.
"""


def export_snapshot(output: Path) -> Path:
    info = lma_paths.describe()
    db = lma_paths.db_path()
    hw = lma_paths.hardware_profile_path()
    sw = lma_paths.software_profile_path()
    root = lma_paths.lma_root()

    if db.source == "missing" or db.path is None or not db.path.is_file():
        raise SystemExit(
            f"Error: model DB not found at {db.path or '(unset)'}. Run ./scripts/init-db.sh first."
        )

    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    schema = root / "scripts" / "schema.sql"
    hw_template = root / "computer-profile" / "hardware-profile.template.yaml"
    sw_template = root / "computer-profile" / "software-profile.template.yaml"
    contract = root / "integrations" / "lmo" / "lma-lmo-contract.md"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db_copy = tmp_path / "model-assessor.db"
        _backup_db(db.path, db_copy)
        stats = _db_stats(db_copy)
        manifest = _manifest(info, stats, _git_head(root))
        sources = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "paths": info,
            "stats": stats,
        }
        (tmp_path / "MANIFEST.md").write_text(manifest, encoding="utf-8")
        (tmp_path / "sources.json").write_text(
            json.dumps(sources, indent=2) + "\n", encoding="utf-8"
        )

        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("MANIFEST.md", manifest)
            zf.write(tmp_path / "sources.json", "sources.json")
            zf.write(db_copy, "model-assessor.db")
            if hw.path and hw.path.is_file():
                zf.write(hw.path, "hardware-profile.yaml")
            if sw.path and sw.path.is_file():
                zf.write(sw.path, "software-profile.yaml")
            if schema.is_file():
                zf.write(schema, "schema.sql")
            if hw_template.is_file():
                zf.write(hw_template, "templates/hardware-profile.template.yaml")
            if sw_template.is_file():
                zf.write(sw_template, "templates/software-profile.template.yaml")
            if contract.is_file():
                zf.write(contract, "lma-lmo-contract.md")

    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Export hardware, software, and model DB for LMO")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Zip path (default: <LMA_ROOT>/ref/lma-lmo-snapshot.zip)",
    )
    args = parser.parse_args()
    out = args.output
    if out is None:
        out = lma_paths.lma_root() / "ref" / "lma-lmo-snapshot.zip"
    try:
        written = export_snapshot(out)
    except lma_paths.PathResolutionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {written}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
