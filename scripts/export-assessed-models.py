#!/usr/bin/env python3
"""
Generate assessed-models.md from model-assessor.db.
Combines models table + model_docs with static header/template content.

Run from repo root: ./scripts/py scripts/export-assessed-models.py
"""

import sqlite3
import sys
from pathlib import Path
from typing import Optional

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import lma_paths  # noqa: E402

REPO_ROOT = _SCRIPTS.parent
DEFAULT_MD = REPO_ROOT / "model-data" / "assessed-models.md"


def build_spec_row(label: str, value: str) -> str:
    safe_label = label.replace("|", "\\|")
    safe_value = value.replace("|", "\\|")
    return f"| {safe_label} | {safe_value} |"


def _md_escape_inline(text: str) -> str:
    return str(text).replace("|", "\\|").replace("`", "\\`")


def _truthy(v):
    return v in (True, 1, "true", "1", "yes")


def model_to_spec_table(m: dict, doc: Optional[dict]) -> str:
    """Build markdown spec table from model + optional doc overrides."""
    if doc and doc.get("spec_table"):
        return doc["spec_table"]
    rows = [
        build_spec_row("VRAM", f"{m['vram']}GB"),
        build_spec_row("Context", f"{m['ctx']:,}"),
        build_spec_row("Speed", f"~{m['tps']} t/s"),
    ]
    extras = []
    if _truthy(m.get("vision")):
        extras.append("Vision")
    if _truthy(m.get("tools")):
        extras.append("Tools")
    if _truthy(m.get("reasoning")):
        extras.append("Reasoning")
    if _truthy(m.get("fim")):
        extras.append("FIM")
    if _truthy(m.get("moe")):
        extras.append("MoE")
    if _truthy(m.get("structured")):
        extras.append("Structured output")
    if m.get("latency"):
        rows.append(build_spec_row("Latency", str(m["latency"])))
    if extras:
        rows.append(build_spec_row("Special", ", ".join(extras)))
    header = "| Spec | Value |\n|------|-------|"
    return header + "\n" + "\n".join(rows)


