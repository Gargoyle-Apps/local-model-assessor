#!/usr/bin/env python3
"""
Insert models from YAML output directly into model-assessor.db.
Used by LLM-prompts/model-assessment-prompt.yaml: LLM outputs YAML → pipe to this script.

Usage:
  ./scripts/py scripts/add-model-from-yaml.py model-data/new-models.yaml
  ./scripts/py scripts/add-model-from-yaml.py --assessor gpt-oss:20b --assessor-type local model-data/new-models.yaml
  ./scripts/py scripts/add-model-from-yaml.py   # defaults to model-data/new-models.yaml if it exists
  ./scripts/py scripts/add-model-from-yaml.py < assessment-output.yaml
  # Script extracts from ```yaml ... ``` blocks if present

Provenance (optional):
  --assessor NAME        Model or person that performed the assessment
  --assessor-type TYPE   One of: local, cloud, human
  Also via env: LMA_ASSESSOR, LMA_ASSESSOR_TYPE
"""

import argparse
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    print(
        "Error: PyYAML is required (see requirements.txt).\n"
        "  ./scripts/bootstrap-python.sh\n"
        "  ./scripts/py scripts/add-model-from-yaml.py ...\n"
        "See lma-python-env skill.",
        file=sys.stderr,
    )
    sys.exit(1)

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import lma_paths  # noqa: E402

REPO_ROOT = _SCRIPTS.parent
DEFAULT_YAML = REPO_ROOT / "model-data" / "new-models.yaml"
MODELFILE_ROOT = Path(
    os.environ.get("LMA_MODELFILE_DIR", str(REPO_ROOT / "model-data" / "modelfile"))
)

_TABLE_COLUMNS = {
    "models": frozenset({
        "model_id", "vram", "ctx", "class", "tps", "url", "install", "runtime",
        "vision", "tools", "reasoning", "moe", "fim", "structured", "creative",
        "multilingual", "rag", "no_corun", "latency", "assessed_at",
        "created_at", "created_by", "created_by_type",
        "updated_at", "updated_by", "updated_by_type",
    }),
    "role_model": frozenset({
        "role", "variant", "model_id", "notes",
        "created_at", "created_by", "created_by_type",
        "updated_at", "updated_by", "updated_by_type",
    }),
    "constraint_model": frozenset({
        "constraint_name", "model_id", "sort_order",
        "created_at", "created_by", "created_by_type",
        "updated_at", "updated_by", "updated_by_type",
    }),
    "task_category": frozenset({
        "category", "role_name", "sort_order",
        "created_at", "created_by", "created_by_type",
        "updated_at", "updated_by", "updated_by_type",
    }),
    "model_docs": frozenset({
        "model_id", "spec_table", "description", "best_for", "caveats", "creative_tier",
        "created_at", "created_by", "created_by_type",
        "updated_at", "updated_by", "updated_by_type",
    }),
    "provisioned_models": frozenset({
        "alias", "base_model_id", "role", "variant", "num_ctx", "temperature",
        "num_predict", "repeat_penalty", "repeat_last_n", "system_prompt",
        "modelfile_content", "modelfile_path", "create_command", "pull_command",
        "is_active", "created_at", "created_by", "created_by_type",
        "updated_at", "updated_by", "updated_by_type",
    }),
}

_MODEL_INSERT_DEFAULTS = {
    "vram": 0.0,
    "ctx": 0,
    "class": "",
    "tps": 0,
    "url": "",
    "install": "",
    "runtime": "ollama",
    "vision": 0,
    "tools": 0,
    "reasoning": 0,
    "moe": 0,
    "fim": 0,
    "structured": 0,
    "creative": None,
    "multilingual": 0,
    "rag": 0,
    "no_corun": 0,
    "latency": None,
}

_BOOL_MODEL_FIELDS = (
    "vision", "tools", "reasoning", "moe", "fim", "structured", "multilingual", "rag", "no_corun",
)


def _truthy(v):
    return v in (True, 1, "true", "1", "yes")


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


_KNOWN_TABLES = frozenset({
    "models", "role_model", "constraint_model", "task_category",
    "decision_tree", "rag_pipeline", "model_docs", "provisioned_models",
})


