"""Tests for bench-inference.py against a local fake OpenAI-compatible server."""

import importlib.util
import copy
import io
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"


def _load_script(name: str):
    module_name = name.replace("-", "_").removesuffix(".py")
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


mod = _load_script("bench-inference.py")


class _FakeServer(BaseHTTPRequestHandler):
    fail_chat = False
    fail_utility = False
    events = None
    with_usage = True
    seen = []

    def log_message(self, *args):
        pass

    def _json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).seen.append((self.path, body))
        if self.path == "/v1/chat/completions":
            if type(self).fail_chat:
                return self._json(500, {"error": "boom"})
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            if type(self).events is not None:
                for event in type(self).events:
                    self.wfile.write(f"data: {json.dumps(event) if isinstance(event, dict) else event}\n\n".encode())
                return None
            for word in ["Hello", " there", " friend", " 42"]:
                chunk = {"choices": [{"delta": {"content": word}}]}
                self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            if type(self).with_usage:
                usage = {"choices": [], "usage": {"prompt_tokens": 100, "completion_tokens": 4}}
                self.wfile.write(f"data: {json.dumps(usage)}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n")
            return None
        if type(self).fail_utility:
            return self._json(200, {"error": "synthetic utility failure"})
        if self.path == "/v1/embeddings":
            return self._json(200, {"data": [{"embedding": [0.1, 0.2]} for _ in body["input"]]})
        if self.path == "/v1/rerank":
            return self._json(200, {"results": [{"index": i, "relevance_score": 0.5}
                                                for i in range(len(body["documents"]))]})
        return self._json(404, {"error": "not found"})


@pytest.fixture
def server():
    _FakeServer.fail_chat = False
    _FakeServer.fail_utility = False
    _FakeServer.events = None
    _FakeServer.with_usage = True
    _FakeServer.seen = []
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _FakeServer)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture(autouse=True)
def _fake_environment(monkeypatch):
    monkeypatch.setattr(mod, "host_environment", lambda nodes: {
        "profile": "fallback", "profile_traits": {"synthetic_client": True}, "os": "test-client", "driver": None,
    })
    monkeypatch.setattr(mod, "_quiet", lambda cmd: None)


def test_api_root_strips_v1():
    assert mod.api_root("http://h:8080/v1/") == "http://h:8080"
    assert mod.api_root("http://h:8080") == "http://h:8080"


def test_run_chat_streams_and_uses_server_usage(server):
    r = mod.run_chat(server, "m", "hi", 16, seed=1)
    assert r["ok"] and r["text"] == "Hello there friend 42"
    assert r["prompt_tokens"] == 100 and r["completion_tokens"] == 4
    assert r["usage_source"] == "server"
    body = _FakeServer.seen[-1][1]
    assert body["temperature"] == 0 and body["seed"] == 1 and body["stream"] is True


def test_run_chat_counts_chunks_without_usage(server):
    _FakeServer.with_usage = False
    r = mod.run_chat(server, "m", "hi", 16, seed=1)
    assert r["completion_tokens"] == 4 and r["usage_source"] == "chunks"


def test_run_chat_records_http_errors(server):
    _FakeServer.fail_chat = True
    r = mod.run_chat(server, "m", "hi", 16, seed=1)
    assert not r["ok"] and "HTTPError" in r["error"]


def test_summarize_error_rate_and_throughput():
    results = [
        {"ok": True, "ttft_s": 0.1, "prefill_tps": 1000.0, "decode_tps": 50.0, "completion_tokens": 10},
        {"ok": False, "error": "x"},
    ]
    s = mod.summarize(results, wall_s=2.0)
    assert s["error_rate"] == 0.5 and s["throughput_tps"] == 5.0 and s["first_error"] == "x"


def test_shared_prefix_only_for_w2():
    w2 = mod.chat_prompts(mod.WORKLOADS["W2"], 3, seed=7, prompt_tokens=50)
    w1 = mod.chat_prompts(mod.WORKLOADS["W1"], 3, seed=7, prompt_tokens=50)
    assert len({p.split("\n\n")[0] for p in w2}) == 1
    assert len({p.split("\n\n")[0] for p in w1}) == 3


