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
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2_REF,
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
    prepare as _prepare_segmented_decision,
)


EXECUTION_IDENTITY = (
    "fin01-s3-t09-three-cell-deepseek-owner-grade-research-lead-v5-"
    "live-validation-r1"
)
PROSPECTIVE_ADMISSION_ID = (
    "fin01-s3-t09-three-cell-deepseek-owner-grade-research-lead-v5-"
    "exact-admission-r1"
)
PROSPECTIVE_ADMISSION_FILE = (
    "configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_"
    "research_lead_v5_exact_admission_r1.json"
)
IMPLEMENTATION_STATUS = (
    "pass_zero_call_provider_neutral_lead_capability_compact_alias_local_"
    "typed_expansion_local_row_ids_closed_reference_cardinality_dual_"
    "capacity_and_full_fake_provider_proven"
)
DECISION_STATUS = (
    "pass_zero_call_research_lead_v5_fresh_exact_proof_contract_frozen_"
    "admission_issuance_pending_separate_authority"
)
NEXT_ACTION = (
    "S3-T09-OWNER-GRADE-RESEARCH-LEAD-V5-FRESH-EXACT-"
    "ADMISSION-ISSUANCE"
)
CAPACITY_FIXTURE_DIGESTS = (
    "ae3963f35f8eb3f9624f143f8c6f0e7897b51a3b56ab5f8e6ddaa45d64c41d7a",
    "f207e92024c9a4e109ec3ddb7665c3e396d965250726705ab43de635d6ce1bc3",
    "2fff37072e7af7e4a825931eb8c639c344704285708828e3a60a9ccd4d9da02b",
)


class ResearchLeadV5FreshProofDecisionError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ResearchLeadV5FreshProofDecisionError(code)


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
        releases
        / "fin_ia_0_1_s3_t09_cross_cell_scoped_identity_fresh_live_execution_result_v1_0.json",
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
            "exact_live_three_cell_deepseek_owner_grade_research_lead_v5_r1"
        ),
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
        required_transport_result_status=IMPLEMENTATION_STATUS,
        decision_status=DECISION_STATUS,
        decision_contract_ref=(
            "fin01.s3.research_lead_v5_fresh_exact_proof_decision:v1"
        ),
        transport_result_binding_path=(
            "implementation",
            "research_lead_transport_ref",
        ),
        required_transport_result_binding_value=(
            S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF
        ),
        provider_output_capture_policy_ref=S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
        research_lead_transport_ref=S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF,
        memo_writer_transport_ref=S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF,
        research_profile_ref=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2_REF,
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
        "research_lead_v5_implementation_not_fixture_proven",
    )
    implemented = implementation.get("implementation")
    _require(
        isinstance(implemented, dict)
        and implemented.get("research_lead_transport_ref")
        == S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF
        and implemented.get("research_profile_ref")
        == S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2_REF
        and implemented.get("canonical_output_contract_ref")
        == S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF
        and implemented.get("canonical_identity_contract_ref")
        == S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
        and implemented.get("provider_output_capture_precedes_post_node_validation")
        is True,
        "research_lead_v5_implementation_binding_mismatch",
    )
    capacity_fixtures = implementation.get("capacity_fixtures")
    _require(
        isinstance(capacity_fixtures, dict)
        and tuple(
            capacity_fixtures[key]["capacity_digest"]
            for key in (
                "minimum_reference_surface",
                "exact_prior_live_shape_surface",
                "maximum_specialist_reference_surface",
            )
        )
        == CAPACITY_FIXTURE_DIGESTS,
        "research_lead_v5_capacity_fixture_digest_mismatch",
    )
    observed = implementation.get("observed_counts")
    _require(
        isinstance(observed, dict) and set(observed.values()) == {0},
        "research_lead_v5_implementation_must_be_zero_call",
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
    result["source_refs"]["research_lead_v5_implementation"] = (
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
            S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF
        ),
        "memo_writer_transport_ref": (
            S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF
        ),
        "scoped_identity_contract_ref": (
            S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
        ),
        "research_profile_ref": S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2_REF,
        "compact_alias_contract_ref": implemented["compact_alias_contract_ref"],
        "provider_local_ids_preserved": True,
        "provider_alias_is_authoritative_or_persisted": False,
        "provider_alias_expands_before_output_v4_validation": True,
        "writer_verifier_and_artifact_alias_residue_allowed": False,
        "cross_cell_raw_id_references_fail_closed": True,
    }
    result["capacity_contract"] = {
        "fixture_digests": list(CAPACITY_FIXTURE_DIGESTS),
        "provider_raw_wire_utf8_byte_maximum": (
            implemented["provider_raw_wire_utf8_byte_maximum"]
        ),
        "canonical_alias_segment_utf8_byte_maximum": (
            implemented["canonical_alias_segment_utf8_byte_maximum"]
        ),
        "local_expanded_hard_utf8_byte_maximum": (
            implemented["local_expanded_hard_utf8_byte_maximum"]
        ),
        "aggregate_provider_narrative_unicode_character_maximum": (
            implemented[
                "aggregate_provider_narrative_unicode_character_maximum"
            ]
        ),
        "lead_max_output_tokens": implemented["lead_max_output_tokens"],
        "aggregate_max_output_tokens": (
            implemented["aggregate_max_output_tokens"]
        ),
        "token_or_cost_increase_selected": False,
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
        "transport_or_lead_only_green_is_success": False,
        "complete_product_semantic_review_required_after_live_success": True,
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
            "Lead-v5 compact Provider aliases and local typed expansion allow "
            "one fresh output-v4 Run to complete Specialist-v7, Lead-v5, "
            "Writer-v3, Verifier and all nine canonical Artifact families "
            "without weakening Cell-scoped identity or increasing budgets."
        ),
        "stop_condition": (
            "The first credible parse, shape, schema, semantic, authority, "
            "identity, alias, capacity, length, budget, terminalization, or "
            "capture-persistence failure must terminally stop without retry, "
            "fallback, patch, or rerun."
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
        / "fin_ia_0_1_s3_t09_research_lead_v5_compact_scoped_reference_"
        "dual_capacity_zero_call_implementation_v1_0.json",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
