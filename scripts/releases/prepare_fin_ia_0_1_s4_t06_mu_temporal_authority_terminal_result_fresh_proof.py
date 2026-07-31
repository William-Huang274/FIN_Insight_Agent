from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF,
    S4_SPECIALIST_WWC_TEMPORAL_AUTHORITY_POLICY_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF,
    S3_TASK_CLAIM_LINK_POLICY_REF,
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
from test_fin_0_1_s4_t06_mu_temporal_authority_and_terminal_result_zero_call_implementation import (
    test_capture_v1_constant_remains_available_for_historical_admissions,
    test_runner_uses_admission_bound_capture_v2_and_materializes_failure_result,
    test_supervised_failure_receipt_hashes_final_stderr_without_provider_call,
    test_temporal_v2_does_not_weaken_material_financial_number_gate,
    test_temporal_v2_is_versioned_and_v1_schema_is_immutable,
    test_three_case_temporal_authority_full_fake_reaches_twelve_calls_and_nine_artifacts,
    test_unknown_temporal_alias_fails_closed_with_typed_atom_telemetry,
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
SOURCE_R5_ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_runtime_audit_evidence_v2_"
    "and_material_numeric_classifier_fresh_exact_admission_r5.json"
)
SOURCE_R5_FAILURE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_runtime_audit_evidence_v2_"
    "and_material_numeric_classifier_r5_exact_live_execution_failure_"
    "result_v1_0.json"
)
IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_action_planning_temporal_"
    "authority_and_capture_v2_terminal_result_materialization_minimum_"
    "zero_call_implementation_v1_0.json"
)
DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_action_planning_temporal_"
    "authority_and_capture_v2_terminal_result_materialization_fresh_"
    "agent_proof_decision_v1_0.json"
)
PROSPECTIVE_ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_action_planning_temporal_"
    "authority_and_capture_v2_terminal_result_materialization_fresh_"
    "exact_admission_r6.json"
)
EXECUTION_IDENTITY = (
    "fin01-s4-t06-mu-temporal-authority-terminal-result-exact-live-r6"
)
PROSPECTIVE_ADMISSION_ID = (
    "fin01-s4-t06-mu-temporal-authority-terminal-result-fresh-exact-"
    "admission-r6"
)
EXECUTION_MODE = (
    "exact_live_s4_mu_temporal_authority_terminal_result_r6"
)
CURRENT_ACTION = (
    "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
    "TERMINAL-RESULT-MATERIALIZATION-FRESH-AGENT-PROOF-DECISION"
)
NEXT_ACTION = (
    "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
    "TERMINAL-RESULT-MATERIALIZATION-FRESH-EXACT-ADMISSION-R6-"
    "AUTHORITY-DECISION"
)


class S4T06TemporalFreshProofError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S4T06TemporalFreshProofError(code)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _display(path: Path) -> str:
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
        str(row["ref"]): str(row["sha256"])
        for row in implementation["code_bindings"]
    }
    for relative_path, expected_digest in bindings.items():
        _require(
            _sha256(ROOT / relative_path) == expected_digest,
            f"implementation_code_binding_drift:{relative_path}",
        )
    return bindings


def _run_fixture_reproof() -> dict[str, Any]:
    test_temporal_v2_is_versioned_and_v1_schema_is_immutable()
    test_capture_v1_constant_remains_available_for_historical_admissions()

    positive: dict[str, list[int]] = {}
    for ticker in ("DELL", "MU", "NVDA"):
        with pytest.MonkeyPatch.context() as monkeypatch:
            test_three_case_temporal_authority_full_fake_reaches_twelve_calls_and_nine_artifacts(
                monkeypatch,
                ticker,
            )
        positive[ticker] = [6, 12, 12, 9]

    with pytest.MonkeyPatch.context() as monkeypatch:
        test_unknown_temporal_alias_fails_closed_with_typed_atom_telemetry(
            monkeypatch
        )
    with pytest.MonkeyPatch.context() as monkeypatch:
        test_temporal_v2_does_not_weaken_material_financial_number_gate(
            monkeypatch
        )

    with tempfile.TemporaryDirectory(
        prefix="fin01-s4-t06-temporal-runner-proof-"
    ) as temp_dir:
        with pytest.MonkeyPatch.context() as monkeypatch:
            with redirect_stdout(io.StringIO()):
                test_runner_uses_admission_bound_capture_v2_and_materializes_failure_result(
                    Path(temp_dir),
                    monkeypatch,
                )
    with tempfile.TemporaryDirectory(
        prefix="fin01-s4-t06-supervision-final-log-proof-"
    ) as temp_dir:
        test_supervised_failure_receipt_hashes_final_stderr_without_provider_call(
            Path(temp_dir)
        )
        time.sleep(0.5)

    return {
        "historical_WWC_v1_and_capture_v1_immutable": True,
        "typed_temporal_policy_ref": (
            S4_SPECIALIST_WWC_TEMPORAL_AUTHORITY_POLICY_REF
        ),
        "provider_authored_calendar_text_allowed": False,
        "request_local_ISO_date_aliases": True,
        "local_bound_date_next_quarter_and_unscheduled_rendering": True,
        "three_case_positive_nodes_callbacks_captures_artifacts": positive,
        "unknown_date_alias_typed_failure": True,
        "material_financial_number_L1_failure": True,
        "admission_bound_capture_v2_terminal_result_materialized": True,
        "supervision_final_stderr_digest_match": True,
    }


