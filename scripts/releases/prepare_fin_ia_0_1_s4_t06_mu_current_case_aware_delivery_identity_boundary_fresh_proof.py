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
    S4_CASE_DELIVERY_IDENTITY_REGISTRY_REF,
    S4_CASE_NUMERIC_AUTHORITY_POLICY_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
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
from test_fin_0_1_s4_t06_mu_current_case_aware_delivery_identity_boundary_zero_call_implementation import (
    test_every_provider_phase_rejects_nonlocal_registered_identity,
    test_three_case_natural_current_ticker_full_fake_reaches_six_twelve_nine,
    test_v2_nonlocal_failure_telemetry_is_canonically_registered,
    test_v2_projection_and_final_delivery_owner_reject_mutation,
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
SOURCE_ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_mandatory_material_truth_"
    "identity_safety_closure_fresh_exact_admission_r3.json"
)
SOURCE_R3_FAILURE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_mandatory_material_truth_"
    "identity_safety_closure_r3_exact_live_execution_failure_result_"
    "v1_0.json"
)
IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_current_case_aware_"
    "delivery_identity_boundary_scope_replacement_minimum_zero_call_"
    "implementation_v1_0.json"
)
DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_current_case_aware_"
    "delivery_identity_boundary_fresh_agent_proof_decision_v1_0.json"
)
PROSPECTIVE_ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_current_case_aware_"
    "delivery_identity_boundary_fresh_exact_admission_r4.json"
)
EXECUTION_IDENTITY = (
    "fin01-s4-t06-mu-current-case-aware-delivery-identity-boundary-"
    "exact-live-r4"
)
PROSPECTIVE_ADMISSION_ID = (
    "fin01-s4-t06-mu-current-case-aware-delivery-identity-boundary-"
    "fresh-exact-admission-r4"
)
EXECUTION_MODE = (
    "exact_live_s4_mu_current_case_aware_delivery_identity_boundary_r4"
)
NEXT_ACTION = (
    "S4-T06-MU-CURRENT-CASE-AWARE-DELIVERY-IDENTITY-BOUNDARY-"
    "FRESH-EXACT-ADMISSION-R4"
)


class S4T06MuIdentityBoundaryFreshProofError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S4T06MuIdentityBoundaryFreshProofError(code)


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
    case_results: dict[str, list[int]] = {}
    for ticker in ("DELL", "MU", "NVDA"):
        with pytest.MonkeyPatch.context() as monkeypatch:
            test_three_case_natural_current_ticker_full_fake_reaches_six_twelve_nine(
                monkeypatch,
                ticker,
            )
        case_results[ticker] = [6, 12, 12, 9]
    phase_counts = {
        "specialist": 1,
        "research_lead": 10,
        "memo_writer": 11,
        "verifier": 12,
    }
    for phase, expected_call_count in phase_counts.items():
        with pytest.MonkeyPatch.context() as monkeypatch:
            test_every_provider_phase_rejects_nonlocal_registered_identity(
                monkeypatch,
                phase,
                expected_call_count,
            )
    test_v2_projection_and_final_delivery_owner_reject_mutation()
    test_v2_nonlocal_failure_telemetry_is_canonically_registered()
    return {
        "three_case_natural_current_ticker_final_path": case_results,
        "registered_nonlocal_mutation_rejected_by_phase": phase_counts,
        "final_9_artifact_identity_mutation_rejected": True,
        "canonical_typed_failure_registration_recomputed": True,
    }


