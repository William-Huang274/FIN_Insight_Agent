from __future__ import annotations

from copy import deepcopy

import pytest

from sec_agent.canonical_runtime import canonical_digest
from sec_agent.research.multi_agent_preview import (
    MultiAgentPreviewError,
    SPECIALIST_AGENT_IDS,
    compile_role_evaluation_progress_checkpoint,
    validate_role_evaluation,
    validate_role_evaluation_progress_checkpoint,
    validate_specialist_workpaper,
)
from sec_agent.research.multi_agent_successor import (
    HIERARCHICAL_EVALUATION_STRATEGY,
    MultiAgentSuccessorError,
    compile_completed_workpaper_frontier_node,
    compile_fresh_frontier_node,
    compile_hierarchical_evaluator_zero_call_proof,
    compile_successor_execution_frontier,
    validate_hierarchical_evaluator_zero_call_proof,
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
            "cross_role_challenges": (
                [
                    {
                        "target_agent_id": "AGENT::DEMAND_QUALITY",
                        "challenge": "需求证据可能仍混合了真实部署与短期提前采购。",
                        "material_reason": "若无法区分两者，需求持续性的置信度会被高估。",
                        "requested_action": "request_new_evidence",
                    }
                ]
                if agent_id == "AGENT::COUNTEREVIDENCE"
                else []
            ),
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


def test_frontier_compiles_hierarchical_evaluator_capacity_from_real_roles() -> None:
    agents = (
        "AGENT::DEMAND_QUALITY",
        "AGENT::CASH_CONVERSION",
        "AGENT::SUPPLY_RELATIONSHIP",
    )
    completed = []
    for index, agent in enumerate(agents, start=1):
        context = _context(agent, f"SESSION::H::{index}")
        completed.append(
            compile_completed_workpaper_frontier_node(
                challenge_id=f"CHALLENGE::H::{index}",
                node_id=agent + "::COUNTER_REPAIR",
                target_agent_id=agent,
                source_run_id=f"RUN::H::{index}",
                source_workpaper=_workpaper(context, agent),
                model_visible_context=context,
                source_terminal_ref=f"terminal-h-{index}.json",
                source_terminal_sha256=str(index) * 64,
                source_terminal_digest=str(index + 3) * 64,
                source_request_ref=f"capture-h-{index}.json",
                source_request_sha256=str(index + 6) * 64,
                source_request_digest=str(index + 3) * 64,
            )
        )
    frontier = compile_successor_execution_frontier(
        case_key="DELL",
        cell_id="MULTI_AGENT_PREVIEW",
        accepted_challenge_ids=[
            f"CHALLENGE::H::{index}" for index in range(1, 4)
        ],
        lead_coordination_checkpoint_digest="f" * 64,
        predecessor_failure=_reasoning_budget_failure(),
        nodes=completed,
        evaluation_strategy=HIERARCHICAL_EVALUATION_STRATEGY,
    )

    assert validate_successor_execution_frontier(frontier) == frontier
    assert frontier["evaluation_strategy"] == HIERARCHICAL_EVALUATION_STRATEGY
    assert frontier["execution_limits"]["maximum_new_model_nodes"] == 13
    assert frontier["execution_limits"][
        "maximum_initial_role_evaluation_nodes"
    ] == 6
    assert frontier["execution_limits"]["maximum_cross_role_evaluation_nodes"] == 2
    assert frontier["execution_limits"][
        "maximum_affected_role_reevaluation_nodes"
    ] == 2
    assert frontier["constraints"][
        "cross_role_audit_consumes_reviewed_summaries_only"
    ] is True

    role_receipts = [
        {
            "agent_id": agent_id,
            "workpaper_digest": str(index) * 64,
            "context_digest": str(index + 1) * 64,
            "content_view_digest": str(index + 2) * 64,
            "input_characters": 10_000 + index,
            "evidence_ref_count": 2,
            "numeric_ref_count": 1,
            "numeric_relation_ref_count": 1,
            "typed_gap_ref_count": 1,
        }
        for index, agent_id in enumerate(SPECIALIST_AGENT_IDS, start=1)
    ]
    proof = compile_hierarchical_evaluator_zero_call_proof(
        frontier_ref="frontier.json",
        frontier_sha256="a" * 64,
        frontier=frontier,
        role_view_receipts=role_receipts,
        cross_role_view_receipt={
            "cross_role_view_digest": "b" * 64,
            "input_characters": 30_000,
            "role_count": 6,
            "referenced_authority_included": False,
        },
        local_case_absence_blocking_finding_count=0,
        mutation_checks={
            "missing_role_fails_closed": True,
            "wrong_role_target_fails_closed": True,
            "unresolved_authority_ref_fails_closed": True,
            "workpaper_permutation_is_stable": True,
            "frontier_budget_mutation_fails_closed": True,
            "unaffected_role_reevaluation_is_forbidden": True,
        },
        fake_execution_receipt={
            "pass_without_repair_node_count": 8,
            "maximum_two_repair_path_node_count": 13,
            "third_repair_path_node_count": 15,
            "maximum_authorized_model_nodes": 13,
            "conditional_writer_count": 1,
            "unaffected_role_reevaluation_count": 0,
        },
    )
    assert validate_hierarchical_evaluator_zero_call_proof(
        proof, frontier=frontier
    ) == proof

    mutated = deepcopy(proof)
    mutated["mutation_checks"]["wrong_role_target_fails_closed"] = False
    body = {key: value for key, value in mutated.items() if key != "result_digest"}
    mutated["result_digest"] = canonical_digest(body)
    with pytest.raises(
        MultiAgentSuccessorError,
        match="multi_agent_hierarchical_proof_mutation_invalid",
    ):
        validate_hierarchical_evaluator_zero_call_proof(
            mutated, frontier=frontier
        )


def test_role_evaluation_progress_checkpoint_reuses_completed_prefix() -> None:
    contexts = {
        agent_id: _context(agent_id, f"SESSION::EVAL::{index}")
        for index, agent_id in enumerate(SPECIALIST_AGENT_IDS, start=1)
    }
    workpapers = [
        _workpaper(contexts[agent_id], agent_id)
        for agent_id in SPECIALIST_AGENT_IDS
    ]
    demand = workpapers[0]
    evaluation = validate_role_evaluation(
        {
            "schema_version": "fin_ia_multi_agent_evaluation_v1_0",
            "findings": [],
            "cross_role_conflicts": [],
            "report_may_proceed": True,
        },
        workpaper=demand,
    )

    def attempt(phase: str, status: str, finish_reason: str) -> dict:
        return {
            "attempt_id": f"ATTEMPT::{phase}",
            "phase": phase,
            "status": status,
            "finish_reason": finish_reason,
            "request_capture_ref": f"captures/{phase}-request.json",
            "request_digest": "a" * 64,
            "response_capture_ref": f"captures/{phase}-response.json",
            "response_digest": "b" * 64,
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }

    terminal_body = {
        "status": "multi_agent_preview_terminal_failure_preserved",
        "failure_code": "model_gateway_reasoning_budget_exhausted",
        "node_executions": [
            {
                "agent_id": "EVAL::ROLE::DEMAND_QUALITY",
                "node_id": "EVAL::ROLE::DEMAND_QUALITY::CONTENT_AUDIT_R1",
                "attempts": [
                    attempt("analysis", "analysis_draft_valid", "stop"),
                    attempt("submission", "contract_valid", "tool_calls"),
                ],
                "validated_payload": evaluation,
                "validated_payload_digest": canonical_digest(evaluation),
            }
        ],
    }
    terminal = {
        **terminal_body,
        "full_result_digest": canonical_digest(terminal_body),
    }
    checkpoint = compile_role_evaluation_progress_checkpoint(
        case_key="DELL",
        source_run_id="RUN::EVALUATOR",
        source_authority_ref="authority.json",
        source_authority_sha256="1" * 64,
        source_public_result_ref="result.json",
        source_public_result_sha256="2" * 64,
        source_public_result_digest="3" * 64,
        source_terminal_result_ref="terminal.json",
        source_terminal_result_sha256="4" * 64,
        terminal_failure=terminal,
        evaluator_analysis_profile_ref="profile.json",
        evaluator_analysis_profile_sha256="5" * 64,
        workpapers=workpapers,
        contexts=contexts,
    )

    assert validate_role_evaluation_progress_checkpoint(
        checkpoint,
        terminal_failure=terminal,
        workpapers=workpapers,
        contexts=contexts,
    ) == checkpoint
    assert checkpoint["completed_agent_ids"] == [
        "AGENT::DEMAND_QUALITY"
    ]
    assert checkpoint["pending_agent_ids"][0] == (
        "AGENT::OPERATING_PERFORMANCE"
    )
    frontier = compile_successor_execution_frontier(
        case_key="DELL",
        cell_id="MULTI_AGENT_PREVIEW",
        accepted_challenge_ids=[],
        lead_coordination_checkpoint_digest="f" * 64,
        predecessor_failure=_reasoning_budget_failure(),
        nodes=[],
        evaluation_strategy=HIERARCHICAL_EVALUATION_STRATEGY,
        completed_role_evaluation_agent_ids=checkpoint[
            "completed_agent_ids"
        ],
        evaluation_progress_checkpoint_digest=checkpoint[
            "checkpoint_digest"
        ],
    )
    assert validate_successor_execution_frontier(frontier) == frontier
    assert frontier["schema_version"].endswith("v1_2")
    assert frontier["execution_limits"]["maximum_new_model_nodes"] == 12
    assert frontier["execution_limits"][
        "maximum_initial_role_evaluation_nodes"
    ] == 5
    assert frontier["execution_limits"]["reused_role_evaluation_count"] == 1
    assert frontier["constraints"][
        "completed_role_evaluation_rerun_forbidden"
    ] is True

    mutated = deepcopy(checkpoint)
    mutated["validated_role_evaluations"]["AGENT::DEMAND_QUALITY"][
        "report_may_proceed"
    ] = False
    mutated_body = {
        key: value for key, value in mutated.items() if key != "checkpoint_digest"
    }
    mutated["checkpoint_digest"] = canonical_digest(mutated_body)
    with pytest.raises(
        MultiAgentPreviewError,
        match="multi_agent_role_evaluation_checkpoint_recompile_drift",
    ):
        validate_role_evaluation_progress_checkpoint(
            mutated,
            terminal_failure=terminal,
            workpapers=workpapers,
            contexts=contexts,
        )
