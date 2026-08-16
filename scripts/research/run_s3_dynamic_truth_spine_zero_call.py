from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.research_evidence_pack_service import (
    ResearchEvidencePackPrincipal,
    ResearchEvidencePackService,
)
from apps.workbench.backend.application.research_retrieval_service import (
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from sec_agent.research.bounded_finance_loop import (
    BoundedFinanceLoopError,
    MICRO_JUDGMENT_TOOL_NAMES,
    SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL,
    SUBMIT_RESEARCH_MECHANISM_TOOL,
    SUBMIT_RESEARCH_THESIS_TOOL,
    compile_finance_micro_fragment_analysis_messages,
    compile_finance_micro_fragment_context,
    compile_finance_micro_fragment_submission_messages,
    compile_finance_micro_fragment_validation_repair_successor,
    compile_finance_micro_judgment_fragments,
    compile_finance_micro_judgment_tools,
    load_bounded_finance_loop_policy,
    load_dynamic_micro_judgment_policy,
    scope_bounded_finance_micro_judgment_policy,
    validate_finance_micro_judgment_fragment,
)
from sec_agent.research.current_consumer import compile_current_research_deliverable
from sec_agent.research.dynamic_research_runtime import (
    compile_dynamic_claim_surface_projection,
    compile_dynamic_research_input_projection,
)
from sec_agent.research.dynamic_truth_spine import (
    DynamicTruthSpineError,
    compile_dynamic_evidence_responses,
    compile_dynamic_reviewed_pack_view,
)
from sec_agent.research.planning import (
    compile_research_objective,
    load_research_planning_policy,
)
from sec_agent.research.reviewed_evidence_pack import canonical_digest
from retrieval.contracts import load_financial_research_kernel
from retrieval.route_compiler import load_query_object_fact_route_policy
from sec_agent.runtime_bridge.paths import resolve_runtime_paths
from sec_agent.runtime_resource_registry import read_registered_runtime_json


POLICY = ROOT / (
    "configs/research/fin_ia_0_1_3_s3_dynamic_truth_spine_policy_v1_0.json"
)
CONSUMER_POLICY = ROOT / (
    "configs/research/fin_ia_0_1_3_s3_current_research_consumer_policy_v1_2.json"
)
DELL_OBJECTIVE = ROOT / (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_minimal_planner_canary_objective_v1_0.json"
)
DELL_ATOMS = ROOT / (
    "tests/fixtures/research/"
    "fin_ia_0_1_3_s3_dell_planner_r1_atoms_v1_0.json"
)
DELL_CLAIM_TEMPLATE = ROOT / (
    "configs/research/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_claim_authority_v1_0.json"
)
DELL_CLAIM_SURFACE_TEMPLATE = ROOT / (
    "configs/research/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "claim_surface_authority_v1_2.json"
)
BOUNDED_LOOP_POLICY = ROOT / (
    "configs/research/"
    "fin_ia_0_1_3_s3_bounded_finance_agent_loop_policy_v1_1.json"
)
DYNAMIC_MICRO_POLICY = ROOT / (
    "configs/research/"
    "fin_ia_0_1_3_s3_dynamic_micro_judgment_policy_v1_0.json"
)


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_new(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _services() -> tuple[ResearchEvidencePackService, ResearchRetrievalService]:
    paths = resolve_runtime_paths(ROOT)
    return (
        ResearchEvidencePackService.from_runtime_paths(ROOT, paths),
        ResearchRetrievalService.from_runtime_paths(ROOT, paths),
    )


def _one_slot_inputs(case_key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    kernel = load_financial_research_kernel(
        read_registered_runtime_json(
            ROOT, "application.config.current_financial_research_kernel"
        )
    )
    route_policy = load_query_object_fact_route_policy(
        read_registered_runtime_json(
            ROOT, "application.config.current_query_object_fact_route_policy"
        ),
        kernel,
    )
    planning = load_research_planning_policy(
        read_registered_runtime_json(
            ROOT, "application.config.current_research_planning_policy"
        ),
        route_policy,
    )
    draft = {
        "schema_version": "fin_ia_research_objective_draft_v1_0",
        "raw_question": (
            f"{case_key} 的增长是否转化为可持续利润，当前证据还缺什么？"
        ),
        "task_type": "company_deep_dive",
        "case_key": case_key,
        "required_slot_ids": ["pricing_mix_value_capture"],
        "allowed_source_types": ["10-K", "10-Q", "8-K", "20-F", "6-K"],
        "forbidden_source_types": [],
        "output_format": "investment_research_memo",
        "gap_policy": "return_typed_gap",
        "reviewer_role": "qualified_financial_research_reviewer",
        "period": {"start_date": "2024-01-01", "fiscal_years": [2025, 2026, 2027]},
        "budget": {
            "max_evidence_requests": 1,
            "max_metric_intents_per_request": 4,
            "max_product_intents_per_request": 2,
            "max_model_calls": 1,
        },
        "pass_criteria": [
            "identity_and_as_of_bound",
            "required_dimensions_covered",
            "numeric_facts_source_bound",
            "candidate_not_evidence_boundary_preserved",
            "qualified_human_review_required",
        ],
    }
    objective = compile_research_objective(draft, kernel=kernel, policy=planning)
    atoms = {
        "schema_version": "fin_ia_research_planner_atoms_v1_0",
        "objective_id": objective.objective_id,
        "atoms": [
            {
                "facet_id": "margin_and_incremental_profit",
                "metric_ids": [
                    "gross_profit",
                    "operating_income",
                    "operating_margin",
                    "gross_margin",
                ],
                "product_intents": [
                    "product-to-company profit bridge",
                    "incremental profit durability",
                ],
                "target_entity": case_key,
            }
        ],
    }
    return draft, atoms


def _case_inputs(case_key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if case_key == "DELL":
        return _json(DELL_OBJECTIVE), _json(DELL_ATOMS)
    return _one_slot_inputs(case_key)


def _case_projection(
    case_key: str,
    *,
    evidence: ResearchEvidencePackService,
    retrieval: ResearchRetrievalService,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    permissions = frozenset({"current_product:read"})
    objective, atoms = _case_inputs(case_key)
    pack = evidence.get_case(
        case_key, ResearchEvidencePackPrincipal("current", permissions)
    )
    controlled = retrieval.execute_controlled_plan(
        case_key,
        objective,
        atoms,
        ResearchRetrievalPrincipal("current", permissions),
    )
    projection = compile_dynamic_research_input_projection(
        truth_spine_policy=_json(POLICY),
        consumer_policy=_json(CONSUMER_POLICY),
        controlled_plan=controlled,
        evidence_pack=pack,
    )
    return (
        pack,
        controlled,
        projection["evidence_responses"],
        projection["dynamic_research_input"] or None,
    )


def _mutations(
    *,
    pack: Mapping[str, Any],
    controlled: Mapping[str, Any],
    baseline: Mapping[str, Any],
) -> dict[str, bool]:
    policy = _json(POLICY)
    reordered = deepcopy(dict(controlled))
    for result in reordered["request_results"]:
        hybrid = result.get("hybrid_object_retrieval")
        if isinstance(hybrid, dict):
            hybrid["candidates"].reverse()
        else:
            for lane in result.get("lanes") or ():
                lane["candidates"].reverse()
    reorder_result = compile_dynamic_evidence_responses(
        policy=policy,
        controlled_plan=reordered,
        evidence_pack=pack,
    )

    text_mutated = deepcopy(dict(controlled))
    for result in text_mutated["request_results"]:
        hybrid = result.get("hybrid_object_retrieval")
        if isinstance(hybrid, dict) and hybrid.get("candidates"):
            hybrid["candidates"][0]["model_text"] = (
                "UNTRUSTED CANDIDATE TEXT MUST NOT GRANT AUTHORITY"
            )
            break
    text_result = compile_dynamic_evidence_responses(
        policy=policy,
        controlled_plan=text_mutated,
        evidence_pack=pack,
    )

    cross_case = deepcopy(dict(controlled))
    cross_case["objective"]["case_key"] = "MU"
    cross_case_failed = False
    try:
        compile_dynamic_evidence_responses(
            policy=policy,
            controlled_plan=cross_case,
            evidence_pack=pack,
        )
    except DynamicTruthSpineError as exc:
        cross_case_failed = str(exc) == "dynamic_truth_spine_case_binding_invalid"

    drift = deepcopy(dict(pack))
    drift["artifact_digest"] = "0" * 64
    pack_drift_failed = False
    try:
        compile_dynamic_reviewed_pack_view(
            evidence_pack=drift,
            evidence_responses=baseline,
        )
    except DynamicTruthSpineError as exc:
        pack_drift_failed = str(exc) == "dynamic_truth_spine_pack_binding_drift"

    return {
        "candidate_reordering_is_semantically_stable": (
            reorder_result["evidence_response_set_digest"]
            == baseline["evidence_response_set_digest"]
        ),
        "untrusted_candidate_text_has_no_authority_effect": (
            text_result["evidence_response_set_digest"]
            == baseline["evidence_response_set_digest"]
        ),
        "cross_case_mutation_failed_closed": cross_case_failed,
        "reviewed_pack_binding_drift_failed_closed": pack_drift_failed,
    }


def _relation_for_bridge(
    cell: Mapping[str, Any], bridge: str, atom_field: str
) -> Mapping[str, Any]:
    relation = next(
        (
            row
            for row in cell["claim_relation_card"]["allowed_combinations"]
            if row["causal_bridge_authority"] == bridge
            and atom_field in set(row["allowed_atom_fields"])
        ),
        None,
    )
    if relation is None:
        raise ValueError("dynamic_micro_required_relation_missing")
    return relation


def _common_fragment_fields(
    relation: Mapping[str, Any],
    *,
    cell_id: str,
    surface_input: Mapping[str, Any],
) -> dict[str, Any]:
    numeric_relation_by_ref = {
        str(row["numeric_relation_ref"]): row
        for row in surface_input["numeric_relation_cards"]
    }
    numeric_refs = sorted(
        {
            str(numeric_relation_by_ref[ref][field])
            for ref in relation["required_numeric_relation_refs"]
            for field in ("current_numeric_ref", "comparison_numeric_ref")
        }
    )
    return {
        "cell_id": cell_id,
        "claim_relation_ref": relation["claim_relation_ref"],
        "evidence_uses": [
            {"evidence_ref": ref, "use_role": "support"}
            for ref in relation["required_evidence_refs"]
        ],
        "numeric_refs": numeric_refs,
        "numeric_relation_refs": list(
            relation["required_numeric_relation_refs"]
        ),
        "qualitative_fact_refs": list(
            relation["required_qualitative_fact_refs"]
        ),
        "method_step_refs": [],
        "graph_edge_refs": [],
    }


def _controlled_dynamic_fragments(
    surface_input: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    cell_id = "CELL::value_capture"
    cell = next(
        row for row in surface_input["cells"] if row["cell_id"] == cell_id
    )
    thesis_relation = _relation_for_bridge(
        cell, "bridge_unavailable", "thesis_atom"
    )
    mechanism_relation = _relation_for_bridge(
        cell, "same_scope_observation_only", "mechanism_atom"
    )
    counter_relation = _relation_for_bridge(
        cell, "bridge_unavailable", "counterargument_atom"
    )
    method_step_refs = [
        row["method_step_ref"]
        for row in cell["role_method_pack"]["method_steps"]
    ]
    graph_edge_refs = [
        row["graph_edge_ref"] for row in cell["graph_context_pack"]["edges"]
    ]
    return {
        SUBMIT_RESEARCH_THESIS_TOOL: {
            **_common_fragment_fields(
                thesis_relation,
                cell_id=cell_id,
                surface_input=surface_input,
            ),
            "method_step_refs": method_step_refs,
            "graph_edge_refs": graph_edge_refs,
            "judgment_status": "insufficient_evidence",
            "confidence_basis": "gap_dominated",
            "inference_authority": "not_inferable",
            "claim_scope": thesis_relation["claim_scope"],
            "financial_scope": thesis_relation["financial_scope"],
            "causal_bridge_authority": thesis_relation[
                "causal_bridge_authority"
            ],
            "thesis_atom": (
                "当前资料不足以判断产品层表现是否已转化为公司利润改善。"
            ),
        },
        SUBMIT_RESEARCH_MECHANISM_TOOL: {
            **_common_fragment_fields(
                mechanism_relation,
                cell_id=cell_id,
                surface_input=surface_input,
            ),
            "inference_authority": "bounded_inference",
            "mechanism_atom": (
                "公司整体毛利率存在同口径变化，但该观察不构成产品到公司"
                "利润的归因桥。"
            ),
        },
        SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL: {
            **_common_fragment_fields(
                counter_relation,
                cell_id=cell_id,
                surface_input=surface_input,
            ),
            "inference_authority": "not_inferable",
            "counterargument_atom": (
                "产品到公司利润的可复算桥仍缺失，多因素共同作用仍是最强"
                "替代解释。"
            ),
            "what_would_change": {
                "observable": "可复算的产品收入、成本与公司利润桥",
                "direction": "resolve_gap",
                "time_horizon": "下一次正式财务披露",
                "evidence_route": "公司正式文件与权威数值事实",
                "threshold_numeric_ref": "",
            },
        },
    }


def _dynamic_micro_judgment_projection(
    *,
    surface_input: Mapping[str, Any],
    kernel,
    route_policy,
) -> tuple[dict[str, Any], dict[str, bool]]:
    cell_id = "CELL::value_capture"
    micro_policy = load_dynamic_micro_judgment_policy(
        _json(DYNAMIC_MICRO_POLICY)
    )
    scoped = scope_bounded_finance_micro_judgment_policy(
        load_bounded_finance_loop_policy(_json(BOUNDED_LOOP_POLICY)),
        micro_policy=micro_policy,
        cell_count=1,
        maximum_evidence_requests=0,
    )
    tools = compile_finance_micro_judgment_tools(
        research_input=surface_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route_policy,
        policy=scoped,
        strict=True,
    )
    controlled = _controlled_dynamic_fragments(surface_input)
    accepted: dict[str, dict[str, Any]] = {}
    context_digests: dict[str, str] = {}
    context_response_refs: dict[str, list[str]] = {}
    message_digests: dict[str, dict[str, str]] = {}
    for tool_name in MICRO_JUDGMENT_TOOL_NAMES:
        context = compile_finance_micro_fragment_context(
            research_input=surface_input,
            cell_id=cell_id,
            tool_name=tool_name,
            accepted_fragments=accepted,
        )
        analysis_messages = compile_finance_micro_fragment_analysis_messages(
            context
        )
        submission_messages = compile_finance_micro_fragment_submission_messages(
            fragment_context=context,
            analysis_draft=(
                "受控零调用草案仅用于证明动态上下文、严格提交与终端编译"
                "能够连接；不代表模型研究判断。"
            ),
        )
        context_digests[tool_name] = context["projection_digest"]
        context_response_refs[tool_name] = list(
            context["projection_manifest"]["evidence_response_refs"]
        )
        message_digests[tool_name] = {
            "analysis": canonical_digest(list(analysis_messages)),
            "submission": canonical_digest(list(submission_messages)),
        }
        accepted[tool_name] = validate_finance_micro_judgment_fragment(
            tool_name=tool_name,
            arguments=controlled[tool_name],
            research_input=surface_input,
            cell_id=cell_id,
            thesis_fragment=accepted.get(SUBMIT_RESEARCH_THESIS_TOOL),
        )
    cell = next(
        row for row in surface_input["cells"] if row["cell_id"] == cell_id
    )
    terminal = compile_finance_micro_judgment_fragments(accepted, cell=cell)
    deliverable = compile_current_research_deliverable(
        research_input=surface_input,
        judgment_output={"cells": [terminal]},
        required_cell_ids=[cell_id],
    )

    promotion = deepcopy(dict(surface_input))
    promotion["dynamic_truth_spine_contract"]["candidate_promotions"] = 1
    promotion_failed = False
    try:
        compile_finance_micro_fragment_context(
            research_input=promotion,
            cell_id=cell_id,
            tool_name=SUBMIT_RESEARCH_THESIS_TOOL,
        )
    except BoundedFinanceLoopError as exc:
        promotion_failed = str(exc) == (
            "finance_loop_dynamic_evidence_response_binding_invalid"
        )

    inconsistent = deepcopy(accepted)
    inconsistent[SUBMIT_RESEARCH_THESIS_TOOL]["judgment_status"] = (
        "bounded_support"
    )
    thesis_escalation_failed = False
    try:
        compile_finance_micro_judgment_fragments(inconsistent, cell=cell)
    except BoundedFinanceLoopError as exc:
        thesis_escalation_failed = str(exc) == (
            "finance_loop_micro_thesis_disposition_invalid"
        )

    temporal_overreach = deepcopy(
        accepted[SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL]
    )
    temporal_overreach["counterargument_atom"] = (
        "公司毛利率同财季同比下降，同期优化服务器组合上升并压低毛利率；"
        "现有材料仍不能建立产品到公司利润的可复算桥。"
    )
    temporal_overreach_failed = False
    temporal_repair = None
    try:
        validate_finance_micro_judgment_fragment(
            tool_name=SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL,
            arguments=temporal_overreach,
            research_input=surface_input,
            cell_id=cell_id,
            thesis_fragment=accepted[SUBMIT_RESEARCH_THESIS_TOOL],
        )
    except BoundedFinanceLoopError as exc:
        temporal_overreach_failed = str(exc) == (
            "finance_loop_micro_temporal_relation_unbound"
        )
        if temporal_overreach_failed:
            temporal_repair = (
                compile_finance_micro_fragment_validation_repair_successor(
                    research_input=surface_input,
                    cell_id=cell_id,
                    rejected_tool_name=(
                        SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL
                    ),
                    accepted_prefix_fragments={
                        key: accepted[key]
                        for key in (
                            SUBMIT_RESEARCH_THESIS_TOOL,
                            SUBMIT_RESEARCH_MECHANISM_TOOL,
                        )
                    },
                    rejected_fragment=temporal_overreach,
                    terminal_failure_code=(
                        "finance_loop_micro_temporal_relation_unbound"
                    ),
                )
            )

    summary = {
        "policy_ref": str(DYNAMIC_MICRO_POLICY.relative_to(ROOT)).replace(
            "\\", "/"
        ),
        "policy_digest": canonical_digest(_json(DYNAMIC_MICRO_POLICY)),
        "tool_names": [row["function"]["name"] for row in tools],
        "tool_contract_digest": canonical_digest(list(tools)),
        "fragment_context_schema_version": (
            "fin_ia_micro_fragment_context_projection_v1_4"
        ),
        "fragment_context_digests": context_digests,
        "fragment_evidence_response_refs": context_response_refs,
        "fragment_message_digests": message_digests,
        "controlled_fragment_digests": {
            name: canonical_digest(value) for name, value in accepted.items()
        },
        "terminal_judgment_digest": canonical_digest(terminal),
        "deliverable_digest": deliverable["deliverable_digest"],
        "terminal_disposition": {
            "judgment_status": terminal["judgment_status"],
            "inference_authority": terminal["inference_authority"],
            "causal_bridge_authority": terminal["causal_bridge_authority"],
        },
        "candidate_promotions": 0,
        "temporal_relation_boundary": {
            "unbound_contemporaneity_rejected": temporal_overreach_failed,
            "repair_compiled": temporal_repair is not None,
            "repair_rejected_at": (
                temporal_repair["repair_feedback"]["rejected_at"]
                if temporal_repair
                else ""
            ),
            "repair_messages_digest": (
                temporal_repair["repair_messages_digest"]
                if temporal_repair
                else ""
            ),
            "maximum_repair_turns": (
                temporal_repair["maximum_repair_turns"]
                if temporal_repair
                else 0
            ),
        },
        "model_calls": 0,
        "controlled_fragments_are_product_judgment": False,
    }
    return summary, {
        "dynamic_candidate_promotion_failed_closed": promotion_failed,
        "abstaining_thesis_cannot_be_escalated_by_later_fragments": (
            thesis_escalation_failed
        ),
        "unbound_cross_item_temporal_relation_failed_closed": (
            temporal_overreach_failed and temporal_repair is not None
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--implementation-commit", required=True)
    args = parser.parse_args()
    if re.fullmatch(r"[0-9a-f]{40}", args.implementation_commit) is None:
        raise ValueError("dynamic_truth_spine_implementation_commit_invalid")
    output = args.output.resolve()
    evidence, retrieval = _services()
    kernel_payload = read_registered_runtime_json(
        ROOT, "application.config.current_financial_research_kernel"
    )
    kernel = load_financial_research_kernel(kernel_payload)
    route_policy = load_query_object_fact_route_policy(
        read_registered_runtime_json(
            ROOT, "application.config.current_query_object_fact_route_policy"
        ),
        kernel,
    )
    cases = []
    dell_private: tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None = None
    dynamic_micro_mutations: dict[str, bool] = {}
    for case_key in ("DELL", "MU", "NVDA"):
        pack, controlled, responses, dynamic_input = _case_projection(
            case_key,
            evidence=evidence,
            retrieval=retrieval,
        )
        response_rows = [
            {
                "request_id": row["request_id"],
                "request_bindings": row["request_bindings"],
                "candidate_route": row["candidate_route"],
                "candidate_count": row["candidate_count"],
                "accepted_reviewed_evidence_count": len(row["accepted"]),
                "accepted_source_record_ids": [
                    decision["source_record_id"] for decision in row["accepted"]
                ],
                "rejected_reviewed_binding_reasons": sorted(
                    {decision["reason"] for decision in row["rejected"]}
                ),
                "unreviewed_candidate_count": len(row["needs_human_review"]),
                "typed_gap_codes": sorted(
                    {
                        str(typed["gap"].get("gap_code") or "")
                        for typed in row["typed_gaps"]
                    }
                ),
            }
            for row in responses["responses"]
        ]
        cases.append(
            {
                "case_key": case_key,
                "controlled_plan_digest": controlled["projection_digest"],
                "reviewed_pack_artifact_digest": pack["artifact_digest"],
                "evidence_response_set_digest": responses[
                    "evidence_response_set_digest"
                ],
                "summary": responses["summary"],
                "dynamic_research_input_compiled": dynamic_input is not None,
                "dynamic_research_input_digest": (
                    dynamic_input["research_input_digest"]
                    if dynamic_input is not None
                    else ""
                ),
                "requests": response_rows,
            }
        )
        if case_key == "DELL":
            dell_private = (pack, controlled, responses)
            if dynamic_input is not None:
                surface_projection = compile_dynamic_claim_surface_projection(
                    dynamic_research_input=dynamic_input,
                    claim_authority_template=_json(DELL_CLAIM_TEMPLATE),
                    claim_surface_template=_json(
                        DELL_CLAIM_SURFACE_TEMPLATE
                    ),
                )
                dynamic_claim_policy = surface_projection[
                    "dynamic_claim_authority_policy"
                ]
                claim_input = surface_projection[
                    "claim_authority_research_input"
                ]
                dynamic_surface_policy = surface_projection[
                    "dynamic_claim_surface_policy"
                ]
                surface_input = surface_projection[
                    "claim_surface_research_input"
                ]
                surface_relations = dynamic_surface_policy[
                    "allowed_structured_claim_combinations"
                ]
                cases[-1]["dynamic_claim_authority"] = {
                    "policy_digest": canonical_digest(dynamic_claim_policy),
                    "compiled_input_digest": claim_input["research_input_digest"],
                    "allowed_causal_bridge_authorities": dynamic_claim_policy[
                        "allowed_causal_bridge_authorities"
                    ],
                    "candidate_promotions": claim_input[
                        "claim_authority_contract"
                    ]["candidate_promotions"],
                }
                cases[-1]["dynamic_claim_surface"] = {
                    "policy_digest": canonical_digest(dynamic_surface_policy),
                    "compiled_input_digest": surface_input[
                        "research_input_digest"
                    ],
                    "allowed_claim_relation_refs": [
                        row["claim_relation_ref"] for row in surface_relations
                    ],
                    "fragment_coverage": {
                        field: any(
                            field in set(row["allowed_atom_fields"])
                            for row in surface_relations
                        )
                        for field in (
                            "thesis_atom",
                            "mechanism_atom",
                            "counterargument_atom",
                        )
                    },
                    "gap_only_thesis_abstention_available": any(
                        row["causal_bridge_authority"] == "bridge_unavailable"
                        and "thesis_atom" in set(row["allowed_atom_fields"])
                        for row in surface_relations
                    ),
                    "candidate_promotions": surface_input[
                        "claim_surface_authority_contract"
                    ]["candidate_promotions"],
                }
                (
                    cases[-1]["dynamic_micro_judgment"],
                    dynamic_micro_mutations,
                ) = _dynamic_micro_judgment_projection(
                    surface_input=surface_input,
                    kernel=kernel,
                    route_policy=route_policy,
                )
    assert dell_private is not None
    mutations = _mutations(
        pack=dell_private[0],
        controlled=dell_private[1],
        baseline=dell_private[2],
    )
    mutations.update(dynamic_micro_mutations)
    total_promotions = sum(
        int(row["summary"]["new_evidence_promotions"]) for row in cases
    )
    case_keys = [row["case_key"] for row in cases]
    passed = (
        case_keys == ["DELL", "MU", "NVDA"]
        and len(set(case_keys)) == 3
        and total_promotions == 0
        and all(mutations.values())
        and cases[0]["summary"]["accepted_reviewed_evidence_count"] > 0
        and cases[0]["dynamic_research_input_compiled"] is True
        and cases[0]["dynamic_claim_authority"]["candidate_promotions"] == 0
        and cases[0]["dynamic_claim_surface"]["candidate_promotions"] == 0
        and all(
            cases[0]["dynamic_claim_surface"]["fragment_coverage"].values()
        )
        and cases[0]["dynamic_micro_judgment"]["candidate_promotions"] == 0
        and cases[0]["dynamic_micro_judgment"]["terminal_disposition"]
        == {
            "judgment_status": "insufficient_evidence",
            "inference_authority": "not_inferable",
            "causal_bridge_authority": "bridge_unavailable",
        }
    )
    body = {
        "schema_version": "fin_ia_s3_dynamic_truth_spine_zero_call_result_v1_3",
        "status": (
            "zero_call_dynamic_truth_spine_engineering_pass"
            if passed
            else "zero_call_dynamic_truth_spine_engineering_failed"
        ),
        "recorded_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "implementation_commit": args.implementation_commit,
        "scope": (
            "S1_EvidenceRequest_to_S2_NumericFact_to_S3_EvidenceResponse_"
            "dynamic_micro_Judgment_and_terminal_deliverable"
        ),
        "cases": cases,
        "mutations": mutations,
        "observed_counts": {
            "case_count": len(cases),
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "new_evidence_promotions": total_promotions,
        },
        "stage_acceptance": {
            "real_current_s1_requests_executed": True,
            "real_current_s2_typed_fact_requests_executed": True,
            "typed_evidence_responses_compiled": True,
            "already_reviewed_evidence_only": True,
            "unreviewed_candidate_text_excluded": True,
            "three_case_identity_isolation": True,
            "dynamic_dell_claim_authority_narrowed": passed,
            "dynamic_dell_claim_relation_surface_compiled": passed,
            "gap_only_thesis_can_only_abstain": passed,
            "dynamic_dell_micro_fragment_contexts_compiled": passed,
            "dynamic_dell_terminal_deliverable_compiled": passed,
            "dynamic_candidate_promotion_and_thesis_escalation_fail_closed": (
                passed
            ),
            "unbound_cross_item_temporal_relation_fails_closed": passed,
            "natural_model_planner_executed": False,
            "natural_model_judgment_executed": False,
            "dynamic_agentic_research_claimed": False,
            "s3_product_acceptance_claimed": False,
        },
        "known_boundary": (
            "This proof runs the current local S1 candidate and S2 NumericFact "
            "services, then compiles request-scoped EvidenceResponses. Planner "
            "atoms and Judgment fragments remain controlled fixtures, so this is "
            "an engineering proof, not natural Agentic Research. The current S1 "
            "object route does not "
            "yet discover reviewed earnings-call transcripts; those remain an "
            "explicit source-route gap rather than being silently prefed."
        ),
    }
    result = {**body, "result_digest": canonical_digest(body)}
    _write_new(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
