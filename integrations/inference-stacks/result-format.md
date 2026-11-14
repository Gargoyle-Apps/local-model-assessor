# Inference benchmark result contract

`scripts/bench-inference.py` writes **schema version 1**, method **`finite-v2`**. This contract covers finite W1–W4 observations. Scoring, continuous soak scheduling and feature probes are separate workstreams; no hardware recommendation follows from implementing this format.

Raw runs, deployment metadata, launch files, linked evidence and machine identifiers stay in local, gitignored paths such as `integrations/inference-stacks/results/`. The examples below are explicitly synthetic format examples, with no feasibility or performance claims.

## Envelope

| Field | Meaning |
|---|---|
| `schema_version` | Integer format version; currently `1` |
| `method_version` | Measurement semantics; currently `finite-v2` |
| `run_id` | UUID, also present in the output filename |
| `run_status` | `running`, `complete`, `failed` or `interrupted` |
| `environment` | Server hardware observation and engine/model identity; client hardware is separate under `client` |
| `parameters` | Effective inputs, including defaults, sampling, socket timeout and requested workload shape |
| `provenance` | Operator-supplied JSON from `--metadata`; values are recorded, not independently attested |
| `evidence_links` | Copy of the provenance links for this deployment/configuration |
| `result` | Per-concurrency chat summaries or per-utility summaries, setup/probe observations and memory telemetry |
| `quality` | Optional `substring-smoke` results and the SHA-256 of the exact JSONL fixture bytes |
| `comparison` | Recomputed structural readiness: `ready` or `incomplete`, with `issues` |
| `finished_at`, `error` | End timestamp and optional execution failure/interruption reason |

An initial `running` checkpoint is written before the first request, then after each concurrency level or utility, and again at completion. Writes use a temporary file in the destination directory and atomic replacement. UUID filenames prevent two runs with the same timestamp from overwriting each other.

Ctrl-C saves observations already collected and marks the record `interrupted` (exit 130). Request failures, including setup, W4 utilities, chat probes and quality transport failures, produce `failed` (exit 1). Exit 0 means requests completed; it does not establish comparison readiness or model quality. A failed substring assertion is recorded as a quality failure without making a successfully delivered request an execution error. CLI validation errors exit 2 before requests start.

Uncatchable termination or an output-storage failure can leave the last `running` checkpoint. Consumers must treat it as incomplete. Finite mode uses socket timeouts, not absolute request deadlines: already-running worker requests can outlive interruption until their I/O finishes. Bounded drain and trickling-response protection belong to the soak workstream. This format does not claim those guarantees.

## Server identity

`--server-location` defaults to `unknown`. A loopback URL alone does not prove a local server: it may be a tunnel. Unknown location permits an exploratory run but leaves its server profile unknown, disables local memory sampling, and blocks comparison readiness.

- `local`: operator confirms a loopback endpoint serves this physical machine. Hardware/OS/driver detection describes the server. `--pid` and `--nodes` apply only here. The flag does not inspect tunnels or prove PID ownership.
- `remote`: use `metadata.server` for the server's observed profile, traits, OS and driver. Client detection is retained only as client information; it cannot fill missing server facts. Local memory sampling is disabled.

Remote server metadata accepts this shape (synthetic, deliberately not a real observation):

```json
{
  "server": {
    "profile": "fallback",
    "traits": {"synthetic_example": true},
    "os": "synthetic-os",
    "driver": "synthetic-driver",
    "observation": "simulated"
  }
}
```

Use `observation: real` only for actual server observations. `simulated`, `unknown`, empty traits or missing OS/profile remain incomplete. `server` metadata is rejected unless the CLI location is `remote`; local observations cannot be overridden by a planning profile.

## Deployment metadata

Pass `--metadata <local-json-file>`. Omitting it remains valid for exploratory runs, which are marked incomplete. Provided fields must have the documented types; malformed metadata fails before requests. Additional fields are retained and participate in repeat identity, so material flags and memory settings can be represented without hiding them in notes.

