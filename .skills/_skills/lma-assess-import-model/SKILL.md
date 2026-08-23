---
name: lma-assess-import-model
description: "Assess a new Ollama model, generate YAML, import to DB, and export the report. On Apple Silicon, prefer Ollama -mlx library tags when they exist."
triggers:
  - assess model
  - evaluate model
  - add model
  - import model
  - new model yaml
  - discover models
  - new models
  - ollama search
  - popular models
  - find models
  - who assessed
  - created_by
  - provenance
  - assessor
  - ollama mlx
  - prefer mlx tag
  - 27b-mlx
dependencies:
  - lma-python-env
  - lma-db-core
  - lma-ide-config
version: "1.3.2"
---

# LMA Assess & Import Model

## When to use this skill

Load when the user wants to assess a new model from the Ollama catalog, discover popular models, import a YAML assessment into the DB, or query/set provenance on model records. For HF GGUF models **not** in the Ollama library, load `lma-hf-gguf-ollama` instead (it depends on this skill). For HuggingFace MLX safetensors via **mlx-lm** (not Ollama), load `lma-mlx-lm` instead.

Ollama library tags ending in `-mlx` stay in **this** skill. They are not mlx-lm. Load [references/ollama-mlx-tags.md](references/ollama-mlx-tags.md) before choosing a tag or comparing an Ollama candidate on Apple Silicon.

> **Cloud models are excluded.** Never assess or import models that exist only as cloud/API proxies (e.g. Ollama `model:cloud` tags). If a model is cloud-only on Ollama, inform the user and suggest checking [Hugging Face](https://huggingface.co) for a local alternative (GGUF or MLX format).

## Instructions

### 1. Discover new models (optional starting point)

**HF Hub (optional):** Load **`lma-hf-mcp`** for discovery — **REST** (`hf-hub-api.py`) for lists/counts, **MCP** (`hub_repo_details`, `hub_repo_search`) for drill-down; **avoid `hf_hub_query`**. If MCP offline: REST script + fallbacks in that skill. Skip Hub search if the user already named a model or URL.

**Ollama catalog:** Follow `LLM-prompts/ollama-search.md`:
1. Fetch the Ollama popular models page.
2. Parse and pre-filter against existing DB models.
3. Cap at 7 candidates.
4. Assess each via the assessment prompt (step 2 below).

### 2. Assess a model

On Apple Silicon, choose the Ollama tag per [references/ollama-mlx-tags.md](references/ollama-mlx-tags.md) **before** writing YAML. Prefer the same-size `-mlx` library tag over the GGUF default when it exists and keeps the intended hardware class.

Read `LLM-prompts/model-assessment-prompt.yaml` for the full assessment rubric. Key outputs:
- Model specs (VRAM, context, class, speed, capabilities).
- Role assignments (`by_role`) — coding, chat, writing, embedding, etc.
- Constraint flags (`by_constraint`) — vision, tools, reasoning, etc.
- Provisioning config — per-role Modelfile overrides (context, temperature, system prompt).

Run `./scripts/py scripts/lma_paths.py`, read the resolved `hardware_profile` path, and gate all assessments on that file — especially `vram_budget`, `context_strategy`, and heavy-lifter / co-run rules. Do not assume full advertised context from the upstream card.

Mock hardware is rejected by default. Only when the user explicitly asks to assess against simulated inventory, rerun `./scripts/py scripts/lma_paths.py --allow-mock --format json`, confirm `hardware_profile.mock` is true, and label the assessment simulated. A mock budget supports fit planning only: do not claim the host can run the model, install or benchmark on that basis, or report estimated `tps` as measured.

### 3. Write assessment YAML

Output goes to `model-data/new-models.yaml` (gitignored). Use the template:

```bash
cp model-data/new-models.template.yaml model-data/new-models.yaml
```

Fill in the YAML structure per the assessment prompt's schema.

### 4. Import to DB

```bash
./scripts/py scripts/add-model-from-yaml.py [--assessor NAME --assessor-type TYPE] model-data/new-models.yaml
```

This writes to: `models`, `role_model`, `constraint_model`, `model_docs`, `provisioned_models`. It also generates Modelfiles under `model-data/modelfile/*.mf`.

### 5. Export the report

```bash
./scripts/py scripts/export-assessed-models.py [path]
```

Generates `model-data/assessed-models.md` (or a custom path).

### 6. Build clones in Ollama (when provisioning)

For each new or updated `provisioning` row, run the base `install` command (if needed), then each clone `create_command` from the DB or Modelfile path. Confirm with `ollama list`.

```bash
./scripts/query-db.sh "SELECT alias, create_command, pull_command FROM provisioned_models WHERE base_model_id='<model_id>'"
```

### 7. IDE config sweep (mandatory)

After imports and whenever clones are built or removed, run the sweep (`lma-ide-config` skill):

```bash
./scripts/py scripts/sweep-ide-config.py
```

Run again if clones were only defined in the DB in step 4 but not yet created in Ollama in step 6.

### 8. Provenance

Content tables track who created and last updated each row:

| Column | Set when | Preserved on update? |
|--------|----------|---------------------|
| `created_at` | First insert | Yes |
| `created_by` | First insert (assessor name) | Yes |
| `created_by_type` | First insert (`local`/`cloud`/`human`) | Yes |
| `updated_at` | Every write | No (overwritten) |
| `updated_by` | Every write (assessor name) | No (overwritten) |
| `updated_by_type` | Every write | No (overwritten) |

**How to set provenance:**

Via CLI flags:
```bash
./scripts/py scripts/add-model-from-yaml.py --assessor gpt-oss:20b --assessor-type local model-data/new-models.yaml
```

Via env vars:
```bash
LMA_ASSESSOR=gpt-oss:20b LMA_ASSESSOR_TYPE=local ./scripts/py scripts/add-model-from-yaml.py model-data/new-models.yaml
```

Via direct SQL (if inserting manually): include `created_by`, `created_by_type`, `updated_by`, `updated_by_type` in the INSERT.

**Query provenance:**
```bash
./scripts/query-db.sh "SELECT model_id, created_at, created_by, created_by_type, updated_at, updated_by FROM models"
```

## Notes

- `model-data/new-models.yaml` and `model-data/modelfile/*` are gitignored.
- `assessed-models.md` is also gitignored — it's a generated artifact.
- Discovery via `ollama-search.md` and assessment via `model-assessment-prompt.yaml` are LLM prompt files — reference them, don't duplicate their content.
- End every add/import flow with `./scripts/py scripts/sweep-ide-config.py` once Ollama reflects the new inventory.
- Apple Silicon Ollama `-mlx` tags: [references/ollama-mlx-tags.md](references/ollama-mlx-tags.md). HuggingFace mlx-lm remains a separate skill (`lma-mlx-lm`).
