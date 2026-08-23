---
name: lma-model-selection
description: "Select, recommend, or install an Ollama model for a given role or task."
triggers:
  - select model
  - which model
  - recommend model
  - model for coding
  - model for writing
  - best model
  - model details
  - model info
  - assessed models
  - model docs
  - install model
  - pull model
  - ollama pull
  - setup model
dependencies:
  - lma-db-core
  - lma-ide-config
version: "1.2.2"
---

# LMA Model Selection

## When to use this skill

Load when the user asks which model to use for a task, wants model details, or needs to install a model. Covers the full select → recommend → install flow for both Ollama and MLX LM models. Cloud-only models are never recommended.

## Instructions

### 1. Read the selection prompt

Follow `LLM-prompts/model-selector-prompt.yaml` for the full decision rubric.

### 2. Query the DB

Join `role_model` → `provisioned_models` → `models` to find the best candidate:

```bash
./scripts/query-db.sh "SELECT rm.role, rm.variant, rm.model_id, pm.alias, pm.num_ctx, pm.is_active FROM role_model rm LEFT JOIN provisioned_models pm ON rm.model_id = pm.base_model_id AND rm.role = pm.role ORDER BY rm.role"
```

### 3. Check for drift

Run `ollama list` and compare against DB records. If a model is in the DB but not installed locally, note it as needing installation.

### 4. Check hardware budget

```bash
./scripts/py scripts/lma_paths.py
```

Read `vram_budget` from the resolved `hardware_profile` path. Effective budget ≈ `total_available - os_headroom_gb`.

If resolution reports a mock-profile error, do not silently fall back. Only when the user explicitly wants a simulated recommendation, run `./scripts/py scripts/lma_paths.py --allow-mock --format json`, confirm `hardware_profile.mock` is true, and label the recommendation simulated. Do not install or claim host compatibility from mock inventory.

**Co-run rule:** `(model_vram + concurrency_reserve) < total_available` → can co-run. Heavy Lifters (30–48 GB) run solo.

### 5. Recommend

Prefer a **provisioned alias** when `provisioned_models` has an active row for the requested role. Fallback when no clone exists:

```markdown
**Recommended:** `model:tag`
**Class:** [class] | **VRAM:** XGB | **Speed:** ~X t/s
**Why:** [reasoning]
**Alternative:** `backup-model` (reason)
**Install:** `ollama pull model:tag` (or `ollama create -f …` for GGUF bases)
```

### 6. Get model details

For detailed info on a specific model:

```bash
./scripts/query-db.sh "SELECT * FROM model_docs WHERE model_id='...'"
```

Or read `model-data/assessed-models.md` for the human-readable report.

### 7. Install a model

Look up the install command and run it:

```bash
./scripts/query-db.sh "SELECT install FROM models WHERE model_id='...'"
```

The returned command may be `ollama pull <tag>` (catalog models, including Ollama `-mlx` tags), `ollama create -f …` (GGUF bases), or an `mlx_lm.generate` command (`runtime=mlx` HuggingFace models). Check the `runtime` column: `ollama` (default, including library `-mlx` tags) vs `mlx` (mlx-lm only).

On Apple Silicon, if the user asks to pull a library model and a same-size `-mlx` tag exists, install that tag. Load `lma-assess-import-model` for the discrete Ollama `-mlx` tag strategy. Do not route Ollama `-mlx` tags through `lma-mlx-lm`.

After installing a base model and any provisioned clones (`create_command` from `provisioned_models`), sweep IDE config:

```bash
./scripts/py scripts/sweep-ide-config.py
```

Skip the sweep for MLX-only installs (`runtime=mlx`) — `sweep-ide-config.py` covers Ollama provisioned clones only.

## Notes

- `model-selector-prompt.yaml` contains the full decision logic — reference it, don't duplicate.
- The response format above is the standard for model recommendations to users.