def test_main_w1_writes_result(server, tmp_path):
    rc = mod.main([
        "--base-url", f"{server}/v1", "--workload", "W1", "--model", "m",
        "--engine", "fake", "--engine-version", "0", "--prompt-tokens", "20",
        "--concurrency", "1", "2", "--requests", "2", "--out-dir", str(tmp_path),
    ])
    assert rc == 0
    record = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert [lvl["concurrency"] for lvl in record["result"]["levels"]] == [1, 2]
    assert record["result"]["levels"][0]["errors"] == 0


def test_main_w1_returns_nonzero_on_errors(server, tmp_path):
    _FakeServer.fail_chat = True
    rc = mod.main([
        "--base-url", server, "--workload", "W1", "--model", "m", "--engine", "fake",
        "--engine-version", "0", "--prompt-tokens", "20", "--requests", "2", "--warmup", "0",
        "--out-dir", str(tmp_path),
    ])
    assert rc == 1


def test_main_w4_embeddings_and_rerank(server, tmp_path):
    rc = mod.main([
        "--base-url", server, "--workload", "W4", "--model", "m", "--embed-model", "e",
        "--rerank-model", "r", "--engine", "fake", "--engine-version", "0", "--requests", "2",
        "--out-dir", str(tmp_path),
    ])
    assert rc == 0
    result = json.loads(next(tmp_path.glob("*.json")).read_text())["result"]
    assert result["embedding"]["errors"] == 0 and result["rerank"]["errors"] == 0
    assert result["embedding"]["items_per_s"] > 0
    assert "chat_ttft_after_s" in result


def test_quality_set_grading(server, tmp_path):
    qs = tmp_path / "q.jsonl"
    qs.write_text(
        json.dumps({"id": "a", "prompt": "p", "expect": ["42"]}) + "\n"
        + json.dumps({"id": "b", "prompt": "p", "expect": ["absent"]}) + "\n"
    )
    rc = mod.main([
        "--base-url", server, "--workload", "W1", "--model", "m", "--engine", "fake",
        "--engine-version", "0", "--prompt-tokens", "20", "--requests", "1",
        "--concurrency", "1", "--quality-set", str(qs), "--out-dir", str(tmp_path),
    ])
    assert rc == 0
    quality = json.loads(next(tmp_path.glob("*.json")).read_text())["quality"]
    assert quality["pass_rate"] == 0.5
    assert quality["method"] == "substring-smoke" and quality["sha256"] == mod.hashlib.sha256(qs.read_bytes()).hexdigest()


def test_smoke_eval_set_is_valid():
    path = REPO_ROOT / "integrations/inference-stacks/eval/smoke.jsonl"
    items = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    assert items and all({"id", "prompt", "expect"} <= set(i) for i in items)
    assert len({i["id"] for i in items}) == len(items)


def _args(server, out, workload="W1"):
    args = ["--base-url", server, "--workload", workload, "--engine", "fake", "--engine-version", "test-v1",
            "--requests", "1", "--out-dir", str(out)]
    return args + (["--embed-model", "embed", "--rerank-model", "rank"] if workload == "W4" else
                   ["--model", "chat", "--prompt-tokens", "20", "--warmup", "0"])


def _metadata():
    # Entirely synthetic evidence, including its claimed observation, for contract tests.
    return {
        "system_id": "test-system", "deployment_id": "test-deployment", "config_id": "test-config",
        "model_family": "test-model", "model_revision": "test-revision", "artifact_id": "test-artifact",
        "tokenizer_id": "test-tokenizer", "chat_template_id": "test-template",
        "context_tokens": 100, "engine_slots": 1, "compute_backend": "test-backend", "compute_precision": "test-precision",
        "speculation": {"method": "none"},
        "server": {"profile": "fallback", "traits": {"synthetic_server": True}, "os": "test-server", "observation": "real"},
        "utilities": {role: {"model_family": "test-utility", "model_revision": "test-revision", "artifact_id": role,
                             "quant": "test-quant", "engine": "fake", "engine_version": "test-v1"}
                      for role in ("embedding", "rerank")},
    }


