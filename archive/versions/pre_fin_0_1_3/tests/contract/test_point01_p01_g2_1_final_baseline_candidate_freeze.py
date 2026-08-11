"""Static contract tests for the P01-G2 final baseline candidate freeze."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

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
    validate_final_baseline_candidate,
)


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = {
    "manifest": ROOT / "data/manifests/point01_p01_g2_1_final_baseline_candidate_input_manifest_v1_0.json",
    "package": ROOT / "data/manifests/point01_p01_g2_1_final_baseline_candidate_package_v1_0.json",
    "preflight": ROOT / "data/manifests/point01_p01_g2_1_final_baseline_candidate_preflight_v1_0.json",
    "gate": ROOT / "data/manifests/point01_p01_g2_1_final_baseline_candidate_gate_v1_0.json",
}
HISTORICAL_P01 = {
    "package": ROOT / "data/manifests/point01_p01_g2_1_operational_execution_package_manifest_v1_0.json",
    "gate": ROOT / "data/manifests/point01_p01_g2_1_operational_execution_package_gate_v1_0.json",
}
TRANCHE = {
    "tranche": ROOT / "data/manifests/point01_p01_g2_operational_tranche_manifest_v1_1.json",
    "gate": ROOT / "data/manifests/point01_p01_g2_operational_tranche_gate_v1_1.json",
}
V2 = {
    "package": ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_10.json",
    "package_gate": ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_freeze_gate_result_v2_10.json",
    "plan": ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_7_execution_proof.json",
    "plan_gate": ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_7_execution_proof_gate.json",
    "blueprint": ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_7_execution_proof.json",
    "blueprint_gate": ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_7_execution_proof_gate.json",
}
STABLE = {
    "detailed_design_sha256": ROOT / "docs/architecture/repository/RELEASE_FIN_IA_0_1_DETAILED_PRODUCT_TECHNICAL_DESIGN_20260717.zh-CN.md",
    "detailed_backlog_sha256": ROOT / "configs/releases/fin_ia_0_1_detailed_execution_backlog_v1_0.json",
    "release_contract_sha256": ROOT / "configs/releases/fin_ia_0_1_release_contract_v1_1.json",
    "feature_scope_sha256": ROOT / "configs/releases/fin_ia_0_1_feature_scope_matrix_v1_0.json",
}


def _mapping(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(candidate: dict[str, object], manifest: dict[str, object]) -> dict[str, object]:
    historical = {name: _mapping(path) for name, path in HISTORICAL_P01.items()}
    tranche = {name: _mapping(path) for name, path in TRANCHE.items()}
    v2 = {name: _mapping(path) for name, path in V2.items()}
    stable = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in STABLE.items()}
    fixed = ROOT / str(v2["package"]["fixed_store_fingerprints"]["fixed_approval_store"]["path"])
    return validate_final_baseline_candidate(
        candidate,
        manifest=manifest,
        historical_execution_package=historical["package"],
        historical_execution_gate=historical["gate"],
        tranche=tranche["tranche"],
        tranche_gate=tranche["gate"],
        v2_package=v2["package"],
        v2_package_gate=v2["package_gate"],
        v2_plan=v2["plan"],
        v2_plan_gate=v2["plan_gate"],
        v2_blueprint=v2["blueprint"],
        v2_blueprint_gate=v2["blueprint_gate"],
        stable_contract_digests=stable,
        fixed_store_sha256=hashlib.sha256(fixed.read_bytes()).hexdigest(),
    )


def test_final_baseline_candidate_freeze_is_exact_default_deny() -> None:
    manifest, candidate, preflight, gate = (_mapping(CANDIDATE[name]) for name in ("manifest", "package", "preflight", "gate"))
    assert manifest["schema_version"] == P01_G2_1_FINAL_BASELINE_CANDIDATE_MANIFEST_SCHEMA
    assert manifest["manifest_digest"] == canonical_digest(candidate_manifest_payload(manifest))
    assert candidate["schema_version"] == P01_G2_1_FINAL_BASELINE_CANDIDATE_SCHEMA
    assert candidate["candidate_digest"] == canonical_digest(candidate_package_payload(candidate))
    assert candidate["status"] == "P01_G2_FINAL_BASELINE_CANDIDATE_FREEZE_PENDING_EXACT_DIGEST_APPROVAL"
    assert candidate["future_scope"] == "single_ai_semis_operational_baseline_only"
    assert candidate["case_instance_pack"] == {
        "pack_version_id": AI_SEMIS_CASE_INSTANCE_PACK_REF,
        "payload_digest": AI_SEMIS_CASE_INSTANCE_PACK_PAYLOAD_DIGEST,
        "case_id": "m2-a1-ai-semis-input",
        "override_mode": "no_override",
    }
    assert _validate(candidate, manifest)["status"] == "pass"
    assert preflight["schema_version"] == P01_G2_1_FINAL_BASELINE_CANDIDATE_PREFLIGHT_SCHEMA
    assert preflight["preflight_digest"] == canonical_digest(candidate_preflight_payload(preflight))
    assert preflight["status"] == "pass"
    assert gate["schema_version"] == P01_G2_1_FINAL_BASELINE_CANDIDATE_GATE_SCHEMA
    assert gate["gate_digest"] == canonical_digest(candidate_gate_payload(gate))
    assert gate["status"] == "pass"


def test_final_baseline_candidate_rejects_case_pack_or_inventory_tamper() -> None:
    manifest, candidate = _mapping(CANDIDATE["manifest"]), _mapping(CANDIDATE["package"])
    tampered = copy.deepcopy(candidate)
    tampered["case_instance_pack"]["payload_digest"] = "0" * 64
    tampered["candidate_digest"] = canonical_digest(candidate_package_payload(tampered))
    assert _validate(tampered, manifest)["status"] == "fail_closed"
    tampered_manifest = copy.deepcopy(manifest)
    first_input = next(iter(tampered_manifest["input_file_sha256"]))
    tampered_manifest["input_file_sha256"][first_input] = "0" * 64
    tampered_manifest["manifest_digest"] = canonical_digest(candidate_manifest_payload(tampered_manifest))
    assert _validate(candidate, tampered_manifest)["status"] == "fail_closed"


def test_final_baseline_candidate_is_freeze_only_with_all_execution_counts_zero() -> None:
    manifest, candidate, preflight, gate = (_mapping(CANDIDATE[name]) for name in ("manifest", "package", "preflight", "gate"))
    assert manifest["input_hash_count"] == preflight["candidate_input_hash_count"]
    assert preflight["candidate_input_hash_match_count"] == manifest["input_hash_count"]
    assert preflight["candidate_working_index_match_count"] == manifest["input_hash_count"]
    assert preflight["historical_v2_input_drift_count"] == 8
    assert candidate["execution_counts"] == {key: 0 for key in candidate["execution_counts"]}
    assert preflight["execution_counts"] == candidate["execution_counts"]
    assert gate["execution_counts"] == candidate["execution_counts"]
    assert gate["next_step"] == "independent_exact_digest_approval_required_no_authority_created"
