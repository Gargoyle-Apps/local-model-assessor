# Transformer & Hugging Face Lexicon (Self-Updating Reference)

Load this reference when translating model cards, `config.json` parameters, quantization formats, benchmark tables, or Hugging Face Hub UI options into plain language, or when updating this skill with new technical conventions.

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
| **Native Multimodal ViT + MLP Projector** (`vision_config`, `patch_size`, `downsample_ratio`) | A built-in Vision Transformer slices images into patches (for example, 14x14 pixels), downsamples them (for example, 3x3 pixel-unshuffle), and maps them into the same token space as text. | Lets the model read screenshots, charts, and documents natively (`image-text-to-text`), though some text-only quantized engines or flags (`--language-model-only`) skip or separate the vision encoder. |

---

## 3. Attention & Context-Memory Compression

Standard attention stores Key (K) and Value (V) tensors for every past token in every layer (the **KV cache**). At 100K–1M tokens, an uncompressed KV cache can easily exceed 100 GB of RAM. Modern architectures compress this aggressively:

| Term / Marker | Plain-Language Meaning | Practical Hardware Impact |
|---|---|---|
| **GQA / MQA** (`num_attention_heads` vs. `num_key_value_heads`) | Multiple query heads share fewer Key/Value heads. | Shrinks KV cache proportionally (for example, 8x smaller when 64 query heads share 8 KV heads). |
| **MLA (Multi-head Latent Attention)** (`q_lora_rank`, `kv_lora_rank`, `qk_rope_head_dim`) | Compresses Keys and Values into a compact low-rank latent vector before caching, plus a tiny decoupled rotary position slice. | Dramatically lowers KV-cache memory per token while maintaining multi-head expressiveness. |
| **CSA2 (Compressed Sparse Attention 2)** (`kv_source_layer_ids`, `index_source_layer_ids`, `index_topk`, `candidate_topk_blocks`) | Assigns each attention layer to one of three modes: **Full** (computes KV and sparse index), **Reindex** (reuses shared KV, recomputes top-K index), or **Reuse** (reuses both shared KV and top-K indices from an earlier layer). A **Hierarchical Sparse Indexer** limits later decoder layers to a candidate block pool from layer 20. | Bounds long-context attention cost even at 1M tokens and avoids storing separate full KV caches in all 40 layers. Paired with FP4 KV caching, DeepSeek-V4.1-Flash drops global KV cache to **890 bytes/token** (~890 MB for 1M tokens). |
| **SWA Bounded Replay** (`sliding_window: 128`) | Sliding Window Attention only attends to the last *N* tokens (for example, 128). Instead of saving SWA states for the entire history to RAM or SSD, Bounded Replay recomputes missing local SWA states on the fly from the most recent window of tokens. | Cuts persistent KV-cache footprint by ~8x compared to persisting SWA states across long contexts. |
| **RoPE & YaRN** (`rope_theta`, `rope_scaling.rope_type: "yarn"`, `factor: 16`) | Rotary Position Embedding encodes token order as rotation angles. **YaRN** (Yet another RoPE extensioN) rescales high- and low-frequency rotations (`beta_fast`, `beta_slow`) so a model trained at 64K (`65536`) can generalize to 1M (`1048576`) tokens (`65536 * 16`). | Enables ultra-long context windows without quadratic positional degradation, provided your runtime and RAM budget can hold the prompt buffers. |

---

## 4. Auxiliary Memory & Speculative Decoding