def _ready_args(server, tmp_path, workload="W1"):
    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps(_metadata()))
    return _args(server, tmp_path / "out", workload) + [
        "--metadata", str(metadata), "--server-location", "remote", "--quant", "test-quant",
        "--model-file", "test-file", "--reasoning-mode", "disabled",
    ]


def _record(out):
    return mod.read_result(next(out.glob("*.json")))


def test_current_contract_and_remote_server_identity(server, tmp_path):
    assert mod.main(_ready_args(server, tmp_path)) == 0
    record = _record(tmp_path / "out")
    assert record["schema_version"] == 1 and record["method_version"] == "finite-v2"
    assert record["run_status"] == "complete" and record["comparison"] == {"status": "ready", "issues": []}
    env = record["environment"]
    assert env["os"] == "test-server" and env["client"]["os"] == "test-client"
    assert env["profile_traits"] == {"synthetic_server": True}
    params = record["parameters"]
    assert params["concurrency"] == [1] and params["requests_per_level"] == [1]
    assert params["max_tokens"] == mod.WORKLOADS["W1"]["max_tokens"]
    assert params["temperature"] == 0 and params["top_p"] == 1 and params["prompt_tokens_target"] == 20
    memory = record["result"]["levels"][0]["memory"]["metrics"]
    assert all(v["value"] is None and v["missing_reason"] == "server is not confirmed local" for v in memory.values())


def test_unconfirmed_loopback_does_not_inherit_client(server, tmp_path):
    assert mod.main(_args(server, tmp_path)) == 0
    r = _record(tmp_path)
    assert r["environment"]["profile"] == "unknown"
    assert r["environment"]["profile_traits"] == {} and r["environment"]["os"] is None
    assert r["comparison"]["status"] == "incomplete"


def test_confirmed_local_server_uses_host_observation(server, tmp_path, monkeypatch):
    monkeypatch.setattr(mod.MemorySampler, "sample", lambda self: None)
    assert mod.main(_args(server, tmp_path) + ["--server-location", "local"]) == 0
    env = _record(tmp_path)["environment"]
    assert env["profile_traits"] == {"synthetic_client": True} and env["hardware_observation"] == "real"


def test_same_timestamp_produces_unique_atomic_results(server, tmp_path, monkeypatch):
    original = mod.environment
    monkeypatch.setattr(mod, "environment", lambda args: {**original(args), "timestamp": "2026-01-01T00:00:00+00:00"})
    for _ in range(2):
        assert mod.main(_args(server, tmp_path)) == 0
    paths = list(tmp_path.glob("*.json"))
    assert len(paths) == 2 and len({mod.read_result(p)["run_id"] for p in paths}) == 2
    assert not list(tmp_path.glob("*.tmp"))
    prompts = [body["messages"][0]["content"] for _, body in _FakeServer.seen]
    assert len(set(prompts)) == 2


def test_long_labels_do_not_exceed_filename_limit(server, tmp_path):
    assert mod.main(_args(server, tmp_path) + ["--engine", "engine" * 30, "--model", "模型" * 50,
                                             "--quant", "quant" * 30]) == 0
    path = next(tmp_path.glob("*.json"))
    assert path.name.isascii() and len(path.name.encode()) < 255
    assert _record(tmp_path)["environment"]["model"] == "模型" * 50


