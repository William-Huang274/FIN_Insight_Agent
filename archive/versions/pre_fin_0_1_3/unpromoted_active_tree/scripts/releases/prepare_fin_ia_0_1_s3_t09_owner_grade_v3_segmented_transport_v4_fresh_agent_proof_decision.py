from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V4_REF,
    S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_owner_grade_v3_segmented_exact_admission_decision import (
    prepare as _prepare_segmented_decision,
)


EXECUTION_IDENTITY = (
    "fin01-s3-t09-three-cell-deepseek-owner-grade-v3-segmented-"
    "transport-v4-live-validation-r1"
)
PROSPECTIVE_ADMISSION_ID = (
    "fin01-s3-t09-three-cell-deepseek-owner-grade-v3-segmented-"
    "transport-v4-exact-admission-r1"
)
PROSPECTIVE_ADMISSION_FILE = (
    "configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_v3_"
    "segmented_transport_v4_exact_admission_v1_0.json"
)
EXECUTION_MODE = (
    "exact_live_three_cell_deepseek_owner_grade_v3_segmented_"
    "transport_v4_r1"
)
DECISION_STATUS = (
    "pass_fresh_segmented_transport_v4_exact_proof_contract_decided_"
    "admission_issuance_ready"
)
DECISION_CONTRACT_REF = (
    "fin01.s3.owner_grade_v3.segmented_transport_v4_fresh_agent_"
    "proof_decision:v1"
)
REQUIRED_REPAIR_STATUS = (
    "pass_zero_call_transport_v4_epistemic_status_state_machine_fixture_proven"
)


def prepare(
    *,
    runtime_root: Path,
    baseline_result_path: Path,
    paired_decision_path: Path,
    monolithic_v3_result_path: Path,
    segmented_v1_live_result_path: Path,
    transport_v2_live_result_path: Path,
    transport_v3_live_result_path: Path,
    transport_v4_repair_result_path: Path,
    prospective_admission_file: str = PROSPECTIVE_ADMISSION_FILE,
) -> dict[str, Any]:
    result = _prepare_segmented_decision(
        runtime_root=runtime_root,
        baseline_result_path=baseline_result_path,
        paired_decision_path=paired_decision_path,
        monolithic_v3_result_path=monolithic_v3_result_path,
        transport_implementation_result_path=transport_v4_repair_result_path,
        additional_prior_failed_result_paths=(
            segmented_v1_live_result_path,
            transport_v2_live_result_path,
            transport_v3_live_result_path,
        ),
        execution_identity=EXECUTION_IDENTITY,
        prospective_admission_id=PROSPECTIVE_ADMISSION_ID,
        prospective_admission_file=prospective_admission_file,
        execution_mode=EXECUTION_MODE,
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V4_REF,
        required_transport_result_status=REQUIRED_REPAIR_STATUS,
        decision_status=DECISION_STATUS,
        decision_contract_ref=DECISION_CONTRACT_REF,
        provider_output_capture_policy_ref=S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
    )
    result["freshness_and_nonreuse"].update(
        {
            "consumed_segmented_v1_identity_reusable": False,
            "consumed_transport_v2_identity_reusable": False,
            "consumed_transport_v3_identity_reusable": False,
            "prior_admission_payload_or_digest_reusable": False,
        }
    )
    result["provider_route_review"].update(
        {
            "decision": "retain_deepseek_for_one_exact_transport_v4_proof_only",
            "transport_ref": S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V4_REF,
            "epistemic_status_state_machine_fixture_proven": True,
            "provider_output_capture_policy_ref": (
                S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF
            ),
            "exact_assistant_final_text_capture_required": True,
            "real_transport_v4_provider_conformance_proven": False,
            "repeated_claim_card_contract_failure_disposition": (
                "stop_prompt_only_v5_work_and_move_to_provider_route_disposition"
            ),
        }
    )
    result["experiment_governance"] = {
        "hypothesis": (
            "The explicit four-state Claim Card contract should remove the observed "
            "cannot_infer cross-field conflict while preserving fail-closed validation."
        ),
        "decision_target": (
            "One fresh exact Run either completes six logical nodes and nine Artifact "
            "families or terminalizes at the first typed failure with exact assistant "
            "final texts retained through restricted object references."
        ),
        "stop_condition": (
            "Any credible failure consumes the admission and ends this run with no "
            "retry, fallback, patch or rerun. A repeated Claim Card contract failure "
            "ends prompt-only versioning."
        ),
        "decision_label": "proceed_to_exact_admission_issuance_and_exact_once_execution",
        "live_execution_authorized_by_user": True,
    }
    result["product_proof_target"] = {
        "success_is_not_transport_or_first_segment_only": True,
        "required_logical_node_count": 6,
        "required_artifact_family_count": 9,
        "required_output_contract_ref": "fin01.s3.bounded_agent_three_cell_output:v3",
        "unsupported_claims_must_remain_bounded_or_cannot_infer": True,
        "what_would_change_must_remain_actionable": True,
        "verifier_false_green_forbidden": True,
        "provider_output_capture_count_on_full_success": 12,
        "paired_comparison_and_owner_acceptance_remain_separate": True,
    }
    return result


def main() -> int:
    releases = ROOT / "configs" / "releases"
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=ROOT
        / ".codex_runtime"
        / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1",
    )
    parser.add_argument(
        "--baseline-result",
        type=Path,
        default=releases
        / "fin_ia_0_1_s3_t09_paired_deterministic_baseline_materialization_v1_0.json",
    )
    parser.add_argument(
        "--paired-decision",
        type=Path,
        default=releases
        / "fin_ia_0_1_s3_t09_replacement_live_artifact_paired_baseline_decision_v1_0.json",
    )
    parser.add_argument(
        "--monolithic-v3-result",
        type=Path,
        default=releases
        / "fin_ia_0_1_s3_t09_owner_grade_v3_fresh_live_execution_result_v1_0.json",
    )
    parser.add_argument(
        "--segmented-v1-live-result",
        type=Path,
        default=releases
        / "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_fresh_live_execution_result_v1_0.json",
    )
    parser.add_argument(
        "--transport-v2-live-result",
        type=Path,
        default=releases
        / "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_text_contract_v2_fresh_live_execution_result_v1_0.json",
    )
    parser.add_argument(
        "--transport-v3-live-result",
        type=Path,
        default=releases
        / "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_transport_v3_fresh_live_execution_result_v1_0.json",
    )
    parser.add_argument(
        "--transport-v4-repair-result",
        type=Path,
        default=releases
        / "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_transport_v4_epistemic_status_state_machine_repair_v1_0.json",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            prepare(
                runtime_root=args.runtime_root,
                baseline_result_path=args.baseline_result.resolve(),
                paired_decision_path=args.paired_decision.resolve(),
                monolithic_v3_result_path=args.monolithic_v3_result.resolve(),
                segmented_v1_live_result_path=args.segmented_v1_live_result.resolve(),
                transport_v2_live_result_path=args.transport_v2_live_result.resolve(),
                transport_v3_live_result_path=args.transport_v3_live_result.resolve(),
                transport_v4_repair_result_path=args.transport_v4_repair_result.resolve(),
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