def _has_column(c, table: str, col: str) -> bool:
    if table not in _KNOWN_TABLES:
        raise ValueError(f"_has_column called with unknown table {table!r}")
    allowed = _TABLE_COLUMNS.get(table)
    if allowed is not None and col not in allowed:
        raise ValueError(f"_has_column called with unknown column {col!r} on {table!r}")
    c.execute(f"SELECT COUNT(*) FROM pragma_table_info('{table}') WHERE name='{col}'")
    return c.fetchone()[0] > 0


def _normalize_text(val, default: str = "") -> str:
    if val is None:
        return default
    s = str(val).strip()
    if s.lower() == "none":
        return default
    return s


def _normalize_optional_text(val):
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() == "none":
        return None
    return s


def _coerce_float(val, default: float = 0.0) -> float:
    if val is None:
        return default
    return float(val)


def _coerce_int(val, default: int = 0) -> int:
    if val is None:
        return default
    return int(val)


def _warn_model_downgrade(model_id: str, field: str, old, new) -> None:
    print(
        f"Warning: {model_id} {field} downgraded {old!r} → {new!r}",
        file=sys.stderr,
    )


def _modelfile_out_path(rel_path: str) -> Path:
    """Resolve repo-relative modelfile path; LMA_MODELFILE_DIR overrides the directory."""
    if os.environ.get("LMA_MODELFILE_DIR"):
        return MODELFILE_ROOT / Path(rel_path).name
    return REPO_ROOT / rel_path


def _flush_modelfile_ops(ops: list) -> None:
    for op in ops:
        kind = op[0]
        if kind == "write":
            _, rel_path, content = op
            out_path = _modelfile_out_path(rel_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = out_path.with_suffix(out_path.suffix + ".tmp")
            tmp.write_text(content, encoding="utf-8")
            os.replace(tmp, out_path)
        elif kind == "unlink":
            _, rel_path = op
            stale = _modelfile_out_path(rel_path)
            if stale.is_file():
                try:
                    stale.unlink()
                except OSError as e:
                    print(f"Warning: could not remove stale modelfile {stale}: {e}", file=sys.stderr)


def _table_exists(c, name: str) -> bool:
    c.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    )
    return c.fetchone() is not None


def alias_to_modelfile_path(alias: str) -> str:
    if any(ch in alias for ch in ("/", "\\", "\x00")):
        raise ValueError(
            f"Alias {alias!r} contains path-separator or NUL — refusing to build path"
        )
    return f"model-data/modelfile/{alias.replace(':', '-')}.mf"


def build_modelfile_content(
    base_model_id: str,
    num_ctx: int,
    temperature: Optional[float],
    num_predict: Optional[int],
    system_prompt: Optional[str],
    repeat_penalty: Optional[float] = None,
    repeat_last_n: Optional[int] = None,
) -> str:
    """Build a deterministic Modelfile body from normalized parameters.

    Callers must pass typed values (float/int/str or None); raw strings are
    not re-parsed here.

    `repeat_penalty` / `repeat_last_n` are anti-loop sampling controls. Useful
    for small models (e.g. Gemma 4B) that degenerate into paragraph-level loops
    at low temperature. Recommended starting points: repeat_penalty 1.15-1.2,
    repeat_last_n 256.
    """
    lines = [f"FROM {base_model_id}", f"PARAMETER num_ctx {int(num_ctx)}"]
    if temperature is not None:
        lines.append(f"PARAMETER temperature {float(temperature)}")
    if num_predict is not None:
        lines.append(f"PARAMETER num_predict {int(num_predict)}")
    if repeat_penalty is not None:
        lines.append(f"PARAMETER repeat_penalty {float(repeat_penalty)}")
    if repeat_last_n is not None:
        lines.append(f"PARAMETER repeat_last_n {int(repeat_last_n)}")
    if system_prompt:
        sp = system_prompt.strip()
        if "\n" in sp:
            if '"""' in sp:
                raise ValueError(
                    "system_prompt contains triple-quotes which would break "
                    "Modelfile SYSTEM block — remove them before importing"
                )
            lines.append(f'SYSTEM """\n{sp}\n"""')
        else:
            esc = sp.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'SYSTEM "{esc}"')
    return "\n".join(lines) + "\n"