def prepare(
    *,
    runtime_root: Path = RUNTIME_ROOT,
    source_preparation_path: Path = SOURCE_PREPARATION,
    source_r5_admission_path: Path = SOURCE_R5_ADMISSION,
    source_r5_failure_path: Path = SOURCE_R5_FAILURE,
    implementation_path: Path = IMPLEMENTATION,
    require_prospective_absent: bool = True,
) -> dict[str, Any]:
    runtime_root = runtime_root.resolve()
    canonical_root = runtime_root / "canonical-runtime"
    database_path = canonical_root / "canonical.sqlite"
    object_root = canonical_root / "objects"
    source_preparation = _load(source_preparation_path)
    source_admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(source_r5_admission_path)
    )
    source_failure = _load(source_r5_failure_path)
    implementation = _load(implementation_path)
    materialization = source_preparation["canonical_materialization"]
    case_id = str(materialization["case_id"])
    decision_surface_ref = str(
        materialization["decision_surface_contract_ref"]
    )

    _require(
        implementation["status"]
        == (
            "pass_zero_call_implementation_fixture_proven_"
            "fresh_agent_proof_pending"
        ),
        "implementation_not_fixture_proven",
    )
    implementation_bindings = _verify_implementation_bindings(
        implementation
    )
    _require(
        source_failure["status"]
        == (
            "terminal_failed_admission_consumed_no_retry_no_artifact_"
            "runner_result_materialization_failed"
        ),
        "immutable_R5_failure_record_status_mismatch",
    )
    _require(
        source_failure["first_credible_failure"]["failure_code"]
        == "s4_case_numeric_authority_provider_narrative_invalid",
        "immutable_R5_failure_code_mismatch",
    )
    _require(
        source_failure["first_credible_failure"][
            "planning_deadline_authority_violation_established"
        ]
        is True,
        "immutable_R5_temporal_violation_missing",
    )
    _require(
        source_failure["first_credible_failure"][
            "financial_fact_error_established"
        ]
        is False,
        "immutable_R5_financial_fact_classification_changed",
    )
    _require(
        source_admission.wwc_judgment_atom_policy_ref is None,
        "immutable_R5_temporal_policy_history_changed",
    )
    _require(
        source_admission.transport_ref
        != S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF,
        "immutable_R5_specialist_transport_history_changed",
    )
    _require(
        source_admission.provider_output_capture_policy_ref
        == S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF,
        "immutable_R5_capture_v2_history_changed",
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
        prefix="fin01-s4-t06-temporal-fresh-proof-"
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
                "transport_ref": (
                    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF
                ),
                "task_claim_link_policy_ref": (
                    S3_TASK_CLAIM_LINK_POLICY_REF
                ),
                "wwc_judgment_atom_policy_ref": (
                    S4_SPECIALIST_WWC_TEMPORAL_AUTHORITY_POLICY_REF
                ),
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
        prospective_admission.wwc_judgment_atom_policy_ref
        == S4_SPECIALIST_WWC_TEMPORAL_AUTHORITY_POLICY_REF,
        "temporal_authority_v2_not_bound",
    )
    _require(
        prospective_admission.transport_ref
        == S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF,
        "specialist_v8_not_bound",
    )
    _require(
        prospective_admission.task_claim_link_policy_ref
        == S3_TASK_CLAIM_LINK_POLICY_REF,
        "task_claim_link_policy_not_bound",
    )
    _require(
        prospective_admission.provider_output_capture_policy_ref
        == S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF,
        "provider_interaction_capture_v2_not_bound",
    )
    _require(
        prospective_admission.case_numeric_authority_policy_ref
        == S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF,
        "material_numeric_classifier_v2_not_bound",
    )
    _require(
        prospective_admission.research_lead_transport_ref
        == S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF,
        "research_lead_v7_not_preserved",
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
            "prospective_R6_admission_already_exists",
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
        "prospective_R6_admission_roundtrip_digest_drift",
    )

    return {
        "schema_version": (
            "fin_ia_0_1_s4_t06_temporal_authority_terminal_result_"
            "fresh_agent_proof_decision_v1_0"
        ),
        "decision_id": CURRENT_ACTION,
        "recorded_at": "2026-07-30T20:30:00+08:00",
        "status": (
            "pass_zero_call_double_disposable_runtime_fresh_proof_"
            "R6_admission_not_authorized"
        ),
        "authority": {
            "user_instruction": "继续",
            "proof_step_authorized": True,
            "model_provider_network_calls_authorized": False,
            "R6_admission_issuance_authorized": False,
            "R6_exact_live_authorized": False,
        },
        "source_refs": {
            "implementation": _display(implementation_path),
            "canonical_preparation": _display(source_preparation_path),
            "immutable_consumed_R5_admission": _display(
                source_r5_admission_path
            ),
            "immutable_R5_failure": _display(source_r5_failure_path),
        },
        "implementation_reaudit": {
            "implementation_sha256": _sha256(implementation_path),
            "exact_code_bindings": implementation_bindings,
            "typed_temporal_authority_ref": (
                S4_SPECIALIST_WWC_TEMPORAL_AUTHORITY_POLICY_REF
            ),
            "capture_v2_ref": (
                S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF
            ),
            "material_numeric_classifier_v2_ref": (
                S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF
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
        "prospective_R6_admission": {
            "payload": admission_payload,
            "digest": prospective_digest,
            "temporal_v2_specialist_v8_task_claim_bound": True,
            "capture_v2_numeric_v2_identity_v2_preserved": True,
            "research_lead_v7_preserved": True,
            "prospective_admission_file": _display(
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
            "exact_live_runs": 0,
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
            "R6_admission_requires_separate_authority_decision": True,
            "R6_exact_live_requires_separate_authority": True,
            "automatic_R7": False,
            "new_L1_after_future_exact_live_blocks_agent_authored_surface": True,
            "second_temporal_implementation_bundle_allowed": False,
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
        "ref": _display(Path(__file__)),
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
