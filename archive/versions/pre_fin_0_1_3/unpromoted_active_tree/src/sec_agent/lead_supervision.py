from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping

from sec_agent.dimension_evidence_portfolio import compact_dimension_evidence_portfolio
from sec_agent.source_authority_coverage import (
    dimension_source_authority_candidates,
    source_authority_repairability,
    summarize_dimension_authority,
)


RESEARCH_OBJECTIVE_CONTRACT_SCHEMA_VERSION = "finsight_research_objective_contract_v0_1"
LEAD_REVIEW_CHECKPOINT_SCHEMA_VERSION = "finsight_lead_review_checkpoint_v0_1"
TARGETED_REPAIR_PLAN_SCHEMA_VERSION = "finsight_targeted_repair_plan_v0_1"
DIMENSION_STATUSES = {"sufficient", "retrievable_gap", "bounded_gap", "commercial_gap", "not_material"}
OFFICIAL_ISSUER_SOURCE_CLASSES = [
    "sec_fpi_filings",
    "company_ir",
    "local_exchange_filings",
    "regulator_filings",
]
OFFICIAL_ISSUER_SOURCE_PROBE_ORDER = [
    "sec_fpi_filings_20f_6k",
    "company_ir_reports",
    "local_exchange_filings",
    "regulator_filings",
]
PUBLIC_WEB_REPAIR_SOURCE_CLASSES: dict[str, list[str]] = {
    "issuer_official": [
        "sec_fpi_filings",
        "company_ir",
        "company_ir_material",
        "local_exchange_filings",
        "regulator_filings",
        "government_dataset_endpoint",
    ],
    "product_surface": [
        "company_product_page",
        "company_product_documentation",
        "company_ir_material",
        "company_support_documentation",
        "official_app_store_or_marketplace",
    ],
    "local_filing": [
        "sec_fpi_filings",
        "company_ir",
        "company_ir_material",
        "local_exchange_filings",
        "regulator_filings",
        "government_dataset_endpoint",
    ],
    "market_proxy": [
        "mainstream_financial_news_article",
        "official_statistics_dataset",
        "government_dataset_endpoint",
        "industry_association_dataset",
        "official_market_share_snapshot",
        "public_market_proxy_snapshot",
        "official_app_store_or_marketplace",
        "ecommerce_major_platform",
        "developer_ecosystem_snapshot",
        "public_tender_or_contract_portal",
        "job_posting_snapshot",
        "channel_pricing_snapshot",
        "platform_review_or_ranking_snapshot",
    ],
    "capital_ownership": [
        "sec_ownership_filing",
        "sec_offering_filing",
        "sec_company_submissions",
        "company_ir_material",
        "regulator_filings",
    ],
    "supply_chain": [
        "company_customer_page",
        "company_supplier_page",
        "supplier_customer_official_news",
        "company_ir_material",
        "official_partner_directory",
        "industry_association_dataset",
    ],
}
PUBLIC_WEB_REPAIR_ROUTES: dict[str, str] = {
    "issuer_official": "official_issuer_disclosure_repair",
    "product_surface": "official_product_surface_repair",
    "local_filing": "official_local_filing_repair",
    "market_proxy": "public_market_proxy_repair",
    "capital_ownership": "capital_ownership_repair",
    "supply_chain": "official_supply_chain_repair",
}
PUBLIC_WEB_REPAIR_SCOPE_POLICIES: dict[str, list[str]] = {
    "issuer_official": ["company_ir_local_exchange_regulator_sec_fpi_only"],
    "product_surface": ["official_product_surface_only"],
    "local_filing": ["company_ir_local_exchange_regulator_sec_fpi_only"],
    "market_proxy": ["official_statistics_or_industry_dataset_only"],
    "capital_ownership": ["sec_company_ir_offering_ownership_only"],
    "supply_chain": ["official_company_partner_supplier_customer_only"],
}
PUBLIC_WEB_REPAIR_PROBE_ORDER: dict[str, list[str]] = {
    "issuer_official": OFFICIAL_ISSUER_SOURCE_PROBE_ORDER,
    "product_surface": ["company_product_pages", "company_ir_product_pages", "official_docs_or_marketplace"],
    "local_filing": ["sec_fpi_filings_20f_6k", "company_ir_reports", "local_exchange_filings", "regulator_filings"],
    "market_proxy": [
        "mainstream_financial_news_article",
        "official_statistics_dataset",
        "industry_association_dataset",
        "official_market_share_snapshot",
        "official_app_store_or_marketplace",
        "ecommerce_major_platform",
        "developer_ecosystem_snapshot",
        "public_tender_or_contract_portal",
        "job_posting_snapshot",
        "channel_pricing_snapshot",
        "platform_review_or_ranking_snapshot",
    ],
    "capital_ownership": ["sec_offering_filings", "sec_ownership_filings", "company_ir_financing_pages"],
    "supply_chain": ["company_customer_pages", "company_supplier_pages", "supplier_customer_official_news", "official_partner_directory"],
}


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
    source_layer_capability: Mapping[str, Any] | None = None,
    source_authority_coverage: Mapping[str, Any] | None = None,
    run_audit: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    dimensions = [str(item) for item in objective_contract.get("required_dimensions") or []]
    claims = [dict(item) for item in claim_cards or []]
    gap_rows = [dict(item) for item in gaps or []]
    pack_map = dict(packs or {})
    dimension_portfolio = (
        pack_map.get("dimension_evidence_portfolio")
        if isinstance(pack_map.get("dimension_evidence_portfolio"), Mapping)
        else {}
    )
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
                source_layer_capability=source_layer_capability or {},
                source_authority_coverage=source_authority_coverage or {},
            )
        )
    issuer_reviews = _review_issuer_coverage_gaps(gap_rows)
    checkpoint = {
        "schema_version": LEAD_REVIEW_CHECKPOINT_SCHEMA_VERSION,
        "checkpoint_id": f"lead_review:{_digest({'objective': objective_contract, 'claims': claims, 'gaps': gap_rows})[:20]}",
        "objective_contract_id": objective_contract.get("contract_id") or "",
        "dimension_reviews": dimension_reviews,
        "dimension_evidence_portfolio_ref": compact_dimension_evidence_portfolio(
            dimension_portfolio,
            agent_id="research_lead",
        )
        if dimension_portfolio
        else {},
        "issuer_coverage_reviews": issuer_reviews,
        "source_authority_summary": _lead_source_authority_summary(
            dimension_reviews,
            source_authority_coverage or {},
        ),
        "status_counts": _status_counts(dimension_reviews),
        "run_audit_digest": _digest(run_audit or {}),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "policy": "lead_supervises_goal_coverage_before_writer_source_authority_matrix_v0_3",
    }
    checkpoint["memo_directive"] = _build_lead_memo_directive(
        objective_contract=objective_contract,
        dimension_reviews=dimension_reviews,
        issuer_reviews=issuer_reviews,
        gaps=gap_rows,
    )
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
        if item.get("suggested_route") == "official_issuer_disclosure_repair":
            continue
        repair_type = _repair_type(item)
        route = PUBLIC_WEB_REPAIR_ROUTES.get(repair_type, str(item.get("suggested_route") or "artifact_or_database_search"))
        repair = {
            "repair_id": f"repair:{item.get('dimension')}:{len(repairs) + 1}",
            "dimension": item.get("dimension"),
            "repair_type": repair_type,
            "route": route,
            "allowed_source_families": item.get("allowed_source_families") or [],
            "forbidden_source_families": item.get("forbidden_source_families") or ["live_public_web_context_without_snapshot_gate"],
            "expected_claim_type": item.get("expected_claim_type") or "bounded_claim_card",
            "promotion_gate": _promotion_gate_for_repair_type(repair_type),
            "not_found_gap": {
                "gap_type": _not_found_gap_type(repair_type),
                "dimension": item.get("dimension"),
                "repair_type": repair_type,
            },
        }
        if route in set(PUBLIC_WEB_REPAIR_ROUTES.values()):
            repair.update(
                {
                    "web_search_allowed": True,
                    "web_search_boundary": _web_search_boundary_for_repair_type(repair_type),
                    "web_scope_policy_ids": list(PUBLIC_WEB_REPAIR_SCOPE_POLICIES.get(repair_type, [])),
                    "source_probe_order": list(PUBLIC_WEB_REPAIR_PROBE_ORDER.get(repair_type, [])),
                    "allowed_source_classes": list(PUBLIC_WEB_REPAIR_SOURCE_CLASSES.get(repair_type, [])),
                    "claim_scope_boundary": _claim_scope_boundary_for_repair_type(repair_type),
                }
            )
            for key in (
                "ticker",
                "tickers",
                "company_domains",
                "official_product_urls",
                "official_product_surfaces",
                "official_metric_leads",
                "probe_urls",
                "market_proxy_urls",
                "market_source_class",
                "supply_chain_urls",
                "supply_source_class",
                "offering_urls",
                "ownership_urls",
                "source_authority_roles",
                "source_authority_source_ids",
                "source_authority_signal_types",
                "source_authority_probe_order",
                "source_authority_forbidden_claim_types",
            ):
                value = item.get(key)
                if value:
                    repair[key] = value
        repairs.append(repair)
    for item in checkpoint.get("issuer_coverage_reviews") or []:
        if not isinstance(item, Mapping) or item.get("status") != "retrievable_gap":
            continue
        ticker = str(item.get("ticker") or "UNKNOWN").strip().upper()
        repairs.append(
            {
                "repair_id": f"repair:issuer_coverage:{ticker}:{len(repairs) + 1}",
                "dimension": item.get("dimension") or "fundamentals",
                "ticker": ticker,
                "repair_type": "issuer_official",
                "route": "official_issuer_disclosure_repair",
                "web_search_allowed": True,
                "web_search_boundary": "official_sources_only_no_news_blogs_social_or_marketing_pages",
                "web_scope_policy_ids": list(PUBLIC_WEB_REPAIR_SCOPE_POLICIES["issuer_official"]),
                "source_probe_order": list(item.get("source_probe_order") or OFFICIAL_ISSUER_SOURCE_PROBE_ORDER),
                "official_source_classes": list(item.get("official_source_classes") or OFFICIAL_ISSUER_SOURCE_CLASSES),
                "allowed_source_classes": list(PUBLIC_WEB_REPAIR_SOURCE_CLASSES["issuer_official"]),
                "target_forms": ["20-F", "6-K"],
                "allowed_source_families": [
                    "primary_sec_filing",
                    "company_ir_reports",
                    "public_source_context",
                    "live_public_web_context",
                ],
                "forbidden_source_families": [
                    "unofficial_social_media",
                    "marketing_blog",
                    "forum_or_unverified_post",
                    "commercial_tracker_without_license",
                ],
                "expected_claim_type": "official_company_disclosure_context_or_company_reported_fact",
                "promotion_gate": "official_origin_parser_period_unit_citation_source_boundary_gate",
                "not_found_gap": {
                    "gap_type": "bounded_gap_after_official_issuer_source_probe",
                    "ticker": ticker,
                    "dimension": item.get("dimension") or "fundamentals",
                    "repair_type": "issuer_official",
                    "source_probe_order": list(item.get("source_probe_order") or OFFICIAL_ISSUER_SOURCE_PROBE_ORDER),
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
    web_routes = set(PUBLIC_WEB_REPAIR_ROUTES.values())
    for repair in plan.get("repairs") or []:
        if not isinstance(repair, Mapping):
            continue
        if not repair.get("route"):
            errors.append({"type": "repair_route_required", "repair_id": repair.get("repair_id")})
        if not repair.get("promotion_gate"):
            errors.append({"type": "promotion_gate_required", "repair_id": repair.get("repair_id")})
        if repair.get("route") == "official_issuer_disclosure_repair":
            if not repair.get("web_search_allowed"):
                errors.append({"type": "official_issuer_repair_requires_web_search_allowed", "repair_id": repair.get("repair_id")})
            if not repair.get("source_probe_order"):
                errors.append({"type": "official_issuer_repair_requires_probe_order", "repair_id": repair.get("repair_id")})
            if not repair.get("official_source_classes"):
                errors.append({"type": "official_issuer_repair_requires_source_classes", "repair_id": repair.get("repair_id")})
        if repair.get("route") in web_routes:
            if repair.get("repair_type") not in PUBLIC_WEB_REPAIR_ROUTES:
                errors.append({"type": "web_repair_requires_known_repair_type", "repair_id": repair.get("repair_id")})
            if not repair.get("web_scope_policy_ids"):
                errors.append({"type": "web_repair_requires_scope_policy", "repair_id": repair.get("repair_id")})
            if not repair.get("allowed_source_classes"):
                errors.append({"type": "web_repair_requires_allowed_source_classes", "repair_id": repair.get("repair_id")})
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
    source_layer_capability: Mapping[str, Any],
    source_authority_coverage: Mapping[str, Any],
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
    issuer_gap_present = any(_is_issuer_official_probe_gap(gap) for gap in dimension_gaps)
    repair_type = _repair_type_for_dimension_gaps(
        dimension,
        dimension_gaps=dimension_gaps,
        issuer_gap_present=issuer_gap_present,
    )
    source_layer_candidates = _source_layer_candidates_for_dimension(dimension, source_layer_capability)
    has_source_layer_repair_candidate = _has_source_layer_repair_candidate(source_layer_candidates)
    source_authority_candidates = dimension_source_authority_candidates(source_authority_coverage, dimension)
    source_authority_summary = summarize_dimension_authority(source_authority_candidates, dimension)
    source_authority_repair = source_authority_repairability(source_authority_candidates)
    has_source_authority_repair_candidate = bool(source_authority_repair.get("repairable_candidate_count"))
    portfolio_dimension = _portfolio_dimension_for_review(dimension, packs)
    portfolio_has_available_pack = bool(portfolio_dimension.get("available_pack_refs"))
    if supporting:
        status = "sufficient"
    elif any(str(gap.get("gap_type") or "").startswith("commercial") or "commercial" in str(gap) for gap in dimension_gaps):
        status = "commercial_gap"
    elif issuer_gap_present:
        status = "retrievable_gap"
    elif has_source_authority_repair_candidate:
        status = "retrievable_gap"
    elif has_source_layer_repair_candidate:
        status = "retrievable_gap"
    elif portfolio_has_available_pack:
        status = "retrievable_gap"
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
        "pack_present": bool(packs.get(_pack_key(dimension))) or portfolio_has_available_pack,
        "dimension_portfolio_status": str(portfolio_dimension.get("evidence_status") or ""),
        "dimension_portfolio_available_pack_refs": _unique_strings(portfolio_dimension.get("available_pack_refs") or []),
        "dimension_portfolio_missing_pack_refs": _unique_strings(portfolio_dimension.get("missing_pack_refs") or []),
        "dimension_portfolio_lead_questions": _unique_strings(portfolio_dimension.get("lead_questions") or [])[:6],
        "repair_type": repair_type,
        "suggested_route": PUBLIC_WEB_REPAIR_ROUTES.get(repair_type) or _suggested_route(dimension),
        "candidate_source_layers": source_layer_candidates,
        "source_layer_repairability": _source_layer_repairability(source_layer_candidates),
        "source_authority_candidates": source_authority_candidates[:12],
        "source_authority_coverage": source_authority_summary,
        "source_authority_repairability": source_authority_repair,
        "source_authority_roles": _unique_strings([row.get("source_role") for row in source_authority_candidates]),
        "source_authority_source_ids": _unique_strings([row.get("source_id") for row in source_authority_candidates]),
        "source_authority_signal_types": _unique_strings([row.get("signal_authority_type") for row in source_authority_candidates]),
        "source_authority_probe_order": _unique_strings([row.get("source_id") for row in source_authority_candidates if row.get("can_enter_evidence_bundle")]),
        "source_authority_forbidden_claim_types": _unique_strings(
            claim
            for row in source_authority_candidates
            for claim in (row.get("forbidden_claim_types") or [])
        ),
        "gap_types": _unique_strings([str(gap.get("gap_type") or "") for gap in dimension_gaps if str(gap.get("gap_type") or "")]),
        "ticker": (_tickers_from_gaps(dimension_gaps) or [""])[0],
        "tickers": _tickers_from_gaps(dimension_gaps),
        "company_domains": _strings_from_gaps(dimension_gaps, ["company_domains", "domains", "allowed_domains"]),
        "official_product_urls": _urls_from_gaps(dimension_gaps, ["official_product_urls", "product_urls", "company_product_urls"]),
        "official_product_surfaces": _strings_from_gaps(dimension_gaps, ["official_product_surfaces", "product_surfaces", "target_products", "products"]),
        "official_metric_leads": _strings_from_gaps(dimension_gaps, ["official_metric_leads", "metric_leads", "target_metrics"]),
        "probe_urls": _urls_from_gaps(dimension_gaps, ["probe_urls", "official_urls", "source_urls"]),
        "market_proxy_urls": _urls_from_gaps(
            dimension_gaps,
            [
                "market_proxy_urls",
                "official_market_urls",
                "app_store_urls",
                "ecommerce_urls",
                "developer_ecosystem_urls",
                "github_urls",
                "npm_urls",
                "pypi_urls",
                "huggingface_urls",
                "tender_urls",
                "public_order_urls",
                "hiring_urls",
                "job_posting_urls",
                "channel_offer_urls",
                "review_ranking_urls",
                "news_urls",
                "mainstream_news_urls",
            ],
        ),
        "market_source_class": (
            _strings_from_gaps(dimension_gaps, ["market_source_class", "source_class", "public_proxy_source_class"]) or [""]
        )[0],
        "supply_chain_urls": _urls_from_gaps(
            dimension_gaps,
            ["supply_chain_urls", "partner_urls", "customer_urls", "supplier_urls", "supplier_customer_news_urls", "official_news_urls"],
        ),
        "supply_source_class": (
            _strings_from_gaps(dimension_gaps, ["supply_source_class", "source_class", "official_news_source_class"]) or [""]
        )[0],
        "offering_urls": _urls_from_gaps(dimension_gaps, ["offering_urls", "debt_urls", "financing_urls"]),
        "ownership_urls": _urls_from_gaps(dimension_gaps, ["ownership_urls", "holder_urls", "insider_urls"]),
        "allowed_source_families": (
            ["primary_sec_filing", "company_ir_reports", "public_source_context", "live_public_web_context"]
            if issuer_gap_present
            else _allowed_source_families(dimension)
        ),
        "forbidden_source_families": ["milvus_semantic_as_exact_authority", "live_public_web_context_without_snapshot_gate"],
        "expected_claim_type": (
            "official_company_disclosure_context_or_company_reported_fact"
            if issuer_gap_present
            else _expected_claim_type(dimension)
        ),
    }


def _default_minimum_requirements(dimensions: list[str]) -> dict[str, Any]:
    return {
        dimension: {"min_verified_claim_cards": 1, "requires_source_boundary": True}
        for dimension in dimensions
    }


def _lead_source_authority_summary(
    dimension_reviews: list[Mapping[str, Any]],
    source_authority_coverage: Mapping[str, Any],
) -> dict[str, Any]:
    source_summary = source_authority_coverage.get("summary") if isinstance(source_authority_coverage.get("summary"), Mapping) else {}
    dimension_summaries = {}
    for row in dimension_reviews:
        dimension = str(row.get("dimension") or "")
        if not dimension:
            continue
        dimension_summaries[dimension] = {
            key: (row.get("source_authority_coverage") or {}).get(key)
            for key in (
                "candidate_count",
                "evidence_bundle_allowed_count",
                "exact_company_fact_authority_count",
                "thesis_driver_authority_count",
                "route_or_parser_debt_count",
                "attempt_backed_public_boundary_count",
                "gap_classification",
                "primary_source_roles",
                "primary_signal_authority_types",
            )
            if isinstance(row.get("source_authority_coverage"), Mapping)
        }
    return {
        "schema_version": "finsight_lead_source_authority_summary_v0_1",
        "coverage_status": str(source_authority_coverage.get("status") or ""),
        "scope_tickers": list(source_authority_coverage.get("scope_tickers") or []),
        "selected_row_count": int(source_authority_coverage.get("selected_row_count") or 0),
        "row_count": int(source_authority_coverage.get("row_count") or 0),
        "evidence_bundle_allowed_count": int(source_summary.get("evidence_bundle_allowed_count") or 0),
        "exact_company_fact_authority_count": int(source_summary.get("exact_company_fact_authority_count") or 0),
        "thesis_driver_authority_count": int(source_summary.get("thesis_driver_authority_count") or 0),
        "by_source_role": dict(source_summary.get("by_source_role") or {}),
        "by_signal_authority_type": dict(source_summary.get("by_signal_authority_type") or {}),
        "dimension_summaries": dimension_summaries,
        "policy": "LeadReviewCheckpoint must repair evidence-available signal gaps before exposing bounded gaps.",
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


def _source_layer_candidates_for_dimension(dimension: str, source_layer_capability: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = [
        row
        for row in source_layer_capability.get("rows") or []
        if isinstance(row, Mapping)
    ]
    if not rows:
        return []
    wanted_slots = _wanted_source_layer_slots(dimension)
    candidates: list[dict[str, Any]] = []
    for row in rows:
        slots = {str(item) for item in row.get("specialist_slots") or []}
        if wanted_slots and slots.isdisjoint(wanted_slots):
            continue
        layer_id = str(row.get("layer_id") or "")
        if layer_id not in {"L1", "L2", "L3"}:
            continue
        candidates.append(
            {
                "source_id": str(row.get("source_id") or ""),
                "layer_id": layer_id,
                "evidence_graph_status": str(row.get("evidence_graph_status") or ""),
                "claim_scope": str(row.get("claim_scope") or ""),
                "context_or_proxy_allowed": bool(row.get("context_or_proxy_allowed")),
                "exact_value_authority_ready": bool(row.get("exact_value_authority_ready")),
                "blocking_reason": str(row.get("blocking_reason") or ""),
                "next_action": str(row.get("next_action") or ""),
                "memo_usage": str(row.get("memo_usage") or ""),
            }
        )
    candidates.sort(key=_source_layer_candidate_sort_key)
    return candidates[:12]


def _wanted_source_layer_slots(dimension: str) -> set[str]:
    if dimension.startswith("fundamental"):
        return {"fundamental"}
    if dimension.startswith("product"):
        return {"product_technology"}
    if dimension.startswith("capital"):
        return {"capital_macro"}
    if dimension.startswith("competition"):
        return {"market_valuation", "industry_supply_chain", "product_technology"}
    if dimension.startswith("industry"):
        return {"industry_supply_chain"}
    if dimension.startswith("risk"):
        return {"risk_counterevidence"}
    return set()


def _source_layer_candidate_sort_key(row: Mapping[str, Any]) -> tuple[int, int, str]:
    status = str(row.get("evidence_graph_status") or "")
    status_rank = {
        "exact_authority_ready": 0,
        "runtime_ready_context": 1,
        "structured_not_promoted": 2,
        "staging_parser_gate_pending": 3,
        "crawlable_not_parsed_or_not_routed": 4,
        "missing_runtime_route": 5,
        "not_registered": 6,
    }.get(status, 7)
    layer_rank = {"L1": 0, "L2": 1, "L3": 2}.get(str(row.get("layer_id") or ""), 3)
    return (status_rank, layer_rank, str(row.get("source_id") or ""))


def _has_source_layer_repair_candidate(candidates: list[Mapping[str, Any]]) -> bool:
    repairable_statuses = {
        "structured_not_promoted",
        "staging_parser_gate_pending",
        "crawlable_not_parsed_or_not_routed",
        "runtime_ready_context",
    }
    return any(str(row.get("evidence_graph_status") or "") in repairable_statuses for row in candidates)


def _source_layer_repairability(candidates: list[Mapping[str, Any]]) -> dict[str, Any]:
    repairable = [
        row
        for row in candidates
        if str(row.get("evidence_graph_status") or "")
        in {"structured_not_promoted", "staging_parser_gate_pending", "crawlable_not_parsed_or_not_routed", "runtime_ready_context"}
    ]
    not_registered = [row for row in candidates if str(row.get("evidence_graph_status") or "") == "not_registered"]
    return {
        "repairable_candidate_count": len(repairable),
        "not_registered_candidate_count": len(not_registered),
        "primary_repair_sources": [str(row.get("source_id") or "") for row in repairable[:6]],
        "missing_runtime_route_sources": [str(row.get("source_id") or "") for row in not_registered[:6]],
        "policy": "repair structured/staging/crawlable sources before exposing bounded gap; not_registered sources become implementation backlog",
    }


def _pack_key(dimension: str) -> str:
    if dimension.startswith("fundamental"):
        return "fundamental_statement_pack"
    if dimension.startswith("product"):
        return "product_spec_pack"
    if dimension.startswith("capital"):
        return "capital_macro_exposure_pack"
    return f"{dimension}_pack"


def _portfolio_dimension_for_review(dimension: str, packs: Mapping[str, Any]) -> dict[str, Any]:
    portfolio = packs.get("dimension_evidence_portfolio") if isinstance(packs.get("dimension_evidence_portfolio"), Mapping) else {}
    if not portfolio:
        return {}
    aliases = _dimension_aliases(dimension)
    for row in portfolio.get("dimensions") or []:
        if not isinstance(row, Mapping):
            continue
        dimension_id = str(row.get("dimension_id") or "")
        if dimension_id in aliases:
            return dict(row)
    return {}


def _dimension_aliases(dimension: str) -> set[str]:
    value = str(dimension or "")
    aliases = {value}
    if value.startswith("fundamental"):
        aliases.add("fundamentals")
    if value.startswith("product"):
        aliases.add("product_and_production")
    if value.startswith("capital"):
        aliases.add("capital_and_financing")
    if value.startswith("competition") or value.startswith("market"):
        aliases.add("competition_and_market_position")
    if value.startswith("industry") or value.startswith("supply"):
        aliases.add("industry_supply_chain")
    if value.startswith("risk") or value.startswith("counter"):
        aliases.add("risk_and_counterevidence")
    return aliases


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


def _repair_type(item: Mapping[str, Any]) -> str:
    value = str(item.get("repair_type") or "").strip()
    if value in PUBLIC_WEB_REPAIR_ROUTES:
        return value
    return _repair_type_for_dimension_gaps(str(item.get("dimension") or ""), dimension_gaps=[], issuer_gap_present=False)


def _repair_type_for_dimension_gaps(
    dimension: str,
    *,
    dimension_gaps: list[dict[str, Any]],
    issuer_gap_present: bool,
) -> str:
    if issuer_gap_present:
        return "issuer_official"
    text = json.dumps({"dimension": dimension, "gaps": dimension_gaps}, ensure_ascii=False, sort_keys=True, default=str).lower()
    if any(marker in text for marker in ("13f", "13d", "13g", "form 3", "form 4", "form 5", "offering", "s-1", "s-3", "424b", "debt", "ownership", "insider", "holder")):
        return "capital_ownership"
    if dimension.startswith("product"):
        return "product_surface"
    if any(marker in text for marker in ("supplier", "customer", "supply chain", "vendor", "channel", "backlog", "order", "partner")):
        return "supply_chain"
    if any(marker in text for marker in ("local exchange", "regulator", "annual report", "20-f", "6-k", "dart", "edinet", "hkex")):
        return "local_filing"
    if dimension.startswith("capital"):
        return "capital_ownership"
    if dimension.startswith("competition"):
        return "market_proxy"
    if dimension.startswith("fundamental"):
        return "local_filing"
    return "market_proxy"


def _promotion_gate_for_repair_type(repair_type: str) -> str:
    if repair_type == "product_surface":
        return "official_product_surface_snapshot_and_context_only_no_sales_share_or_orders_promotion"
    if repair_type == "capital_ownership":
        return "sec_or_company_origin_period_issuer_security_citation_gate_context_only_until_parser_passes"
    if repair_type == "market_proxy":
        return "official_or_industry_proxy_source_boundary_and_scope_gate_no_company_sales_promotion"
    if repair_type == "supply_chain":
        return "official_relationship_source_boundary_gate_no_volume_or_revenue_promotion"
    return "official_origin_parser_period_unit_citation_source_boundary_gate"


def _not_found_gap_type(repair_type: str) -> str:
    return {
        "issuer_official": "bounded_gap_after_official_issuer_source_probe",
        "product_surface": "bounded_gap_after_official_product_surface_probe",
        "local_filing": "bounded_gap_after_local_filing_probe",
        "market_proxy": "bounded_gap_after_public_market_proxy_probe",
        "capital_ownership": "bounded_gap_after_capital_ownership_probe",
        "supply_chain": "bounded_gap_after_supply_chain_probe",
    }.get(repair_type, "retrievable_gap_not_found_after_targeted_repair")


def _web_search_boundary_for_repair_type(repair_type: str) -> str:
    return {
        "issuer_official": "official_sources_only_no_news_blogs_social_or_marketing_pages",
        "product_surface": "company_or_official_product_pages_only_no_forums_marketing_blogs_or_resellers",
        "local_filing": "regulator_exchange_company_ir_sec_fpi_only",
        "market_proxy": "official_statistics_industry_association_or_named_public_proxy_only_no_unverified_media",
        "capital_ownership": "sec_company_ir_regulator_offering_ownership_filings_only",
        "supply_chain": "official_company_partner_supplier_customer_or_industry_association_only",
    }.get(repair_type, "scoped_public_web_sources_only")


def _claim_scope_boundary_for_repair_type(repair_type: str) -> str:
    return {
        "product_surface": "can support product taxonomy/spec/parser target context; cannot support sell-through, sales, share, backlog, ASP, inventory, or orders without exact parser authority",
        "local_filing": "can support official filing/source availability and parser targeting; cannot promote exact facts until period, unit, and citation gates pass",
        "market_proxy": "can support industry direction or market context; cannot prove issuer-specific sales, share, orders, inventory, or channel metrics",
        "capital_ownership": "can support ownership/offering/debt context; exact amount/security/holder claims require source-specific parser gates",
        "supply_chain": "can support official relationship or supply-chain context; cannot infer shipment, revenue, allocation, or order volume",
        "issuer_official": "can support issuer coverage and official-source existence; cannot support sales/share/orders without parser authority",
    }.get(repair_type, "context only until source-specific parser authority passes")


def _unique_strings(values: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _tickers_from_gaps(gaps: list[dict[str, Any]]) -> list[str]:
    values: list[str] = []
    for gap in gaps:
        for key in ("ticker", "issuer", "company", "subject_ticker"):
            value = str(gap.get(key) or "").strip().upper()
            if value:
                values.append(value)
        values.extend(str(item).strip().upper() for item in gap.get("tickers") or [] if str(item).strip())
    return _unique_strings(values)


def _urls_from_gaps(gaps: list[dict[str, Any]], keys: list[str]) -> list[str]:
    urls: list[str] = []
    for gap in gaps:
        for key in keys:
            value = gap.get(key)
            if isinstance(value, str):
                urls.append(value)
            elif isinstance(value, Mapping):
                for subkey in ("url", "href", "source_url", "snapshot_url"):
                    if str(value.get(subkey) or "").strip():
                        urls.append(str(value.get(subkey) or ""))
            elif isinstance(value, (list, tuple, set)):
                for item in value:
                    if isinstance(item, Mapping):
                        for subkey in ("url", "href", "source_url", "snapshot_url"):
                            if str(item.get(subkey) or "").strip():
                                urls.append(str(item.get(subkey) or ""))
                    elif str(item or "").strip():
                        urls.append(str(item or ""))
        official_sources = gap.get("official_sources")
        if isinstance(official_sources, list):
            for item in official_sources:
                if isinstance(item, Mapping) and str(item.get("url") or "").strip():
                    urls.append(str(item.get("url") or ""))
    return [url for url in _unique_strings(urls) if url.lower().startswith(("http://", "https://"))]


def _strings_from_gaps(gaps: list[dict[str, Any]], keys: list[str]) -> list[str]:
    values: list[str] = []
    for gap in gaps:
        for key in keys:
            value = gap.get(key)
            if isinstance(value, str):
                values.append(value)
            elif isinstance(value, Mapping):
                values.extend(str(item) for item in value.values() if str(item).strip())
            elif isinstance(value, (list, tuple, set)):
                for item in value:
                    if isinstance(item, Mapping):
                        values.extend(str(subvalue) for subvalue in item.values() if str(subvalue).strip())
                    elif str(item or "").strip():
                        values.append(str(item or ""))
    return _unique_strings(values)


def _review_issuer_coverage_gaps(gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reviews: list[dict[str, Any]] = []
    seen: set[str] = set()
    for gap in gaps:
        if not _is_issuer_official_probe_gap(gap):
            continue
        ticker = str(gap.get("ticker") or gap.get("issuer") or "UNKNOWN").strip().upper()
        key = ticker or str(gap.get("gap_id") or _digest(gap)[:10])
        if key in seen:
            continue
        seen.add(key)
        reviews.append(
            {
                "review_id": f"issuer_coverage:{key.lower()}",
                "ticker": ticker,
                "dimension": str(gap.get("analysis_dimension") or gap.get("dimension") or "fundamentals"),
                "status": "retrievable_gap",
                "gap_ids": [str(gap.get("gap_id") or gap.get("id") or "")],
                "reason": str(gap.get("reason") or gap.get("reason_code") or "issuer outside local structured route scope"),
                "source_probe_order": list(gap.get("official_probe_order") or OFFICIAL_ISSUER_SOURCE_PROBE_ORDER),
                "official_source_classes": list(OFFICIAL_ISSUER_SOURCE_CLASSES),
                "allowed_web_scope_policy": "company_ir_local_exchange_regulator_sec_fpi_only",
                "expected_boundary_if_not_found": "bounded_gap_after_official_issuer_source_probe",
                "promotion_gate": "official_origin_parser_period_unit_citation_source_boundary_gate",
            }
        )
    return reviews


def _build_lead_memo_directive(
    *,
    objective_contract: Mapping[str, Any],
    dimension_reviews: list[dict[str, Any]],
    issuer_reviews: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
) -> dict[str, Any]:
    statuses = _status_counts(dimension_reviews)
    supported_count = int(statuses.get("sufficient") or 0)
    retrievable_count = int(statuses.get("retrievable_gap") or 0)
    bounded_count = int(statuses.get("bounded_gap") or 0) + int(statuses.get("commercial_gap") or 0)
    total_count = max(1, len(dimension_reviews))
    answerable = supported_count >= max(1, min(2, total_count))
    product_review = next(
        (row for row in dimension_reviews if str(row.get("dimension") or "").startswith("product")),
        {},
    )
    directive = {
        "schema_version": "finsight_lead_memo_directive_v0_1",
        "memo_stance": "bounded_analyst_judgment" if answerable else "evidence_gap_diagnostic",
        "core_question": str(objective_contract.get("core_question") or ""),
        "objective_satisfaction": {
            "core_question_answerable": answerable,
            "supported_dimension_count": supported_count,
            "retrievable_gap_dimension_count": retrievable_count,
            "bounded_or_commercial_gap_dimension_count": bounded_count,
        },
        "writer_role": "expression_and_synthesis_only_no_new_fact_tools",
        "opening_policy": "lead_with_answer_and_business_mechanism_not_gap_ledger",
        "gap_budget_policy": {
            "max_gap_share_in_user_memo": 0.25,
            "allowed_gap_placement": "short_actionable_gap_section_only",
            "forbidden_style": "do_not_repeat_unanswerable_or_current_data_insufficient_after_each_claim",
        },
        "product_output_contract": {
            "required_user_facing_shape": [
                "product_or_platform_taxonomy",
                "company_disclosed_product_kpi_when_available",
                "product_spec_or_parameter_context_when_available",
                "production_capacity_backlog_or_order_context_when_available",
                "peer_or_competitive_comparable_when_supported",
                "commercial_tracker_gap_only_after_public_official_sources_are_exhausted",
            ],
            "missing_source_boundary": "state precisely which public/official source was probed before exposing a product gap",
            "forbidden_fallback": "do_not_replace_product_sales_share_inventory_or_real_sell_through_with_generic_web_proxy",
        },
        "research_lead_review_policy": "lead_must_review_coverage_repair_and_direct_writer_before_memo_v0_1",
        "issuer_targeted_repair_required": bool(issuer_reviews),
        "issuer_targeted_repair_tickers": [str(row.get("ticker") or "") for row in issuer_reviews if str(row.get("ticker") or "")],
        "dimension_write_priorities": [
            {
                "dimension": str(row.get("dimension") or ""),
                "status": str(row.get("status") or ""),
                "write_role": _dimension_write_role(row),
            }
            for row in dimension_reviews
        ],
        "product_dimension_status": str(product_review.get("status") or ""),
        "source_authority_write_policy": _source_authority_write_policy(dimension_reviews),
        "gap_count": len(gaps),
    }
    return directive


def _dimension_write_role(row: Mapping[str, Any]) -> str:
    status = str(row.get("status") or "")
    if status == "sufficient":
        return "support_core_thesis_with_mechanism_and_financial_bridge"
    if status == "retrievable_gap":
        return "lead_targeted_repair_before_writer_then_write_only_if_repaired_else_short_gap"
    if status == "commercial_gap":
        return "commercial_boundary_only_no_proxy_promotion"
    if status == "bounded_gap":
        return "short_source_boundary_or_counterevidence_not_main_body"
    return "omit_unless_material"


def _source_authority_write_policy(dimension_reviews: list[Mapping[str, Any]]) -> dict[str, Any]:
    exact_dimensions: list[str] = []
    thesis_driver_dimensions: list[str] = []
    repair_first_dimensions: list[str] = []
    boundary_dimensions: list[str] = []
    for row in dimension_reviews:
        dimension = str(row.get("dimension") or "")
        coverage = row.get("source_authority_coverage") if isinstance(row.get("source_authority_coverage"), Mapping) else {}
        if not dimension:
            continue
        if int(coverage.get("exact_company_fact_authority_count") or 0) > 0:
            exact_dimensions.append(dimension)
        if int(coverage.get("thesis_driver_authority_count") or 0) > 0:
            thesis_driver_dimensions.append(dimension)
        if str(row.get("status") or "") == "retrievable_gap" and int(coverage.get("evidence_bundle_allowed_count") or 0) > 0:
            repair_first_dimensions.append(dimension)
        if int(coverage.get("attempt_backed_public_boundary_count") or 0) > 0 and int(coverage.get("evidence_bundle_allowed_count") or 0) == 0:
            boundary_dimensions.append(dimension)
    return {
        "exact_fact_dimensions": exact_dimensions,
        "thesis_driver_dimensions": thesis_driver_dimensions,
        "repair_first_dimensions": repair_first_dimensions,
        "boundary_only_dimensions": boundary_dimensions,
        "writer_rule": (
            "Use exact dimensions as numeric anchors and thesis-driver dimensions as mechanism evidence; "
            "do not render internal authority field names or turn boundary-only dimensions into repeated caveats."
        ),
    }


def _is_issuer_official_probe_gap(gap: Mapping[str, Any]) -> bool:
    text = json.dumps(gap, ensure_ascii=False, sort_keys=True, default=str).lower()
    if str(gap.get("gap_type") or "") == "issuer_official_source_probe_required":
        return True
    return any(
        marker in text
        for marker in (
            "not_in_manifest",
            "mcp route scope",
            "route_scope",
            "sec/mcp",
            "foreign issuer",
            "non_us",
            "issuer coverage",
            "20-f",
            "6-k",
        )
    )


def _status_counts(items: list[Mapping[str, Any]]) -> dict[str, int]:
    counts = {status: 0 for status in sorted(DIMENSION_STATUSES)}
    for item in items:
        status = str(item.get("status") or "")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()
