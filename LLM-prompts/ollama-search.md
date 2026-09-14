# Ollama Popular Models Search & Assessment Pipeline

A guidance document for tool-calling AI agents to discover new Ollama models worth assessing, pre-filter by hardware/software criteria, and add only models that improve the local fleet.

> **Cloud models are excluded.** Models listed on Ollama as cloud-only (e.g. `model:cloud`, or entries whose only category is `cloud`) are **never** candidates for assessment or import. They are remote API proxies, not local weights. Do not add them to the DB, do not recommend them to the user. If the user asks about a cloud-only model, inform them it is not available for local use and suggest checking [Hugging Face](https://huggingface.co) or similar sources for a locally-runnable equivalent (GGUF, MLX, safetensors).

---

## Overview

1. **Fetch** the Ollama popular models page
2. **Parse** entries into structured data (template below)
3. **Gate** every entry – cloud-only, architecture/runtime, memory fit, licence, role need (§ 3a). Failing any gate is disqualifying.
4. **Rank** the survivors – provenance tier, then generation recency, then popularity, with packaging recency as tiebreak only (§ 3b)
5. **On Apple Silicon**, resolve each surviving library candidate to its same-size `-mlx` tag when one exists (discrete from mlx-lm; see `lma-assess-import-model`). Non-Apple hosts skip MLX entirely – it fails the architecture gate.
6. **Cap** at 7 candidate models for full assessment
7. **Assess** accepted candidates using `LLM-prompts/model-assessment-prompt.yaml` and insert into DB, assigning roles by fit at this point
8. **Update** last scan timestamp in the database

---

## 1. Data Source

**URL:** `https://ollama.com/search?o=popular`

Default sort is popular. The `o=popular` parameter may not be officially documented but reflects intent. Avoid `o=newest` — too many niche models.

**Fetch:** Use `curl`, `fetch`, or equivalent. The page is client-rendered; expect a mix of HTML and possibly limited structure. Parse what you can from the rendered content.

---

## 2. Entry Structure (Expected)

Use this JSON shape as a template for what to extract from each Ollama listing. Adjust parsing if the page structure differs.

```json
{
  "name": "olmo-3",
  "url": "https://ollama.com/library/olmo-3",
  "description": "Olmo is a series of Open language models designed to enable the science of language models.",
  "categories": ["vision", "tools", "thinking", "cloud"],
  "size_variants": ["7b", "32b"],
  "pulls": "169.7K",
  "tag_count": 15,
  "updated": "2 months ago"
}
```

| Field | Example | Notes |
|-------|---------|-------|
| `name` | `olmo-3` | Model name (from URL or heading) |
| `url` | `https://ollama.com/library/olmo-3` | Link to model page |
| `description` | Text | First sentence(s) before size/pulls |
| `categories` | `["vision","tools","cloud"]` | Capability tags; **exclude if only `cloud`** |
| `size_variants` | `["7b","32b"]` | Parameter sizes |
| `pulls` | `169.7K` | Download count |
| `tag_count` | 15 | Number of tags |
| `updated` | `2 months ago` | Relative timestamp from page |

**Cloud-only — hard exclusion:** If `categories` is `["cloud"]` or the only category is `cloud` (no vision/tools/embedding/etc.), **skip entirely**. These are remote API proxies, not downloadable weights. Do **not** add them to the DB or present them as candidates. If a model appears only as a cloud variant on Ollama (e.g. `model:cloud`), inform the user and suggest checking [Hugging Face](https://huggingface.co) for a locally-runnable version (GGUF or MLX format).

---

## 3. Gates, then Ranking

Candidate selection is **two stages**. Gates are pass/fail and admit no trade-off. Ranking only orders the models that survive every gate. Do not blend the two – a model does not earn points for clearing a gate.

### 3a. Gates (pass/fail)

| Gate | Fails when |
|------|-----------|
| **Cloud-only** | The model exists only as a remote API proxy (see hard exclusion above) |
| **Architecture / runtime** | The weights cannot run on this host's accelerator and OS architecture per the software profile. Apple Silicon resolves to the same-size `-mlx` tag when one exists; **non-Apple hosts never take MLX** (neither Ollama `-mlx` tags nor `mlx-community` safetensors), because MLX is Apple-only |
| **Memory fit** | Weights + KV at the intended `num_ctx` exceed `total_available - os_headroom_gb` |
| **Licence and terms** | The licence forbids the intended use, or carries conditions the user has not accepted (e.g. revenue thresholds, vendor open-model agreements, non-commercial or research-only clauses). Record the licence in `model_docs.caveats` |
| **Role need** | The model neither fills an unmet role nor serves an assigned role better than the incumbent – this is the "beat" test in § 5 |

A model that fails any gate is skipped, however new or popular it is.

### 3b. Ranking (orders the survivors)

Apply in order; each criterion only breaks ties left by the one above it.

1. **Provenance tier** – official first-party release, then a fork by a recognised open-source org (assess but **flag** it, e.g. `mlx-community`), then an individual's fork (**never** without explicit user permission).
2. **Model generation recency** – when the model family or architecture itself was released or superseded upstream.
3. **Popularity** – pulls on Ollama, downloads on Hugging Face, position on the popular list.
4. **Packaging recency** – the Ollama `updated` stamp, a re-quant, or a repackage. **Tiebreak only.**

> **Do not let packaging recency outrank generation recency.** Ollama's "Updated 2 days ago" describes when someone rebuilt the GGUF, not when the model got better. A freshly repackaged older generation loses to a newer generation packaged months ago. Ranking a superseded family first because its tag looked fresher is the specific failure this ordering exists to prevent.

**Role fit is not a ranking criterion.** It decides *which* role a survivor is assigned to, and it is applied after gates and ranking, when writing `by_role`.

### 3c. Primary vs alternative within a role

Ranking decides which models **qualify** for a role. Which one takes `primary` is decided by **role fit**, and for interactive roles (`coding`, `autocomplete`, `formatting`, `generalist`, `reasoning`) that means preferring estimated throughput, because a slower model taxes every single response. `reasoning` is the most sensitive of these, since long chains of thought multiply the cost of a low `tps`.

This can invert rank order, and that is intended: a newer generation that decodes at half the speed of a slightly older sibling is the wrong default for an interactive role.

**Keep the rank-order pick in the `alternative` slot rather than dropping it.** It stays provisioned and available, so the choice can be revisited once real workflow tests exist rather than being re-litigated from the catalogue. Record the reason for the split in a comment next to `by_role` so the trade-off is legible later.

**Query last scan:**
```bash
./scripts/query-db.sh "SELECT value FROM meta WHERE key='last_ollama_scan'"
```

If empty, treat all models as candidates. When `updated` is relative (e.g. "5 days ago", "2 months ago"), use heuristics: "X hours ago" or "X days ago" with X small = recently repackaged; "X months ago" = older. Remember this is packaging recency (rank 4), not generation recency (rank 2) – establish generation from the upstream model card or release notes, not from the Ollama stamp.

---

## 4. Evaluating the Gates Against the Profiles

Resolve the live profiles first – never read the templates when a linked or local profile exists:

```bash
./scripts/py scripts/lma_paths.py --format json
```

Then check the memory-fit and architecture gates against them.

- **Hardware profile** (`hardware_profile` in the resolver output)
  - `vram_budget.total_available` and `os_headroom_gb` – effective budget for the memory-fit gate
  - `concurrency_reserve` – needed for the co-run judgement, not the gate itself
  - `hardware_classes` – which class the model falls into
  - `context_strategy` – caps on `num_ctx`
  - For MoE models, gate on **resident** memory (all experts are loaded even though only some activate per token), not on active-parameter count

- **Software profile** (`software_profile` in the resolver output)
  - `model_runtime` – the runtimes actually installed. A model whose only distribution format needs a runtime this host does not have **fails the architecture gate**, regardless of merit.
  - Accelerator and OS architecture – decides the MLX question. Apple Silicon prefers same-size `-mlx` tags; anything else excludes MLX entirely.

If the profile is mock, every conclusion drawn here is **simulated**. Confirm `hardware_profile.mock` and `simulate_installs` in the resolver output before describing fit or throughput.

### Estimating `tps`: bandwidth, not FLOPS

Single-stream decode on local hardware is almost always **memory-bandwidth-bound**, not compute-bound: each token requires reading the active weights from memory. So estimate `tps` from bytes read per token against the host's memory bandwidth, and treat vendor peak-FLOPS or low-precision throughput figures as close to irrelevant for interactive single-user decode.

Two consequences that catch people out:

- **Do not derive `tps` from VRAM size alone.** Resident footprint and decode speed are different quantities. For MoE, footprint tracks **resident** parameters (gate on this) while decode tracks **active** parameters (estimate `tps` from this). A 30B-A3B MoE can decode several times faster than a dense 31B while occupying similar memory, so ordering `tps` inversely by VRAM inverts MoE models.
- **Low-precision compute formats need not raise `tps`.** A narrower weight format helps mainly by reducing bytes read; its arithmetic advantage is wasted at batch 1 on a bandwidth-bound host. Where a faster runtime does win is prefill and time-to-first-token, plus concurrent throughput, neither of which is `tps`.

`tps` is an estimate unless measured. On a mock profile it is a **simulated placeholder** – never present it as a measurement, and prefer a published benchmark on the same silicon over a guess when one exists.

---

## 5. "Beat" Criterion – the Role-Need Gate

This is the mechanism behind the **role need** gate in § 3a, not a separate later step. A candidate **beats** existing models if it improves at least one of:

| Dimension | Beat means |
|-----------|------------|
| **Size** | Larger capable variant (e.g. 32b vs 24b) or fills a missing size tier |
| **Performance** | Higher expected t/s for the same VRAM class. On Apple Silicon, a same-size Ollama `-mlx` tag beats its GGUF sibling even if that sibling is already in the DB (see `lma-assess-import-model` `references/ollama-mlx-tags.md`). |
| **Need** | Fills an unmet role/constraint (e.g. no vision model, no tools model, no embedding) |

When a library model has both a GGUF default and a same-size `-mlx` tag, assess **only** the `-mlx` tag on Apple Silicon. Do not treat the GGUF tag as a second candidate.

**Query current fleet:**
```bash
./scripts/query-db.sh "SELECT model_id, vram, class, tps, vision, tools, reasoning FROM models"
./scripts/query-db.sh "SELECT role, variant, model_id FROM role_model"
./scripts/query-db.sh "SELECT constraint_name, model_id FROM constraint_model"
```

A candidate that doesn't beat any existing model on size, performance, or need should be **skipped**.

---

## 6. Cap and Select

- **Maximum 7** candidate models for full assessment per run.
- If fewer than 7 qualify after prioritization, pre-filter, and beat logic, assess only those.
- If **no models** meet criteria, return a clear explanation (e.g. "All popular models are either Cloud-only, already in DB, or don't beat existing models on size/performance/need").

---

## 7. Full Assessment (Accepted Candidates)

For each accepted candidate, follow **`LLM-prompts/model-assessment-prompt.yaml`**:

1. Read `computer-profile/hardware-profile.yaml` (or template)
2. For each model URL/name, produce YAML output per the prompt. Use `model-data/new-models.template.yaml` as the schema reference; write to `model-data/new-models.yaml` (gitignored).
3. Run (after `./scripts/bootstrap-python.sh` if `.venv` is missing — see `lma-python-env` skill):
   ```bash
   ./scripts/py scripts/add-model-from-yaml.py model-data/new-models.yaml
   ./scripts/py scripts/export-assessed-models.py
   ```
4. After clones are built in Ollama, sweep IDE config (`lma-ide-config` skill). On opted-in mock hardware (`simulate_installs: true`), skip `ollama pull` / `ollama create` and still run the sweep: the DB records simulated `is_active=1` and does not deploy Continue to `$HOME`.

New models get `assessed_at` set automatically when inserted.

---

## 8. Update Last Scan Timestamp

After completing a scan (whether or not any models were added), update the DB:

```bash
./scripts/query-db.sh "INSERT OR REPLACE INTO meta (key, value) VALUES ('last_ollama_scan', datetime('now'))"
```

---

## Summary Checklist

- [ ] Fetch `https://ollama.com/search?o=popular`
- [ ] Parse entries into JSON template (name, url, description, categories, size_variants, pulls, updated)
- [ ] Exclude Cloud-only models (`categories` = only `cloud`) — never add to DB; inform user to check HuggingFace for local alternatives
- [ ] Resolve live profiles with `lma_paths.py --format json`; note `mock` / `simulate_installs`
- [ ] Apply the gates: architecture/runtime, memory fit (resident, not active, for MoE), licence and terms, role need
- [ ] Rank survivors: provenance tier → generation recency → popularity → packaging recency (tiebreak only)
- [ ] Confirm generation recency from the upstream model card, **not** the Ollama `updated` stamp
- [ ] On Apple Silicon, resolve each candidate to its same-size `-mlx` tag when the library ships one; on any other host, exclude MLX
- [ ] Compare to current fleet — only keep candidates that "beat" on size, performance, or need
- [ ] Cap at 7 candidates
- [ ] Assign roles by fit only after gates and ranking
- [ ] If none qualify: return explanation and stop
- [ ] Otherwise: assess each via `LLM-prompts/model-assessment-prompt.yaml`, run `add-model-from-yaml.py`, `export-assessed-models.py`, then `sweep-ide-config.py`. On mock hardware with `simulate_installs`, skip Ollama downloads and still sweep.
- [ ] Update `meta.last_ollama_scan` with `datetime('now')`

---

## Database: Last Modified Fields

| Location | Field | Purpose |
|----------|-------|---------|
| `meta` | `key='last_ollama_scan'`, `value=datetime` | When we last scanned the Ollama popular page |
| `models` | `assessed_at` | When this model was assessed/added locally |

Run `./scripts/migrate-schema.sh` if your DB was created before these fields existed.
