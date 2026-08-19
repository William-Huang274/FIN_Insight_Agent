from __future__ import annotations

import json
from pathlib import Path

import pytest

from sec_agent.research.multi_agent_preview import (
    MULTI_AGENT_EVALUATION_SCHEMA_VERSION,
    MULTI_AGENT_REPORT_DRAFT_SCHEMA_VERSION,
    RESEARCH_LEAD_AGENT_ID,
    SPECIALIST_AGENT_IDS,
    SPECIALIST_PLAN_OPINION_SCHEMA_VERSION,
    SPECIALIST_WORKPAPER_SCHEMA_VERSION,
    MultiAgentPreviewError,
    compile_analysis_continuation_messages,
    compile_analysis_fragment_checkpoint,
    compile_challenge_catalog,
    compile_evaluation_messages,
    compile_lead_plan_messages,
    compile_lead_coordination_messages,
    compile_planner_payload_from_role_opinions,
    compile_report_messages,
    compile_specialist_plan_checkpoint,
    compile_specialist_plan_messages,
    compile_specialist_workpaper_messages,
    compile_token_budget_basis,
    evaluation_tool,
    lead_plan_tool,
    lead_coordination_tool,
    load_multi_agent_role_topology,
    local_case_absence_findings,
    report_draft_tool,
    specialist_plan_tool,
    specialist_workpaper_tool,
    validate_evaluation,
    validate_analysis_fragment_checkpoint,
    validate_lead_plan,
    validate_lead_coordination_decision,
    validate_report_draft,
    validate_specialist_plan_opinion,
    validate_specialist_plan_checkpoint,
    validate_specialist_workpaper,
)
from sec_agent.research.reviewed_evidence_pack import canonical_digest


ROOT = Path(__file__).resolve().parents[1]
TOPOLOGY = ROOT / "configs/research/fin_ia_0_1_3_multi_agent_role_topology_v1_0.json"


def _topology() -> dict:
    return load_multi_agent_role_topology(
        json.loads(TOPOLOGY.read_text(encoding="utf-8"))
    )


def _analysis_checkpoint(*, draft: str = "Preserved visible Lead draft with bounded facts.") -> dict:
    return compile_analysis_fragment_checkpoint(
        case_key="DELL",
        run_id="PREVIEW-R4",
        node_id="RESEARCH-LEAD-PLAN",
        source_authority_ref="authority.json",
        source_authority_sha256="a" * 64,
        source_public_result_ref="result.json",
        source_public_result_sha256="b" * 64,
        source_public_result_digest="c" * 64,
        request_capture_ref="capture/request.json",
        request_capture_sha256="d" * 64,
        request_digest="e" * 64,
        response_capture_ref="capture/response.json",
        response_capture_sha256="f" * 64,
        response_digest="1" * 64,
        partial_draft=draft,
        required_outputs=("accepted_agent_ids", "stop_conditions"),
        completed_required_outputs=("accepted_agent_ids",),
        partial_required_outputs=(),
        missing_required_outputs=("stop_conditions",),
        usage={"prompt_tokens": 100, "completion_tokens": 200},
        recorded_at="2026-08-20T12:00:00+00:00",
    )


def test_analysis_fragment_checkpoint_binds_content_and_remaining_scope() -> None:
    draft = "Preserved visible Lead draft with bounded facts."
    checkpoint = _analysis_checkpoint(draft=draft)
    trusted = validate_analysis_fragment_checkpoint(checkpoint)
    messages = compile_analysis_continuation_messages(
        checkpoint=trusted,
        partial_draft=draft,
        tool_name="submit_lead_plan",
    )
    prompt = json.dumps(messages, ensure_ascii=False)
    assert trusted["missing_required_outputs"] == ["stop_conditions"]
    assert draft in prompt
    assert "COMPLETED_OUTPUTS::stop_conditions" in prompt
    assert "OUTPUT::stop_conditions" in prompt

    drifted = dict(checkpoint)
    drifted["response_capture_sha256"] = "not-a-digest"
    drifted["checkpoint_digest"] = canonical_digest(
        {key: value for key, value in drifted.items() if key != "checkpoint_digest"}
    )
    with pytest.raises(MultiAgentPreviewError, match="checkpoint_binding_invalid"):
        validate_analysis_fragment_checkpoint(drifted)

    with pytest.raises(MultiAgentPreviewError, match="checkpoint_content_drift"):
        compile_analysis_continuation_messages(
            checkpoint=checkpoint,
            partial_draft=draft + " changed",
            tool_name="submit_lead_plan",
        )


