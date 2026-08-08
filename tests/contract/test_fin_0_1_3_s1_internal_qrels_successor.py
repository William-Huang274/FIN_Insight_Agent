from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_internal_qrels_successor import (  # noqa: E402
    S1InternalQrelsSuccessorError,
    build_internal_qrels_successor_packet,
    load_bound_internal_qrels_successor_inputs,
    load_internal_qrels_successor_policy,
)


POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_internal_qrels_successor_policy_v1_1.json"
)


def _inputs() -> tuple[dict, dict]:
    policy = load_internal_qrels_successor_policy(POLICY_PATH, repo_root=ROOT)
    inputs = load_bound_internal_qrels_successor_inputs(policy, repo_root=ROOT)
    return policy, inputs


def test_newer_local_asset_raises_candidate_ceiling_without_ranking() -> None:
    policy, inputs = _inputs()
    packet = build_internal_qrels_successor_packet(policy=policy, inputs=inputs)
    assert packet["strict_current_target_in_pool_count"] == 10
    assert packet["target_count"] == 18
    assert packet["strict_current_target_recall"] == pytest.approx(10 / 18)
    assert packet["all_target_exact_sql_candidate_count"] == 0
    assert packet["gate_decision"] == {
        "agent_curated_candidate_ceiling_pass": False,
        "owner_review_complete": False,
        "candidate_ceiling_proven": False,
        "BGE_fusion_rerank_admitted": False,
        "reason": (
            "The newer local object index raises strict current target-in-pool "
            "to 10/18, but missing current official documents and zero current "
            "exact-SQL coverage still block ranking admission."
        ),
    }
    row = next(
        item
        for item in packet["qrels"]
        if (
            item["case_key"],
            item["evidence_slot_id"],
            item["evidence_owner_ticker"],
        )
        == ("NVDA", "regulatory_risk_and_financial_reconciliation", "NVDA")
    )
    assert row["strict_current_target_in_pool"] is True
    assert row["selected_candidate"]["source_url"].endswith(
        "/000104581026000052/nvda-20260426.htm"
    )
    assert row["selected_candidate"]["published_at"] == "2026-05-20"


def test_unknown_successor_candidate_fails_closed() -> None:
    policy, inputs = _inputs()
    mutated = deepcopy(policy)
    mutated["adjudication_overrides"][0]["selected_source_key"] = "missing"
    with pytest.raises(
        S1InternalQrelsSuccessorError,
        match="internal_qrels_successor_selected_candidate_missing",
    ):
        build_internal_qrels_successor_packet(policy=mutated, inputs=inputs)
