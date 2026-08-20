from __future__ import annotations

from copy import deepcopy

import pytest

from sec_agent.canonical_runtime import canonical_digest
from sec_agent.research.multi_agent_preview import validate_specialist_workpaper
from sec_agent.research.multi_agent_successor import (
    MultiAgentSuccessorError,
    compile_completed_workpaper_frontier_node,
    compile_fresh_frontier_node,
    compile_successor_execution_frontier,
    validate_successor_execution_frontier,
)


def _context(agent_id: str, session_id: str) -> dict:
    body = {
        "schema_version": "fin_ia_specialist_context_v1_0",
        "agent": {"agent_id": agent_id},
        "authority": {"allowed": True},
        "case_fact_presence": {},
        "cell_analysis_view": {
            "cell": {
                "cell_evidence_views": [{"evidence_ref": "EV::ONE"}],
                "allowed_numeric_refs": ["NUM::ONE"],
                "allowed_numeric_relation_refs": ["REL::ONE"],
                "residual_gap_cards": [{"gap_ref": "GAP::ONE"}],
            }
        },
        "feedback_receipts": [
            {
                "session_id": session_id,
                "target_node_id": agent_id,
                "artifact_refs": ["challenge://CHALLENGE::ONE"],
            }
        ],
        "lead_plan": {},
        "plan_opinion": {},
        "prior_workpaper": {},
    }
    return {**body, "context_digest": canonical_digest(body)}


def _workpaper(context: dict, agent_id: str) -> dict:
    return validate_specialist_workpaper(
        {
            "schema_version": "fin_ia_specialist_workpaper_v1_0",
            "agent_id": agent_id,
            "thesis": "当前证据只支持一个有边界的公司层判断，不能把公司层结果变化单独归因给某一个产品或订单信号。",
            "confidence": "medium",
            "sourced_claims": [
                {
                    "claim": "现有官方披露只支持当前公司层观察，不支持单一产品因果归因。",
                    "authority": "bounded_inference",
                    "evidence_refs": ["EV::ONE"],
                    "numeric_refs": ["NUM::ONE"],
                    "numeric_relation_refs": ["REL::ONE"],
                }
            ],
            "mechanism": "经营结果可能同时受到业务规模、产品组合、采购成本、运营费用和交付节奏影响，现有证据不能把变化只分配给单一产品。",
            "alternative_explanations": ["其他业务组合和期间性项目也可能解释变化。"],
            "strongest_counterarguments": ["目前仍缺少产品表现到公司财务结果的直接桥接证据。"],
            "remaining_gap_refs": ["GAP::ONE"],
            "what_would_change": ["获得同期间产品利润桥后重裁决。"],
            "cross_role_challenges": [],
            "stop_reason": "当前材料足以形成有限结论。",
        },
        context=context,
        expected_agent_id=agent_id,
    )


def _failure() -> dict:
    return {
        "authority_ref": "authority.json",
        "authority_sha256": "a" * 64,
        "public_result_ref": "result.json",
        "public_result_sha256": "b" * 64,
        "public_result_digest": "c" * 64,
        "terminal_result_ref": "terminal.json",
        "terminal_result_sha256": "d" * 64,
        "terminal_result_digest": "e" * 64,
        "failure_code": "multi_agent_bound_workpaper_digest_invalid",
        "provider_attempt_count": 0,
    }


def _reasoning_budget_failure() -> dict:
    return {
        **_failure(),
        "failure_code": "model_gateway_reasoning_budget_exhausted",
        "provider_attempt_count": 3,
    }


def test_frontier_distinguishes_exact_reuse_and_derived_rebind() -> None:
    agent = "AGENT::DEMAND_QUALITY"
    original_context = _context(agent, "SESSION::OLD")
    workpaper = _workpaper(original_context, agent)
    exact = compile_completed_workpaper_frontier_node(
        challenge_id="CHALLENGE::ONE",
        node_id=agent + "::COUNTER_REPAIR",
        target_agent_id=agent,
        source_run_id="RUN::ONE",
        source_workpaper=workpaper,
        model_visible_context=original_context,
        source_terminal_ref="terminal.json",
        source_terminal_sha256="5" * 64,
        source_terminal_digest="6" * 64,
        source_request_ref="capture.json",
        source_request_sha256="1" * 64,
        source_request_digest="2" * 64,
    )
    rebound_context = _context(agent, "SESSION::MODEL-VISIBLE")
    rebound = compile_completed_workpaper_frontier_node(
        challenge_id="CHALLENGE::TWO",
        node_id=agent + "::COUNTER_REPAIR",
        target_agent_id=agent,
        source_run_id="RUN::TWO",
        source_workpaper=workpaper,
        model_visible_context=rebound_context,
        source_terminal_ref="terminal-two.json",
        source_terminal_sha256="7" * 64,
        source_terminal_digest="8" * 64,
        source_request_ref="capture-two.json",
        source_request_sha256="3" * 64,
        source_request_digest="4" * 64,
    )

    assert exact["disposition"] == "exact_reuse"
    assert rebound["disposition"] == "derived_digest_rebind"
    assert rebound["business_payload_digest"] == exact["business_payload_digest"]
    assert rebound["source_workpaper_digest"] != rebound["normalized_workpaper_digest"]
    assert rebound["normalized_workpaper"]["context_digest"] == rebound_context["context_digest"]