def upsert_provisioned(
    c,
    base_model_id: str,
    install: str,
    entry: dict,
    assessor: str,
    assessor_type: str,
) -> tuple[Optional[str], list]:
    """Insert/update provisioned_models. Returns (alias, pending_modelfile_ops).

    create_command uses a repo-relative -f path; run it from the repository root.
    """
    alias = str(entry.get("alias", "")).strip()
    role = str(entry.get("role", "")).strip()
    if not alias or not role:
        return None, []
    variant = str(entry.get("variant", "primary")).strip() or "primary"
    try:
        num_ctx = int(entry["num_ctx"])
    except (KeyError, TypeError, ValueError):
        print(f"Warning: skip provisioning for {base_model_id!r}: invalid num_ctx", file=sys.stderr)
        return None, []

    temperature = entry.get("temperature")
    if temperature == "":
        temperature = None
    elif temperature is not None:
        try:
            temperature = float(temperature)
        except (TypeError, ValueError):
            temperature = None

    num_predict = entry.get("num_predict")
    if num_predict == "" or num_predict is None:
        num_predict = None
    else:
        try:
            num_predict = int(num_predict)
        except (TypeError, ValueError):
            num_predict = None

    repeat_penalty = entry.get("repeat_penalty")
    if repeat_penalty == "" or repeat_penalty is None:
        repeat_penalty = None
    else:
        try:
            repeat_penalty = float(repeat_penalty)
        except (TypeError, ValueError):
            repeat_penalty = None

    repeat_last_n = entry.get("repeat_last_n")
    if repeat_last_n == "" or repeat_last_n is None:
        repeat_last_n = None
    else:
        try:
            repeat_last_n = int(repeat_last_n)
        except (TypeError, ValueError):
            repeat_last_n = None

    system_prompt = entry.get("system_prompt")
    if system_prompt is not None:
        system_prompt = str(system_prompt).strip() or None

    pull_command = (install or "").strip()
    modelfile_path = alias_to_modelfile_path(alias)
    modelfile_content = build_modelfile_content(
        base_model_id, num_ctx, temperature, num_predict, system_prompt,
        repeat_penalty=repeat_penalty, repeat_last_n=repeat_last_n,
    )
    create_command = f"ollama create {alias} -f {modelfile_path}"
    now = _now()

    c.execute(
        "SELECT base_model_id, role, variant FROM provisioned_models WHERE alias=?",
        (alias,),
    )
    alias_row = c.fetchone()
    if alias_row:
        eb, er, ev = alias_row
        if (eb, er, ev) != (base_model_id, role, variant):
            print(
                f"Error: provisioning alias {alias!r} is already used for "
                f"{eb!r} role={er!r} variant={ev!r}; cannot reuse for "
                f"{base_model_id!r} role={role!r} variant={variant!r}.",
                file=sys.stderr,
            )
            return None, []

    c.execute(
        "SELECT modelfile_path, is_active, modelfile_content, alias FROM provisioned_models "
        "WHERE base_model_id=? AND role=? AND variant=?",
        (base_model_id, role, variant),
    )
    prior = c.fetchone()
    if prior:
        old_path_str, was_active, old_content, old_alias = prior
        if was_active and (
            old_content != modelfile_content or old_alias != alias
        ):
            print(
                f"Warning: reprovisioning {base_model_id!r} ({role}/{variant}) changed "
                f"Modelfile body or alias; is_active was cleared. Re-verify with `ollama list` "
                f"after rebuilding the clone in Ollama.",
                file=sys.stderr,
            )

    has_repeat_params = (
        _has_column(c, "provisioned_models", "repeat_penalty")
        and _has_column(c, "provisioned_models", "repeat_last_n")
    )
    if not has_repeat_params and (repeat_penalty is not None or repeat_last_n is not None):
        print(
            "Warning: repeat_penalty/repeat_last_n columns missing from provisioned_models. "
            "Modelfile will still include the PARAMETER lines, but DB columns will not be "
            "populated. Run ./scripts/migrate-schema.sh to add them.",
            file=sys.stderr,
        )

    if has_repeat_params:
        c.execute(
            """
            INSERT INTO provisioned_models (
              alias, base_model_id, role, variant, num_ctx, temperature, num_predict,
              repeat_penalty, repeat_last_n, system_prompt,
              modelfile_content, modelfile_path, create_command, pull_command, is_active,
              created_at, created_by, created_by_type, updated_at, updated_by, updated_by_type
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?,?,?,?,?)
            ON CONFLICT(base_model_id, role, variant) DO UPDATE SET
              alias=excluded.alias,
              num_ctx=excluded.num_ctx,
              temperature=excluded.temperature,
              num_predict=excluded.num_predict,
              repeat_penalty=excluded.repeat_penalty,
              repeat_last_n=excluded.repeat_last_n,
              system_prompt=excluded.system_prompt,
              modelfile_content=excluded.modelfile_content,
              modelfile_path=excluded.modelfile_path,
              create_command=excluded.create_command,
              pull_command=excluded.pull_command,
              is_active=CASE
                WHEN excluded.modelfile_content = provisioned_models.modelfile_content
                 AND excluded.alias = provisioned_models.alias
                THEN provisioned_models.is_active
                ELSE 0
              END,
              updated_at=excluded.updated_at,
              updated_by=excluded.updated_by,
              updated_by_type=excluded.updated_by_type
            """,
            (
                alias,
                base_model_id,
                role,
                variant,
                num_ctx,
                temperature,
                num_predict,
                repeat_penalty,
                repeat_last_n,
                system_prompt,
                modelfile_content,
                modelfile_path,
                create_command,
                pull_command,
                now,
                assessor,
                assessor_type,
                now,
                assessor,
                assessor_type,
            ),
        )
    else:
        c.execute(
            """
            INSERT INTO provisioned_models (
              alias, base_model_id, role, variant, num_ctx, temperature, num_predict, system_prompt,
              modelfile_content, modelfile_path, create_command, pull_command, is_active,
              created_at, created_by, created_by_type, updated_at, updated_by, updated_by_type
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0,?,?,?,?,?,?)
            ON CONFLICT(base_model_id, role, variant) DO UPDATE SET
              alias=excluded.alias,
              num_ctx=excluded.num_ctx,
              temperature=excluded.temperature,
              num_predict=excluded.num_predict,
              system_prompt=excluded.system_prompt,
              modelfile_content=excluded.modelfile_content,
              modelfile_path=excluded.modelfile_path,
              create_command=excluded.create_command,
              pull_command=excluded.pull_command,
              is_active=CASE
                WHEN excluded.modelfile_content = provisioned_models.modelfile_content
                 AND excluded.alias = provisioned_models.alias
                THEN provisioned_models.is_active
                ELSE 0
              END,
              updated_at=excluded.updated_at,
              updated_by=excluded.updated_by,
              updated_by_type=excluded.updated_by_type
            """,
            (
                alias,
                base_model_id,
                role,
                variant,
                num_ctx,
                temperature,
                num_predict,
                system_prompt,
                modelfile_content,
                modelfile_path,
                create_command,
                pull_command,
                now,
                assessor,
                assessor_type,
                now,
                assessor,
                assessor_type,
            ),
        )

    pending_ops: list = [("write", modelfile_path, modelfile_content)]
    if prior and prior[0] and prior[0] != modelfile_path:
        stale_path = prior[0]
        if stale_path != modelfile_path:
            pending_ops.append(("unlink", stale_path))

    return alias, pending_ops


