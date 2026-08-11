from __future__ import annotations

import json
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.financial_research_held_out_business_review import (
    HeldOutBusinessReviewError,
    load_held_out_business_review_policy,
)


pytestmark = pytest.mark.fast_contract

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_three_held_out_"
    "business_review_policy_v1_0.json"
)
RESULT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_three_held_out_"
    "business_review_result_v1_0.json"
)


def _mutated_policy(tmp_path: Path, mutate) -> Path:
    payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    mutate(payload)
    target = tmp_path / "mutated-held-out-business-review.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def test_business_review_covers_every_lane_and_required_mutation() -> None:
    policy, candidate = load_held_out_business_review_policy(
        POLICY_PATH,
        repo_root=ROOT,
    )
    assert tuple(row.case_key for row in policy.case_reviews) == (
        "ORCL",
        "ASML",
        "ANET",
    )
    assert candidate["result_digest"] == policy.candidate_result_digest
    for review, result_case in zip(
        policy.case_reviews,
        candidate["case_results"],
        strict=True,
    ):
        assert {row.lane_id for row in review.lane_reviews} == {
            row["lane_id"] for row in result_case["query_lane_results"]
        }
    mutations = {
        row.case_key: {item.mutation_id: item.outcome for item in row.mutation_reviews}
        for row in policy.case_reviews
    }
    assert mutations["ORCL"] == {
        "same-name entity": "pass",
        "fiscal-calendar mismatch": "pass",
        "competitor pollution": "pass",
    }
    assert mutations["ASML"]["currency mismatch"] == "fail"
    assert mutations["ASML"]["PDF-only source"] == "not_proven"
    assert mutations["ANET"]["zero-result route"] == "pass"


def test_review_keeps_currentness_and_attribution_failures_business_visible() -> None:
    policy, _candidate = load_held_out_business_review_policy(
        POLICY_PATH,
        repo_root=ROOT,
    )
    blockers = {
        row.code: row
        for review in policy.case_reviews
        for row in review.blockers
    }
    assert blockers["orcl_fy2026_q4_or_annual_source_absent"].blocks_sparse_dense_rebuild
    assert blockers["asml_q2_2026_6k_or_ir_pdf_absent"].blocks_sparse_dense_rebuild
    assert blockers["foreign_issuer_currency_semantics_corrupt"].blocks_sparse_dense_rebuild
    assert blockers["anet_q2_2026_official_results_absent"].blocks_sparse_dense_rebuild
    assert not blockers[
        "anet_counterparty_demand_not_company_attribution"
    ].blocks_sparse_dense_rebuild


def test_unknown_candidate_reference_fails_closed(tmp_path: Path) -> None:
    def mutate(payload: dict) -> None:
        payload["case_reviews"][0]["lane_reviews"][0][
            "useful_candidate_refs"
        ][0] = "fabricated-candidate"

    with pytest.raises(
        HeldOutBusinessReviewError,
        match="held_out_business_review_candidate_binding_invalid",
    ):
        load_held_out_business_review_policy(
            _mutated_policy(tmp_path, mutate),
            repo_root=ROOT,
        )


def test_missing_lane_review_fails_closed(tmp_path: Path) -> None:
    def mutate(payload: dict) -> None:
        payload["case_reviews"][2]["lane_reviews"].pop()

    with pytest.raises(
        HeldOutBusinessReviewError,
        match="held_out_business_review_lane_coverage_invalid",
    ):
        load_held_out_business_review_policy(
            _mutated_policy(tmp_path, mutate),
            repo_root=ROOT,
        )


def test_result_is_content_addressed_and_blocks_premature_rebuild() -> None:
    if not RESULT_PATH.exists():
        pytest.skip("held-out business review has not been materialized yet")
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    digest = result.pop("result_digest")
    assert canonical_digest(result) == digest
    assert result["status"] == (
        "held_out_generalization_blocked_before_index_rebuild"
    )
    assert result["stage_acceptance"] == {
        "business_semantics_reviewed": True,
        "external_supplement_admitted": False,
        "held_out_interface_terminalization_pass": True,
        "held_out_product_generalization_pass": False,
        "locked_candidate_set_reviewed": True,
        "model_synthesis_admitted": False,
        "required_mutations_all_proven": False,
        "sparse_dense_rebuild_admitted": False,
    }
    assert result["observed_calls"] == {
        "additional_retrieval": 0,
        "embedding": 0,
        "evidence_promotion": 0,
        "model": 0,
        "network": 0,
        "provider": 0,
        "rerank": 0,
    }
