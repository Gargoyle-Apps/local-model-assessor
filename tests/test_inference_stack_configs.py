"""Structural checks for the inference-stack profiles and reference llama-swap configs."""

from pathlib import Path

import pytest
import yaml

STACKS = Path(__file__).resolve().parent.parent / "integrations" / "inference-stacks"
SWAP_CONFIGS = sorted(STACKS.glob("configs/*/llama-swap*.yaml"))


def _load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_swap_configs_found():
    assert len(SWAP_CONFIGS) >= 4


@pytest.mark.parametrize("path", SWAP_CONFIGS, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_group_members_are_defined_models(path):
    cfg = _load(path)
    models = set(cfg["models"])
    groups = cfg["routing"]["router"]["settings"]["groups"]
    members = [m for g in groups.values() for m in g["members"]]
    assert set(members) <= models
    assert len(members) == len(set(members)), "a model can belong to only one group"
    assert set(cfg.get("hooks", {}).get("on_startup", {}).get("preload", [])) <= models


@pytest.mark.parametrize("path", SWAP_CONFIGS, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_every_model_has_a_cmd_and_docker_models_stop_cleanly(path):
    for name, model in _load(path)["models"].items():
        assert model.get("cmd"), name
        if "docker run" in model["cmd"] or "${docker_gpu}" in model["cmd"]:
            assert model.get("cmdStop") == "docker stop ${MODEL_ID}", name


def test_routing_rules_reference_known_profiles_and_workloads():
    data = _load(STACKS / "profiles.yaml")
    assert set(data["routing"]["rules"]) <= set(data["profiles"])
    workloads = set(data["workloads"]) | {"default"}
    for profile, rules in data["routing"]["rules"].items():
        assert set(rules) <= workloads, profile
        for rule in rules.values():
            assert rule.get("status", "hypothesis") in {"hypothesis", "measured"}


def test_no_rule_claims_measured_without_results():
    data = _load(STACKS / "profiles.yaml")
    measured = [r for rules in data["routing"]["rules"].values() for r in rules.values()
                if r.get("status") == "measured"]
    for rule in measured:
        assert rule.get("evidence"), "measured rules must cite their results run"
