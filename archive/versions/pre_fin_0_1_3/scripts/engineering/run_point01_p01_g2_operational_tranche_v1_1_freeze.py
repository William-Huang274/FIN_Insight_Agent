"""Freeze the repaired P01-G2.0 authority/coverage tranche; never execute it."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.canonical_runtime.p01_g2_operational_tranche_v1_1 import (  # noqa: E402
    P01_G2_TRANCHE_SCHEMA,
    gate_payload,
    validate_p01_g2_operational_tranche,
)


POLICY = "configs/engineering_handoff/point01_p01_g2_operational_tranche_policy_v1_1.json"
RECEIPT_TEMPLATE = "configs/engineering_handoff/point01_p01_g2_proposed_baseline_reviewer_decision_receipt_template_v1_1.json"
SOURCE_MATRIX = "configs/engineering_handoff/point01_m2_a1_execution_ready_scenario_matrix_v2_1.json"
V2_10_PATHS = {
    "package": "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_10.json",
    "package_gate": "data/manifests/point01_m2_a1_execution_ready_audit_package_freeze_gate_result_v2_10.json",
    "plan": "data/manifests/point01_m2_a1_receipt_execution_plan_v1_7_execution_proof.json",
    "plan_gate": "data/manifests/point01_m2_a1_receipt_execution_plan_v1_7_execution_proof_gate.json",
    "blueprint": "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_7_execution_proof.json",
    "blueprint_gate": "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_7_execution_proof_gate.json",
}
OUTPUTS = {
    "tranche": ROOT / "data/manifests/point01_p01_g2_operational_tranche_manifest_v1_1.json",
    "gate": ROOT / "data/manifests/point01_p01_g2_operational_tranche_gate_v1_1.json",
}
FREEZE_INPUTS = {
    POLICY,
    RECEIPT_TEMPLATE,
    "src/sec_agent/canonical_runtime/p01_g2_operational_tranche_v1_1.py",
    "scripts/engineering/run_point01_p01_g2_operational_tranche_v1_1_freeze.py",
    "tests/contract/test_point01_p01_g2_operational_tranche_v1_1_freeze.py",
}


def _index_bytes(relative_path: str) -> bytes:
    result = subprocess.run(["git", "show", f":{relative_path}"], cwd=ROOT, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"p01_g2_v1_1_index_input_missing:{relative_path}")
    return result.stdout


def _index_mapping(relative_path: str) -> dict[str, Any]:
    value = json.loads(_index_bytes(relative_path).decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"p01_g2_v1_1_index_mapping_required:{relative_path}")
    return value


def _sha(relative_path: str) -> str:
    return hashlib.sha256(_index_bytes(relative_path)).hexdigest()


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _zero_counts() -> dict[str, int]:
    return {
        "active_approval": 0, "admission": 0, "receipt": 0,
        "formal_namespace": 0, "runtime": 0, "baseline": 0,
        "external": 0, "network_success": 0, "tool_success": 0,
        "model": 0, "provider": 0, "fixed_store_write": 0,
        "legacy_authority_change": 0,
    }


def _baseline_case() -> dict[str, Any]:
    terminal = "succeeded"
    return {
        "case_id": "g2-baseline",
        "sequence": 1,
        "coverage_class": "selected_original_matrix_scenario",
        "source_matrix_scenario_id": "p01-baseline-separated-input",
        "future_authority_mode": "baseline_only_future_single_use_authority_allowed",
        "expected_terminal": terminal,
        "expected_pre_counts": _zero_counts(),
        "expected_post_counts": {
            "valid_authority_issue_count": 1, "receipt_registration_count": 1,
            "receipt_consume_count": 1, "formal_namespace_count": 1,
            "runtime_materialization_count": 1, "terminal_lifecycle_write_count": 1,
            "baseline_execution_count": 1, "network_success": 0, "tool_success": 0,
            "model_success": 0, "provider_success": 0, "fixed_store_write": 0,
            "legacy_authority_change": 0, "terminal": terminal,
        },
        "artifact_refs": [
            "package_external_reviewer_decision_receipt_digest_only",
            "external_admission_digest_only",
            "single_use_execution_receipt_digest_only",
            "append_only_ledger_event_sequence",
            "immutable_actual_artifact",
            "independent_oracle_artifact",
            "reviewer_gate_artifact",
        ],
        "rollback_cleanup": {
            "authority_and_artifacts": "append_only_retain_until_independent_closeout",
            "cleanup": "only_after_closeout_under_separate_retention_policy",
            "receipt": "no_retry_no_replay_no_renewal",
        },
        "stop_rule": "fail_fast_stop_all_remaining_cases",
    }


def _pre_authority_case(
    *,
    case_id: str,
    sequence: int,
    source_id: str | None,
    expected_terminal: str,
    probe_key: str,
    artifact_refs: list[str],
    supplemental: bool = False,
) -> dict[str, Any]:
    counts: dict[str, int | str] = {
        "valid_authority_issue_count": 0, "receipt_registration_count": 0,
        "receipt_consume_count": 0, "formal_namespace_count": 0,
        "runtime_materialization_count": 0, "terminal_lifecycle_write_count": 0,
        "baseline_execution_count": 0, "network_success": 0, "tool_success": 0,
        "model_success": 0, "provider_success": 0, "fixed_store_write": 0,
        "legacy_authority_change": 0, probe_key: 1, "terminal": expected_terminal,
    }
    return {
        "case_id": case_id,
        "sequence": sequence,
        "coverage_class": "supplemental_pre_authority_probe" if supplemental else "selected_original_matrix_scenario",
        "source_matrix_scenario_id": source_id,
        "supplemental_case_id": case_id if supplemental else None,
        "future_authority_mode": "pre_authority_only_no_admission_receipt_namespace_or_runtime",
        "expected_terminal": expected_terminal,
        "expected_pre_counts": _zero_counts(),
        "expected_post_counts": counts,
        "artifact_refs": artifact_refs,
        "rollback_cleanup": {
            "artifacts": "immutable_pre_authority_probe_retain_until_independent_closeout",
            "cleanup": "only_after_closeout_under_separate_retention_policy",
            "authority": "not_issued_no_retry_replay_or_renewal",
        },
        "stop_rule": "stop_case_pre_authority_no_auto_repair_or_fallback",
    }


def build_artifacts() -> dict[str, dict[str, Any]]:
    policy = _index_mapping(POLICY)
    template = _index_mapping(RECEIPT_TEMPLATE)
    matrix = _index_mapping(SOURCE_MATRIX)
    family = {key: _index_mapping(path) for key, path in V2_10_PATHS.items()}
    package = family["package"]
    selected = tuple(policy["selected_original_source_matrix_scenario_ids"])
    if selected != ("p01-baseline-separated-input", "p02-stale-or-superseded-pack", "p03-network-tool-transport"):
        raise RuntimeError("p01_g2_v1_1_policy_selection_contract_invalid")
    source_by_id = {item["scenario_id"]: item for item in matrix["scenarios"]}
    deferred_ids = sorted(set(source_by_id).difference(selected))
    deferred = [
        {
            "scenario_id": scenario_id,
            "owner": source_by_id[scenario_id]["owner"],
            "expected_typed_stop": source_by_id[scenario_id]["expected_typed_stop"],
            "disposition": "deferred_named_original_operational_regression_after_g2_baseline_and_independent_authority_review",
        }
        for scenario_id in deferred_ids
    ]
    cases = [
        _baseline_case(),
        _pre_authority_case(
            case_id="g2-wrong-package-or-approval", sequence=2, source_id=None,
            expected_terminal="pre_authority_typed_deny:package_or_approval_mismatch",
            probe_key="package_approval_binding_deny_artifact_count",
            artifact_refs=["immutable_pre_authority_deny_artifact", "package_and_approval_binding_snapshot", "reviewer_comparison_artifact"],
            supplemental=True,
        ),
        _pre_authority_case(
            case_id="g2-stale-input-version-drift", sequence=3, source_id=selected[1],
            expected_terminal="typed_stop:superseded_pack_version_or_pack_not_fresh",
            probe_key="pack_version_admission_preflight_artifact_count",
            artifact_refs=["immutable_pre_authority_deny_artifact", "exact_pack_version_input_binding", "pack_admission_preflight_observation", "reviewer_comparison_artifact"],
        ),
        _pre_authority_case(
            case_id="g2-unauthorized-transport", sequence=4, source_id=selected[2],
            expected_terminal="typed_stop:shadow_scope_violation",
            probe_key="network_tool_permission_probe_artifact_count",
            artifact_refs=["immutable_pre_authority_deny_artifact", "permission_canary_observation", "network_tool_success_zero_counter_snapshot", "reviewer_comparison_artifact"],
        ),
    ]
    input_hashes = package["input_file_sha256"]
    family_binding = {
        "package_digest": package["package_digest"],
        "package_gate_digest": family["package_gate"]["gate_digest"],
        "plan_digest": family["plan"]["plan_digest"],
        "plan_gate_digest": family["plan_gate"]["gate_digest"],
        "blueprint_digest": family["blueprint"]["blueprint_digest"],
        "blueprint_gate_digest": family["blueprint_gate"]["gate_digest"],
        "trigger_ddl_digest": package["trigger_ddl_contract"]["normalized_ddl_digest"],
        "fixed_store_sha256": package["fixed_store_fingerprints"]["fixed_approval_store"]["sha256"],
    }
    blueprint_exact = family["blueprint"]["exact_binding"]
    blueprint_other = family["blueprint"]["all_other_scenarios"]
    receipt_proposal = {
        "schema_version": template["schema_version"],
        "state": template["state"],
        "template_ref": RECEIPT_TEMPLATE,
        "template_digest": canonical_digest(template),
        "eligible_case_id": template["eligible_case_id"],
        "canonical_digest_inputs": {
            "template_required_exact_bindings": template["canonical_digest_inputs"]["required_exact_bindings"],
            "family_binding": family_binding,
            "tranche_binding": ["tranche_digest", "tranche_gate_digest"],
            "future_dynamic_fields_are_unresolved": template["unresolved_fields"],
        },
        "do_not_invoke": True,
    }
    freeze_hashes = {path: _sha(path) for path in sorted(FREEZE_INPUTS)}
    payload = {
        "schema_version": P01_G2_TRANCHE_SCHEMA,
        "tranche_id": "P01-G2.0-minimum-operational-qualification-tranche-v1-1-authority-coverage-repair",
        "status": "P01_G2_0_TRANCHE_FROZEN_PENDING_INDEPENDENT_EXECUTION_AUTHORITY",
        "purpose": policy["purpose"],
        "supersedes": {"tranche_manifest_v1_0": "8df521fcc321c6c5dfa30f6ae7a3ad377a0be223c21091525ef741d9208a047f", "reason": "authority_scope_conflict_and_original_matrix_coverage_gap"},
        "v2_10_family": family_binding,
        "v2_10_staged_input_binding": {"input_hash_count": len(input_hashes), "input_file_sha256": input_hashes, "input_hashes_digest": canonical_digest(input_hashes)},
        "tranche_freeze_input_binding": {"input_file_sha256": freeze_hashes, "input_hash_count": len(freeze_hashes), "input_hashes_digest": canonical_digest(freeze_hashes)},
        "authority_boundary": {
            "legacy_authority": policy["legacy_authority"], "production_readiness": policy["production_readiness"],
            "active_authority_forbidden": True, "operational_execution_authorized": False,
            "formal_namespace_must_remain_absent": True,
            "negative_cases_must_remain_pre_authority": True,
            "no_paid_full_chain_network_model_provider_or_tool_success": True,
        },
        "blueprint_authority_contract": {
            "authorized_baseline_scenario_id": blueprint_exact["scenario_id"],
            "authorized_baseline_input_ref": blueprint_exact["input_ref"],
            "authorized_baseline_mutation": blueprint_exact["mutation"],
            "all_other_scenarios_authority_issue_forbidden": blueprint_other["authority_issue_forbidden"],
            "all_other_scenarios_count": blueprint_other["count"],
        },
        "selected_cases": cases,
        "original_matrix_coverage": {
            "original_matrix_count": len(source_by_id),
            "selected_original_source_matrix_ids": list(selected),
            "deferred_original_source_matrix_ids": deferred_ids,
            "supplemental_case_ids": ["g2-wrong-package-or-approval"],
        },
        "deferred_original_regression_backlog": deferred,
        "baseline_failure_halts_all_remaining_cases": True,
        "proposed_baseline_reviewer_decision_receipt": receipt_proposal,
        "freeze_execution_counts": _zero_counts(),
    }
    tranche = {**payload, "tranche_digest": canonical_digest(payload)}
    verification = validate_p01_g2_operational_tranche(
        tranche, source_matrix=matrix, v2_10_package=family["package"],
        v2_10_package_gate=family["package_gate"], v2_10_plan=family["plan"],
        v2_10_plan_gate=family["plan_gate"], v2_10_blueprint=family["blueprint"],
        v2_10_blueprint_gate=family["blueprint_gate"],
    )
    return {"tranche": tranche, "gate": gate_payload(tranche=tranche, verification=verification)}


def main() -> int:
    artifacts = build_artifacts()
    for name, path in OUTPUTS.items():
        _write(path, artifacts[name])
    print(json.dumps({"status": artifacts["gate"]["status"], "tranche_digest": artifacts["tranche"]["tranche_digest"], "gate_digest": artifacts["gate"]["gate_digest"], "execution_counts": artifacts["gate"]["execution_counts"]}, sort_keys=True))
    return 0 if artifacts["gate"]["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
