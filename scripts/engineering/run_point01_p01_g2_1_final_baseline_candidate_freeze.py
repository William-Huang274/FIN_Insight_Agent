"""Freeze the final P01-G2 AI-semis baseline candidate without authority.

This is a new immutable candidate version within the existing P01-G2.1
execution-package family.  It recalculates the current Git-index hashes for
the accepted v2.10 runtime inventory after the bounded lineage repair.  It
does not issue, register, consume, or replay any approval material.
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
    AI_SEMIS_CASE_INSTANCE_PACK_PAYLOAD_DIGEST,
    AI_SEMIS_CASE_INSTANCE_PACK_REF,
    P01_G2_1_FINAL_BASELINE_CANDIDATE_GATE_SCHEMA,
    P01_G2_1_FINAL_BASELINE_CANDIDATE_MANIFEST_SCHEMA,
    P01_G2_1_FINAL_BASELINE_CANDIDATE_PREFLIGHT_SCHEMA,
    P01_G2_1_FINAL_BASELINE_CANDIDATE_SCHEMA,
    candidate_gate_payload,
    candidate_manifest_payload,
    candidate_package_payload,
    candidate_preflight_payload,
    digest_file,
    validate_final_baseline_candidate,
)


POLICY = "configs/engineering_handoff/point01_p01_g2_1_final_baseline_candidate_policy_v1_0.json"
HISTORICAL_P01 = {
    "package": "data/manifests/point01_p01_g2_1_operational_execution_package_manifest_v1_0.json",
    "gate": "data/manifests/point01_p01_g2_1_operational_execution_package_gate_v1_0.json",
}
TRANCHE = {
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
STABLE_CONTRACTS = {
    "detailed_design_sha256": "docs/architecture/repository/RELEASE_FIN_IA_0_1_DETAILED_PRODUCT_TECHNICAL_DESIGN_20260717.zh-CN.md",
    "detailed_backlog_sha256": "configs/releases/fin_ia_0_1_detailed_execution_backlog_v1_0.json",
    "release_contract_sha256": "configs/releases/fin_ia_0_1_release_contract_v1_1.json",
    "feature_scope_sha256": "configs/releases/fin_ia_0_1_feature_scope_matrix_v1_0.json",
}
EXTRA_INPUTS = {
    POLICY,
    "configs/engineering_handoff/point01_p01_g2_1_operational_execution_policy_v1_0.json",
    "src/sec_agent/canonical_runtime/p01_g2_1_operational_tranche.py",
    "scripts/engineering/run_point01_p01_g2_1_final_baseline_candidate_freeze.py",
    "scripts/engineering/run_point01_p01_g2_1_execute_tranche.py",
    "tests/contract/test_point01_p01_g2_1_final_baseline_candidate_freeze.py",
    "tests/contract/test_point01_p01_g2_1_execution_package.py",
    *HISTORICAL_P01.values(),
    *TRANCHE.values(),
    *V2.values(),
    *STABLE_CONTRACTS.values(),
}
OUTPUTS = {
    "manifest": ROOT / "data/manifests/point01_p01_g2_1_final_baseline_candidate_input_manifest_v1_0.json",
    "package": ROOT / "data/manifests/point01_p01_g2_1_final_baseline_candidate_package_v1_0.json",
    "preflight": ROOT / "data/manifests/point01_p01_g2_1_final_baseline_candidate_preflight_v1_0.json",
    "gate": ROOT / "data/manifests/point01_p01_g2_1_final_baseline_candidate_gate_v1_0.json",
}


def _index_bytes(relative: str) -> bytes:
    completed = subprocess.run(["git", "show", f":{relative}"], cwd=ROOT, capture_output=True, check=False)
    if completed.returncode:
        raise RuntimeError(f"p01_g2_final_candidate_index_input_missing:{relative}")
    return completed.stdout


def _index_mapping(relative: str) -> Mapping[str, Any]:
    value = json.loads(_index_bytes(relative).decode("utf-8"))
    if not isinstance(value, Mapping):
        raise RuntimeError(f"p01_g2_final_candidate_mapping_required:{relative}")
    return value


def _sha_index(relative: str) -> str:
    return hashlib.sha256(_index_bytes(relative)).hexdigest()


def _normalized(value: bytes) -> bytes:
    return value.replace(b"\r\n", b"\n")


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _current_inventory(v2_package: Mapping[str, Any]) -> dict[str, str]:
    old_hashes = v2_package.get("input_file_sha256")
    if not isinstance(old_hashes, Mapping) or not old_hashes:
        raise RuntimeError("p01_g2_final_candidate_v2_input_inventory_missing")
    paths = set(str(path) for path in old_hashes) | EXTRA_INPUTS
    return {relative: _sha_index(relative) for relative in sorted(paths)}


def _stable_contract_digests() -> dict[str, str]:
    return {name: _sha_index(relative) for name, relative in STABLE_CONTRACTS.items()}


def _candidate_preflight(
    *,
    manifest: Mapping[str, Any],
    candidate: Mapping[str, Any],
    verification: Mapping[str, Any],
    fixed_store_path: Path,
    historical_v2_hashes: Mapping[str, Any],
) -> dict[str, Any]:
    errors = list(verification.get("errors", ()))
    hashes = manifest["input_file_sha256"]
    index_match_count = 0
    working_match_count = 0
    for relative, expected in hashes.items():
        indexed = _index_bytes(str(relative))
        if hashlib.sha256(indexed).hexdigest() != expected:
            errors.append(f"candidate_index_hash_mismatch:{relative}")
            continue
        index_match_count += 1
        working = (ROOT / str(relative)).read_bytes()
        if _normalized(working) != _normalized(indexed):
            errors.append(f"candidate_working_tree_drift:{relative}")
            continue
        working_match_count += 1
    historical_drift = sorted(
        relative
        for relative, old_digest in historical_v2_hashes.items()
        if hashes.get(relative) != old_digest
    )
    expected_fixed = candidate["exact_bindings"]["fixed_store_sha256"]
    actual_fixed = digest_file(fixed_store_path)
    if actual_fixed != expected_fixed:
        errors.append("candidate_fixed_store_fingerprint_drift")
    payload = {
        "schema_version": P01_G2_1_FINAL_BASELINE_CANDIDATE_PREFLIGHT_SCHEMA,
        "status": "pass" if not errors else "fail_closed",
        "candidate_ref": candidate["candidate_ref"],
        "candidate_digest": candidate["candidate_digest"],
        "manifest_digest": manifest["manifest_digest"],
        "verification": dict(verification),
        "candidate_input_hash_match_count": index_match_count,
        "candidate_working_index_match_count": working_match_count,
        "candidate_input_hash_count": len(hashes),
        "historical_v2_input_drift_replaced_by_candidate": historical_drift,
        "historical_v2_input_drift_count": len(historical_drift),
        "fixed_store_sha256_expected": expected_fixed,
        "fixed_store_sha256_actual": actual_fixed,
        "execution_counts": candidate["execution_counts"],
        "next_step": "independent_exact_digest_approval_required_no_authority_created",
    }
    return {**payload, "preflight_digest": canonical_digest(payload)}


def _gate(*, manifest: Mapping[str, Any], candidate: Mapping[str, Any], preflight: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if preflight.get("status") != "pass":
        errors.append("candidate_preflight_not_pass")
    if preflight.get("candidate_digest") != candidate.get("candidate_digest"):
        errors.append("candidate_preflight_package_binding_invalid")
    if preflight.get("manifest_digest") != manifest.get("manifest_digest"):
        errors.append("candidate_preflight_manifest_binding_invalid")
    if preflight.get("candidate_input_hash_match_count") != manifest.get("input_hash_count"):
        errors.append("candidate_preflight_index_count_invalid")
    if preflight.get("candidate_working_index_match_count") != manifest.get("input_hash_count"):
        errors.append("candidate_preflight_working_count_invalid")
    payload = {
        "schema_version": P01_G2_1_FINAL_BASELINE_CANDIDATE_GATE_SCHEMA,
        "status": "pass" if not errors else "fail_closed",
        "candidate_ref": candidate["candidate_ref"],
        "candidate_digest": candidate["candidate_digest"],
        "manifest_digest": manifest["manifest_digest"],
        "preflight_digest": preflight["preflight_digest"],
        "verification": {"status": "pass" if not errors else "fail_closed", "errors": sorted(errors)},
        "execution_counts": candidate["execution_counts"],
        "next_step": "independent_exact_digest_approval_required_no_authority_created",
    }
    return {**payload, "gate_digest": canonical_digest(payload)}


def build_artifacts() -> dict[str, Mapping[str, Any]]:
    policy = _index_mapping(POLICY)
    historical_p01 = {name: _index_mapping(relative) for name, relative in HISTORICAL_P01.items()}
    tranche = {name: _index_mapping(relative) for name, relative in TRANCHE.items()}
    v2 = {name: _index_mapping(relative) for name, relative in V2.items()}
    if any(v2[name].get("status") != "pass" for name in ("package_gate", "plan_gate", "blueprint_gate")):
        raise RuntimeError("p01_g2_final_candidate_v2_historical_gate_not_pass")
    if tranche["gate"].get("status") != "pass" or historical_p01["gate"].get("status") != "pass":
        raise RuntimeError("p01_g2_final_candidate_p01_historical_gate_not_pass")
    inventory = _current_inventory(v2["package"])
    manifest_payload = {
        "schema_version": P01_G2_1_FINAL_BASELINE_CANDIDATE_MANIFEST_SCHEMA,
        "manifest_ref": "point01-p01-g2-1-final-ai-semis-baseline-candidate-input-manifest-v1",
        "status": "frozen_current_git_index_inputs_only",
        "input_bytes_source": "git_index",
        "input_file_sha256": inventory,
        "input_hash_count": len(inventory),
        "input_hashes_digest": canonical_digest(inventory),
        "base_v2_10_input_count": len(v2["package"]["input_file_sha256"]),
        "candidate_extra_input_count": len(set(inventory) - set(v2["package"]["input_file_sha256"])),
        "outputs_excluded_from_input_inventory": sorted(str(path.relative_to(ROOT)).replace("\\", "/") for path in OUTPUTS.values()),
    }
    manifest = {**manifest_payload, "manifest_digest": canonical_digest(manifest_payload)}
    stable = _stable_contract_digests()
    fixed_path = ROOT / str(v2["package"]["fixed_store_fingerprints"]["fixed_approval_store"]["path"])
    fixed_sha = digest_file(fixed_path)
    bindings = {
        "historical_execution_package_digest": historical_p01["package"]["package_digest"],
        "historical_execution_gate_digest": historical_p01["gate"]["gate_digest"],
        "tranche_digest": tranche["tranche"]["tranche_digest"],
        "tranche_gate_digest": tranche["gate"]["gate_digest"],
        "v2_package_digest": v2["package"]["package_digest"],
        "v2_package_gate_digest": v2["package_gate"]["gate_digest"],
        "v2_plan_digest": v2["plan"]["plan_digest"],
        "v2_plan_gate_digest": v2["plan_gate"]["gate_digest"],
        "v2_blueprint_digest": v2["blueprint"]["blueprint_digest"],
        "v2_blueprint_gate_digest": v2["blueprint_gate"]["gate_digest"],
        "trigger_ddl_digest": v2["package"]["trigger_ddl_contract"]["normalized_ddl_digest"],
        "fixed_store_sha256": fixed_sha,
        "case_instance_pack_ref": AI_SEMIS_CASE_INSTANCE_PACK_REF,
        "case_instance_pack_payload_digest": AI_SEMIS_CASE_INSTANCE_PACK_PAYLOAD_DIGEST,
        "stable_contract_digests": stable,
    }
    candidate_payload = {
        "schema_version": P01_G2_1_FINAL_BASELINE_CANDIDATE_SCHEMA,
        "candidate_ref": "point01-p01-g2-1-final-ai-semis-operational-baseline-candidate-v1",
        "status": "P01_G2_FINAL_BASELINE_CANDIDATE_FREEZE_PENDING_EXACT_DIGEST_APPROVAL",
        "future_scope": policy["future_scope"],
        "manifest_ref": manifest["manifest_ref"],
        "manifest_digest": manifest["manifest_digest"],
        "exact_bindings": bindings,
        "baseline_contract": policy["baseline"],
        "case_instance_pack": policy["case_instance_pack"],
        "authority_boundary": policy["authority_boundary"],
        "execution_counts": policy["execution_counts"],
        "deferred_backlog": policy["deferred_backlog"],
        "prohibitions": policy["prohibitions"],
        "historical_receipt_policy": "all_historical_consumed_or_expired_receipts_non_replayable",
        "candidate_input_delta": "recalculated_current_git_index_inventory_supersedes_historical_v2_10_input_hashes_without_issuing_authority",
    }
    candidate = {**candidate_payload, "candidate_digest": canonical_digest(candidate_payload)}
    verification = validate_final_baseline_candidate(
        candidate,
        manifest=manifest,
        historical_execution_package=historical_p01["package"],
        historical_execution_gate=historical_p01["gate"],
        tranche=tranche["tranche"],
        tranche_gate=tranche["gate"],
        v2_package=v2["package"],
        v2_package_gate=v2["package_gate"],
        v2_plan=v2["plan"],
        v2_plan_gate=v2["plan_gate"],
        v2_blueprint=v2["blueprint"],
        v2_blueprint_gate=v2["blueprint_gate"],
        stable_contract_digests=stable,
        fixed_store_sha256=fixed_sha,
    )
    preflight = _candidate_preflight(
        manifest=manifest,
        candidate=candidate,
        verification=verification,
        fixed_store_path=fixed_path,
        historical_v2_hashes=v2["package"]["input_file_sha256"],
    )
    gate = _gate(manifest=manifest, candidate=candidate, preflight=preflight)
    return {"manifest": manifest, "package": candidate, "preflight": preflight, "gate": gate}


def main() -> int:
    artifacts = build_artifacts()
    for name, path in OUTPUTS.items():
        _write(path, artifacts[name])
    summary = {
        "status": artifacts["gate"]["status"],
        "manifest_digest": artifacts["manifest"]["manifest_digest"],
        "candidate_digest": artifacts["package"]["candidate_digest"],
        "preflight_digest": artifacts["preflight"]["preflight_digest"],
        "gate_digest": artifacts["gate"]["gate_digest"],
        "input_hash_count": artifacts["manifest"]["input_hash_count"],
    }
    print(json.dumps(summary, sort_keys=True))
    return 0 if artifacts["gate"]["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
