#!/usr/bin/env python3
"""Benchmark one OpenAI-compatible endpoint for the inference-stack spike.

Run via ./scripts/py scripts/bench-inference.py --base-url URL --model ID --workload W1 \
    --engine llama.cpp --engine-version b7966 --quant Q4_K_M --model-file NAME.gguf

Works against any server that speaks /v1/chat/completions (Ollama, llama-server,
llama-swap, vLLM, SGLang, MLX servers). Sends no API keys; sampling defaults to
greedy with a fixed seed. Start a fresh server per run. Results are machine-specific and
default to the gitignored integrations/inference-stacks/results/ directory.
"""

import argparse
import hashlib
import importlib.util
import ipaddress
import json
import math
import os
import platform
import random
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "integrations" / "inference-stacks" / "results"
SCHEMA_VERSION = 1
METHOD_VERSION = "finite-v2"


def _finite_number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool) and
            -sys.float_info.max <= value <= sys.float_info.max)


def _count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _json(text):
    def invalid(value):
        raise ValueError(f"non-finite JSON value: {value}")
    value = json.loads(text, parse_constant=invalid)
    json.dumps(value, allow_nan=False)  # Also reject overflow such as 1e999.
    return value


def load_metadata(path):
    """Operator-observed deployment facts, never inferred from names or notes."""
    data = _json(Path(path).read_text(encoding="utf-8")) if path else {}
    return validate_metadata(data)


def validate_metadata(data):
    if not isinstance(data, dict):
        raise ValueError("metadata must be a JSON object")
    string_fields = (
        "system_id", "deployment_id", "config_id", "model_family", "model_revision",
        "artifact_id", "tokenizer_id", "chat_template_id", "compute_backend",
        "compute_precision", "expected_backend", "router_version",
    )
    for key in string_fields:
        if key in data and (not isinstance(data[key], str) or not data[key].strip()):
            raise ValueError(f"metadata.{key} must be a nonempty string")
    for key in ("context_tokens", "engine_slots", "router_limit"):
        if key in data and (not _count(data[key]) or data[key] == 0):
            raise ValueError(f"metadata.{key} must be a positive integer")
    for key in ("server", "utilities", "speculation"):
        if key in data and not isinstance(data[key], dict):
            raise ValueError(f"metadata.{key} must be an object")
    server = data.get("server", {})
    for key in ("profile", "os", "driver"):
        if key in server and (not isinstance(server[key], str) or not server[key].strip()):
            raise ValueError(f"metadata.server.{key} must be a nonempty string")
    if "traits" in server and not isinstance(server["traits"], dict):
        raise ValueError("metadata.server.traits must be an object")
    if "observation" in server and server["observation"] not in ("real", "simulated", "unknown"):
        raise ValueError("metadata.server.observation must be real, simulated or unknown")
    for role, facts in data.get("utilities", {}).items():
        if role not in ("embedding", "rerank") or not isinstance(facts, dict):
            raise ValueError("metadata.utilities accepts embedding/rerank objects")
        for key in ("artifact_id", "model_family", "model_revision", "quant", "engine", "engine_version"):
            if key in facts and (not isinstance(facts[key], str) or not facts[key].strip()):
                raise ValueError(f"metadata.utilities.{role}.{key} must be a nonempty string")
    for key in ("method", "artifact_id"):
        value = data.get("speculation", {}).get(key)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"metadata.speculation.{key} must be a nonempty string")
    links = data.get("evidence_links", [])
    if not isinstance(links, list) or any(
        not isinstance(link, dict) or any(not isinstance(link.get(k), str) or not link[k].strip()
                                         for k in ("kind", "run_id", "file", "deployment_id", "config_id"))
        for link in links
    ):
        raise ValueError("evidence_links need kind, run_id, file, deployment_id and config_id strings")
    for link in links:
        if any(link[k] != data.get(k) for k in ("deployment_id", "config_id")):
            raise ValueError("evidence link deployment/config identity does not match this run")
    return data


