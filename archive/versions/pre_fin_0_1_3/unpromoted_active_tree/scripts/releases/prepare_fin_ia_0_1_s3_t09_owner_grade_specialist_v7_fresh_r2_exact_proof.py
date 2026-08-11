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
    S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V2_REF,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V3_REF,
    S3_OWNER_GRADE_RESEARCH_LEAD_V2_AGGREGATE_OUTPUT_TOKEN_BUDGET,
    S3_OWNER_GRADE_RESEARCH_LEAD_V2_STAGE_OUTPUT_TOKEN_BUDGETS,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
    S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_owner_grade_v3_segmented_exact_admission_decision import (
    prepare as _prepare_segmented_decision,
)


EXECUTION_IDENTITY = (
    "fin01-s3-t09-three-cell-deepseek-owner-grade-v3-specialist-v7-"
    "research-lead-v3-writer-v2-live-validation-r2"
)
PROSPECTIVE_ADMISSION_ID = (
    "fin01-s3-t09-three-cell-deepseek-owner-grade-v3-specialist-v7-"
    "research-lead-v3-writer-v2-exact-admission-r2"
)
PROSPECTIVE_ADMISSION_FILE = (
    "configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_v3_"
    "specialist_v7_research_lead_v3_writer_v2_exact_admission_r2.json"
)
IMPLEMENTATION_STATUS = (
    "pass_zero_call_specialist_v7_outer_capability_and_capture_repair_"
    "fixture_proven_fresh_r2_proof_decision_pending"
)
DECISION_STATUS = (
    "pass_specialist_v7_fresh_r2_exact_proof_decided_"
    "admission_issuance_authorized"
)


class SpecialistV7R2ProofDecisionError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise SpecialistV7R2ProofDecisionError(code)


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
        "specialist_v7_r2_repair_not_fixture_proven",
    )
    architecture = implementation.get("architecture")
    _require(
        isinstance(architecture, dict)
        and architecture.get("selected_transport_ref")
        == S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF
        and architecture.get("inner_and_outer_use_same_capacity_policy")
        is True
        and architecture.get("transport_version_membership_selects_capacity")
        is False
        and architecture.get("accumulated_usage_receipts_propagated") is True
        and architecture.get("accumulated_provider_output_captures_propagated")
        is True,
        "specialist_v7_r2_repair_contract_mismatch",
    )
    observed = implementation.get("observed_counts")
    _require(
        isinstance(observed, dict) and set(observed.values()) == {0},
        "specialist_v7_r2_repair_must_be_zero_call",
    )

    releases = ROOT / "configs" / "releases"
    result = _prepare_segmented_decision(
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
            "exact_live_three_cell_deepseek_owner_grade_v3_specialist_v7_"
            "research_lead_v3_writer_v2_r2"
        ),
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
        required_transport_result_status=IMPLEMENTATION_STATUS,
        decision_status=DECISION_STATUS,
        decision_contract_ref=(
            "fin01.s3.owner_grade_v3.specialist_v7_research_lead_v3_"
            "writer_v2_fresh_r2_exact_proof_decision:v1"
        ),
        transport_result_binding_path=("architecture", "selected_transport_ref"),
        provider_output_capture_policy_ref=S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
        research_lead_transport_ref=S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V3_REF,
        memo_writer_transport_ref=S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V2_REF,
        research_profile_ref=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_REF,
        stage_output_token_budgets=(
            S3_OWNER_GRADE_RESEARCH_LEAD_V2_STAGE_OUTPUT_TOKEN_BUDGETS
        ),
        aggregate_output_token_budget=(
            S3_OWNER_GRADE_RESEARCH_LEAD_V2_AGGREGATE_OUTPUT_TOKEN_BUDGET
        ),
    )
    result["source_refs"]["outer_capability_and_capture_repair"] = (
        implementation_result_path.resolve().relative_to(ROOT).as_posix()
    )
    result["repair_proof_contract"] = {
        "shared_capacity_policy": (
            "specialist_assembled_output_max_utf8_bytes"
        ),
        "bounded_v7_output_limit_utf8_bytes": 8192,
        "legacy_non_bounded_limit_utf8_bytes": 6000,
        "post_node_usage_and_capture_propagation": True,
        "raw_validator_payload_or_error_text_persisted": False,
    }
    result["experiment_governance"] = {
        "hypothesis": (
            "A capability-plus-profile capacity resolver removes the v7 outer "
            "6000-byte false failure, while typed post-node propagation makes "
            "every already produced assistant answer and usage receipt replayable."
        ),
        "stop_condition": (
            "Any credible parse, schema, semantic, authority, length, budget, "
            "terminalization, or capture-persistence failure consumes the fresh "
            "r2 admission and stops without retry, fallback, patch, or rerun."
        ),
        "fresh_r2_admission_issuance_authorized": True,
        "one_exact_live_execution_authorized": True,
        "automatic_retry_fallback_patch_or_rerun_authorized": False,
        "paired_comparison_or_owner_acceptance_authorized": False,
    }
    result["next_action"] = (
        "S3-T09-OWNER-GRADE-SPECIALIST-V7-FRESH-R2-EXACT-ADMISSION-ISSUANCE"
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
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    releases = ROOT / "configs" / "releases"
    result = prepare(
        runtime_root=args.runtime_root,
        implementation_result_path=releases
        / "fin_ia_0_1_s3_t09_specialist_v7_outer_assembly_capability_"
        "and_capture_zero_call_implementation_v1_0.json",
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
