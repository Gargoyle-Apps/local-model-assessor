#!/usr/bin/env python3
"""Benchmark one OpenAI-compatible endpoint for the inference-stack spike.

Run via ./scripts/py scripts/bench-inference.py --base-url URL --model ID --workload W1 \
    --engine llama.cpp --engine-version b7966 --quant Q4_K_M --model-file NAME.gguf

Works against any server that speaks /v1/chat/completions (Ollama, llama-server,
llama-swap, vLLM, SGLang, MLX servers). Sends no API keys and uses greedy,
seeded sampling. Start a fresh server per run. Results are machine-specific and
default to the gitignored integrations/inference-stacks/results/ directory.
"""

import argparse
import importlib.util
import json
import platform
import random
import shutil
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "integrations" / "inference-stacks" / "results"

# Request shapes from the spike. W2 keeps one long prefix across requests so
# engines with prefix caching can reuse it; W1/W3 prepend a nonce to defeat it.
WORKLOADS = {
    "W1": {"concurrency": [1], "prompt_tokens": 2000, "max_tokens": 500, "shared_prefix": False},
    "W2": {"concurrency": [1, 2, 4], "prompt_tokens": 16000, "max_tokens": 400, "shared_prefix": True},
    "W3": {"concurrency": [8, 16], "prompt_tokens": 2000, "max_tokens": 300, "shared_prefix": False},
    "W4": {"batch": 32, "doc_tokens": 256},
}

_VOCAB = (
    "system memory cache engine request token model router stream kernel batch "
    "latency throughput prefix context decode prefill swap queue worker config "
    "tensor layer expert gate vector index shard driver build version profile"
).split()

# Synthetic text runs ~1.3 tokens per word on common tokenizers; usage reports
# from the server give the real counts.
_WORDS_PER_TOKEN = 0.75


def synthetic_text(tokens, rng):
    return " ".join(rng.choice(_VOCAB) for _ in range(max(1, int(tokens * _WORDS_PER_TOKEN))))


def api_root(base_url):
    base = base_url.rstrip("/")
    return base[:-3] if base.endswith("/v1") else base


def _post(url, body, timeout):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"},
        method="POST",
    )
    return urllib.request.urlopen(req, timeout=timeout)


def run_chat(root, model, prompt, max_tokens, seed, timeout=600.0):
    """Stream one chat completion and time it. Never raises; errors are recorded."""
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "top_p": 1,
        "seed": seed,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    start = time.perf_counter()
    first = last = None
    chunks, text, usage = 0, [], None
    try:
        with _post(f"{root}/v1/chat/completions", body, timeout) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                event = json.loads(data)
                if event.get("usage"):
                    usage = event["usage"]
                for choice in event.get("choices") or []:
                    delta = choice.get("delta") or {}
                    piece = delta.get("content") or delta.get("reasoning_content") or delta.get("reasoning")
                    if piece:
                        now = time.perf_counter()
                        first = first or now
                        last = now
                        chunks += 1
                        text.append(delta.get("content") or "")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "total_s": time.perf_counter() - start}
    end = time.perf_counter()
    if first is None:
        return {"ok": False, "error": "no tokens streamed", "total_s": end - start}
    prompt_tokens = (usage or {}).get("prompt_tokens")
    completion_tokens = (usage or {}).get("completion_tokens") or chunks
    ttft = first - start
    decode_s = last - first
    return {
        "ok": True,
        "ttft_s": ttft,
        "total_s": end - start,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "usage_source": "server" if usage else "chunks",
        "prefill_tps": prompt_tokens / ttft if prompt_tokens and ttft > 0 else None,
        "decode_tps": (completion_tokens - 1) / decode_s if completion_tokens > 1 and decode_s > 0 else None,
        "text": "".join(text),
    }


def _pct(values, q):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    return values[min(len(values) - 1, round(q * (len(values) - 1)))]


def summarize(results, wall_s):
    ok = [r for r in results if r["ok"]]
    out = {
        "requests": len(results),
        "errors": len(results) - len(ok),
        "error_rate": (len(results) - len(ok)) / len(results) if results else None,
        "wall_s": wall_s,
        "throughput_tps": sum(r["completion_tokens"] for r in ok) / wall_s if ok and wall_s > 0 else None,
    }
    for key in ("ttft_s", "prefill_tps", "decode_tps"):
        vals = [r[key] for r in ok]
        out[f"{key}_p50"] = _pct(vals, 0.5)
        out[f"{key}_p95"] = _pct(vals, 0.95)
    if len(ok) < len(results):
        out["first_error"] = next(r["error"] for r in results if not r["ok"])
    return out


