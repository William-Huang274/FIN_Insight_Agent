from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S4_CASE_DELIVERY_IDENTITY_CURRENT_CASE_AWARE_POLICY_REF,
    S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
    S3ThreeCellBoundedAgentAdmission,
    S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF,
    build_s3_three_cell_bounded_agent_executor_for_admission,
    compile_s4_case_runtime_mandatory_safety_admission,
)
from apps.workbench.backend.application.research_runtime import (
    prepare_s4_source_grounded_exact_input,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_paired_deterministic_baseline_decision import (
    _logical_snapshot,
    _sha256,
    _tree_digest,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    _principal,
    _services,
)
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s4_case_runtime import (
    compile_s4_case_evidence_role_group_mapping,
    load_s4_case_runtime_binding,
    load_s4_source_grounded_input_pack,
)
from test_fin_0_1_s4_t06_runtime_audit_evidence_v2_and_material_numeric_classifier_zero_call_implementation import (
    test_r4_two_path_reporting_period_replay_is_nonterminal_under_v2,
    test_three_case_full_fake_uses_v2_capture_and_bound_period_classification,
    test_three_case_material_failure_binds_safe_path_class_and_capture_sequence,
    test_v1_classifier_is_immutable_while_v2_allows_bound_period_labels,
    test_v2_failure_capture_is_atomic_replayable_indexed_and_not_promoted,
    test_v2_keeps_material_or_unknown_numeric_surfaces_fail_closed,
    test_v2_rejects_credential_bearing_request_before_terminal_write,
)


RUNTIME_ROOT = (
    ROOT
    / ".codex_runtime"
    / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
)
SOURCE_PREPARATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_canonical_case_surface_"
    "and_fresh_exact_admission_preparation_zero_call_proof_v1_0.json"
)
SOURCE_R4_ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_current_case_aware_"
    "delivery_identity_boundary_fresh_exact_admission_r4.json"
)
SOURCE_R4_FAILURE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_current_case_aware_"
    "delivery_identity_boundary_r4_exact_live_execution_failure_"
    "result_v1_0.json"
)
IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_runtime_audit_evidence_v2_"
    "and_material_numeric_classifier_minimum_zero_call_"
    "implementation_v1_0.json"
)
DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_runtime_audit_evidence_v2_"
    "and_material_numeric_classifier_fresh_agent_proof_decision_"
    "v1_0.json"
)
PROSPECTIVE_ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_runtime_audit_evidence_"
    "v2_and_material_numeric_classifier_fresh_exact_admission_r5.json"
)
EXECUTION_IDENTITY = (
    "fin01-s4-t06-mu-runtime-audit-evidence-v2-material-numeric-"
    "classifier-exact-live-r5"
)
PROSPECTIVE_ADMISSION_ID = (
    "fin01-s4-t06-mu-runtime-audit-evidence-v2-material-numeric-"
    "classifier-fresh-exact-admission-r5"
)
EXECUTION_MODE = (
    "exact_live_s4_mu_runtime_audit_evidence_v2_material_numeric_"
    "classifier_r5"
)
NEXT_ACTION = (
    "S4-T06-MU-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
    "CLASSIFIER-FRESH-EXACT-ADMISSION-R5-AUTHORITY-DECISION"
)


class S4T06AuditNumericFreshProofError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S4T06AuditNumericFreshProofError(code)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    return (
        resolved.relative_to(ROOT).as_posix()
        if resolved.is_relative_to(ROOT)
        else str(resolved)
    )


def _execution_counts(case_service: object, case_id: str) -> dict[str, int]:
    store = case_service._facade.store
    return {
        table: len(store.list_latest(table, case_id=case_id))
        for table in (
            "canonical_work_units",
            "canonical_attempts",
            "canonical_research_run_versions",
            "canonical_artifact_versions",
        )
    }


def _verify_implementation_bindings(
    implementation: Mapping[str, Any],
) -> dict[str, str]:
    bindings = {
        str(path): str(digest)
        for path, digest in implementation["exact_code_bindings"].items()
    }
    for relative_path, expected_digest in bindings.items():
        _require(
            _sha256(ROOT / relative_path) == expected_digest,
            f"implementation_code_binding_drift:{relative_path}",
        )
    return bindings