def evidence_issues(record):
    """Structural comparability only; quality/feature/soak gates belong to scoring."""
    if record.get("schema_version") != SCHEMA_VERSION:
        return ["legacy or unsupported schema: comparison provenance unavailable"]
    issues = []
    if record.get("method_version") != METHOD_VERSION:
        issues.append("unsupported benchmark method")
    if record.get("run_status") != "complete":
        issues.append("run is not complete")
    try:
        uuid.UUID(record.get("run_id", ""))
    except (ValueError, TypeError, AttributeError):
        issues.append("missing or invalid run identity")
    env, params, meta = (record.get(k, {}) for k in ("environment", "parameters", "provenance"))
    if any(not isinstance(v, dict) for v in (env, params, meta, record.get("result"))):
        return issues + ["environment, parameters, provenance and result must be objects"]
    try:
        validate_metadata(meta)
    except ValueError as exc:
        return issues + [str(exc)]
    if record.get("evidence_links", []) != meta.get("evidence_links", []):
        issues.append("evidence links do not match provenance")
    if env.get("server_location") not in ("local", "remote"):
        issues.append("server location is unconfirmed (loopback may be a tunnel)")
    if env.get("hardware_observation") != "real":
        issues.append("server hardware is not a real observation")
    for key in ("profile", "os", "engine", "engine_version", "router"):
        if not isinstance(env.get(key), str) or not env[key].strip() or env[key] == "unknown":
            issues.append(f"missing environment.{key}")
    if not isinstance(env.get("profile_traits"), dict) or not env["profile_traits"]:
        issues.append("missing server hardware traits")
    for key in ("system_id", "deployment_id", "config_id", "compute_backend", "compute_precision"):
        if not isinstance(meta.get(key), str) or not meta[key].strip():
            issues.append(f"missing provenance.{key}")
    if env.get("router") != "none":
        if not meta.get("router_version") or not _count(meta.get("router_limit")) or meta["router_limit"] < 1:
            issues.append("router version/admission limit missing")
    for key in ("temperature", "top_p", "socket_timeout_s"):
        if not _finite_number(params.get(key)):
            issues.append(f"missing finite parameters.{key}")
    if not isinstance(params.get("chat_options"), dict) or type(params.get("seed")) is not int:
        issues.append("missing request options/seed")
    result = record["result"]
    if record.get("workload") == "W4":
        selected = [role for role, key in (("embedding", "embed_model"), ("rerank", "rerank_model")) if env.get(key)]
        if not selected or params.get("utility_order") != selected:
            issues.append("missing utility workload identity")
        for key in ("requests_per_utility", "batch", "doc_tokens"):
            if not _count(params.get(key)) or params[key] < 1:
                issues.append(f"missing parameters.{key}")
        for role in ("embedding", "rerank"):
            if env.get("embed_model" if role == "embedding" else "rerank_model"):
                utility = meta.get("utilities", {}).get(role, {})
                if not isinstance(utility, dict) or any(not utility.get(k) for k in (
                    "artifact_id", "model_family", "model_revision", "quant", "engine", "engine_version"
                )):
                    issues.append(f"missing {role} artifact/runtime provenance")
                issues.extend(summary_issues(result.get(role), params.get("requests_per_utility"), role))
                if not isinstance(result.get(role), dict) or not _finite_number(result[role].get("items_per_s")):
                    issues.append(f"missing {role} item rate")
        probes = result.get("chat_probes", [])
        if (not isinstance(probes, list) or len(probes) != (2 if env.get("model") else 0) or
                any(not isinstance(p, dict) or p.get("ok") is not True for p in probes)):
            issues.append("missing or failed utility chat probes")
    elif record.get("workload") in ("W1", "W2", "W3"):
        levels, targets, counts = result.get("levels", []), params.get("concurrency"), params.get("requests_per_level")
        if (not isinstance(targets, list) or not targets or any(not _count(c) or c < 1 for c in targets) or
                len(set(targets)) != len(targets) or not isinstance(counts, list) or len(counts) != len(targets)):
            issues.append("missing concurrency/request-count identity")
        elif (not isinstance(levels, list) or len(levels) != len(targets) or
              any(not isinstance(l, dict) for l in levels) or [l.get("concurrency") for l in levels] != targets):
            issues.append("missing concurrency levels")
        else:
            for level, count in zip(levels, counts):
                issues.extend(summary_issues(level, count, f"c={level['concurrency']}"))
                if level.get("level_status") != "complete":
                    issues.append("concurrency level is not complete")
                if level.get("usage_source") != "server":
                    issues.append(f"c={level['concurrency']}: token rates use estimated/unknown counts")
                if level.get("prompt_tokens_samples") != count:
                    issues.append(f"c={level['concurrency']}: incomplete prompt token accounting")
                for key in ("throughput_tps", "ttft_s_p50", "prompt_tokens_p50"):
                    if not _finite_number(level.get(key)):
                        issues.append(f"c={level['concurrency']}: missing {key}")
        for key in ("prompt_tokens_target", "max_tokens"):
            if not _count(params.get(key)) or params[key] < 1:
                issues.append(f"missing parameters.{key}")
        if not params.get("cache_treatment") or not _count(params.get("warmup")):
            issues.append("missing cache/warmup treatment")
        setup = result.get("setup", [])
        expected = params.get("warmup", 0) if _count(params.get("warmup")) else 0
        expected += 2 if params.get("swap_from") else 1 if params.get("measure_cold_start") else 0
        if (not isinstance(setup, list) or len(setup) != expected or
                any(not isinstance(s, dict) or s.get("ok") is not True for s in setup)):
            issues.append("missing or failed setup requests")
    else:
        issues.append("unsupported workload")
    if record.get("workload") != "W4" or env.get("model"):
        for key in ("model_family", "model_revision", "artifact_id", "tokenizer_id", "chat_template_id"):
            if not meta.get(key):
                issues.append(f"missing provenance.{key}")
        for key in ("context_tokens", "engine_slots"):
            if not _count(meta.get(key)) or meta[key] < 1:
                issues.append(f"missing provenance.{key}")
        if not env.get("model") or not env.get("quant") or not env.get("model_file"):
            issues.append("missing model ID/file/quantization")
        if params.get("reasoning_mode") not in ("enabled", "disabled"):
            issues.append("reasoning mode is unconfirmed")
        speculation = meta.get("speculation", {})
        if not speculation.get("method") or (speculation["method"] != "none" and not speculation.get("artifact_id")):
            issues.append("speculation method/artifact identity missing")
    if params.get("quality_sha256"):
        quality = record.get("quality", {})
        if (not isinstance(quality, dict) or quality.get("sha256") != params["quality_sha256"] or
                not _count(quality.get("items_scheduled")) or quality.get("items_scheduled", 0) < 1 or
                quality.get("items") != quality.get("items_scheduled")):
            issues.append("quality spot-check is incomplete or mismatched")
    return issues


