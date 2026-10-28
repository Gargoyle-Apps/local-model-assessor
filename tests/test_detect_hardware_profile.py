"""Tests for detect-hardware-profile.py (synthetic signals, no hardware access)."""

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

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


mod = _load_script("detect-hardware-profile.py")


@pytest.mark.parametrize("brand, expected", [
    ("Apple M1", {"generation": 1, "tier": "base"}),
    ("Apple M4 Max", {"generation": 4, "tier": "Max"}),
    ("Apple M5 Pro", {"generation": 5, "tier": "Pro"}),
    ("Intel(R) Core(TM) i9", None),
])
def test_parse_apple_chip(brand, expected):
    assert mod.parse_apple_chip(brand) == expected


def test_parse_nvidia_smi_treats_na_memory_as_unavailable():
    gpus = mod.parse_nvidia_smi("NVIDIA GB10, [N/A], 12.1, 580.173.02\n")
    assert gpus == [{"name": "NVIDIA GB10", "memory_mb": None, "compute_cap": "12.1", "driver": "580.173.02"}]


def test_parse_meminfo_total_gb():
    assert mod.parse_meminfo_total_gb("MemTotal:       127604576 kB\nMemFree: 1 kB\n") == 121.7


@pytest.mark.parametrize("mem, profile", [
    (8, "mac-16-24"), (16, "mac-16-24"), (24, "mac-16-24"),
    (32, "mac-32-64"), (48, "mac-32-64"), (64, "mac-32-64"),
    (96, "mac-96plus"), (128, "mac-96plus"), (512, "mac-96plus"),
])
def test_mac_memory_tiers(mem, profile):
    result = mod.classify({"os": "darwin", "arch": "arm64", "chip": "Apple M3 Max", "memory_gb": mem})
    assert result["profile"] == profile


def test_mac_below_tier_warns():
    result = mod.classify({"os": "darwin", "arch": "arm64", "chip": "Apple M2", "memory_gb": 8})
    assert any("below" in w for w in result["warnings"])


def test_m5_prefill_trait():
    m5 = mod.classify({"os": "darwin", "arch": "arm64", "chip": "Apple M5 Pro", "memory_gb": 48})
    m4 = mod.classify({"os": "darwin", "arch": "arm64", "chip": "Apple M4 Pro", "memory_gb": 48})
    assert m5["traits"]["m5_prefill_path"] is True
    assert m4["traits"]["m5_prefill_path"] is False


def test_intel_mac_falls_back():
    result = mod.classify({"os": "darwin", "arch": "x86_64", "chip": "Intel(R) Core(TM) i9", "memory_gb": 64})
    assert result["profile"] == "fallback"


def _gb10_signals(memory_mb=None):
    return {
        "os": "linux", "arch": "aarch64", "memory_gb": 121.7,
        "nvidia_gpus": [{"name": "NVIDIA GB10", "memory_mb": memory_mb, "compute_cap": "12.1", "driver": "580.173.02"}],
    }


def test_gb10_detected_from_unified_memory():
    result = mod.classify(_gb10_signals())
    assert result["profile"] == "gb10"
    assert result["traits"]["unified_memory_gb"] == 121.7
    assert result["warnings"] == []


def test_gb10_x2_requires_explicit_nodes():
    assert mod.classify(_gb10_signals(), nodes=2)["profile"] == "gb10-x2"


def test_gb10_with_reported_memory_warns():
    result = mod.classify(_gb10_signals(memory_mb=122000.0))
    assert result["profile"] == "gb10"
    assert result["warnings"]


def test_sm121_without_name_still_gb10():
    signals = _gb10_signals()
    signals["nvidia_gpus"][0]["name"] = "NVIDIA Graphics Device"
    assert mod.classify(signals)["profile"] == "gb10"


def test_discrete_rtx():
    result = mod.classify({
        "os": "linux", "arch": "x86_64", "memory_gb": 62.7,
        "nvidia_gpus": [{"name": "NVIDIA GeForce RTX 4090", "memory_mb": 24564.0, "compute_cap": "8.9", "driver": "580.95"}],
    })
    assert result["profile"] == "nvidia-discrete"
    assert result["traits"]["vram_gb"] == 24.0


def test_multi_gpu_warns_and_sizes_largest():
    result = mod.classify({
        "os": "linux", "arch": "x86_64", "memory_gb": 128.0,
        "nvidia_gpus": [
            {"name": "NVIDIA GeForce RTX 3090", "memory_mb": 24576.0, "compute_cap": "8.6", "driver": "580.95"},
            {"name": "NVIDIA GeForce RTX 5090", "memory_mb": 32607.0, "compute_cap": "12.0", "driver": "580.95"},
        ],
    })
    assert result["traits"]["gpu"] == "NVIDIA GeForce RTX 5090"
    assert result["warnings"]


@pytest.mark.parametrize("signals", [
    {"os": "linux", "arch": "x86_64", "memory_gb": 64, "nvidia_gpus": []},
    {"os": "linux", "arch": "aarch64", "memory_gb": 480,
     "nvidia_gpus": [{"name": "NVIDIA GH200 480GB", "memory_mb": 97871.0, "compute_cap": "9.0", "driver": "580"}]},
    {"os": "windows", "arch": "amd64"},
])
def test_out_of_scope_falls_back(signals):
    assert mod.classify(signals)["profile"] == "fallback"


def test_profile_ids_match_profiles_yaml():
    data = yaml.safe_load((REPO_ROOT / "integrations/inference-stacks/profiles.yaml").read_text())
    assert set(data["profiles"]) == set(mod.PROFILE_IDS)
