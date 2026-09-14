# Project Rules for AI Coding Agents

> **Cursor:** `.cursorrules` → reference this file; `required_permissions: ["all"]` for git if sandbox blocks `.git`.

**Agents:** shell-capable IDEs only — query DB, run scripts; do not ask users to paste data.

**Scope:** Procedural workflows live in **skills** under [`.skills/_skills/`](.skills/_skills/) (index: [`.skills/_index.md`](.skills/_index.md)). This file is the **spine** — non-negotiable conventions, static reference tables, and pointers. [README.md](README.md) = human quick start + tree.

### LMA version

**`2.10.0`** – bump **MAJOR** for breaking paths, agent-facing contracts, or DB/schema expectations without a clear migration; **MINOR** for additive capability (e.g. new runtime, integration, or skills surface); **PATCH** for fixes and docs-only; keep **README.md** and this heading in sync; prefer non-`x.y.0` patch on intentional release lines.

---

## Skills (agnostic / multi-ecosystem)

This repository uses **Path B** from the bundled skills harness: **portable skills** under [`.skills/`](.skills/) (manifest: [`.skills/_index.md`](.skills/_index.md)), kit vendored at [`.skills-harness/`](.skills-harness/) (git subtree; `skills-harness` remote), **no** tool-specific runtime harness pasted from [`.skills/_harness/*_template.md`](.skills/_harness/) into this tree. Those templates are **reference** for consumers who clone this repo and may run Path A in their own environment.

**Authoring:** Use bundled `skill-template` / `skill-author` and the index when adding skills. Do **not** paste ecosystem harness blocks into this file for this repository. Repo-specific LMA skills are registered in [`.skills/_index.md`](.skills/_index.md) — load the right one by matching user intent to triggers.

**Gate:** Do not create, rename, delete skills under `.skills/_skills/`, change `.skills/_index.md`, or load full `SKILL.md` for skill refactors **unless** the user's task explicitly includes that work. Reading `.skills/_index.md` to describe the system is fine.

---

## Non-negotiables

- **Python:** Always run scripts via `./scripts/py scripts/<name>.py …` from the repo root. See `lma-python-env` skill for venv details.
- **DB path:** `LMA_DB` env var overrides the DB path for every consumer. Without it, `LMA_ROOT` relocates the default `model-data/model-assessor.db` for Python scripts, `query-db.sh`, `init-db.sh`, and `migrate-schema.sh`.
- **Optional LMO sidecar:** LMA works alone. When [Local Model Orchestrator](https://github.com/Gargoyle-Apps/local-model-orchestrator) is cloned locally, share **absolute paths** (env or gitignored `integrations/lmo/paths.yaml`). LMO may own hardware/software YAML; LMA always owns the model DB. Resolve with `./scripts/py scripts/lma_paths.py`. Mock/dry-run profiles are rejected unless the operator explicitly passes `--allow-mock` or sets `LMA_ALLOW_MOCK=1`; keep them untracked and label all derived results simulated. Contract: [integrations/lmo/lma-lmo-contract.md](integrations/lmo/lma-lmo-contract.md). Skill: `lma-lmo-sidecar`.
- **Queries:** `./scripts/query-db.sh "SQL"` — always pass SQL as a quoted string argument.
- **If DB missing:** `./scripts/init-db.sh`. **If columns/tables missing:** `./scripts/migrate-schema.sh`.
- **Tests:** `./scripts/py -m pytest tests/ -v` from repo root. Add tests for new helpers and ingestion paths. Dev deps: `pip install -r requirements-dev.txt`.
- **Cloud models excluded:** Never assess, import, or recommend models that exist only as cloud/API proxies (e.g. Ollama `model:cloud` tags). If a model is cloud-only, inform the user and suggest checking [HuggingFace](https://huggingface.co) for a local alternative.
- **Model runtimes:** Ollama is primary. On Apple Silicon, prefer an Ollama library `-mlx` tag over the same-size GGUF default when both exist (`runtime` stays `ollama`; see `lma-assess-import-model` `references/ollama-mlx-tags.md`). **MLX LM** (`runtime=mlx`) is a separate optional path for HuggingFace MLX safetensors with no Ollama equivalent. See `lma-mlx-lm` and README § "Model Runtimes: Ollama vs MLX LM."
- **HF Hub discovery:** **REST + MCP hybrid** — `./scripts/py scripts/hf-hub-api.py` for lists/counts/collections; MCP (`hub_repo_details`, `hub_repo_search`, `hf_doc_search`, `hf_whoami`) for drill-down. **Avoid `hf_hub_query`** (hangs/timeouts). See `lma-hf-mcp` skill and [integrations/mcp/hf-hub-api.md](integrations/mcp/hf-hub-api.md).

---

## Local vs Tracked Files

| Type | Files |
|------|-------|
| **Tracked** | Templates (`*.template.yaml`), `LLM-prompts/`, scripts, `requirements.txt`, `Brewfile` (optional `libpq` via `brew bundle`), `AGENTS.md`, `.skills/` (consumer skills + `_index.md`; `_harness/` symlinked from subtree), `.skills-harness/` (skills-harness git subtree), `integrations/IDE-model-management/`, `integrations/embed-retrieval-stack/` (compose + `embed-retrieval-stack.md` + `versions.lock.yaml` + `.env.example`), `integrations/mcp/` (`huggingface-mcp.md`, `hf-hub-api.md`, `scout/.gitkeep`), `integrations/lmo/` (`lma-lmo-contract.md`, `paths.template.yaml`), `tests/`, `requirements-dev.txt` |
| **Gitignored** | `.venv/`, `model-assessor.db`, `hardware-profile.yaml`, `software-profile.yaml`, `assessed-models.md`, `model-data/new-models.yaml`, `model-data/model-lookup.json`, `model-data/modelfile/*` (except `.gitkeep`), `.cursorrules`, `.agents/`, `.continue/`, `.opencode/`, `opencode.json`, `opencode.jsonc`, local config copies (`integrations/IDE-model-management/*/generated/*`, `integrations/IDE-model-management/continue/config.yaml`, `integrations/IDE-model-management/cline/provider-settings.json`, `integrations/IDE-model-management/opencode/opencode.json`, `integrations/IDE-model-management/pi/*.json`, `integrations/IDE-model-management/zed/settings.json`), `integrations/embed-retrieval-stack/out/`, `integrations/mcp/scout/*` (except `.gitkeep`), `integrations/lmo/paths.yaml`, `ref/`, `.pytest_cache/` |

Create local files from templates: `cp computer-profile/hardware-profile.template.yaml computer-profile/hardware-profile.yaml` (or use setup in `model-assessment-prompt.yaml`). For assessment output: `cp model-data/new-models.template.yaml model-data/new-models.yaml`.

**Repo development vs using the repo:** End-user agents rely on this section matching **`.gitignore`** and the real tree. When you change ignore rules, add generated artifacts, or new local-only paths, update **this table** and **README.md** ("Repo vs Local") together so agents and humans stay aligned.

---

## Hardware Budget

Resolve the live hardware YAML first (LMO sidecar or local file):

```bash
./scripts/py scripts/lma_paths.py
```

Then read `vram_budget` from the printed `hardware_profile` path (standalone default: `computer-profile/hardware-profile.yaml`).
For an explicitly requested simulation, rerun with `--allow-mock`; never describe its budget as the current host.

Effective budget ≈ `total_available - os_headroom_gb`.

**Co-run rule:** `(model_vram + concurrency_reserve) < total_available` → can co-run. Heavy Lifters (30–48 GB) run solo.