def _opinion(agent_id: str, facet_id: str, *extra_facets: str) -> dict:
    return {
        "schema_version": SPECIALIST_PLAN_OPINION_SCHEMA_VERSION,
        "agent_id": agent_id,
        "mandate_interpretation": "只研究本角色拥有的命题，并把资料不足与工具失败严格区分开。",
        "hypotheses": [
            "当前官方披露可能支持一个有限但可复核的主判断。",
            "最强替代解释可能来自期间、关系方向或财务桥缺失。",
        ],
        "requested_atoms": [
            {
                "facet_id": value,
                "product_intents": ["查明当前命题的官方披露与最强反方"],
            }
            for value in (facet_id, *extra_facets)
        ],
        "dependencies": ["S1 reviewed Evidence", "case fact presence"],
        "failure_risks": ["把本单元未加载误写成全案不存在"],
        "stop_condition": "已有直接证据和最强反方，或形成可追溯的真实信息边界。",
    }


def _opinions() -> list[dict]:
    facets = {
        "AGENT::DEMAND_QUALITY": ("orders_and_backlog",),
        "AGENT::OPERATING_PERFORMANCE": ("reported_results",),
        "AGENT::VALUE_CAPTURE": ("margin_and_incremental_profit",),
        "AGENT::CASH_CONVERSION": ("cash_generation",),
        "AGENT::SUPPLY_RELATIONSHIP": (
            "upstream_capacity_context",
            "subject_relationship_disclosure",
        ),
        "AGENT::COUNTEREVIDENCE": ("issuer_counterevidence",),
    }
    topology = _topology()
    return [
        validate_specialist_plan_opinion(
            _opinion(agent_id, *facets[agent_id]),
            topology=topology,
            expected_agent_id=agent_id,
        )
        for agent_id in SPECIALIST_AGENT_IDS
    ]


def _lead(opinions: list[dict]) -> dict:
    payload = {
        "schema_version": "fin_ia_multi_agent_lead_plan_v1_0",
        "lead_agent_id": RESEARCH_LEAD_AGENT_ID,
        "accepted_agent_ids": list(SPECIALIST_AGENT_IDS),
        "ordered_agent_ids": list(SPECIALIST_AGENT_IDS),
        "accepted_facets": [
            atom["facet_id"]
            for row in opinions
            for atom in row["requested_atoms"]
        ],
        "coordination_questions": [
            "订单和收入事实是否在不同角色间保持同一存在性语义？",
            "产品到公司利润的因果桥是否被明确保留为缺口？",
        ],
        "expected_information_boundaries": [
            "免费公开资料可能不披露订单取消和 backlog 账龄。",
            "当前没有生产级 PIT 估值路线。",
        ],
        "stop_conditions": [
            "所有激活角色都形成可追溯工作底稿。",
            "所有 L1 冲突被修复或准确归属并阻断报告。",
        ],
    }
    return validate_lead_plan(
        payload, opinions=opinions, topology=_topology()
    )


def _context(agent_id: str) -> dict:
    return {
        "context_digest": "context-digest",
        "cell_analysis_view": {
            "cell": {
                "cell_evidence_views": [
                    {"evidence_ref": "EV::ONE"},
                    {"evidence_ref": "EV::TWO"},
                ],
                "allowed_numeric_refs": ["NUM::ONE"],
                "allowed_numeric_relation_refs": ["REL::ONE"],
                "residual_gap_cards": [{"gap_ref": "GAP::ONE"}],
            }
        },
        "agent": {"agent_id": agent_id},
    }