| Term / Marker | Plain-Language Meaning | Practical Hardware Impact |
|---|---|---|
| **Engram Conditional Memory** (`engram_layer_ids`, `engram_num_embeddings`, `engram_max_ngram_size`) | Massive n-gram embedding lookup tables attached to specific layers (for example, 196B parameters across layers 1 and 14 in DeepSeek-V4.1-Flash). For each token sequence, the model hashes up to 4-gram token patterns and retrieves factual/lexical memory directly without spending FLOPs in dense layers. | Adds ~189–203 GB of static table data to the checkpoint, **but only tiny rows are read per token**. Runtimes like `vLLM` (`table_memory: "disk"`) and `DwarfStar` read Engram directly from fast NVMe SSD or pinned host RAM instead of burning GPU VRAM. |
| **MTP / DSpark Speculative Decoding** (`num_nextn_predict_layers: 3`, `dspark_block_size: 5`, `dspark_target_layer_ids`) | Built-in lightweight draft layers at the end of the network predict multiple future tokens at once (for example, 5–7 tokens ahead), which the main model verifies in a single parallel pass using confidence scheduling. | Multiplies single-user decode speed (often 1.5x–2.5x faster tokens/sec on code and structured output) without changing output quality. |
| **Controllable Reasoning Effort** (`reasoning_effort: 1..100`) | A prompt-encoding knob that tells the model how much internal chain-of-thought ("thinking") budget to spend before answering. | Lets you trade latency and token cost for deeper math/code/agentic accuracy on a per-request basis. |

---

## 5. Quantization, Precision & Checkpoint Formats

| Format / Tag | Bits per Weight (bpw) | What It Means & Where It Runs |
|---|---|---|
| **`safetensors`** | Container format | Hugging Face's safe, zero-copy weight file format. Large models split weights across numbered shards (`model-00001-of-00048.safetensors`) with a map in `model.safetensors.index.json`. |
| **`BF16` / `FP16`** | 16 bpw (2 bytes/param) | Uncompressed inference precision. Used for norms, routers, embeddings, or vision towers even inside quantized checkpoints. |
| **`FP8` (`E4M3` / `MXFP8`)** | ~8–8.25 bpw (~1 byte/param) | 8-bit floating point with block or microscaling (`ue8m0` scales). Supported natively on NVIDIA Hopper/Blackwell and modern server engines (`vLLM`, `SGLang`). |
| **`MXFP4` / `NVFP4`** | ~4.25–4.5 bpw (~0.53 bytes/param) | 4-bit microscaling floating-point (`E2M1` values with shared block scales). `MXFP4` uses 32-element blocks with `UE8M0` scales; NVIDIA's `NVFP4` uses finer 16-element blocks with `E4M3` scales for higher accuracy on Blackwell Tensor Cores. |
| **`EXL3` (ExLlamaV3 Trellis)** | 2.0–5.0 bpw (tunable mix, e.g. `2.7–3.0 bpw`) | Uses non-uniform trellis quantization (`MUL1` / `TR3` codebook) to give sensitive weights more bits and less-sensitive weights fewer bits. Popular for fitting large MoE models onto 1x or 2x NVIDIA DGX Spark / ASUS GX10 nodes via `SparkInfer` or custom `vLLM` plugins. |
| **`REAP` (Router-weighted Expert Pruning)** | Expert-count reduction (e.g. `216 of 256` or `K154`) | Measures which MoE experts actually get picked during real coding and tool-use prompts, locks those in as mandatory, and removes the least-used experts (saving 15%–60% of RAM) so the model fits on a single 128 GB box. |
| **`PrismaQuant AQUA` / `GridBook` (`NVFP4_CB`, `FP8_CB`)** | ~2.35 bpw mixed codebook | Instead of deleting experts, assigns a custom lookup codebook (`CB`) to each layer based on how much errors hurt final output quality (4-bit codebooks on early layers, 8-bit codebooks on sensitive late layers). Runs in vanilla `vLLM` via the `gridbook` plugin. |
| **`Unsloth Dynamic 2.0` (`UD-IQ2_XXS`, `UD-Q2_K_XL`)** | ~2.2–2.7 bpw dynamic GGUF | Smart `llama.cpp` GGUF compression where the "decision-making" parts (attention, routers, shared experts) stay at 8-bit/16-bit while the hundreds of specialist MoE experts are compressed to ~2 bits using a calibration importance matrix (`imatrix`). |
| **`GGUF` (`Q2_K`, `IQ2_XXS`, `Q3_K_M`, `Q4_K_M`, `Q8_0`)** | ~2.1–8.5 bpw | Single-file (or split-shard) format for `llama.cpp`, `Ollama`, `LM Studio`, and `DwarfStar`. Uses an **importance matrix (`imatrix`)** during quantization so critical weights lose less precision at ultra-low bitrates like `Q2_K`. Note: `Q1_0` (1.125 bpw) frequently collapses on MoE models. |
| **`MLX` (`oQ4e`, `4bit`, `8bit`)** | ~4.25–8.5 bpw | Apple Silicon unified-memory format using Metal kernels (`mlx-lm`, `oMLX`, or Ollama `-mlx` tags). Does not run on NVIDIA/Linux systems like the ASUS GX10. |

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
| **Libraries -> Transformers** | Shows a Python snippet using Hugging Face `transformers` (`AutoModelForCausalLM.from_pretrained`). | Best for reference code or small models. For 100B+ frontier MoEs with custom kernels (`mHC`, `CSA2`, `FP4`), plain `transformers` is often unsupported or far too slow/memory-hungry. |
| **Inference -> Inference Providers / HuggingChat** | Sends API requests to hosted cloud clusters (Together, Fireworks, Novita, DeepInfra). | **Pick this when you want to test a massive model immediately** without downloading 200–500 GB or owning multi-node GPUs. (Note: LMA excludes cloud proxies from local DB imports, but you can use them to evaluate model behavior externally.) |
| **Notebooks -> Google Colab / Kaggle** | Opens a cloud notebook template. | Free/pro notebook GPUs (16–80 GB VRAM) cannot load 400+ GB checkpoints. Only useful for API calls or tiny models. |
| **Local Apps -> vLLM** | Generates a `vllm serve <org>/<model>` command. | **Primary choice for Linux + NVIDIA GPUs (including ASUS Ascent GX10 / DGX Spark)**, **provided** you pick a checkpoint/quantization that fits your node memory and a vLLM build that supports the model's custom ops. |
| **Local Apps -> SGLang** | Generates a `python -m sglang.launch_server` command. | High-throughput alternative to `vLLM` on Linux + NVIDIA GPUs. Check whether the model requires a specific SGLang docker tag or revision. |
| **Local Apps -> Docker Model Runner** | Runs packaged desktop container models. | Designed for workstation-sized GGUF/OCI models; will not fit a 400+ GB multi-node checkpoint on a single 128 GB node. |
| **Footer -> Browse Quantizations** (`llama.cpp`, `Ollama`, `LM Studio`, EXL3, NVFP4) | Opens the Hub tree of community and vendor quantized derivatives (`base_model:quantized:...`). | **Mandatory stop for local hardware** whenever the upstream repo exceeds your VRAM/unified RAM budget. Look here for **EXL3 / NVFP4** (for NVIDIA `vLLM`), **GGUF** (for `llama.cpp` / `DwarfStar` / `Ollama`), or **MLX** (for Apple Silicon). Always verify in the quantized repo's README whether upstream `llama.cpp` / `Ollama` supports the architecture yet! |

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

