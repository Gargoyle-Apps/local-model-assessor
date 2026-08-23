---
name: lma-mlx-lm
description: "Run and assess HuggingFace MLX safetensors on Apple Silicon via mlx-lm. Do not use for Ollama library -mlx tags."
triggers:
  - mlx-lm
  - MLX LM
  - mlx-community
  - mlx_lm.generate
  - mlx_lm.server
  - HuggingFace MLX
  - safetensors model
dependencies:
  - lma-assess-import-model
version: "1.2.2"
---

# LMA MLX LM

## When to use this skill

Load when the user wants to run, assess, or import an **MLX-format model that is not in the Ollama library** (typically from [mlx-community](https://huggingface.co/mlx-community) on HuggingFace) on an Apple Silicon Mac. Those weights use safetensors and run via the [mlx-lm](https://github.com/ml-explore/mlx-lm) Python package. They do **not** go through Ollama. Set `runtime: mlx`.

**Not this skill:** Ollama library tags ending in `-mlx` (for example `qwen3.8:27b-mlx`). Those stay on Ollama (`runtime` default `ollama`, clones, IDE sweep). Load `lma-assess-import-model` instead. That skill owns the discrete Ollama `-mlx` tag strategy. On Apple Silicon, it prefers the Ollama `-mlx` tag over GGUF when both exist.

## Anti-triggers

- `ollama pull …-mlx` or replacing a GGUF Ollama tag with its `-mlx` sibling
- Any model already listed on [ollama.com/library](https://ollama.com/library)

## Prerequisites

- **Apple Silicon Mac** (M1/M2/M3/M4/… — MLX does not run on Intel Macs)
- **mlx-lm** installed: `uv pip install mlx-lm` (or `pip install mlx-lm`)
- Sufficient **unified memory** for the quantized model size (resolve the live profile with `./scripts/py scripts/lma_paths.py`)

## Instructions

### 0. Discovery (optional)

If the user has no `mlx-community/…` pick yet, load **`lma-hf-mcp`** — **REST first** (`./scripts/py scripts/hf-hub-api.py collections|models --owner mlx-community`), then MCP `hub_repo_details` / `hub_repo_search` for README and quant suffixes (`-4bit`, `-6bit`, `-8bit`). **Do not use `hf_hub_query`.**

**MCP offline:** same REST script or browse [huggingface.co/mlx-community](https://huggingface.co/mlx-community), `WebFetch` a repo card — see `lma-hf-mcp` fallbacks and [integrations/mcp/hf-hub-api.md](../../../integrations/mcp/hf-hub-api.md).

Skip if user already named a repo ID.

### 1. Pre-flight: hardware check

Run `./scripts/py scripts/lma_paths.py`, read the resolved `hardware_profile` path, and confirm the model's weight size fits its unified memory budget. MLX models load entirely into unified memory — the effective budget is the same VRAM concept used for Ollama models.

Only for an explicitly requested simulated fit check, run `./scripts/py scripts/lma_paths.py --allow-mock --format json`. Confirm `hardware_profile.mock` is true, label the result simulated, and stop before download, installation, serving, benchmarking, or import unless the user's request includes those actions with mock inventory.

For quantized models, rough size estimates:
- **4-bit**: ~0.5 GB per billion parameters
- **6-bit**: ~0.75 GB per billion parameters  
- **8-bit**: ~1 GB per billion parameters

MoE models use total parameter count for download size but only activate a fraction per token.

### 2. Understand the key differences from Ollama

| Aspect | Ollama (including `-mlx` tags) | MLX LM (this skill) |
|--------|--------|--------|
| Format | GGUF or Ollama-served MLX | HuggingFace MLX safetensors |
| Install | `ollama pull` or `ollama create -f` | First `mlx_lm.generate` triggers HF download |
| Runtime column | `ollama` (default) | `mlx` |
| Clones | Modelfile-based aliases | Not supported — use CLI flags |
| IDE integration | Native (Ollama provider) | Via `mlx_lm.server` (OpenAI-compatible) |
| Platform | Cross-platform (MLX tags: Apple Silicon) | Apple Silicon only |

### 3. Install and verify

```bash
# Install mlx-lm (if not already)
uv pip install mlx-lm

# Test a model (first run downloads from HuggingFace)
mlx_lm.generate --model mlx-community/ModelName-4bit --prompt "Hello"

# Interactive chat
mlx_lm.chat --model mlx-community/ModelName-4bit

# OpenAI-compatible server (for IDE integration)
mlx_lm.server --model mlx-community/ModelName-4bit --port 8080
```

### 4. Choose the right quantization

The [mlx-community](https://huggingface.co/mlx-community) organization on HuggingFace provides models in multiple quantization levels. Prefer:
- **4-bit** for large models or constrained memory
- **8-bit** when memory allows, for better quality
- **6-bit** as a middle ground

### 5. Fill the assessment YAML

Follow the standard assessment flow from `lma-assess-import-model`, with these MLX-specific fields:

```yaml
models:
  mlx-community/ModelName-4bit:
    vram: 10          # estimated unified memory usage in GB
    ctx: 32768        # context window
    class: Middleweight
    tps: 50           # estimated tokens/sec on your hardware
    runtime: mlx      # REQUIRED — distinguishes from Ollama models
    url: https://huggingface.co/mlx-community/ModelName-4bit
    install: mlx_lm.generate --model mlx-community/ModelName-4bit --prompt "test"
    # Do NOT include provisioning — MLX models don't use Ollama clones
```

Key differences from Ollama YAML:
- **`runtime: mlx`** — required; tells the import script to skip Ollama provisioning
- **`model_id`** — use the full HuggingFace repo path (e.g. `mlx-community/ModelName-4bit`)
- **`install`** — the `mlx_lm.generate` command that triggers download on first run
- **No `provisioning`** — MLX models don't use Ollama Modelfiles or clones
- **`by_role` / `by_constraint` / `model_docs`** — same rules as Ollama models

### 6. Import and export

```bash
./scripts/py scripts/add-model-from-yaml.py [--assessor NAME --assessor-type TYPE] model-data/new-models.yaml
./scripts/py scripts/export-assessed-models.py
```

The import script will store the model with `runtime=mlx` in the DB and skip Ollama clone provisioning.

### 7. Using MLX models with IDEs

MLX LM includes an OpenAI-compatible server:

```bash
mlx_lm.server --model mlx-community/ModelName-4bit --port 8080
```

IDEs that support custom OpenAI-compatible endpoints (Continue, Cline, etc.) can connect to `http://localhost:8080`. This is separate from Ollama's API and requires manual IDE configuration — `generate-ide-config.py` does not currently generate MLX server configs.

## Checklist

- [ ] Confirmed Apple Silicon Mac with sufficient unified memory
- [ ] `mlx-lm` installed (`uv pip install mlx-lm`)
- [ ] Model fits the resolved live hardware budget
- [ ] Tested model locally: `mlx_lm.generate --model <repo> --prompt "test"`
- [ ] Assessment YAML filled with `runtime: mlx`, no `provisioning`
- [ ] Ran `add-model-from-yaml.py` and `export-assessed-models.py`
- [ ] Updated `software-profile.yaml` to include MLX LM as a runtime (if first MLX model)

## Notes

- MLX models are stored in `~/.cache/huggingface/hub/` by default. Unlike Ollama's blob store, they follow standard HuggingFace caching.
- The `mlx_lm.server` command starts a single-model server. To switch models, restart with a different `--model` flag.
- For large models, use `--max-kv-size N` to limit KV cache memory usage (same concept as Ollama's context limits).
- macOS 15+ users can increase wired memory limits for better performance: `sudo sysctl iogpu.wired_limit_mb=N`
- See [mlx-lm README](https://github.com/ml-explore/mlx-lm) for full documentation.