def load_yaml(content: str) -> dict:
    """Parse YAML, optionally extracting from markdown code block."""
    content = content.strip()
    fences = re.findall(r"^```yaml\s*\n(.*?)^```\s*$", content, re.DOTALL | re.MULTILINE)
    if fences:
        if len(fences) > 1:
            print(
                f"Warning: found {len(fences)} ```yaml fences; using the first one.",
                file=sys.stderr,
            )
        content = fences[0].strip()
    return yaml.safe_load(content) or {}


def insert_model(c, model_id: str, m: dict, assessor: str, assessor_type: str) -> None:
    now = _now()
    has_provenance = _has_column(c, "models", "created_at")
    has_runtime = _has_column(c, "models", "runtime")

    c.execute("SELECT * FROM models WHERE model_id=?", (model_id,))
    existing_row = c.fetchone()
    existing = dict(zip([d[0] for d in c.description], existing_row)) if existing_row else None
    is_new = existing is None
    present = set(m.keys()) - {"provisioning"}

    insert_cols = ["model_id"]
    insert_vals: list = [model_id]

    def _add(field: str, value) -> None:
        insert_cols.append(field)
        insert_vals.append(value)

    def _should_set(field: str) -> bool:
        return field in present or is_new

    if _should_set("vram"):
        val = _coerce_float(m.get("vram"), _MODEL_INSERT_DEFAULTS["vram"])
        _add("vram", val)
        if not is_new and val < (existing.get("vram") or 0):
            _warn_model_downgrade(model_id, "vram", existing["vram"], val)
    if _should_set("ctx"):
        val = _coerce_int(m.get("ctx"), _MODEL_INSERT_DEFAULTS["ctx"])
        _add("ctx", val)
        if not is_new and val < (existing.get("ctx") or 0):
            _warn_model_downgrade(model_id, "ctx", existing["ctx"], val)
    if _should_set("tps"):
        val = _coerce_int(m.get("tps"), _MODEL_INSERT_DEFAULTS["tps"])
        _add("tps", val)
        if not is_new and val < (existing.get("tps") or 0):
            _warn_model_downgrade(model_id, "tps", existing["tps"], val)

    for field in ("class", "url", "install"):
        if _should_set(field):
            _add(field, _normalize_text(m.get(field), _MODEL_INSERT_DEFAULTS[field]))

    if has_runtime and _should_set("runtime"):
        _add("runtime", _normalize_text(m.get("runtime"), "ollama") or "ollama")

    for field in _BOOL_MODEL_FIELDS:
        if _should_set(field):
            val = 1 if _truthy(m.get(field)) else 0
            _add(field, val)
            if not is_new and existing.get(field) == 1 and val == 0:
                _warn_model_downgrade(model_id, field, 1, 0)

    for field in ("creative", "latency"):
        if _should_set(field):
            val = _normalize_optional_text(m.get(field)) if field in present else _MODEL_INSERT_DEFAULTS[field]
            _add(field, val)
            if not is_new and field in present and existing.get(field) and val is None:
                _warn_model_downgrade(model_id, field, existing[field], val)

    _add("assessed_at", now)

    if is_new:
        if has_provenance:
            _add("created_at", now)
            _add("created_by", assessor)
            _add("created_by_type", assessor_type)
            _add("updated_at", now)
            _add("updated_by", assessor)
            _add("updated_by_type", assessor_type)

        placeholders = ", ".join(["?"] * len(insert_vals))
        update_parts = [
            f"{col}=excluded.{col}" for col in insert_cols
            if col not in ("model_id", "created_at", "created_by", "created_by_type")
        ]
        c.execute(
            f"INSERT INTO models ({', '.join(insert_cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT(model_id) DO UPDATE SET {', '.join(update_parts)}",
            insert_vals,
        )
        return

    col_val = dict(zip(insert_cols, insert_vals))
    set_parts: list[str] = []
    update_vals: list = []
    for col, val in col_val.items():
        if col == "model_id":
            continue
        set_parts.append(f"{col}=?")
        update_vals.append(val)

    if has_provenance:
        set_parts.extend(["updated_at=?", "updated_by=?", "updated_by_type=?"])
        update_vals.extend([now, assessor, assessor_type])

    update_vals.append(model_id)
    c.execute(
        f"UPDATE models SET {', '.join(set_parts)} WHERE model_id=?",
        update_vals,
    )


