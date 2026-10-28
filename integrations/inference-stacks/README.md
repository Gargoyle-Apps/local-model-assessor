# Inference stacks per hardware profile (spike: `optimize-lma`)

**Status:** tooling ready, **no measured results yet**. Every recommendation here is the spike's starting hypothesis. A rule changes from `hypothesis` to `measured` in [profiles.yaml](profiles.yaml) only after [scripts/bench-inference.py](../../scripts/bench-inference.py) results from real hardware support it.

**Question:** for each common hardware profile, which stack performs best and most reliably, and how should that change with workload and user preference? The stack covers the router, engine, model format/quantization and key settings. Ollama is the baseline.

**Working hypothesis:** on every profile, one OpenAI-compatible front door (llama-swap) starts and stops the right engine per request:

- **Mac:** an MLX engine for the main LLMs; llama.cpp for embeddings, reranking and fallback.
- **GB10:** vLLM or SGLang for concurrent use; llama.cpp for single-user and utility models. This is the least certain profile.
- **Discrete NVIDIA:** vLLM/SGLang for concurrent use; llama.cpp for single-user use, or when the model exceeds VRAM.

## Layout

| Path | What it is |
|---|---|
| [profiles.yaml](profiles.yaml) | Profile definitions, workloads, proposed reference models, draft routing rules, Ollama baseline settings |
| [configs/mac/](configs/mac/) | llama-swap config and launchd agent (native only) |
| [configs/gb10/](configs/gb10/) | llama-swap config: native llama.cpp plus vLLM/SGLang containers |
| [configs/nvidia-discrete/](configs/nvidia-discrete/) | llama-swap config for 24–32 GB cards, including MoE expert offload |
| [configs/linux/](configs/linux/) | systemd unit (x86_64 and aarch64), multi-arch Compose file and container config |
| [eval/smoke.jsonl](eval/smoke.jsonl) | Synthetic quality spot-check set |
| `results/` | Benchmark output. **Local only (gitignored):** results are machine-specific |
| [scripts/detect-hardware-profile.py](../../scripts/detect-hardware-profile.py) | Maps this machine's signals to a profile ID |
| [scripts/bench-inference.py](../../scripts/bench-inference.py) | Re-runnable benchmark for any OpenAI-compatible endpoint |

All configs are **synthetic examples**: paths, image tags and memory fractions are placeholders to benchmark, never defaults for a machine.

## Running a benchmark

1. **Detect the profile** on the machine under test:

   ```bash
   ./scripts/py scripts/detect-hardware-profile.py          # add --nodes 2 for two linked GB10s
   ```

2. **Start a fresh server** for one engine × model × quantization, either directly or behind llama-swap.

3. **Run each workload.** Every run records the engine version, driver, OS, model file and quantization:

   ```bash
   ./scripts/py scripts/bench-inference.py --base-url http://127.0.0.1:8080 \
     --workload W1 --model chat-mid-gguf --router llama-swap \
     --engine llama.cpp --engine-version b7966 --quant Q4_K_M \
     --model-file NVIDIA-Nemotron-3.5-Lightning-30B-A3B-Q4_K_M.gguf \
     --pid "$(pgrep -f llama-server | head -1)" --quality-set integrations/inference-stacks/eval/smoke.jsonl
   ```

   | Workload | Extra flags |
   |---|---|
   | W2 | `--prompt-tokens 8000` up to `32000` |
   | W3 | `--concurrency 8 16` (the default) |
   | W4 | `--embed-model embed --rerank-model rerank` (add `--model` to check the chat model stays loaded) |
   | Cold start | `--measure-cold-start`, immediately after starting the server |
   | Model swap | `--swap-from <other-model>` behind llama-swap or Ollama |

   Ollama baseline: `--base-url http://127.0.0.1:11434 --engine ollama --engine-version "$(ollama --version)"`.

4. **Read the results.** Output lands in `results/` as one JSON file per run.

**Metrics:**
- Per concurrency level, p50/p95 of: time to first token, prefill tok/s and decode tok/s.
- Total throughput, error rate, peak RSS (`--pid`), peak GPU allocation (`nvidia-smi` compute apps) and minimum `MemAvailable` (Linux).
- Cold start and swap time, when requested.

