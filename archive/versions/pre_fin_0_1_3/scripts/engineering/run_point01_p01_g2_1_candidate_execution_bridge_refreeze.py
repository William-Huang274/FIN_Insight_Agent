"""Derive a candidate-bound, baseline-only executable package without authority."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sec_agent.canonical_runtime.m2_a1_execution_receipt import event_append_only_trigger_ddl_digest
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.p01_g2_1_candidate_execution_bridge import (
    BRIDGE_GATE_SCHEMA,
    BRIDGE_MANIFEST_SCHEMA,
    BRIDGE_MODE,
    BRIDGE_STATUS,
    bridge_gate_payload,
    bridge_manifest_payload,
    bridge_package_payload,
    bridge_preflight_payload,
    preflight_candidate_bound_execution,
    validate_execution_package,
)
from sec_agent.canonical_runtime.p01_g2_1_operational_tranche import P01_G2_1_PACKAGE_SCHEMA


POLICY = "configs/engineering_handoff/point01_p01_g2_1_candidate_execution_bridge_policy_v1_0.json"
CANDIDATE = {
    "manifest": "data/manifests/point01_p01_g2_1_final_baseline_candidate_input_manifest_v1_0.json",
    "package": "data/manifests/point01_p01_g2_1_final_baseline_candidate_package_v1_0.json",
    "preflight": "data/manifests/point01_p01_g2_1_final_baseline_candidate_preflight_v1_0.json",
    "gate": "data/manifests/point01_p01_g2_1_final_baseline_candidate_gate_v1_0.json",
}
V2 = {
    "package": "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_10.json",
}
BRIDGE_REF = "point01-p01-g2-1-final-ai-semis-candidate-bound-executable-baseline-v1"
NAMESPACE_ID = "point01_m2_a1_candidate_bound_final_baseline_v2_10"
NAMESPACE_PATH = "D:/temp/FIN_Insight_Agent/point01_m2_a1_candidate_bound_final_baseline_v2_10"
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
BRIDGE_INPUTS = {
    POLICY,
    "src/sec_agent/canonical_runtime/p01_g2_1_candidate_execution_bridge.py",
    "scripts/engineering/run_point01_p01_g2_1_candidate_execution_bridge_refreeze.py",
    "scripts/engineering/run_point01_p01_g2_1_candidate_bound_baseline.py",
    "tests/contract/test_point01_p01_g2_1_candidate_execution_bridge.py",
}


def _index_bytes(relative: str) -> bytes:
    completed = subprocess.run(["git", "show", f":{relative}"], cwd=ROOT, capture_output=True, check=False)
    if completed.returncode:
        raise RuntimeError(f"candidate_bridge_index_input_missing:{relative}")
    return completed.stdout


def _load_index(relative: str) -> dict[str, Any]:
    value = json.loads(_index_bytes(relative).decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"candidate_bridge_mapping_required:{relative}")
    return value


def _sha_index(relative: str) -> str:
    return hashlib.sha256(_index_bytes(relative)).hexdigest()


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _gate(kind: str, target: Mapping[str, Any], *, package_ref: str, package_digest: str, verification: Mapping[str, Any]) -> dict[str, Any]:
    field = {"package": "package_digest", "plan": "plan_digest", "blueprint": "blueprint_digest"}[kind]
    payload = {
        "result_version": f"finsight_point01_m2_a1_candidate_bound_v2_10_{kind}_gate_v1",
        "status": "pass" if verification.get("status") == "pass" else "fail_closed",
        "package_ref": package_ref,
        "package_digest": package_digest,
        "target_digest": target[field],
        "verification": dict(verification),
        "execution_counts": {"approval": 0, "admission": 0, "receipt": 0, "ledger": 0, "namespace": 0, "actual": 0, "network": 0, "tool": 0, "model": 0, "provider": 0, "store_write": 0},
        "next_step": "independent_exact_digest_review_required_no_authority_created",
    }
    return {**payload, "gate_digest": canonical_digest(payload)}


def _runtime_digest(relative: str) -> str:
    value = _load_index(relative)
    return canonical_digest(value)


def _entry(relative: str, hashes: Mapping[str, str]) -> dict[str, str]:
    return {"relative_path": relative, "sha256": hashes[relative]}


def build_artifacts() -> dict[str, dict[str, Any]]:
    policy = _load_index(POLICY)
    candidate = {name: _load_index(relative) for name, relative in CANDIDATE.items()}
    historical = _load_index(V2["package"])
    candidate_hashes = dict(candidate["manifest"]["input_file_sha256"])
    runtime_entries = {
        "orchestrator": _entry("scripts/engineering/run_point01_m2_a1_v2_10_frozen_jit_window.py", candidate_hashes),
        "registrar": _entry("scripts/engineering/run_point01_m2_a1_receipt_registrar_v2_10.py", candidate_hashes),
        "parent": _entry("scripts/engineering/run_point01_m2_a1_actual_audit_v2_10.py", candidate_hashes),
        "clean_child": _entry("scripts/engineering/run_point01_m2_a1_actual_audit_clean_child_v2_10.py", candidate_hashes),
        "lifecycle_kernel": _entry("src/sec_agent/canonical_runtime/m2_a1_v2_10_execution_proof.py", candidate_hashes),
    }
    inner_payload = dict(historical)
    inner_payload.update(
        {
            "package_ref": "point01-m2-a1-v2-10-p01-g2-candidate-bound-baseline-executable",
            "input_file_sha256": candidate_hashes,
            "execution_preflight": {
                **historical["execution_preflight"],
                "execution_staging_namespace_id": NAMESPACE_ID,
                "execution_staging_namespace_path": NAMESPACE_PATH,
                "runtime_inputs": {
                    "corpus": {"relative_path": "configs/engineering_handoff/point01_m2_a1_adversarial_input_corpus_v1_1.json", "canonical_digest": _runtime_digest("configs/engineering_handoff/point01_m2_a1_adversarial_input_corpus_v1_1.json")},
                    "scenario_matrix": {"relative_path": "configs/engineering_handoff/point01_m2_a1_execution_ready_scenario_matrix_v2_1.json", "canonical_digest": _runtime_digest("configs/engineering_handoff/point01_m2_a1_execution_ready_scenario_matrix_v2_1.json")},
                    "execution_policy": {"relative_path": "configs/engineering_handoff/point01_m2_a1_operational_qualification_policy_v2_4.json", "canonical_digest": _runtime_digest("configs/engineering_handoff/point01_m2_a1_operational_qualification_policy_v2_4.json")},
                },
            },
            "corpus_digest": _runtime_digest("configs/engineering_handoff/point01_m2_a1_adversarial_input_corpus_v1_1.json"),
            "oracle_digest": _runtime_digest("configs/engineering_handoff/point01_m2_a1_independent_expected_cell_oracle_v1_1.json"),
            "scenario_matrix_digest": _runtime_digest("configs/engineering_handoff/point01_m2_a1_execution_ready_scenario_matrix_v2_1.json"),
            "execution_policy_digest": _runtime_digest("configs/engineering_handoff/point01_m2_a1_operational_qualification_policy_v2_4.json"),
            "executable_authority_contract": {**historical["executable_authority_contract"], "entries": runtime_entries},
            "transport_isolation": {**historical["transport_isolation"], "runtime_hash_bindings": {**runtime_entries, "canary": _entry("src/sec_agent/canonical_runtime/m2_a1_audit_canary.py", candidate_hashes)}},
            "supersedes": {"historical_v2_10_package_digest": historical["package_digest"], "disposition": "candidate_bound_baseline_only_refreeze_no_authority"},
        }
    )
    inner_payload.pop("package_digest", None)
    inner_package = {**inner_payload, "package_digest": canonical_digest(inner_payload)}
    package_gate = _gate("package", inner_package, package_ref=inner_package["package_ref"], package_digest=inner_package["package_digest"], verification={"status": "pass", "input_hash_count": len(candidate_hashes), "production_schema": "v2_10"})
    plan_payload = {
        "schema_version": "finsight_point01_m2_a1_receipt_execution_plan_v1_7_execution_proof",
        "status": BRIDGE_STATUS,
        "exact_package": {"package_ref": inner_package["package_ref"], "package_digest": inner_package["package_digest"], "package_gate_digest": package_gate["gate_digest"], "scope": inner_package["scope"], "authority_boundary": inner_package["authority_boundary"], "execution_staging_namespace_id": NAMESPACE_ID, "trigger_ddl_digest": event_append_only_trigger_ddl_digest()},
        "scenario_execution_order": [{"sequence": 1, "scenario_id": policy["baseline"]["scenario_id"], "future_authority": "single_exact_human_approval_admission_receipt_JIT_only", "on_failure": "fail_fast_no_retry_no_replay"}],
        "negative_cases": {"enabled": False, "authorization": "not_authorized"},
        "execution_counts": {"approval": 0, "admission": 0, "receipt": 0, "ledger": 0, "namespace": 0, "actual": 0, "external": 0, "store_write": 0},
    }
    plan = {**plan_payload, "plan_digest": canonical_digest(plan_payload)}
    plan_gate = _gate("plan", plan, package_ref=inner_package["package_ref"], package_digest=inner_package["package_digest"], verification={"status": "pass", "scenario_count": 1, "negative_cases_disabled": True})
    blueprint_payload = {
        "schema_version": "finsight_point01_m2_a1_baseline_authority_blueprint_v1_7_execution_proof",
        "status": BRIDGE_STATUS,
        "exact_binding": {"package_digest": inner_package["package_digest"], "package_gate_digest": package_gate["gate_digest"], "plan_digest": plan["plan_digest"], "plan_gate_digest": plan_gate["gate_digest"], "trigger_ddl_digest": event_append_only_trigger_ddl_digest(), "scenario_id": policy["baseline"]["scenario_id"], "input_ref": policy["baseline"]["input_ref"], "mutation": policy["baseline"]["mutation"], "authority_boundary": inner_package["authority_boundary"], "execution_staging_namespace_id": NAMESPACE_ID},
        "templates": {"production_reviewer_decision_receipt_v2_10": {"schema_version": "finsight_point01_m2_a1_production_reviewer_decision_receipt_v2_10", "state": "unresolved_not_active", "package_external": True}, "production_human_jit_window_approval_v2_10": {"schema_version": "finsight_point01_m2_a1_production_human_jit_window_approval_v2_10", "state": "unresolved_not_active", "authority_class": "production_human_total_reviewer"}, "v2_10_admission": "unresolved_not_active", "v2_10_receipt": "unresolved_not_active"},
        "all_other_scenarios": {"count": 15, "authority_issue_forbidden": True},
        "negative_cases": {"enabled": False, "authorization": "not_authorized"},
        "command_contracts": {"bridge_runner": "do_not_invoke_without_fresh_exact_approval", "registrar": "do_not_invoke", "executor": "do_not_invoke"},
        "execution_counts": {"approval": 0, "admission": 0, "receipt": 0, "ledger": 0, "namespace": 0, "actual": 0, "external": 0, "store_write": 0},
    }
    blueprint = {**blueprint_payload, "blueprint_digest": canonical_digest(blueprint_payload)}
    blueprint_gate = _gate("blueprint", blueprint, package_ref=inner_package["package_ref"], package_digest=inner_package["package_digest"], verification={"status": "pass", "baseline_only": True, "all_other_scenarios_blocked": True})
    bridge_paths = set(candidate_hashes) | BRIDGE_INPUTS
    bridge_hashes = {path: _sha_index(path) for path in sorted(bridge_paths)}
    manifest_payload = {"schema_version": BRIDGE_MANIFEST_SCHEMA, "bridge_ref": BRIDGE_REF, "status": BRIDGE_STATUS, "input_bytes_source": "git_index", "input_file_sha256": bridge_hashes, "input_hash_count": len(bridge_hashes), "candidate_input_hash_count": len(candidate_hashes), "candidate_manifest_digest": candidate["manifest"]["manifest_digest"], "input_hashes_digest": canonical_digest(bridge_hashes), "outputs_excluded_from_input_inventory": sorted(str(path.relative_to(ROOT)).replace("\\", "/") for path in OUTPUTS.values())}
    manifest = {**manifest_payload, "bridge_manifest_digest": canonical_digest(manifest_payload)}
    counts = {"human_approval": 0, "admission": 0, "receipt": 0, "baseline": 0, "negative_case": 0, "formal_namespace": 0, "runtime": 0, "network_success": 0, "tool_success": 0, "model_success": 0, "provider_success": 0, "fixed_business_store_write": 0}
    bridge_payload = {
        "schema_version": P01_G2_1_PACKAGE_SCHEMA,
        "package_ref": BRIDGE_REF,
        "status": BRIDGE_STATUS,
        "execution_mode": BRIDGE_MODE,
        "bridge_manifest_digest": manifest["bridge_manifest_digest"],
        "candidate_bindings": {"manifest_digest": candidate["manifest"]["manifest_digest"], "candidate_digest": candidate["package"]["candidate_digest"], "candidate_preflight_digest": candidate["preflight"]["preflight_digest"], "candidate_gate_digest": candidate["gate"]["gate_digest"], "input_hash_count": len(candidate_hashes), "case_instance_pack_ref": policy["candidate_contract"]["case_instance_pack_ref"], "case_instance_pack_payload_digest": policy["candidate_contract"]["case_instance_pack_payload_digest"]},
        "derived_v2_10": {"package_digest": inner_package["package_digest"], "package_gate_digest": package_gate["gate_digest"], "plan_digest": plan["plan_digest"], "plan_gate_digest": plan_gate["gate_digest"], "blueprint_digest": blueprint["blueprint_digest"], "blueprint_gate_digest": blueprint_gate["gate_digest"]},
        "baseline_contract": {"case_id": policy["baseline"]["case_id"], "scenario_id": policy["baseline"]["scenario_id"], "input_ref": policy["baseline"]["input_ref"], "mutation": policy["baseline"]["mutation"], "reviewer_identity": "william/003/total_reviewer", "actor_id": "003", "single_use": True, "no_retry_replay_or_renewal": True},
        "negative_cases": {"enabled": False, "authorization": "not_authorized"},
        "authority_boundary": policy["authority_boundary"],
        "execution_counts": counts,
        "derived_artifact_paths": {name: str(path.relative_to(ROOT)).replace("\\", "/") for name, path in OUTPUTS.items() if name in {"inner_package", "inner_package_gate", "plan", "plan_gate", "blueprint", "blueprint_gate"}},
        "next_step": "independent_review_required_no_authority_or_baseline_execution",
    }
    bridge = {**bridge_payload, "package_digest": canonical_digest(bridge_payload)}
    preflight = preflight_candidate_bound_execution(bridge, repository_root=ROOT, manifest=candidate["manifest"], candidate=candidate["package"], candidate_preflight=candidate["preflight"], candidate_gate=candidate["gate"], inner_package=inner_package, inner_package_gate=package_gate, plan=plan, plan_gate=plan_gate, blueprint=blueprint, blueprint_gate=blueprint_gate, index_reader=lambda root, relative: _index_bytes(relative))
    verification = validate_execution_package(bridge, manifest=candidate["manifest"], candidate=candidate["package"], candidate_preflight=candidate["preflight"], candidate_gate=candidate["gate"], inner_package=inner_package, inner_package_gate=package_gate, plan=plan, plan_gate=plan_gate, blueprint=blueprint, blueprint_gate=blueprint_gate)
    gate_payload = {"schema_version": BRIDGE_GATE_SCHEMA, "status": "pass" if verification["status"] == "pass" and preflight["status"] == "pass" else "fail_closed", "package_ref": bridge["package_ref"], "package_digest": bridge["package_digest"], "bridge_manifest_digest": manifest["bridge_manifest_digest"], "preflight_digest": preflight["preflight_digest"], "verification": verification, "execution_counts": counts, "next_step": "independent_review_required_no_authority_or_baseline_execution"}
    gate = {**gate_payload, "gate_digest": canonical_digest(gate_payload)}
    return {"inner_package": inner_package, "inner_package_gate": package_gate, "plan": plan, "plan_gate": plan_gate, "blueprint": blueprint, "blueprint_gate": blueprint_gate, "manifest": manifest, "package": bridge, "preflight": preflight, "gate": gate}


def main() -> int:
    artifacts = build_artifacts()
    for name, path in OUTPUTS.items():
        _write(path, artifacts[name])
    print(json.dumps({"status": artifacts["gate"]["status"], "bridge_manifest_digest": artifacts["manifest"]["bridge_manifest_digest"], "package_digest": artifacts["package"]["package_digest"], "preflight_digest": artifacts["preflight"]["preflight_digest"], "gate_digest": artifacts["gate"]["gate_digest"], "candidate_input_hash_count": artifacts["preflight"]["candidate_input_hash_count"], "execution_counts": artifacts["package"]["execution_counts"]}, sort_keys=True))
    return 0 if artifacts["gate"]["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