def insert_role(c, role: str, variant: str, model_id: str, notes: str,
                assessor: str, assessor_type: str) -> None:
    now = _now()
    if _has_column(c, "role_model", "created_at"):
        c.execute(
            "INSERT INTO role_model "
            "(role, variant, model_id, notes, created_at, created_by, created_by_type, "
            " updated_at, updated_by, updated_by_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(role, variant) DO UPDATE SET "
            "model_id=excluded.model_id, notes=excluded.notes, "
            "updated_at=excluded.updated_at, updated_by=excluded.updated_by, "
            "updated_by_type=excluded.updated_by_type",
            (role, variant, model_id, notes, now, assessor, assessor_type,
             now, assessor, assessor_type),
        )
    else:
        c.execute(
            "INSERT OR REPLACE INTO role_model (role, variant, model_id, notes) VALUES (?, ?, ?, ?)",
            (role, variant, model_id, notes),
        )


def insert_constraint(c, constraint_name: str, model_id: str, sort_order: int,
                      assessor: str, assessor_type: str) -> None:
    now = _now()
    if _has_column(c, "constraint_model", "created_at"):
        c.execute(
            "INSERT INTO constraint_model "
            "(constraint_name, model_id, sort_order, created_at, created_by, created_by_type, "
            " updated_at, updated_by, updated_by_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(constraint_name, model_id) DO UPDATE SET "
            "sort_order=excluded.sort_order, "
            "updated_at=excluded.updated_at, updated_by=excluded.updated_by, "
            "updated_by_type=excluded.updated_by_type",
            (constraint_name, model_id, sort_order, now, assessor, assessor_type,
             now, assessor, assessor_type),
        )
    else:
        c.execute(
            "INSERT OR IGNORE INTO constraint_model (constraint_name, model_id, sort_order) VALUES (?, ?, ?)",
            (constraint_name, model_id, sort_order),
        )