**Method rules:**
- Fresh server per run, with warmup.
- Greedy sampling (`temperature 0`) with a fixed seed.
- W1/W3 prompts carry a nonce so prefix caches miss; W2 shares one long prefix so they hit.
- Token counts come from the server's usage report when available; otherwise streamed chunks are counted and flagged `usage_source: chunks`.

## Draft decision matrix (hypothesis, no evidence yet)

| Profile | W1 single chat | W2 coding agent | W3 parallel agents | W4 RAG utilities |
|---|---|---|---|---|
| `mac-16-24` | mlx-lm, MLX 4-bit | mlx-lm, ≤16k context | does not fit; Ollama, 1 slot | llama.cpp |
| `mac-32-64` | oMLX, MLX 4-bit | vllm-metal | vllm-metal | llama.cpp |
| `mac-96plus` | oMLX | vllm-metal | vllm-metal | llama.cpp |
| `gb10` | llama.cpp GGUF | SGLang (FP8 vs MXFP4) | vLLM (FP8 vs MXFP4) | llama.cpp |
| `gb10-x2` | – | – | vLLM, TP 2 across nodes | – |
| `nvidia-discrete` | llama.cpp (+ `--n-cpu-moe` past VRAM) | llama.cpp, 4 slots | vLLM (FP8 / NVFP4 / AWQ by generation) | llama.cpp |

**Front door:** llama-swap on every profile. Utilities sit in a persistent group, so chat swaps never evict them. Key flags and alternatives are in [profiles.yaml](profiles.yaml) under `routing.rules`.

## Detection signals

| Platform | Signals | Maps to |
|---|---|---|
| macOS | `sysctl machdep.cpu.brand_string` (chip and generation), `hw.memsize`, `system_profiler SPDisplaysDataType` (GPU cores) | `mac-16-24` (≤24 GB), `mac-32-64` (32–64 GB), `mac-96plus` (≥96 GB); M5+ flagged for its prefill path |
| Linux | `uname -m`, `nvidia-smi --query-gpu=name,memory.total,compute_cap,driver_version`, `/proc/meminfo` | `nvidia-discrete` (x86_64 with VRAM reported) |
| GB10 | Name contains GB10, or compute capability 12.1 with `memory.total` = N/A; unified size from `/proc/meminfo` | `gb10`; `gb10-x2` only with `--nodes 2` |
| Anything else | AMD, Intel, CPU-only, Windows, Intel Macs, non-GB10 Arm NVIDIA | `fallback` (Ollama defaults) |

## Known issues (public sources; verify on current versions)

