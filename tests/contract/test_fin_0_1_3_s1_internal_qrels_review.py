from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.s1_internal_qrels_review import (  # noqa: E402
    S1InternalQrelsReviewError,
    build_internal_qrels_review_packet,
    load_bound_internal_qrels_inputs,
    load_internal_qrels_review_policy,
)


POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_internal_qrels_review_policy_v1_0.json"
)


def _loaded() -> tuple[dict, dict]:
    policy = load_internal_qrels_review_policy(POLICY_PATH, repo_root=ROOT)
    inputs = load_bound_internal_qrels_inputs(policy, repo_root=ROOT)
    return policy, inputs


def test_review_packet_is_post_candidate_agent_curated_and_honestly_failed() -> None:
    policy, inputs = _loaded()
    packet = build_internal_qrels_review_packet(policy=policy, inputs=inputs)
    assert packet["target_count"] == 18
    assert packet["strict_current_target_in_pool_count"] == 9
    assert packet["strict_current_target_absent_count"] == 9
    assert packet["strict_current_target_recall"] == 0.5
    assert packet["all_target_exact_sql_candidate_count"] == 0
    assert packet["gate_decision"] == {
        "agent_curated_candidate_ceiling_pass": False,
        "owner_review_complete": False,
        "candidate_ceiling_proven": False,
        "BGE_fusion_rerank_admitted": False,
        "reason": (
            "Current strict target recall is below 1.0 and exact SQL has no "
            "current candidate. Corpus/index freshness and evidence-owner "
            "coverage must be repaired before ranking evaluation."
        ),
    }
    assert not any(packet["observed_calls"].values())


def test_present_qrels_bind_current_typed_candidate_and_absent_rows_bind_gap() -> None:
    policy, inputs = _loaded()
    packet = build_internal_qrels_review_packet(policy=policy, inputs=inputs)
    for row in packet["qrels"]:
        if row["strict_current_target_in_pool"]:
            candidate = row["selected_candidate"]
            assert row["proposed_relevance"] >= 2
            assert candidate["ticker"] == row["evidence_owner_ticker"]
            assert candidate["published_at"] <= row["as_of_date"]
            assert candidate["strict_identity_filter_applied"] is True
            assert candidate["strict_period_filter_applied"] is True
            assert row["gap_class"] == ""
        else:
            assert row["selected_candidate"] is None
            assert row["gap_class"]


def test_candidate_or_target_mutation_fails_closed() -> None:
    policy, inputs = _loaded()
    mutated = deepcopy(inputs)
    target = next(
        item
        for item in mutated["target_manifest"]["targets"]
        if item["proposed_state"] == "strict_current_target_in_pool"
    )
    target["selected_source_key"] = "missing"
    with pytest.raises(
        S1InternalQrelsReviewError,
        match="internal_qrels_selected_candidate_missing",
    ):
        build_internal_qrels_review_packet(policy=policy, inputs=mutated)

    mutated = deepcopy(inputs)
    terminal = next(
        item
        for item in mutated["candidate_observation"]["route_terminals"]
        if item["candidates"]
    )
    terminal["candidates"][0]["preview"] = "mutated"
    with pytest.raises(
        S1InternalQrelsReviewError,
        match="internal_qrels_candidate_digest_invalid",
    ):
        build_internal_qrels_review_packet(policy=policy, inputs=mutated)


def test_materialized_review_digest_is_bound() -> None:
    path = ROOT / (
        "configs/releases/fin_ia_0_1_3_s1_internal_qrels_review_packet_v1_0.json"
    )
    if not path.exists():
        pytest.skip("review packet materializer has not run")
    packet = json.loads(path.read_text(encoding="utf-8"))
    body = dict(packet)
    supplied = body.pop("review_digest")
    assert supplied == canonical_digest(body)