def _workpaper(agent_id: str) -> dict:
    payload = {
        "schema_version": SPECIALIST_WORKPAPER_SCHEMA_VERSION,
        "agent_id": agent_id,
        "thesis": "现有证据支持一个有限的公司层判断，但不支持未经桥接的产品因果归因。",
        "confidence": "medium",
        "sourced_claims": [
            {
                "claim": "官方披露直接支持当前公司层观察。",
                "authority": "sourced_fact",
                "evidence_refs": ["EV::ONE"],
                "numeric_refs": ["NUM::ONE"],
                "numeric_relation_refs": ["REL::ONE"],
            }
        ],
        "mechanism": "经营结果可能由规模、产品组合、成本和费用杠杆共同作用，当前证据不能把变化只分配给一个产品。",
        "alternative_explanations": ["其他业务组合和一次性项目也可能解释公司层变化。"],
        "strongest_counterarguments": ["产品到公司利润的直接财务桥仍然缺失。"],
        "remaining_gap_refs": ["GAP::ONE"],
        "what_would_change": ["后续官方披露提供同期间产品收入和利润桥时重新裁决。"],
        "cross_role_challenges": (
            [
                {
                    "target_agent_id": "AGENT::VALUE_CAPTURE",
                    "challenge": "当前利润判断是否把公司层变化过度归因于单一产品？",
                    "material_reason": "若缺少产品到公司利润桥，归因会直接改变结论强度。",
                    "requested_action": "recheck_judgment",
                }
            ]
            if agent_id == "AGENT::COUNTEREVIDENCE"
            else []
        ),
        "stop_reason": "当前证据足以形成有限判断，剩余问题已被保留为可追溯缺口。",
    }
    return validate_specialist_workpaper(
        payload,
        context=_context(agent_id),
        expected_agent_id=agent_id,
    )


def test_topology_distinguishes_agents_tools_evaluators_and_labels() -> None:
    topology = _topology()
    assert topology["current_runtime_finding"]["old_five_cell_is_true_multi_agent"] is False
    assert len(topology["preview_agents"]) == 8
    assert len(topology["tools"]) >= 6
    assert len(topology["evaluators"]) == 5
    assert {row["role_id"] for row in topology["label_only_roles"]} >= {
        "financial_specialist",
        "valuation_specialist",
    }
    assert specialist_plan_tool(topology, SPECIALIST_AGENT_IDS[0])["function"]["name"] == "submit_specialist_plan_opinion"
    lead_tool = lead_plan_tool(topology=topology)
    assert lead_tool["function"]["name"] == "submit_lead_plan"
    assert (
        lead_tool["function"]["parameters"]["properties"]
        ["accepted_facets"]["maxItems"]
        == len(topology["facet_catalog"])
    )
    assert evaluation_tool()["function"]["name"] == "submit_multi_agent_evaluation"


def test_role_opinions_compile_one_provider_neutral_planner_payload() -> None:
    opinions = _opinions()
    lead = _lead(opinions)
    result = compile_planner_payload_from_role_opinions(
        objective_id="ROC::TEST",
        opinions=opinions,
        lead_plan=lead,
        topology=_topology(),
    )
    assert result["planner_payload"]["objective_id"] == "ROC::TEST"
    assert len(result["planner_payload"]["atoms"]) == 7
    assert {
        row["facet_id"] for row in result["planner_payload"]["atoms"]
    } == set(lead["accepted_facets"])
    assert all(
        "proposing_agent_ids" in row for row in result["role_facet_bindings"]
    )


