from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.research.dynamic_single_unit_loop import (  # noqa: E402
    DynamicSingleUnitLoopError,
    REFLECTION_PAYLOAD_SCHEMA_VERSION,
    REQUEST_PAYLOAD_SCHEMA_VERSION,
    compile_reflection_artifacts,
    compile_initial_messages,
    compile_material_requirement_blueprints,
    compile_request_catalog,
    compile_workpaper_context,
    load_dynamic_single_unit_policy,
    reflection_tool,
    request_evidence_tool,
    validate_reflection_payload,
    validate_request_selection,
)


POLICY_REF = (
    ROOT
    / "configs/research/"
    "fin_ia_0_1_3_s3_dell_dynamic_single_unit_loop_policy_v1_0.json"
)
PROGRAM_REF = (
    ROOT
    / "configs/retrieval/"
    "fin_ia_0_1_3_s1_dell_proposition_coverage_execution_program_v1_1.json"
)
READINESS_REF = (
    ROOT
    / "configs/retrieval/"
    "fin_ia_0_1_3_s1_s2_dell_value_capture_task_readiness_result_v1_0.json"
)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def policy() -> dict:
    return load_dynamic_single_unit_policy(_json(POLICY_REF))


@pytest.fixture(scope="module")
def program() -> dict:
    return _json(PROGRAM_REF)


@pytest.fixture(scope="module")
def catalog(policy: dict, program: dict) -> dict:
    return compile_request_catalog(
        policy=policy,
        program=program,
        task_readiness=_json(READINESS_REF),
    )


def test_initial_message_contains_no_answer_pack_or_numeric_fact(
    policy: dict, catalog: dict
) -> None:
    messages = compile_initial_messages(policy=policy, request_catalog=catalog)
    rendered = json.dumps(messages, ensure_ascii=False)
    assert len(catalog["requests"]) == 12
    assert "evidence_ref" not in rendered.lower()
    assert "numeric_ref" not in rendered.lower()
    assert "source_url" not in rendered.lower()
    assert "reviewed_evidence" not in rendered.lower()
    assert "$43.8" not in rendered
    assert "戴尔 AI 服务器收入增长" in rendered


def test_request_tool_and_validator_fail_closed_on_repeat_and_cross_case(
    policy: dict, catalog: dict
) -> None:
    tool = request_evidence_tool(
        policy=policy,
        request_catalog=catalog,
        executed_request_ids=(),
        round_index=1,
    )
    allowed = tool["function"]["parameters"]["properties"]["request_ids"][
        "items"
    ]["enum"]
    assert len(allowed) == 12
    payload = {
        "schema_version": REQUEST_PAYLOAD_SCHEMA_VERSION,
        "round_id": "ROUND::1",
        "request_ids": ["REQ::DELL::PVM_BRIDGE::V1"],
        "research_rationale": "先建立收入、价格、数量和产品组合的可验证桥，再判断利润获取。",
        "expected_information_gain": "区分公司披露的收入事实与尚未披露的价格、销量和组合输入。",
    }
    validated = validate_request_selection(
        payload,
        policy=policy,
        request_catalog=catalog,
        executed_request_ids=(),
        round_index=1,
    )
    assert validated["request_ids"] == ["REQ::DELL::PVM_BRIDGE::V1"]

    with pytest.raises(DynamicSingleUnitLoopError) as repeated:
        validate_request_selection(
            payload,
            policy=policy,
            request_catalog=catalog,
            executed_request_ids=["REQ::DELL::PVM_BRIDGE::V1"],
            round_index=1,
        )
    assert repeated.value.code == "dynamic_single_unit_request_selection_scope_invalid"

    cross_case = deepcopy(payload)
    cross_case["request_ids"] = ["REQ::MU::PVM_BRIDGE::V1"]
    with pytest.raises(DynamicSingleUnitLoopError) as outside:
        validate_request_selection(
            cross_case,
            policy=policy,
            request_catalog=catalog,
            executed_request_ids=(),
            round_index=1,
        )
    assert outside.value.code == "dynamic_single_unit_request_selection_scope_invalid"


def test_owner_reviewed_material_scope_compiles_only_selected_requests(
    program: dict,
) -> None:
    selected = [
        "REQ::DELL::PVM_BRIDGE::V1",
        "REQ::DELL::VALUE_POOL_MARGIN::V1",
    ]
    blueprints = compile_material_requirement_blueprints(
        program=program,
        request_ids=selected,
    )
    assert set(blueprints) == set(selected)
    assert all(
        row["material_requirements"] for row in blueprints.values()
    )
    assert all(
        requirement["coverage_mode"] == "collective_axes"
        for row in blueprints.values()
        for requirement in row["material_requirements"]
    )


def _reflection(
    *,
    round_index: int,
    feedback_refs: list[str],
    next_request_ids: list[str],
    decision: str,
    evidence_refs: list[str] | None = None,
) -> dict:
    evidence_refs = evidence_refs or []
    return {
        "schema_version": REFLECTION_PAYLOAD_SCHEMA_VERSION,
        "round_id": f"ROUND::{round_index}",
        "reflection_summary": (
            "当前证据支持收入与分部利润同时改善，但仍缺产品级价格数量组合桥和上游分配证据；"
            "下一轮应定向补充未执行的供给、客户与反方路线，而不是扩大无边界搜索。"
        ),
        "answered_questions": ["已确认当前收入和分部利润的同期间事实锚点。"],
        "unresolved_questions": ["产品级利润桥和戴尔专属供应分配仍未解决。"],
        "feedback_refs": feedback_refs,
        "next_request_ids": next_request_ids,
        "graph_hypotheses": (
            [
                {
                    "source_entity": "MU",
                    "relationship_direction": "possible_upstream_supply_context_for",
                    "target_entity": "DELL",
                    "evidence_refs": evidence_refs,
                    "research_use": "仅用于下一轮供应关系检索，不作为戴尔已获得配额的事实。",
                }
            ]
            if evidence_refs
            else []
        ),
        "proposed_stop_decision": decision,
        "reason_codes": ["material_bridge_requires_targeted_follow_up"],
    }


