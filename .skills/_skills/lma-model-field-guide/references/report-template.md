# Model Field Guide Report Template

Write the untracked report to `integrations/mcp/scout/<model-slug>-field-guide.md`. Omit sections only if the model lacks that component (for example, omit vision if text-only). Never use em-dashes in prose; use en-dashes (`–`), colons, commas, or periods.

```markdown
# Field Guide: <Model Name> (`<owner>/<repo>`)

- **Source URL:** https://huggingface.co/<owner>/<repo>
- **Generated on:** YYYY-MM-DD
- **Assessment target:** <hardware description or unknown>
- **Profile source:** <supplied target / local profile path / selected DB and table / unavailable>
- **Target status and evidence:** <actual / hypothetical / unknown; user statement or observation supporting this>
- **Executing host relationship:** <same as target / different / unknown; no private host identifiers>
- **Capacity inputs:** <units; memory type; node count; per-node physical memory and allocation ceiling; OS headroom; concurrency reserve; unknowns>
- **Derived budget:** <per-node effective and co-run budgets; aggregate physical memory reported separately>
- **Model/runtime evidence:** <resident weights, KV/context/concurrency, buffers, auxiliaries; OS/runtime support and evidence dates>
- **Assumptions and missing inputs:** <conflicts, estimates, uncertainty; no inherited defaults>
- **Authoritative Docs Referenced:** https://huggingface.co/docs

## 1. Executive Summary (Plain English)

- **What this model is:** 2–3 sentences explaining the model's purpose, modalities, and headline innovation without jargon.
- **The headline numbers vs. reality:** Total parameters vs. active parameters per token vs. actual disk/RAM size.
- **Can you run it locally?** Conditional verdict for the assessment target, separating memory fit from runtime support. Explain per-node placement for distributed runs and verify offload support before suggesting it. If inputs are missing, say what remains unknown. Hosted services are external, not local feasibility results.

## 2. Architecture & Transformer Innovations Decoded

| Component / Term | What the Model Card Says | What It Means in Plain Language | Why You Care (Speed / RAM / Quality) |
|---|---|---|---|
| | | | |

## 3. `config.json` Decoder Ring

| `config.json` Field & Value | Plain-English Translation | Runtime Implication |
|---|---|---|
| | | |

## 4. Repository Files, Prompt Encoding & Quantization Landscape

### What is inside the base repository
- Explain the shard layout, chat templates / custom prompt encoders, vision weights, and auxiliary tables.

### Available Quantizations (`Browse Quantizations`)

| Derivative Repo | Format & Precision | Total / Resident Size | Target Hardware & Runtime | Quality / Speed Notes |
|---|---|---|---|---|
| | | | | |

## 5. Navigating the Hugging Face "Use this model" Menu

Map each option in the Hugging Face "Use this model" dropdown to what actually happens on the user's target hardware:

| Menu Option | Verdict for Target Hardware | Why & Exact Next Step |
|---|---|---|
| **Browse Quantizations** | | |
| **Local Apps: vLLM** | | |
| **Local Apps: SGLang** | | |
| **Local Apps: Docker Model Runner** | | |
| **Local Apps: Ollama / llama.cpp / LM Studio** | | |
| **Libraries: Transformers** | | |
| **Inference: Inference Providers / HuggingChat** | | |

## 6. Benchmarks & Evaluation Translated

Explain what the model's benchmark tables show, what evaluation settings were used (such as `reasoning_effort`, context length, and agent scaffolds), and where the model leads or trails frontier peers.

## 7. Authoritative References (`huggingface.co/docs` & Primary Sources)

- List direct links to `https://huggingface.co/docs/...` and repository artifacts used in this report.
```
