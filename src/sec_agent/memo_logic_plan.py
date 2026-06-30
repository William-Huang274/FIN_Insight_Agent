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
    sections = []
    for index, dimension in enumerate(dimension_judgments, start=1):
        dimension_id = str(dimension.get("dimension_id") or dimension.get("dimension") or f"dimension_{index}")
        lead_status = (lead_reviews.get(dimension_id) or {}).get("status") or ""
        product_instruction = ""
        if dimension_id.startswith("product"):
            product_instruction = (
                " Product sections must name the product/platform/taxonomy, disclose available KPI/spec/parameter/backlog/order context, "
                "and keep commercial tracker gaps short after public/official sources are exhausted."
            )
        sections.append(
            {
                "section_id": dimension_id,
                "title": str(dimension.get("title") or _title(dimension_id)),
                "order": index,
                "logic_role": "core_analysis" if lead_status != "bounded_gap" else "boundary_and_gap",
                "required_claim_ids": _list(dimension.get("claim_ids")),
                "required_evidence_refs": _list(dimension.get("evidence_refs")),
                "required_gap_refs": _list((lead_reviews.get(dimension_id) or {}).get("gap_ids")),
                "thesis_direction": _section_thesis_direction(dimension, lead_reviews.get(dimension_id) or {}),
                "decision_changing_evidence_refs": _decision_changing_refs(dimension, lead_reviews.get(dimension_id) or {}),
                "counter_thesis_refs": _counter_thesis_refs(dimension, lead_reviews.get(dimension_id) or {}),
                "dimension_pack_refs": _list((lead_reviews.get(dimension_id) or {}).get("dimension_portfolio_available_pack_refs")),
                "dimension_lead_questions": _list((lead_reviews.get(dimension_id) or {}).get("dimension_portfolio_lead_questions")),
                "writing_instruction": (
                    "explain_business_mechanism_financial_bridge_and_counter_read_with_citations;"
                    " write as analyst judgment, not ClaimCard or driver list."
                    f"{product_instruction}"
                ),
            }
        )
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
        "section_order": [section["section_id"] for section in sections],
        "sections": sections,
        "answer_first_outline": _answer_first_outline(sections=sections, lead_directive=lead_directive),
        "evidence_to_thesis_bridge": _evidence_to_thesis_bridge(sections),
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
        if not outline.get("thesis_statement"):
            errors.append({"type": "answer_first_outline_missing_thesis_statement"})
        if not bridge:
            errors.append({"type": "evidence_to_thesis_bridge_missing"})
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
