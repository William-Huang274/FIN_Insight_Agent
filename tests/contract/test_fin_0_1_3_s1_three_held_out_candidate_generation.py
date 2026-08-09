from __future__ import annotations

import json
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.financial_research_held_out_candidate_generation import (
    HeldOutCandidateGenerationError,
    _execute_lane,
    load_held_out_candidate_generation_policy,
)


pytestmark = pytest.mark.fast_contract

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_three_held_out_"
    "candidate_generation_policy_v1_0.json"
)
RESULT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_three_held_out_"
    "candidate_generation_result_v1_0.json"
)


def _mutated_policy(tmp_path: Path, mutate) -> Path:
    payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    mutate(payload)
    target = tmp_path / "mutated-held-out-candidate-policy.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def test_candidate_policy_preserves_selection_and_core_then_covers_required_slots() -> None:
    policy, selection, extended = load_held_out_candidate_generation_policy(
        POLICY_PATH,
        repo_root=ROOT,
    )
    assert tuple(row.case_key for row in policy.case_plans) == (
        "ORCL",
        "ASML",
        "ANET",
    )
    assert tuple(row.profile.case_key for row in selection.selections) == (
        "ORCL",
        "ASML",
        "ANET",
    )
    assert policy.expected_core_fingerprint == (
        "94af69dcc875ba285afca587d36622dfa859b092c7a2bf686141c5e43308b458"
    )
    assert len(extended.industry_packs) > 3
    for plan in policy.case_plans:
        subject_lanes = {
            row.slot_id
            for row in plan.query_lanes
            if row.relationship_direction == "subject_self_disclosure"
        }
        assert {
            "operating_performance",
            "demand_volume_quality",
            "pricing_mix_value_capture",
            "capacity_inputs_execution",
            "cash_conversion_balance_sheet",
            "relationship_attribution",
            "regulatory_policy_exposure",
            "counterevidence_and_what_would_change",
        } <= subject_lanes


def test_candidate_policy_is_gold_blind_and_zero_external_call() -> None:
    policy, _selection, _extended = load_held_out_candidate_generation_policy(
        POLICY_PATH,
        repo_root=ROOT,
    )
    serialized = json.dumps(policy.model_dump(mode="json"), ensure_ascii=False)
    assert "http://" not in serialized
    assert "https://" not in serialized
    assert "accession_number" not in serialized
    assert "target_id" not in serialized
    assert all(
        policy.hard_boundaries[key] == 0
        for key in (
            "network",
            "provider",
            "model",
            "embedding",
            "rerank",
            "evidence_promotion",
        )
    )


def test_wrong_relationship_direction_fails_closed(tmp_path: Path) -> None:
    def mutate(payload: dict) -> None:
        payload["case_plans"][2]["query_lanes"][6][
            "relationship_direction"
        ] = "subject_self_disclosure"

    with pytest.raises(
        HeldOutCandidateGenerationError,
        match="held_out_candidate_relationship_missing_or_reversed",
    ):
        load_held_out_candidate_generation_policy(
            _mutated_policy(tmp_path, mutate),
            repo_root=ROOT,
        )


def test_wrong_ticker_filter_fails_closed(tmp_path: Path) -> None:
    def mutate(payload: dict) -> None:
        payload["case_plans"][0]["query_lanes"][0]["filters"][
            "ticker"
        ] = "MSFT"

    with pytest.raises(
        HeldOutCandidateGenerationError,
        match="held_out_candidate_lane_contract_invalid",
    ):
        load_held_out_candidate_generation_policy(
            _mutated_policy(tmp_path, mutate),
            repo_root=ROOT,
        )


def test_answer_locator_in_query_fails_closed(tmp_path: Path) -> None:
    def mutate(payload: dict) -> None:
        payload["case_plans"][0]["query_lanes"][0]["query_texts"] = [
            "https://example.invalid/preselected-answer"
        ]

    with pytest.raises(
        HeldOutCandidateGenerationError,
        match="held_out_candidate_answer_or_locator_leakage",
    ):
        load_held_out_candidate_generation_policy(
            _mutated_policy(tmp_path, mutate),
            repo_root=ROOT,
        )


def test_missing_current_source_cannot_be_silently_accepted(tmp_path: Path) -> None:
    def mutate(payload: dict) -> None:
        payload["case_plans"][1]["currentness_requirement"][
            "missing_current_source_is_typed_gap"
        ] = False

    with pytest.raises(
        HeldOutCandidateGenerationError,
        match="held_out_candidate_currentness_boundary_invalid",
    ):
        load_held_out_candidate_generation_policy(
            _mutated_policy(tmp_path, mutate),
            repo_root=ROOT,
        )


def test_zero_result_route_terminalizes_without_fabricating_candidate() -> None:
    class EmptyRetriever:
        def search(self, query: str, top_k: int, filters: dict) -> list[dict]:
            return []

    policy, _selection, _extended = load_held_out_candidate_generation_policy(
        POLICY_PATH,
        repo_root=ROOT,
    )
    plan = next(row for row in policy.case_plans if row.case_key == "ANET")
    lane = next(row for row in plan.query_lanes if row.lane_id == "anet_demand")
    asset = next(row for row in plan.assets if row.asset_id == lane.asset_id)
    result = _execute_lane(lane, asset=asset, retriever=EmptyRetriever())
    assert result["status"] == "completed_typed_zero_result"
    assert result["candidates"] == []


def test_materialized_candidate_result_is_content_addressed_and_not_evidence() -> None:
    if not RESULT_PATH.exists():
        pytest.skip("candidate generation has not been materialized yet")
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    digest = result.pop("result_digest")
    assert canonical_digest(result) == digest
    assert result["status"] == (
        "gold_blind_candidate_generation_complete_review_required"
    )
    assert result["stage_acceptance"]["candidate_review_started"] is False
    assert result["stage_acceptance"]["held_out_generalization_complete"] is False
    assert result["observed_calls"]["network"] == 0
    assert result["observed_calls"]["model"] == 0
    assert result["observed_calls"]["embedding"] == 0
    assert result["observed_calls"]["rerank"] == 0
    assert result["observed_calls"]["evidence_promotion"] == 0
    assert all(
        candidate["candidate_state"] == "candidate_only_not_evidence"
        for case in result["case_results"]
        for lane in case["query_lane_results"]
        for candidate in lane["candidates"]
    )
