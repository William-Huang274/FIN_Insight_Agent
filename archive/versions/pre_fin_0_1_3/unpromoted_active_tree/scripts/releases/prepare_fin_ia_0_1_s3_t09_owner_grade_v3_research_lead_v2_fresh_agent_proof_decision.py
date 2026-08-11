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
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V2_REF,
    S3_OWNER_GRADE_RESEARCH_LEAD_V2_AGGREGATE_OUTPUT_TOKEN_BUDGET,
    S3_OWNER_GRADE_RESEARCH_LEAD_V2_STAGE_OUTPUT_TOKEN_BUDGETS,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V5_REF,
    S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_owner_grade_v3_segmented_exact_admission_decision import (
    prepare as _prepare_segmented_decision,
)


EXECUTION_IDENTITY = (
    "fin01-s3-t09-three-cell-deepseek-owner-grade-v3-specialist-v5-"
    "research-lead-v2-live-validation-r1"
)
PROSPECTIVE_ADMISSION_ID = (
    "fin01-s3-t09-three-cell-deepseek-owner-grade-v3-specialist-v5-"
    "research-lead-v2-exact-admission-r1"
)
PROSPECTIVE_ADMISSION_FILE = (
    "configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_v3_"
    "specialist_v5_research_lead_v2_exact_admission_v1_0.json"
)
EXECUTION_MODE = (
    "exact_live_three_cell_deepseek_owner_grade_v3_specialist_v5_"
    "research_lead_v2_r1"
)
DECISION_STATUS = (
    "pass_fresh_specialist_v5_research_lead_v2_exact_proof_contract_decided_"
    "admission_issuance_pending_separate_authority"
)
DECISION_CONTRACT_REF = (
    "fin01.s3.owner_grade_v3.specialist_v5_research_lead_v2_"
    "fresh_agent_proof_decision:v1"
)
REQUIRED_TRANSPORT_V5_REPAIR_STATUS = (
    "pass_zero_call_transport_v5_bounded_assembly_fixture_proven"
)
REQUIRED_RESEARCH_LEAD_V2_REPAIR_STATUS = (
    "pass_zero_call_research_lead_v2_closed_output_local_heads_bounded_"
    "capacity_and_safe_telemetry_fixture_proven"
)