@pytest.mark.parametrize("workload", ["W1", "W4"])
def test_interruption_retains_partial_observation(server, tmp_path, monkeypatch, workload):
    if workload == "W1":
        def partial(futures):
            yield futures[0]
            raise KeyboardInterrupt
        monkeypatch.setattr(mod, "as_completed", partial)
    else:
        original = mod.validate_utility
        calls = 0
        def partial(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise KeyboardInterrupt
            return original(*args)
        monkeypatch.setattr(mod, "validate_utility", partial)
    args = _args(server, tmp_path, workload) + ["--requests", "3"]
    assert mod.main(args) == 130
    r = _record(tmp_path)
    assert r["run_status"] == "interrupted" and r["comparison"]["status"] == "incomplete"
    summary = r["result"]["levels"][0] if workload == "W1" else r["result"]["embedding"]
    assert summary["requests"] == 1 and summary["unfinished_requests"] == 2


def test_checkpoint_exists_before_requests_and_failure_is_saved(server, tmp_path, monkeypatch):
    def fail(*args):
        initial = _record(tmp_path)
        assert initial["run_status"] == "running" and initial["result"] == {}
        raise RuntimeError("synthetic failure")
    monkeypatch.setattr(mod, "run_chat_workload", fail)
    assert mod.main(_args(server, tmp_path)) == 1
    assert _record(tmp_path)["run_status"] == "failed"


def test_atomic_replacement_failure_preserves_last_checkpoint(tmp_path, monkeypatch):
    path = tmp_path / "result.json"
    record = {"environment": {}, "result": {}}
    mod.write_result(path, record)
    before = path.read_bytes()
    def fail(*args):
        raise OSError("synthetic disk failure")
    monkeypatch.setattr(mod.os, "replace", fail)
    with pytest.raises(OSError, match="synthetic disk failure"):
        mod.write_result(path, {**record, "extra": True})
    assert path.read_bytes() == before and not list(tmp_path.glob("*.tmp"))


def test_w4_errors_set_exit_status_and_failed_time_counts(server, tmp_path):
    _FakeServer.fail_utility = True
    assert mod.main(_args(server, tmp_path, "W4")) == 1
    r = _record(tmp_path)
    assert r["run_status"] == "failed"
    for role in ("embedding", "rerank"):
        assert r["result"][role]["errors"] == 1 and r["result"][role]["items_per_s"] == 0
    summary = mod.summarize_utility([(1.0, None), (3.0, "failure")], batch=32)
    assert summary["items_per_s"] == 8 and summary["wall_s"] == 4 and summary["error_rate"] == 0.5


def test_w4_provenance_and_chat_probe_failure(server, tmp_path):
    args = _ready_args(server, tmp_path, "W4")
    assert mod.main(args) == 0
    assert _record(tmp_path / "out")["comparison"]["status"] == "ready"
    _FakeServer.fail_chat = True
    assert mod.main(args + ["--model", "chat", "--out-dir", str(tmp_path / "failed")]) == 1
    r = _record(tmp_path / "failed")
    assert r["result"]["embedding"]["errors"] == 0 and r["run_status"] == "failed"
    assert r["result"]["residency_verified"] is False


def test_setup_failure_remains_failed_after_successful_workload(server, tmp_path, monkeypatch):
    original = mod._chat
    calls = 0
    def chat(*args):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"ok": False, "error": "synthetic warmup failure", "total_s": 0.1}
        return original(*args)
    monkeypatch.setattr(mod, "_chat", chat)
    assert mod.main(_args(server, tmp_path) + ["--warmup", "1"]) == 1
    record = _record(tmp_path)
    assert record["result"]["levels"][0]["errors"] == 0 and record["run_status"] == "failed"


def test_missing_server_completion_usage_blocks_comparison(server, tmp_path):
    _FakeServer.with_usage = False
    assert mod.main(_ready_args(server, tmp_path)) == 0
    record = _record(tmp_path / "out")
    assert record["comparison"]["status"] == "incomplete"
    assert any("estimated" in issue for issue in record["comparison"]["issues"])


def test_partial_prompt_accounting_is_not_complete_evidence(server, tmp_path):
    assert mod.main(_ready_args(server, tmp_path)) == 0
    record = _record(tmp_path / "out")
    level = record["result"]["levels"][0]
    level["prompt_tokens_samples"] = 0
    assert any("prompt token accounting" in issue for issue in mod.evidence_issues(record))