def _run_fixture_reproof() -> dict[str, Any]:
    test_v1_classifier_is_immutable_while_v2_allows_bound_period_labels()
    test_r4_two_path_reporting_period_replay_is_nonterminal_under_v2()
    material_classes = {
        "$4.1B 增长": "financial_amount",
        "84.6% 毛利率": "percentage",
        "120 days 库存": "measurement",
        "FY1900 展望": "unknown_reporting_period_label",
        "42 定性判断": "material_numeric_value",
    }
    for text, semantic_class in material_classes.items():
        test_v2_keeps_material_or_unknown_numeric_surfaces_fail_closed(
            text,
            semantic_class,
        )

    positive: dict[str, list[int]] = {}
    negative: dict[str, list[int]] = {}
    for ticker in ("DELL", "MU", "NVDA"):
        with pytest.MonkeyPatch.context() as monkeypatch:
            test_three_case_full_fake_uses_v2_capture_and_bound_period_classification(
                monkeypatch,
                ticker,
            )
        positive[ticker] = [6, 12, 12, 9]
        with pytest.MonkeyPatch.context() as monkeypatch:
            test_three_case_material_failure_binds_safe_path_class_and_capture_sequence(
                monkeypatch,
                ticker,
            )
        negative[ticker] = [1, 1, 0]

    with tempfile.TemporaryDirectory(
        prefix="fin01-s4-t06-audit-v2-atomic-replay-"
    ) as temp_dir:
        test_v2_failure_capture_is_atomic_replayable_indexed_and_not_promoted(
            Path(temp_dir)
        )
    with tempfile.TemporaryDirectory(
        prefix="fin01-s4-t06-audit-v2-secret-rejection-"
    ) as temp_dir:
        test_v2_rejects_credential_bearing_request_before_terminal_write(
            Path(temp_dir)
        )

    return {
        "historical_v1_semantics_immutable": True,
        "R4_safe_paths": [
            "$.fact_layer[0].statement",
            "$.explanation_layer[0]",
        ],
        "R4_semantic_class": "reporting_period_label",
        "R4_terminal": False,
        "material_numeric_semantic_classes_terminal": sorted(
            set(material_classes.values())
        ),
        "three_case_positive_nodes_callbacks_captures_artifacts": positive,
        "three_case_negative_callbacks_captures_artifacts": negative,
        "capture_v2_atomic_replay_and_nonpromotion": True,
        "credential_bearing_request_rejected_before_terminal_write": True,
    }


