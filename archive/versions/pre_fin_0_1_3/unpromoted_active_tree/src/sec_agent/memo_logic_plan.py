from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping


MEMO_LOGIC_PLAN_SCHEMA_VERSION = "finsight_memo_logic_plan_v0_1"


def build_memo_logic_plan(
    *,
    judgment_state: Mapping[str, Any],
    lead_review_checkpoint: Mapping[str, Any] | None = None,
    memo_intent: str = "investment_research_memo",
    product_reasoning_frame: Mapping[str, Any] | None = None,
    required_question_items: list[Mapping[str, Any]] | None = None,
    focus_ticker_coverage_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    dimension_judgments = [dict(item) for item in judgment_state.get("dimension_judgments") or [] if isinstance(item, Mapping)]
    lead_reviews = {
        str(item.get("dimension")): dict(item)
        for item in (lead_review_checkpoint or {}).get("dimension_reviews") or []
        if isinstance(item, Mapping)
    }
    dimension_portfolio_ref = (
        dict((lead_review_checkpoint or {}).get("dimension_evidence_portfolio_ref") or {})
        if isinstance((lead_review_checkpoint or {}).get("dimension_evidence_portfolio_ref"), Mapping)
        else {}
    )
    lead_directive = (
        dict((lead_review_checkpoint or {}).get("memo_directive") or {})
        if isinstance((lead_review_checkpoint or {}).get("memo_directive"), Mapping)
        else {}
    )
    repair_execution = (
        dict((lead_review_checkpoint or {}).get("lead_targeted_repair_execution") or {})
        if isinstance((lead_review_checkpoint or {}).get("lead_targeted_repair_execution"), Mapping)
        else {}
    )
    compact_required_items = _compact_required_question_items(required_question_items or [])
    sections = []
    for index, dimension in enumerate(dimension_judgments, start=1):
        dimension_id = str(dimension.get("dimension_id") or dimension.get("dimension") or f"dimension_{index}")
        lead_status = (lead_reviews.get(dimension_id) or {}).get("status") or ""
        required_claim_ids = _list(dimension.get("claim_ids") or dimension.get("primary_claim_ids"))
        required_gap_refs = _list(
            (lead_reviews.get(dimension_id) or {}).get("gap_ids")
            or dimension.get("gap_ids")
            or dimension.get("gap_refs")
        )
        product_instruction = ""
        if dimension_id.startswith("product"):
            product_instruction = (
                " Product sections must name the product/platform/taxonomy, disclose available KPI/spec/parameter/backlog/order context, "
                "and keep commercial tracker gaps short after public/official sources are exhausted."
            )
        section_required_items = [
            str(item.get("question_item_id") or "")
            for item in compact_required_items
            if str(item.get("dimension") or "") == dimension_id and str(item.get("question_item_id") or "")
        ]
        sections.append(
            {
                "section_id": dimension_id,
                "title": str(dimension.get("title") or _title(dimension_id)),
                "order": index,
                "logic_role": "core_analysis" if lead_status != "bounded_gap" else "boundary_and_gap",
                "required_claim_ids": required_claim_ids,
                "required_evidence_refs": _list(dimension.get("evidence_refs")),
                "required_gap_refs": required_gap_refs,
                "thesis_direction": _section_thesis_direction(dimension, lead_reviews.get(dimension_id) or {}),
                "decision_changing_evidence_refs": _decision_changing_refs(dimension, lead_reviews.get(dimension_id) or {}),
                "counter_thesis_refs": _counter_thesis_refs(dimension, lead_reviews.get(dimension_id) or {}),
                "dimension_pack_refs": _list((lead_reviews.get(dimension_id) or {}).get("dimension_portfolio_available_pack_refs")),
                "dimension_lead_questions": _list((lead_reviews.get(dimension_id) or {}).get("dimension_portfolio_lead_questions")),
                "required_item_ids": section_required_items[:8],
                "writing_instruction": (
                    "explain_business_mechanism_financial_bridge_and_counter_read_with_citations;"
                    " write as analyst judgment, not ClaimCard or driver list."
                    f"{product_instruction}"
                ),
            }
        )
    product_frame = _compact_product_reasoning_frame(product_reasoning_frame or {})
    judgment_cards = _compact_judgment_cards(judgment_state.get("judgment_cards"))
    thesis_path = _compact_thesis_path(judgment_state.get("thesis_path"))
    answer_outline = _answer_first_outline(sections=sections, lead_directive=lead_directive)
    thesis_bridge = _evidence_to_thesis_bridge(sections)
    required_item_answer_plan = _required_item_answer_plan(compact_required_items, sections=sections, product_frame=product_frame)
    economic_role_summary = _economic_role_summary(judgment_state)
    plan = {
        "schema_version": MEMO_LOGIC_PLAN_SCHEMA_VERSION,
        "plan_id": f"memo_logic:{_digest({'judgment': judgment_state, 'lead': lead_review_checkpoint or {}})[:20]}",
        "memo_intent": memo_intent,
        "opening_answer_policy": "answer_first_high_information_density_no_driver_list_dump",
        "lead_memo_directive": _compact_lead_directive(lead_directive),
        "lead_targeted_repair_execution": _compact_repair_execution(repair_execution),
        "dimension_evidence_portfolio_ref": _compact_dimension_portfolio_ref(dimension_portfolio_ref),
        "memo_style_contract": {
            "primary_surface": "natural_language_analyst_memo",
            "forbidden_surface": [
                "internal_gate_language",
                "claimcard_dump",
                "driver_by_driver_list",
                "gap_ledger_as_main_answer",
                "repeated_current_data_insufficient_caveats",
            ],
            "gap_budget_policy": (lead_directive.get("gap_budget_policy") or {})
            if isinstance(lead_directive.get("gap_budget_policy"), Mapping)
            else {},
            "product_output_contract": (lead_directive.get("product_output_contract") or {})
            if isinstance(lead_directive.get("product_output_contract"), Mapping)
            else {},
        },
        "product_reasoning_frame": product_frame,
        "judgment_cards": judgment_cards,
        "thesis_path": thesis_path,
        "economic_role_summary": economic_role_summary,
        "required_question_items": compact_required_items,
        "required_item_answer_plan": required_item_answer_plan,
        "focus_ticker_coverage_policy": _compact_focus_ticker_policy(focus_ticker_coverage_policy or {}),
        "section_order": [section["section_id"] for section in sections],
        "sections": sections,
        "answer_first_outline": answer_outline,
        "evidence_to_thesis_bridge": thesis_bridge,
        "thesis_density_contract": _thesis_density_contract(sections=sections, product_frame=product_frame),
        "writer_thesis_skeleton": _writer_thesis_skeleton(
            outline=answer_outline,
            bridge=thesis_bridge,
            product_frame=product_frame,
            lead_directive=lead_directive,
            required_item_answer_plan=required_item_answer_plan,
            economic_role_summary=economic_role_summary,
            judgment_cards=judgment_cards,
            thesis_path=thesis_path,
        ),
        "writer_allowed_inputs": ["judgment_state", "memo_logic_plan", "verified_claim_cards", "bounded_gaps", "report_style_config"],
        "writer_forbidden_tools": ["database_query", "live_web_snapshot", "retrieval", "new_fact_generation"],
        "citation_policy": "copy_claim_and_evidence_refs_exactly_no_new_refs",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    plan["validation"] = validate_memo_logic_plan(plan, judgment_state=judgment_state)
    return plan


def validate_memo_logic_plan(plan: Mapping[str, Any], *, judgment_state: Mapping[str, Any] | None = None) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    if str(plan.get("schema_version") or "") != MEMO_LOGIC_PLAN_SCHEMA_VERSION:
        errors.append({"type": "schema_version_mismatch"})
    if "database_query" not in set(plan.get("writer_forbidden_tools") or []):
        errors.append({"type": "writer_db_tool_must_be_forbidden"})
    if "live_web_snapshot" not in set(plan.get("writer_forbidden_tools") or []):
        errors.append({"type": "writer_web_tool_must_be_forbidden"})
    portfolio_ref = plan.get("dimension_evidence_portfolio_ref") if isinstance(plan.get("dimension_evidence_portfolio_ref"), Mapping) else {}
    if portfolio_ref and portfolio_ref.get("schema_version") != "finsight_dimension_evidence_portfolio_ref_v0_1":
        errors.append({"type": "dimension_evidence_portfolio_ref_schema_mismatch"})
    directive = plan.get("lead_memo_directive") if isinstance(plan.get("lead_memo_directive"), Mapping) else {}
    if directive and not directive.get("gap_budget_policy"):
        errors.append({"type": "lead_memo_directive_missing_gap_budget_policy"})
    if not plan.get("sections") and (judgment_state or {}).get("dimension_judgments"):
        errors.append({"type": "sections_required_for_dimension_judgments"})
    if (judgment_state or {}).get("judgment_cards") and not plan.get("judgment_cards"):
        errors.append({"type": "judgment_cards_not_projected_to_memo_logic_plan"})
    if (judgment_state or {}).get("thesis_path") and not plan.get("thesis_path"):
        errors.append({"type": "thesis_path_not_projected_to_memo_logic_plan"})
    for section in plan.get("sections") or []:
        if not isinstance(section, Mapping):
            continue
        if not section.get("required_claim_ids") and not section.get("required_gap_refs"):
            errors.append({"type": "section_without_claim_or_gap_trace", "section_id": section.get("section_id")})
        if section.get("required_claim_ids") and not section.get("decision_changing_evidence_refs"):
            errors.append({"type": "section_claims_missing_decision_changing_evidence", "section_id": section.get("section_id")})
    if plan.get("sections"):
        outline = plan.get("answer_first_outline") if isinstance(plan.get("answer_first_outline"), Mapping) else {}
        bridge = [row for row in plan.get("evidence_to_thesis_bridge") or [] if isinstance(row, Mapping)]
        skeleton = plan.get("writer_thesis_skeleton") if isinstance(plan.get("writer_thesis_skeleton"), Mapping) else {}
        density = plan.get("thesis_density_contract") if isinstance(plan.get("thesis_density_contract"), Mapping) else {}
        if not outline.get("thesis_statement"):
            errors.append({"type": "answer_first_outline_missing_thesis_statement"})
        if not bridge:
            errors.append({"type": "evidence_to_thesis_bridge_missing"})
        if not skeleton.get("opening_judgment"):
            errors.append({"type": "writer_thesis_skeleton_missing_opening_judgment"})
        if not skeleton.get("dimension_moves"):
            errors.append({"type": "writer_thesis_skeleton_missing_dimension_moves"})
        if not density.get("minimum_supported_insight_sentences"):
            errors.append({"type": "thesis_density_contract_missing_minimums"})
    required_items = [row for row in plan.get("required_question_items") or [] if isinstance(row, Mapping)]
    if required_items:
        answer_plan = [row for row in plan.get("required_item_answer_plan") or [] if isinstance(row, Mapping)]
        answer_plan_ids = {str(row.get("question_item_id") or "") for row in answer_plan}
        required_ids = {str(row.get("question_item_id") or "") for row in required_items if str(row.get("question_item_id") or "")}
        missing_ids = sorted(required_ids - answer_plan_ids)
        if missing_ids:
            errors.append({"type": "required_item_answer_plan_missing", "question_item_ids": missing_ids[:8]})
        for row in answer_plan:
            if not str(row.get("answer_first_judgment_prompt") or "").strip():
                errors.append(
                    {
                        "type": "required_item_answer_plan_missing_answer_prompt",
                        "question_item_id": row.get("question_item_id"),
                    }
                )
    product_sections = [
        section
        for section in plan.get("sections") or []
        if isinstance(section, Mapping) and str(section.get("section_id") or "").startswith("product")
    ]
    if product_sections:
        frame = plan.get("product_reasoning_frame") if isinstance(plan.get("product_reasoning_frame"), Mapping) else {}
        if not frame.get("coverage_roles"):
            errors.append({"type": "product_section_missing_product_reasoning_frame"})
    return {
        "schema_version": "finsight_memo_logic_plan_validation_v0_1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "policy": "memo_writer_expression_only_no_fact_tools_v0_1",
    }


def _title(dimension_id: str) -> str:
    return dimension_id.replace("_", " ").title()


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)] if str(value).strip() else []


