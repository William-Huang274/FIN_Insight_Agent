from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping


RESEARCH_OBJECTIVE_CONTRACT_SCHEMA_VERSION = "finsight_research_objective_contract_v0_1"
LEAD_REVIEW_CHECKPOINT_SCHEMA_VERSION = "finsight_lead_review_checkpoint_v0_1"
TARGETED_REPAIR_PLAN_SCHEMA_VERSION = "finsight_targeted_repair_plan_v0_1"
DIMENSION_STATUSES = {"sufficient", "retrievable_gap", "bounded_gap", "commercial_gap", "not_material"}


def build_research_objective_contract(
    *,
    query: str,
    required_dimensions: list[str] | None = None,
    minimum_evidence_requirements: Mapping[str, Any] | None = None,
    source_family_plan: Mapping[str, Any] | None = None,
    forbidden_claims: list[str] | None = None,
    mandatory_second_pass_triggers: list[str] | None = None,
    memo_intent: str = "investment_research_memo",
) -> dict[str, Any]:
    dimensions = required_dimensions or [
        "fundamentals",
        "product_and_production",
        "capital_and_financing",
        "competition_and_market_position",
        "risk_and_counterevidence",
    ]
    contract = {
        "schema_version": RESEARCH_OBJECTIVE_CONTRACT_SCHEMA_VERSION,
        "contract_id": f"roc:{_digest({'query': query, 'dimensions': dimensions})[:20]}",
        "core_question": query.strip(),
        "required_dimensions": dimensions,
        "minimum_evidence_requirements": dict(minimum_evidence_requirements or _default_minimum_requirements(dimensions)),
        "source_family_plan": dict(source_family_plan or {}),
        "forbidden_claims": list(forbidden_claims or []),
        "mandatory_second_pass_triggers": list(mandatory_second_pass_triggers or ["retrievable_gap"]),
        "memo_intent": memo_intent,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    contract["validation"] = validate_research_objective_contract(contract)
    return contract


def validate_research_objective_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    if str(contract.get("schema_version") or "") != RESEARCH_OBJECTIVE_CONTRACT_SCHEMA_VERSION:
        errors.append({"type": "schema_version_mismatch"})
    if not str(contract.get("core_question") or "").strip():
        errors.append({"type": "core_question_required"})
    if not contract.get("required_dimensions"):
        errors.append({"type": "required_dimensions_required"})
    return {"schema_version": "finsight_research_objective_contract_validation_v0_1", "status": "fail" if errors else "pass", "errors": errors}


def build_lead_review_checkpoint(
    *,
    objective_contract: Mapping[str, Any],
    retrieval_budget_audit: Mapping[str, Any] | None = None,
    packs: Mapping[str, Any] | None = None,
    claim_cards: list[Mapping[str, Any]] | None = None,
    gaps: list[Mapping[str, Any]] | None = None,
    source_capability: Mapping[str, Any] | None = None,
    run_audit: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    dimensions = [str(item) for item in objective_contract.get("required_dimensions") or []]
    claims = [dict(item) for item in claim_cards or []]
    gap_rows = [dict(item) for item in gaps or []]
    pack_map = dict(packs or {})
    dimension_reviews = []
    for dimension in dimensions:
        dimension_reviews.append(
            _review_dimension(
                dimension,
                objective_contract=objective_contract,
                retrieval_budget_audit=retrieval_budget_audit or {},
                packs=pack_map,
                claim_cards=claims,
                gaps=gap_rows,
                source_capability=source_capability or {},
            )
        )
    checkpoint = {
        "schema_version": LEAD_REVIEW_CHECKPOINT_SCHEMA_VERSION,
        "checkpoint_id": f"lead_review:{_digest({'objective': objective_contract, 'claims': claims, 'gaps': gap_rows})[:20]}",
        "objective_contract_id": objective_contract.get("contract_id") or "",
        "dimension_reviews": dimension_reviews,
        "status_counts": _status_counts(dimension_reviews),
        "run_audit_digest": _digest(run_audit or {}),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "policy": "lead_supervises_goal_coverage_before_writer_v0_1",
    }
    checkpoint["validation"] = validate_lead_review_checkpoint(checkpoint)
    return checkpoint


def validate_lead_review_checkpoint(checkpoint: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    for item in checkpoint.get("dimension_reviews") or []:
        if not isinstance(item, Mapping):
            continue
        if item.get("status") not in DIMENSION_STATUSES:
            errors.append({"type": "invalid_dimension_status", "dimension": item.get("dimension"), "status": item.get("status")})
        if item.get("status") == "sufficient" and not item.get("supporting_claim_ids"):
            errors.append({"type": "sufficient_dimension_without_claims", "dimension": item.get("dimension")})
    return {"schema_version": "finsight_lead_review_checkpoint_validation_v0_1", "status": "fail" if errors else "pass", "errors": errors}


def build_targeted_repair_plan(checkpoint: Mapping[str, Any]) -> dict[str, Any]:
    repairs = []
    for item in checkpoint.get("dimension_reviews") or []:
        if not isinstance(item, Mapping) or item.get("status") != "retrievable_gap":
            continue
        repairs.append(
            {
                "repair_id": f"repair:{item.get('dimension')}:{len(repairs) + 1}",
                "dimension": item.get("dimension"),
                "route": item.get("suggested_route") or "artifact_or_database_search",
                "allowed_source_families": item.get("allowed_source_families") or [],
                "forbidden_source_families": item.get("forbidden_source_families") or ["live_public_web_context_without_snapshot_gate"],
                "expected_claim_type": item.get("expected_claim_type") or "bounded_claim_card",
                "promotion_gate": "source_authority_period_unit_citation_and_claim_support_required",
                "not_found_gap": {
                    "gap_type": "retrievable_gap_not_found_after_targeted_repair",
                    "dimension": item.get("dimension"),
                },
            }
        )
    plan = {
        "schema_version": TARGETED_REPAIR_PLAN_SCHEMA_VERSION,
        "checkpoint_id": checkpoint.get("checkpoint_id") or "",
        "status": "ready" if repairs else "no_retrievable_gap",
        "repairs": repairs,
        "policy": "targeted_repair_only_for_retrievable_gap_no_generic_second_pass_v0_1",
    }
    plan["validation"] = validate_targeted_repair_plan(plan)
    return plan


def validate_targeted_repair_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    for repair in plan.get("repairs") or []:
        if not isinstance(repair, Mapping):
            continue
        if not repair.get("route"):
            errors.append({"type": "repair_route_required", "repair_id": repair.get("repair_id")})
        if not repair.get("promotion_gate"):
            errors.append({"type": "promotion_gate_required", "repair_id": repair.get("repair_id")})
    return {"schema_version": "finsight_targeted_repair_plan_validation_v0_1", "status": "fail" if errors else "pass", "errors": errors}


def _review_dimension(
    dimension: str,
    *,
    objective_contract: Mapping[str, Any],
    retrieval_budget_audit: Mapping[str, Any],
    packs: Mapping[str, Any],
    claim_cards: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    source_capability: Mapping[str, Any],
) -> dict[str, Any]:
    supporting = [
        claim
        for claim in claim_cards
        if dimension == str(claim.get("analysis_dimension") or claim.get("dimension") or "")
        or dimension in [str(item) for item in claim.get("dimensions") or []]
    ]
    dimension_gaps = [
        gap
        for gap in gaps
        if dimension == str(gap.get("analysis_dimension") or gap.get("dimension") or "")
        or dimension in str(gap.get("gap_id") or gap.get("gap_type") or "")
    ]
    if supporting:
        status = "sufficient"
    elif any(str(gap.get("gap_type") or "").startswith("commercial") or "commercial" in str(gap) for gap in dimension_gaps):
        status = "commercial_gap"
    elif any(str(gap.get("gap_type") or "") in {"source_boundary_blocked", "not_disclosed", "not_found"} for gap in dimension_gaps):
        status = "bounded_gap"
    elif _has_route_capacity(dimension, retrieval_budget_audit, source_capability):
        status = "retrievable_gap"
    else:
        status = "bounded_gap" if dimension_gaps else "not_material"
    min_req = (objective_contract.get("minimum_evidence_requirements") or {}).get(dimension) or {}
    return {
        "dimension": dimension,
        "status": status,
        "supporting_claim_ids": [str(claim.get("claim_id") or "") for claim in supporting if str(claim.get("claim_id") or "")],
        "gap_ids": [str(gap.get("gap_id") or gap.get("id") or "") for gap in dimension_gaps if str(gap.get("gap_id") or gap.get("id") or "")],
        "minimum_evidence_requirement": min_req,
        "pack_present": bool(packs.get(_pack_key(dimension))),
        "suggested_route": _suggested_route(dimension),
        "allowed_source_families": _allowed_source_families(dimension),
        "forbidden_source_families": ["milvus_semantic_as_exact_authority", "live_public_web_context_without_snapshot_gate"],
        "expected_claim_type": _expected_claim_type(dimension),
    }


def _default_minimum_requirements(dimensions: list[str]) -> dict[str, Any]:
    return {
        dimension: {"min_verified_claim_cards": 1, "requires_source_boundary": True}
        for dimension in dimensions
    }


def _has_route_capacity(dimension: str, retrieval_budget_audit: Mapping[str, Any], source_capability: Mapping[str, Any]) -> bool:
    route_text = json.dumps({"retrieval": retrieval_budget_audit, "source": source_capability}, ensure_ascii=False).lower()
    if dimension.startswith("product"):
        return any(term in route_text for term in ("product", "public_source_context", "company_product_evidence_graph"))
    if dimension.startswith("capital"):
        return any(term in route_text for term in ("capital", "ownership", "debt", "13f"))
    if dimension.startswith("competition"):
        return any(term in route_text for term in ("market", "relationship", "industry"))
    return bool(route_text.strip("{}"))


def _pack_key(dimension: str) -> str:
    if dimension.startswith("fundamental"):
        return "fundamental_statement_pack"
    if dimension.startswith("product"):
        return "product_spec_pack"
    if dimension.startswith("capital"):
        return "capital_macro_exposure_pack"
    return f"{dimension}_pack"


def _suggested_route(dimension: str) -> str:
    if dimension.startswith("product"):
        return "company_product_evidence_graph_or_official_product_surface"
    if dimension.startswith("capital"):
        return "sec_capital_ownership_structured_sources"
    if dimension.startswith("competition"):
        return "market_snapshot_or_industry_relationship_context"
    return "ledger_first_or_sec_structured_artifact"


def _allowed_source_families(dimension: str) -> list[str]:
    if dimension.startswith("product"):
        return ["company_product_evidence_graph", "primary_sec_filing", "public_source_context", "live_public_web_context"]
    if dimension.startswith("capital"):
        return ["primary_sec_filing", "public_source_context"]
    if dimension.startswith("competition"):
        return ["market_snapshot", "industry_snapshot", "relationship_graph"]
    return ["primary_sec_filing", "company_authored_unaudited_sec_filing"]


def _expected_claim_type(dimension: str) -> str:
    if dimension.startswith("product"):
        return "company_reported_product_fact_or_product_context"
    if dimension.startswith("capital"):
        return "capital_structure_or_ownership_context"
    if dimension.startswith("competition"):
        return "market_or_competitive_context"
    return "company_reported_financial_fact"


def _status_counts(items: list[Mapping[str, Any]]) -> dict[str, int]:
    counts = {status: 0 for status in sorted(DIMENSION_STATUSES)}
    for item in items:
        status = str(item.get("status") or "")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()
