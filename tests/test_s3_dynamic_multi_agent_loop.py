from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from retrieval.contracts import load_financial_research_kernel
from retrieval.route_compiler import load_query_object_fact_route_policy
from sec_agent.research.dynamic_multi_agent_loop import (
    DynamicMultiAgentLoopError,
    compile_dynamic_multi_agent_role_programs,
    compile_role_material_requirement_blueprints,
    compile_role_stop_decision,
    load_dynamic_multi_agent_loop_policy,
    normalize_bound_specialist_workpaper,
)
from sec_agent.research.multi_agent_preview import (
    SPECIALIST_WORKPAPER_SCHEMA_VERSION,
    compile_planner_payload_from_role_opinions,
    load_multi_agent_role_topology,
    validate_lead_plan_checkpoint,
    validate_specialist_plan_checkpoint,
    validate_specialist_workpaper,
)
from sec_agent.research.multi_agent_preview_runtime import (
    load_preview_planning_policy,
)
from sec_agent.runtime_resource_registry import read_registered_runtime_json
from sec_agent.research.reviewed_evidence_pack import canonical_digest


ROOT = Path(__file__).resolve().parents[1]


def _load(ref: str) -> dict:
    return json.loads((ROOT / ref).read_text(encoding="utf-8"))


def _inputs() -> tuple:
    topology = load_multi_agent_role_topology(
        _load("configs/research/fin_ia_0_1_3_multi_agent_role_topology_v1_0.json")
    )
    checkpoint = validate_specialist_plan_checkpoint(
        _load(
            "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_R3_specialist_plan_checkpoint_v1_0.json"
        ),
        topology=topology,
    )
    opinions = checkpoint["specialist_plans"]
    lead = validate_lead_plan_checkpoint(
        _load(
            "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_R6_lead_plan_checkpoint_v1_0.json"
        ),
        opinions=opinions,
        topology=topology,
    )["lead_plan"]
    kernel = load_financial_research_kernel(
        read_registered_runtime_json(
            ROOT, "application.config.current_financial_research_kernel"
        )
    )
    route = load_query_object_fact_route_policy(
        read_registered_runtime_json(
            ROOT, "application.config.current_query_object_fact_route_policy"
        ),
        kernel,
    )
    planning = load_preview_planning_policy(ROOT, route_policy=route)
    compiled = compile_planner_payload_from_role_opinions(
        objective_id="OBJECTIVE::TEST",
        opinions=opinions,
        lead_plan=lead,
        topology=topology,
    )
    return topology, kernel, route, planning, compiled


def test_role_partition_recovers_all_thirteen_facets_before_execution() -> None:
    topology, kernel, route, planning, compiled = _inputs()
    result = compile_dynamic_multi_agent_role_programs(
        policy=_load(
            "configs/research/fin_ia_0_1_3_s3_current_dynamic_multi_agent_loop_policy_v1_0.json"
        ),
        topology=topology,
        objective_payload=_load(
            "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_objective_v1_0.json"
        ),
        planner_compilation=compiled,
        kernel=kernel,
        route_policy=route,
        planning_policy=planning,
    )

    assert result["summary"] == {
        "specialist_role_count": 6,
        "assigned_facet_count": 13,
        "compiled_request_count": 13,
        "deferred_facet_count": 0,
        "independent_session_required_count": 6,
        "model_calls": 0,
        "network_calls": 0,
    }
    supply = next(
        row
        for row in result["role_programs"]
        if row["agent_id"] == "AGENT::SUPPLY_RELATIONSHIP"
    )
    assert supply["facet_ids"] == [
        "upstream_capacity_context",
        "counterparty_direct_mention",
        "subject_relationship_disclosure",
    ]
    assert len(supply["requests"]) == 3
    assert supply["loop_policy"]["coverage_groups"][
        "counterparty_direct_mention"
    ]
    blueprints = compile_role_material_requirement_blueprints(supply)
    assert set(blueprints) == {
        row["request_id"] for row in supply["requests"]
    }
    direct_mention = next(
        row
        for row in supply["requests"]
        if row["requested_facet_ids"] == ["counterparty_direct_mention"]
    )
    assert {
        row["role"]
        for row in blueprints[direct_mention["request_id"]][
            "material_requirements"
        ]
    } == {"direct", "context"}


def test_role_partition_fails_closed_when_one_facet_is_missing() -> None:
    topology, kernel, route, planning, compiled = _inputs()
    mutated = deepcopy(compiled)
    mutated["planner_payload"]["atoms"] = [
        row
        for row in mutated["planner_payload"]["atoms"]
        if row["facet_id"] != "counterparty_direct_mention"
    ]
    with pytest.raises(
        DynamicMultiAgentLoopError,
        match="dynamic_multi_agent_atom_partition_invalid",
    ):
        compile_dynamic_multi_agent_role_programs(
            policy=_load(
                "configs/research/fin_ia_0_1_3_s3_current_dynamic_multi_agent_loop_policy_v1_0.json"
            ),
            topology=topology,
            objective_payload=_load(
                "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_objective_v1_0.json"
            ),
            planner_compilation=mutated,
            kernel=kernel,
            route_policy=route,
            planning_policy=planning,
        )