def _compact_lead_directive(value: Mapping[str, Any]) -> dict[str, Any]:
    if not value:
        return {}
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "memo_stance": str(value.get("memo_stance") or ""),
        "objective_satisfaction": dict(value.get("objective_satisfaction") or {})
        if isinstance(value.get("objective_satisfaction"), Mapping)
        else {},
        "opening_policy": str(value.get("opening_policy") or ""),
        "gap_budget_policy": dict(value.get("gap_budget_policy") or {})
        if isinstance(value.get("gap_budget_policy"), Mapping)
        else {},
        "product_output_contract": dict(value.get("product_output_contract") or {})
        if isinstance(value.get("product_output_contract"), Mapping)
        else {},
        "issuer_targeted_repair_required": bool(value.get("issuer_targeted_repair_required")),
        "issuer_targeted_repair_tickers": _list(value.get("issuer_targeted_repair_tickers"))[:12],
        "dimension_write_priorities": [
            dict(item)
            for item in value.get("dimension_write_priorities") or []
            if isinstance(item, Mapping)
        ][:12],
    }


def _compact_product_reasoning_frame(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not value:
        return {}
    return {
        "schema_version": str(value.get("schema_version") or "finsight_product_reasoning_frame_v0_1"),
        "coverage_roles": _list(value.get("coverage_roles"))[:12],
        "product_profile_refs": _list(value.get("product_profile_refs"))[:12],
        "product_spec_refs": _list(value.get("product_spec_refs"))[:12],
        "product_kpi_refs": _list(value.get("product_kpi_refs"))[:12],
        "deployment_refs": _list(value.get("deployment_refs"))[:12],
        "performance_proxy_refs": _list(value.get("performance_proxy_refs"))[:12],
        "relationship_edge_refs": _list(value.get("relationship_edge_refs"))[:12],
        "scope_hypothesis_refs": _list(value.get("scope_hypothesis_refs"))[:12],
        "required_reasoning_edges": _list(value.get("required_reasoning_edges"))[:12],
        "writer_instruction": str(value.get("writer_instruction") or "")[:600],
    }


def _economic_role_summary(judgment_state: Mapping[str, Any]) -> dict[str, Any]:
    claims = [row for row in judgment_state.get("supported_claims") or [] if isinstance(row, Mapping)]
    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    boundary_counts: dict[str, int] = {}
    for claim in claims:
        economic_role = str(claim.get("economic_role") or "").strip()
        transmission_role = str(claim.get("transmission_role") or "").strip()
        role_boundary = str(claim.get("role_boundary") or "").strip()
        if not economic_role and not transmission_role and not role_boundary:
            continue
        if economic_role:
            counts[economic_role] = counts.get(economic_role, 0) + 1
        if role_boundary:
            boundary_counts[role_boundary] = boundary_counts.get(role_boundary, 0) + 1
        rows.append(
            {
                "claim_id": str(claim.get("claim_id") or "")[:120],
                "ticker_scope": _list(claim.get("ticker_scope"))[:4],
                "metric_scope": _list(claim.get("metric_scope"))[:4],
                "analysis_dimension": str(claim.get("analysis_dimension") or "")[:80],
                "scope_role": str(claim.get("scope_role") or "")[:80],
                "economic_role": economic_role[:120],
                "transmission_role": transmission_role[:160],
                "memo_use_role": str(claim.get("memo_use_role") or "")[:260],
                "role_boundary": role_boundary[:160],
                "evidence_refs": _list(claim.get("evidence_refs"))[:2],
            }
        )
    return {
        "schema_version": "finsight_economic_role_summary_v0_1",
        "role_counts": dict(sorted(counts.items())),
        "role_boundary_counts": dict(sorted(boundary_counts.items())),
        "role_rows": rows[:18],
        "writer_instruction": (
            "Use economic_role/transmission_role before interpreting a fact. "
            "Peer/customer capex is demand-pool context, not supplier revenue or direct order. "
            "Issuer capex is own reinvestment or cash-flow pressure, not customer demand without an explicit counterparty edge."
        )
        if rows
        else "",
    }


def _compact_required_question_items(value: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in value:
        if not isinstance(row, Mapping):
            continue
        rows.append(
            {
                "question_item_id": str(row.get("question_item_id") or row.get("item_id") or row.get("required_item_id") or "")[:120],
                "dimension": str(row.get("dimension") or "")[:80],
                "required_tickers": _list(row.get("required_tickers"))[:12],
                "required_evidence_roles": _list(row.get("required_evidence_roles"))[:12],
                "minimum_answer_status": str(row.get("minimum_answer_status") or "answered_with_boundary")[:80],
                "expected_repair_policy": str(row.get("expected_repair_policy") or "root_cause_if_not_answered")[:120],
                "terms_any": _list(row.get("terms_any"))[:16],
                "answer_contract": str(row.get("answer_contract") or "")[:300],
            }
        )
    return rows


def _compact_focus_ticker_policy(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not value:
        return {}
    return {
        "focus_tickers": _list(value.get("focus_tickers"))[:12],
        "policy": str(value.get("policy") or "memo_must_not_claim_missing_data_when_approved_facts_exist")[:160],
        "minimum_statuses": _list(value.get("minimum_statuses"))[:8],
    }


def _compact_dimension_portfolio_ref(value: Mapping[str, Any]) -> dict[str, Any]:
    if not value:
        return {}
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "portfolio_id": str(value.get("portfolio_id") or ""),
        "agent_id": str(value.get("agent_id") or ""),
        "focus_tickers": _list(value.get("focus_tickers"))[:12],
        "status_counts": dict(value.get("status_counts") or {}) if isinstance(value.get("status_counts"), Mapping) else {},
        "dimensions": [
            {
                "dimension_id": str(item.get("dimension_id") or ""),
                "evidence_status": str(item.get("evidence_status") or ""),
                "evidence_roles": _list(item.get("evidence_roles"))[:8],
                "available_pack_refs": _list(item.get("available_pack_refs"))[:6],
                "missing_pack_refs": _list(item.get("missing_pack_refs"))[:6],
            }
            for item in value.get("dimensions") or []
            if isinstance(item, Mapping)
        ][:8],
        "writer_boundary": str(value.get("writer_boundary") or ""),
    }


def _compact_judgment_cards(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return rows
    for item in value:
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                "judgment_card_id": str(item.get("judgment_card_id") or ""),
                "source_claim_id": str(item.get("source_claim_id") or ""),
                "dimension_id": str(item.get("dimension_id") or ""),
                "memo_slot": str(item.get("memo_slot") or ""),
                "judgment": str(item.get("judgment") or "")[:360],
                "evidence_bridge": str(item.get("evidence_bridge") or "")[:360],
                "business_mechanism": str(item.get("business_mechanism") or "")[:260],
                "financial_bridge": str(item.get("financial_bridge") or "")[:260],
                "counter_read": str(item.get("counter_read") or "")[:220],
                "what_would_change_view": _list(item.get("what_would_change_view"))[:3],
                "evidence_refs": _list(item.get("evidence_refs"))[:6],
                "source_role": str(item.get("source_role") or ""),
                "authority_boundary": str(item.get("authority_boundary") or "")[:180],
                "mechanism_bridge_status": str(item.get("mechanism_bridge_status") or ""),
            }
        )
        if len(rows) >= 10:
            break
    return rows


def _compact_thesis_path(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "status": str(value.get("status") or ""),
        "primary_thesis": str(value.get("primary_thesis") or "")[:360],
        "mechanism_bridge_status": str(value.get("mechanism_bridge_status") or ""),
        "path_nodes": [
            {
                "node_id": str(row.get("node_id") or ""),
                "dimension_id": str(row.get("dimension_id") or ""),
                "judgment_card_ids": _list(row.get("judgment_card_ids"))[:4],
                "claim_ids": _list(row.get("claim_ids"))[:4],
                "evidence_refs": _list(row.get("evidence_refs"))[:5],
                "business_mechanism": str(row.get("business_mechanism") or "")[:220],
                "financial_bridge": str(row.get("financial_bridge") or "")[:220],
                "counter_read": str(row.get("counter_read") or "")[:180],
                "what_would_change_view": _list(row.get("what_would_change_view"))[:3],
                "node_status": str(row.get("node_status") or ""),
            }
            for row in value.get("path_nodes") or []
            if isinstance(row, Mapping)
        ][:8],
        "path_edges": [
            {
                "edge_id": str(row.get("edge_id") or ""),
                "from_node_id": str(row.get("from_node_id") or ""),
                "to_node_id": str(row.get("to_node_id") or ""),
                "edge_type": str(row.get("edge_type") or ""),
                "mechanism": str(row.get("mechanism") or "")[:220],
                "evidence_refs": _list(row.get("evidence_refs"))[:5],
            }
            for row in value.get("path_edges") or []
            if isinstance(row, Mapping)
        ][:10],
        "writer_instruction": str(value.get("writer_instruction") or "")[:260],
    }


def _compact_repair_execution(value: Mapping[str, Any]) -> dict[str, Any]:
    if not value:
        return {}
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "status": str(value.get("status") or ""),
        "attempted_count": int(value.get("attempted_count") or 0),
        "success_count": int(value.get("success_count") or 0),
        "bounded_gap_count": int(value.get("bounded_gap_count") or 0),
        "official_context_summaries": [
            {
                "ticker": str(item.get("ticker") or ""),
                "source_class": str(item.get("source_class") or ""),
                "title": str(item.get("title") or ""),
                "url": str(item.get("url") or item.get("snapshot_url") or ""),
                "claim_boundary": str(item.get("claim_boundary") or item.get("authority_boundary") or ""),
                "parser_diagnosis_complete": bool(item.get("parser_diagnosis_complete")),
                "source_specific_parser_status": str(item.get("source_specific_parser_status") or "")[:160],
                "exact_fact_parser_failure_reason": str(item.get("exact_fact_parser_failure_reason") or "")[:260],
                "next_parser_action": str(item.get("next_parser_action") or "")[:220],
            }
            for item in value.get("official_context_summaries") or []
            if isinstance(item, Mapping)
        ][:8],
    }


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _section_thesis_direction(dimension: Mapping[str, Any], lead_review: Mapping[str, Any]) -> str:
    for key in ("thesis_direction", "judgment", "summary", "conclusion", "stance"):
        value = str(dimension.get(key) or lead_review.get(key) or "").strip()
        if value:
            return value
    claim_ids = _list(dimension.get("claim_ids"))
    gap_ids = _list(lead_review.get("gap_ids"))
    if claim_ids and gap_ids:
        return "mixed_support_with_boundary"
    if claim_ids:
        return "supporting_evidence_available"
    if gap_ids:
        return "boundary_or_counter_thesis_required"
    return "planning_context"