def insert_doc(c, model_id: str, doc: dict, assessor: str, assessor_type: str) -> None:
    now = _now()
    c.execute("SELECT 1 FROM model_docs WHERE model_id=?", (model_id,))
    is_new = c.fetchone() is None
    present = set(doc.keys())

    if is_new:
        insert_cols = ["model_id"]
        insert_vals: list = [model_id]
        for field in ("spec_table", "description", "best_for", "caveats", "creative_tier"):
            insert_cols.append(field)
            insert_vals.append(doc.get(field) or "" if field != "creative_tier" else doc.get(field))
        if _has_column(c, "model_docs", "created_at"):
            insert_cols.extend([
                "created_at", "created_by", "created_by_type",
                "updated_at", "updated_by", "updated_by_type",
            ])
            insert_vals.extend([now, assessor, assessor_type, now, assessor, assessor_type])
        placeholders = ", ".join(["?"] * len(insert_vals))
        c.execute(
            f"INSERT INTO model_docs ({', '.join(insert_cols)}) VALUES ({placeholders})",
            insert_vals,
        )
        return

    set_parts: list[str] = []
    update_vals: list = []
    for field in ("spec_table", "description", "best_for", "caveats", "creative_tier"):
        if field in present:
            set_parts.append(f"{field}=?")
            update_vals.append(doc.get(field) or "" if field != "creative_tier" else doc.get(field))
    if not set_parts:
        return
    if _has_column(c, "model_docs", "created_at"):
        set_parts.extend(["updated_at=?", "updated_by=?", "updated_by_type=?"])
        update_vals.extend([now, assessor, assessor_type])
    update_vals.append(model_id)
    c.execute(
        f"UPDATE model_docs SET {', '.join(set_parts)} WHERE model_id=?",
        update_vals,
    )


def insert_task_category(c, category: str, role_name: str, sort_order: int,
                         assessor: str, assessor_type: str) -> None:
    now = _now()
    if _has_column(c, "task_category", "created_at"):
        c.execute(
            "INSERT INTO task_category "
            "(category, role_name, sort_order, created_at, created_by, created_by_type, "
            " updated_at, updated_by, updated_by_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(category, role_name) DO UPDATE SET "
            "sort_order=excluded.sort_order, "
            "updated_at=excluded.updated_at, updated_by=excluded.updated_by, "
            "updated_by_type=excluded.updated_by_type",
            (category, role_name, sort_order, now, assessor, assessor_type,
             now, assessor, assessor_type),
        )
    else:
        c.execute(
            "INSERT OR REPLACE INTO task_category (category, role_name, sort_order) "
            "VALUES (?, ?, ?)",
            (category, role_name, sort_order),
        )


def insert_decision_tree(c, need_key: str, chain_text: str) -> None:
    c.execute(
        "INSERT INTO decision_tree (need_key, chain_text) VALUES (?, ?) "
        "ON CONFLICT(need_key) DO UPDATE SET chain_text=excluded.chain_text",
        (need_key, chain_text),
    )


def insert_rag_pipeline(c, pipeline_name: str, entry: dict) -> None:
    c.execute(
        "INSERT INTO rag_pipeline "
        "(pipeline_name, embedding_model, synthesis_model, generation_model, rules_model, notes) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(pipeline_name) DO UPDATE SET "
        "embedding_model=excluded.embedding_model, synthesis_model=excluded.synthesis_model, "
        "generation_model=excluded.generation_model, rules_model=excluded.rules_model, "
        "notes=excluded.notes",
        (
            pipeline_name,
            entry.get("embedding_model"),
            entry.get("synthesis_model"),
            entry.get("generation_model"),
            entry.get("rules_model"),
            entry.get("notes"),
        ),
    )