def test_reflection_compiles_plan_delta_and_hypothesis_only_graph(
    policy: dict, catalog: dict
) -> None:
    feedback = [{"feedback_id": "FEEDBACK::ONE"}]
    executed = [
        "REQ::DELL::PRICE_CONFIGURATION::V1",
        "REQ::DELL::UNIT_VOLUME::V1",
        "REQ::DELL::PVM_BRIDGE::V1",
    ]
    next_ids = ["REQ::DELL::SUPPLY_RELATIONSHIP::V1"]
    reflection_tool(
        policy=policy,
        request_catalog=catalog,
        feedback_receipts=feedback,
        accepted_evidence_refs=["EV::ONE"],
        executed_request_ids=executed,
        round_index=1,
    )
    validated = validate_reflection_payload(
        _reflection(
            round_index=1,
            feedback_refs=["FEEDBACK::ONE"],
            next_request_ids=next_ids,
            decision="continue",
            evidence_refs=["EV::ONE"],
        ),
        policy=policy,
        request_catalog=catalog,
        feedback_receipts=feedback,
        accepted_evidence_refs=["EV::ONE"],
        executed_request_ids=executed,
        round_index=1,
    )
    artifacts = compile_reflection_artifacts(
        policy=policy,
        reflection=validated,
        session_id="SESSION::TEST",
        agent_id="AGENT::VALUE_CAPTURE",
        base_plan={"executed_request_ids": []},
        base_graph_digest="a" * 64,
        executed_request_ids=executed,
        open_gap_refs=["GAP::ONE"],
        model_calls_used=2,
    )
    assert artifacts["plan_delta"]["validation_status"] == "accepted"
    assert artifacts["accepted_plan"]["next_request_ids"] == next_ids
    assert artifacts["graph_delta"]["edge_additions"] == []
    assert artifacts["graph_delta"]["hypothesis_only_edges"]
    assert artifacts["graph_delta"]["fact_authority_granted"] is False
    assert artifacts["stop_decision"]["decision"] == "continue"


def test_stop_sufficient_rejected_before_all_proposition_groups_covered(
    policy: dict, catalog: dict
) -> None:
    payload = _reflection(
        round_index=1,
        feedback_refs=[],
        next_request_ids=[],
        decision="stop_sufficient",
    )
    validated = validate_reflection_payload(
        payload,
        policy=policy,
        request_catalog=catalog,
        feedback_receipts=[],
        accepted_evidence_refs=[],
        executed_request_ids=["REQ::DELL::PVM_BRIDGE::V1"],
        round_index=1,
    )
    with pytest.raises(DynamicSingleUnitLoopError) as exc:
        compile_reflection_artifacts(
            policy=policy,
            reflection=validated,
            session_id="SESSION::TEST",
            agent_id="AGENT::VALUE_CAPTURE",
            base_plan={"executed_request_ids": []},
            base_graph_digest="a" * 64,
            executed_request_ids=["REQ::DELL::PVM_BRIDGE::V1"],
            open_gap_refs=["GAP::ONE"],
            model_calls_used=2,
        )
    assert exc.value.code == "dynamic_single_unit_stop_sufficient_coverage_incomplete"


def test_workpaper_context_merges_rounds_without_candidate_promotion(
    policy: dict,
) -> None:
    round_one = {
        "reviewed_evidence": [
            {
                "evidence_ref": "EV::ONE",
                "source_visible_fact_excerpt": "reviewed source fact",
            }
        ],
        "numeric_facts": [
            {"numeric_ref": "NUM::ONE", "metric_id": "revenue"}
        ],
        "numeric_relations": [
            {
                "numeric_relation_ref": "REL::ONE",
                "current_numeric_ref": "NUM::ONE",
            }
        ],
        "residual_gaps": [{"gap_ref": "GAP::ONE", "gap_code": "missing"}],
        "task_quantitative_context": {
            "research_estimates": [
                {"estimate_id": "ESTIMATE::ONE", "metric_id": "shipments"}
            ],
            "scenarios": [
                {"scenario_id": "SCENARIO::ONE", "scenario_type": "base"}
            ],
        },
        "_dynamic_research_input": {
            "cells": [
                {
                    "cell_id": "CELL::value_capture",
                    "role_method_pack": {
                        "pack_id": "ROLE_METHOD::VALUE_CAPTURE::TEST",
                        "method_steps": [{"method_step_ref": "METHOD::ONE"}],
                    },
                    "graph_context_pack": {
                        "nodes": [],
                        "edges": [],
                        "authority": {"fact_authority": False},
                    },
                }
            ]
        },
    }
    context = compile_workpaper_context(
        policy=policy,
        round_responses=[round_one, deepcopy(round_one)],
        feedback_receipts=[],
        reflections=[],
        stop_decision={"decision": "stop_no_progress"},
    )
    cell = context["cell_analysis_view"]["cell"]
    assert len(cell["cell_evidence_views"]) == 1
    assert set(cell["allowed_numeric_refs"]) == {
        "NUM::ONE",
        "ESTIMATE::ONE",
    }
    assert cell["allowed_numeric_relation_refs"] == ["REL::ONE"]
    assert context["authority"]["candidate_or_graph_hypothesis_is_not_evidence"]