def prepare(
    *,
    runtime_root: Path = RUNTIME_ROOT,
    source_preparation_path: Path = SOURCE_PREPARATION,
    source_admission_path: Path = SOURCE_ADMISSION,
    source_r3_failure_path: Path = SOURCE_R3_FAILURE,
    implementation_path: Path = IMPLEMENTATION,
    require_prospective_absent: bool = True,
) -> dict[str, Any]:
    runtime_root = runtime_root.resolve()
    canonical_root = runtime_root / "canonical-runtime"
    database_path = canonical_root / "canonical.sqlite"
    object_root = canonical_root / "objects"
    source_preparation = _load(source_preparation_path)
    source_admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(source_admission_path)
    )
    source_r3_failure = _load(source_r3_failure_path)
    implementation = _load(implementation_path)
    materialization = source_preparation["canonical_materialization"]
    case_id = str(materialization["case_id"])
    decision_surface_ref = str(
        materialization["decision_surface_contract_ref"]
    )

    _require(
        implementation["status"]
        == "pass_single_zero_call_replacement_bundle_fixture_proven_"
        "fresh_agent_proof_pending",
        "implementation_not_fixture_proven",
    )
    implementation_bindings = _verify_implementation_bindings(
        implementation
    )
    _require(
        source_r3_failure["status"]
        == (
            "terminal_failed_first_specialist_identity_policy_"
            "overconstraint_no_retry_no_paired_assessment"
        ),
        "immutable_R3_failure_record_status_mismatch",
    )
    _require(
        source_r3_failure["first_credible_failure"]["failure_code"]
        == "s4_case_delivery_identity_provider_narrative_invalid",
        "immutable_R3_failure_code_mismatch",
    )
    _require(
        source_admission.case_delivery_identity_policy_ref
        == "fin01.s4.case_delivery_identity_projection:v1",
        "immutable_R3_identity_policy_history_changed",
    )
    _require(
        source_admission.research_lead_transport_ref
        == S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF,
        "source_R3_lead_transport_is_not_v7",
    )
    _require(
        source_admission.transport_ref
        == S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
        "source_R3_specialist_transport_is_not_v7",
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
        prefix="fin01-s4-t06-mu-identity-v2-fresh-proof-"
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
            },
        )
    )
    prospective_admission.assert_profile_admissible()
    _require(
        prospective_admission.case_numeric_authority_policy_ref
        == S4_CASE_NUMERIC_AUTHORITY_POLICY_REF,
        "numeric_authority_policy_not_bound",
    )
    _require(
        prospective_admission.case_delivery_identity_policy_ref
        == S4_CASE_DELIVERY_IDENTITY_CURRENT_CASE_AWARE_POLICY_REF,
        "current_case_aware_identity_policy_not_bound",
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
            "fin_ia_0_1_s4_t06_mu_current_case_aware_delivery_identity_"
            "boundary_fresh_agent_proof_decision_v1_0"
        ),
        "decision_id": (
            "S4-T06-MU-CURRENT-CASE-AWARE-DELIVERY-IDENTITY-BOUNDARY-"
            "FRESH-AGENT-PROOF-DECISION"
        ),
        "recorded_at": "2026-07-29T23:20:00+08:00",
        "status": (
            "pass_zero_call_independent_fresh_proof_contract_frozen_"
            "R4_admission_issuance_authorized_by_user"
        ),
        "authority": {
            "user_instruction": (
                "按这个顺序继续做T06，看看这轮t06 exact-live做完后效果如何"
            ),
            "continuous_sequence_authority": True,
            "proof_step_model_provider_network_calls_authorized": False,
            "one_future_MU_R4_exact_live_authorized_after_issuance": True,
        },
        "source_refs": {
            "implementation": _display_path(implementation_path),
            "canonical_preparation": _display_path(source_preparation_path),
            "immutable_consumed_R3_admission": _display_path(
                source_admission_path
            ),
            "immutable_R3_failure": _display_path(source_r3_failure_path),
        },
        "implementation_reaudit": {
            "implementation_sha256": _sha256(implementation_path),
            "exact_code_bindings": implementation_bindings,
            "numeric_authority_policy_ref": (
                S4_CASE_NUMERIC_AUTHORITY_POLICY_REF
            ),
            "delivery_identity_policy_ref": (
                S4_CASE_DELIVERY_IDENTITY_CURRENT_CASE_AWARE_POLICY_REF
            ),
            "case_identity_registry_ref": (
                S4_CASE_DELIVERY_IDENTITY_REGISTRY_REF
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
        "prospective_admission": {
            "payload": admission_payload,
            "digest": prospective_digest,
            "numeric_and_identity_v2_pair_bound": True,
            "research_lead_v7_bound": True,
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
            "human_reviews": 0,
        },
        "stop_rule": {
            "second_identity_repair_bundle_allowed": False,
            "MU_R4_maximum_exact_live_attempts": 1,
            "first_new_L1_failure_stops_without_R5": True,
        },
        "next_action": NEXT_ACTION,
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
