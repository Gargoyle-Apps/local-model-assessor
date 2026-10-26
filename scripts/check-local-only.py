#!/usr/bin/env python3
"""Reject tracked local artifacts, even when force-added or ignores drift.

Run via ./scripts/py scripts/check-local-only.py [--repo PATH].
Only Git metadata/path names are read; file contents and local data are not read.
"""

import argparse
import fnmatch
import os
from pathlib import Path
import subprocess
import sys


# Machine-readable counterpart of AGENTS.md / README's local-data policy.
# Keep these patterns and .gitignore aligned when local artifact paths change.
LOCAL_ONLY = (
    "computer-profile/hardware-profile.yaml",
    "computer-profile/software-profile.yaml",
    "model-data/*.db",
    "model-data/*.db-*",
    "model-data/assessed-models.md",
    "model-data/new-models.yaml",
    "model-data/model-lookup.json",
    "model-data/modelfile/*",
    "integrations/IDE-model-management/*/generated/*",
    "integrations/IDE-model-management/continue/config.yaml",
    "integrations/IDE-model-management/cline/provider-settings.json",
    "integrations/IDE-model-management/opencode/opencode.json",
    "integrations/IDE-model-management/goose/config.yaml",
    "integrations/IDE-model-management/pi/settings.json",
    "integrations/IDE-model-management/pi/models.json",
    "integrations/IDE-model-management/zed/settings.json",
    "integrations/embed-retrieval-stack/out/*",
    "integrations/mcp/scout/*",
    ".cursorrules", ".cursorignore", ".agents/*", ".continue/*", ".opencode/*",
    "opencode.json", "opencode.jsonc", ".venv/*", ".pytest_cache/*", "ref/*",
)
KEEP_FILES = (
    "model-data/modelfile/.gitkeep",
    "integrations/IDE-model-management/*/generated/.gitkeep",
    "integrations/mcp/scout/.gitkeep",
)


def git(repo, *args, input_bytes=None, allowed=(0,)):
    result = subprocess.run(
        ["git", "-C", str(repo), *args], input=input_bytes,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode not in allowed:
        raise RuntimeError(os.fsdecode(result.stderr).strip())
    return result.stdout


def violations(repo):
    """Return tracked paths and reasons using NUL-safe Git plumbing."""
    tracked = git(repo, "ls-files", "--cached", "-z")
    if not tracked:
        return {}
    # --no-index is essential: check-ignore otherwise skips tracked files.
    ignored = set(git(
        repo, "check-ignore", "--no-index", "-z", "--stdin",
        input_bytes=tracked, allowed=(0, 1),
    ).split(b"\0"))
    findings = {}
    for raw in tracked.split(b"\0"):
        if not raw:
            continue
        path = os.fsdecode(raw)
        reasons = []
        if raw in ignored:
            reasons.append("matches active ignore rules")
        if (any(fnmatch.fnmatchcase(path, p) for p in LOCAL_ONLY)
                and not any(fnmatch.fnmatchcase(path, p) for p in KEEP_FILES)):
            reasons.append("documented local-only path")
        if reasons:
            findings[path] = reasons
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    try:
        # Normalize to root so nested invocation cannot miss tracked paths.
        root = Path(os.fsdecode(git(args.repo, "rev-parse", "--show-toplevel")).strip())
        findings = violations(root)
    except (OSError, RuntimeError) as exc:
        print(f"Local-only check failed: {exc}", file=sys.stderr)
        return 2
    for path, reasons in sorted(findings.items()):
        print(f"ERROR {path!r}: {', '.join(reasons)}")
    if findings:
        return 1
    print("Local-only path check passed. Content review is still required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