Synthetic chat metadata example (omit `server` for local execution; add the server object above for a remote synthetic example):

```json
{
  "system_id": "synthetic-system",
  "deployment_id": "synthetic-deployment",
  "config_id": "synthetic-config-digest",
  "model_family": "synthetic-family",
  "model_revision": "synthetic-revision",
  "artifact_id": "synthetic-artifact-digest",
  "tokenizer_id": "synthetic-tokenizer-revision",
  "chat_template_id": "synthetic-template-digest",
  "context_tokens": 4096,
  "engine_slots": 2,
  "compute_backend": "synthetic-observed-backend",
  "compute_precision": "synthetic-observed-precision",
  "expected_backend": "synthetic-recipe-backend",
  "speculation": {"method": "none"},
  "evidence_links": []
}
```

Replace synthetic values with observed deployment facts before use on a real target. The example is not a machine profile, memory budget or recommended configuration.

| Metadata | Contract |
|---|---|
| `system_id` | Stable local identifier for the actual test system; profile tiers alone do not identify a machine |
| `deployment_id`, `config_id` | Identity shared by associated evidence. Change the config ID when launch flags, model mappings, memory settings or templates change; a digest of the effective configuration is suitable |
| `model_family`, `model_revision`, `artifact_id` | Family plus pinned source revision and exact served artifact identity |
| `tokenizer_id`, `chat_template_id` | Pinned tokenizer and effective template identities |
| `context_tokens` | Positive **per-request** context allocation, including input, template and output; not the aggregate context pool |
| `engine_slots` | Positive configured server slot count, distinct from client concurrency |
| `compute_backend`, `compute_precision` | Actual observed compute path, separate from the CLI weight `--quant` |
| `expected_backend` | Optional recipe expectation for later fallback review; it does not override the observation |
| `speculation` | Explicit `method: none`, or a nonempty method and `artifact_id` identifying the draft artifact/configuration |
| `router_version`, `router_limit` | Required when `--router` is not `none`; admission limit is a positive effective limit, not an unresolved sentinel |
| `utilities` | Separate `embedding` and/or `rerank` objects for W4 |

Every selected W4 utility needs `artifact_id`, `model_family`, `model_revision`, `quant`, `engine` and `engine_version` strings in its own object. Include per-utility compute paths/settings as additional fields when they differ. W4 with `--model` also needs the chat artifact/template/context/speculation facts. Before/after chat probes are sequential observations; `residency_verified` remains false. They do not establish concurrent performance or retained residency.

Each `evidence_links` entry needs nonempty strings `kind`, `run_id`, `file`, `deployment_id` and `config_id`. Deployment/config IDs must match this run. Kinds can identify future parity, install/upgrade or soak records. The writer preserves references; it does not open files, check their contents or consider linked gates satisfied. A future consumer must resolve and validate the linked evidence before using it.

## Effective parameters and metrics

Chat parameters record concurrency **in requested order**, request count per level, approximate synthetic input-token target, output limit, warmup, cold/swap controls, seed, sampling, cache treatment and socket timeout. W4 records request count per utility, batch/document sizes, utility order and optional chat-probe output limit. Quality uses the fixture's byte hash, rather than its mutable path, as identity.

`--temperature` defaults to 0 and `--top-p` to 1. Choose explicit model-appropriate settings when needed. `--reasoning-mode enabled|disabled` records an operator observation; it does not enable or disable the server's reasoning behavior. The default `unknown` blocks chat comparison readiness. `--chat-options` accepts extra JSON request fields (for example `chat_template_kwargs`) and records them. Reserved fields such as model, messages, token limits, stream controls, sampling and `n` cannot override benchmark controls through that object. Do not put secrets in request options or notes; they are saved locally.