class MemorySampler(threading.Thread):
    """Poll memory while a run is in flight; records peaks, never raises."""

    def __init__(self, pid=None, interval=0.5):
        super().__init__(daemon=True)
        self.pid, self.interval = pid, interval
        # Not `_stop`: threading.Thread uses that name internally.
        self._halt = threading.Event()
        self.peak_rss_mb = self.peak_gpu_mb = self.min_mem_available_gb = None

    def run(self):
        while not self._halt.is_set():
            self.sample()
            self._halt.wait(self.interval)

    def sample(self):
        if self.pid:
            out = _quiet(["ps", "-o", "rss=", "-p", str(self.pid)])
            if out and out.strip().isdigit():
                self.peak_rss_mb = max(self.peak_rss_mb or 0, int(out.strip()) / 1024)
        # GB10 reports N/A for memory.used, so per-process allocations are the
        # usable GPU signal there.
        out = _quiet(["nvidia-smi", "--query-compute-apps=used_memory", "--format=csv,noheader,nounits"])
        if out:
            used = sum(float(x) for x in out.split() if x.replace(".", "", 1).isdigit())
            self.peak_gpu_mb = max(self.peak_gpu_mb or 0, used)
        try:
            with open("/proc/meminfo", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("MemAvailable:"):
                        gb = int(line.split()[1]) / 2**20
                        self.min_mem_available_gb = min(self.min_mem_available_gb or gb, gb)
                        break
        except OSError:
            pass

    def stop(self):
        self._halt.set()
        self.join(timeout=5)
        return {
            "peak_rss_mb": self.peak_rss_mb,
            "peak_gpu_mb": self.peak_gpu_mb,
            "min_mem_available_gb": self.min_mem_available_gb,
        }


def _quiet(cmd):
    if not shutil.which(cmd[0]):
        return None
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout if out.returncode == 0 else None


def chat_prompts(shape, n, seed, prompt_tokens=None):
    rng = random.Random(seed)
    tokens = prompt_tokens or shape["prompt_tokens"]
    if shape["shared_prefix"]:
        prefix = synthetic_text(tokens, rng)
        return [f"{prefix}\n\nTask {i}: summarize the text above in five bullets." for i in range(n)]
    return [
        f"[run {seed}-{i}] {synthetic_text(tokens, rng)}\n\nSummarize the text above in five bullets."
        for i in range(n)
    ]


def run_chat_workload(args, root):
    shape = WORKLOADS[args.workload]
    levels = args.concurrency or shape["concurrency"]
    max_tokens = args.max_tokens or shape["max_tokens"]
    report = {"levels": []}

    if args.swap_from:
        run_chat(root, args.swap_from, "Say OK.", 8, args.seed)
        swap = run_chat(root, args.model, "Say OK.", 8, args.seed)
        report["swap_ttft_s"] = swap.get("ttft_s")
    elif args.measure_cold_start:
        cold = run_chat(root, args.model, "Say OK.", 8, args.seed)
        report["cold_ttft_s"] = cold.get("ttft_s")

    for i in range(args.warmup):
        run_chat(root, args.model, chat_prompts(shape, 1, args.seed + 1000 + i, args.prompt_tokens)[0],
                 32, args.seed)

    for level in levels:
        n = args.requests or max(level * 2, 4)
        prompts = chat_prompts(shape, n, args.seed + level, args.prompt_tokens)
        sampler = MemorySampler(pid=args.pid)
        sampler.start()
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=level) as pool:
            results = list(pool.map(
                lambda p: run_chat(root, args.model, p, max_tokens, args.seed, args.timeout), prompts))
        wall = time.perf_counter() - start
        summary = summarize(results, wall)
        summary.update({"concurrency": level, "max_tokens": max_tokens, **sampler.stop()})
        report["levels"].append(summary)
    return report


def run_utility_workload(args, root):
    """W4: embedding and rerank throughput, checking the chat model stays resident."""
    shape = WORKLOADS["W4"]
    rng = random.Random(args.seed)
    docs = [synthetic_text(shape["doc_tokens"], rng) for _ in range(shape["batch"])]
    n = args.requests or 8
    report = {}

    def timed(url, body):
        start = time.perf_counter()
        try:
            with _post(url, body, args.timeout) as resp:
                json.loads(resp.read())
            return time.perf_counter() - start, None
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return time.perf_counter() - start, f"{type(exc).__name__}: {exc}"

    if args.model:
        report["chat_ttft_before_s"] = run_chat(root, args.model, "Say OK.", 8, args.seed).get("ttft_s")

    for key, model, url, body in (
        ("embedding", args.embed_model, f"{root}/v1/embeddings",
         lambda m: {"model": m, "input": docs}),
        ("rerank", args.rerank_model, f"{root}/v1/rerank",
         lambda m: {"model": m, "query": docs[0], "documents": docs}),
    ):
        if not model:
            continue
        timings = [timed(url, body(model)) for _ in range(n)]
        ok = [t for t, err in timings if err is None]
        report[key] = {
            "model": model,
            "requests": n,
            "errors": n - len(ok),
            "items_per_s": shape["batch"] * len(ok) / sum(ok) if ok else None,
            "latency_s_p50": _pct(ok, 0.5),
            "first_error": next((err for _, err in timings if err), None),
        }

    if args.model:
        report["chat_ttft_after_s"] = run_chat(root, args.model, "Say OK.", 8, args.seed).get("ttft_s")
    return report


