from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_V2_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
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
from test_fin_0_1_s4_t06_mu_case_runtime_mandatory_material_truth_identity_safety_closure_zero_call_implementation import (
    test_final_mu_artifact_envelope_rejects_projection_numeric_and_identity_mutations,
)
from test_fin_0_1_s4_t06_mu_deterministic_judgment_atom_planner_compiled_contract_implementation import (
    test_downstream_failure_preserves_all_prior_and_failing_capture,
    test_three_case_compiled_atom_full_fake_reaches_12_calls_and_9_artifacts,
    test_wwc_candidate_boundary_selects_at_most_three_after_validation,
    test_wwc_candidate_count_outside_one_to_six_fails_closed,
    test_wwc_candidate_permutation_has_stable_selected_result,
    test_wwc_exact_duplicate_fails_before_selection,
    test_wwc_validates_all_six_candidates_before_selection,
)
from test_fin_0_1_s4_t06_mu_temporal_authority_and_terminal_result_zero_call_implementation import (
    test_runner_uses_admission_bound_capture_v2_and_materializes_failure_result,
)
from test_fin_0_1_s4_t06_mu_wwc_provider_candidate_validation_and_deterministic_final_selection_minimum_zero_call_implementation import (
    test_contract_separates_candidates_from_final_tasks,
    test_full_chain_and_final_artifact_audit_are_recorded,
    test_implementation_binds_current_runtime_and_test_bytes,
    test_implementation_consumes_one_zero_call_bundle_only,
)


RUNTIME_ROOT = ROOT / (
    ".codex_runtime/"
    "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
)
SOURCE_PREPARATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_canonical_case_surface_"
    "and_fresh_exact_admission_preparation_zero_call_proof_v1_0.json"
)
SOURCE_R7_ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_claim_epistemic_support_"
    "role_compiled_contract_v2_fresh_exact_admission_r7.json"
)
IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_wwc_provider_candidate_"
    "validation_and_deterministic_final_selection_minimum_zero_call_"
    "implementation_v1_0.json"
)
DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_wwc_stable_top3_"
    "replacement_independent_fresh_agent_proof_decision_v1_0.json"
)
PROSPECTIVE_ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_wwc_stable_top3_"
    "replacement_exact_admission_r1.json"
)
EXECUTION_IDENTITY = (
    "fin01-s4-t06-mu-wwc-stable-top3-replacement-exact-live-r1"
)
PROSPECTIVE_ADMISSION_ID = (
    "fin01-s4-t06-mu-wwc-stable-top3-replacement-exact-admission-r1"
)
EXECUTION_MODE = "exact_live_s4_mu_wwc_stable_top3_replacement_r1"
CURRENT_ACTION = (
    "S4-T06-MU-WWC-PROVIDER-CANDIDATE-VALIDATION-AND-DETERMINISTIC-"
    "FINAL-SELECTION-INDEPENDENT-FRESH-AGENT-PROOF-DECISION"
)
NEXT_ACTION = (
    "S4-T06-MU-WWC-STABLE-TOP3-REPLACEMENT-EXACT-LIVE-R1"
)


class S4T06WWCStableTop3FreshProofError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S4T06WWCStableTop3FreshProofError(code)


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


def _run_with_monkeypatch(
    test: Callable[..., None],
    *args: Any,
) -> None:
    with pytest.MonkeyPatch.context() as monkeypatch:
        test(monkeypatch, *args)


def _verify_implementation_bindings(
    implementation: Mapping[str, Any],
) -> dict[str, str]:
    bindings = {
        str(row["ref"]): str(row["sha256"])
        for row in implementation["runtime_changes"].values()
    }
    for relative_path, expected_digest in bindings.items():
        _require(
            _sha256(ROOT / relative_path) == expected_digest,
            f"implementation_code_binding_drift:{relative_path}",
        )
    return bindings


def _run_fixture_reproof() -> dict[str, Any]:
    test_implementation_consumes_one_zero_call_bundle_only()
    test_implementation_binds_current_runtime_and_test_bytes()
    test_contract_separates_candidates_from_final_tasks()
    test_full_chain_and_final_artifact_audit_are_recorded()

    positive: dict[str, list[int]] = {}
    for ticker in ("DELL", "MU", "NVDA"):
        _run_with_monkeypatch(
            test_three_case_compiled_atom_full_fake_reaches_12_calls_and_9_artifacts,
            ticker,
        )
        positive[ticker] = [6, 12, 12, 9]

    for candidate_count, selected_count in ((1, 1), (3, 3), (6, 3)):
        test_wwc_candidate_boundary_selects_at_most_three_after_validation(
            candidate_count,
            selected_count,
        )
    for candidate_count in (0, 7):
        test_wwc_candidate_count_outside_one_to_six_fails_closed(
            candidate_count
        )
    test_wwc_validates_all_six_candidates_before_selection()
    test_wwc_exact_duplicate_fails_before_selection()
    test_wwc_candidate_permutation_has_stable_selected_result()

    for request_marker, expected_capture_count in (
        ("research_lead_transport_ref", 10),
        ("memo_writer_transport_ref", 11),
        ("output_state_machine", 12),
    ):
        _run_with_monkeypatch(
            test_downstream_failure_preserves_all_prior_and_failing_capture,
            request_marker,
            expected_capture_count,
        )
    _run_with_monkeypatch(
        test_final_mu_artifact_envelope_rejects_projection_numeric_and_identity_mutations
    )
    with tempfile.TemporaryDirectory(
        prefix="fin01-s4-t06-terminal-materialization-proof-"
    ) as temp_dir:
        with pytest.MonkeyPatch.context() as monkeypatch:
            test_runner_uses_admission_bound_capture_v2_and_materializes_failure_result(
                Path(temp_dir),
                monkeypatch,
            )

    return {
        "three_case_positive_nodes_calls_captures_artifacts": positive,
        "candidate_counts": [0, 1, 3, 6, 7],
        "all_candidates_validated_before_selection": True,
        "invalid_candidate_silent_drop": False,
        "exact_duplicate_fail_closed": True,
        "permutation_stable": True,
        "downstream_failure_capture_sequences": [10, 11, 12],
        "final_artifact_numeric_identity_lineage_mutations_fail_closed": True,
        "terminal_result_materialized": True,
    }


