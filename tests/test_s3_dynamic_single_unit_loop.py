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
    bind_reflection_submission,
    compile_reflection_artifacts,
    compile_reflection_submission_messages,
    compile_initial_messages,
    compile_material_requirement_blueprints,
    compile_request_catalog,
    compile_workpaper_context,
    compile_workpaper_repair_context,
    compile_workpaper_submission_view,
    load_dynamic_single_unit_policy,
    reflection_tool,
    reflection_submission_tool,
    request_evidence_tool,
    validate_reflection_payload,
    validate_reflection_submission,
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
    tool = reflection_tool(
        policy=policy,
        request_catalog=catalog,
        feedback_receipts=feedback,
        accepted_evidence_refs=["EV::ONE"],
        executed_request_ids=executed,
        round_index=1,
    )
    feedback_schema = tool["function"]["parameters"]["properties"][
        "feedback_refs"
    ]
    assert feedback_schema["minItems"] == 1
    assert feedback_schema["maxItems"] == 1
    assert feedback_schema["items"]["enum"] == ["FEEDBACK::ONE"]
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


def test_reflection_cannot_silently_ignore_one_current_feedback_receipt(
    policy: dict, catalog: dict
) -> None:
    feedback = [
        {"feedback_id": "FEEDBACK::ONE"},
        {"feedback_id": "FEEDBACK::TWO"},
    ]
    tool = reflection_tool(
        policy=policy,
        request_catalog=catalog,
        feedback_receipts=feedback,
        accepted_evidence_refs=[],
        executed_request_ids=["REQ::DELL::PVM_BRIDGE::V1"],
        round_index=1,
    )
    schema = tool["function"]["parameters"]["properties"]["feedback_refs"]
    assert schema["minItems"] == 2
    assert schema["maxItems"] == 2
    with pytest.raises(DynamicSingleUnitLoopError) as exc:
        validate_reflection_payload(
            _reflection(
                round_index=1,
                feedback_refs=["FEEDBACK::ONE"],
                next_request_ids=["REQ::DELL::SUPPLY_RELATIONSHIP::V1"],
                decision="continue",
            ),
            policy=policy,
            request_catalog=catalog,
            feedback_receipts=feedback,
            accepted_evidence_refs=[],
            executed_request_ids=["REQ::DELL::PVM_BRIDGE::V1"],
            round_index=1,
        )
    assert exc.value.code == "dynamic_single_unit_reflection_feedback_invalid"


def test_reflection_empty_enums_compile_to_empty_arrays_not_fake_refs(
    policy: dict, catalog: dict
) -> None:
    all_request_ids = [row["request_id"] for row in catalog["requests"]]
    tool = reflection_tool(
        policy=policy,
        request_catalog=catalog,
        feedback_receipts=[],
        accepted_evidence_refs=[],
        executed_request_ids=all_request_ids,
        round_index=2,
    )
    properties = tool["function"]["parameters"]["properties"]
    assert properties["feedback_refs"]["minItems"] == 0
    assert properties["feedback_refs"]["maxItems"] == 0
    assert properties["next_request_ids"]["maxItems"] == 0
    assert properties["graph_hypotheses"]["items"]["properties"][
        "evidence_refs"
    ]["maxItems"] == 0

    validated = validate_reflection_payload(
        _reflection(
            round_index=2,
            feedback_refs=[],
            next_request_ids=[],
            decision="stop_no_progress",
        ),
        policy=policy,
        request_catalog=catalog,
        feedback_receipts=[],
        accepted_evidence_refs=[],
        executed_request_ids=all_request_ids,
        round_index=2,
    )
    assert validated["feedback_refs"] == []
    assert validated["next_request_ids"] == []