W1/W3 prepend a run/request nonce to reduce prefix reuse. W2 shares a synthetic prefix within a level. A fresh server per run remains an operator procedure, and the client does not attest cache eviction or cache hits. Synthetic token targets are approximate and exclude some template/task text. Server-reported prompt counts are recorded separately; allow room for output and template overhead within the actual context allocation.

Chat summaries retain `usage_source` (`server`, `chunks`, `mixed`, `unavailable`), source counts and completion-token totals. A prompt-only usage event does not count as server completion-token accounting. Chunk estimates remain visible for diagnosis and block comparison readiness. Streams that end without a completion signal fail rather than counting partial text as success.

- `ttft_s`: time to first content or reasoning fragment. `visible_ttft_s` separately measures first visible content.
- `prefill_tps`: prompt count divided by TTFT, an end-to-end proxy including queue/transport overhead; not an isolated kernel prefill measurement.
- `decode_tps`: estimated from completion count and first/last streamed fragment timing; buffering and multi-token fragments limit precision even with server usage.
- `throughput_tps`: successfully reported completion tokens divided by total level wall time, including failed requests.
- Utility `items_per_s`: successful batch items divided by summed request elapsed time, **including failed-request time**. Validation requires complete finite numeric vectors or indexed rerank scores; HTTP 200 with an error/invalid body is a failed request.
- Percentiles use sorted successful samples and the existing nearest-index rule. Per-metric sample counts and missing reasons expose coverage; failed requests do not become zero-latency samples. Cached/reasoning token counts stay null when unreported, and a reported zero stays zero.

`requests` counts observed terminal outcomes, including errors; `successful_requests + errors = requests`. `requests_scheduled` is the intended count, and `unfinished_requests` is the difference. On interruption it includes outcomes not collected by the coordinator, even if an outstanding worker later finishes. A partial summary is never a completed run. Setup/probe failures are recorded separately and also affect process exit status.

## Memory

Legacy scalar names remain for inspection. Each is also present in `memory.metrics` with `value`, `unit`, `source`, `scope`, `samples` and `missing_reason`; `memory.sampling_interval_s` is the requested poll interval, not a sampling-frequency guarantee.

| Metric | Unit | Scope |
|---|---|---|
| `peak_rss_mb` | MiB | Only the explicit server PID; excludes children |
| `peak_gpu_mb` | MiB | Sum across **all visible GPU compute processes**, not necessarily just the server |
| `min_mem_available_gb` | GiB | Linux host `/proc/meminfo` available memory |

Missing/unsupported telemetry, including `nvidia-smi` N/A, is null with a reason. Zero is reserved for a valid zero observation. RSS, GPU allocation and host available memory measure different scopes: do not add them or treat missing values as unlimited headroom. Remote runs need separately collected target telemetry before a memory gate can pass; there is no remote telemetry importer in this workstream.

## Reading and comparing

`read_result(path)` reads unversioned legacy records as schema 0, preserves their observations and marks them incomplete. It accepts schema 1, rejects unknown schema versions/non-finite JSON, and recomputes readiness instead of trusting a saved `comparison` label. Incomplete nested evidence produces issues; malformed top-level objects are rejected. No filename or free-text inference supplies missing facts.

`comparison_fingerprint(record)` refuses incomplete evidence. It hashes method, workload, server environment, structured provenance and effective parameters. Timestamp, client hardware, notes, endpoint URL, sampling PID, run ID and links are excluded. Context, concurrency, artifact, engine/router, quantization, sampling, template, config and system identities remain distinct. It is a key for **repeats of the same candidate configuration**, not the cross-engine comparison group or a ranking algorithm.

`comparison.status: ready` means the run has the structural identity and successful request/token accounting needed to consider repeat comparison. It does **not** prove quality equivalence, cache behavior, feature parity, installation reliability, memory headroom or soak stability. Missing telemetry and external evidence still require later admission gates. A future scorer must compare controlled workload/model/system dimensions, preserve engine/quantization differences as candidate variables, check linked evidence, and apply an explicit acceptance policy before declaring a winner.
