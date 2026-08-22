#!/usr/bin/env python3
"""
Emit stack handoff artifacts for Postgres + pgvector + AGE + Ollama embeddings.

**Prerequisite:** At least one assessed embedding model in model-assessor.db
(models row + role_model.embedding and/or provisioned_models with role='embedding').

Reads model-assessor.db for the embedding role (provisioned_models first, then
role_model fallback). Writes STACK_HANDOFF.md and embed_sample.py for copy-out
into an application repo.

Usage:
  ./scripts/py scripts/generate-stack-handoff.py
  ./scripts/py scripts/generate-stack-handoff.py --dry-run
  ./scripts/py scripts/generate-stack-handoff.py --output-dir /path/to/out --active-only

Env: LMA_DB overrides database path (same as other scripts).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import textwrap
from pathlib import Path
from typing import Any, Optional

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import lma_paths  # noqa: E402

REPO_ROOT = _SCRIPTS.parent
DEFAULT_OUT = REPO_ROOT / "integrations" / "embed-retrieval-stack" / "out"
SCHEMA_SQL = REPO_ROOT / "integrations" / "embed-retrieval-stack" / "init" / "02-schema.sql"
OLLAMA_DEFAULT = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_VECTOR_DIM = 768


def _patch_schema_vector_dim(vector_dim: int) -> None:
    """Keep init SQL in sync with the handoff dimension."""
    if not SCHEMA_SQL.is_file():
        return
    text = SCHEMA_SQL.read_text(encoding="utf-8")
    patched, n = re.subn(r"vector\(\d+\)", f"vector({vector_dim})", text)
    if n and patched != text:
        SCHEMA_SQL.write_text(patched, encoding="utf-8")
        print(f"Patched {SCHEMA_SQL} to vector({vector_dim})")


class EmbeddingResolutionError(Exception):
    """No embedding model could be resolved from the database (CLI maps this to exit 1)."""


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    c = conn.cursor()
    c.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    )
    return c.fetchone() is not None


def resolve_embedding_model(
    db_path: Path,
    active_only: bool = False,
) -> dict[str, Any]:
    """Return dict with alias, base_model_id, source ('provisioned'|'role_model').

    When *active_only* is True, only an active (is_active=1) provisioned clone
    qualifies — the role_model fallback is skipped and EmbeddingResolutionError
    is raised if nothing matches.
    """
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        if _table_exists(conn, "provisioned_models"):
            c.execute(
                """
                SELECT pm.alias, pm.base_model_id, pm.is_active, pm.create_command
                  FROM provisioned_models pm
                 WHERE pm.role = 'embedding' AND pm.is_active = 1
                 ORDER BY CASE pm.variant WHEN 'primary' THEN 0 ELSE 1 END,
                          pm.alias
                 LIMIT 1
                """
            )
            row = c.fetchone()
            if row:
                return {
                    "alias": row["alias"],
                    "base_model_id": row["base_model_id"],
                    "source": "provisioned_models",
                    "is_active": row["is_active"],
                    "create_command": row["create_command"],
                }

            if active_only:
                raise EmbeddingResolutionError(
                    "No active (is_active=1) embedding provisioned clone found. "
                    "Build the clone in Ollama or omit --active-only."
                )

        c.execute(
            """
            SELECT model_id, variant
              FROM role_model
             WHERE role = 'embedding'
             ORDER BY CASE variant WHEN 'primary' THEN 0 ELSE 1 END,
                      variant
             LIMIT 1
            """
        )
        row = c.fetchone()
        if row:
            return {
                "alias": row["model_id"],
                "base_model_id": row["model_id"],
                "source": "role_model",
                "is_active": None,
                "create_command": None,
            }

        if not active_only and _table_exists(conn, "provisioned_models"):
            c.execute(
                """
                SELECT pm.alias, pm.base_model_id, pm.is_active, pm.create_command
                  FROM provisioned_models pm
                 WHERE pm.role = 'embedding' AND pm.is_active = 0
                 ORDER BY CASE pm.variant WHEN 'primary' THEN 0 ELSE 1 END,
                          pm.alias
                 LIMIT 1
                """
            )
            row = c.fetchone()
            if row:
                return {
                    "alias": row["alias"],
                    "base_model_id": row["base_model_id"],
                    "source": "provisioned_models",
                    "is_active": row["is_active"],
                    "create_command": row["create_command"],
                }

        if active_only:
            raise EmbeddingResolutionError(
                "No active (is_active=1) embedding provisioned clone found. "
                "Build the clone in Ollama or omit --active-only."
            )

    raise EmbeddingResolutionError(
        "No embedding model found. Prerequisite: assess at least one embedding model — "
        "add it to `models`, set `role_model` with role='embedding', and ideally a "
        "provisioned clone (model-assessment-prompt.yaml → new-models.yaml → "
        "add-model-from-yaml.py). See integrations/embed-retrieval-stack/embed-retrieval-stack.md and lma-embed-stack-handoff skill."
    )


def build_stack_handoff_md(
    *,
    embedding_alias: str,
    ollama_host: str,
    vector_dim: int,
    resolved_from: str,
    is_active: Optional[int],
    create_command: Optional[str] = None,
) -> str:
    create_note = ""
    if create_command:
        create_note = (
            f"\n> **Provisioned clone:** run `{create_command}` if the alias is not yet in `ollama list`.\n"
        )
    active_note = ""
    if is_active is not None and not is_active:
        active_note = (
            "\n> **Note:** This embedding alias is provisioned but `is_active=0`. "
            "Run the clone `create_command` in Ollama before relying on it.\n"
        )

    return textwrap.dedent(
        f"""\
        # Stack handoff — embeddings + Postgres (pgvector) + AGE

        Generated by Local Model Assessor (`scripts/generate-stack-handoff.py`). Copy this file
        and `embed_sample.py` into your application repo or attach them to another LLM chat.

        {active_note}{create_note}
        ## What you have

        - **Embedding model (Ollama):** `{embedding_alias}`  
          *(resolved from `{resolved_from}` in `model-assessor.db`)*
        - **Ollama base URL:** `{ollama_host}`
        - **Sample vector dimension** (must match DB column): **{vector_dim}**  
          Confirm on the model card / Ollama library; change `init/02-schema.sql` before first
          `docker compose up` if your model is not `{vector_dim}-dimensional`.

        ## Docker stack (Postgres + pgvector + Apache AGE)

        From the Local Model Assessor repo:

        ```bash
        cd integrations/embed-retrieval-stack
        cp .env.example .env
        # set POSTGRES_PASSWORD, etc.
        docker compose up -d --build
        ```

        Full steps, use-case ideas, dimension caveats, and AGE notes: **`integrations/embed-retrieval-stack/embed-retrieval-stack.md`**
        in this repo (especially **Common use cases** and **Embedding dimension**).

        ## Next steps

        1. Ensure Ollama is running and the base model for `{embedding_alias}` is installed (`ollama list`).
        2. If you use a **provisioned clone** alias, run its `create_command` from `provisioned_models` if you have not already.
        3. Align `vector({vector_dim})` in `integrations/embed-retrieval-stack/init/02-schema.sql` with your model output.
        4. Install Python deps for the sample: `pip install 'psycopg[binary]'`
        5. Run `embed_sample.py` (set `DATABASE_URL` and `OLLAMA_HOST` in the environment or edit the script).

        ## Apache AGE (optional)

        AGE is loaded in the same Postgres instance. For Cypher and graph modeling, start at
        [Apache AGE](https://age.apache.org/) — not required for basic vector RAG.
        """
    ).rstrip() + "\n"


def build_embed_sample_py(
    *,
    embedding_alias: str,
    ollama_host: str,
    vector_dim: int,
) -> str:
    # Template uses str.format: double {{ }} for literals in generated Python source.
    return textwrap.dedent(
        '''\
        #!/usr/bin/env python3
        """Minimal embed + insert sample (generated by Local Model Assessor).

        pip install 'psycopg[binary]'

        Environment:
          DATABASE_URL  (required) e.g. postgresql://lma:SECRET@localhost:5432/lma
          OLLAMA_HOST   default {ollama_host_default}
        """
        from __future__ import annotations

        import json
        import os
        import sys
        import urllib.request

        import psycopg

        OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "{ollama_host_default}").rstrip("/")
        DATABASE_URL = os.environ.get("DATABASE_URL")
        if not DATABASE_URL:
            print("Error: DATABASE_URL env var is required.", file=sys.stderr)
            sys.exit(1)
        MODEL = "{embedding_alias}"
        EXPECTED_DIM = {vector_dim}


        def embed_text(text: str) -> list[float]:
            url = f"{{OLLAMA_HOST}}/api/embeddings"
            body = json.dumps({{"model": MODEL, "prompt": text}}).encode("utf-8")
            req = urllib.request.Request(
                url, data=body, headers={{"Content-Type": "application/json"}}, method="POST"
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.load(resp)
            vec = data.get("embedding")
            if not isinstance(vec, list):
                raise RuntimeError(f"Unexpected Ollama response: {{data!r}}")
            if len(vec) != EXPECTED_DIM:
                raise RuntimeError(
                    f"Embedding dim {{len(vec)}} != EXPECTED_DIM {{EXPECTED_DIM}} — "
                    "update EXPECTED_DIM and Postgres vector(N) to match your model."
                )
            return vec


        def main() -> None:
            text = os.environ.get("SAMPLE_TEXT", "Hello from Local Model Assessor stack handoff.")
            vec = embed_text(text)
            vec_literal = "[" + ",".join(str(x) for x in vec) + "]"
            with psycopg.connect(DATABASE_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO documents (content, metadata, embedding)
                        VALUES (%s, %s, %s::vector)
                        RETURNING id
                        """,
                        (text, {{"source": "embed_sample"}}, vec_literal),
                    )
                    new_id = cur.fetchone()[0]
                conn.commit()
            print(f"Inserted documents.id={{new_id}} (dim={{len(vec)}})")


        if __name__ == "__main__":
            main()
        '''
    ).format(
        ollama_host_default=json.dumps(ollama_host),
        embedding_alias=json.dumps(embedding_alias),
        vector_dim=vector_dim,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate STACK_HANDOFF.md + embed_sample.py from model-assessor.db",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output directory (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--active-only",
        action="store_true",
        help="Only consider provisioned_models with is_active=1 (no role_model fallback)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print files to stdout; do not write",
    )
    parser.add_argument(
        "--ollama-host",
        default=OLLAMA_DEFAULT,
        help="Ollama base URL for generated samples",
    )
    parser.add_argument(
        "--vector-dim",
        type=int,
        default=DEFAULT_VECTOR_DIM,
        help=f"Embedding dimension documented in handoff (default {DEFAULT_VECTOR_DIM})",
    )
    args = parser.parse_args()

    try:
        db_path = lma_paths.require_db_path()
    except lma_paths.PathResolutionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        info = resolve_embedding_model(db_path, active_only=args.active_only)
    except EmbeddingResolutionError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    md = build_stack_handoff_md(
        embedding_alias=info["alias"],
        ollama_host=args.ollama_host,
        vector_dim=args.vector_dim,
        resolved_from=info["source"],
        is_active=info.get("is_active"),
        create_command=info.get("create_command"),
    )
    py = build_embed_sample_py(
        embedding_alias=info["alias"],
        ollama_host=args.ollama_host,
        vector_dim=args.vector_dim,
    )

    if not args.dry_run:
        _patch_schema_vector_dim(args.vector_dim)

    if args.dry_run:
        print("=== STACK_HANDOFF.md ===\n")
        print(md)
        print("\n=== embed_sample.py ===\n")
        print(py)
        return

    out_dir = args.output_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "STACK_HANDOFF.md").write_text(md, encoding="utf-8")
    (out_dir / "embed_sample.py").write_text(py, encoding="utf-8")
    print(f"Wrote {out_dir / 'STACK_HANDOFF.md'}")
    print(f"Wrote {out_dir / 'embed_sample.py'}")


if __name__ == "__main__":
    main()
