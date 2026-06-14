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
    sections = []
    for index, dimension in enumerate(dimension_judgments, start=1):
        dimension_id = str(dimension.get("dimension_id") or dimension.get("dimension") or f"dimension_{index}")
        lead_status = (lead_reviews.get(dimension_id) or {}).get("status") or ""
        sections.append(
            {
                "section_id": dimension_id,
                "title": str(dimension.get("title") or _title(dimension_id)),
                "order": index,
                "logic_role": "core_analysis" if lead_status != "bounded_gap" else "boundary_and_gap",
                "required_claim_ids": _list(dimension.get("claim_ids")),
                "required_evidence_refs": _list(dimension.get("evidence_refs")),
                "required_gap_refs": _list((lead_reviews.get(dimension_id) or {}).get("gap_ids")),
                "writing_instruction": "explain_business_mechanism_financial_bridge_and_counter_read_with_citations",
            }
        )
    plan = {
        "schema_version": MEMO_LOGIC_PLAN_SCHEMA_VERSION,
        "plan_id": f"memo_logic:{_digest({'judgment': judgment_state, 'lead': lead_review_checkpoint or {}})[:20]}",
        "memo_intent": memo_intent,
        "opening_answer_policy": "answer_first_high_information_density_no_driver_list_dump",
        "section_order": [section["section_id"] for section in sections],
        "sections": sections,
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
    if not plan.get("sections") and (judgment_state or {}).get("dimension_judgments"):
        errors.append({"type": "sections_required_for_dimension_judgments"})
    for section in plan.get("sections") or []:
        if not isinstance(section, Mapping):
            continue
        if not section.get("required_claim_ids") and not section.get("required_gap_refs"):
            errors.append({"type": "section_without_claim_or_gap_trace", "section_id": section.get("section_id")})
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


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()