def test_frontier_compiles_limits_and_fails_closed_on_mutation() -> None:
    agent = "AGENT::DEMAND_QUALITY"
    context = _context(agent, "SESSION::ONE")
    completed = compile_completed_workpaper_frontier_node(
        challenge_id="CHALLENGE::ONE",
        node_id=agent + "::COUNTER_REPAIR",
        target_agent_id=agent,
        source_run_id="RUN::ONE",
        source_workpaper=_workpaper(context, agent),
        model_visible_context=context,
        source_terminal_ref="terminal.json",
        source_terminal_sha256="5" * 64,
        source_terminal_digest="6" * 64,
        source_request_ref="capture.json",
        source_request_sha256="1" * 64,
        source_request_digest="2" * 64,
    )
    pending = compile_fresh_frontier_node(
        challenge_id="CHALLENGE::TWO",
        node_id="AGENT::SUPPLY_RELATIONSHIP::COUNTER_REPAIR",
        target_agent_id="AGENT::SUPPLY_RELATIONSHIP",
        disposition="pending_fresh",
        reason_code="predecessor_never_completed",
    )
    frontier = compile_successor_execution_frontier(
        case_key="DELL",
        cell_id="MULTI_AGENT_PREVIEW",
        accepted_challenge_ids=["CHALLENGE::ONE", "CHALLENGE::TWO"],
        lead_coordination_checkpoint_digest="f" * 64,
        predecessor_failure=_failure(),
        nodes=[completed, pending],
    )

    assert validate_successor_execution_frontier(frontier) == frontier
    assert frontier["execution_limits"]["maximum_new_model_nodes"] == 6
    assert frontier["execution_limits"]["reused_completed_challenge_repair_count"] == 1

    mutated = deepcopy(frontier)
    mutated["nodes"][0]["normalized_workpaper"]["thesis"] += " 未授权改写。"
    with pytest.raises(
        MultiAgentSuccessorError,
        match="multi_agent_successor_frontier_digest_invalid",
    ):
        validate_successor_execution_frontier(mutated)


def test_frontier_can_resume_after_downstream_reasoning_budget_failure() -> None:
    agents = (
        "AGENT::DEMAND_QUALITY",
        "AGENT::CASH_CONVERSION",
        "AGENT::SUPPLY_RELATIONSHIP",
    )
    completed = []
    for index, agent in enumerate(agents, start=1):
        context = _context(agent, f"SESSION::{index}")
        completed.append(
            compile_completed_workpaper_frontier_node(
                challenge_id=f"CHALLENGE::{index}",
                node_id=agent + "::COUNTER_REPAIR",
                target_agent_id=agent,
                source_run_id=f"RUN::{index}",
                source_workpaper=_workpaper(context, agent),
                model_visible_context=context,
                source_terminal_ref=f"terminal-{index}.json",
                source_terminal_sha256=str(index) * 64,
                source_terminal_digest=str(index + 3) * 64,
                source_request_ref=f"capture-{index}.json",
                source_request_sha256=str(index + 6) * 64,
                source_request_digest=str(index + 3) * 64,
            )
        )
    frontier = compile_successor_execution_frontier(
        case_key="DELL",
        cell_id="MULTI_AGENT_PREVIEW",
        accepted_challenge_ids=[f"CHALLENGE::{index}" for index in range(1, 4)],
        lead_coordination_checkpoint_digest="f" * 64,
        predecessor_failure=_reasoning_budget_failure(),
        nodes=completed,
    )

    assert validate_successor_execution_frontier(frontier) == frontier
    assert frontier["execution_limits"][
        "reused_completed_challenge_repair_count"
    ] == 3
    assert frontier["execution_limits"][
        "maximum_new_counter_challenge_repairs"
    ] == 0
    assert frontier["execution_limits"]["maximum_new_model_nodes"] == 5