When updating this lexicon from a new technical source, append a row below:

| Date | Source URL / Artifact | Concepts Added or Updated |
|---|---|---|
| 2026-10-23 | `https://huggingface.co/docs` + `deepseek-ai/DeepSeek-V4.1-Flash` & quantized derivatives (`nvidia`, `0xSero`, `sudoingx`, `antirez`, `kyuz0`, `vcruz305`, `Jundot`) | Initial lexicon: CED, CSA2, SWA Bounded Replay, Single-Pass mHC, Engram conditional memory, DSpark MTP, MXFP4/NVFP4/EXL3/GGUF/oQ4e formats, KLD/ΔNLL metrics, and HF "Use this model" menu mapping for ASUS Ascent GX10 (GB10). |
| 2026-10-23 | `deepseek-ai/DeepSeek-V4-Flash-0731` + single-GX10 derivatives (`0xSero/deepseek-v4-flash-0731-spark`, `rdtand/...-PrismaQuant-AQUA-gridbook-87GB-spark-vllm`, `unsloth/DeepSeek-V4-Flash-0731-GGUF`, `sayyidfareed/DeepSeek-V4.1-Flash-Next-DGX-Spark-512K`) | Added single-node 128 GB compression conventions: REAP expert pruning, Fixed-Expert Arena (`K154` / `CB3-v2`), PrismaQuant AQUA / GridBook mixed codebooks (`NVFP4_CB` / `FP8_CB`), and Unsloth Dynamic 2.0 (`UD-IQ2_XXS` / `UD-Q2_K_XL`). |