@pytest.mark.parametrize("kind,payload", [
    ("embedding", {"data": []}),
    ("embedding", {"data": [{"embedding": [float("nan")]}]}),
    ("embedding", {"data": [{"embedding": [True]}]}),
    ("embedding", {"data": [{"embedding": []}]}),
    ("embedding", {"data": [{"embedding": [1], "index": 3}]}),
    ("rerank", {"results": [{"index": 0, "relevance_score": "0.5"}]}),
    ("rerank", {"results": [{"index": 1, "relevance_score": 0.5}]}),
])
def test_invalid_utility_responses(kind, payload):
    with pytest.raises(ValueError):
        mod.validate_utility(payload, kind, 1)


def test_utility_duplicate_indices_and_dimensions():
    with pytest.raises(ValueError, match="duplicate"):
        mod.validate_utility({"results": [{"index": 0, "relevance_score": 0.5}] * 2}, "rerank", 2)
    with pytest.raises(ValueError, match="dimensions"):
        mod.validate_utility({"data": [{"embedding": [1]}, {"embedding": [1, 2]}]}, "embedding", 2)


def test_stream_usage_and_early_eof(server):
    content = {"choices": [{"delta": {"content": "ok"}}]}
    _FakeServer.events = [content]
    assert not mod.run_chat(server, "m", "p", 8, 1)["ok"]
    _FakeServer.events = [content, {"usage": {"prompt_tokens": 8}}, "[DONE]"]
    result = mod.run_chat(server, "m", "p", 8, 1)
    assert result["ok"] and result["usage_source"] == "chunks"
    assert mod.summarize([result], 1)["usage_source"] == "chunks"


def test_reasoning_visible_latency_and_sampling(server):
    _FakeServer.events = [
        {"choices": [{"delta": {"reasoning_content": "reason"}}]},
        {"choices": [{"delta": {"content": "answer"}, "finish_reason": "stop"}]},
        {"usage": {"completion_tokens": 2, "prompt_tokens": 8,
                   "prompt_tokens_details": {"cached_tokens": 0}, "completion_tokens_details": {"reasoning_tokens": 1}}},
        "[DONE]",
    ]
    r = mod.run_chat(server, "m", "p", 8, 1, temperature=0.6, top_p=0.9,
                     chat_options={"chat_template_kwargs": {"enable_thinking": True}})
    assert r["text"] == "answer" and r["visible_ttft_s"] >= r["ttft_s"]
    assert r["cached_tokens"] == 0 and r["reasoning_tokens"] == 1
    body = _FakeServer.seen[-1][1]
    assert body["temperature"] == 0.6 and body["top_p"] == 0.9 and body["chat_template_kwargs"]["enable_thinking"]


def test_repeat_fingerprint_does_not_pool_different_conditions(server, tmp_path):
    assert mod.main(_ready_args(server, tmp_path)) == 0
    r = _record(tmp_path / "out")
    baseline = mod.comparison_fingerprint(r)
    same = copy.deepcopy(r)
    same["run_id"] = str(mod.uuid.uuid4())
    same["environment"]["timestamp"] = "different timestamp"
    same["environment"]["client"]["os"] = "different client"
    same["parameters"]["memory_pid"] = 999
    assert mod.comparison_fingerprint(same) == baseline
    for group, key, value in [
        ("parameters", "prompt_tokens_target", 40), ("parameters", "temperature", 0.6),
        ("provenance", "context_tokens", 200), ("provenance", "engine_slots", 2),
        ("provenance", "config_id", "other"), ("environment", "quant", "other"),
    ]:
        changed = copy.deepcopy(r)
        changed[group][key] = value
        assert mod.comparison_fingerprint(changed) != baseline
    r["result"]["levels"][0]["usage_source"] = "chunks"
    with pytest.raises(ValueError, match="estimated"):
        mod.comparison_fingerprint(r)