def main():
    parser = argparse.ArgumentParser(description="Insert models from YAML into model-assessor.db")
    parser.add_argument("yaml_file", nargs="?", help="Path to YAML file (default: model-data/new-models.yaml or stdin)")
    parser.add_argument("--assessor", default=os.environ.get("LMA_ASSESSOR"),
                        help="Model or person that performed the assessment")
    parser.add_argument("--assessor-type", default=os.environ.get("LMA_ASSESSOR_TYPE"),
                        choices=["local", "cloud", "human"],
                        help="One of: local, cloud, human")
    args = parser.parse_args()

    if args.yaml_file:
        content = Path(args.yaml_file).read_text()
    elif DEFAULT_YAML.exists():
        content = DEFAULT_YAML.read_text()
    else:
        content = sys.stdin.read()

    data = load_yaml(content)
    if not data:
        print("Error: No YAML data found.", file=sys.stderr)
        sys.exit(1)

    try:
        db_path = lma_paths.require_db_path()
    except lma_paths.PathResolutionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    assessor = args.assessor or "unknown"
    assessor_type = args.assessor_type or "human"

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    c = conn.cursor()

    modelfile_ops: list = []

    try:
        prov_table = _table_exists(c, "provisioned_models")

        for model_id, m in (data.get("models") or {}).items():
            if str(model_id).startswith("_"):
                continue
            if not isinstance(m, dict):
                continue
            try:
                insert_model(c, model_id, m, assessor, assessor_type)
            except (TypeError, ValueError) as e:
                print(f"Error: skipping model {model_id!r}: {e}", file=sys.stderr)
                continue
            print(f"Added/updated model: {model_id}")

            raw_prov = m.get("provisioning")
            model_runtime = _normalize_text(m.get("runtime"), "ollama") or "ollama"
            if raw_prov and model_runtime != "ollama":
                print(f"  Skipping Ollama provisioning for {model_id} (runtime={model_runtime})")
            elif raw_prov and prov_table:
                entries = raw_prov if isinstance(raw_prov, list) else [raw_prov]
                install = _normalize_text(m.get("install", ""))
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    done_alias, ops = upsert_provisioned(
                        c, str(model_id), install, entry, assessor, assessor_type
                    )
                    modelfile_ops.extend(ops)
                    if done_alias:
                        print(f"  Provisioned clone: {done_alias}")
            elif raw_prov and not prov_table:
                print(
                    "Warning: YAML has provisioning but provisioned_models table is missing. "
                    "Run ./scripts/migrate-schema.sh",
                    file=sys.stderr,
                )

        for role, variants in (data.get("by_role") or {}).items():
            if str(role).startswith("_"):
                continue
            if not isinstance(variants, dict):
                continue
            for variant, val in variants.items():
                if str(variant).startswith("_"):
                    continue
                model_id = val.get("primary", val) if isinstance(val, dict) else val
                notes = val.get("notes") if isinstance(val, dict) else None
                if model_id and not str(model_id).startswith("_"):
                    insert_role(c, role, variant, str(model_id), notes, assessor, assessor_type)

        for constraint_name, model_ids in (data.get("by_constraint") or {}).items():
            if str(constraint_name).startswith("_"):
                continue
            if not isinstance(model_ids, list):
                model_ids = [model_ids]
            for i, model_id in enumerate(model_ids):
                if model_id and not str(model_id).startswith("_"):
                    insert_constraint(c, constraint_name, str(model_id), i, assessor, assessor_type)

        for model_id, doc in (data.get("model_docs") or {}).items():
            if str(model_id).startswith("_"):
                continue
            if not isinstance(doc, dict):
                continue
            insert_doc(c, model_id, doc, assessor, assessor_type)

        if _table_exists(c, "task_category"):
            for category, roles in (data.get("by_task_category") or {}).items():
                if str(category).startswith("_"):
                    continue
                for i, role_name in enumerate(roles or []):
                    if role_name and not str(role_name).startswith("_"):
                        insert_task_category(c, category, str(role_name), i, assessor, assessor_type)

        if _table_exists(c, "decision_tree"):
            for need_key, chain_text in (data.get("decision_tree") or {}).items():
                if str(need_key).startswith("_"):
                    continue
                if chain_text:
                    insert_decision_tree(c, need_key, str(chain_text))

        if _table_exists(c, "rag_pipeline"):
            for pipeline_name, entry in (data.get("rag_pipeline") or {}).items():
                if str(pipeline_name).startswith("_"):
                    continue
                if isinstance(entry, dict):
                    insert_rag_pipeline(c, pipeline_name, entry)

        conn.commit()
        _flush_modelfile_ops(modelfile_ops)
    except (sqlite3.Error, OSError, ValueError, TypeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

    print("Done. Run: ./scripts/py scripts/export-assessed-models.py  # to update assessed-models.md")


if __name__ == "__main__":
    main()
