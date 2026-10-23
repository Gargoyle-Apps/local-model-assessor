# Model Field Guide Report Template

Write the untracked report to `integrations/mcp/scout/<model-slug>-field-guide.md`. Omit sections only if the model lacks that component (for example, omit vision if text-only). Never use em-dashes in prose; use en-dashes (`–`), colons, commas, or periods.

```markdown
# Field Guide: <Model Name> (`<owner>/<repo>`)

- **Source URL:** https://huggingface.co/<owner>/<repo>
- **Generated on:** YYYY-MM-DD
- **Target Hardware Context:** <Hardware name and mode, e.g., Simulated ASUS Ascent GX10 (128 GB unified memory)>
- **Authoritative Docs Referenced:** https://huggingface.co/docs

## 1. Executive Summary (Plain English)

- **What this model is:** 2–3 sentences explaining the model's purpose, modalities, and headline innovation without jargon.
- **The headline numbers vs. reality:** Total parameters vs. active parameters per token vs. actual disk/RAM size.
- **Can you run it locally?** Direct verdict for the active hardware profile (single node vs. multi-node vs. SSD streaming vs. cloud API).

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
