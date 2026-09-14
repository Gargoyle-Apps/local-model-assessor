# Local Model Assessor

**Version 2.10.0** — bump criteria: [AGENTS.md](AGENTS.md#lma-version).

For **tool-calling agents** in IDEs (Cursor, Cline, Continue, …): query SQLite and run repo scripts — not for chat-only LLMs without shell access.

**Prerequisites:** [Ollama](https://ollama.com) · Python 3 · `./scripts/bootstrap-python.sh` (creates gitignored `.venv` from [requirements.txt](requirements.txt)) · run scripts with `./scripts/py` — see [`lma-python-env`](.skills/_skills/lma-python-env/SKILL.md) skill in [`.skills/_index.md`](.skills/_index.md) · IDE agent · [profiles](#3-define-your-environment) · optional LLM for assessments · optional [mlx-lm](https://github.com/ml-explore/mlx-lm) for Apple Silicon MLX models · **Docker** only for [integrations/embed-retrieval-stack/embed-retrieval-stack.md](integrations/embed-retrieval-stack/embed-retrieval-stack.md) (`docker compose exec postgres psql …` for checks).

---

## Repo vs Local

Ships **scripts, schema, templates** — empty `model-assessor.db` until you init, profile, assess. **`Brewfile`:** optional `brew bundle` → `libpq` (keg-only; see `brew info libpq`); not needed for Docker stack (`docker compose exec`). **Tracked:** templates under `computer-profile/`, `model-data/` (e.g. `*.template.yaml`, `modelfile/.gitkeep`), `scripts/`, `.skills/` + `.skills-harness/` (skills harness; see [Skills harness](#skills-harness-third-party)), `integrations/` (copy-out: IDE + embed stack + `mcp/scout/.gitkeep` + optional LMO contract). **Gitignored:** profiles, DB, `new-models.yaml`, `model-data/model-lookup.json`, generated modelfiles, `integrations/mcp/scout/*` (scout notes), `integrations/lmo/paths.yaml`, local IDE copies (`integrations/IDE-model-management/*/generated/*`, `continue/config.yaml`, `cline/provider-settings.json`, `opencode/opencode.json`, `opencode.json`, `opencode.jsonc`, `pi/*.json`, `zed/settings.json`), `integrations/embed-retrieval-stack/out/`, `ref/`, `.cursorrules`. Details: [AGENTS.md](AGENTS.md) + `.gitignore`.

---

## Quick Start

### 1. Add to Your Project

```bash
# Clone into your project
git clone https://github.com/Gargoyle-Apps/Local-Model-Assessor.git .model-assessor

# Or copy the folder directly
cp -r /path/to/local-model-assessor .model-assessor
```

```text
.model-assessor/
├── computer-profile/
│   ├── hardware-profile.template.yaml
│   ├── software-profile.template.yaml
│   ├── hardware-profile.yaml        # local (gitignored)
│   ├── software-profile.yaml        # local (gitignored)
│   └── .gitkeep
├── model-data/
│   ├── model-assessor.db            # local SQLite DB (gitignored)
│   ├── assessed-models.md            # regenerated from DB (gitignored)
│   ├── new-models.template.yaml     # schema for assessment output (tracked)
│   ├── new-models.yaml              # assessment output (gitignored; copy from template)
│   ├── modelfile/                   # Ollama Modelfiles (.mf); contents gitignored, .gitkeep only
│   └── .gitkeep
├── scripts/
│   ├── py                       # run Python with .venv (+ sync requirements.txt)
│   ├── bootstrap-python.sh      # create .venv and pip install -r requirements.txt
│   ├── schema.sql
│   ├── init-db.sh
│   ├── migrate-schema.sh
│   ├── add-model-from-yaml.py
│   ├── export-assessed-models.py
│   ├── generate-ide-config.py       # Continue + Cline/Roo config from DB
│   ├── sweep-ide-config.py          # Sync is_active, regenerate + deploy IDE configs
│   ├── generate-stack-handoff.py    # Postgres/pgvector/AGE + embedding handoff
│   ├── import-profiles.py
│   ├── lma_paths.py                 # resolve DB + profile paths (optional LMO)
│   ├── export-lmo-snapshot.py       # zip hardware/software/DB for LMO study
│   ├── reconcile-inventory.py       # present/removed vs ollama list (+ history seed)
│   └── query-db.sh
├── integrations/                    # copy-out kits: IDE configs + Docker data stack
│   ├── embed-retrieval-stack/       # Postgres + pgvector + Apache AGE
│   │   ├── embed-retrieval-stack.md
│   │   ├── versions.lock.yaml
│   │   ├── docker-compose.yml
│   │   ├── Dockerfile
│   │   ├── .env.example
│   │   └── init/
│   ├── IDE-model-management/
│   │   ├── IDE.md                   # setup docs, role mappings, timeout policy, templates
│   │   ├── continue/                # Continue (VS Code)
│   │   ├── cline/                   # Cline / Roo Code (JSON provider settings)
│   │   ├── opencode/                # OpenCode (CLI/TUI)
│   │   ├── goose/                   # Goose (CLI/Desktop)
│   │   ├── pi/                      # Pi coding-agent (Terminal)
│   │   └── zed/                     # Zed (Editor)
│   ├── mcp/
│   │   ├── hf-hub-api.md            # REST + MCP hybrid; hf_hub_query gap
│   │   ├── huggingface-mcp.md       # HF MCP setup + scout folder
│   │   └── scout/                   # local discovery notes (gitignored except .gitkeep)
│   └── lmo/                         # optional Local Model Orchestrator sidecar
│       ├── lma-lmo-contract.md      # path-passing contract (LMA-side)
│       └── paths.template.yaml      # copy to paths.yaml (gitignored) when LMO is cloned
├── ref/                             # local agent config copies (gitignored)
├── LLM-prompts/
│   ├── model-assessment-prompt.yaml
│   ├── model-selector-prompt.yaml
│   └── ollama-search.md
├── .skills/                         # portable consumer skills + `_index.md`
├── .skills-harness/                 # vendored third-party skills kit (git subtree)
├── tests/                           # pytest suite
├── AGENTS.md                        # agent spine: non-negotiables, file layout, hardware budget
├── requirements.txt                 # PyYAML for YAML import scripts; install via bootstrap-python.sh
├── requirements-dev.txt             # pytest and dev tooling
├── Brewfile                         # optional: brew bundle → libpq
├── .gitignore
└── LICENSE
```

### 2. Initialize the Database and Profiles

```bash
cd .model-assessor

# Create empty DB (init-db.sh creates only the database, not profile files)
./scripts/init-db.sh
# Existing DB? Run ./scripts/migrate-schema.sh to add assessed_at, inventory_status, and other columns (same LMA_DB override as Python scripts)
cp computer-profile/hardware-profile.template.yaml computer-profile/hardware-profile.yaml
cp computer-profile/software-profile.template.yaml computer-profile/software-profile.yaml

# Python deps (PEP 668-safe venv); then import profiles into DB (after editing them)
./scripts/bootstrap-python.sh
./scripts/py scripts/import-profiles.py
```

### 3. Define Your Environment

Edit the **local** profile files in `computer-profile/`:

**`hardware-profile.yaml`** — Your machine's specs and VRAM budget:
```yaml
system:
  name: "Your Machine"
  unified_ram: "64GB"  # or available RAM
vram_budget:
  total_available: 50  # GB safe for Ollama
```

**`software-profile.yaml`** — Your IDE and coding agents:
```yaml
ide:
  name: "VS Code"  # or Cursor, etc.
primary_agent:
  name: "Cline"    # your main coding agent
```

Hardware and software YAML are optional to author here if [Local Model Orchestrator](https://github.com/Gargoyle-Apps/local-model-orchestrator) (LMO) is cloned locally and owns those files. Point LMA at them with `LMA_HARDWARE_PROFILE` / `LMA_SOFTWARE_PROFILE` or `integrations/lmo/paths.yaml`. See [Optional LMO sidecar](#optional-lmo-sidecar). The model database stays in this repo.

### 4. Run Initial Model Assessments

Use `LLM-prompts/model-assessment-prompt.yaml` + your hardware profile + Ollama model URLs. Send to `gpt-oss:20b` (or a capable cloud LLM). Save the YAML output to `model-data/new-models.yaml`, then run the [assessment flow](#assess-new-models).

### 5. Model Selection: Configure Your Agents

Your coding agent reads the selector prompt and queries the DB directly:

```text
[System: contents of .model-assessor/LLM-prompts/model-selector-prompt.yaml]

I'm setting up Cline for coding tasks. What models should I configure?
```

The agent will run `./scripts/query-db.sh` or `sqlite3` to look up models, roles, and constraints from `model-assessor.db`. No manual data pasting required.

### 6. Install & Configure

Install the recommended models:
```bash
ollama pull <model:tag>
```

Configure your agent's settings file with the recommended models. After provisioned clones exist in Ollama, run `./scripts/py scripts/sweep-ide-config.py` (or `generate-ide-config.py --dry-run` to preview only) — see [integrations/IDE-model-management/IDE.md](integrations/IDE-model-management/IDE.md) and [`lma-ide-config`](.skills/_skills/lma-ide-config/SKILL.md).

### 7. Ad-Hoc Selection

When switching tasks or needing a different capability, invoke the model selector:

```text
What model should I use for [vision tasks / creative writing / RAG / etc.]?
```

---

## Assess new models

1. `LLM-prompts/model-assessment-prompt.yaml` + `hardware-profile.yaml` + URLs (Ollama including `-mlx` tags via [`lma-assess-import-model`](.skills/_skills/lma-assess-import-model/SKILL.md), HF GGUF via [`lma-hf-gguf-ollama`](.skills/_skills/lma-hf-gguf-ollama/SKILL.md), or HuggingFace MLX via [`lma-mlx-lm`](.skills/_skills/lma-mlx-lm/SKILL.md))
2. LLM → save YAML → `model-data/new-models.yaml`
3. `./scripts/py scripts/add-model-from-yaml.py model-data/new-models.yaml` then `./scripts/py scripts/export-assessed-models.py`

**Discover:** `LLM-prompts/ollama-search.md` → [Ollama popular](https://ollama.com/search?o=popular), cap 7, same import flow; sets `meta.last_ollama_scan`. Cloud-only models are excluded — check [HuggingFace](https://huggingface.co) for local alternatives.

---

## IDE + embed stack

- **IDEs:** [integrations/IDE-model-management/IDE.md](integrations/IDE-model-management/IDE.md) — roles, timeouts, Continue (`~/.continue/config.yaml`) / Cline-Roo (JSON), others; `sweep-ide-config.py` / `generate-ide-config.py`; see [`lma-ide-config`](.skills/_skills/lma-ide-config/SKILL.md) skill.
- **Postgres + pgvector + AGE:** [integrations/embed-retrieval-stack/embed-retrieval-stack.md](integrations/embed-retrieval-stack/embed-retrieval-stack.md) — pins, compose under `integrations/embed-retrieval-stack/`, use cases, troubleshooting. **Handoff** (`STACK_HANDOFF.md`, `embed_sample.py`): assessed **embedding** in DB → `./scripts/py scripts/generate-stack-handoff.py` → `integrations/embed-retrieval-stack/out/` (gitignored); copy stack + `out/` to your app.
- **Hugging Face Hub:** [integrations/mcp/hf-hub-api.md](integrations/mcp/hf-hub-api.md) — **REST + MCP hybrid** (`hf-hub-api.py` for lists/collections; MCP for drill-down; **avoid `hf_hub_query`**). MCP setup: [integrations/mcp/huggingface-mcp.md](integrations/mcp/huggingface-mcp.md); scout notes in `integrations/mcp/scout/` (gitignored).
- **Optional LMO sidecar:** [integrations/lmo/lma-lmo-contract.md](integrations/lmo/lma-lmo-contract.md) — local path passing with Local Model Orchestrator. See [Optional LMO sidecar](#optional-lmo-sidecar).

---

## Skills harness (third-party)

The kit is vendored as a **git subtree** at [`.skills-harness/`](.skills-harness/) ([Gargoyle-Apps/skills-harness](https://github.com/Gargoyle-Apps/skills-harness), MIT, **v1.6.0**). Runtime layout:

- **`.skills-harness/`** — upstream kit (updated with `git subtree pull`; do not hand-edit)
- **`.skills/`** — consumer tree: symlinked kit `_harness/` and bundled skills; **real directories** for repo-specific `lma-*` skills under `.skills/_skills/`

**Validate layout:** `.skills/_harness/check.sh` prints directory-symlink topology for kit skills (e.g. `_skills/skill-author: directory symlink → … ✓`). Kit skills are linked at the **directory** level — inner `SKILL.md` files look like regular files; use `check.sh` or `readlink .skills/_skills/<name>`, not `readlink` on inner paths.

Policy is **agnostic / multi-ecosystem** (Path B): see [AGENTS.md](AGENTS.md) **Skills (agnostic / multi-ecosystem)** — we do not merge tool-specific harness templates from `.skills/_harness/` into this project.

**Update kit:** `git fetch skills-harness && git subtree pull --prefix=.skills-harness skills-harness main --squash` (or pin a release tag), then `.skills/_harness/migrate-to-subtree.sh --skip-subtree --reconcile --apply` and `.skills/_harness/check.sh --link` (see **harness-subtree** skill). **Credit:** shared templates and kit skills — contribute upstream; LMA skills stay in this repo.

---

## Model Runtimes: Ollama vs MLX LM

Two **discrete** Apple Silicon MLX paths exist. Do not mix them.

### 1. Ollama `-mlx` tags (still Ollama)

**Ollama** is the primary runtime. Use it for any model in the [Ollama library](https://ollama.com/library) or importable as GGUF. It provides the HTTP API that IDEs connect to, provisioned clones, and the assessment/selection/config pipeline.

On **Apple Silicon**, if the library ships a same-size `-mlx` tag (for example `qwen3.8:27b-mlx` next to `qwen3.8:27b`), **pull and compare that tag first**. It stays `runtime=ollama`. Do not set `runtime: mlx`. Do not run it through mlx-lm. Strategy: [`lma-assess-import-model`](.skills/_skills/lma-assess-import-model/SKILL.md) → `references/ollama-mlx-tags.md`.

### 2. MLX LM (HuggingFace safetensors)

**[MLX LM](https://github.com/ml-explore/mlx-lm)** is an optional secondary runtime. Use it **only** when the model is **not** in Ollama (no library tag, including no `-mlx` tag) but exists as MLX safetensors, typically from [mlx-community](https://huggingface.co/mlx-community). Set `runtime: mlx`. No Modelfile clones. See [`lma-mlx-lm`](.skills/_skills/lma-mlx-lm/SKILL.md).

When to use MLX LM:
- The model has **no Ollama equivalent** (including no `-mlx` library tag)
- You need **mlx-lm-only features** (LoRA fine-tuning, `mlx_lm.server` against a Hub repo)
- You want an mlx-community quant that Ollama does not ship

When *not* to use MLX LM:
- The same weights are already an Ollama tag (GGUF or `-mlx`)
- You're on an Intel Mac or non-macOS platform

The `runtime` column is `ollama` (default, including Ollama `-mlx` tags) or `mlx` (mlx-lm only). Cloud-only Ollama tags remain excluded.

---

## Hardware Classes

Assess hardware you may buy or deploy with [`lma-hardware-assessment`](.skills/_skills/lma-hardware-assessment/SKILL.md). Give it a SKU, product page, or specifications to get model-size, quantization, practical context, theoretical performance, concurrency, and workload-fit estimates. If a local `hardware-profile.yaml` exists, it can add a separate comparison with the declared current system; it does not probe the host or overwrite the profile.

### Profile classes

Models are categorized by VRAM footprint and performance. **Full fields** (budget, `os_headroom_gb`, quantization, concurrency, `context_strategy`, hardware class definitions) live in **`computer-profile/hardware-profile.template.yaml`** — copy to `hardware-profile.yaml` and edit.

| Class | VRAM | Speed | Use Case |
|-------|------|-------|----------|
| **Utility** | 1-4GB | 100-1000 t/s | Embedding, OCR (always-on) |
| **Speedster** | <8GB | 80-120 t/s | Autocomplete, quick vision |
| **Middleweight** | 8-12GB | 45-50 t/s | Interactive assistant |
| **Daily Driver** | 12-24GB | 25-40 t/s | Reasoning, coding |
| **Heavy Lifter** | 30-48GB | ~15 t/s | Quality-critical (runs solo) |

**Concurrency:** 1 Utility + 1 Speedster + 1 larger model can run simultaneously. Heavy Lifters cannot co-run.

---

## Optional LMO sidecar

[Local Model Orchestrator (LMO)](https://github.com/Gargoyle-Apps/local-model-orchestrator) can own **hardware** and **software** inventory when both repos are cloned on the same machine. LMA still owns **`model-assessor.db`**. Neither repo is required for the other to run.

Live sharing is **absolute local paths** (environment variables or gitignored `integrations/lmo/paths.yaml`), not file copies. Resolve and inspect:

```bash
./scripts/py scripts/lma_paths.py
./scripts/py scripts/lma_paths.py --format json
```

Mock inventory is an explicit planning mode. Mark it with `profile.mode: dry_run`,
`profile.mock: true`, or `profile.physical_hardware_present: false`, keep the YAML
untracked, and opt in for that operation:

```bash
./scripts/py scripts/lma_paths.py --allow-mock --format json
./scripts/py scripts/import-profiles.py --allow-mock
./scripts/py scripts/export-lmo-snapshot.py --allow-mock
```

Without `--allow-mock` (or `LMA_ALLOW_MOCK=1` for scripts that consume profiles),
resolution stops instead of silently treating simulated capacity as the current
machine. The resolver reports `mock` and `profile_mode`; label every derived
assessment or recommendation as simulated.

Pack a local study zip of the current hardware YAML, software YAML, and model DB (writes gitignored `ref/lma-lmo-snapshot.zip`):

```bash
./scripts/py scripts/export-lmo-snapshot.py
```

The archive contains the full database and absolute local paths. Keep it on this machine; do not upload or send it externally.

Full contract: [integrations/lmo/lma-lmo-contract.md](integrations/lmo/lma-lmo-contract.md). Agent workflow: [`lma-lmo-sidecar`](.skills/_skills/lma-lmo-sidecar/SKILL.md).

---

## Roles & Constraints

Query `model-assessor.db` for current assignments:

```bash
./scripts/query-db.sh "SELECT role, variant, model_id FROM role_model"
./scripts/query-db.sh "SELECT constraint_name, model_id FROM constraint_model"
```

Example roles: `coding`, `vision`, `reasoning`, `autocomplete`, `embedding`, `generalist`. See `model-data/assessed-models.md` for descriptions.

---

## Tests

```bash
# Install dev deps (includes pytest + production deps)
.venv/bin/pip install -r requirements-dev.txt
# Run tests
./scripts/py -m pytest tests/ -v
```

Tests cover schema validity, ingestion helpers, end-to-end YAML→DB round-trips, and migration idempotency.

---

## License

[LICENSE](LICENSE) — MIT (ImpureCrumpet; see file for **skills-harness** attribution under `.skills-harness/`). Individual models (Ollama and MLX) have their own licenses — check each model’s page.
