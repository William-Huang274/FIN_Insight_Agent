from __future__ import annotations

import json
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.financial_research_generalization_contract import (
    compile_case_research_contract,
)
from sec_agent.financial_research_source_object_vertical import (
    FinancialSourceObjectVerticalError,
    load_amended_financial_source_object_vertical_policy,
    normalized_sha256,
    validate_financial_source_object_vertical_policy,
)


pytestmark = pytest.mark.fast_contract

ROOT = Path(__file__).resolve().parents[2]
AMENDMENT_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_dell_financial_source_object_"
    "vertical_policy_amendment_r2_v1_0.json"
)
R1_RESULT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_dell_"
    "financial_source_object_vertical_result_v1_0.json"
)
R3_RESULT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_dell_"
    "financial_source_object_vertical_result_r3_v1_0.json"
)


@pytest.fixture(scope="module")
def loaded():
    return load_amended_financial_source_object_vertical_policy(
        AMENDMENT_PATH,
        repo_root=ROOT,
    )


def test_amendment_preserves_base_policy_and_generic_core(loaded) -> None:
    policy, contract, compiled, amendment = loaded
    assert normalized_sha256(ROOT / amendment.base_policy_ref) == amendment.base_policy_sha256
    assert policy.contract_ref.endswith(":v2")
    assert len(policy.reviewed_candidate_bindings) == 23
    assert len(policy.declared_residual_gaps) == 16
    fingerprints = {
        compile_case_research_contract(contract, case_key).core_fingerprint
        for case_key in ("DELL", "MU", "NVDA")
    }
    assert fingerprints == {compiled.core_fingerprint}


def test_policy_keeps_queries_independent_from_review_targets_and_calls_zero(loaded) -> None:
    policy, _, _, _ = loaded
    targets_by_lane: dict[str, list[str]] = {}
    for binding in policy.reviewed_candidate_bindings:
        targets_by_lane.setdefault(binding.lane_id, []).append(binding.target_id.casefold())
    for lane in policy.query_lanes:
        for query in lane.query_texts:
            assert all(target not in query.casefold() for target in targets_by_lane.get(lane.lane_id, []))
    for key in ("network", "provider", "model", "embedding", "rerank", "evidence_promotion"):
        assert policy.hard_boundaries[key] == 0
    assert policy.hard_boundaries["qrels_loaded_after_candidate_generation"] is True


def test_query_target_leakage_mutation_fails_closed(loaded) -> None:
    policy, _, compiled, _ = loaded
    binding = policy.reviewed_candidate_bindings[0]
    mutated_lanes = tuple(
        lane.model_copy(update={"query_texts": (binding.target_id,)})
        if lane.lane_id == binding.lane_id
        else lane
        for lane in policy.query_lanes
    )
    with pytest.raises(
        FinancialSourceObjectVerticalError,
        match="vertical_query_contains_review_target_id",
    ):
        validate_financial_source_object_vertical_policy(
            policy.model_copy(update={"query_lanes": mutated_lanes}),
            compiled=compiled,
        )


def test_reversed_relationship_binding_mutation_fails_closed(loaded) -> None:
    policy, _, compiled, _ = loaded
    target = next(
        row
        for row in policy.reviewed_candidate_bindings
        if row.evidence_owner_entity_key != compiled.subject_entity_key
    )
    reversed_direction = "reversed_unregistered_direction"
    mutated_bindings = tuple(
        row.model_copy(update={"relationship_direction": reversed_direction})
        if row.qualification_id == target.qualification_id
        else row
        for row in policy.reviewed_candidate_bindings
    )
    mutated_lanes = tuple(
        row.model_copy(update={"relationship_direction": reversed_direction})
        if row.lane_id == target.lane_id
        else row
        for row in policy.query_lanes
    )
    with pytest.raises(
        FinancialSourceObjectVerticalError,
        match="vertical_relationship_binding_missing_or_reversed",
    ):
        validate_financial_source_object_vertical_policy(
            policy.model_copy(
                update={
                    "reviewed_candidate_bindings": mutated_bindings,
                    "query_lanes": mutated_lanes,
                }
            ),
            compiled=compiled,
        )


def test_failed_r1_is_preserved_as_diagnostic_evidence() -> None:
    result = json.loads(R1_RESULT_PATH.read_text(encoding="utf-8"))
    assert result["status"] == "engineering_blocked_reviewed_candidate_retrieval_or_content_miss"
    assert result["observed_counts"]["reviewed_candidate_misses"] == 1
    miss = next(
        row
        for row in result["candidate_qualifications"]
        if row["qualification_status"] != "qualified"
    )
    assert miss["qualification_id"] == "dell-relationship-self"
    assert miss["finding_codes"] == [
        "reviewed_source_excerpt_not_found",
        "reviewed_target_excerpt_not_found",
    ]


def test_r3_real_local_vertical_is_engineering_pass_with_honest_gaps() -> None:
    result = json.loads(R3_RESULT_PATH.read_text(encoding="utf-8"))
    assert result["status"] == "engineering_pass_product_pack_incomplete"
    assert result["candidate_pack_evaluation"]["status"] == "incomplete_not_admitted"
    assert result["observed_counts"] == {
        "candidate_contract_rejections": 0,
        "declared_residual_gaps": 16,
        "qualified_candidates": 23,
        "query_lanes": 23,
        "retrieved_candidate_rows": 265,
        "reviewed_candidate_bindings": 23,
        "reviewed_candidate_misses": 0,
        "source_records": 15,
    }
    assert all(value == 0 for value in result["observed_calls"].values())
    assert result["stage_acceptance"]["reviewed_candidate_recall_complete"] is True
    assert result["stage_acceptance"]["candidate_contract_valid"] is True
    assert result["stage_acceptance"]["dell_local_evidence_pack_complete"] is False
    assert result["stage_acceptance"]["evidence_promotion_admitted"] is False

    for slot in result["candidate_pack_evaluation"]["slot_evaluations"]:
        if slot["missing_facets"]:
            assert set(slot["missing_facets"]) == set(slot["declared_gap_facets"])
            assert slot["status"] == "terminal_with_declared_gaps"
        else:
            assert slot["status"] == "candidate_complete_pending_evidence_gate"


def test_r3_result_is_content_addressed_and_does_not_duplicate_private_text() -> None:
    result = json.loads(R3_RESULT_PATH.read_text(encoding="utf-8"))
    digest = result.pop("result_digest")
    assert canonical_digest(result) == digest
    assert normalized_sha256(ROOT / result["implementation"]["module_ref"]) == result[
        "implementation"
    ]["module_sha256"]
    serialized = json.dumps(result, ensure_ascii=False)
    assert "target_content" not in serialized
    assert "accepted_evidence" not in serialized
    assert all(
        {
            "research_as_of_date",
            "analysis_period_id",
            "source_reporting_period_id",
            "relationship_valid_as_of",
        }
        <= set(row["period_binding"])
        for row in result["candidate_qualifications"]
    )
    assert {row["code"] for row in result["hierarchy_findings"]} == {
        "parent_summary_misclassified_as_disclaimer",
        "table_inherits_wrong_subsection",
        "metric_child_loses_column_period_context",
        "object_id_not_directly_addressable",
    }