def prepare(
    *,
    runtime_root: Path = RUNTIME_ROOT,
    source_preparation_path: Path = SOURCE_PREPARATION,
    source_r7_admission_path: Path = SOURCE_R7_ADMISSION,
    implementation_path: Path = IMPLEMENTATION,
    require_prospective_absent: bool = True,
) -> dict[str, Any]:
    runtime_root = runtime_root.resolve()
    canonical_root = runtime_root / "canonical-runtime"
    database_path = canonical_root / "canonical.sqlite"
    object_root = canonical_root / "objects"
    source_preparation = _load(source_preparation_path)
    source_admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(source_r7_admission_path)
    )
    implementation = _load(implementation_path)
    materialization = source_preparation["canonical_materialization"]
    case_id = str(materialization["case_id"])
    decision_surface_ref = str(
        materialization["decision_surface_contract_ref"]
    )

    _require(
        implementation["status"]
        == (
            "pass_WWC_candidate_validation_stable_top3_and_zero_call_"
            "full_chain_proven_independent_fresh_proof_pending"
        ),
        "implementation_not_current_fixture_proven",
    )
    implementation_bindings = _verify_implementation_bindings(
        implementation
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
        prefix="fin01-s4-t06-wwc-stable-top3-fresh-proof-"
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
                "judgment_atom_compiled_contract_ref": (
                    S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_V2_REF
                ),
            },
        )
    )
    prospective_admission.assert_profile_admissible()
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
            "prospective_replacement_admission_already_exists",
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
        "prospective_replacement_admission_roundtrip_digest_drift",
    )

    return {
        "schema_version": (
            "fin_ia_0_1_s4_t06_mu_wwc_stable_top3_replacement_"
            "independent_fresh_agent_proof_decision_v1_0"
        ),
        "decision_id": CURRENT_ACTION,
        "status": (
            "pass_zero_call_double_disposable_runtime_WWC_stable_top3_"
            "fresh_proof_replacement_exact_live_authorized_by_user_sequence"
        ),
        "authority": {
            "user_instruction": "按照这个顺序修",
            "proof_and_single_replacement_sequence_authorized": True,
            "model_provider_network_calls_during_proof": 0,
            "maximum_replacement_exact_lives_after_proof": 1,
            "automatic_second_replacement": False,
            "L2_to_L4_carry_forward_required": True,
        },
        "source_refs": {
            "implementation": _display(implementation_path),
            "canonical_preparation": _display(source_preparation_path),
            "immutable_consumed_R7_admission": _display(
                source_r7_admission_path
            ),
        },
        "implementation_reaudit": {
            "implementation_sha256": _sha256(implementation_path),
            "exact_code_bindings": implementation_bindings,
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
        "prospective_replacement_admission": {
            "payload": admission_payload,
            "digest": prospective_digest,
            "compiled_contract_v2_bound": True,
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
            "target_canonical_writes": 0,
            "target_object_writes": 0,
            "exact_live_runs": 0,
            "paired_assessments": 0,
            "owner_acceptances": 0,
            "T07_entries": 0,
        },
        "replacement_exact_live_contract": {
            "maximum_runs": 1,
            "terminal_state_required": "succeeded",
            "logical_nodes": 6,
            "provider_calls": 12,
            "provider_output_captures": 12,
            "logical_artifact_families": 9,
            "independent_final_artifact_L1_required": True,
            "paired_L1_to_L4_required": True,
            "owner_acceptance_only_after_L1_pass_and_agent_gain": True,
        },
        "stop_rule": {
            "new_L1_stops_without_second_replacement": True,
            "new_L1_allows_one_project_level_disposition_only": True,
            "automatic_field_patch": False,
            "L2_to_L4_block_T06": False,
            "L2_to_L4_carry_to": ["S4-T08", "S4-T09", "S4-T10", "S5"],
        },
        "stage_acceptance": {
            "engineering_pass": True,
            "RC_P36_083": "closed_independent_current_binding_proof_pass",
            "RC_P36_080": "open_replacement_live_product_proof_pending",
            "S4_T06": "engineering_pass_live_product_pass_pending",
            "paired_assessment": "not_started",
            "owner_acceptance": "not_started",
            "S4_T07": "not_entered",
        },
        "next_action": NEXT_ACTION,
        "next_action_authorized": True,
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
    result["recorded_at"] = datetime.now(
        ZoneInfo("Asia/Shanghai")
    ).isoformat(timespec="seconds")
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