def test_specialist_cannot_request_another_roles_facet() -> None:
    payload = _opinion("AGENT::DEMAND_QUALITY", "reported_results")
    with pytest.raises(MultiAgentPreviewError) as exc:
        validate_specialist_plan_opinion(
            payload,
            topology=_topology(),
            expected_agent_id="AGENT::DEMAND_QUALITY",
        )
    assert exc.value.code == "multi_agent_specialist_facet_invalid"


def test_workpaper_and_evaluator_refs_fail_closed() -> None:
    workpaper = _workpaper("AGENT::DEMAND_QUALITY")
    tool = report_draft_tool(workpapers=[workpaper])
    assert tool["function"]["name"] == "submit_report_draft"
    evaluation = validate_evaluation(
        {
            "schema_version": MULTI_AGENT_EVALUATION_SCHEMA_VERSION,
            "findings": [
                {
                    "finding_code": "causal_bridge_missing",
                    "severity": "L2",
                    "target_agent_id": "AGENT::DEMAND_QUALITY",
                    "failure_owner": "model_judgment",
                    "explanation": "当前结论把公司层变化过度归因于单一产品。",
                    "evidence_refs": ["EV::ONE"],
                    "permitted_repair": "收窄为公司层观察并保留产品财务桥缺口。",
                    "blocks_report": False,
                }
            ],
            "cross_role_conflicts": [],
            "report_may_proceed": True,
        },
        workpapers=[workpaper],
    )
    assert evaluation["report_may_proceed"] is True
    bad = json.loads(json.dumps(workpaper))
    bad.pop("workpaper_digest")
    bad.pop("context_digest")
    bad["sourced_claims"][0]["evidence_refs"] = ["EV::UNKNOWN"]
    with pytest.raises(MultiAgentPreviewError) as exc:
        validate_specialist_workpaper(
            bad,
            context=_context("AGENT::DEMAND_QUALITY"),
            expected_agent_id="AGENT::DEMAND_QUALITY",
        )
    assert exc.value.code == "multi_agent_workpaper_ref_out_of_scope"


def test_report_can_only_use_validated_workpapers() -> None:
    workpaper = _workpaper("AGENT::DEMAND_QUALITY")
    report = validate_report_draft(
        {
            "schema_version": MULTI_AGENT_REPORT_DRAFT_SCHEMA_VERSION,
            "report_title": "Dell AI 基础设施研究 Preview",
            "executive_thesis": "当前资料能够支持一个有限且可复核的公司层判断，但产品到公司利润和现金的直接桥仍然缺失，报告因此保留明确边界。",
            "sections": [
                {
                    "heading": heading,
                    "body": "这一节只复用已经验证的工作底稿，区分官方事实、有限推断、替代解释和仍待补证的边界，不增加新的来源或因果关系。",
                    "source_workpaper_agent_ids": ["AGENT::DEMAND_QUALITY"],
                    "evidence_refs": ["EV::ONE"],
                    "numeric_refs": ["NUM::ONE"],
                }
                for heading in ("需求", "经营", "反方", "结论")
            ],
            "remaining_gaps": ["产品到公司利润的直接桥仍未由当前公开资料建立。"],
            "what_would_change": [
                "订单持续转化为收入且取消风险未上升时提高置信度。",
                "官方披露产品利润桥或出现相反供需信号时重新裁决。",
            ],
            "confidence_statement": "这是受当前信息边界约束的诊断性 Preview，不是产品验收或投资建议。",
        },
        workpapers=[workpaper],
    )
    assert len(report["workpaper_digests"]) == 1
    assert report["report_digest"]


def test_absence_language_is_routed_to_harness_reconciliation() -> None:
    workpaper = _workpaper("AGENT::DEMAND_QUALITY")
    workpaper["thesis"] = "当前单元没有披露相关事实，因此需要先检查全案存在目录再作判断。"
    findings = local_case_absence_findings(
        workpapers=[workpaper],
        case_truth_model_view={"presence_catalog": [{"truth_aliases": ["TRUTH::ONE"]}]},
    )
    assert findings[0]["failure_owner"] == "harness_control"
    assert findings[0]["blocks_report"] is True


