# Transformer & Hugging Face Lexicon (Self-Updating Reference)

Load this reference when translating model cards, `config.json` parameters, quantization formats, benchmark tables, or Hugging Face Hub UI options into plain language, or when updating this skill with new technical conventions.

Public model-specific numbers below illustrate the named architecture or source revision; they are not target hardware defaults or deployment verdicts. Recheck current model/runtime evidence before applying them. Updates must contain reusable, source-backed knowledge only: never copy local profiles, database contents, inventories, generated reports, profile-derived budgets, or local feasibility conclusions here. Keep those in the ignored field-guide report, including for hypothetical targets.

## Table of Contents

1. [Authoritative Documentation Sources](#1-authoritative-documentation-sources)
2. [Architecture & Layer Topologies](#2-architecture--layer-topologies)
3. [Attention & Context-Memory Compression](#3-attention--context-memory-compression)
4. [Auxiliary Memory & Speculative Decoding](#4-auxiliary-memory--speculative-decoding)
5. [Quantization, Precision & Checkpoint Formats](#5-quantization-precision--checkpoint-formats)
6. [`config.json` Decoder Ring](#6-configjson-decoder-ring)
7. [Hugging Face "Use this model" Menu Decoder](#7-hugging-face-use-this-model-menu-decoder)
8. [Benchmark & Evaluation Conventions](#8-benchmark--evaluation-conventions)
9. [Source Update Log](#9-source-update-log)

---

## 1. Authoritative Documentation Sources

Prefer these sources in order when verifying or adding terminology:

1. **Hugging Face Docs (Primary):** [https://huggingface.co/docs](https://huggingface.co/docs)
   - DeepSeek-V4 / V4.1 & V3.2 model architecture docs (CSA, Lightning Indexer, Shared K=V MQA, mHC, MoE schedule): [https://huggingface.co/docs/transformers/model_doc/deepseek_v4](https://huggingface.co/docs/transformers/model_doc/deepseek_v4) and [https://huggingface.co/docs/transformers/model_doc/deepseek_v32](https://huggingface.co/docs/transformers/model_doc/deepseek_v32)
   - Quantization concept guide (FP8, MXFP4, NVFP4, AWQ, GPTQ, GGUF): [https://huggingface.co/docs/transformers/quantization/concept_guide](https://huggingface.co/docs/transformers/quantization/concept_guide)
   - Fine-grained FP8 and `UE8M0` power-of-two block scale format: [https://huggingface.co/docs/transformers/quantization/finegrained_fp8#ue8m0-scale-format](https://huggingface.co/docs/transformers/quantization/finegrained_fp8#ue8m0-scale-format)
   - MXFP4 and FP-Quant formats: [https://huggingface.co/docs/transformers/quantization/mxfp4](https://huggingface.co/docs/transformers/quantization/mxfp4) and [https://huggingface.co/docs/transformers/quantization/fp_quant](https://huggingface.co/docs/transformers/quantization/fp_quant)
   - Mixture-of-Experts (MoE) backends, Blackwell `deepgemm_megamoe`, and expert parallelism: [https://huggingface.co/docs/transformers/experts_interface#fused-mega-moe-on-blackwell](https://huggingface.co/docs/transformers/experts_interface#fused-mega-moe-on-blackwell) and [https://huggingface.co/docs/transformers/expert_parallelism](https://huggingface.co/docs/transformers/expert_parallelism)
   - RoPE and YaRN long-context scaling: [https://huggingface.co/docs/transformers/internal/rope_utils](https://huggingface.co/docs/transformers/internal/rope_utils) and [https://huggingface.co/docs/trl/long_context_training](https://huggingface.co/docs/trl/long_context_training)
   - Multimodal Vision Encoders (`DeepSeek-ViT` in `timm`) and `image-text-to-text` task guide: [https://huggingface.co/docs/timm/models#multimodal-model-vision-encoders](https://huggingface.co/docs/timm/models#multimodal-model-vision-encoders) and [https://huggingface.co/docs/transformers/tasks/image_text_to_text](https://huggingface.co/docs/transformers/tasks/image_text_to_text)
   - KV cache strategies, Assisted/Speculative Decoding, and Safetensors sharded index metadata: [https://huggingface.co/docs/transformers/kv_cache](https://huggingface.co/docs/transformers/kv_cache), [https://huggingface.co/docs/transformers/assisted_decoding](https://huggingface.co/docs/transformers/assisted_decoding), and [https://huggingface.co/docs/safetensors/metadata_parsing](https://huggingface.co/docs/safetensors/metadata_parsing)
   - Local GGUF integrations (`llama.cpp`, LM Studio): [https://huggingface.co/docs/transformers/community_integrations/llama_cpp](https://huggingface.co/docs/transformers/community_integrations/llama_cpp) and [https://huggingface.co/docs/hub/lmstudio](https://huggingface.co/docs/hub/lmstudio)
2. **First-party model artifacts:** `config.json`, `README.md`, `inference/README.md`, and bundled technical reports inside the target Hugging Face repository.
3. **Derivative quantization receipts:** Model cards on child repos (`base_model:quantized:<org>/<model>`) that document calibration panels, KL divergence, and tested serving flags.

---

## 2. Architecture & Layer Topologies

| Term / Marker | Plain-Language Meaning | Practical Hardware Impact |
|---|---|---|
| **Dense Decoder-only** | Every parameter in every layer runs for every single token generated. | Simple to serve; both RAM capacity and token speed scale directly with total parameter count. |
| **MoE (Mixture-of-Experts)** (`n_routed_experts`, `n_shared_experts`, `num_experts_per_tok`) | The feed-forward network in each layer is split into many small specialist sub-networks ("experts"). A lightweight router picks only a few experts (for example, 6 out of 384 plus 1 always-on shared expert) for each token. | **Compute speed** feels like a small model (active parameters), but **memory capacity** still feels like a giant model because all experts must sit in RAM/VRAM (or stream from fast NVMe SSD). |
| **CED (Causal Encoder-Decoder)** (e.g., `DeepseekV41ForCausalLM`) | Splits a causal Transformer into two halves: a causal encoder stack (for example, layers 0–19) and a decoder stack (layers 20–39). The decoder projects its global KV cache from the final encoder hidden states instead of building independent KV states at every decoder layer. | Cuts active parameters during prompt reading (prefill) to roughly half of decode active parameters (for example, 8B prefill vs. 16B decode in DeepSeek-V4.1-Flash), making long-prompt agentic workloads much faster and cheaper. |
| **Single-Pass mHC (Multi-Head / Hyper-Connections)** (`hc_mult`, `hc_sinkhorn_iters`) | Replaces the single residual stream between Transformer layers with multiple parallel residual streams mixed via doubly-stochastic (Sinkhorn-normalized) matrices. | Improves representation quality per layer with negligible parameter overhead, but requires runtime kernel support (`Mega-mHC`) in engines like vLLM, SGLang, or custom `llama.cpp`. |
| **AttnRes (Attention Residuals)** (`attn_res_block_size: 12`) | Instead of each layer only adding its output to the immediately preceding layer's state, layers attend across a block of earlier residual states (for example, in blocks of 12 layers across a 93-layer model). | Keeps signal sharp across ultra-deep (90+ layer) networks without vanishing gradients or layer-to-layer drift. |
| **Stable LatentMoE** (`routed_expert_hidden_size: 3584` vs. `hidden_size: 7168`, `latent_moe_use_norm: true`) | Projects token vectors down into a narrower "latent" dimension (`3584` instead of `7168`) before routing them through hundreds of tiny experts (`896` experts, `16` active per token), with normalization for training stability. | Lets a model scale to extreme sparsity (nearly 900 experts per layer) while cutting per-expert memory and communication overhead by ~2.5x. |
| **SiTU-GLU Activation** (`hidden_act: "situ"`, `activation_situ_beta: 4.0`, `activation_situ_linear_beta: 25.0`) | A smoother, parameterized gated linear unit activation function replacing standard `SwiGLU` / `SiLU` inside MoE feed-forward networks. | Prevents activation spikes when training massive 3-trillion-parameter models Directly in low-bit precision (`MXFP4`). |
| **Native Multimodal ViT + MLP Projector** (`vision_config`, `patch_size`, `downsample_ratio`, `MoonViT-V2`) | A built-in Vision Transformer (such as `DeepSeek-ViT` or `MoonViT-V2` with `patchmergerv2` and temporal pooling `sd2_tpool`) slices images and video frames into patches, merges adjacent patches (e.g., 2x2), and maps them into the same token space as text. | Lets the model read screenshots, charts, PDFs, and video natively (`image-text-to-text`) with a relatively tiny vision encoder (`400M–500M` parameters). |

---

## 3. Attention & Context-Memory Compression

Standard attention stores Key (K) and Value (V) tensors for every past token in every layer (the **KV cache**). At 100K–1M tokens, an uncompressed KV cache can easily exceed 100 GB of RAM. Modern architectures compress this aggressively:

| Term / Marker | Plain-Language Meaning | Practical Hardware Impact |
|---|---|---|
| **GQA / MQA** (`num_attention_heads` vs. `num_key_value_heads`) | Multiple query heads share fewer Key/Value heads. | Shrinks KV cache proportionally (for example, 8x smaller when 64 query heads share 8 KV heads). |
| **MLA (Multi-head Latent Attention) & Gated MLA** (`q_lora_rank`, `kv_lora_rank`, `qk_rope_head_dim`, `mla_use_output_gate`) | Compresses Keys and Values into a compact low-rank latent vector (`kv_lora_rank: 512`) before caching, plus a tiny decoupled rotary position slice (`qk_rope_head_dim: 64`). **Gated MLA** adds a learned output gate (`mla_use_output_gate: true`) to filter attention output per head. | Dramatically lowers KV-cache memory per token while maintaining full 96-head expressiveness. |
| **KDA (Kimi Delta Attention / Hybrid Linear Attention)** (`linear_attn_config.kda_layers`, `full_attn_layers`, `short_conv_kernel_size: 4`) | A recurrent/linear attention mechanism based on the **delta rule** (updating a fixed-size fast-weight memory state by erasing stale associations and writing new ones, paired with a size-4 short convolution and full-rank gate). In Kimi K3 (`93` layers), **69 layers use fast linear KDA** (3 out of every 4 layers) and **24 layers use full Gated MLA** (every 4th layer: `4, 8, 12, ...`). | Linear KDA layers do **not** grow a per-token KV cache as the prompt gets longer – they keep a fixed-size state! Only 24 of the 93 layers need a growing KV cache, making 1-million-token contexts much faster and lighter in memory. |
| **CSA2 (Compressed Sparse Attention 2)** (`kv_source_layer_ids`, `index_source_layer_ids`, `index_topk`, `candidate_topk_blocks`) | Assigns each attention layer to one of three modes: **Full** (computes KV and sparse index), **Reindex** (reuses shared KV, recomputes top-K index), or **Reuse** (reuses both shared KV and top-K indices from an earlier layer). A **Hierarchical Sparse Indexer** limits later decoder layers to a candidate block pool from layer 20. | Bounds long-context attention cost even at 1M tokens and avoids storing separate full KV caches in all 40 layers. Paired with FP4 KV caching, DeepSeek-V4.1-Flash drops global KV cache to **890 bytes/token** (~890 MB for 1M tokens). |
| **SWA Bounded Replay** (`sliding_window: 128`) | Sliding Window Attention only attends to the last *N* tokens (for example, 128). Instead of saving SWA states for the entire history to RAM or SSD, Bounded Replay recomputes missing local SWA states on the fly from the most recent window of tokens. | Cuts persistent KV-cache footprint by ~8x compared to persisting SWA states across long contexts. |
| **RoPE & YaRN** (`rope_theta`, `rope_scaling.rope_type: "yarn"`, `factor: 16`) | Rotary Position Embedding encodes token order as rotation angles. **YaRN** (Yet another RoPE extensioN) rescales high- and low-frequency rotations (`beta_fast`, `beta_slow`) so a model trained at 64K (`65536`) can generalize to 1M (`1048576`) tokens (`65536 * 16`). | Enables ultra-long context windows without quadratic positional degradation, provided your runtime and RAM budget can hold the prompt buffers. |

---

## 4. Auxiliary Memory & Speculative Decoding

| Term / Marker | Plain-Language Meaning | Practical Hardware Impact |
|---|---|---|
| **Engram Conditional Memory** (`engram_layer_ids`, `engram_num_embeddings`, `engram_max_ngram_size`) | Massive n-gram embedding lookup tables attached to specific layers (for example, 196B parameters across layers 1 and 14 in DeepSeek-V4.1-Flash). For each token sequence, the model hashes up to 4-gram token patterns and retrieves factual/lexical memory directly without spending FLOPs in dense layers. | Adds ~189–203 GB of static table data to the checkpoint, **but only tiny rows are read per token**. Runtimes like `vLLM` (`table_memory: "disk"`) and `DwarfStar` read Engram directly from fast NVMe SSD or pinned host RAM instead of burning GPU VRAM. |
| **MTP / DSpark Speculative Decoding** (`num_nextn_predict_layers: 3`, `dspark_block_size: 5`, `dspark_target_layer_ids`) | Built-in lightweight draft layers at the end of the network predict multiple future tokens at once (for example, 5–7 tokens ahead), which the main model verifies in a single parallel pass using confidence scheduling. | Multiplies single-user decode speed (often 1.5x–2.5x faster tokens/sec on code and structured output) without changing output quality. |
| **Controllable Reasoning Effort** (`reasoning_effort: 1..100` or `"low"|"high"|"max"`) | A prompt-encoding knob that tells the model how much internal chain-of-thought ("thinking") budget to spend before answering. | Lets you trade latency and token cost for deeper math/code/agentic accuracy on a per-request basis. |
| **Preserved Thinking History** (`reasoning_content` kept across turns) | In multi-turn agent loops, you pass the model's previous internal `reasoning_content` and `tool_calls` back into the conversation history on the next turn instead of stripping them out. | Prevents the agent from losing its train of thought across 50–500 step coding or research sessions. |

---

## 5. Quantization, Precision & Checkpoint Formats

| Format / Tag | Bits per Weight (bpw) | What It Means & Where It Runs |
|---|---|---|
| **`safetensors`** | Container format | Hugging Face's safe, zero-copy weight file format. Large models split weights across numbered shards (`model-00001-of-00048.safetensors`) with a map in `model.safetensors.index.json`. |
| **`BF16` / `FP16`** | 16 bpw (2 bytes/param) | Uncompressed inference precision. Used for norms, routers, embeddings, or vision towers even inside quantized checkpoints. |
| **`FP8` (`E4M3` / `MXFP8`)** | ~8–8.25 bpw (~1 byte/param) | 8-bit floating point with block or microscaling (`ue8m0` scales). Supported natively on NVIDIA Hopper/Blackwell and modern server engines (`vLLM`, `SGLang`). |
| **`MXFP4` / `NVFP4`** | ~4.25–4.5 bpw (~0.53 bytes/param) | 4-bit microscaling floating-point (`E2M1` values with shared block scales). `MXFP4` uses 32-element blocks with `UE8M0` scales; NVIDIA's `NVFP4` uses finer 16-element blocks with `E4M3` scales for higher accuracy on Blackwell Tensor Cores. |
| **`EXL3` (ExLlamaV3 Trellis)** | 2.0–5.0 bpw (tunable mix, e.g. `2.7–3.0 bpw`) | Uses non-uniform trellis quantization (`MUL1` / `TR3` codebook) to give sensitive weights more bits and less-sensitive weights fewer bits. Verify the derivative's runtime requirements and resident footprint against the selected target; compression alone does not establish single-node or distributed fit. |
| **`REAP` (Router-weighted Expert Pruning)** | Expert-count reduction (e.g. `216 of 256` or `K154`) | Measures which MoE experts are selected during calibration prompts and removes less-used experts. Memory savings and quality depend on the derivative and calibration; expert pruning does not guarantee fit on any particular machine. |
| **`PrismaQuant AQUA` / `GridBook` (`NVFP4_CB`, `FP8_CB`)** | ~2.35 bpw mixed codebook | Instead of deleting experts, assigns a custom lookup codebook (`CB`) to each layer based on how much errors hurt final output quality (4-bit codebooks on early layers, 8-bit codebooks on sensitive late layers). Runs in vanilla `vLLM` via the `gridbook` plugin. |
| **`Unsloth Dynamic 2.0` (`UD-IQ2_XXS`, `UD-Q2_K_XL`)** | ~2.2–2.7 bpw dynamic GGUF | Smart `llama.cpp` GGUF compression where the "decision-making" parts (attention, routers, shared experts) stay at 8-bit/16-bit while the hundreds of specialist MoE experts are compressed to ~2 bits using a calibration importance matrix (`imatrix`). |
| **`GGUF` (`Q2_K`, `IQ2_XXS`, `Q3_K_M`, `Q4_K_M`, `Q8_0`)** | ~2.1–8.5 bpw | Single-file (or split-shard) format for `llama.cpp`, `Ollama`, `LM Studio`, and `DwarfStar`. Uses an **importance matrix (`imatrix`)** during quantization so critical weights lose less precision at ultra-low bitrates like `Q2_K`. Note: `Q1_0` (1.125 bpw) frequently collapses on MoE models. |
| **`MLX` (`oQ4e`, `4bit`, `8bit`)** | ~4.25–8.5 bpw | Apple Silicon unified-memory model packs using Metal kernels (`mlx-lm`, `oMLX`, or Ollama `-mlx` tags). Verify the exact pack and runtime's target-platform support rather than inferring it from the Hub menu. |

---

## 6. `config.json` Decoder Ring

| JSON Key | Meaning in Plain English |
|---|---|
| `architectures` / `model_type` | The exact class name (`DeepseekV41ForCausalLM`) and architecture key (`deepseek_v41`) that `transformers`, `vLLM`, `SGLang`, or `llama.cpp` must implement to load the model. If an engine lacks this key, loading fails immediately. |
| `vocab_size` | Number of distinct token IDs the tokenizer knows (`129280`). |
| `hidden_size` | Width of the main representation vector flowing between layers (`5120`). |
| `num_hidden_layers` | Total Transformer layers stacked vertically (`40`). |
| `n_routed_experts` / `num_experts_per_tok` | Total specialist MoE experts per layer (`384`) vs. how many wake up for each token (`6`). |
| `max_position_embeddings` | Maximum context window supported by the positional configuration (`1048576` = 1M tokens). |
| `quantization_config` | Describes how the checkpoint weights on disk are already compressed (for example, `quant_method: "fp8"`, `expert_dtype: "fp4"`, `scale_fmt: "ue8m0"`). |

---

## 7. Hugging Face "Use this model" Menu Decoder

Hugging Face renders the **"Use this model"** dropdown automatically from repository tags (`transformers`, `safetensors`, `endpoints_compatible`). **Appearance in the dropdown does not guarantee the base checkpoint fits on a single workstation or works in stock consumer apps.**

| Menu Item | What It Actually Does | When to Pick It (and Local Hardware Gotchas) |
|---|---|---|
| **Libraries -> Transformers** | Shows a Python snippet using Hugging Face `transformers` (`AutoModelForCausalLM.from_pretrained`). | Verify architecture, custom-kernel and quantization support in the selected version, then evaluate memory and workload requirements. |
| **Inference -> Inference Providers / HuggingChat** | Sends requests to an external hosted service. | This is not execution on the assessment target. Explain the distinction; LMA does not assess, import, or recommend cloud-only proxies as local models. |
| **Notebooks -> Google Colab / Kaggle** | Opens a cloud notebook template. | The notebook has its own hardware/runtime allocation; assess that separately from the user's local target rather than assuming a fixed memory tier. |
| **Local Apps -> vLLM** | Generates a `vllm serve <org>/<model>` command. | Verify the selected build's OS, accelerator, architecture and quantization support, then check per-node memory and any distributed placement requirements. |
| **Local Apps -> SGLang** | Generates a `python -m sglang.launch_server` command. | High-throughput alternative to `vLLM` on Linux + NVIDIA GPUs. Check whether the model requires a specific SGLang docker tag or revision. |
| **Local Apps -> Docker Model Runner** | Runs packaged container models. | Check model format, runtime support, accelerator access, and container memory limits on the assessment target. |
| **Footer -> Browse Quantizations** (`llama.cpp`, `Ollama`, `LM Studio`, EXL3, NVFP4) | Opens the Hub tree of community and vendor quantized derivatives (`base_model:quantized:...`). | Compare derivative size, quality evidence, and runtime support when considering lower memory use. A smaller download does not by itself establish resident-memory fit or runtime compatibility. |

---

## 8. Benchmark & Evaluation Conventions

| Benchmark / Metric | What It Measures |
|---|---|
| **MMLU-Pro / SuperGPQA / AGIEval** | Broad academic, graduate-level, and professional knowledge across STEM and humanities. |
| **GPQA Diamond** | PhD-level science questions (physics, chemistry, biology) designed to be hard even with web search. |
| **HLE (Humanity's Last Exam)** | Frontier multi-disciplinary reasoning benchmark (`w/ tools` measures agentic tool-assisted problem solving; `†` often denotes the text-only subset). |
| **DeepSWE v1.1 / SWE-bench** | Real-world GitHub software engineering issues where an agent must edit a repository and pass unit tests (`Resolved %`). |
| **Terminal-Bench (2.1 / 3.0 / 4.0)** | End-to-end command-line agent tasks inside Linux containers (compiling code, debugging servers, data pipelines). |
| **CyberGym / SEC-Bench Pro / ExploitGym** | Cybersecurity vulnerability analysis, patching, and defensive/offensive security engineering tasks. |
| **MMMU-Pro / DocVQA / Chartography** | Multimodal visual reasoning over complex diagrams, documents, and charts. |
| **KLD (Kullback-Leibler Divergence) & ΔNLL** | Quantization fidelity metrics comparing a compressed model's token probability distribution against the unquantized teacher on identical prompts. **Lower KLD (`< 0.05–0.10 nats`) and higher Top-1 agreement (`> 90–95%`)** indicate minimal quality loss from quantization. |

---

## 9. Source Update Log

When updating this lexicon from a new technical source, append a row below with a direct source and reusable concepts only. Review the diff for local context before saving; a source log must not preserve local assessment conclusions.

| Date | Source URL / Artifact | Concepts Added or Updated |
|---|---|---|
| 2026-10-23 | `https://huggingface.co/docs` + `deepseek-ai/DeepSeek-V4.1-Flash` & quantized derivatives (`nvidia`, `0xSero`, `sudoingx`, `antirez`, `kyuz0`, `vcruz305`, `Jundot`) | Initial lexicon: CED, CSA2, SWA Bounded Replay, Single-Pass mHC, Engram conditional memory, DSpark MTP, MXFP4/NVFP4/EXL3/GGUF/oQ4e formats, KLD/ΔNLL metrics, and generic HF menu meanings. |
| 2026-10-23 | `deepseek-ai/DeepSeek-V4-Flash-0731` and public quantized derivatives, including `unsloth/DeepSeek-V4-Flash-0731-GGUF` | Added compression conventions: REAP expert pruning, Fixed-Expert Arena (`K154` / `CB3-v2`), PrismaQuant AQUA / GridBook mixed codebooks (`NVFP4_CB` / `FP8_CB`), and Unsloth Dynamic 2.0 (`UD-IQ2_XXS` / `UD-Q2_K_XL`). |
| 2026-10-24 | `https://huggingface.co/moonshotai/Kimi-K3` (`README.md`, `config.json`) + `https://www.kimi.ai/blog/kimi-k3-1-pro` + `https://huggingface.co/docs/transformers/quantization/compressed_tensors` | Added Kimi K3 / K3.1 Pro architecture conventions: KDA (Kimi Delta Attention 3:1 hybrid linear schedule), Gated MLA, AttnRes (Attention Residuals), Stable LatentMoE (`896` experts, `3584` latent dim), `SiTU-GLU` activation, `MoonViT-V2`, `compressed-tensors` QAT `MXFP4` weights / `MXFP8` activations, and Preserved Thinking History. |
