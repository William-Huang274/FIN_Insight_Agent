"""Deterministic contract tests for the one permitted candidate execution bridge."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from sec_agent.canonical_runtime.p01_g2_1_candidate_execution_bridge import bridge_gate_payload, bridge_manifest_payload, bridge_package_payload, bridge_preflight_payload, preflight_candidate_bound_execution, validate_execution_package


ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = {
    "inner_package": ROOT / "data/manifests/point01_m2_a1_candidate_bound_execution_package_manifest_v2_10.json",
    "inner_package_gate": ROOT / "data/manifests/point01_m2_a1_candidate_bound_execution_package_gate_v2_10.json",
    "plan": ROOT / "data/manifests/point01_m2_a1_candidate_bound_receipt_execution_plan_v2_10.json",
    "plan_gate": ROOT / "data/manifests/point01_m2_a1_candidate_bound_receipt_execution_plan_gate_v2_10.json",
    "blueprint": ROOT / "data/manifests/point01_m2_a1_candidate_bound_baseline_authority_blueprint_v2_10.json",
    "blueprint_gate": ROOT / "data/manifests/point01_m2_a1_candidate_bound_baseline_authority_blueprint_gate_v2_10.json",
    "manifest": ROOT / "data/manifests/point01_p01_g2_1_candidate_execution_bridge_manifest_v1_0.json",
    "package": ROOT / "data/manifests/point01_p01_g2_1_candidate_execution_bridge_package_v1_0.json",
    "preflight": ROOT / "data/manifests/point01_p01_g2_1_candidate_execution_bridge_preflight_v1_0.json",
    "gate": ROOT / "data/manifests/point01_p01_g2_1_candidate_execution_bridge_gate_v1_0.json",
}
CANDIDATE = {
    "manifest": ROOT / "data/manifests/point01_p01_g2_1_final_baseline_candidate_input_manifest_v1_0.json",
    "package": ROOT / "data/manifests/point01_p01_g2_1_final_baseline_candidate_package_v1_0.json",
    "preflight": ROOT / "data/manifests/point01_p01_g2_1_final_baseline_candidate_preflight_v1_0.json",
    "gate": ROOT / "data/manifests/point01_p01_g2_1_final_baseline_candidate_gate_v1_0.json",
}


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _all() -> tuple[dict[str, object], dict[str, object]]:
    return ({name: _load(path) for name, path in OUTPUTS.items()}, {name: _load(path) for name, path in CANDIDATE.items()})


def _validate(bridge: dict[str, object], candidate: dict[str, object]) -> dict[str, object]:
    return validate_execution_package(bridge["package"], manifest=candidate["manifest"], candidate=candidate["package"], candidate_preflight=candidate["preflight"], candidate_gate=candidate["gate"], inner_package=bridge["inner_package"], inner_package_gate=bridge["inner_package_gate"], plan=bridge["plan"], plan_gate=bridge["plan_gate"], blueprint=bridge["blueprint"], blueprint_gate=bridge["blueprint_gate"])


def test_candidate_bound_bridge_is_exact_and_default_deny() -> None:
    bridge, candidate = _all()
    assert bridge["manifest"]["bridge_manifest_digest"] == __import__("sec_agent.canonical_runtime.models", fromlist=["canonical_digest"]).canonical_digest(bridge_manifest_payload(bridge["manifest"]))
    assert bridge["package"]["package_digest"] == __import__("sec_agent.canonical_runtime.models", fromlist=["canonical_digest"]).canonical_digest(bridge_package_payload(bridge["package"]))
    assert bridge["preflight"]["preflight_digest"] == __import__("sec_agent.canonical_runtime.models", fromlist=["canonical_digest"]).canonical_digest(bridge_preflight_payload(bridge["preflight"]))
    assert bridge["gate"]["gate_digest"] == __import__("sec_agent.canonical_runtime.models", fromlist=["canonical_digest"]).canonical_digest(bridge_gate_payload(bridge["gate"]))
    assert _validate(bridge, candidate)["status"] == "pass"
    assert bridge["preflight"]["status"] == "pass"
    assert bridge["preflight"]["candidate_input_hash_match_count"] == 100
    assert bridge["package"]["negative_cases"] == {"enabled": False, "authorization": "not_authorized"}
    assert all(value == 0 for value in bridge["package"]["execution_counts"].values())


def test_candidate_or_manifest_tamper_is_rejected() -> None:
    bridge, candidate = _all()
    broken_candidate = copy.deepcopy(candidate)
    broken_candidate["package"]["candidate_digest"] = "0" * 64
    assert _validate(bridge, broken_candidate)["status"] == "fail_closed"
    broken_manifest = copy.deepcopy(candidate)
    key = next(iter(broken_manifest["manifest"]["input_file_sha256"]))
    broken_manifest["manifest"]["input_file_sha256"][key] = "0" * 64
    assert _validate(bridge, broken_manifest)["status"] == "fail_closed"


def test_production_preflight_accepts_derived_v2_only_up_to_missing_admission() -> None:
    bridge, candidate = _all()
    result = preflight_candidate_bound_execution(bridge["package"], repository_root=ROOT, manifest=candidate["manifest"], candidate=candidate["package"], candidate_preflight=candidate["preflight"], candidate_gate=candidate["gate"], inner_package=bridge["inner_package"], inner_package_gate=bridge["inner_package_gate"], plan=bridge["plan"], plan_gate=bridge["plan_gate"], blueprint=bridge["blueprint"], blueprint_gate=bridge["blueprint_gate"], index_reader=lambda root, relative: __import__("subprocess").run(["git", "show", f":{relative}"], cwd=root, capture_output=True, check=True).stdout)
    assert result["status"] == "pass"
    assert result["production_preflight_without_admission"] == "package_admission_required"
    assert result["execution_counts"] == bridge["package"]["execution_counts"]


def test_runner_receives_package_argument_not_historical_package_constant() -> None:
    source = (ROOT / "scripts/engineering/run_point01_p01_g2_1_candidate_bound_baseline.py").read_text(encoding="utf-8")
    assert "--executable-package" in source
    assert "PACKAGE_PATH =" not in source
    assert "point01_m2_a1_execution_ready_audit_package_manifest_v2_10.json" not in source
