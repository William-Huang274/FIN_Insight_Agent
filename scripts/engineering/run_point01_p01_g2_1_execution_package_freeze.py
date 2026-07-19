"""Freeze the exact P01-G2.1 operational-tranche execution package.

The package binds the already accepted P01-G2.0 v1.1 tranche and the complete
v2.10 family.  It has no active approval, admission, receipt, or namespace.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.p01_g2_1_operational_tranche import (
    P01_G2_1_PACKAGE_SCHEMA,
    gate_payload,
    validate_execution_package,
)


V1_1 = {
    "tranche": "data/manifests/point01_p01_g2_operational_tranche_manifest_v1_1.json",
    "gate": "data/manifests/point01_p01_g2_operational_tranche_gate_v1_1.json",
}
V2 = {
    "package": "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_10.json",
    "package_gate": "data/manifests/point01_m2_a1_execution_ready_audit_package_freeze_gate_result_v2_10.json",
    "plan": "data/manifests/point01_m2_a1_receipt_execution_plan_v1_7_execution_proof.json",
    "plan_gate": "data/manifests/point01_m2_a1_receipt_execution_plan_v1_7_execution_proof_gate.json",
    "blueprint": "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_7_execution_proof.json",
    "blueprint_gate": "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_7_execution_proof_gate.json",
}
INPUTS = (
    "configs/engineering_handoff/point01_p01_g2_1_operational_execution_policy_v1_0.json",
    "src/sec_agent/canonical_runtime/p01_g2_1_operational_tranche.py",
    "scripts/engineering/run_point01_p01_g2_1_execution_package_freeze.py",
    "scripts/engineering/run_point01_p01_g2_1_execute_tranche.py",
    "tests/contract/test_point01_p01_g2_1_execution_package.py",
    *V1_1.values(),
    *V2.values(),
)
OUTPUTS = {
    "package": ROOT / "data/manifests/point01_p01_g2_1_operational_execution_package_manifest_v1_0.json",
    "gate": ROOT / "data/manifests/point01_p01_g2_1_operational_execution_package_gate_v1_0.json",
}


def _index_bytes(relative: str) -> bytes:
    completed = subprocess.run(["git", "show", f":{relative}"], cwd=ROOT, capture_output=True, check=False)
    if completed.returncode:
        raise RuntimeError(f"p01_g2_1_index_input_missing:{relative}")
    return completed.stdout


def _index_mapping(relative: str) -> Mapping[str, Any]:
    value = json.loads(_index_bytes(relative).decode("utf-8"))
    if not isinstance(value, Mapping):
        raise RuntimeError(f"p01_g2_1_mapping_required:{relative}")
    return value


def _sha_index(relative: str) -> str:
    return hashlib.sha256(_index_bytes(relative)).hexdigest()


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_artifacts() -> dict[str, Mapping[str, Any]]:
    v1 = {name: _index_mapping(path) for name, path in V1_1.items()}
    v2 = {name: _index_mapping(path) for name, path in V2.items()}
    if v1["gate"].get("status") != "pass" or any(v2[name].get("status") != "pass" for name in ("package_gate", "plan_gate", "blueprint_gate")):
        raise RuntimeError("p01_g2_1_upstream_gate_not_pass")
    policy = _index_mapping("configs/engineering_handoff/point01_p01_g2_1_operational_execution_policy_v1_0.json")
    package_inputs = {relative: _sha_index(relative) for relative in sorted(INPUTS)}
    binding = {
        "tranche_digest": v1["tranche"]["tranche_digest"],
        "tranche_gate_digest": v1["gate"]["gate_digest"],
        "v2_package_digest": v2["package"]["package_digest"],
        "v2_package_gate_digest": v2["package_gate"]["gate_digest"],
        "v2_plan_digest": v2["plan"]["plan_digest"],
        "v2_plan_gate_digest": v2["plan_gate"]["gate_digest"],
        "v2_blueprint_digest": v2["blueprint"]["blueprint_digest"],
        "v2_blueprint_gate_digest": v2["blueprint_gate"]["gate_digest"],
        "trigger_ddl_digest": v2["package"]["trigger_ddl_contract"]["normalized_ddl_digest"],
        "fixed_store_sha256": v2["package"]["fixed_store_fingerprints"]["fixed_approval_store"]["sha256"],
    }
    cases = [
        {"case_id": "g2-baseline", "mode": "single_authorized_v2_10_production_lifecycle", "expected_terminal": "succeeded", "authority": 1, "formal_namespace": 1, "runtime": 1, "terminal_lifecycle": 1},
        {"case_id": "g2-wrong-package-or-approval", "mode": "pre_authority_boundary_probe", "expected_terminal": policy["negative_cases"]["g2-wrong-package-or-approval"], "authority": 0, "formal_namespace": 0, "runtime": 0, "terminal_lifecycle": 0},
        {"case_id": "g2-stale-input-version-drift", "mode": "pre_authority_pack_admission_probe", "expected_terminal": policy["negative_cases"]["g2-stale-input-version-drift"], "authority": 0, "formal_namespace": 0, "runtime": 0, "terminal_lifecycle": 0},
        {"case_id": "g2-unauthorized-transport", "mode": "pre_authority_permission_canary_probe", "expected_terminal": policy["negative_cases"]["g2-unauthorized-transport"], "authority": 0, "formal_namespace": 0, "runtime": 0, "terminal_lifecycle": 0},
    ]
    payload = {
        "schema_version": P01_G2_1_PACKAGE_SCHEMA,
        "package_ref": "point01-p01-g2-1-exact-operational-tranche-execution-package-v1",
        "status": "frozen_external_total_reviewer_execution_authority_required",
        "execution_state_on_success": "P01_G2_1_OPERATIONAL_TRANCHE_EXECUTED_PENDING_INDEPENDENT_REVIEW",
        "exact_bindings": binding,
        "baseline_contract": {
            "case_id": "g2-baseline", "scenario_id": "p01-baseline-separated-input", "input_ref": "m2-a1-ai-semis-input", "mutation": "none",
            "reviewer_identity": "william/003/total_reviewer", "actor_id": "003", "admission_ttl_minutes": 30, "receipt_ttl_minutes": 15,
            "single_use": True, "no_retry_replay_or_renewal": True,
        },
        "cases": cases,
        "authority_boundary": {
            "baseline_only_valid_authority": True,
            "negative_cases_pre_authority_only": True,
            "v2_10_production_kernel_only": True,
            "synthetic_child_callback_or_alternate_runner_forbidden": True,
            "network_tool_model_provider_success_forbidden": True,
            "fixed_store_fingerprint_only": True,
            "legacy_authority": "retained",
            "production_readiness": "not_admitted",
        },
        "input_bytes_source": "git_index",
        "input_file_sha256": package_inputs,
        "input_hash_count": len(package_inputs),
        "input_hashes_digest": canonical_digest(package_inputs),
        "v2_10_staged_input_hash_count": len(v1["tranche"]["v2_10_staged_input_binding"]["input_file_sha256"]),
        "v2_10_staged_input_hashes_digest": v1["tranche"]["v2_10_staged_input_binding"]["input_hashes_digest"],
        "policy_digest": canonical_digest(policy),
        "prohibitions": policy["prohibitions"],
    }
    package = {**payload, "package_digest": canonical_digest(payload)}
    verification = validate_execution_package(package, tranche=v1["tranche"], tranche_gate=v1["gate"], v2_package=v2["package"], v2_package_gate=v2["package_gate"], v2_plan=v2["plan"], v2_plan_gate=v2["plan_gate"], v2_blueprint=v2["blueprint"], v2_blueprint_gate=v2["blueprint_gate"])
    return {"package": package, "gate": gate_payload(package=package, verification=verification)}


def main() -> int:
    artifacts = build_artifacts()
    for name, path in OUTPUTS.items():
        _write(path, artifacts[name])
    print(json.dumps({"status": artifacts["gate"]["status"], "package_digest": artifacts["package"]["package_digest"], "gate_digest": artifacts["gate"]["gate_digest"], "input_hash_count": artifacts["package"]["input_hash_count"]}, sort_keys=True))
    return 0 if artifacts["gate"]["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
