from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
for candidate in (ROOT, ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sec_agent.research.multi_agent_preview import (  # noqa: E402
    LEAD_PLAN_SCHEMA_VERSION,
    RESEARCH_LEAD_AGENT_ID,
    SPECIALIST_AGENT_IDS,
    SPECIALIST_PLAN_OPINION_SCHEMA_VERSION,
    load_multi_agent_role_topology,
    validate_lead_plan,
    validate_specialist_plan_opinion,
)
from sec_agent.research.multi_agent_preview_runtime import (  # noqa: E402
    compile_multi_agent_preview_materialization,
)
from sec_agent.research.reviewed_evidence_pack import canonical_digest  # noqa: E402


RESULT = (
    ROOT
    / "configs/research/evals/"
    "fin_ia_0_1_3_s3_multi_agent_preview_zero_call_result_v1_2.json"
)
PREDECESSOR_RESULT = (
    ROOT
    / "configs/research/evals/"
    "fin_ia_0_1_3_s3_multi_agent_preview_zero_call_result_v1_1.json"
)
TOPOLOGY = ROOT / "configs/research/fin_ia_0_1_3_multi_agent_role_topology_v1_0.json"
OBJECTIVE = (
    ROOT
    / "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_multi_agent_preview_objective_v1_0.json"
)


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _fixture_opinions(topology: Mapping[str, Any]) -> list[dict[str, Any]]:
    facets = {
        "AGENT::DEMAND_QUALITY": ["orders_and_backlog", "conversion_and_durability"],
        "AGENT::OPERATING_PERFORMANCE": ["reported_results", "guidance_and_outlook"],
        "AGENT::VALUE_CAPTURE": ["margin_and_incremental_profit", "pricing_and_mix"],
        "AGENT::CASH_CONVERSION": ["cash_generation", "working_capital_risk"],
        "AGENT::SUPPLY_RELATIONSHIP": [
            "upstream_capacity_context",
            "counterparty_direct_mention",
            "subject_relationship_disclosure",
        ],
        "AGENT::COUNTEREVIDENCE": ["issuer_counterevidence"],
    }
    opinions = []
    for agent_id in SPECIALIST_AGENT_IDS:
        payload = {
            "schema_version": SPECIALIST_PLAN_OPINION_SCHEMA_VERSION,
            "agent_id": agent_id,
            "mandate_interpretation": "本角色只研究自己拥有的金融命题，并严格区分资料、工具、编排和判断失败。",
            "hypotheses": [
                "现有官方资料可能支持一个有限但可复核的本角色判断。",
                "最强替代解释可能来自期间、关系方向或产品财务桥缺失。",
            ],
            "requested_atoms": [
                {
                    "facet_id": facet_id,
                    "product_intents": ["查明本命题的官方披露和最强反方证据"],
                }
                for facet_id in facets[agent_id]
            ],
            "dependencies": ["S1 reviewed Evidence", "case fact presence"],
            "failure_risks": ["把本角色未加载的事实误写成全案不存在"],
            "stop_condition": "已有直接证据和最强反方，或形成可追溯的真实信息边界。",
        }
        opinions.append(
            validate_specialist_plan_opinion(
                payload,
                topology=topology,
                expected_agent_id=agent_id,
            )
        )
    return opinions


def _lead_plan(
    opinions: list[dict[str, Any]], topology: Mapping[str, Any]
) -> dict[str, Any]:
    facets = [
        atom["facet_id"]
        for opinion in opinions
        for atom in opinion["requested_atoms"]
    ]
    return validate_lead_plan(
        {
            "schema_version": LEAD_PLAN_SCHEMA_VERSION,
            "lead_agent_id": RESEARCH_LEAD_AGENT_ID,
            "accepted_agent_ids": list(SPECIALIST_AGENT_IDS),
            "ordered_agent_ids": list(SPECIALIST_AGENT_IDS),
            "accepted_facets": facets,
            "coordination_questions": [
                "不同角色是否对订单、收入、利润和现金保持一致的存在性语义？",
                "上游扩产和公司利润变化是否被错误升级为 Dell AI 的直接因果事实？",
            ],
            "expected_information_boundaries": [
                "免费公开资料可能不披露订单取消、积压账龄和 Dell 特定供给分配。",
                "当前没有生产级时点估值和商业渠道库存路线。",
            ],
            "stop_conditions": [
                "所有激活角色都形成可追溯工作底稿。",
                "所有 L1 冲突被修复或准确归属并阻断报告。",
            ],
        },
        opinions=opinions,
        topology=topology,
    )


def _request_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    request = result["request"]
    hybrid = result.get("hybrid_object_retrieval") or {}
    summary = result["summary"]
    return {
        "request_id": request["request_id"],
        "facet_ids": list(request["requested_facet_ids"]),
        "requester_role": request["requester_role"],
        "target_entities": list(request["target_entities"]),
        "narrative_candidate_count": summary["unique_candidates"],
        "typed_fact_resolved_count": summary["typed_fact_resolved_count"],
        "typed_fact_gap_count": summary["typed_fact_gap_count"],
        "hybrid_selected_count": int((hybrid.get("summary") or {}).get("selected_count") or 0),
        "source_route_state": str(
            (result.get("source_route_execution_truth") or {}).get("route_state")
            or (result.get("source_route_execution_truth") or {}).get("status")
            or ""
        ),
        "failure_owner_if_empty": (
            "S1_local_object_query_retrieval_or_ranking"
            if summary["unique_candidates"] == 0
            else "none"
        ),
    }


def run() -> dict[str, Any]:
    topology = load_multi_agent_role_topology(_json(TOPOLOGY))
    objective_payload = _json(OBJECTIVE)
    opinions = _fixture_opinions(topology)
    lead = _lead_plan(opinions, topology)
    materialization = compile_multi_agent_preview_materialization(
        repo_root=ROOT,
        topology=topology,
        objective_payload=objective_payload,
        opinions=opinions,
        lead_plan=lead,
    )
    plan = materialization.plan
    controlled = materialization.controlled_plan
    responses = materialization.evidence_responses
    reviewed_view = materialization.reviewed_pack_view
    dynamic_input = materialization.dynamic_research_input
    projection = {
        "evidence_responses": responses,
        "reviewed_pack_view": reviewed_view,
        "dynamic_research_input": dynamic_input,
        "candidate_promotions": 0,
    }
    research_input = materialization.research_input
    truth = materialization.case_truth_packet
    contexts = list(materialization.specialist_contexts)
    role_readiness = [
        {
            "agent_id": context["agent"]["agent_id"],
            "role_slot_ids": context["cell_analysis_view"]["projection_receipt"]["role_slot_ids"],
            "reviewed_evidence_visible": len(
                context["cell_analysis_view"]["cell"]["cell_evidence_views"]
            ),
            "numeric_facts_visible": len(
                context["cell_analysis_view"]["cell"]["allowed_numeric_refs"]
            ),
            "numeric_relations_visible": len(
                context["cell_analysis_view"]["cell"]["allowed_numeric_relation_refs"]
            ),
            "typed_gaps_visible": len(
                context["cell_analysis_view"]["cell"]["residual_gap_cards"]
            ),
            "context_digest": context["context_digest"],
        }
        for context in contexts
    ]
    empty_roles = [
        row["agent_id"]
        for row in role_readiness
        if row["reviewed_evidence_visible"] == 0
        and row["numeric_facts_visible"] == 0
    ]
    predecessor = _json(PREDECESSOR_RESULT)
    response_business_results = [
        {
            "request_id": row["request_id"],
            "candidate_route": row["candidate_route"],
            "candidate_count": row["candidate_count"],
            "accepted_reviewed_evidence_count": len(row["accepted"]),
            "rejected_reviewed_binding_count": len(row["rejected"]),
            "unreviewed_candidate_count": len(row["needs_human_review"]),
            "typed_gap_count": len(row["typed_gaps"]),
        }
        for row in projection["evidence_responses"]["responses"]
    ]
    result_body = {
        "schema_version": "fin_ia_s3_multi_agent_preview_zero_call_result_v1_2",
        "status": (
            "zero_call_topology_and_current_tool_spine_pass"
            if not empty_roles
            else "zero_call_data_or_projection_blocker_present"
        ),
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "case_key": "DELL",
        "research_as_of": "2026-08-06",
        "predecessor_result": {
            "path": str(PREDECESSOR_RESULT.relative_to(ROOT)).replace("\\", "/"),
            "result_digest": predecessor["result_digest"],
            "status": predecessor["status"],
        },
        "successor_change": {
            "root_cause": "dynamic_candidate_reselection_was_incorrectly_used_as_the_only_reader_for_already_reviewed_evidence",
            "owning_layer": "harness_control",
            "disposition": "separate_exact_reviewed_evidence_reader_from_dynamic_candidate_retrieval_and_attach_both_receipts",
        },
        "activated_true_agent_ids": [
            RESEARCH_LEAD_AGENT_ID, *SPECIALIST_AGENT_IDS, "AGENT::WRITER"
        ],
        "independent_specialist_opinion_count": len(opinions),
        "accepted_facet_count": len(lead["accepted_facets"]),
        "compiled_evidence_request_count": len(plan.evidence_requests),
        "controlled_plan_summary": deepcopy(controlled["summary"]),
        "request_business_results": [
            _request_summary(row) for row in controlled["request_results"]
        ],
        "request_evidence_response_results": response_business_results,
        "dynamic_evidence_response_summary": {
            "accepted_evidence_count": len(
                projection["evidence_responses"]["accepted_evidence_item_digests"]
            ),
            "candidate_promotions": projection["candidate_promotions"],
            "research_input_digest": research_input["research_input_digest"],
            "case_truth_packet_digest": truth["case_truth_packet_digest"],
        },
        "role_readiness": role_readiness,
        "blocking_empty_role_ids": empty_roles,
        "failure_owner_contract": {
            "empty_local_candidate_pool": "data_infrastructure_or_tool",
            "reviewed_evidence_exists_but_role_projection_empty": "harness_control",
            "tool_not_executed_or_feedback_not_routed": "agent_orchestration_and_role_design",
            "evidence_visible_but_judgment_wrong": "model_judgment",
            "scoring_or_false_positive": "evaluator",
        },
        "claims": {
            "model_calls": 0,
            "network_calls": 0,
            "paid_tool_calls": 0,
            "current_product_pointer_mutations": 0,
            "true_multi_agent_live_proven": False,
            "S1_pass": False,
            "S3_pass": False,
            "release_ready": False,
        },
    }
    result = {**result_body, "result_digest": canonical_digest(result_body)}
    if RESULT.exists():
        raise RuntimeError("multi_agent_preview_zero_call_result_exists")
    RESULT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2, sort_keys=True))
