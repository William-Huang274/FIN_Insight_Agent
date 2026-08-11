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
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF,
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
    prepare as _prepare,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_research_lead_v5_fresh_exact_proof import (
    _prior_failed_results,
)


RELEASES = ROOT / "configs" / "releases"
IMPLEMENTATION_STATUS = (
    "pass_zero_call_profile_v3_quality_target_hard_safety_separation_"
    "complete_safe_count_and_artifact_observation_fixture_proven"
)
EXECUTION_IDENTITY = (
    "fin01-s3-t09-three-cell-deepseek-owner-grade-research-lead-v5-"
    "profile-v3-final-live-validation-r1"
)
PROSPECTIVE_ADMISSION_ID = (
    "fin01-s3-t09-three-cell-deepseek-owner-grade-research-lead-v5-"
    "profile-v3-final-exact-admission-r1"
)
PROSPECTIVE_ADMISSION_FILE = (
    "configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_"
    "research_lead_v5_profile_v3_final_exact_admission_r1.json"
)
DECISION_STATUS = (
    "pass_zero_call_profile_v3_final_fresh_exact_proof_contract_frozen_"
    "issuance_ready"
)


def prepare(
    *,
    runtime_root: Path,
    implementation_result_path: Path,
) -> dict[str, Any]:
    implementation = json.loads(
        implementation_result_path.read_text(encoding="utf-8")
    )
    if implementation.get("status") != IMPLEMENTATION_STATUS:
        raise RuntimeError("profile_v3_implementation_not_fixture_proven")
    implemented = implementation.get("implementation") or {}
    if (
        implemented.get("research_profile_ref")
        != S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3_REF
        or implemented.get("research_lead_transport_ref")
        != S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF
        or implemented.get("research_lead_narrative_quality_target") != 320
        or implemented.get("research_lead_narrative_hard_maximum") != 512
    ):
        raise RuntimeError("profile_v3_implementation_binding_mismatch")

    prior_results = (
        *_prior_failed_results(RELEASES),
        RELEASES
        / "fin_ia_0_1_s3_t09_research_lead_v5_fresh_live_execution_result_v1_0.json",
    )
    result = _prepare(
        runtime_root=runtime_root,
        baseline_result_path=RELEASES
        / "fin_ia_0_1_s3_t09_paired_deterministic_baseline_materialization_v1_0.json",
        paired_decision_path=RELEASES
        / "fin_ia_0_1_s3_t09_replacement_live_artifact_paired_baseline_decision_v1_0.json",
        monolithic_v3_result_path=RELEASES
        / "fin_ia_0_1_s3_t09_owner_grade_v3_fresh_live_execution_result_v1_0.json",
        transport_implementation_result_path=implementation_result_path,
        additional_prior_failed_result_paths=prior_results,
        execution_identity=EXECUTION_IDENTITY,
        prospective_admission_id=PROSPECTIVE_ADMISSION_ID,
        prospective_admission_file=PROSPECTIVE_ADMISSION_FILE,
        execution_mode=(
            "exact_live_three_cell_deepseek_owner_grade_research_lead_v5_"
            "profile_v3_final_r1"
        ),
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
        required_transport_result_status=IMPLEMENTATION_STATUS,
        decision_status=DECISION_STATUS,
        decision_contract_ref=(
            "fin01.s3.research_lead_v5_profile_v3_final_exact_proof_decision:v1"
        ),
        transport_result_binding_path=(
            "implementation",
            "research_lead_transport_ref",
        ),
        required_transport_result_binding_value=(
            S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF
        ),
        provider_output_capture_policy_ref=(
            S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF
        ),
        research_lead_transport_ref=(
            S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF
        ),
        memo_writer_transport_ref=(
            S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF
        ),
        research_profile_ref=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3_REF,
        output_contract_ref=(
            S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF
        ),
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
    result["architecture_contract"] = {
        "output_contract_ref": (
            S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF
        ),
        "specialist_transport_ref": (
            S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF
        ),
        "research_lead_transport_ref": (
            S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF
        ),
        "memo_writer_transport_ref": (
            S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF
        ),
        "research_profile_ref": (
            S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3_REF
        ),
        "narrative_quality_target": 320,
        "narrative_hard_maximum": 512,
        "quality_target_exceedance_terminal": False,
        "quality_observation_persisted": True,
    }
    result["artifact_acceptance_contract"] = {
        "success_requires_terminal_state": "succeeded",
        "success_requires_logical_nodes": 6,
        "success_requires_provider_calls": 12,
        "success_requires_artifact_families": 9,
        "quality_target_exceedance_may_pass_with_closed_observation": True,
        "hard_integrity_failure_must_stop": True,
        "paired_comparison_and_independent_product_review_after_success": True,
        "owner_acceptance_requires_user_confirmation": True,
    }
    result["experiment_governance"] = {
        "this_is_the_only_authorized_final_exact_live": True,
        "retry_fallback_rerun_counts": [0, 0, 0],
        "second_live_execution_authorized": False,
        "hard_integrity_failure_behavior": "terminal_stop",
        "soft_quality_gap_behavior": (
            "persist_and_carry_forward_without_new_S3_transport_iteration"
        ),
    }
    result["next_action"] = (
        "S3-T09-OWNER-GRADE-RESEARCH-LEAD-V5-PROFILE-V3-"
        "FINAL-FRESH-EXACT-ADMISSION-ISSUANCE"
    )
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
    parser.add_argument(
        "--implementation-result",
        type=Path,
        default=RELEASES
        / "fin_ia_0_1_s3_t09_research_lead_v5_profile_v3_"
        "narrative_quality_zero_call_implementation_v1_0.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(
        runtime_root=args.runtime_root.resolve(),
        implementation_result_path=args.implementation_result.resolve(),
    )
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