def test_legacy_and_malformed_results_are_not_comparable(tmp_path):
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps({"environment": {}, "result": {}, "comparison": {"status": "ready"}}))
    legacy = mod.read_result(path)
    assert legacy["schema_version"] == 0 and legacy["comparison"]["status"] == "incomplete"
    with pytest.raises(ValueError, match="legacy"):
        mod.comparison_fingerprint(legacy)
    for value in (2, True, "1"):
        path.write_text(json.dumps({"schema_version": value, "environment": {}, "result": {}}))
        with pytest.raises(ValueError, match="unsupported schema"):
            mod.read_result(path)


@pytest.mark.parametrize("group,key,value", [
    ("provenance", "utilities", []), ("provenance", "speculation", None),
    ("result", "levels", [None]), ("parameters", "concurrency", [None]),
    ("result", "setup", [None]), ("result", "levels", []),
])
def test_malformed_nested_evidence_is_incomplete(server, tmp_path, group, key, value):
    assert mod.main(_ready_args(server, tmp_path)) == 0
    r = _record(tmp_path / "out")
    r[group][key] = value
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(r))
    assert mod.read_result(path)["comparison"]["status"] == "incomplete"


@pytest.mark.parametrize("extra", [
    ["--requests", "0"], ["--concurrency", "-1"], ["--concurrency", "1", "1"],
    ["--timeout", "nan"], ["--top-p", "0"], ["--temperature", "-1"],
    ["--chat-options", '{"model":"override"}'], ["--chat-options", "[]"],
    ["--chat-options", '{"x":1e999}'], ["--pid", "1"], ["--measure-cold-start", "--swap-from", "m"],
    ["--base-url", "https://user:password@example.invalid"],
    ["--base-url", "https://example.invalid", "--server-location", "local"],
])
def test_invalid_inputs_fail_before_requests(server, tmp_path, extra):
    with pytest.raises(SystemExit) as exc:
        mod.main(_args(server, tmp_path) + extra)
    assert exc.value.code == 2 and not _FakeServer.seen and not list(tmp_path.glob("*.json"))


@pytest.mark.parametrize("value", [[], {"context_tokens": 0}, {"server": {"traits": []}},
                                  {"utilities": {"embedding": None}}, {"evidence_links": [{}]}])
def test_invalid_metadata_fails_before_requests(server, tmp_path, value):
    path = tmp_path / "metadata.json"
    path.write_text(json.dumps(value))
    with pytest.raises(SystemExit) as exc:
        mod.main(_args(server, tmp_path / "out") + ["--metadata", str(path)])
    assert exc.value.code == 2 and not _FakeServer.seen and not (tmp_path / "out").exists()


def test_evidence_links_must_match_deployment_and_config(tmp_path):
    path = tmp_path / "metadata.json"
    data = _metadata()
    link = {"kind": "parity", "run_id": "test-run", "file": "test-parity.json",
            "deployment_id": data["deployment_id"], "config_id": data["config_id"]}
    data["evidence_links"] = [link]
    path.write_text(json.dumps(data))
    assert mod.load_metadata(path)["evidence_links"] == [link]
    link["config_id"] = "other-config"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="does not match"):
        mod.load_metadata(path)


def test_memory_unavailable_is_not_zero_and_zero_minimum_is_preserved(monkeypatch):
    meminfo = "MemAvailable: 0 kB\n"
    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: io.StringIO(meminfo))
    monkeypatch.setattr(mod, "_quiet", lambda cmd: "N/A\n" if cmd[0] == "nvidia-smi" else "2048")
    sampler = mod.MemorySampler(pid=42)
    sampler.sample()
    assert sampler.peak_gpu_mb is None and sampler.peak_rss_mb == 2
    meminfo = "MemAvailable: 1048576 kB\n"
    sampler.sample()
    assert sampler.min_mem_available_gb == 0
    sampler._halt.set()
    sampler.start()
    report = sampler.stop()["memory"]["metrics"]
    assert report["peak_gpu_mb"]["missing_reason"] == "no valid samples"
    assert report["min_mem_available_gb"]["samples"] == 2
    assert report["peak_rss_mb"]["unit"] == "MiB" and report["peak_rss_mb"]["scope"] == "PID 42"