def main():
    try:
        db_path = lma_paths.require_db_path()
    except lma_paths.PathResolutionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    md_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_MD

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute("SELECT * FROM models WHERE superseded_by IS NULL ORDER BY vram, model_id")
            models = [dict(r) for r in c.fetchall()]

            c.execute("SELECT * FROM model_docs")
            docs = {r["model_id"]: dict(r) for r in c.fetchall()}

            provisioned = []
            c.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='provisioned_models'"
            )
            if c.fetchone():
                c.execute(
                    """
                    SELECT pm.alias, pm.base_model_id, pm.role, pm.variant, pm.num_ctx,
                           pm.temperature, pm.is_active, pm.modelfile_path, pm.create_command,
                           pm.pull_command, m.class, m.vram, m.tps
                      FROM provisioned_models pm
                      LEFT JOIN models m ON m.model_id = pm.base_model_id
                     ORDER BY pm.role, pm.alias
                    """
                )
                provisioned = [dict(r) for r in c.fetchall()]
    except sqlite3.Error as e:
        print(f"Database error: {e}", file=sys.stderr)
        sys.exit(1)

    # Group by class for section headers
    class_order = ["Utility", "Speedster", "Middleweight", "Daily Driver", "Heavy Lifter"]

    header = """# Assessed Models

A human-readable reference for all evaluated Ollama models. For machine-readable data, see the database (`model-assessor.db`) or exported JSON.

> **Hardware:** See `computer-profile/hardware-profile.yaml` (or hardware_profile in DB) for system specifications, VRAM budgets, and hardware class definitions.

---

## Hardware Classes

> **Source:** `computer-profile/hardware-profile.yaml` — hardware class definitions and VRAM ranges are defined there.

| Class | VRAM | Speed | Co-run? | Use Case |
|-------|------|-------|---------|----------|
| **Utility** | 1-4GB | 100-1000 t/s | Always | Embedding, OCR |
| **Speedster** | <8GB | 80-120 t/s | Always | Autocomplete, quick tasks |
| **Middleweight** | 8-12GB | 45-50 t/s | Yes | Daily driver, interactive |
| **Daily Driver** | 12-24GB | 25-40 t/s | Yes | Reasoning, coding |
| **Heavy Lifter** | 30-48GB | ~15 t/s | **No** | Quality-critical |

**Concurrency Rule:** See `computer-profile/hardware-profile.yaml` for concurrency rules. Generally: 1 Utility + 1 Speedster + 1 larger model can run simultaneously. Heavy Lifters run solo.

---

## Creative Quality Tiers

For writing and creative tasks, choose based on stage:

| Stage | Model | Speed | When to Use |
|-------|-------|-------|-------------|
"""

    creative_tiers = []
    for m in models:
        d = docs.get(m["model_id"]) or {}
        ct = d.get("creative_tier") or m.get("creative")
        if ct:
            creative_tiers.append((ct, m["model_id"], m["tps"]))
    if creative_tiers:
        for ct, mid, tps in creative_tiers[:6]:
            ct_label = str(ct).capitalize() if isinstance(ct, str) else str(ct)
            header += f"| 🎨 **{ct_label}** | `{_md_escape_inline(mid)}` | ~{tps} t/s | See model entry |\n"
    else:
        header += "| Draft | (your draft model) | ~50 t/s | Brainstorming, iteration |\n"
        header += "| Quality | (your quality model) | ~25 t/s | Substantive drafts |\n"
        header += "| Polish | (your polish model) | ~15 t/s | Publication-ready |\n"
    header += "\n---\n\n"

    sections = {cls: [] for cls in class_order}
    other_models: list = []
    for m in models:
        cls = m.get("class") or "Other"
        if cls in sections:
            sections[cls].append(m)
        else:
            other_models.append(m)
    if other_models:
        sections.setdefault("Other", []).extend(other_models)

    body_parts = []
    rendered_count = 0
    section_order = class_order + (["Other"] if other_models else [])
    for cls in section_order:
        mods = sections.get(cls, [])
        if not mods:
            continue
        body_parts.append(f"## {cls} Class Models\n")
        for m in mods:
            rendered_count += 1
            doc = docs.get(m["model_id"])
            spec_table = model_to_spec_table(m, doc)
            desc = (doc and doc.get("description")) or ""
            best_for = (doc and doc.get("best_for")) or ""
            caveats = (doc and doc.get("caveats")) or ""
            creative = (doc and doc.get("creative_tier")) or m.get("creative")
            if creative is not None and not isinstance(creative, str):
                creative = str(creative)
            creative_row = (
                f"\n{build_spec_row('Creative', creative + ' tier')}\n" if creative else ""
            )

            model_heading = _md_escape_inline(m["model_id"])
            block = f"### `{model_heading}`\n{spec_table}{creative_row}\n\n"
            if desc:
                block += f"{_md_escape_inline(desc)}\n\n"
            if best_for:
                block += f"**Best for:** {_md_escape_inline(best_for)}\n\n"
            if caveats:
                block += f"**Caveats:** {_md_escape_inline(caveats)}\n\n"
            block += "---\n\n"
            body_parts.append(block)

    if provisioned:
        body_parts.append("## Role-tuned provisioned clones (Ollama aliases)\n\n")
        body_parts.append(
            "These rows come from `provisioned_models`. "
            "`is_active` is set after you run `pull_command` / `create_command` and confirm with `ollama list`.\n\n"
        )
        body_parts.append(
            "| Alias | Base model | Role | Variant | num_ctx | Temp | Class | VRAM | t/s | Active |\n"
        )
        body_parts.append(
            "|-------|------------|------|---------|---------|------|-------|------|-----|--------|\n"
        )
        for p in provisioned:
            temp = p.get("temperature")
            temp_s = "" if temp is None else str(temp)
            cls = p.get("class") or "—"
            vram = p.get("vram")
            vram_s = "" if vram is None else f"{vram}GB"
            tps = p.get("tps")
            tps_s = "" if tps is None else str(tps)
            active = "yes" if p.get("is_active") else "no"
            body_parts.append(
                f"| `{_md_escape_inline(p['alias'])}` | `{_md_escape_inline(p['base_model_id'])}` | {p['role']} | {p['variant']} | "
                f"{p['num_ctx']} | {temp_s} | {cls} | {vram_s} | {tps_s} | {active} |\n"
            )
        body_parts.append(
            "\n**Build commands (per alias):** query the DB for `pull_command`, "
            "`create_command`, and `modelfile_path`.\n\n---\n\n"
        )

    footer = """
## Role Architecture

Run `./scripts/query-db.sh "SELECT role, variant, model_id FROM role_model ORDER BY role, variant"` for role mappings.

## RAG Pipelines

Run `./scripts/query-db.sh "SELECT * FROM rag_pipeline"` for pipeline configs.

## Quick Decision Tree

Run `./scripts/query-db.sh "SELECT * FROM decision_tree"` for the decision tree.
"""

    output = header + "\n".join(body_parts) + footer
    md_path.write_text(output, encoding="utf-8")
    print(f"Exported {rendered_count} active models to {md_path}")

    try:
        with sqlite3.connect(db_path) as conn2:
            conn2.row_factory = sqlite3.Row
            sup = conn2.execute(
                "SELECT model_id, superseded_by FROM models WHERE superseded_by IS NOT NULL ORDER BY model_id"
            ).fetchall()
            if sup:
                print(f"  ({len(sup)} superseded model(s) excluded: "
                      + ", ".join(f"{r['model_id']} → {r['superseded_by']}" for r in sup) + ")")
    except sqlite3.Error:
        pass


if __name__ == "__main__":
    main()