def prepare(
    *,
    runtime_root: Path = RUNTIME_ROOT,
    source_preparation_path: Path = SOURCE_PREPARATION,
    source_r4_admission_path: Path = SOURCE_R4_ADMISSION,
    source_r4_failure_path: Path = SOURCE_R4_FAILURE,
    implementation_path: Path = IMPLEMENTATION,
    require_prospective_absent: bool = True,
) -> dict[str, Any]:
    runtime_root = runtime_root.resolve()
    canonical_root = runtime_root / "canonical-runtime"
    database_path = canonical_root / "canonical.sqlite"
    object_root = canonical_root / "objects"
    source_preparation = _load(source_preparation_path)
    source_admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(source_r4_admission_path)
    )
    source_failure = _load(source_r4_failure_path)
    implementation = _load(implementation_path)
    materialization = source_preparation["canonical_materialization"]
    case_id = str(materialization["case_id"])
    decision_surface_ref = str(
        materialization["decision_surface_contract_ref"]
    )

    _require(
        implementation["status"]
        == (
            "pass_zero_call_runtime_injected_three_case_fixture_proven_"
            "fresh_agent_proof_pending_no_R5"
        ),
        "implementation_not_fixture_proven",
    )
    implementation_bindings = _verify_implementation_bindings(
        implementation
    )
    _require(
        source_failure["status"]
        == (
            "terminal_failed_new_numeric_narrative_L1_no_R5_no_"
            "paired_no_owner"
        ),
        "immutable_R4_failure_record_status_mismatch",
    )
    _require(
        source_failure["first_credible_failure"]["failure_code"]
        == "s4_case_numeric_authority_provider_narrative_invalid",
        "immutable_R4_failure_code_mismatch",
    )
    _require(
        source_admission.case_numeric_authority_policy_ref
        != S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF,
        "immutable_R4_numeric_policy_history_changed",
    )
    _require(
        source_admission.provider_output_capture_policy_ref
        != S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF,
        "immutable_R4_capture_policy_history_changed",
    )
    _require(
        source_admission.case_delivery_identity_policy_ref
        == S4_CASE_DELIVERY_IDENTITY_CURRENT_CASE_AWARE_POLICY_REF,
        "immutable_R4_identity_policy_history_changed",
    )
    fixture_reproof = _run_fixture_reproof()

    before_database_digest = _sha256(database_path)
    before_object_digest = _tree_digest(object_root)
    before_snapshot = _logical_snapshot(database_path, case_id)

    binding = load_s4_case_runtime_binding(ROOT, "MU")
    source_pack = load_s4_source_grounded_input_pack(ROOT, "MU")
    mapping = compile_s4_case_evidence_role_group_mapping(binding)
    _require(
        [len(group.source_evidence_roles) for group in mapping.role_groups]
        == [4, 5, 5],
        "mu_role_group_shape_mismatch",
    )
    _require(mapping.exact_role_count == 14, "mu_exact_role_count_mismatch")

    with tempfile.TemporaryDirectory(
        prefix="fin01-s4-t06-audit-numeric-v2-fresh-proof-"
    ) as temp_dir:
        clone_runtime_root = Path(temp_dir) / runtime_root.name
        shutil.copytree(runtime_root, clone_runtime_root)
        case_service, _, evidence_service = _services(clone_runtime_root)
        clone_before = _execution_counts(case_service, case_id)
        first = prepare_s4_source_grounded_exact_input(
            case_service,
            evidence_service,
            binding,
            source_pack,
            case_id,
            _principal(),
            decision_surface_contract_ref=decision_surface_ref,
            execution_identity=EXECUTION_IDENTITY,
        )
        second = prepare_s4_source_grounded_exact_input(
            case_service,
            evidence_service,
            binding,
            source_pack,
            case_id,
            _principal(),
            decision_surface_contract_ref=decision_surface_ref,
            execution_identity=EXECUTION_IDENTITY,
        )
        clone_after = _execution_counts(case_service, case_id)

    first_payload = first.model_dump(mode="json")
    _require(
        first_payload == second.model_dump(mode="json"),
        "double_prepare_parity_failed",
    )
    _require(clone_before == clone_after, "prepare_created_clone_state")
    _require(
        first.work_unit_id not in before_snapshot["work_unit_ids"],
        "fresh_work_unit_reused",
    )
    _require(
        first.attempt_id not in before_snapshot["attempt_ids"],
        "fresh_attempt_reused",
    )
    _require(
        first.research_run_id not in before_snapshot["research_run_ids"],
        "fresh_research_run_reused",
    )
    _require(
        first.input_digest == source_admission.input_digest,
        "exact_MU_input_digest_changed",
    )

    prospective_admission = (
        compile_s4_case_runtime_mandatory_safety_admission(
            source_admission,
            updates={
                "admission_id": PROSPECTIVE_ADMISSION_ID,
                "execution_mode": EXECUTION_MODE,
                "input_digest": first.input_digest,
                "case_numeric_authority_policy_ref": (
                    S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF
                ),
                "provider_output_capture_policy_ref": (
                    S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF
                ),
            },
        )
    )
    prospective_admission.assert_profile_admissible()
    _require(
        prospective_admission.case_numeric_authority_policy_ref
        == S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF,
        "material_numeric_classifier_v2_not_bound",
    )
    _require(
        prospective_admission.provider_output_capture_policy_ref
        == S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF,
        "provider_interaction_capture_v2_not_bound",
    )
    _require(
        prospective_admission.case_delivery_identity_policy_ref
        == S4_CASE_DELIVERY_IDENTITY_CURRENT_CASE_AWARE_POLICY_REF,
        "current_case_identity_v2_not_preserved",
    )
    _require(
        prospective_admission.research_lead_transport_ref
        == S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF,
        "research_lead_v7_not_preserved",
    )
    _require(
        prospective_admission.transport_ref
        == S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
        "specialist_v7_not_preserved",
    )
    callback_calls = 0

    def _must_not_call_provider(**_: Any) -> dict[str, Any]:
        nonlocal callback_calls
        callback_calls += 1
        raise AssertionError("provider_callback_forbidden_in_fresh_proof")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        prospective_admission,
        chat_completion_fn=_must_not_call_provider,
    )
    _require(callback_calls == 0, "provider_callback_called")
    if require_prospective_absent:
        _require(
            not PROSPECTIVE_ADMISSION.exists(),
            "prospective_admission_already_exists",
        )

    after_snapshot = _logical_snapshot(database_path, case_id)
    _require(before_snapshot == after_snapshot, "target_logical_state_changed")
    _require(
        before_database_digest == _sha256(database_path),
        "target_database_changed",
    )
    _require(
        before_object_digest == _tree_digest(object_root),
        "target_object_tree_changed",
    )

    admission_payload = prospective_admission.digest_payload()
    prospective_digest = canonical_digest(admission_payload)
    roundtrip = S3ThreeCellBoundedAgentAdmission.model_validate(
        admission_payload
    )
    _require(
        canonical_digest(roundtrip.digest_payload()) == prospective_digest,
        "prospective_admission_roundtrip_digest_drift",
    )

    return {
        "schema_version": (
            "fin_ia_0_1_s4_t06_runtime_audit_evidence_v2_and_material_"
            "numeric_classifier_fresh_agent_proof_decision_v1_0"
        ),
        "decision_id": (
            "S4-T06-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
            "CLASSIFIER-FRESH-AGENT-PROOF-DECISION"
        ),
        "recorded_at": "2026-07-30T03:30:00+08:00",
        "status": (
            "pass_zero_call_double_disposable_runtime_fresh_proof_"
            "R5_admission_not_authorized"
        ),
        "authority": {
            "user_instruction": "继续",
            "proof_step_authorized": True,
            "model_provider_network_calls_authorized": False,
            "R5_admission_issuance_authorized": False,
            "R5_exact_live_authorized": False,
        },
        "source_refs": {
            "implementation": _display_path(implementation_path),
            "canonical_preparation": _display_path(
                source_preparation_path
            ),
            "immutable_consumed_R4_admission": _display_path(
                source_r4_admission_path
            ),
            "immutable_R4_failure": _display_path(
                source_r4_failure_path
            ),
        },
        "implementation_reaudit": {
            "implementation_sha256": _sha256(implementation_path),
            "exact_code_bindings": implementation_bindings,
            "capture_v2_ref": (
                S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF
            ),
            "material_numeric_classifier_v2_ref": (
                S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF
            ),
            "current_case_identity_v2_ref": (
                S4_CASE_DELIVERY_IDENTITY_CURRENT_CASE_AWARE_POLICY_REF
            ),
        },
        "independent_fixture_reproof": fixture_reproof,
        "fresh_identity": {
            "execution_identity": EXECUTION_IDENTITY,
            "case_id": case_id,
            "case_version": int(materialization["case_version"]),
            "decision_surface_contract_ref": decision_surface_ref,
            "work_unit_id": first.work_unit_id,
            "attempt_id": first.attempt_id,
            "research_run_id": first.research_run_id,
            "input_digest": first.input_digest,
            "preparation_digest": first.preparation_digest,
            "role_group_mapping_digest": first.role_group_mapping_digest,
            "evidence_alignment_digest": first.evidence_alignment_digest,
            "evidence_dispatch_digest": first.evidence_dispatch_digest,
        },
        "double_prepare": {
            "equal": True,
            "prepared_payload_digest": canonical_digest(first_payload),
            "clone_execution_counts_before": clone_before,
            "clone_execution_counts_after": clone_after,
        },
        "prospective_R5_admission": {
            "payload": admission_payload,
            "digest": prospective_digest,
            "capture_v2_and_numeric_classifier_v2_bound": True,
            "current_case_identity_v2_preserved": True,
            "research_lead_v7_preserved": True,
            "specialist_v7_preserved": True,
            "prospective_admission_file": _display_path(
                PROSPECTIVE_ADMISSION
            ),
            "prospective_admission_file_absent_at_proof": True,
            "issued": False,
            "consumed": False,
            "execution_started": False,
        },
        "target_read_only_audit": {
            "canonical_database_sha256": before_database_digest,
            "canonical_object_tree_sha256": before_object_digest,
            "logical_snapshot_digest": canonical_digest(before_snapshot),
            "target_state_unchanged": True,
        },
        "hard_boundaries": {
            "model_calls": 0,
            "provider_calls": callback_calls,
            "network_calls": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
            "admissions_issued": 0,
            "admissions_consumed": 0,
            "target_canonical_writes": 0,
            "target_object_writes": 0,
            "paired_assessments": 0,
            "owner_acceptances": 0,
            "T07_entries": 0,
        },
        "future_success_contract": {
            "terminal_state": "succeeded",
            "logical_nodes": 6,
            "provider_calls": 12,
            "provider_output_captures": 12,
            "logical_artifact_families": 9,
            "independent_final_artifact_L1_required": True,
            "paired_L1_to_L4_required": True,
            "owner_acceptance_only_after_L1_pass_and_agent_gain": True,
        },
        "stop_rule": {
            "R5_admission_requires_separate_authority_decision": True,
            "R5_exact_live_requires_separate_authority": True,
            "automatic_R6": False,
            "first_new_L1_failure_stops_without_R6": True,
        },
        "next_action": NEXT_ACTION,
        "next_action_authorized": False,
    }


def build_decision(
    *,
    runtime_root: Path = RUNTIME_ROOT,
    require_prospective_absent: bool = True,
) -> dict[str, Any]:
    kwargs = {
        "runtime_root": runtime_root,
        "require_prospective_absent": require_prospective_absent,
    }
    first = prepare(**kwargs)
    second = prepare(**kwargs)
    _require(first == second, "independent_proof_outputs_differ")
    result = deepcopy(first)
    result["proof_generator"] = {
        "ref": _display_path(Path(__file__)),
        "sha256": _sha256(Path(__file__)),
        "independent_invocations": 2,
        "independent_outputs_equal": True,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=RUNTIME_ROOT)
    parser.add_argument("--output", type=Path, default=DECISION)
    args = parser.parse_args()
    result = build_decision(runtime_root=args.runtime_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