def summary_issues(summary, scheduled, label):
    if not isinstance(summary, dict):
        return [f"{label}: missing results"]
    if (any(not _count(summary.get(k)) for k in ("requests_scheduled", "requests", "successful_requests", "errors", "unfinished_requests")) or
            not _count(scheduled) or scheduled < 1 or summary.get("requests_scheduled") != scheduled or
            summary.get("requests") != scheduled or summary.get("successful_requests") != scheduled or
            summary.get("errors") != 0 or summary.get("unfinished_requests") != 0):
        return [f"{label}: failed, unfinished or inconsistent request counts"]
    if not _finite_number(summary.get("wall_s")) or summary["wall_s"] <= 0:
        return [f"{label}: missing positive elapsed time"]
    return []


def read_result(path):
    """Read legacy observations without inventing provenance; reject newer schemas."""
    record = _json(Path(path).read_text(encoding="utf-8"))
    if not isinstance(record, dict) or any(not isinstance(record.get(k), dict)
                                          for k in ("environment", "result")):
        raise ValueError("result needs environment and result objects")
    version = record.get("schema_version", 0)
    if type(version) is not int or version not in (0, SCHEMA_VERSION):
        raise ValueError(f"unsupported schema_version: {version!r}")
    record["schema_version"] = version
    if version == 0:
        record.setdefault("run_status", "unknown")
    else:
        for key in ("parameters", "provenance"):
            if not isinstance(record.get(key), dict):
                raise ValueError(f"result needs a {key} object")
    issues = evidence_issues(record)
    record["comparison"] = {"status": "incomplete" if issues else "ready", "issues": issues}
    return record


def comparison_fingerprint(record):
    """Key for repeats of an identical configuration, not cross-engine ranking."""
    issues = evidence_issues(record)
    if issues:
        raise ValueError("incomplete evidence: " + "; ".join(issues))
    env = {k: v for k, v in record["environment"].items()
           if k not in ("timestamp", "client", "notes")}
    meta = {k: v for k, v in record["provenance"].items() if k != "evidence_links"}
    params = {k: v for k, v in record["parameters"].items() if k not in ("base_url", "memory_pid")}
    identity = {"method": record["method_version"], "workload": record["workload"],
                "environment": env, "provenance": meta, "parameters": params}
    return hashlib.sha256(json.dumps(identity, sort_keys=True, allow_nan=False).encode()).hexdigest()


def write_result(path, record):
    """Replace one run's checkpoint atomically; different runs have UUID filenames."""
    issues = evidence_issues(record)
    record["comparison"] = {"status": "incomplete" if issues else "ready", "issues": issues}
    payload = json.dumps(record, indent=2, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".inference-", suffix=".tmp", delete=False) as fh:
            temp_path = Path(fh.name)
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

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