def test_stop_sufficient_is_compiled_to_no_progress_before_coverage_complete(
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
    artifacts = compile_reflection_artifacts(
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
    assert artifacts["stop_decision"]["decision"] == "stop_no_progress"
    assert artifacts["stop_decision"]["decided_by_agent_id"] == (
        "HARNESS::DYNAMIC-RESEARCH-STOP-COMPILER"
    )
    receipt = artifacts["stop_compilation_receipt"]
    assert receipt["proposed_stop_decision"] == "stop_sufficient"
    assert receipt["effective_stop_decision"] == "stop_no_progress"
    assert receipt["model_research_judgment_changed"] is False


def test_strict_reflection_submission_binds_local_identity_and_requires_missing_coverage(
    policy: dict, catalog: dict
) -> None:
    executed = ["REQ::DELL::PVM_BRIDGE::V1"]
    tool = reflection_submission_tool(
        policy=policy,
        request_catalog=catalog,
        feedback_receipts=[{"feedback_id": "FEEDBACK::ONE"}],
        accepted_evidence_refs=["EV::ONE"],
        executed_request_ids=executed,
        open_gap_refs=["GAP::ONE"],
        round_index=1,
    )
    parameters = tool["function"]["parameters"]
    assert "schema_version" not in parameters["properties"]
    assert "round_id" not in parameters["properties"]
    assert parameters["properties"]["proposed_stop_decision"]["enum"] == [
        "continue"
    ]
    relation = parameters["properties"]["graph_hypotheses"]["items"][
        "properties"
    ]["relationship_direction"]
    assert relation["maxLength"] == 80
    assert relation["pattern"].startswith("^")

    model_owned = _reflection(
        round_index=1,
        feedback_refs=["FEEDBACK::ONE"],
        next_request_ids=["REQ::DELL::SUPPLY_RELATIONSHIP::V1"],
        decision="continue",
        evidence_refs=["EV::ONE"],
    )
    model_owned.pop("schema_version")
    model_owned.pop("round_id")
    bound, receipt = bind_reflection_submission(model_owned, round_index=1)
    assert bound["schema_version"] == REFLECTION_PAYLOAD_SCHEMA_VERSION
    assert receipt["locally_bound_fields"] == ["round_id", "schema_version"]
    validated, validated_receipt = validate_reflection_submission(
        model_owned,
        policy=policy,
        request_catalog=catalog,
        feedback_receipts=[{"feedback_id": "FEEDBACK::ONE"}],
        accepted_evidence_refs=["EV::ONE"],
        executed_request_ids=executed,
        open_gap_refs=["GAP::ONE"],
        round_index=1,
    )
    assert validated["proposed_stop_decision"] == "continue"
    assert validated_receipt == receipt
    messages = compile_reflection_submission_messages(
        source_draft="{invalid but preserved research draft}",
        source_capture_digest="a" * 64,
        tool=tool,
    )
    rendered = json.dumps(messages, ensure_ascii=False)
    assert "strict contract mapper" in rendered
    assert "invalid but preserved" in rendered

    model_owned["proposed_stop_decision"] = "stop_sufficient"
    model_owned["next_request_ids"] = []
    with pytest.raises(DynamicSingleUnitLoopError) as exc:
        validate_reflection_submission(
            model_owned,
            policy=policy,
            request_catalog=catalog,
            feedback_receipts=[{"feedback_id": "FEEDBACK::ONE"}],
            accepted_evidence_refs=["EV::ONE"],
            executed_request_ids=executed,
            open_gap_refs=["GAP::ONE"],
            round_index=1,
        )
    assert exc.value.code == "dynamic_single_unit_reflection_required_coverage_deferred"


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

    submission = compile_workpaper_submission_view(context)
    assert submission["source_context_digest"] == context["context_digest"]
    assert [row["evidence_ref"] for row in submission["reviewed_evidence"]] == [
        "EV::ONE"
    ]
    assert {
        row.get("numeric_ref") or row.get("estimate_id")
        for row in submission["numeric_authorities"]
    } == {"NUM::ONE", "ESTIMATE::ONE"}
    assert [
        row["numeric_relation_ref"] for row in submission["numeric_relations"]
    ] == ["REL::ONE"]
    assert [row["gap_ref"] for row in submission["residual_gaps"]] == [
        "GAP::ONE"
    ]
    assert "cell_analysis_view" not in submission
    assert "evidence_fact_catalog" not in submission

    tampered = deepcopy(context)
    tampered["objective"]["research_question"] = "tampered"
    with pytest.raises(
        DynamicSingleUnitLoopError,
        match="workpaper_submission_context_invalid",
    ):
        compile_workpaper_submission_view(tampered)

    prior_body = {
        "schema_version": "fin_ia_multi_agent_specialist_workpaper_v1_0",
        "agent_id": "AGENT::VALUE_CAPTURE",
        "thesis": "prior",
    }
    from sec_agent.canonical_runtime.session import canonical_digest

    prior = {**prior_body, "workpaper_digest": canonical_digest(prior_body)}
    feedback = {
        "feedback_id": "FEEDBACK::ROLE-REPAIR",
        "session_id": "SESSION::VALUE",
        "source_node_id": "AGENT::COUNTEREVIDENCE",
        "target_node_id": "AGENT::VALUE_CAPTURE",
        "failure_class": "material_cross_role_judgment_challenge",
        "failure_code": "recheck_judgment",
        "owning_plane": "agent_work_mode_plane",
        "owning_stage": "S3",
        "artifact_refs": ["challenge://one"],
        "model_visible_summary": "Recheck the causal bridge.",
        "permitted_next_actions": ["Revise the affected judgment."],
        "forbidden_interpretations": ["Do not invent evidence."],
        "created_at": "2026-08-23T12:00:00+00:00",
    }
    repaired = compile_workpaper_repair_context(
        context=context,
        prior_workpaper=prior,
        feedback_receipts=[feedback],
    )
    assert repaired["repair_state"]["new_evidence_authority_granted"] is False
    assert repaired["repair_state"]["accepted_feedback_refs"] == [
        "FEEDBACK::ROLE-REPAIR"
    ]
    assert repaired["source_context_digest"] == context["context_digest"]

    foreign = deepcopy(feedback)
    foreign["target_node_id"] = "AGENT::DEMAND_QUALITY"
    with pytest.raises(
        DynamicSingleUnitLoopError,
        match="dynamic_single_unit_repair_feedback_invalid",
    ):
        compile_workpaper_repair_context(
            context=context,
            prior_workpaper=prior,
            feedback_receipts=[foreign],
        )
