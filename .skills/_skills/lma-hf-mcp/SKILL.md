---
name: lma-hf-mcp
description: "Hub discovery via REST API + HF MCP (hybrid); avoid hf_hub_query."
triggers:
  - huggingface mcp
  - hf mcp
  - hf-mcp-server
  - search huggingface
  - hub search
  - find gguf
  - mlx-community search
  - hugging face search
  - hf collections
  - mlx-community collections
dependencies: []
version: "1.3.3"
---

# LMA Hugging Face MCP + Hub REST API

## When to use this skill

Load when you need to **discover** Hub resources before or during LMA assessment — model/GGUF/MLX candidates, **collections**, README metadata, HF library docs, datasets, or papers.

**Mandatory hybrid:** use **Hub REST** for lists/counts/pagination, then **HF MCP** for selective drill-down. MCP alone is unreliable for bulk Hub queries.

> **Cloud models excluded.** Only pursue **local weights** (GGUF, safetensors/MLX). After discovery → `lma-assess-import-model`, `lma-hf-gguf-ollama`, or `lma-mlx-lm`.

**Docs:** [integrations/mcp/hf-hub-api.md](../../../integrations/mcp/hf-hub-api.md) (REST + gap) · [integrations/mcp/huggingface-mcp.md](../../../integrations/mcp/huggingface-mcp.md) (MCP setup) · [huggingface.co/settings/mcp](https://huggingface.co/settings/mcp).

## Non-negotiable: REST + MCP hybrid

| Layer | Tool | Use for |
|-------|------|---------|
| **REST** | `./scripts/py scripts/hf-hub-api.py` | Collection lists/counts, org model indexes, pagination, `--json` for scout |
| **MCP** | `hub_repo_details`, `hub_repo_search`, `hf_doc_search` | Single-repo README/license, targeted search, HF docs |
| **MCP probe** | `hf_whoami` | Auth + transport check only |

### Do **not** use `hf_hub_query`

Known gap (Jul 2026): hangs 8–10+ minutes or `MCP -32001` timeout even with explicit `limit` / `scan_limit` / `max_pages`. The same data via REST returns in **&lt;1s**. **Never** route collections, counts, or bulk discovery through `hf_hub_query` until HF fixes it. Log findings in scout notes; see [hf-hub-api.md](../../../integrations/mcp/hf-hub-api.md).

**Without MCP:** REST script + `WebFetch` + user URL — do not block assess/import.

## Instructions

### 1. Confirm MCP is usable (optional accelerator)

```bash
./scripts/py scripts/hf-hub-api.py health
```

MCP: call `hf_whoami`. If connected, continue hybrid workflow. If `hf_whoami` works but a prior `hf_hub_query` hung, **that is expected** — switch to REST, not transport troubleshooting.

**If not connected — graceful fallback:**

1. Suggest connect once: [huggingface-mcp.md](../../../integrations/mcp/huggingface-mcp.md), reload Cursor.
2. Proceed with REST script and table below.

| Need | Primary | Fallback |
|------|---------|------------|
| Collections / org lists | `hf-hub-api.py collections` | `WebFetch` collection page; user snapshot |
| Org model index | `hf-hub-api.py models --author …` | [huggingface.co/models](https://huggingface.co/models) |
| Ollama catalog | `LLM-prompts/ollama-search.md` | [ollama.com/library](https://ollama.com/library) |
| GGUF / HF repo | REST search + MCP `hub_repo_details` | `WebFetch` model card; user URL |
| MLX conversion | REST `mlx-community` + MCP `hub_repo_search` | Browse [mlx-community](https://huggingface.co/mlx-community) |
| HF library how-to | MCP `hf_doc_search` | [huggingface.co/docs](https://huggingface.co/docs) |

### 2. Pick the right tool (routing)

| LMA phase | Layer | Tool / command |
|-----------|-------|----------------|
| Collection count / recent lists | **REST** | `hf-hub-api.py collections --owner mlx-community --recent 10` |
| mlx-community (or org) model index | **REST** | `hf-hub-api.py models --author mlx-community --limit 20` |
| Cloud-only Ollama → local alt | **MCP** | `hub_repo_search` — "GGUF quants for &lt;model&gt; Ollama" |
| MLX path (no Ollama/GGUF) | **REST** then **MCP** | REST index → `hub_repo_details` on 1–3 candidates |
| README, license, arch hints | **MCP** | `hub_repo_details` (`include_readme` when needed) |
| Quant / PEFT / transformers | **MCP** | `hf_doc_search` |
| Benchmark / eval notes | **MCP** | `hub_repo_search` (datasets) or `paper_search` |
| Auth / transport probe | **MCP** | `hf_whoami` |
| ~~Broad Hub navigator~~ | ~~MCP~~ | ~~`hf_hub_query`~~ — **avoid** |

### 3. Discovery → assess handoff

After REST shortlist + MCP drill-down on **local-runnable** candidates:

| Candidate type | Next skill |
|----------------|------------|
| In Ollama library | `lma-assess-import-model` |
| GGUF not in Ollama | `lma-hf-gguf-ollama` |
| MLX safetensors (`mlx-community/…`) | `lma-mlx-lm` |

Run `./scripts/py scripts/lma_paths.py` and gate on the resolved hardware profile's VRAM budget before assess. MCP does not replace live benchmarks.

If the user explicitly requests discovery against mock inventory, run `./scripts/py scripts/lma_paths.py --allow-mock --format json`, confirm `hardware_profile.mock` is true, and label shortlist fit as simulated. Do not turn mock fit into an install or measured-performance claim.

**Scout notes:** `integrations/mcp/scout/` — log REST totals, MCP repo picks, VRAM fit. Example: `scout/mlx-community-collections.md`.

### 4. What this stack does **not** do

- Write to `model-assessor.db` — `add-model-from-yaml.py`
- Replace hardware VRAM gating
- Measure `tps`, `moe`, `structured`, `fim` — live runtime tests required

## Checklist

- [ ] REST `health` or MCP `hf_whoami` OK (or fallback chosen)
- [ ] Lists/counts via **REST**, not `hf_hub_query`
- [ ] MCP used only for selective drill-down (`hub_repo_*`, `hf_doc_*`)
- [ ] Result is local weights, not cloud/API-only
- [ ] Candidate fits hardware budget
- [ ] Handed off to correct import skill
- [ ] Scout written when multi-candidate (optional)

## Example agent flow (mlx-community collections)

1. `./scripts/py scripts/hf-hub-api.py collections --owner mlx-community --recent 10 --json`
2. Pick 1–2 collections matching task (code, vision, etc.)
3. MCP `hub_repo_details` on specific `mlx-community/Model-4bit` repos
4. If the repo is already an Ollama `-mlx` library tag, stop and hand off to `lma-assess-import-model`. Otherwise: VRAM check → assess → `new-models.yaml` (`runtime: mlx`)