def _decision_changing_refs(dimension: Mapping[str, Any], lead_review: Mapping[str, Any]) -> list[str]:
    refs = [
        *_list(dimension.get("decision_changing_evidence_refs")),
        *_list(dimension.get("evidence_refs")),
        *_list(lead_review.get("evidence_refs")),
    ]
    return _dedupe(refs)[:8]


def _counter_thesis_refs(dimension: Mapping[str, Any], lead_review: Mapping[str, Any]) -> list[str]:
    refs = [
        *_list(dimension.get("counter_thesis_refs")),
        *_list(dimension.get("counter_claim_ids")),
        *_list(dimension.get("unsupported_claim_ids")),
        *_list(lead_review.get("gap_ids")),
    ]
    return _dedupe(refs)[:8]


def _answer_first_outline(*, sections: list[dict[str, Any]], lead_directive: Mapping[str, Any]) -> dict[str, Any]:
    supporting = [section for section in sections if section.get("required_claim_ids")]
    boundary = [section for section in sections if section.get("required_gap_refs") or section.get("counter_thesis_refs")]
    decision_refs = _dedupe(
        ref
        for section in sections
        for ref in _list(section.get("decision_changing_evidence_refs"))
    )[:12]
    memo_stance = str(lead_directive.get("memo_stance") or "").strip()
    if memo_stance:
        thesis_statement = memo_stance
    elif supporting:
        titles = ", ".join(str(section.get("title") or section.get("section_id")) for section in supporting[:3])
        thesis_statement = f"Lead with the judgment supported by {titles}; use gaps only where they change that judgment."
    elif boundary:
        thesis_statement = "Lead with the bounded judgment and state which missing evidence prevents stronger thesis promotion."
    else:
        thesis_statement = "Lead with the research objective answer before listing evidence or gaps."
    return {
        "schema_version": "finsight_memo_answer_first_outline_v0_1",
        "thesis_statement": thesis_statement,
        "supporting_dimension_ids": [str(section.get("section_id") or "") for section in supporting],
        "counter_thesis_dimension_ids": [str(section.get("section_id") or "") for section in boundary],
        "decision_changing_evidence_refs": decision_refs,
        "opening_instruction": "state judgment first, then causal bridge, then evidence and boundaries",
    }