**GB10:**
- `nvidia-smi` reports GPU memory as "Not Supported" or N/A because the GPU has no dedicated framebuffer. Use `/proc/meminfo` and `nvidia-smi --query-compute-apps=used_memory`. `cudaMemGetInfo` also undercounts allocatable memory, because the CPU can free more by swapping. Sources: [DGX Spark known issues](https://docs.nvidia.com/dgx/dgx-spark/known-issues.html), [llama-swap #782](https://github.com/mostlygeek/llama-swap/issues/782).
- Engine × quantization support is unsettled. Community reports range from NVFP4 slower than FP8 (and crashing on SGLang) to vLLM trailing SGLang and llama.cpp on MXFP4 ([forum thread](https://forums.developer.nvidia.com/t/vllm-on-gb10-gpt-oss-120b-mxfp4-slower-than-sglang-llama-cpp-what-s-missing/356651)). Also reported: vLLM silently falling back to slow kernels for NVFP4 MoE unless the MoE backend is forced. Check the backend line in every log.
- TensorRT-LLM is supported from 1.2, but community reports describe SM121 gaps (fused MoE, CUTLASS autotuner). Stretch only.
- llama.cpp needs a native build with `CMAKE_CUDA_ARCHITECTURES=121a-real` ([NVIDIA playbook](https://build.nvidia.com/spark/llama-cpp/overview)).

**All Linux:**
- llama-server can close keep-alive connections after a streamed response, giving 502 "proxy error: EOF" behind llama-swap. The configs set `disableKeepAlives: true` (llama-swap #1205).
- vLLM sends anonymous usage stats by default: set `VLLM_NO_USAGE_STATS=1`.
- `OLLAMA_NO_CLOUD=1` disables cloud models and hosted web search, not model pulls.

**macOS:**
- No containers: Docker gets no Metal acceleration, so Mac stacks are native-only.
- MLX serving engines are young; vendor speed claims (vllm-metal vs oMLX) need independent confirmation. Cross-check with [SiliconBench](https://github.com/WindChimeRan/SiliconBench).
- GPU memory ceiling: `sudo sysctl iogpu.wired_limit_mb=<MB>` (resets on reboot). The value per memory tier is a spike deliverable, not yet measured.

## Phase checklists

**Built on this branch:**
- [x] Benchmark script (W1–W4, cold start, swap, memory, quality)
- [x] Hardware detector
- [x] Profile definitions
- [x] Draft routing rules
- [x] Reference configs
- [x] Tests

**Phase 1: llama.cpp + llama-swap vs Ollama** (needs each test machine):
- [ ] Install natively (launchd on Mac, systemd on Linux) and in the container on Linux
- [ ] Feature parity: streaming, tool calling, structured output, embeddings, reranking, vision, reasoning output, idle unloading (`keep_alive` vs `ttl`)
- [ ] Front door: llama-server router mode (`--models-dir`, `--models-max`) vs llama-swap for llama.cpp-only setups
- [ ] W1–W4 against Ollama on the same machine; on Mac, against both of Ollama's runners
- [ ] Tuning: `--n-cpu-moe`, speculative decoding, `--parallel`, `-fa`, KV cache quantization
- [ ] Context length and concurrency per profile that avoid swapping or out-of-memory errors (fill `memory_limits` in profiles.yaml)

**Phase 2: specialized engines:**
- [ ] Mac: vllm-metal, oMLX, mlx-lm on W1–W4; whether any replaces llama.cpp for utilities; `iogpu.wired_limit_mb` per tier; SGLang MLX smoke test
- [ ] GB10: upstream vs NVIDIA Spark images; engine × quantization grid; memory-fraction behaviour on unified memory; prefix caching (RadixAttention vs vLLM); both engines behind llama-swap; stretch TensorRT-LLM and gb10-x2
- [ ] Discrete: find the concurrency where vLLM/SGLang overtake llama.cpp; shared-card fractions vs swapping

**Decision criteria** (weights TBD):
- Performance at the target concurrency
- Memory headroom at the recommended context length
- Feature parity
- Install and upgrade reliability
- A one-hour W3 soak test

Ties go to the simpler stack.

## Follow-up tickets

1. Fill test-machine details and run Phase 1 on each available profile; commit only the summary, not raw results.
2. Weighting for the decision criteria, and a scoring helper that reads `results/*.json`.
3. Soak-test mode in `bench-inference.py` (duration-based W3 run with error-rate tracking).
4. Pin image tags and digests in the GB10 and discrete configs once a combination passes.
5. Wire `detect-hardware-profile.py` into the LMA hardware-profile setup, so profiles map to routing rules automatically.
6. Add a `runtime` value per engine in the DB (today: `ollama`, `mlx`, `vllm`) and generate IDE configs that point at llama-swap.
7. Re-run schedule: GB10 and MLX results go stale quickly; re-benchmark at least quarterly.

## References

- [llama.cpp](https://github.com/ggml-org/llama.cpp), including [router mode](https://huggingface.co/blog/ggml-org/model-management-in-llamacpp)
- [llama-swap](https://github.com/mostlygeek/llama-swap)
- [vLLM](https://github.com/vllm-project/vllm) and [vllm-metal](https://github.com/vllm-project/vllm-metal)
- [SGLang](https://github.com/sgl-project/sglang)
- [oMLX](https://github.com/jundot/omlx) and [mlx-lm](https://github.com/ml-explore/mlx-lm)
- [NVIDIA DGX Spark playbooks](https://build.nvidia.com/spark)