def test_token_budget_basis_is_quality_driven() -> None:
    basis = compile_token_budget_basis(
        node_id="AGENT::DEMAND_QUALITY::WORKPAPER",
        purpose="形成需求真实性、转化和最强反方的完整工作底稿，并保留事实与信息边界。",
        input_characters=12000,
        input_reference_count=18,
        required_outputs=["thesis", "mechanism", "counterargument", "what_would_change"],
        schema_burden="one nested tool schema with source-bound reference enums",
        materiality_quality_risk="false absence or backlog-to-revenue overreach is L1/L2 material",
        comparable_run_evidence=["DELL dynamic five-cell R7 demand and operating cells"],
        reasoning_profile="deepseek-v4-pro thinking=max",
        output_token_ceiling=8000,
        stop_truncation_behavior="fail closed on truncation; preserve capture and do not promote partial output",
    )
    assert basis["cost_and_latency_are_secondary_constraints"] is True
    assert basis["output_token_ceiling"] == 8000


def test_model_message_compilers_keep_role_and_evaluator_boundaries() -> None:
    topology = _topology()
    objective = {
        "case_key": "DELL",
        "research_as_of": "2026-08-06",
        "raw_question": "判断 Dell AI 基础设施需求、利润、现金与供给关系。",
        "required_slot_ids": sorted(
            {row["slot_id"] for row in topology["facet_catalog"].values()}
        ),
    }
    opinions = _opinions()
    lead = _lead(opinions)
    plan_messages = compile_specialist_plan_messages(
        topology=topology,
        agent_id="AGENT::DEMAND_QUALITY",
        objective=objective,
    )
    assert len(plan_messages) == 2
    assert "DEMAND_QUALITY" in plan_messages[1]["content"]
    lead_messages = compile_lead_plan_messages(
        topology=topology,
        objective=objective,
        opinions=opinions,
    )
    assert len(lead_messages) == 2
    assert "specialist_opinions" in lead_messages[1]["content"]

    context = _context("AGENT::DEMAND_QUALITY")
    workpaper = _workpaper("AGENT::DEMAND_QUALITY")
    assert len(compile_specialist_workpaper_messages(context=context)) == 2
    assert len(
        compile_evaluation_messages(
            workpapers=[workpaper],
            case_truth_model_view={"presence_catalog": []},
        )
    ) == 2
    evaluation = validate_evaluation(
        {
            "schema_version": MULTI_AGENT_EVALUATION_SCHEMA_VERSION,
            "findings": [],
            "cross_role_conflicts": [],
            "report_may_proceed": True,
        },
        workpapers=[workpaper],
    )
    assert len(
        compile_report_messages(
            workpapers=[workpaper], evaluation=evaluation
        )
    ) == 2


def test_empty_reference_enums_remain_valid_but_unselectable() -> None:
    context = _context("AGENT::SUPPLY_RELATIONSHIP")
    context["cell_analysis_view"]["cell"]["allowed_numeric_refs"] = []
    context["cell_analysis_view"]["cell"]["allowed_numeric_relation_refs"] = []
    tool = specialist_workpaper_tool(
        agent_id="AGENT::SUPPLY_RELATIONSHIP", context=context
    )
    claim = tool["function"]["parameters"]["properties"]["sourced_claims"]["items"]
    numeric = claim["properties"]["numeric_refs"]
    assert numeric["maxItems"] == 0
    assert numeric["items"]["enum"] == ["__NO_VALID_REF__"]

    workpaper = _workpaper("AGENT::DEMAND_QUALITY")
    workpaper["sourced_claims"][0]["numeric_refs"] = []
    report_tool = report_draft_tool(workpapers=[workpaper])
    section = report_tool["function"]["parameters"]["properties"]["sections"]["items"]
    report_numeric = section["properties"]["numeric_refs"]
    assert report_numeric["maxItems"] == 0
    assert report_numeric["items"]["enum"] == ["__NO_VALID_REF__"]