def run_quality(args, root):
    """Greedy spot-check: an item passes when every expected substring appears."""
    items = [json.loads(line) for line in Path(args.quality_set).read_text().splitlines() if line.strip()]
    graded = []
    for item in items:
        r = run_chat(root, args.model, item["prompt"], item.get("max_tokens", 256), args.seed, args.timeout)
        text = (r.get("text") or "").lower()
        passed = r["ok"] and all(e.lower() in text for e in item["expect"])
        graded.append({"id": item["id"], "passed": passed, "output": r.get("text"), "error": r.get("error")})
    return {"items": len(graded), "pass_rate": sum(g["passed"] for g in graded) / len(graded) if graded else None,
            "results": graded}


def environment(args):
    detect_path = Path(__file__).resolve().parent / "detect-hardware-profile.py"
    spec = importlib.util.spec_from_file_location("detect_hardware_profile", detect_path)
    detect = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(detect)
    detected = detect.classify(detect.collect_signals(), nodes=args.nodes)
    smi = _quiet(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"])
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "profile": detected["profile"],
        "profile_traits": detected["traits"],
        "os": platform.platform(),
        "driver": smi.strip().splitlines()[0] if smi else None,
        "engine": args.engine,
        "engine_version": args.engine_version,
        "router": args.router,
        "model": args.model,
        "model_file": args.model_file,
        "quant": args.quant,
        "embed_model": args.embed_model,
        "rerank_model": args.rerank_model,
        "seed": args.seed,
        "notes": args.notes,
    }


def _slug(value):
    return "".join(c if c.isalnum() or c in ".-" else "-" for c in (value or "none"))[:48]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", required=True, help="Server root or /v1 URL, e.g. http://127.0.0.1:8080")
    parser.add_argument("--workload", choices=sorted(WORKLOADS), required=True)
    parser.add_argument("--model", help="Chat model ID as the server names it (required for W1-W3)")
    parser.add_argument("--embed-model", help="W4 embedding model ID")
    parser.add_argument("--rerank-model", help="W4 reranker model ID")
    parser.add_argument("--engine", required=True, help="e.g. ollama, llama.cpp, vllm, sglang, omlx, vllm-metal")
    parser.add_argument("--engine-version", required=True)
    parser.add_argument("--router", default="none", help="Front door in use: none, llama-swap, llama-server-router")
    parser.add_argument("--quant", help="e.g. Q4_K_M, MLX-4bit, FP8, NVFP4, MXFP4")
    parser.add_argument("--model-file", help="Exact file or repo revision served")
    parser.add_argument("--concurrency", type=int, nargs="+", help="Override the workload's concurrency levels")
    parser.add_argument("--requests", type=int, help="Requests per level (default: 2x concurrency, min 4)")
    parser.add_argument("--prompt-tokens", type=int, help="Override prompt length (W2 spans 8k-32k)")
    parser.add_argument("--max-tokens", type=int)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--measure-cold-start", action="store_true",
                        help="Time the first request before warmup (start the server just before)")
    parser.add_argument("--swap-from", help="Load this model first, then time the swap to --model")
    parser.add_argument("--quality-set", help="JSONL eval set run after the workload")
    parser.add_argument("--pid", type=int, help="Server PID for peak RSS sampling")
    parser.add_argument("--nodes", type=int, default=1, help="Linked GB10 nodes (2 for gb10-x2)")
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--notes", help="Free-text flags or settings worth recording")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    if args.workload != "W4" and not args.model:
        parser.error("--model is required for W1-W3")
    if args.workload == "W4" and not (args.embed_model or args.rerank_model):
        parser.error("W4 needs --embed-model and/or --rerank-model")

    root = api_root(args.base_url)
    record = {"environment": environment(args), "workload": args.workload}
    if args.workload == "W4":
        record["result"] = run_utility_workload(args, root)
    else:
        record["result"] = run_chat_workload(args, root)
    if args.quality_set:
        record["quality"] = run_quality(args, root)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    env = record["environment"]
    stamp = env["timestamp"].replace(":", "").replace("+0000", "Z")
    name = "_".join(_slug(x) for x in (stamp, env["profile"], args.engine, args.model or args.embed_model,
                                       args.quant, args.workload))
    path = args.out_dir / f"{name}.json"
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    print(f"{args.workload} on {env['profile']} via {args.engine} {args.engine_version}")
    for level in record["result"].get("levels", []):
        def fmt(v, spec=".2f"):
            return "-" if v is None else format(v, spec)
        print(f"  c={level['concurrency']:>2}  ttft p50 {fmt(level['ttft_s_p50'])}s  "
              f"decode p50 {fmt(level['decode_tps_p50'], '.1f')} tok/s  "
              f"throughput {fmt(level['throughput_tps'], '.1f')} tok/s  errors {level['errors']}/{level['requests']}")
    for key in ("embedding", "rerank"):
        if key in record["result"]:
            r = record["result"][key]
            print(f"  {key}: {r['items_per_s'] or 0:.1f} items/s, errors {r['errors']}/{r['requests']}")
    if record.get("quality", {}).get("pass_rate") is not None:
        print(f"  quality pass rate: {record['quality']['pass_rate']:.0%}")
    print(f"Wrote {path}")
    errors = sum(lvl["errors"] for lvl in record["result"].get("levels", []))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