def test_role_policy_rejects_overlapping_facet_ownership() -> None:
    topology, *_ = _inputs()
    policy = _load(
        "configs/research/fin_ia_0_1_3_s3_current_dynamic_multi_agent_loop_policy_v1_0.json"
    )
    policy["specialist_roles"][1]["facet_ids"][0] = "orders_and_backlog"
    with pytest.raises(
        DynamicMultiAgentLoopError,
        match="dynamic_multi_agent_policy_role_invalid",
    ):
        load_dynamic_multi_agent_loop_policy(policy, topology=topology)


def test_role_stop_distinguishes_catalog_exhaustion_from_sufficiency() -> None:
    assert compile_role_stop_decision(
        next_request_ids=["REQ::NEXT"], open_gap_refs=[], feedback_refs=[]
    ) == "continue"
    assert compile_role_stop_decision(
        next_request_ids=[], open_gap_refs=["GAP::OPEN"], feedback_refs=[]
    ) == "stop_no_progress"
    assert compile_role_stop_decision(
        next_request_ids=[], open_gap_refs=[], feedback_refs=["FEEDBACK::OPEN"]
    ) == "stop_no_progress"
    assert compile_role_stop_decision(
        next_request_ids=[], open_gap_refs=[], feedback_refs=[]
    ) == "stop_sufficient"


def _minimal_workpaper_context(agent_id: str) -> dict:
    return {
        "context_digest": "CONTEXT::BOUND",
        "agent": {"agent_id": agent_id},
        "cell_analysis_view": {
            "cell": {
                "cell_evidence_views": [{"evidence_ref": "EV::ONE"}],
                "allowed_numeric_refs": ["NUM::ONE"],
                "allowed_numeric_relation_refs": ["REL::ONE"],
                "residual_gap_cards": [{"gap_ref": "GAP::ONE"}],
            }
        },
    }


def _bound_workpaper(agent_id: str) -> tuple[dict, dict]:
    context = _minimal_workpaper_context(agent_id)
    payload = {
        "schema_version": SPECIALIST_WORKPAPER_SCHEMA_VERSION,
        "agent_id": agent_id,
        "thesis": "现有证据支持有限的公司层判断，但不支持把全部利润变化归因于单一产品。",
        "confidence": "medium",
        "sourced_claims": [
            {
                "claim": "公司披露直接支持当前经营结果，但产品到利润的桥接仍不完整。",
                "authority": "sourced_fact",
                "evidence_refs": ["EV::ONE"],
                "numeric_refs": ["NUM::ONE"],
                "numeric_relation_refs": ["REL::ONE"],
            }
        ],
        "mechanism": "规模、组合、成本和费用杠杆可能共同影响利润，当前资料不能只分配给单一产品。",
        "alternative_explanations": ["其他业务组合也可能解释公司层利润变化。"],
        "strongest_counterarguments": ["产品到公司利润的直接桥接仍然缺失。"],
        "remaining_gap_refs": ["GAP::ONE"],
        "what_would_change": ["获得同期间产品收入和利润桥后重新裁决。"],
        "cross_role_challenges": [],
        "stop_reason": "当前证据只支持有限结论，剩余问题保留为可追溯缺口。",
    }
    return (
        validate_specialist_workpaper(
            payload,
            context=context,
            expected_agent_id=agent_id,
        ),
        context,
    )


def test_workpaper_digest_normalization_accepts_only_reproducible_legacy_bug() -> None:
    agent_id = "AGENT::VALUE_CAPTURE"
    bound, context = _bound_workpaper(agent_id)
    canonical, canonical_receipt = normalize_bound_specialist_workpaper(
        bound,
        context=context,
        expected_agent_id=agent_id,
    )
    assert canonical == bound
    assert canonical_receipt["status"] == "canonical"

    legacy = deepcopy(bound)
    legacy["workpaper_digest"] = canonical_digest(bound)
    normalized, receipt = normalize_bound_specialist_workpaper(
        legacy,
        context=context,
        expected_agent_id=agent_id,
        allow_legacy_double_hash=True,
    )
    assert normalized == bound
    assert receipt["status"] == "legacy_double_hash_normalized"
    assert receipt["input_workpaper_digest"] == legacy["workpaper_digest"]
    assert receipt["canonical_workpaper_digest"] == bound["workpaper_digest"]
    assert receipt["content_changed"] is False
    assert receipt["authority_refs_changed"] is False

    with pytest.raises(
        DynamicMultiAgentLoopError,
        match="dynamic_multi_agent_bound_workpaper_digest_invalid",
    ):
        normalize_bound_specialist_workpaper(
            legacy,
            context=context,
            expected_agent_id=agent_id,
        )

    tampered = deepcopy(legacy)
    tampered["thesis"] += " 未经摘要绑定的改写。"
    with pytest.raises(
        DynamicMultiAgentLoopError,
        match="dynamic_multi_agent_bound_workpaper_digest_invalid",
    ):
        normalize_bound_specialist_workpaper(
            tampered,
            context=context,
            expected_agent_id=agent_id,
            allow_legacy_double_hash=True,
        )
