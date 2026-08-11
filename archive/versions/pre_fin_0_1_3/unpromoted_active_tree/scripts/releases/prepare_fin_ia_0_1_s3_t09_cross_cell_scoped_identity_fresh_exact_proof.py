from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V4_REF,
    S3_OWNER_GRADE_RESEARCH_LEAD_V2_AGGREGATE_OUTPUT_TOKEN_BUDGET,
    S3_OWNER_GRADE_RESEARCH_LEAD_V2_STAGE_OUTPUT_TOKEN_BUDGETS,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
    S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
)
from apps.workbench.backend.application.bounded_agent_identity_policies import (
    S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_owner_grade_v3_segmented_exact_admission_decision import (
    prepare as _prepare_segmented_decision,
)


EXECUTION_IDENTITY = (
    "fin01-s3-t09-three-cell-deepseek-cross-cell-scoped-identity-"
    "output-v4-live-validation-r1"
)
PROSPECTIVE_ADMISSION_ID = (
    "fin01-s3-t09-three-cell-deepseek-cross-cell-scoped-identity-"
    "output-v4-exact-admission-r1"
)
PROSPECTIVE_ADMISSION_FILE = (
    "configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_cross_cell_"
    "scoped_identity_output_v4_exact_admission_r1.json"
)
IMPLEMENTATION_STATUS = (
    "pass_zero_call_cross_cell_scoped_identity_and_safe_collision_telemetry_"
    "fixture_proven_fresh_agent_proof_decision_pending"
)
DECISION_STATUS = (
    "pass_zero_call_cross_cell_scoped_identity_output_v4_fresh_exact_"
    "proof_contract_frozen_admission_issuance_pending_separate_authority"
)
NEXT_ACTION = (
    "S3-T09-OWNER-GRADE-CROSS-CELL-SCOPED-IDENTITY-"
    "FRESH-EXACT-ADMISSION-ISSUANCE"
)


class ScopedIdentityFreshProofDecisionError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ScopedIdentityFreshProofDecisionError(code)


def _prior_failed_results(releases: Path) -> tuple[Path, ...]:
    return (
        releases
        / "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_fresh_live_execution_result_v1_0.json",
        releases
        / "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_text_contract_v2_fresh_live_execution_result_v1_0.json",
        releases
        / "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_transport_v3_fresh_live_execution_result_v1_0.json",
        releases
        / "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_transport_v4_fresh_live_execution_result_v1_0.json",
        releases
        / "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_transport_v5_fresh_live_execution_result_v1_0.json",
        releases
        / "fin_ia_0_1_s3_t09_owner_grade_v3_research_lead_v2_fresh_live_execution_result_v1_0.json",
        releases
        / "fin_ia_0_1_s3_t09_owner_grade_v3_research_lead_v3_orphan_typed_closeout_result_v1_0.json",
        releases
        / "fin_ia_0_1_s3_t09_owner_grade_v3_writer_v2_fresh_live_execution_result_v1_0.json",
        releases
        / "fin_ia_0_1_s3_t09_owner_grade_v3_specialist_v6_fresh_live_execution_result_v1_0.json",
        releases
        / "fin_ia_0_1_s3_t09_owner_grade_specialist_v7_fresh_live_execution_result_v1_0.json",
        releases
        / "fin_ia_0_1_s3_t09_owner_grade_specialist_v7_fresh_r2_live_execution_result_v1_0.json",
    )


def _prepare_once(
    *,
    runtime_root: Path,
    implementation_result_path: Path,
) -> dict[str, Any]:
    releases = ROOT / "configs" / "releases"
    return _prepare_segmented_decision(
        runtime_root=runtime_root,
        baseline_result_path=releases
        / "fin_ia_0_1_s3_t09_paired_deterministic_baseline_materialization_v1_0.json",
        paired_decision_path=releases
        / "fin_ia_0_1_s3_t09_replacement_live_artifact_paired_baseline_decision_v1_0.json",
        monolithic_v3_result_path=releases
        / "fin_ia_0_1_s3_t09_owner_grade_v3_fresh_live_execution_result_v1_0.json",
        transport_implementation_result_path=implementation_result_path,
        additional_prior_failed_result_paths=_prior_failed_results(releases),
        execution_identity=EXECUTION_IDENTITY,
        prospective_admission_id=PROSPECTIVE_ADMISSION_ID,
        prospective_admission_file=PROSPECTIVE_ADMISSION_FILE,
        execution_mode=(
            "exact_live_three_cell_deepseek_cross_cell_scoped_identity_"
            "output_v4_r1"
        ),
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
        required_transport_result_status=IMPLEMENTATION_STATUS,
        decision_status=DECISION_STATUS,
        decision_contract_ref=(
            "fin01.s3.cross_cell_scoped_identity_output_v4_"
            "fresh_exact_proof_decision:v1"
        ),
        transport_result_binding_path=("architecture", "specialist_transport_ref"),
        provider_output_capture_policy_ref=S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
        research_lead_transport_ref=S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V4_REF,
        memo_writer_transport_ref=S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF,
        research_profile_ref=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_REF,
        output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
        scoped_identity_contract_ref=(
            S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
        ),
        stage_output_token_budgets=(
            S3_OWNER_GRADE_RESEARCH_LEAD_V2_STAGE_OUTPUT_TOKEN_BUDGETS
        ),
        aggregate_output_token_budget=(
            S3_OWNER_GRADE_RESEARCH_LEAD_V2_AGGREGATE_OUTPUT_TOKEN_BUDGET
        ),
    )


def prepare(
    *,
    runtime_root: Path,
    implementation_result_path: Path,
) -> dict[str, Any]:
    implementation = json.loads(
        implementation_result_path.read_text(encoding="utf-8")
    )
    _require(
        implementation.get("status") == IMPLEMENTATION_STATUS,
        "cross_cell_scoped_identity_implementation_not_fixture_proven",
    )
    architecture = implementation.get("architecture")
    _require(
        isinstance(architecture, dict)
        and architecture.get("contract_ref")
        == S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
        and architecture.get("specialist_transport_ref")
        == S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF
        and architecture.get("research_lead_transport_ref")
        == S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V4_REF
        and architecture.get("memo_writer_transport_ref")
        == S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF
        and architecture.get("output_contract_ref")
        == S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
        "cross_cell_scoped_identity_implementation_binding_mismatch",
    )
    observed = implementation.get("observed_counts")
    _require(
        isinstance(observed, dict) and set(observed.values()) == {0},
        "cross_cell_scoped_identity_implementation_must_be_zero_call",
    )

    first = _prepare_once(
        runtime_root=runtime_root,
        implementation_result_path=implementation_result_path,
    )
    second = _prepare_once(
        runtime_root=runtime_root,
        implementation_result_path=implementation_result_path,
    )
    parity_keys = (
        "identity",
        "double_prepare",
        "prospective_admission",
        "target_read_only_audit",
    )
    _require(
        all(first[key] == second[key] for key in parity_keys),
        "independent_disposable_clone_prepare_parity_failed",
    )

    result = first
    result["source_refs"]["cross_cell_scoped_identity_implementation"] = (
        implementation_result_path.resolve().relative_to(ROOT).as_posix()
    )
    result["double_prepare"]["independent_disposable_clone_invocations"] = 2
    result["double_prepare"]["independent_invocation_equal"] = True
    result["architecture_contract"] = {
        "output_contract_ref": S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
        "specialist_transport_ref": (
            S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF
        ),
        "research_lead_transport_ref": (
            S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V4_REF
        ),
        "memo_writer_transport_ref": (
            S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF
        ),
        "scoped_identity_contract_ref": (
            S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
        ),
        "research_profile_ref": S3_NVDA_THREE_CELL_RESEARCH_PROFILE_REF,
        "provider_local_ids_preserved": True,
        "cross_cell_raw_id_references_fail_closed": True,
    }
    result["artifact_acceptance_contract"] = {
        "success_requires_terminal_state": "succeeded",
        "success_requires_logical_nodes": 6,
        "success_requires_provider_calls": 12,
        "success_requires_artifact_families": 9,
        "required_artifact_types": [
            "SpecialistAnalysis",
            "ResearchLeadSynthesis",
            "MemoDraft",
            "VerifierResult",
            "FactSet",
            "EvidenceSet",
            "NumericSet",
            "JudgmentSet",
            "Report",
        ],
        "failure_requires_typed_terminal_closeout": True,
        "failure_preserves_completed_assistant_outputs_and_usage": True,
        "transport_only_green_is_success": False,
    }
    result["audit_contract"] = {
        "target_service_initialization_allowed": False,
        "target_SQLite_access": "direct_mode_ro_or_digest_only",
        "service_backed_preparation": "disposable_clone_only",
        "target_database_or_object_write_allowed": False,
        "credential_value_read_output_or_persisted": False,
    }
    result["experiment_governance"] = {
        "hypothesis": (
            "The shared Cell-scoped identity contract allows a fresh real "
            "output-v4 run to traverse Specialist-v7, Lead-v4, Writer-v3, "
            "and Verifier without cross-Cell Claim or WWC namespace loss."
        ),
        "stop_condition": (
            "The first credible parse, schema, semantic, authority, identity, "
            "length, budget, terminalization, or capture-persistence failure "
            "must terminally stop without retry, fallback, patch, or rerun."
        ),
        "admission_issuance_authorized": False,
        "admission_consumption_authorized": False,
        "live_execution_authorized": False,
        "automatic_retry_fallback_patch_or_rerun_authorized": False,
        "paired_comparison_or_owner_acceptance_authorized": False,
    }
    result["next_action"] = NEXT_ACTION
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=ROOT
        / ".codex_runtime"
        / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1",
    )
    args = parser.parse_args()
    releases = ROOT / "configs" / "releases"
    result = prepare(
        runtime_root=args.runtime_root,
        implementation_result_path=releases
        / "fin_ia_0_1_s3_t09_cross_cell_scoped_identity_zero_call_"
        "implementation_v1_0.json",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