def run_chat(root, model, prompt, max_tokens, seed, timeout=600.0, *,
             temperature=0.0, top_p=1.0, chat_options=None):
    """Stream one chat completion and time it. Never raises; errors are recorded."""
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "seed": seed,
        "stream": True,
        "stream_options": {"include_usage": True},
        **(chat_options or {}),
    }
    start = time.perf_counter()
    first = last = first_visible = None
    chunks, text, usage = 0, [], None
    terminal = False
    try:
        with _post(f"{root}/v1/chat/completions", body, timeout) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    terminal = True
                    break
                event = _json(data)
                if not isinstance(event, dict) or event.get("error"):
                    raise ValueError("invalid stream event or server error")
                if event.get("usage"):
                    usage = event["usage"]
                    if not isinstance(usage, dict):
                        raise ValueError("invalid usage object")
                for choice in event.get("choices") or []:
                    if not isinstance(choice, dict):
                        raise ValueError("invalid stream choice")
                    terminal = terminal or bool(choice.get("finish_reason"))
                    delta = choice.get("delta") or {}
                    if not isinstance(delta, dict):
                        raise ValueError("invalid stream delta")
                    piece = delta.get("content") or delta.get("reasoning_content") or delta.get("reasoning")
                    if piece:
                        if not isinstance(piece, str):
                            raise ValueError("invalid streamed text")
                        now = time.perf_counter()
                        first = now if first is None else first
                        last = now
                        if delta.get("content") and first_visible is None:
                            first_visible = now
                        chunks += 1
                        text.append(delta.get("content") or "")
    except (urllib.error.URLError, OSError, ValueError, TypeError) as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "total_s": time.perf_counter() - start}
    end = time.perf_counter()
    if first is None or not terminal:
        return {"ok": False, "error": "no tokens streamed" if first is None else "stream ended without completion",
                "total_s": end - start}
    prompt_tokens = (usage or {}).get("prompt_tokens")
    prompt_tokens = prompt_tokens if _count(prompt_tokens) else None
    reported = (usage or {}).get("completion_tokens")
    # A prompt-only usage event is not a server-reported completion count.
    server_counts = _count(reported) and reported > 0
    completion_tokens = reported if server_counts else chunks
    details = (usage or {}).get("completion_tokens_details") or {}
    reasoning_tokens = details.get("reasoning_tokens") if isinstance(details, dict) else None
    prompt_details = (usage or {}).get("prompt_tokens_details") or {}
    cached_tokens = prompt_details.get("cached_tokens") if isinstance(prompt_details, dict) else None
    ttft = first - start
    decode_s = last - first
    return {
        "ok": True,
        "ttft_s": ttft,
        "visible_ttft_s": first_visible - start if first_visible is not None else None,
        "total_s": end - start,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "usage_source": "server" if server_counts else "chunks",
        "reasoning_tokens": reasoning_tokens if _count(reasoning_tokens) else None,
        "cached_tokens": cached_tokens if _count(cached_tokens) else None,
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
    sources = Counter(r.get("usage_source", "unknown") for r in ok)
    out = {
        "requests": len(results),
        "successful_requests": len(ok),
        "errors": len(results) - len(ok),
        "error_rate": (len(results) - len(ok)) / len(results) if results else None,
        "wall_s": wall_s,
        "throughput_tps": sum(r["completion_tokens"] for r in ok) / wall_s if ok and wall_s > 0 else None,
        "usage_source": next(iter(sources)) if len(sources) == 1 else "mixed" if sources else "unavailable",
        "usage_source_counts": dict(sources),
        "completion_tokens": sum(r["completion_tokens"] for r in ok),
    }
    out["metric_missing_reasons"] = {}
    for key in ("ttft_s", "visible_ttft_s", "prefill_tps", "decode_tps", "prompt_tokens", "cached_tokens", "reasoning_tokens"):
        vals = [r.get(key) for r in ok]
        out[f"{key}_samples"] = sum(v is not None for v in vals)
        out[f"{key}_p50"] = _pct(vals, 0.5)
        out[f"{key}_p95"] = _pct(vals, 0.95)
        if out[f"{key}_samples"] < len(results):
            out["metric_missing_reasons"][key] = "failed request, unreported usage, or insufficient streamed timing samples"
    if len(ok) < len(results):
        out["first_error"] = next(r["error"] for r in results if not r["ok"])
    return out


class MemorySampler(threading.Thread):
    """Poll memory while a run is in flight; records peaks, never raises."""

    def __init__(self, pid=None, interval=0.5, enabled=True):
        super().__init__(daemon=True)
        self.pid, self.interval, self.enabled = pid, interval, enabled
        # Not `_stop`: threading.Thread uses that name internally.
        self._halt = threading.Event()
        self.peak_rss_mb = self.peak_gpu_mb = self.min_mem_available_gb = None
        self.samples = Counter()

    def run(self):
        while not self._halt.is_set():
            self.sample()
            self._halt.wait(self.interval)

    def sample(self):
        if not self.enabled:
            return
        if self.pid:
            out = _quiet(["ps", "-o", "rss=", "-p", str(self.pid)])
            if out and out.strip().isdigit():
                self.peak_rss_mb = max(self.peak_rss_mb or 0, int(out.strip()) / 1024)
                self.samples["peak_rss_mb"] += 1
        # GB10 reports N/A for memory.used, so per-process allocations are the
        # usable GPU signal there.
        out = _quiet(["nvidia-smi", "--query-compute-apps=used_memory", "--format=csv,noheader,nounits"])
        if out is not None:
            try:
                values = [float(x.strip()) for x in out.splitlines() if x.strip()]
                if all(math.isfinite(v) and v >= 0 for v in values):
                    self.peak_gpu_mb = max(self.peak_gpu_mb or 0, sum(values))
                    self.samples["peak_gpu_mb"] += 1
            except ValueError:
                # N/A (or partly unavailable output) is not zero allocation.
                pass
        try:
            with open("/proc/meminfo", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("MemAvailable:"):
                        gb = int(line.split()[1]) / 2**20
                        self.min_mem_available_gb = gb if self.min_mem_available_gb is None else min(self.min_mem_available_gb, gb)
                        self.samples["min_mem_available_gb"] += 1
                        break
        except (OSError, ValueError, IndexError):
            pass

    def stop(self):
        self._halt.set()
        self.join()
        values = {
            "peak_rss_mb": self.peak_rss_mb,
            "peak_gpu_mb": self.peak_gpu_mb,
            "min_mem_available_gb": self.min_mem_available_gb,
        }
        definitions = {
            "peak_rss_mb": ("MiB", "ps rss", f"PID {self.pid}" if self.pid else "no PID supplied"),
            "peak_gpu_mb": ("MiB", "nvidia-smi compute apps", "all visible GPU processes, not just the server"),
            "min_mem_available_gb": ("GiB", "/proc/meminfo MemAvailable", "whole server host"),
        }
        metrics = {}
        for key, value in values.items():
            unit, source, scope = definitions[key]
            reason = None
            if value is None:
                reason = "server is not confirmed local" if not self.enabled else "no valid samples"
                if self.enabled and key == "peak_rss_mb" and not self.pid:
                    reason = "server PID not supplied"
            metrics[key] = {"value": value, "unit": unit, "source": source, "scope": scope,
                            "samples": self.samples[key], "missing_reason": reason}
        return {**values, "memory": {"sampling_interval_s": self.interval, "metrics": metrics}}


def _quiet(cmd):
    if not shutil.which(cmd[0]):
        return None
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout if out.returncode == 0 else None


def chat_prompts(shape, n, seed, prompt_tokens=None, nonce=None):
    rng = random.Random(seed)
    tokens = prompt_tokens or shape["prompt_tokens"]
    if shape["shared_prefix"]:
        prefix = synthetic_text(tokens, rng)
        return [f"{prefix}\n\nTask {i}: summarize the text above in five bullets." for i in range(n)]
    return [
        f"[run {nonce or seed}-{i}] {synthetic_text(tokens, rng)}\n\nSummarize the text above in five bullets."
        for i in range(n)
    ]


def _chat(args, root, model, prompt, max_tokens):
    return run_chat(root, model, prompt, max_tokens, args.seed, args.timeout,
                    temperature=args.temperature, top_p=args.top_p, chat_options=args.chat_options)


def run_chat_workload(args, root, report=None, checkpoint=None):
    shape = WORKLOADS[args.workload]
    levels = args.concurrency or shape["concurrency"]
    max_tokens = args.max_tokens or shape["max_tokens"]
    report = report if report is not None else {}
    report.update({"levels": [], "setup": []})

    def setup(phase, model, prompt, max_tokens):
        result = _chat(args, root, model, prompt, max_tokens)
        report["setup"].append({"phase": phase, **{k: v for k, v in result.items() if k != "text"}})
        return result

    if args.swap_from:
        setup("swap_from", args.swap_from, "Say OK.", 8)
        swap = setup("swap_to", args.model, "Say OK.", 8)
        report["swap_ttft_s"] = swap.get("ttft_s")
    elif args.measure_cold_start:
        cold = setup("cold_start", args.model, "Say OK.", 8)
        report["cold_ttft_s"] = cold.get("ttft_s")

    for i in range(args.warmup):
        setup("warmup", args.model, chat_prompts(shape, 1, args.seed + 1000 + i,
                                                args.prompt_tokens, f"{args.run_id}-warmup-{i}")[0], 32)

    for level in levels:
        n = args.requests or max(level * 2, 4)
        prompts = chat_prompts(shape, n, args.seed + level, args.prompt_tokens, f"{args.run_id}-{level}")
        sampler = MemorySampler(pid=args.pid, enabled=args.server_location == "local")
        sampler.start()
        start = time.perf_counter()
        pool = ThreadPoolExecutor(max_workers=level)
        results, complete = [], False
        try:
            futures = [pool.submit(_chat, args, root, args.model, prompt, max_tokens) for prompt in prompts]
            for future in as_completed(futures):
                results.append(future.result())
            complete = True
        finally:
            wall = time.perf_counter() - start
            pool.shutdown(wait=False, cancel_futures=True)
            summary = summarize(results, wall)
            summary.update({"concurrency": level, "max_tokens": max_tokens,
                            "requests_scheduled": n, "unfinished_requests": n - len(results),
                            "level_status": "complete" if complete else "interrupted",
                            **sampler.stop()})
            report["levels"].append(summary)
            if checkpoint:
                checkpoint()
    return report


def validate_utility(payload, kind, count):
    """Reject HTTP-200 error bodies and incomplete or nonnumeric utility output."""
    if not isinstance(payload, dict) or payload.get("error"):
        raise ValueError("invalid utility response or server error")
    rows = payload.get("data") if kind == "embedding" else payload.get("results", payload.get("data"))
    if not isinstance(rows, list) or len(rows) != count or any(not isinstance(r, dict) for r in rows):
        raise ValueError(f"{kind} response must contain {count} results")
    if kind == "embedding":
        vectors = [r.get("embedding") for r in rows]
        if any(not isinstance(v, list) or not v or any(not _finite_number(x) for x in v) for v in vectors):
            raise ValueError("invalid embedding vector")
        if len({len(v) for v in vectors}) != 1:
            raise ValueError("embedding dimensions differ")
        indexed = any("index" in r for r in rows)
    else:
        if any(not _finite_number(r.get("relevance_score")) for r in rows):
            raise ValueError("invalid rerank score")
        indexed = True
    if indexed:
        indices = [r.get("index") for r in rows]
        if any(not _count(i) for i in indices) or set(indices) != set(range(count)):
            raise ValueError("invalid or duplicate utility result indices")


def summarize_utility(timings, batch):
    ok = [t for t, err in timings if err is None]
    wall = sum(t for t, _ in timings)
    return {"requests": len(timings), "successful_requests": len(ok), "errors": len(timings) - len(ok),
            "error_rate": (len(timings) - len(ok)) / len(timings) if timings else None,
            "wall_s": wall, "items_per_s": batch * len(ok) / wall if wall > 0 else None,
            "latency_s_p50": _pct(ok, 0.5), "latency_s_p95": _pct(ok, 0.95),
            "first_error": next((err for _, err in timings if err), None)}


def run_utility_workload(args, root, report=None, checkpoint=None):
    """W4 utility timings; before/after chat probes do not prove residency."""
    shape = WORKLOADS["W4"]
    rng = random.Random(args.seed)
    docs = [synthetic_text(shape["doc_tokens"], rng) for _ in range(shape["batch"])]
    n = args.requests or 8
    report = report if report is not None else {}
    report["chat_probes"] = []
    report["residency_verified"] = False

    def timed(url, body, kind):
        start = time.perf_counter()
        try:
            with _post(url, body, args.timeout) as resp:
                validate_utility(_json(resp.read()), kind, len(docs))
            return time.perf_counter() - start, None
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return time.perf_counter() - start, f"{type(exc).__name__}: {exc}"

    def chat_probe(phase):
        r = _chat(args, root, args.model, "Say OK.", 8)
        report[f"chat_ttft_{phase}_s"] = r.get("ttft_s")
        report["chat_probes"].append({"phase": phase, **{k: v for k, v in r.items() if k != "text"}})

    sampler = MemorySampler(pid=args.pid, enabled=args.server_location == "local")
    sampler.start()
    try:
        if args.model:
            chat_probe("before")
        for key, model, url, body in (
            ("embedding", args.embed_model, f"{root}/v1/embeddings",
             lambda m: {"model": m, "input": docs}),
            ("rerank", args.rerank_model, f"{root}/v1/rerank",
             lambda m: {"model": m, "query": docs[0], "documents": docs}),
        ):
            if not model:
                continue
            timings = []
            try:
                for _ in range(n):
                    timings.append(timed(url, body(model), key))
            finally:
                report[key] = {"model": model, "requests_scheduled": n,
                               "unfinished_requests": n - len(timings), **summarize_utility(timings, shape["batch"])}
                if checkpoint:
                    checkpoint()
        if args.model:
            chat_probe("after")
    finally:
        report.update(sampler.stop())
    return report


def run_quality(args, root, report=None):
    """Substring spot-check, explicitly distinct from task-quality equivalence."""
    report = report if report is not None else {}
    items = [_json(line) for line in args.quality_bytes.decode().splitlines() if line.strip()]
    graded = report["results"] = []
    report.update({"method": "substring-smoke", "sha256": hashlib.sha256(args.quality_bytes).hexdigest(),
                   "items_scheduled": len(items)})
    try:
        for item in items:
            r = _chat(args, root, args.model, item["prompt"], item.get("max_tokens", 256))
            text = (r.get("text") or "").lower()
            passed = r["ok"] and all(e.lower() in text for e in item["expect"])
            graded.append({"id": item["id"], "passed": passed, "output": r.get("text"), "error": r.get("error")})
    finally:
        report.update({"items": len(graded), "pass_rate": sum(g["passed"] for g in graded) / len(graded) if graded else None})
    return report


def host_environment(nodes):
    detect_path = Path(__file__).resolve().parent / "detect-hardware-profile.py"
    spec = importlib.util.spec_from_file_location("detect_hardware_profile", detect_path)
    detect = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(detect)
    detected = detect.classify(detect.collect_signals(), nodes=nodes)
    smi = _quiet(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"])
    return {
        "profile": detected["profile"],
        "profile_traits": detected["traits"],
        "os": platform.platform(),
        "driver": smi.strip().splitlines()[0] if smi else None,
    }


def environment(args):
    client = host_environment(args.nodes if args.server_location == "local" else 1)
    server = args.metadata.get("server", {}) if args.server_location == "remote" else {}
    observed = client if args.server_location == "local" else {
        "profile": server.get("profile", "unknown"), "profile_traits": server.get("traits", {}),
        "os": server.get("os"), "driver": server.get("driver"),
    }
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **observed,
        "client": client,
        "server_location": args.server_location,
        "hardware_observation": "real" if args.server_location == "local" else server.get("observation", "unknown"),
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
    # Leave room for all labels plus the UUID within a filesystem's name limit.
    return "".join(c if c.isascii() and (c.isalnum() or c in ".-") else "-" for c in (value or "none"))[:32]


def effective_parameters(args):
    params = {
        "base_url": api_root(args.base_url), "seed": args.seed,
        "temperature": args.temperature, "top_p": args.top_p,
        "reasoning_mode": args.reasoning_mode, "chat_options": args.chat_options,
        "socket_timeout_s": args.timeout,
        "quality_sha256": hashlib.sha256(args.quality_bytes).hexdigest() if args.quality_bytes else None,
        "memory_pid": args.pid,
    }
    if args.workload == "W4":
        params.update({"requests_per_utility": args.requests or 8, **WORKLOADS["W4"],
                       "chat_probe_max_tokens": 8 if args.model else None,
                       "utility_order": [k for k, m in (("embedding", args.embed_model), ("rerank", args.rerank_model)) if m]})
    else:
        shape = WORKLOADS[args.workload]
        levels = args.concurrency or shape["concurrency"]
        params.update({
            "concurrency": levels, "requests_per_level": [args.requests or max(c * 2, 4) for c in levels],
            "prompt_tokens_target": args.prompt_tokens or shape["prompt_tokens"],
            "max_tokens": args.max_tokens or shape["max_tokens"], "warmup": args.warmup,
            "warmup_max_tokens": 32, "measure_cold_start": args.measure_cold_start,
            "swap_from": args.swap_from, "setup_max_tokens": 8,
            "cache_treatment": "shared-prefix-per-level" if shape["shared_prefix"] else "unique-run-request-prefix",
        })
    return params


def runtime_errors(record):
    result = record["result"]
    errors = sum(level["errors"] + level.get("unfinished_requests", 0) for level in result.get("levels", []))
    for role in ("embedding", "rerank"):
        if role in result:
            errors += result[role]["errors"] + result[role].get("unfinished_requests", 0)
    errors += sum(not r["ok"] for key in ("setup", "chat_probes") for r in result.get(key, []))
    errors += sum(bool(r.get("error")) for r in record.get("quality", {}).get("results", []))
    return errors


def validate_arguments(parser, args):
    if args.workload != "W4" and not args.model:
        parser.error("--model is required for W1-W3")
    if args.workload == "W4" and not (args.embed_model or args.rerank_model):
        parser.error("W4 needs --embed-model and/or --rerank-model")
    if args.workload != "W4" and (args.embed_model or args.rerank_model):
        parser.error("--embed-model/--rerank-model apply only to W4")
    if args.workload == "W4" and (args.concurrency or args.prompt_tokens is not None or
                                   args.max_tokens is not None or args.warmup != 1 or
                                   args.measure_cold_start or args.swap_from):
        parser.error("W4 does not use concurrency, prompt/max tokens, warmup, cold-start or swap controls")
    for key in ("requests", "prompt_tokens", "max_tokens", "pid", "nodes"):
        value = getattr(args, key)
        if value is not None and value <= 0:
            parser.error(f"--{key.replace('_', '-')} must be positive")
    if args.warmup < 0:
        parser.error("--warmup must be nonnegative")
    if args.concurrency and (any(c <= 0 for c in args.concurrency) or len(set(args.concurrency)) != len(args.concurrency)):
        parser.error("--concurrency must contain distinct positive integers")
    for key in ("timeout", "temperature", "top_p"):
        if not math.isfinite(getattr(args, key)):
            parser.error(f"--{key.replace('_', '-')} must be finite")
    if args.timeout <= 0 or args.temperature < 0 or not 0 < args.top_p <= 1:
        parser.error("timeout must be positive, temperature nonnegative and top-p in (0, 1]")
    try:
        parsed = urllib.parse.urlsplit(args.base_url)
        parsed.port  # Validate malformed/non-numeric ports before any request.
    except ValueError as exc:
        parser.error(f"invalid --base-url: {exc}")
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        parser.error("--base-url must be an http(s) URL without credentials, query or fragment")
    try:
        local = ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        local = parsed.hostname == "localhost"
    if args.server_location == "local" and not local:
        parser.error("--server-location local requires a loopback URL without a tunnel")
    if args.server_location != "local" and (args.pid is not None or args.nodes != 1):
        parser.error("--pid/--nodes describe a confirmed local server only")
    try:
        args.metadata = load_metadata(args.metadata)
        if args.metadata.get("server") and args.server_location != "remote":
            raise ValueError("metadata.server requires --server-location remote")
        args.chat_options = _json(args.chat_options)
        reserved = {"model", "messages", "max_tokens", "max_completion_tokens", "temperature", "top_p",
                    "seed", "stream", "stream_options", "n"}
        if not isinstance(args.chat_options, dict) or reserved.intersection(args.chat_options):
            raise ValueError("--chat-options must be an object without reserved request fields")
        args.quality_bytes = Path(args.quality_set).read_bytes() if args.quality_set else None
        if args.quality_bytes is not None:
            if not args.model:
                raise ValueError("--quality-set needs --model")
            items = [_json(line) for line in args.quality_bytes.decode().splitlines() if line.strip()]
            if not items:
                raise ValueError("quality set is empty")
            ids = set()
            for item in items:
                if (not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"] or
                    item["id"] in ids or not isinstance(item.get("prompt"), str) or not item["prompt"] or
                    not isinstance(item.get("expect"), list) or not item["expect"] or
                    any(not isinstance(s, str) or not s for s in item["expect"]) or
                    not _count(item.get("max_tokens", 256)) or item.get("max_tokens", 256) == 0):
                    raise ValueError("invalid quality item: unique id, prompt, nonempty expect strings and positive max_tokens required")
                ids.add(item["id"])
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


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
    parser.add_argument("--metadata", type=Path, help="Local JSON deployment provenance; see result-format.md")
    parser.add_argument("--server-location", choices=("unknown", "local", "remote"), default="unknown",
                        help="Explicit server location; loopback may be an SSH tunnel (default: unknown)")
    parser.add_argument("--concurrency", type=int, nargs="+", help="Override the workload's concurrency levels")
    parser.add_argument("--requests", type=int, help="Requests per level (default: 2x concurrency, min 4)")
    parser.add_argument("--prompt-tokens", type=int, help="Synthetic prompt token target; reserve context for output/template")
    parser.add_argument("--max-tokens", type=int)
    parser.add_argument("--warmup", type=int, default=1)
    setup = parser.add_mutually_exclusive_group()
    setup.add_argument("--measure-cold-start", action="store_true",
                        help="Time the first request before warmup (start the server just before)")
    setup.add_argument("--swap-from", help="Load this model first, then time the swap to --model")
    parser.add_argument("--quality-set", help="JSONL eval set run after the workload")
    parser.add_argument("--pid", type=int, help="Server PID for peak RSS sampling")
    parser.add_argument("--nodes", type=int, default=1, help="Linked GB10 nodes (2 for gb10-x2)")
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--reasoning-mode", choices=("unknown", "enabled", "disabled"), default="unknown",
                        help="Operator-observed mode; this label does not configure the server")
    parser.add_argument("--chat-options", default="{}", help="JSON extra request options, e.g. chat_template_kwargs")
    parser.add_argument("--timeout", type=float, default=600.0, help="Socket timeout, not a total request deadline")
    parser.add_argument("--notes", help="Free-text flags or settings worth recording")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    validate_arguments(parser, args)
    args.run_id = str(uuid.uuid4())
    root = api_root(args.base_url)
    record = {"schema_version": SCHEMA_VERSION, "method_version": METHOD_VERSION,
              "run_id": args.run_id, "run_status": "running", "environment": environment(args),
              "workload": args.workload, "parameters": effective_parameters(args),
              "provenance": args.metadata, "evidence_links": args.metadata.get("evidence_links", []), "result": {}}
    env = record["environment"]
    stamp = env["timestamp"].replace(":", "").replace("+0000", "Z")
    name = "_".join(_slug(x) for x in (stamp, env["profile"], args.engine, args.model or args.embed_model,
                                       args.quant, args.workload))
    path = args.out_dir / f"{name}_{args.run_id}.json"
    write_result(path, record)  # Persist identity before issuing the first request.
    rc = 1
    try:
        workload = run_utility_workload if args.workload == "W4" else run_chat_workload
        workload(args, root, record["result"], lambda: write_result(path, record))
        if args.quality_set:
            record["quality"] = {}
            run_quality(args, root, record["quality"])
        rc = 1 if runtime_errors(record) else 0
        record["run_status"] = "failed" if rc else "complete"
    except KeyboardInterrupt:
        rc = 130
        record.update({"run_status": "interrupted", "error": "interrupted by operator"})
    except Exception as exc:
        record.update({"run_status": "failed", "error": f"{type(exc).__name__}: {exc}"})
    finally:
        record["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        write_result(path, record)

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
    print(f"{record['run_status']}; comparison evidence {record['comparison']['status']}")
    if record.get("error"):
        print(record["error"], file=sys.stderr)
    print(f"Wrote {path}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
