#!/usr/bin/env python3
"""Resolve LMA artifact paths for standalone use or an optional LMO sidecar.

LMA works without Local Model Orchestrator (LMO). When both clones are local,
agents pass absolute paths (env or gitignored integrations/lmo/paths.yaml).

Resolution order per artifact (first hit wins):

1. Explicit env (must exist if set): LMA_DB, LMA_HARDWARE_PROFILE, LMA_SOFTWARE_PROFILE
2. integrations/lmo/paths.yaml keys (relative to lmo_root unless absolute)
3. LMO_ROOT + conventional inventory/ filenames (skip if the file is absent)
4. Repo-local computer-profile/*.yaml or model-data/model-assessor.db
5. Tracked templates (hardware/software only)

LMA_ROOT overrides the LMA clone root (default: parent of scripts/).
LMO_ROOT is the LMO clone root. It does not change LMA ownership of the model DB.
Profiles declaring mock/dry-run inventory require --allow-mock or
LMA_ALLOW_MOCK=1. Resolved output preserves their mock status.

CLI (from repo root):
  ./scripts/py scripts/lma_paths.py
  ./scripts/py scripts/lma_paths.py --format json
  ./scripts/py scripts/lma_paths.py --format env
  ./scripts/py scripts/lma_paths.py --allow-mock --format json
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:  # pragma: no cover - bootstrap tells the user
    yaml = None  # type: ignore[assignment]

LMO_HARDWARE_RELATIVE = Path("inventory") / "hardware-profile.yaml"
LMO_SOFTWARE_RELATIVE = Path("inventory") / "software-profile.yaml"
LINK_RELATIVE = Path("integrations") / "lmo" / "paths.yaml"


@dataclass(frozen=True)
class ResolvedPath:
    path: Optional[Path]
    source: str  # env | lmo-link | lmo-root | local | template | missing
    mock: bool = False
    profile_mode: Optional[str] = None

    def as_str(self) -> str:
        return str(self.path) if self.path is not None else ""


class PathResolutionError(FileNotFoundError):
    """An explicit override was set but the file is missing."""


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}
_MOCK_MODES = {"dry_run", "dry-run", "mock", "simulated"}


def mock_profiles_allowed(explicit: Optional[bool] = None) -> bool:
    """Return whether mock profiles may be consumed for this operation."""
    if explicit is not None:
        return explicit
    raw = os.environ.get("LMA_ALLOW_MOCK")
    if raw is None:
        return False
    normalized = raw.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise PathResolutionError(
        "LMA_ALLOW_MOCK must be one of: 1, true, yes, on, 0, false, no, off"
    )


def lma_root() -> Path:
    raw = os.environ.get("LMA_ROOT")
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


def lmo_root() -> Optional[Path]:
    raw = os.environ.get("LMO_ROOT")
    if raw:
        return Path(raw).expanduser().resolve()
    link = _load_link()
    if link and link.get("lmo_root"):
        return Path(str(link["lmo_root"])).expanduser().resolve()
    return None


def _link_file() -> Path:
    return lma_root() / LINK_RELATIVE


def _load_link() -> dict:
    path = _link_file()
    if not path.is_file():
        return {}
    if yaml is None:
        print(
            "Warning: PyYAML missing; ignoring integrations/lmo/paths.yaml. "
            "Run ./scripts/bootstrap-python.sh",
            file=sys.stderr,
        )
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        print(f"Warning: could not read {path} ({exc})", file=sys.stderr)
        return {}
    return data if isinstance(data, dict) else {}


def _resolve_declared(value: str, *, base: Optional[Path]) -> Path:
    p = Path(value).expanduser()
    if p.is_absolute():
        return p.resolve()
    if base is None:
        raise PathResolutionError(
            f"Relative path {value!r} needs lmo_root in paths.yaml or LMO_ROOT"
        )
    return (base / p).resolve()


def _existing_file(path: Path) -> Optional[Path]:
    return path if path.is_file() else None


def _resolved_profile(
    path: Path, source: str, *, allow_mock: Optional[bool]
) -> ResolvedPath:
    """Annotate a profile and require explicit opt-in for simulated inventory."""
    mode: Optional[str] = None
    is_mock = False
    if yaml is None:
        raise PathResolutionError(
            "PyYAML is required to inspect profiles. Run ./scripts/bootstrap-python.sh"
        )
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise PathResolutionError(f"could not read profile {path}: {exc}") from exc

    if isinstance(data, dict) and isinstance(data.get("profile"), dict):
        profile = data["profile"]
        raw_mode = profile.get("mode")
        if raw_mode is not None:
            mode = str(raw_mode)
        is_mock = (
            profile.get("mock") is True
            or (mode is not None and mode.lower() in _MOCK_MODES)
            or profile.get("physical_hardware_present") is False
        )

    if is_mock and not mock_profiles_allowed(allow_mock):
        raise PathResolutionError(
            f"mock profile requires explicit opt-in: {path}. "
            "Pass --allow-mock to lma_paths.py or set LMA_ALLOW_MOCK=1 "
            "for commands that consume profiles."
        )
    return ResolvedPath(path, source, mock=is_mock, profile_mode=mode)


def db_path() -> ResolvedPath:
    raw = os.environ.get("LMA_DB")
    if raw:
        path = Path(raw).expanduser().resolve()
        if not path.is_file():
            raise PathResolutionError(f"LMA_DB is set but not a file: {path}")
        return ResolvedPath(path, "env")
    default = lma_root() / "model-data" / "model-assessor.db"
    found = _existing_file(default)
    if found:
        return ResolvedPath(found, "local")
    return ResolvedPath(default, "missing")


def require_db_path() -> Path:
    """Return the resolved existing DB path or raise a user-facing error."""
    resolved = db_path()
    if resolved.path is None or not resolved.path.is_file():
        raise PathResolutionError(
            f"model DB not found at {resolved.path or '(unset)'}. Run ./scripts/init-db.sh first."
        )
    return resolved.path


def _profile(
    *,
    env_name: str,
    link_key: str,
    conventional: Path,
    local_name: str,
    template_name: str,
    allow_mock: Optional[bool],
) -> ResolvedPath:
    raw = os.environ.get(env_name)
    if raw:
        p = Path(raw).expanduser().resolve()
        if not p.is_file():
            raise PathResolutionError(f"{env_name} is set but not a file: {p}")
        return _resolved_profile(p, "env", allow_mock=allow_mock)

    link = _load_link()
    if link.get(link_key):
        root = None
        if os.environ.get("LMO_ROOT"):
            root = Path(os.environ["LMO_ROOT"]).expanduser().resolve()
        elif link.get("lmo_root"):
            root = Path(str(link["lmo_root"])).expanduser().resolve()
        declared = _resolve_declared(str(link[link_key]), base=root)
        if not declared.is_file():
            raise PathResolutionError(
                f"integrations/lmo/paths.yaml {link_key} is set but not a file: {declared}"
            )
        return _resolved_profile(declared, "lmo-link", allow_mock=allow_mock)

    root = lmo_root()
    if root:
        candidate = _existing_file(root / conventional)
        if candidate:
            return _resolved_profile(candidate, "lmo-root", allow_mock=allow_mock)

    local = lma_root() / "computer-profile" / local_name
    found = _existing_file(local)
    if found:
        return _resolved_profile(found, "local", allow_mock=allow_mock)

    template = lma_root() / "computer-profile" / template_name
    found = _existing_file(template)
    if found:
        return _resolved_profile(found, "template", allow_mock=allow_mock)

    return ResolvedPath(None, "missing")


def hardware_profile_path(*, allow_mock: Optional[bool] = None) -> ResolvedPath:
    return _profile(
        env_name="LMA_HARDWARE_PROFILE",
        link_key="hardware_profile",
        conventional=LMO_HARDWARE_RELATIVE,
        local_name="hardware-profile.yaml",
        template_name="hardware-profile.template.yaml",
        allow_mock=allow_mock,
    )


def software_profile_path(*, allow_mock: Optional[bool] = None) -> ResolvedPath:
    return _profile(
        env_name="LMA_SOFTWARE_PROFILE",
        link_key="software_profile",
        conventional=LMO_SOFTWARE_RELATIVE,
        local_name="software-profile.yaml",
        template_name="software-profile.template.yaml",
        allow_mock=allow_mock,
    )


def describe(*, allow_mock: Optional[bool] = None) -> dict:
    allowed = mock_profiles_allowed(allow_mock)
    hw = hardware_profile_path(allow_mock=allowed)
    sw = software_profile_path(allow_mock=allowed)
    db = db_path()
    root = lmo_root()
    linked = hw.source in {"env", "lmo-link", "lmo-root"} or sw.source in {
        "env",
        "lmo-link",
        "lmo-root",
    }
    return {
        "lma_root": str(lma_root()),
        "lmo_root": str(root) if root else None,
        "linked": linked,
        "allow_mock": allowed,
        "db": {"path": db.as_str(), "source": db.source},
        "hardware_profile": {
            "path": hw.as_str(),
            "source": hw.source,
            "mock": hw.mock,
            "profile_mode": hw.profile_mode,
        },
        "software_profile": {
            "path": sw.as_str(),
            "source": sw.source,
            "mock": sw.mock,
            "profile_mode": sw.profile_mode,
        },
    }


def _print_text(info: dict) -> None:
    print(f"lma_root\t{info['lma_root']}")
    print(f"lmo_root\t{info['lmo_root'] or ''}")
    print(f"linked\t{str(info['linked']).lower()}")
    print(f"allow_mock\t{str(info['allow_mock']).lower()}")
    for key in ("db", "hardware_profile", "software_profile"):
        block = info[key]
        print(f"{key}\t{block['path']}\t{block['source']}")
        if key != "db":
            print(f"{key}_mock\t{str(block['mock']).lower()}")


def _print_env(info: dict) -> None:
    def assignment(name: str, value: str) -> None:
        print(f"{name}={shlex.quote(value)}")

    assignment("LMA_ROOT", info["lma_root"])
    if info["lmo_root"]:
        assignment("LMO_ROOT", info["lmo_root"])
    if info["allow_mock"]:
        assignment("LMA_ALLOW_MOCK", "1")
    if info["db"]["path"]:
        assignment("LMA_DB", info["db"]["path"])
    if info["hardware_profile"]["path"]:
        assignment("LMA_HARDWARE_PROFILE", info["hardware_profile"]["path"])
    if info["software_profile"]["path"]:
        assignment("LMA_SOFTWARE_PROFILE", info["software_profile"]["path"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Print resolved LMA/LMO artifact paths")
    parser.add_argument(
        "--allow-mock",
        action="store_true",
        default=None,
        help="allow profiles explicitly marked as mock/dry-run inventory",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json", "env"),
        default="text",
        help="text (default), json, or shell env assignments",
    )
    args = parser.parse_args()
    try:
        info = describe(allow_mock=args.allow_mock)
    except PathResolutionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if args.format == "json":
        json.dump(info, sys.stdout, indent=2)
        sys.stdout.write("\n")
    elif args.format == "env":
        _print_env(info)
    else:
        _print_text(info)
    return 0


if __name__ == "__main__":
    sys.exit(main())