def test_research_lead_selects_bounded_cross_role_repairs() -> None:
    workpapers = [
        _workpaper("AGENT::VALUE_CAPTURE"),
        _workpaper("AGENT::COUNTEREVIDENCE"),
    ]
    catalog = compile_challenge_catalog(workpapers=workpapers)
    assert len(catalog) == 1
    tool = lead_coordination_tool(challenge_catalog=catalog)
    assert tool["function"]["name"] == "submit_lead_coordination_decision"
    messages = compile_lead_coordination_messages(
        workpapers=workpapers, challenge_catalog=catalog
    )
    assert catalog[0]["challenge_id"] in messages[1]["content"]
    decision = validate_lead_coordination_decision(
        {
            "schema_version": "fin_ia_multi_agent_lead_coordination_decision_v1_0",
            "lead_agent_id": RESEARCH_LEAD_AGENT_ID,
            "accepted_challenge_ids": [catalog[0]["challenge_id"]],
            "deferred_challenge_ids": [],
            "coordination_rationale": "该挑战直接影响产品到公司利润的归因强度，且可由原角色在现有证据内局部复核。",
            "next_state": "continue_local_repairs",
        },
        challenge_catalog=catalog,
    )
    assert decision["accepted_challenge_ids"] == [catalog[0]["challenge_id"]]


def test_failed_preview_can_checkpoint_only_valid_specialist_plans() -> None:
    opinions = _opinions()
    nodes = []
    for index, (agent_id, opinion) in enumerate(
        zip(SPECIALIST_AGENT_IDS, opinions, strict=True), start=1
    ):
        attempts = [
            {
                "attempt_id": f"R3-{index:02d}",
                "status": "contract_valid",
                "request_digest": f"{index:x}" * 64,
                "response_digest": f"{index + 6:x}" * 64,
                "validated_payload_digest": canonical_digest(opinion),
            }
        ]
        nodes.append(
            {
                "node_id": f"{agent_id}::PLAN",
                "agent_id": agent_id,
                "validated_payload": opinion,
                "attempts": attempts,
            }
        )
    terminal_body = {
        "status": "multi_agent_preview_terminal_failure_preserved",
        "failure_code": "model_gateway_reasoning_budget_exhausted",
        "node_executions": nodes,
        "terminal_node_attempts": [
            {"failure_code": "model_gateway_reasoning_budget_exhausted"},
            {"failure_code": "model_gateway_reasoning_budget_exhausted"},
        ],
        "execution": {
            "model_nodes_started": 7,
            "provider_attempts_preserved": 11,
            "external_source_network_calls": 0,
            "candidate_promotions": 0,
        },
    }
    terminal = {
        **terminal_body,
        "full_result_digest": canonical_digest(terminal_body),
    }
    checkpoint = compile_specialist_plan_checkpoint(
        topology=_topology(),
        predecessor_authority_ref="configs/R3-authority.json",
        predecessor_authority_sha256="a" * 64,
        predecessor_result_ref="configs/R3-result.json",
        predecessor_result_sha256="b" * 64,
        predecessor_result_digest="c" * 64,
        terminal_failure=terminal,
    )
    validated = validate_specialist_plan_checkpoint(
        checkpoint, topology=_topology()
    )
    assert validated["reused_specialist_plan_count"] == 6
    assert [row["agent_id"] for row in validated["specialist_plans"]] == list(
        SPECIALIST_AGENT_IDS
    )
    assert validated["new_model_calls"] == 0

    bad = json.loads(json.dumps(checkpoint))
    bad["specialist_plans"][0]["requested_atoms"][0]["facet_id"] = (
        "reported_results"
    )
    with pytest.raises(MultiAgentPreviewError):
        validate_specialist_plan_checkpoint(bad, topology=_topology())