class ResearchLeadV2ProofDecisionError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ResearchLeadV2ProofDecisionError(code)


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    return (
        resolved.relative_to(ROOT).as_posix()
        if resolved.is_relative_to(ROOT)
        else str(resolved)
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
    transport_v4_live_result_path: Path,
    transport_v5_live_result_path: Path,
    transport_v5_repair_result_path: Path,
    research_lead_v2_repair_result_path: Path,
    prospective_admission_file: str = PROSPECTIVE_ADMISSION_FILE,
) -> dict[str, Any]:
    lead_repair = json.loads(
        research_lead_v2_repair_result_path.read_text(encoding="utf-8")
    )
    _require(
        lead_repair.get("status") == REQUIRED_RESEARCH_LEAD_V2_REPAIR_STATUS,
        "research_lead_v2_repair_not_fixture_proven",
    )
    implementation = lead_repair.get("implementation")
    _require(
        isinstance(implementation, dict)
        and implementation.get("research_lead_transport_ref")
        == S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V2_REF
        and implementation.get("specialist_transport_ref_unchanged")
        == S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V5_REF
        and implementation.get("lead_max_output_tokens")
        == S3_OWNER_GRADE_RESEARCH_LEAD_V2_STAGE_OUTPUT_TOKEN_BUDGETS["lead"]
        and implementation.get("aggregate_max_output_tokens")
        == S3_OWNER_GRADE_RESEARCH_LEAD_V2_AGGREGATE_OUTPUT_TOKEN_BUDGET,
        "research_lead_v2_repair_binding_or_budget_mismatch",
    )
    observed = lead_repair.get("observed_counts")
    _require(
        isinstance(observed, dict) and set(observed.values()) == {0},
        "research_lead_v2_repair_must_be_zero_call",
    )

    result = _prepare_segmented_decision(
        runtime_root=runtime_root,
        baseline_result_path=baseline_result_path,
        paired_decision_path=paired_decision_path,
        monolithic_v3_result_path=monolithic_v3_result_path,
        transport_implementation_result_path=transport_v5_repair_result_path,
        additional_prior_failed_result_paths=(
            segmented_v1_live_result_path,
            transport_v2_live_result_path,
            transport_v3_live_result_path,
            transport_v4_live_result_path,
            transport_v5_live_result_path,
        ),
        execution_identity=EXECUTION_IDENTITY,
        prospective_admission_id=PROSPECTIVE_ADMISSION_ID,
        prospective_admission_file=prospective_admission_file,
        execution_mode=EXECUTION_MODE,
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V5_REF,
        required_transport_result_status=REQUIRED_TRANSPORT_V5_REPAIR_STATUS,
        decision_status=DECISION_STATUS,
        decision_contract_ref=DECISION_CONTRACT_REF,
        provider_output_capture_policy_ref=S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
        research_lead_transport_ref=(
            S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V2_REF
        ),
        stage_output_token_budgets=(
            S3_OWNER_GRADE_RESEARCH_LEAD_V2_STAGE_OUTPUT_TOKEN_BUDGETS
        ),
        aggregate_output_token_budget=(
            S3_OWNER_GRADE_RESEARCH_LEAD_V2_AGGREGATE_OUTPUT_TOKEN_BUDGET
        ),
    )
    result["source_refs"]["research_lead_v2_repair_result"] = _display_path(
        research_lead_v2_repair_result_path
    )
    result["freshness_and_nonreuse"].update(
        {
            "consumed_segmented_v1_identity_reusable": False,
            "consumed_transport_v2_identity_reusable": False,
            "consumed_transport_v3_identity_reusable": False,
            "consumed_transport_v4_identity_reusable": False,
            "consumed_transport_v5_identity_reusable": False,
            "prior_admission_payload_or_digest_reusable": False,
        }
    )
    result["provider_route_review"].update(
        {
            "decision": (
                "retain_deepseek_for_one_separately_authorized_exact_"
                "specialist_v5_research_lead_v2_proof"
            ),
            "specialist_transport_ref": (
                S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V5_REF
            ),
            "research_lead_transport_ref": (
                S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V2_REF
            ),
            "provider_output_capture_policy_ref": (
                S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF
            ),
            "exact_assistant_final_text_capture_required": True,
            "specialist_v5_live_conformance_proven": True,
            "research_lead_v2_live_conformance_proven": False,
            "new_credible_failure_disposition": (
                "stop_without_retry_fallback_patch_or_hidden_rerun"
            ),
        }
    )
    result["research_lead_v2_contract_review"] = {
        "provider_output_members": [
            "cross_cell_dependencies",
            "conflict_adjudications",
            "variant_view",
            "remaining_gaps",
        ],
        "provider_emits_cell_heads": False,
        "local_runtime_derives_exact_three_cell_heads": True,
        "full_validated_specialist_semantics_retained": True,
        "provider_and_assembled_utf8_byte_limits": [6000, 8192],
        "maximum_narrative_unicode_characters": 320,
        "dependencies_conflicts_and_gaps_cardinality": [[1, 3], [0, 3], [1, 4]],
        "lead_and_aggregate_output_token_limits": [1800, 16800],
        "historical_1200_token_admissions_immutable": True,
    }
    result["experiment_governance"] = {
        "hypothesis": (
            "Specialist transport v5 plus the closed Lead v2 semantic segment and "
            "local deterministic heads should complete the Research Lead without "
            "weakening any owner-grade authority or actionability contract."
        ),
        "decision_target": (
            "A separately authorized fresh exact Run either completes six logical "
            "nodes and nine Artifact families or terminalizes at the first typed "
            "failure with restricted final-assistant captures."
        ),
        "stop_condition": (
            "Any credible failure consumes the future admission and ends the future "
            "Run with no retry, fallback, patch or hidden rerun."
        ),
        "decision_label": (
            "proceed_to_exact_admission_issuance_after_separate_authority"
        ),
        "admission_issuance_authorized_by_user": False,
        "live_execution_authorized_by_user": False,
    }
    result["product_proof_target"] = {
        "success_is_not_specialist_or_lead_transport_only": True,
        "required_logical_node_count": 6,
        "required_artifact_family_count": 9,
        "required_output_contract_ref": (
            "fin01.s3.bounded_agent_three_cell_output:v3"
        ),
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
    args = parser.parse_args()
    print(
        json.dumps(
            prepare(
                runtime_root=args.runtime_root,
                baseline_result_path=releases
                / "fin_ia_0_1_s3_t09_paired_deterministic_baseline_"
                "materialization_v1_0.json",
                paired_decision_path=releases
                / "fin_ia_0_1_s3_t09_replacement_live_artifact_paired_"
                "baseline_decision_v1_0.json",
                monolithic_v3_result_path=releases
                / "fin_ia_0_1_s3_t09_owner_grade_v3_fresh_live_execution_"
                "result_v1_0.json",
                segmented_v1_live_result_path=releases
                / "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_fresh_live_"
                "execution_result_v1_0.json",
                transport_v2_live_result_path=releases
                / "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_text_contract_"
                "v2_fresh_live_execution_result_v1_0.json",
                transport_v3_live_result_path=releases
                / "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_transport_v3_"
                "fresh_live_execution_result_v1_0.json",
                transport_v4_live_result_path=releases
                / "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_transport_v4_"
                "fresh_live_execution_result_v1_0.json",
                transport_v5_live_result_path=releases
                / "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_transport_v5_"
                "fresh_live_execution_result_v1_0.json",
                transport_v5_repair_result_path=releases
                / "fin_ia_0_1_s3_t09_owner_grade_v3_segmented_transport_v5_"
                "bounded_assembly_repair_v1_0.json",
                research_lead_v2_repair_result_path=releases
                / "fin_ia_0_1_s3_t09_owner_grade_v3_research_lead_closed_"
                "output_local_head_assembly_and_bounded_headroom_zero_call_"
                "implementation_v1_0.json",
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
