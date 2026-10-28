#!/usr/bin/env python3
"""Detect which inference-stack hardware profile the current machine matches.

Run via ./scripts/py scripts/detect-hardware-profile.py [--nodes 2] [--json].
Reads only local hardware signals (sysctl, system_profiler, uname, nvidia-smi,
/proc/meminfo). Profile IDs match integrations/inference-stacks/profiles.yaml.
The result describes the machine running the script, never a simulated target.
"""

import argparse
import json
import platform
import re
import shutil
import subprocess
import sys

PROFILE_IDS = (
    "mac-16-24",
    "mac-32-64",
    "mac-96plus",
    "gb10",
    "gb10-x2",
    "nvidia-discrete",
    "fallback",
)

# nvidia-smi prints these instead of a number when a field does not apply,
# e.g. memory.total on GB10, whose GPU has no dedicated framebuffer.
_UNAVAILABLE = {"[n/a]", "n/a", "not supported", "[not supported]", ""}


def _run(cmd):
    if not shutil.which(cmd[0]):
        return None
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout if out.returncode == 0 else None


def parse_apple_chip(brand):
    """'Apple M5 Pro' -> {'generation': 5, 'tier': 'Pro'}; None if not Apple M-series."""
    m = re.match(r"Apple M(\d+)(?:\s+(Pro|Max|Ultra))?", brand or "")
    if not m:
        return None
    return {"generation": int(m.group(1)), "tier": m.group(2) or "base"}


def parse_nvidia_smi(csv_text):
    """Parse `--query-gpu=name,memory.total,compute_cap,driver_version --format=csv,noheader,nounits`."""
    gpus = []
    for line in (csv_text or "").strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue
        name, mem, cap, driver = parts[:4]
        mem_mb = None if mem.lower() in _UNAVAILABLE else float(mem)
        gpus.append({"name": name, "memory_mb": mem_mb, "compute_cap": cap, "driver": driver})
    return gpus


def parse_meminfo_total_gb(text):
    m = re.search(r"^MemTotal:\s+(\d+)\s+kB", text or "", re.MULTILINE)
    return round(int(m.group(1)) / 2**20, 1) if m else None


def collect_signals():
    """Gather raw hardware signals from the current machine."""
    system = platform.system().lower()
    signals = {"os": system, "arch": platform.machine().lower()}
    if system == "darwin":
        signals["chip"] = (_run(["sysctl", "-n", "machdep.cpu.brand_string"]) or "").strip()
        memsize = (_run(["sysctl", "-n", "hw.memsize"]) or "").strip()
        signals["memory_gb"] = round(int(memsize) / 2**30) if memsize.isdigit() else None
        displays = _run(["system_profiler", "SPDisplaysDataType", "-json"])
        try:
            cores = json.loads(displays)["SPDisplaysDataType"][0].get("sppci_cores")
            signals["gpu_cores"] = int(cores) if cores else None
        except (TypeError, ValueError, KeyError, IndexError):
            signals["gpu_cores"] = None
    elif system == "linux":
        smi = _run([
            "nvidia-smi",
            "--query-gpu=name,memory.total,compute_cap,driver_version",
            "--format=csv,noheader,nounits",
        ])
        signals["nvidia_gpus"] = parse_nvidia_smi(smi) if smi else []
        try:
            with open("/proc/meminfo", encoding="utf-8") as fh:
                signals["memory_gb"] = parse_meminfo_total_gb(fh.read())
        except OSError:
            signals["memory_gb"] = None
    return signals


def _fallback(reason, signals):
    return {
        "profile": "fallback",
        "reasons": [reason],
        "warnings": [],
        "traits": {"os": signals.get("os"), "arch": signals.get("arch")},
    }


def classify(signals, nodes=1):
    """Map raw signals to a profile ID plus the traits that drove the choice."""
    os_name, arch = signals.get("os"), signals.get("arch")
    warnings = []

    if os_name == "darwin":
        chip = parse_apple_chip(signals.get("chip"))
        if arch != "arm64" or not chip:
            return _fallback("Intel or unknown Mac: out of scope", signals)
        mem = signals.get("memory_gb") or 0
        if mem >= 96:
            profile = "mac-96plus"
        elif mem > 24:
            profile = "mac-32-64"
            if mem > 64:
                warnings.append(f"{mem} GB sits between tiers; treated as mac-32-64")
        else:
            profile = "mac-16-24"
            if mem < 16:
                warnings.append(f"{mem} GB is below the mac-16-24 tier")
        return {
            "profile": profile,
            "reasons": [f"Apple M{chip['generation']} {chip['tier']}, {mem} GB unified memory"],
            "warnings": warnings,
            "traits": {
                "chip_generation": chip["generation"],
                "chip_tier": chip["tier"],
                "memory_gb": mem,
                "gpu_cores": signals.get("gpu_cores"),
                "m5_prefill_path": chip["generation"] >= 5,
            },
        }

    if os_name == "linux":
        gpus = signals.get("nvidia_gpus") or []
        if not gpus:
            return _fallback("No NVIDIA GPU found: AMD, Intel and CPU-only are out of scope", signals)
        gb10 = [
            g for g in gpus
            if "gb10" in g["name"].lower() or (g["compute_cap"] == "12.1" and g["memory_mb"] is None)
        ]
        if gb10:
            g = gb10[0]
            if nodes >= 2:
                profile = "gb10-x2"
            else:
                profile = "gb10"
                if g["memory_mb"] is not None:
                    warnings.append("nvidia-smi reported dedicated memory; GB10 normally reports N/A")
            return {
                "profile": profile,
                "reasons": [f"{g['name']} (compute capability {g['compute_cap']}), unified memory"],
                "warnings": warnings,
                "traits": {
                    "arch": arch,
                    "unified_memory_gb": signals.get("memory_gb"),
                    "compute_cap": g["compute_cap"],
                    "driver": g["driver"],
                    "nodes": max(nodes, 1),
                },
            }
        if arch not in ("x86_64", "amd64"):
            return _fallback(f"NVIDIA on {arch} without GB10: out of scope", signals)
        sized = [g for g in gpus if g["memory_mb"] is not None]
        if not sized:
            return _fallback("NVIDIA GPU without reported VRAM", signals)
        if len(gpus) > 1:
            warnings.append(f"{len(gpus)} GPUs found; multi-GPU servers are out of scope, sizing to the largest card")
        top = max(sized, key=lambda g: g["memory_mb"])
        return {
            "profile": "nvidia-discrete",
            "reasons": [f"{top['name']}, {round(top['memory_mb'] / 1024)} GB VRAM"],
            "warnings": warnings,
            "traits": {
                "arch": arch,
                "gpu": top["name"],
                "vram_gb": round(top["memory_mb"] / 1024, 1),
                "compute_cap": top["compute_cap"],
                "driver": top["driver"],
                "gpu_count": len(gpus),
                "system_memory_gb": signals.get("memory_gb"),
            },
        }

    return _fallback(f"{os_name or 'unknown'} is out of scope", signals)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nodes", type=int, default=1,
                        help="Linked GB10 nodes (2 selects gb10-x2; cannot be auto-detected)")
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    args = parser.parse_args()
    signals = collect_signals()
    result = classify(signals, nodes=args.nodes)
    result["signals"] = signals
    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    print(f"Profile: {result['profile']}")
    for reason in result["reasons"]:
        print(f"  because: {reason}")
    for warning in result["warnings"]:
        print(f"  warning: {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
