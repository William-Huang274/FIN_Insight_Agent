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
    "research-lead-v3-writer-v2-live-validation-r1"
)
PROSPECTIVE_ADMISSION_ID = (
    "fin01-s3-t09-three-cell-deepseek-owner-grade-v3-specialist-v7-"
    "research-lead-v3-writer-v2-exact-admission-r1"
)
PROSPECTIVE_ADMISSION_FILE = (
    "configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_v3_"
    "specialist_v7_research_lead_v3_writer_v2_exact_admission_v1_0.json"
)
EXECUTION_MODE = (
    "exact_live_three_cell_deepseek_owner_grade_v3_specialist_v7_"
    "research_lead_v3_writer_v2_r1"
)
IMPLEMENTATION_STATUS = (
    "pass_zero_call_specialist_v7_contract_convergence_fixture_proven_"
    "fresh_agent_proof_decision_pending"
)
DECISION_STATUS = (
    "pass_specialist_v7_fresh_exact_proof_decided_"
    "admission_issuance_pending_separate_authority"
)


class SpecialistV7ProofDecisionError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise SpecialistV7ProofDecisionError(code)


def prepare(
    *,
    runtime_root: Path,
    implementation_result_path: Path,
    prior_failed_result_paths: tuple[Path, ...],
) -> dict[str, Any]:
    implementation = json.loads(
        implementation_result_path.read_text(encoding="utf-8")
    )
    _require(
        implementation.get("status") == IMPLEMENTATION_STATUS,
        "specialist_v7_implementation_not_fixture_proven",
    )
    architecture = implementation.get("architecture")
    _require(
        isinstance(architecture, dict)
        and architecture.get("selected_transport_ref")
        == S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF
        and architecture.get("prompt_and_validator_share_policy") is True
        and architecture.get("candidate_and_graph_fact_authority_allowed")
        is False
        and architecture.get("local_normalization_trim_remap_drop_or_repair_allowed")
        is False,
        "specialist_v7_contract_binding_mismatch",
    )
    profile = implementation.get("profile_configuration")
    _require(
        isinstance(profile, dict)
        and profile.get("default_profile_ref")
        == S3_NVDA_THREE_CELL_RESEARCH_PROFILE_REF
        and profile.get("new_v7_admission_requires_explicit_profile_ref")
        is True,
        "specialist_v7_profile_binding_mismatch",
    )
    observed = implementation.get("observed_counts")
    _require(
        isinstance(observed, dict) and set(observed.values()) == {0},
        "specialist_v7_implementation_must_be_zero_call",
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
        additional_prior_failed_result_paths=prior_failed_result_paths,
        execution_identity=EXECUTION_IDENTITY,
        prospective_admission_id=PROSPECTIVE_ADMISSION_ID,
        prospective_admission_file=PROSPECTIVE_ADMISSION_FILE,
        execution_mode=EXECUTION_MODE,
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
        required_transport_result_status=IMPLEMENTATION_STATUS,
        decision_status=DECISION_STATUS,
        decision_contract_ref=(
            "fin01.s3.owner_grade_v3.specialist_v7_research_lead_v3_"
            "writer_v2_fresh_exact_proof_decision:v1"
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
    result["source_refs"]["specialist_v7_contract_convergence"] = (
        implementation_result_path.resolve().relative_to(ROOT).as_posix()
    )
    result["fact_support_authority_contract"] = {
        "policy_ref": "closed_fact_support_authority:v1",
        "provider_fact_authority": ["EvidenceVersion", "NumericVersion"],
        "candidate_and_graph_are_context_only": True,
        "prompt_and_local_validator_share_policy": True,
        "normalization_trim_remap_drop_or_repair_allowed": False,
        "full_fake_provider_artifact_count": 9,
    }
    result["research_profile_contract"] = {
        "research_profile_ref": S3_NVDA_THREE_CELL_RESEARCH_PROFILE_REF,
        "explicitly_bound_in_prospective_admission": True,
        "company": "NVDA",
        "program_cell_count": 3,
    }
    result["audit_contract"] = {
        "target_service_initialization_allowed": False,
        "target_SQLite_access": "direct_mode_ro_or_digest_only",
        "service_backed_preparation": "disposable_clone_only",
        "post_run_service_backed_target_audit_allowed": False,
        "RC_P36_038": "recurrence_open",
    }
    result["experiment_governance"] = {
        "hypothesis": (
            "An exact field-local Evidence/Numeric Fact authority, shared by the "
            "Provider prompt and local validator, prevents Graph or Candidate "
            "context from being emitted as Fact support without relaxing any "
            "downstream owner-grade contract."
        ),
        "decision_target": (
            "A separately issued fresh exact Run either produces all six logical "
            "nodes and nine Artifacts or terminalizes at the first credible typed "
            "failure with restricted provider captures."
        ),
        "stop_condition": (
            "Any credible parse, shape, schema, semantic, authority, length, budget, "
            "or terminalization failure consumes the admission and stops with no "
            "retry, fallback, patch, normalization, or hidden rerun."
        ),
        "decision_label": (
            "proceed_to_exact_admission_issuance_pending_separate_authority"
        ),
        "admission_issuance_authorized": False,
        "live_execution_authorized": False,
        "paired_comparison_or_owner_acceptance_authorized": False,
    }
    result["next_action"] = (
        "S3-T09-OWNER-GRADE-SPECIALIST-V7-FRESH-EXACT-ADMISSION-ISSUANCE"
    )
    return result


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
    )


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
    result = prepare(
        runtime_root=args.runtime_root,
        implementation_result_path=releases
        / "fin_ia_0_1_s3_t09_specialist_v7_"
        "contract_convergence_zero_call_implementation_v1_0.json",
        prior_failed_result_paths=_prior_failed_results(releases),
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