def _evidence_to_thesis_bridge(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for section in sections:
        claim_ids = _list(section.get("required_claim_ids"))
        evidence_refs = _list(section.get("decision_changing_evidence_refs"))
        gap_refs = _list(section.get("required_gap_refs"))
        if not claim_ids and not evidence_refs and not gap_refs:
            continue
        rows.append(
            {
                "dimension_id": str(section.get("section_id") or ""),
                "thesis_role": "supporting_thesis" if claim_ids or evidence_refs else "boundary_or_counter_thesis",
                "claim_ids": claim_ids[:8],
                "evidence_refs": evidence_refs[:8],
                "gap_refs": gap_refs[:8],
                "counter_thesis_refs": _list(section.get("counter_thesis_refs"))[:8],
                "writer_instruction": "convert these refs into causal investment judgment; do not dump ids or internal labels",
            }
        )
    return rows


def _thesis_density_contract(*, sections: list[dict[str, Any]], product_frame: Mapping[str, Any]) -> dict[str, Any]:
    supported_sections = [section for section in sections if section.get("required_claim_ids")]
    product_roles = set(_list(product_frame.get("coverage_roles")))
    required_product_moves: list[str] = []
    if product_roles:
        required_product_moves = [
            "state_product_capability_or_line",
            "connect_adoption_or_deployment_signal",
            "bridge_to_financial_or_supply_chain_effect",
            "separate_exact_kpi_gap_from_product_judgment",
        ]
    return {
        "schema_version": "finsight_thesis_density_contract_v0_1",
        "minimum_supported_insight_sentences": max(3, min(6, len(supported_sections) + 2)),
        "minimum_causal_bridges": max(2, min(4, len(supported_sections))),
        "maximum_gap_body_share": 0.2,
        "required_product_moves": required_product_moves,
        "forbidden_low_density_patterns": [
            "evidence_inventory_without_judgment",
            "driver_by_driver_recitation",
            "gap_first_opening_when_supported_claims_exist",
            "product_section_only_says_no_sku_revenue",
            "decision_sections_only_tell_user_what_to_watch",
        ],
        "pass_definition": (
            "Writer must convert supported claims into judgment, causal bridge, counter-read, and monitoring triggers; "
            "absence of hallucination alone is not sufficient."
        ),
    }


def _writer_thesis_skeleton(
    *,
    outline: Mapping[str, Any],
    bridge: list[dict[str, Any]],
    product_frame: Mapping[str, Any],
    lead_directive: Mapping[str, Any],
    required_item_answer_plan: list[dict[str, Any]] | None = None,
    economic_role_summary: Mapping[str, Any] | None = None,
    judgment_cards: list[dict[str, Any]] | None = None,
    thesis_path: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    thesis_statement = str(outline.get("thesis_statement") or "").strip()
    path = dict(thesis_path or {}) if isinstance(thesis_path, Mapping) else {}
    path_primary = str(path.get("primary_thesis") or "").strip()
    cards = [dict(item) for item in judgment_cards or [] if isinstance(item, Mapping)]
    cards_by_dimension: dict[str, list[dict[str, Any]]] = {}
    for card in cards:
        dimension_id = str(card.get("dimension_id") or "")
        if dimension_id:
            cards_by_dimension.setdefault(dimension_id, []).append(card)
    product_edges = _list(product_frame.get("required_reasoning_edges"))
    item_plan_by_dimension: dict[str, list[dict[str, Any]]] = {}
    for item in required_item_answer_plan or []:
        if not isinstance(item, Mapping):
            continue
        dimension = str(item.get("dimension") or "")
        if not dimension:
            continue
        item_plan_by_dimension.setdefault(dimension, []).append(dict(item))
    dimension_moves = []
    for row in bridge:
        if not isinstance(row, Mapping):
            continue
        dimension_id = str(row.get("dimension_id") or "")
        item_plans = item_plan_by_dimension.get(dimension_id, [])
        dimension_moves.append(
            {
                "dimension_id": dimension_id,
                "role": str(row.get("thesis_role") or ""),
                "claim_ids": _list(row.get("claim_ids"))[:4],
                "judgment_card_ids": [
                    str(card.get("judgment_card_id") or "")
                    for card in cards_by_dimension.get(dimension_id, [])[:4]
                    if str(card.get("judgment_card_id") or "")
                ],
                "evidence_refs": _list(row.get("evidence_refs"))[:4],
                "gap_refs": _list(row.get("gap_refs"))[:3],
                "required_item_ids": [str(item.get("question_item_id") or "") for item in item_plans[:6]],
                "required_writer_move": (
                    "make_a_bounded_judgment_then_explain_business_mechanism_financial_bridge_and_counter_read"
                    if row.get("claim_ids") or row.get("evidence_refs")
                    else "state_why_the_boundary_changes_or_limits_the_thesis"
                ),
                "required_item_answer_moves": [
                    {
                        "question_item_id": str(item.get("question_item_id") or ""),
                        "answer_role": str(item.get("answer_role") or ""),
                        "answer_first_judgment_prompt": str(item.get("answer_first_judgment_prompt") or "")[:240],
                        "evidence_bridge_prompt": str(item.get("evidence_bridge_prompt") or "")[:220],
                        "counter_read_prompt": str(item.get("counter_read_prompt") or "")[:180],
                        "what_would_change_prompt": str(item.get("what_would_change_prompt") or "")[:180],
                    }
                    for item in item_plans[:4]
                ],
            }
        )
    causal_chain = [
        "start_from_answerable_thesis_not_evidence_inventory",
        "link_business_or_product_signal_to_financial_or_market_consequence",
        "state_what_would_change_the_view",
    ]
    if product_edges:
        causal_chain.extend(product_edges[:4])
    return {
        "schema_version": "finsight_writer_thesis_skeleton_v0_1",
        "opening_judgment": path_primary or thesis_statement or "Answer the research question first, then explain the evidence bridge.",
        "stance": str(lead_directive.get("memo_stance") or "")[:500],
        "causal_chain": _dedupe(causal_chain)[:8],
        "dimension_moves": dimension_moves[:8],
        "thesis_path_move": _writer_thesis_path_move(path),
        "judgment_card_moves": _writer_judgment_card_moves(cards),
        "product_reasoning_move": {
            "coverage_roles": _list(product_frame.get("coverage_roles"))[:10],
            "required_reasoning_edges": product_edges[:8],
            "instruction": (
                "Use product profile/spec/KPI/deployment/proxy/relationship rows as a reasoning spine. "
                "Do not make SKU revenue absence the main conclusion when other product evidence exists."
            )
            if product_frame
            else "",
        },
        "economic_role_move": {
            "role_counts": dict((economic_role_summary or {}).get("role_counts") or {})
            if isinstance((economic_role_summary or {}).get("role_counts"), Mapping)
            else {},
            "role_boundary_counts": dict((economic_role_summary or {}).get("role_boundary_counts") or {})
            if isinstance((economic_role_summary or {}).get("role_boundary_counts"), Mapping)
            else {},
            "instruction": str((economic_role_summary or {}).get("writer_instruction") or "")[:420]
            if isinstance(economic_role_summary, Mapping)
            else "",
        },
        "writer_priority_order": [
            "opening_judgment",
            "economic_role_move",
            "thesis_path_move",
            "judgment_card_moves",
            "required_item_answer_plan",
            "dimension_moves",
            "product_reasoning_move",
            "what_would_change_the_view",
            "bounded_gaps",
        ],
        "forbidden_writer_moves": [
            "source_boundary_report_as_main_answer",
            "claim_id_dump",
            "generic_monitoring_without_current_judgment",
            "internal_schema_labels",
        ],
    }


def _writer_thesis_path_move(path: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(path, Mapping) or not path:
        return {}
    nodes = [dict(item) for item in path.get("path_nodes") or [] if isinstance(item, Mapping)]
    edges = [dict(item) for item in path.get("path_edges") or [] if isinstance(item, Mapping)]
    return {
        "primary_thesis": str(path.get("primary_thesis") or "")[:320],
        "mechanism_bridge_status": str(path.get("mechanism_bridge_status") or ""),
        "required_sequence": [
            {
                "dimension_id": str(node.get("dimension_id") or ""),
                "judgment_card_ids": _list(node.get("judgment_card_ids"))[:3],
                "business_mechanism": str(node.get("business_mechanism") or "")[:160],
                "financial_bridge": str(node.get("financial_bridge") or "")[:160],
                "counter_read": str(node.get("counter_read") or "")[:140],
            }
            for node in nodes[:5]
        ],
        "required_edges": [
            {
                "edge_type": str(edge.get("edge_type") or ""),
                "from_node_id": str(edge.get("from_node_id") or ""),
                "to_node_id": str(edge.get("to_node_id") or ""),
                "mechanism": str(edge.get("mechanism") or "")[:160],
            }
            for edge in edges[:5]
        ],
        "writer_instruction": str(path.get("writer_instruction") or "")[:220],
    }


def _writer_judgment_card_moves(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for card in cards[:8]:
        rows.append(
            {
                "judgment_card_id": str(card.get("judgment_card_id") or ""),
                "dimension_id": str(card.get("dimension_id") or ""),
                "source_claim_id": str(card.get("source_claim_id") or ""),
                "judgment": str(card.get("judgment") or "")[:220],
                "evidence_bridge": str(card.get("evidence_bridge") or "")[:220],
                "business_mechanism": str(card.get("business_mechanism") or "")[:180],
                "financial_bridge": str(card.get("financial_bridge") or "")[:180],
                "counter_read": str(card.get("counter_read") or "")[:160],
                "what_would_change_view": _list(card.get("what_would_change_view"))[:2],
                "evidence_refs": _list(card.get("evidence_refs"))[:4],
                "authority_boundary": str(card.get("authority_boundary") or "")[:120],
                "writer_move": (
                    "write_current_judgment_with_evidence_bridge_then_counter_read; "
                    "do_not_render_as_raw_claimcard_inventory"
                ),
            }
        )
    return rows


def _required_item_answer_plan(
    required_items: list[Mapping[str, Any]],
    *,
    sections: list[dict[str, Any]],
    product_frame: Mapping[str, Any],
) -> list[dict[str, Any]]:
    section_ids = {str(section.get("section_id") or "") for section in sections}
    product_roles = set(_list(product_frame.get("coverage_roles")))
    rows: list[dict[str, Any]] = []
    for item in required_items:
        if not isinstance(item, Mapping):
            continue
        item_id = str(item.get("question_item_id") or "").strip()
        if not item_id:
            continue
        dimension = str(item.get("dimension") or "").strip()
        if dimension not in section_ids and section_ids:
            dimension = _fallback_dimension_for_item(item_id, dimension)
        answer_contract = _item_answer_contract(item_id)
        rows.append(
            {
                "schema_version": "finsight_required_item_answer_plan_v0_1",
                "question_item_id": item_id,
                "dimension": dimension,
                "required_tickers": _list(item.get("required_tickers"))[:12],
                "required_evidence_roles": _list(item.get("required_evidence_roles"))[:10],
                "terms_any": _list(item.get("terms_any"))[:16],
                "minimum_answer_status": str(item.get("minimum_answer_status") or "answered_with_boundary")[:80],
                "answer_role": answer_contract["answer_role"],
                "answer_first_judgment_prompt": answer_contract["answer_first_judgment_prompt"],
                "evidence_bridge_prompt": answer_contract["evidence_bridge_prompt"],
                "counter_read_prompt": answer_contract["counter_read_prompt"],
                "what_would_change_prompt": answer_contract["what_would_change_prompt"],
                "product_frame_roles_available": sorted(product_roles)[:12],
                "minimum_rendered_standard": (
                    "Rendered memo must answer this item with a present bounded judgment plus causal/evidence bridge; "
                    "keyword mention or generic 'needs verification' language is not sufficient."
                ),
            }
        )
    return rows


def _fallback_dimension_for_item(item_id: str, fallback: str) -> str:
    value = item_id.lower()
    if any(term in value for term in ("capex", "capital", "financing")):
        return "capital_and_financing"
    if any(term in value for term in ("cycle", "shipment", "export", "supply")):
        return "industry_supply_chain" if "export" not in value else "risk_and_counterevidence"
    if any(term in value for term in ("product", "server", "gpu", "deployment", "order", "backlog", "customer")):
        return "product_and_production"
    return fallback or "thesis_synthesis"


def _item_answer_contract(item_id: str) -> dict[str, str]:
    value = item_id.lower()
    contracts: dict[str, dict[str, str]] = {
        "dell_ai_server_quality_margin_bridge": {
            "answer_role": "product_quality_to_margin_bridge",
            "answer_first_judgment_prompt": (
                "Judge whether DELL AI server growth looks like high-quality revenue or low-margin scale; "
                "connect AI server/ISG evidence to gross margin, operating margin, capex, and cash conversion."
            ),
            "evidence_bridge_prompt": "Use DELL AI server/ISG/product KPI and financial margin refs before discussing missing SKU revenue.",
            "counter_read_prompt": "If margin, mix, cash flow, or order evidence is weak, state the quality-risk counter-read.",
            "what_would_change_prompt": "A company-disclosed order/backlog/margin bridge or customer deployment row would upgrade the judgment.",
        },
        "nvda_gpu_supply_generation": {
            "answer_role": "product_generation_capability",
            "answer_first_judgment_prompt": (
                "Judge how NVDA GPU generation/spec/architecture evidence supports product capability and AI demand exposure; "
                "separate product capability from unreported SKU revenue."
            ),
            "evidence_bridge_prompt": "Use H100/H200/B200/GB200/Blackwell/CUDA/spec/deployment/supply-chain refs when available.",
            "counter_read_prompt": "Name the supply, customer deployment, or competitive substitute risk that can weaken the read-through.",
            "what_would_change_prompt": "Official customer deployment, allocation, or product-level demand evidence would make the read-through stronger.",
        },
        "cloud_capex_read_through": {
            "answer_role": "demand_pool_to_supplier_readthrough",
            "answer_first_judgment_prompt": (
                "Judge whether hyperscaler capex is only a demand-pool signal or can be linked to NVDA/DELL supplier revenue; "
                "do not stop at 'capex increased'."
            ),
            "evidence_bridge_prompt": "Bridge MSFT/AMZN/GOOGL capex to supplier products only through customer, supplier, order, deployment, or product exposure refs.",
            "counter_read_prompt": "If supplier-customer linkage is absent, state that capex supports industry demand but not direct supplier share.",
            "what_would_change_prompt": "A named procurement/deployment/customer or vendor allocation signal would upgrade the read-through.",
        },
        "customer_deployment_or_order_signal": {
            "answer_role": "adoption_or_order_validation",
            "answer_first_judgment_prompt": "Judge whether customer deployment/order/adoption evidence confirms product uptake or remains a proxy.",
            "evidence_bridge_prompt": "Use customer/deployment/order/channel refs; distinguish official deployment events from public proxy context.",
            "counter_read_prompt": "If only proxy evidence exists, state the adoption uncertainty rather than dropping the product section.",
            "what_would_change_prompt": "Named customer, order amount, deployment scale, or channel configuration evidence would change confidence.",
        },
        "asml_orders_or_backlog": {
            "answer_role": "orders_backlog_cycle_signal",
            "answer_first_judgment_prompt": "Judge what ASML orders/bookings/backlog imply for semicap cycle visibility and lithography demand.",
            "evidence_bridge_prompt": "Use ASML/non-US filing, IR, orders, backlog, EUV/DUV or systems revenue refs before generic peer-group context.",
            "counter_read_prompt": "If exact order/backlog facts are not promoted, identify parser/source boundary and use peers only as context.",
            "what_would_change_prompt": "Parsed ASML net bookings/backlog/system shipment tables would upgrade the section.",
        },
        "shipment_or_cycle_context": {
            "answer_role": "equipment_shipment_cycle_context",
            "answer_first_judgment_prompt": "Judge where AMAT/LRCX/KLAC/ASML sit in the wafer-fab-equipment cycle using revenue, backlog, capex, and shipment context.",
            "evidence_bridge_prompt": "Connect company facts to WFE/shipment/capex cycle context; do not use peer membership as the main proof.",
            "counter_read_prompt": "If shipment trackers are commercial or absent, state the public-source boundary and rely on company backlog/revenue/capex.",
            "what_would_change_prompt": "A shipment tracker or company order/backlog update would change cycle confidence.",
        },
        "customer_concentration_or_deployment": {
            "answer_role": "customer_concentration_or_deployment",
            "answer_first_judgment_prompt": "Judge whether TSMC/Samsung/Intel/customer exposure supports demand visibility or concentration risk.",
            "evidence_bridge_prompt": "Use official customer/deployment/concentration refs; relationship graph alone is only navigation context.",
            "counter_read_prompt": "If customer evidence is only hypothesized, mark low confidence and explain the missing official link.",
            "what_would_change_prompt": "Customer concentration tables, named deployments, or counterparty capex-to-tool evidence would upgrade the read.",
        },
        "export_restriction_context": {
            "answer_role": "export_control_risk",
            "answer_first_judgment_prompt": "Judge how China/export restrictions affect semicap revenue quality, order visibility, or risk discount.",
            "evidence_bridge_prompt": "Use official filing risk, regional exposure, license, or export-control context; keep broad policy news bounded.",
            "counter_read_prompt": "If revenue exposure is not quantified, state risk direction but not revenue impact magnitude.",
            "what_would_change_prompt": "Company-disclosed China exposure, license status, or order cancellation evidence would change risk weighting.",
        },
    }
    if value in contracts:
        return contracts[value]
    return {
        "answer_role": "required_question_answer",
        "answer_first_judgment_prompt": (
            "Answer the required item with a present bounded judgment first; do not merely list evidence or say more data is needed."
        ),
        "evidence_bridge_prompt": "Bridge available claim/evidence refs to the judgment and name the exact missing link if bounded.",
        "counter_read_prompt": "State the strongest counter-read or why the item remains low confidence.",
        "what_would_change_prompt": "Name the concrete evidence that would change the current judgment.",
    }


def _dedupe(values: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
