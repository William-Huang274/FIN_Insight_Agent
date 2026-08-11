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
    S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V2_REF,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V3_REF,
    S3_OWNER_GRADE_RESEARCH_LEAD_V2_AGGREGATE_OUTPUT_TOKEN_BUDGET,
    S3_OWNER_GRADE_RESEARCH_LEAD_V2_STAGE_OUTPUT_TOKEN_BUDGETS,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V6_REF,
    S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_owner_grade_v3_segmented_exact_admission_decision import (
    prepare as _prepare_segmented_decision,
)


EXECUTION_IDENTITY = (
    "fin01-s3-t09-three-cell-deepseek-owner-grade-v3-specialist-v6-"
    "research-lead-v3-writer-v2-live-validation-r1"
)
PROSPECTIVE_ADMISSION_ID = (
    "fin01-s3-t09-three-cell-deepseek-owner-grade-v3-specialist-v6-"
    "research-lead-v3-writer-v2-exact-admission-r1"
)
PROSPECTIVE_ADMISSION_FILE = (
    "configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_v3_"
    "specialist_v6_research_lead_v3_writer_v2_exact_admission_v1_0.json"
)
EXECUTION_MODE = (
    "exact_live_three_cell_deepseek_owner_grade_v3_specialist_v6_"
    "research_lead_v3_writer_v2_r1"
)
REPAIR_STATUS = (
    "pass_zero_call_specialist_v6_canonical_scope_local_assembly_fixture_proven"
)


class SpecialistV6ProofError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise SpecialistV6ProofError(code)


def prepare(
    *,
    runtime_root: Path,
    repair_result_path: Path,
    prior_failed_result_paths: tuple[Path, ...],
) -> dict[str, Any]:
    repair = json.loads(repair_result_path.read_text(encoding="utf-8"))
    _require(repair.get("status") == REPAIR_STATUS, "specialist_v6_repair_not_proven")
    implementation = repair.get("implementation")
    _require(
        isinstance(implementation, dict)
        and implementation.get("transport_ref")
        == S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V6_REF
        and implementation.get("historical_specialist_v1_through_v5_immutable")
        is True
        and implementation.get("research_lead_transport_ref")
        == S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V3_REF
        and implementation.get("memo_writer_transport_ref")
        == S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V2_REF,
        "specialist_v6_repair_binding_mismatch",
    )
    observed = repair.get("observed_counts")
    _require(
        isinstance(observed, dict) and set(observed.values()) == {0},
        "specialist_v6_repair_must_be_zero_call",
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
        transport_implementation_result_path=repair_result_path,
        additional_prior_failed_result_paths=prior_failed_result_paths,
        execution_identity=EXECUTION_IDENTITY,
        prospective_admission_id=PROSPECTIVE_ADMISSION_ID,
        prospective_admission_file=PROSPECTIVE_ADMISSION_FILE,
        execution_mode=EXECUTION_MODE,
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V6_REF,
        required_transport_result_status=REPAIR_STATUS,
        decision_status=(
            "pass_specialist_v6_fresh_exact_proof_prepared_issuance_authorized"
        ),
        decision_contract_ref=(
            "fin01.s3.owner_grade_v3.specialist_v6_research_lead_v3_"
            "writer_v2_fresh_exact_proof:v1"
        ),
        provider_output_capture_policy_ref=S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
        research_lead_transport_ref=S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V3_REF,
        memo_writer_transport_ref=S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V2_REF,
        stage_output_token_budgets=(
            S3_OWNER_GRADE_RESEARCH_LEAD_V2_STAGE_OUTPUT_TOKEN_BUDGETS
        ),
        aggregate_output_token_budget=(
            S3_OWNER_GRADE_RESEARCH_LEAD_V2_AGGREGATE_OUTPUT_TOKEN_BUDGET
        ),
    )
    result["source_refs"]["specialist_v6_repair_result"] = (
        repair_result_path.resolve().relative_to(ROOT).as_posix()
    )
    result["scope_ownership_contract"] = {
        "provider_emitted_scope_fields": ["metric_or_mechanism"],
        "locally_assembled_scope_fields": [
            "entity_ref",
            "business_scope_kind",
            "business_scope_ref",
            "period",
            "attribution_level",
        ],
        "canonical_token_normalization_allowed": False,
        "strict_scope_authority_validator_preserved": True,
        "full_fake_provider_artifact_count": 9,
    }
    result["experiment_governance"] = {
        "hypothesis": (
            "Moving deterministic Claim scope tokens from Provider generation to "
            "local authority assembly removes stochastic period normalization while "
            "preserving strict support scope and downstream owner-grade contracts."
        ),
        "decision_target": (
            "One fresh exact Run either produces the complete six-node nine-Artifact "
            "set or terminalizes at the first credible typed failure with captures."
        ),
        "stop_condition": (
            "Any credible failure consumes the admission and stops with no retry, "
            "fallback, patch, normalization, or hidden rerun."
        ),
        "decision_label": "proceed_to_issued_exact_once_live_execution",
        "admission_issuance_and_one_live_execution_authorized_by_user": True,
        "paired_comparison_or_owner_acceptance_authorized": False,
    }
    result["next_action"] = (
        "S3-T09-OWNER-GRADE-SPECIALIST-V6-FRESH-EXACT-ADMISSION-ISSUANCE-"
        "AND-ONE-LIVE-EXECUTION"
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
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    releases = ROOT / "configs" / "releases"
    prior = (
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
    )
    result = prepare(
        runtime_root=args.runtime_root,
        repair_result_path=releases
        / "fin_ia_0_1_s3_t09_owner_grade_v3_specialist_v6_"
        "canonical_scope_local_assembly_zero_call_repair_v1_0.json",
        prior_failed_result_paths=prior,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
