"""Tests for bench-inference.py against a local fake OpenAI-compatible server."""

import importlib.util
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
            for word in ["Hello", " there", " friend", " 42"]:
                chunk = {"choices": [{"delta": {"content": word}}]}
                self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            if type(self).with_usage:
                usage = {"choices": [], "usage": {"prompt_tokens": 100, "completion_tokens": 4}}
                self.wfile.write(f"data: {json.dumps(usage)}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n")
            return None
        if self.path == "/v1/embeddings":
            return self._json(200, {"data": [{"embedding": [0.1, 0.2]} for _ in body["input"]]})
        if self.path == "/v1/rerank":
            return self._json(200, {"results": [{"index": i, "relevance_score": 0.5}
                                                for i in range(len(body["documents"]))]})
        return self._json(404, {"error": "not found"})


@pytest.fixture
def server():
    _FakeServer.fail_chat = False
    _FakeServer.with_usage = True
    _FakeServer.seen = []
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _FakeServer)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture(autouse=True)
def _fake_environment(monkeypatch):
    monkeypatch.setattr(mod, "environment", lambda args: {
        "timestamp": "2026-10-27T00:00:00+00:00", "profile": "fallback", "engine": args.engine,
    })


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


def test_smoke_eval_set_is_valid():
    path = REPO_ROOT / "integrations/inference-stacks/eval/smoke.jsonl"
    items = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    assert items and all({"id", "prompt", "expect"} <= set(i) for i in items)
    assert len({i["id"] for i in items}) == len(items)
