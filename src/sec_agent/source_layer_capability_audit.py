from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


SOURCE_LAYER_CAPABILITY_AUDIT_SCHEMA_VERSION = "finsight_source_layer_capability_audit_v0_1"


LAYER_DEFINITIONS: dict[str, dict[str, str]] = {
    "L1": {
        "label": "strong_fact_authority",
        "memo_usage": "can_support_precise_facts_after_parser_period_unit_citation_gate",
    },
    "L2": {
        "label": "trusted_context_supplement",
        "memo_usage": "can_support_context_proxy_relationship_or_regulatory_background_with_boundary",
    },
    "L3": {
        "label": "market_proxy_signal",
        "memo_usage": "can_support_directional_market_or_channel_signal_not_company_exact_fact",
    },
    "L4": {
        "label": "weak_signal_or_exclusion",
        "memo_usage": "discovery_or_exclusion_only_not_core_thesis_evidence",
    },
}


@dataclass(frozen=True)
class ExpectedSourceProfile:
    source_id: str
    provider: str
    layer_id: str
    claim_scope: str
    source_families: tuple[str, ...]
    expected_use: str
    specialist_slots: tuple[str, ...]
    required_before_runtime: tuple[str, ...]


EXPECTED_SOURCE_PROFILES: tuple[ExpectedSourceProfile, ...] = (
    ExpectedSourceProfile(
        "mainstream_financial_news",
        "major financial/news publishers",
        "L2",
        "event_context_and_management_external_validation",
        ("external_event_lead", "trusted_news_context"),
        "Verify material events, management statements, supplier/customer announcements, and regulatory context.",
        ("industry_supply_chain", "market_valuation", "risk_counterevidence"),
        ("domain allowlist", "publisher/source policy", "article snapshot parser", "citation/date gate"),
    ),
    ExpectedSourceProfile(
        "industry_association_reports",
        "industry associations",
        "L2",
        "industry_context_and_market_structure",
        ("industry_snapshot", "trusted_industry_context"),
        "Support industry cycle, demand proxy, channel structure, or competitive context.",
        ("industry_supply_chain", "market_valuation", "product_technology"),
        ("source allowlist", "document parser", "series/table schema", "context-only boundary"),
    ),
    ExpectedSourceProfile(
        "supplier_customer_official_news",
        "supplier/customer official sites",
        "L2",
        "relationship_and_demand_context",
        ("relationship_edge", "official_supply_chain_context"),
        "Support relationship existence, supply-chain mechanism, or official order context when source states it.",
        ("industry_supply_chain", "product_technology", "risk_counterevidence"),
        ("issuer/domain resolver", "official page snapshot", "relationship parser", "no volume promotion gate"),
    ),
    ExpectedSourceProfile(
        "ecommerce_major_platforms",
        "major ecommerce platforms",
        "L3",
        "price_availability_channel_proxy",
        ("channel_offer", "public_market_proxy"),
        "Support price band, configuration, availability, promotion, and channel signal.",
        ("product_technology", "market_valuation"),
        ("platform allowlist", "product/entity resolver", "snapshot parser", "no sales/share/ASP promotion gate"),
    ),
    ExpectedSourceProfile(
        "app_store_rankings",
        "Apple/Google app stores",
        "L3",
        "app_rank_download_or_review_proxy",
        ("public_market_proxy", "developer_ecosystem_signal"),
        "Support adoption direction and competitive app positioning, not revenue or company share.",
        ("product_technology", "market_valuation"),
        ("store allowlist", "app-to-issuer resolver", "rank/review parser", "proxy-only boundary"),
    ),
    ExpectedSourceProfile(
        "developer_ecosystem_github_npm_pypi_huggingface",
        "GitHub/npm/PyPI/HuggingFace",
        "L3",
        "developer_adoption_proxy",
        ("developer_ecosystem_signal", "public_market_proxy"),
        "Support developer adoption, package activity, model/repo ecosystem, or technical interest.",
        ("product_technology", "industry_supply_chain"),
        ("project-to-issuer resolver", "activity metric parser", "proxy-only boundary"),
    ),
    ExpectedSourceProfile(
        "public_tenders_contracts_orders",
        "public procurement/tender portals",
        "L3",
        "public_contract_or_tender_proxy",
        ("public_order_lead", "public_market_proxy"),
        "Support public buyer lead, tender/order existence, and demand proxy with issuer/product matching.",
        ("industry_supply_chain", "product_technology", "capital_macro"),
        ("jurisdiction portal parser", "buyer/supplier resolver", "award/status parser", "no total-sales promotion gate"),
    ),
    ExpectedSourceProfile(
        "job_postings_hiring_signals",
        "company and major job boards",
        "L3",
        "hiring_or_capacity_proxy",
        ("public_market_proxy", "external_event_lead"),
        "Support capacity buildout, product hiring, geography, or strategic emphasis as weak directional signal.",
        ("industry_supply_chain", "product_technology", "risk_counterevidence"),
        ("company/job-board allowlist", "role taxonomy parser", "proxy-only boundary"),
    ),
    ExpectedSourceProfile(
        "channel_pricing_quotations",
        "public distributors/resellers",
        "L3",
        "channel_price_availability_proxy",
        ("channel_offer", "public_market_proxy"),
        "Support channel configuration, pricing band, availability, and lead-time context.",
        ("product_technology", "market_valuation"),
        ("reseller allowlist", "SKU/product resolver", "snapshot parser", "no ASP/inventory promotion gate"),
    ),
    ExpectedSourceProfile(
        "platform_reviews_rankings_downloads",
        "platform review/ranking pages",
        "L3",
        "review_rank_or_download_proxy",
        ("public_market_proxy",),
        "Support direction of consumer/developer attention only when source and timing are explicit.",
        ("product_technology", "market_valuation", "risk_counterevidence"),
        ("platform allowlist", "entity/product resolver", "time snapshot parser", "proxy-only boundary"),
    ),
    ExpectedSourceProfile(
        "official_social_accounts",
        "verified official social accounts",
        "L2",
        "official_statement_or_event_context",
        ("official_event_context", "external_event_lead"),
        "Support official launch/event statements, not operating metrics unless cross-verified.",
        ("product_technology", "risk_counterevidence", "industry_supply_chain"),
        ("verified account allowlist", "snapshot archive", "source boundary", "cross-verification for facts"),
    ),
    ExpectedSourceProfile(
        "sec_offering_filing_metadata",
        "SEC submissions metadata",
        "L1",
        "securities_offering_or_registration_filing_event_context",
        ("primary_sec_filing", "capital_market_event"),
        "Support offering/registration filing-event existence and timing only; not offering amount or security terms.",
        ("capital_macro", "market_valuation", "risk_counterevidence"),
        ("SEC submissions JSON", "issuer CIK/ticker resolver", "form/accession/date parser", "no amount/terms promotion gate"),
    ),
    ExpectedSourceProfile(
        "sec_form_3_4_5_metadata",
        "SEC submissions metadata",
        "L1",
        "insider_transaction_filing_event_context",
        ("primary_sec_filing", "ownership_event"),
        "Support Form 3/4/5/144 filing-event existence and timing only; not transaction shares or price.",
        ("capital_macro", "market_valuation", "risk_counterevidence"),
        ("SEC submissions JSON", "issuer CIK/ticker resolver", "form/accession/date parser", "XML parser for amounts before exact claims"),
    ),
    ExpectedSourceProfile(
        "sec_schedule_13d_13g_metadata",
        "SEC submissions metadata",
        "L1",
        "beneficial_ownership_filing_event_context",
        ("primary_sec_filing", "ownership_event"),
        "Support Schedule 13D/13G filing-event existence and timing only; not ownership percentage or activist thesis.",
        ("capital_macro", "market_valuation", "risk_counterevidence"),
        ("SEC submissions JSON", "issuer CIK/ticker resolver", "form/accession/date parser", "schedule parser for ownership percent before exact claims"),
    ),
    ExpectedSourceProfile(
        "sec_proxy_governance_metadata",
        "SEC submissions metadata",
        "L1",
        "proxy_governance_filing_event_context",
        ("primary_sec_filing", "governance_event"),
        "Support proxy/governance filing-event existence and timing only; not buyback amount, compensation result, or vote result.",
        ("capital_macro", "market_valuation", "risk_counterevidence"),
        ("SEC submissions JSON", "issuer CIK/ticker resolver", "form/accession/date parser", "proxy table/text parser before exact claims"),
    ),
    ExpectedSourceProfile(
        "unverified_self_media_forums",
        "unverified social/self-media/forums",
        "L4",
        "discovery_only_or_exclusion",
        ("external_event_lead",),
        "Discovery lead only; use to formulate search, not to support thesis.",
        ("risk_counterevidence",),
        ("source quality classifier", "official corroboration required", "not-core-evidence gate"),
    ),
)


RUNTIME_CONNECTED_EXPECTED_PROFILES: dict[str, dict[str, Any]] = {
    "mainstream_financial_news": {
        "information_strength_tier": "S2_trusted_news_context",
        "acquisition_status": "scoped_url_fetch_gate_available",
        "crawler_status": "trusted_domain_fetch_gate_available",
        "parser_status": "article_parser_smoke_pass",
        "structured_fact_status": "context_rows_ready",
        "evidence_graph_status": "runtime_ready_context",
        "blocking_reason": "",
        "next_action": "expand publisher coverage, entity/event matching, page variants, and persistent backfill",
        "required_before_runtime": ["entity/event resolver", "publisher page-variant coverage", "persistent evidence graph backfill"],
        "audit_status": "runtime_parser_smoke_pass",
        "availability_decision": "runtime_context_route_available_after_domain_gate",
        "materialization_status": "runtime_context_route_available",
        "runtime_promotion_status": "runtime_ready_context",
    },
    "supplier_customer_official_news": {
        "information_strength_tier": "S2_official_relationship_context",
        "acquisition_status": "scoped_url_fetch_gate_available",
        "crawler_status": "official_relationship_fetch_gate_available",
        "parser_status": "article_parser_smoke_pass",
        "structured_fact_status": "context_rows_ready",
        "evidence_graph_status": "runtime_ready_context",
        "blocking_reason": "",
        "next_action": "expand official domain resolver, counterparty matching, page variants, and persistent backfill",
        "required_before_runtime": ["issuer/counterparty resolver", "official page-variant coverage", "persistent evidence graph backfill"],
        "audit_status": "runtime_parser_smoke_pass",
        "availability_decision": "runtime_context_route_available_after_source_class_gate",
        "materialization_status": "runtime_context_route_available",
        "runtime_promotion_status": "runtime_ready_context",
    },
    "app_store_rankings": {
        "information_strength_tier": "S3_app_marketplace_proxy_context",
        "acquisition_status": "app_store_lookup_api_materialized",
        "crawler_status": "itunes_lookup_api_fetch_pass",
        "parser_status": "app_store_lookup_parser_pass",
        "structured_fact_status": "app_marketplace_context_rows_ready",
        "evidence_graph_status": "runtime_ready_context",
        "blocking_reason": "",
        "next_action": "expand app-to-issuer resolver coverage, add Google Play/major marketplace policy where legally accessible, and keep download/revenue claims blocked",
        "required_before_runtime": ["store allowlist", "app-to-issuer resolver", "lookup/listing parser", "proxy-only boundary"],
        "audit_status": "runtime_parser_smoke_pass",
        "availability_decision": "runtime_context_route_available_after_app_marketplace_gate",
        "materialization_status": "app_marketplace_context_materialized",
        "runtime_promotion_status": "runtime_ready_context",
    },
    "developer_ecosystem_github_npm_pypi_huggingface": {
        "information_strength_tier": "S3_developer_ecosystem_proxy_context",
        "acquisition_status": "developer_api_fetch_materialized",
        "crawler_status": "github_npm_pypi_huggingface_api_fetch_pass",
        "parser_status": "developer_ecosystem_parser_pass",
        "structured_fact_status": "developer_ecosystem_context_rows_ready",
        "evidence_graph_status": "runtime_ready_context",
        "blocking_reason": "",
        "next_action": "expand issuer/project resolver coverage, refresh cadence, and source-boundary regression cases",
        "required_before_runtime": ["issuer/project resolver", "activity metric parser", "proxy-only boundary"],
        "audit_status": "runtime_parser_smoke_pass",
        "availability_decision": "runtime_context_route_available_after_developer_source_gate",
        "materialization_status": "developer_ecosystem_context_materialized",
        "runtime_promotion_status": "runtime_ready_context",
    },
    "job_postings_hiring_signals": {
        "information_strength_tier": "S3_hiring_capacity_proxy_context",
        "acquisition_status": "official_ats_api_materialized",
        "crawler_status": "greenhouse_lever_public_api_fetch_pass",
        "parser_status": "ats_jobposting_jsonld_parser_pass",
        "structured_fact_status": "hiring_capacity_context_rows_ready",
        "evidence_graph_status": "runtime_ready_context",
        "blocking_reason": "",
        "next_action": "expand company ATS resolver coverage, role taxonomy mapping, refresh cadence, and no-headcount-demand-promotion tests",
        "required_before_runtime": ["company/job-board allowlist", "ATS API resolver", "role taxonomy parser", "proxy-only boundary"],
        "audit_status": "runtime_parser_smoke_pass",
        "availability_decision": "runtime_context_route_available_after_hiring_source_gate",
        "materialization_status": "hiring_capacity_context_materialized",
        "runtime_promotion_status": "runtime_ready_context",
    },
    "public_tenders_contracts_orders": {
        "information_strength_tier": "S3_public_contract_award_proxy_context",
        "acquisition_status": "public_award_api_materialized",
        "crawler_status": "usaspending_contract_award_api_fetch_pass",
        "parser_status": "usaspending_award_jsonld_parser_pass",
        "structured_fact_status": "public_contract_award_context_rows_ready",
        "evidence_graph_status": "runtime_ready_context",
        "blocking_reason": "",
        "next_action": "expand jurisdiction/source coverage beyond USAspending, buyer/supplier resolver coverage, and no-backlog-revenue-promotion tests",
        "required_before_runtime": ["jurisdiction portal parser", "buyer/supplier resolver", "award/status parser", "no total-sales promotion gate"],
        "audit_status": "runtime_parser_smoke_pass",
        "availability_decision": "runtime_context_route_available_after_public_contract_source_gate",
        "materialization_status": "public_contract_award_context_materialized",
        "runtime_promotion_status": "runtime_ready_context",
    },
    "channel_pricing_quotations": {
        "information_strength_tier": "S3_channel_price_availability_proxy_context",
        "acquisition_status": "public_reseller_page_materialized",
        "crawler_status": "cdw_search_and_product_page_fetch_pass",
        "parser_status": "cdw_offer_microdata_parser_pass",
        "structured_fact_status": "channel_offer_context_rows_ready",
        "evidence_graph_status": "runtime_ready_context",
        "blocking_reason": "",
        "next_action": "expand reseller/domain coverage beyond CDW and keep ASP, sell-through, inventory, sales, and share claims blocked",
        "required_before_runtime": ["reseller allowlist", "SKU/product resolver", "snapshot parser", "no ASP/inventory promotion gate"],
        "audit_status": "runtime_parser_smoke_pass",
        "availability_decision": "runtime_context_route_available_after_channel_offer_gate",
        "materialization_status": "channel_offer_context_materialized",
        "runtime_promotion_status": "runtime_ready_context",
    },
    "platform_reviews_rankings_downloads": {
        "information_strength_tier": "S3_platform_review_proxy_context",
        "acquisition_status": "public_reseller_review_metadata_materialized",
        "crawler_status": "cdw_product_page_review_metadata_fetch_pass",
        "parser_status": "cdw_review_microdata_parser_pass",
        "structured_fact_status": "platform_review_context_rows_ready",
        "evidence_graph_status": "runtime_ready_context",
        "blocking_reason": "",
        "next_action": "expand platform coverage, add timestamped ranking snapshots where available, and keep sales/revenue/share claims blocked",
        "required_before_runtime": ["platform allowlist", "entity/product resolver", "time snapshot parser", "proxy-only boundary"],
        "audit_status": "runtime_parser_smoke_pass",
        "availability_decision": "runtime_context_route_available_after_platform_review_gate",
        "materialization_status": "platform_review_context_materialized",
        "runtime_promotion_status": "runtime_ready_context",
    },
    "sec_offering_filing_metadata": {
        "information_strength_tier": "S1_sec_filing_event_context",
        "acquisition_status": "sec_submissions_metadata_materialized",
        "crawler_status": "local_sec_submissions_json_available",
        "parser_status": "sec_offering_filing_event_metadata_parser_pass",
        "structured_fact_status": "capital_market_event_context_rows_ready",
        "evidence_graph_status": "runtime_ready_context",
        "blocking_reason": "",
        "next_action": "add filing text/XML parser before promoting offering amounts, security terms, dilution, coupon, maturity, or proceeds",
        "required_before_runtime": ["SEC submissions JSON", "issuer resolver", "form/accession/date parser", "no amount/terms promotion gate"],
        "audit_status": "runtime_parser_smoke_pass",
        "availability_decision": "runtime_context_route_available_after_sec_submissions_gate",
        "materialization_status": "sec_capital_market_event_context_materialized",
        "runtime_promotion_status": "runtime_ready_context",
    },
    "sec_form_3_4_5_metadata": {
        "information_strength_tier": "S1_sec_filing_event_context",
        "acquisition_status": "sec_submissions_metadata_materialized",
        "crawler_status": "local_sec_submissions_json_available",
        "parser_status": "sec_insider_filing_event_metadata_parser_pass",
        "structured_fact_status": "capital_market_event_context_rows_ready",
        "evidence_graph_status": "runtime_ready_context",
        "blocking_reason": "",
        "next_action": "add Form 3/4/5/144 XML parser before promoting shares, prices, ownership change, or management intent",
        "required_before_runtime": ["SEC submissions JSON", "issuer resolver", "form/accession/date parser", "XML parser for exact fields"],
        "audit_status": "runtime_parser_smoke_pass",
        "availability_decision": "runtime_context_route_available_after_sec_submissions_gate",
        "materialization_status": "sec_capital_market_event_context_materialized",
        "runtime_promotion_status": "runtime_ready_context",
    },
    "sec_schedule_13d_13g_metadata": {
        "information_strength_tier": "S1_sec_filing_event_context",
        "acquisition_status": "sec_submissions_metadata_materialized",
        "crawler_status": "local_sec_submissions_json_available",
        "parser_status": "sec_beneficial_ownership_filing_event_metadata_parser_pass",
        "structured_fact_status": "capital_market_event_context_rows_ready",
        "evidence_graph_status": "runtime_ready_context",
        "blocking_reason": "",
        "next_action": "add Schedule 13D/13G parser before promoting ownership percentage, holder intent, or activist thesis",
        "required_before_runtime": ["SEC submissions JSON", "issuer resolver", "form/accession/date parser", "schedule parser for exact fields"],
        "audit_status": "runtime_parser_smoke_pass",
        "availability_decision": "runtime_context_route_available_after_sec_submissions_gate",
        "materialization_status": "sec_capital_market_event_context_materialized",
        "runtime_promotion_status": "runtime_ready_context",
    },
    "sec_proxy_governance_metadata": {
        "information_strength_tier": "S1_sec_filing_event_context",
        "acquisition_status": "sec_submissions_metadata_materialized",
        "crawler_status": "local_sec_submissions_json_available",
        "parser_status": "sec_proxy_governance_filing_event_metadata_parser_pass",
        "structured_fact_status": "capital_market_event_context_rows_ready",
        "evidence_graph_status": "runtime_ready_context",
        "blocking_reason": "",
        "next_action": "add proxy text/table parser before promoting buyback amount, voting result, compensation result, or governance judgment",
        "required_before_runtime": ["SEC submissions JSON", "issuer resolver", "form/accession/date parser", "proxy parser for exact fields"],
        "audit_status": "runtime_parser_smoke_pass",
        "availability_decision": "runtime_context_route_available_after_sec_submissions_gate",
        "materialization_status": "sec_capital_market_event_context_materialized",
        "runtime_promotion_status": "runtime_ready_context",
    },
}


def build_source_layer_capability_audit(
    *,
    coverage_config_path: str | Path = "configs/data_sources/public_source_coverage_v0_1.yaml",
    availability_audit_path: str | Path = "data/manifests/public_source_full_availability_audit_v0_1.jsonl",
    materialization_matrix_path: str | Path = "data/manifests/public_source_strength_materialization_matrix_v0_1.jsonl",
    inventory_summary_path: str | Path = "data/manifests/public_source_inventory_adapter_summary_v0_1.json",
    generated_at: str | None = None,
) -> dict[str, Any]:
    coverage = _load_yaml(coverage_config_path)
    availability_rows = _load_jsonl(availability_audit_path)
    materialization_rows = _load_jsonl(materialization_matrix_path)
    inventory_summary = _load_json(inventory_summary_path)
    generated_at = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    coverage_by_source = {
        str(row.get("source_id") or ""): row
        for row in coverage.get("sources") or []
        if isinstance(row, Mapping) and str(row.get("source_id") or "").strip()
    }
    availability_by_source = {
        str(row.get("source_id") or ""): row
        for row in availability_rows
        if isinstance(row, Mapping) and str(row.get("source_id") or "").strip()
    }
    materialization_by_source = {
        str(row.get("source_id") or ""): row
        for row in materialization_rows
        if isinstance(row, Mapping) and str(row.get("source_id") or "").strip()
    }
    all_source_ids = sorted(set(coverage_by_source) | set(availability_by_source) | set(materialization_by_source))

    rows = [
        _build_row(
            source_id=source_id,
            coverage=coverage_by_source.get(source_id, {}),
            availability=availability_by_source.get(source_id, {}),
            materialization=materialization_by_source.get(source_id, {}),
            inventory_summary=inventory_summary,
            expected_profile=None,
            generated_at=generated_at,
        )
        for source_id in all_source_ids
    ]
    known_source_ids = {row["source_id"] for row in rows}
    for profile in EXPECTED_SOURCE_PROFILES:
        if profile.source_id in known_source_ids:
            continue
        rows.append(
            _build_expected_missing_row(
                profile,
                generated_at=generated_at,
            )
        )

    summary = _summary(rows, inputs={
        "coverage_config": str(coverage_config_path),
        "availability_audit": str(availability_audit_path),
        "materialization_matrix": str(materialization_matrix_path),
        "inventory_summary": str(inventory_summary_path),
    })
    payload = {
        "schema_version": SOURCE_LAYER_CAPABILITY_AUDIT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "policy": "normal_trusted_sources_enter_evidence_graph_as_bounded_context_or_proxy_never_exact_without_parser_gate_v0_1",
        "layer_definitions": LAYER_DEFINITIONS,
        "rows": rows,
        "summary": summary,
        "validation": validate_source_layer_capability_audit(rows),
    }
    return payload


def write_source_layer_capability_audit(
    payload: Mapping[str, Any],
    *,
    output_rows_path: str | Path = "data/manifests/source_layer_capability_audit_v0_1.jsonl",
    output_summary_path: str | Path = "data/manifests/source_layer_capability_audit_summary_v0_1.json",
    output_report_path: str | Path = "docs/internal/vnext_20260610/source_layer_capability_audit.zh-CN.md",
) -> dict[str, str]:
    rows_path = Path(output_rows_path)
    summary_path = Path(output_summary_path)
    report_path = Path(output_report_path)
    rows_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [row for row in payload.get("rows") or [] if isinstance(row, Mapping)]
    rows_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    summary_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"rows"}
    }
    summary_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(render_source_layer_capability_report(payload), encoding="utf-8")
    return {
        "rows": str(rows_path),
        "summary": str(summary_path),
        "report": str(report_path),
    }


def validate_source_layer_capability_audit(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        source_id = str(row.get("source_id") or "").strip()
        if not source_id:
            errors.append({"type": "source_id_required"})
            continue
        if source_id in seen:
            errors.append({"type": "duplicate_source_id", "source_id": source_id})
        seen.add(source_id)
        layer_id = str(row.get("layer_id") or "")
        if layer_id not in LAYER_DEFINITIONS:
            errors.append({"type": "invalid_layer_id", "source_id": source_id, "layer_id": layer_id})
        if not str(row.get("evidence_graph_status") or "").strip():
            errors.append({"type": "evidence_graph_status_required", "source_id": source_id})
        if row.get("context_or_proxy_allowed") is True and not str(row.get("memo_usage") or "").strip():
            warnings.append({"type": "context_source_without_memo_usage", "source_id": source_id})
        if row.get("exact_value_authority_ready") is True and row.get("parser_gate_passed") is not True:
            errors.append({"type": "exact_authority_without_parser_gate", "source_id": source_id})
        if layer_id in {"L2", "L3", "L4"} and row.get("can_support_company_exact_fact") is True:
            errors.append({"type": "non_l1_company_exact_fact_authority", "source_id": source_id, "layer_id": layer_id})
    return {
        "schema_version": "finsight_source_layer_capability_audit_validation_v0_1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
    }


def render_source_layer_capability_report(payload: Mapping[str, Any]) -> str:
    rows = [dict(row) for row in payload.get("rows") or [] if isinstance(row, Mapping)]
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    lines = [
        "# Source Layer Capability Audit",
        "",
        f"- Generated at: `{payload.get('generated_at', '')}`",
        f"- Status: `{(payload.get('validation') or {}).get('status', '') if isinstance(payload.get('validation'), Mapping) else ''}`",
        f"- Source rows: `{len(rows)}`",
        f"- Runtime-ready rows: `{summary.get('runtime_ready_count', 0)}`",
        f"- Expected-but-missing rows: `{summary.get('expected_missing_count', 0)}`",
        "",
        "## Layer Summary",
        "",
        "| Layer | Count | Runtime ready | Parser gate pending | Missing route |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    by_layer = summary.get("by_layer") if isinstance(summary.get("by_layer"), Mapping) else {}
    for layer_id in sorted(LAYER_DEFINITIONS):
        layer = by_layer.get(layer_id) if isinstance(by_layer.get(layer_id), Mapping) else {}
        lines.append(
            f"| {layer_id} {LAYER_DEFINITIONS[layer_id]['label']} | {layer.get('count', 0)} | "
            f"{layer.get('runtime_ready_count', 0)} | {layer.get('parser_gate_pending_count', 0)} | "
            f"{layer.get('missing_route_count', 0)} |"
        )
    lines.extend(
        [
            "",
            "## High Priority Gaps",
            "",
            "| Source | Layer | Evidence graph status | Blocking reason | Next action |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    high_priority = [
        row
        for row in rows
        if str(row.get("priority") or "").startswith("P1")
        or str(row.get("layer_id") or "") in {"L2", "L3"}
        and str(row.get("evidence_graph_status") or "") in {"not_registered", "missing_runtime_route", "staging_parser_gate_pending"}
    ]
    for row in high_priority[:40]:
        lines.append(
            f"| `{row.get('source_id', '')}` | {row.get('layer_id', '')} | "
            f"{row.get('evidence_graph_status', '')} | {row.get('blocking_reason', '')} | {row.get('next_action', '')} |"
        )
    lines.extend(
        [
            "",
            "## Runtime Use Rule",
            "",
            "- L1 rows can become exact facts only after parser, citation, period, unit, and authority gates.",
            "- L2 rows should enter as trusted context/proxy when source and parser gates pass; they do not prove company sales, margin, share, or product revenue unless the source itself is company-disclosed and exact gates pass.",
            "- L3 rows should enter as directional market/channel/developer signals; they cannot prove company exact facts.",
            "- L4 rows are discovery/exclusion only and should not support core thesis.",
            "",
        ]
    )
    return "\n".join(lines)


def _build_row(
    *,
    source_id: str,
    coverage: Mapping[str, Any],
    availability: Mapping[str, Any],
    materialization: Mapping[str, Any],
    inventory_summary: Mapping[str, Any],
    expected_profile: ExpectedSourceProfile | None,
    generated_at: str,
) -> dict[str, Any]:
    claim_scope = _first_nonempty(coverage.get("claim_scope"), availability.get("claim_scope"), expected_profile.claim_scope if expected_profile else "")
    source_families = _string_list(
        coverage.get("source_families")
        or availability.get("source_families")
        or (expected_profile.source_families if expected_profile else ())
    )
    tier = str(materialization.get("information_strength_tier") or _tier_from_claim_scope(claim_scope) or "")
    layer_id = _layer_for_source(source_id=source_id, tier=tier, claim_scope=claim_scope, source_families=source_families)
    acquisition_status = _acquisition_status(coverage=coverage, availability=availability, materialization=materialization)
    parser_gate_passed = _parser_gate_passed(coverage=coverage, availability=availability, materialization=materialization)
    parser_status = _parser_status(coverage=coverage, availability=availability, materialization=materialization)
    structured_fact_status = _structured_fact_status(materialization=materialization, availability=availability)
    evidence_graph_status = _evidence_graph_status(
        source_id=source_id,
        layer_id=layer_id,
        coverage=coverage,
        availability=availability,
        materialization=materialization,
        inventory_summary=inventory_summary,
        parser_gate_passed=parser_gate_passed,
    )
    exact_ready = layer_id == "L1" and parser_gate_passed and structured_fact_status in {"structured_fact_ready", "exact_ledger_ready"}
    context_allowed = layer_id in {"L1", "L2", "L3"} and evidence_graph_status not in {"not_registered", "blocked_by_auth_or_policy"}
    return {
        "schema_version": SOURCE_LAYER_CAPABILITY_AUDIT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "source_id": source_id,
        "provider": _first_nonempty(coverage.get("provider"), availability.get("provider"), expected_profile.provider if expected_profile else ""),
        "priority": _first_nonempty(coverage.get("priority"), availability.get("priority")),
        "layer_id": layer_id,
        "layer_label": LAYER_DEFINITIONS[layer_id]["label"],
        "information_strength_tier": tier,
        "source_families": source_families,
        "claim_scope": claim_scope,
        "claim_boundary": _first_nonempty(coverage.get("boundary_notes"), availability.get("claim_boundary")),
        "allowed_claim_scopes": _allowed_claim_scopes(layer_id=layer_id, claim_scope=claim_scope),
        "forbidden_claim_scopes": _forbidden_claim_scopes(layer_id=layer_id),
        "acquisition_status": acquisition_status,
        "crawler_status": _crawler_status(coverage=coverage, availability=availability, materialization=materialization),
        "can_crawl_or_download": acquisition_status in {"live_probe_pass", "materialized_downloaded", "collector_implemented", "structured_api_available"},
        "parser_status": parser_status,
        "parser_gate_passed": parser_gate_passed,
        "can_parse": parser_status in {"parser_gate_passed", "field_parser_pass", "partial_parser_or_clean_text_available"},
        "structured_fact_status": structured_fact_status,
        "can_structure": structured_fact_status in {"structured_fact_ready", "context_rows_ready", "candidate_rows_ready", "exact_ledger_ready"},
        "evidence_graph_status": evidence_graph_status,
        "runtime_ready_context": evidence_graph_status in {"runtime_ready_context", "exact_authority_ready"},
        "exact_value_authority_ready": exact_ready,
        "context_or_proxy_allowed": context_allowed,
        "can_support_company_exact_fact": exact_ready,
        "specialist_slots": _specialist_slots(source_id=source_id, claim_scope=claim_scope, source_families=source_families, expected_profile=expected_profile),
        "memo_usage": _memo_usage(layer_id=layer_id, evidence_graph_status=evidence_graph_status),
        "blocking_reason": _blocking_reason(
            coverage=coverage,
            availability=availability,
            materialization=materialization,
            evidence_graph_status=evidence_graph_status,
        ),
        "next_action": _next_action(coverage=coverage, availability=availability, materialization=materialization, expected_profile=expected_profile),
        "required_before_runtime": _string_list(
            availability.get("required_before_agent_use")
            or coverage.get("required_before_agent_use")
            or (expected_profile.required_before_runtime if expected_profile else ())
        ),
        "audit_status": str(availability.get("audit_status") or ""),
        "availability_decision": str(availability.get("availability_decision") or ""),
        "materialization_status": str(materialization.get("materialization_status") or ""),
        "runtime_promotion_status": str(materialization.get("runtime_promotion_status") or ""),
    }


def _build_expected_missing_row(profile: ExpectedSourceProfile, *, generated_at: str) -> dict[str, Any]:
    runtime_override = RUNTIME_CONNECTED_EXPECTED_PROFILES.get(profile.source_id)
    row = {
        "schema_version": SOURCE_LAYER_CAPABILITY_AUDIT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "source_id": profile.source_id,
        "provider": profile.provider,
        "priority": "P1_expected_proxy_or_context_source" if profile.layer_id in {"L2", "L3"} else "P2_discovery_boundary",
        "layer_id": profile.layer_id,
        "layer_label": LAYER_DEFINITIONS[profile.layer_id]["label"],
        "information_strength_tier": "expected_not_registered",
        "source_families": list(profile.source_families),
        "claim_scope": profile.claim_scope,
        "claim_boundary": profile.expected_use,
        "allowed_claim_scopes": _allowed_claim_scopes(layer_id=profile.layer_id, claim_scope=profile.claim_scope),
        "forbidden_claim_scopes": _forbidden_claim_scopes(layer_id=profile.layer_id),
        "acquisition_status": "not_connected",
        "crawler_status": "missing_runtime_route",
        "can_crawl_or_download": False,
        "parser_status": "not_registered",
        "parser_gate_passed": False,
        "can_parse": False,
        "structured_fact_status": "not_structured",
        "can_structure": False,
        "evidence_graph_status": "not_registered",
        "runtime_ready_context": False,
        "exact_value_authority_ready": False,
        "context_or_proxy_allowed": False,
        "can_support_company_exact_fact": False,
        "specialist_slots": list(profile.specialist_slots),
        "memo_usage": LAYER_DEFINITIONS[profile.layer_id]["memo_usage"],
        "blocking_reason": "expected_source_profile_not_registered_in_current_runtime",
        "next_action": "add source policy, acquisition route, parser contract, and source-boundary gate",
        "required_before_runtime": list(profile.required_before_runtime),
        "audit_status": "not_audited",
        "availability_decision": "not_registered",
        "materialization_status": "not_materialized",
        "runtime_promotion_status": "not_registered",
    }
    if runtime_override:
        row.update(runtime_override)
        row.update(
            {
                "can_crawl_or_download": True,
                "parser_gate_passed": True,
                "can_parse": True,
                "can_structure": True,
                "runtime_ready_context": True,
                "exact_value_authority_ready": False,
                "context_or_proxy_allowed": True,
                "can_support_company_exact_fact": False,
            }
        )
    return row


def _summary(rows: list[Mapping[str, Any]], *, inputs: Mapping[str, str]) -> dict[str, Any]:
    by_layer: dict[str, dict[str, int]] = {}
    for layer_id in LAYER_DEFINITIONS:
        layer_rows = [row for row in rows if row.get("layer_id") == layer_id]
        by_layer[layer_id] = {
            "count": len(layer_rows),
            "runtime_ready_count": sum(1 for row in layer_rows if row.get("runtime_ready_context")),
            "parser_gate_pending_count": sum(1 for row in layer_rows if str(row.get("evidence_graph_status")) == "staging_parser_gate_pending"),
            "missing_route_count": sum(1 for row in layer_rows if str(row.get("evidence_graph_status")) in {"not_registered", "missing_runtime_route"}),
        }
    return {
        "inputs": dict(inputs),
        "source_count": len(rows),
        "expected_missing_count": sum(1 for row in rows if str(row.get("evidence_graph_status")) == "not_registered"),
        "runtime_ready_count": sum(1 for row in rows if row.get("runtime_ready_context")),
        "exact_authority_ready_count": sum(1 for row in rows if row.get("exact_value_authority_ready")),
        "context_or_proxy_allowed_count": sum(1 for row in rows if row.get("context_or_proxy_allowed")),
        "by_layer": by_layer,
        "by_evidence_graph_status": dict(sorted(Counter(str(row.get("evidence_graph_status") or "unknown") for row in rows).items())),
        "by_acquisition_status": dict(sorted(Counter(str(row.get("acquisition_status") or "unknown") for row in rows).items())),
        "by_parser_status": dict(sorted(Counter(str(row.get("parser_status") or "unknown") for row in rows).items())),
    }


def _layer_for_source(*, source_id: str, tier: str, claim_scope: str, source_families: list[str]) -> str:
    text = " ".join([source_id, tier, claim_scope, *source_families]).lower()
    if any(token in text for token in ["ecommerce", "app_store", "github", "npm", "pypi", "huggingface", "job_posting", "channel_offer", "reviews_rankings", "public_contract", "tender"]):
        return "L3"
    if any(token in text for token in ["self_media", "forum", "unverified", "common_crawl", "discovery_only"]):
        return "L4"
    if "S5_" in tier or "S4_" in tier:
        if any(token in text for token in ["product_pages", "official_product_status", "official_social", "company official web"]):
            return "L2"
        return "L1"
    if "S3_" in tier or "S2_" in tier:
        return "L2"
    if "S1_" in tier:
        return "L3" if any(token in text for token in ["market", "developer", "technology", "event", "lead"]) else "L2"
    if "S0_" in tier:
        return "L4"
    if any(token in text for token in ["regulatory", "clinical", "fda", "nhtsa", "eia", "fred", "bls", "bea", "census", "fdic", "openalex", "patent", "gleif"]):
        return "L2"
    return "L2"


def _tier_from_claim_scope(claim_scope: str) -> str:
    value = claim_scope.lower()
    if "company_reported" in value or "primary_company" in value or "company_authored" in value:
        return "S5_primary_authority"
    if "regulatory" in value or "identifier" in value:
        return "S3_official_regulatory_product_context"
    if "macro" in value or "industry" in value:
        return "S2_official_macro_industry_context"
    if "discovery" in value:
        return "S0_deferred_or_unofficial"
    return "S1_resolver_or_lead"


def _acquisition_status(*, coverage: Mapping[str, Any], availability: Mapping[str, Any], materialization: Mapping[str, Any]) -> str:
    if materialization and _int(materialization.get("downloaded_document_row_count")) > 0:
        return "materialized_downloaded"
    if materialization and _int(materialization.get("extended_materialization_record_count")) > 0:
        return "structured_api_available"
    if str(availability.get("audit_status") or "") in {"live_pass", "live_pass_probe_only"}:
        return "live_probe_pass"
    collector = str(coverage.get("collector_status") or availability.get("collector_status") or "")
    if collector.startswith("implemented") or collector.startswith("partial"):
        return "collector_implemented"
    if str(coverage.get("auth_status") or availability.get("auth_status") or "") in {"commercial_deferred", "blocked_missing_credential"}:
        return "blocked_by_auth_or_policy"
    return "not_connected"


def _crawler_status(*, coverage: Mapping[str, Any], availability: Mapping[str, Any], materialization: Mapping[str, Any]) -> str:
    acquisition = _acquisition_status(coverage=coverage, availability=availability, materialization=materialization)
    if acquisition in {"materialized_downloaded", "structured_api_available", "live_probe_pass"}:
        return acquisition
    if acquisition == "collector_implemented":
        return "collector_exists_needs_runtime_route"
    return "missing_runtime_route"


def _parser_status(*, coverage: Mapping[str, Any], availability: Mapping[str, Any], materialization: Mapping[str, Any]) -> str:
    if _parser_gate_passed(coverage=coverage, availability=availability, materialization=materialization):
        return "parser_gate_passed"
    if str((availability.get("field_completeness") or {}).get("status") or "") == "pass":
        return "field_parser_pass"
    if _int(materialization.get("cleaned_text_row_count")) > 0 or _int(materialization.get("cleaned_text_char_count")) > 0:
        return "partial_parser_or_clean_text_available"
    parser = str(coverage.get("parser_status") or availability.get("parser_status") or materialization.get("next_gate") or "")
    if "pending" in parser or "required" in parser or "candidate" in parser:
        return "parser_gate_pending"
    if "blocked" in parser:
        return "parser_blocked"
    return "not_started"


def _parser_gate_passed(*, coverage: Mapping[str, Any], availability: Mapping[str, Any], materialization: Mapping[str, Any]) -> bool:
    parser_text = " ".join(
        [
            str(coverage.get("parser_status") or ""),
            str(availability.get("parser_status") or ""),
            str(materialization.get("runtime_promotion_status") or ""),
            str(materialization.get("materialization_status") or ""),
        ]
    ).lower()
    if "parser_gate_pending" in parser_text or "parser_required" in parser_text or "pending" in parser_text or "candidate" in parser_text:
        return False
    if any(token in parser_text for token in ["implemented_for_current_us_pipeline", "ledger", "exact"]):
        return True
    return _int(materialization.get("sec_structured_fact_row_count")) > 0 or _int(materialization.get("sec_annual_ledger_fact_count")) > 0


def _structured_fact_status(*, materialization: Mapping[str, Any], availability: Mapping[str, Any]) -> str:
    if _int(materialization.get("sec_annual_ledger_fact_count")) > 0:
        return "exact_ledger_ready"
    if _int(materialization.get("sec_structured_fact_row_count")) > 0:
        return "structured_fact_ready"
    if _int(materialization.get("inventory_runtime_row_count")) > 0 or _int(materialization.get("industry_snapshot_evidence_row_count")) > 0:
        return "context_rows_ready"
    if _int(materialization.get("normalized_snapshot_record_count")) > 0 or _int(materialization.get("extended_materialization_record_count")) > 0:
        return "candidate_rows_ready"
    if str((availability.get("field_completeness") or {}).get("status") or "") == "pass":
        return "normalized_probe_rows_ready"
    return "not_structured"


def _evidence_graph_status(
    *,
    source_id: str,
    layer_id: str,
    coverage: Mapping[str, Any],
    availability: Mapping[str, Any],
    materialization: Mapping[str, Any],
    inventory_summary: Mapping[str, Any],
    parser_gate_passed: bool,
) -> str:
    if not coverage and not availability and not materialization:
        return "not_registered"
    if str(availability.get("audit_status") or "") in {"not_audited_blocked", "not_audited_deferred"}:
        return "blocked_by_auth_or_policy"
    promoted_sources = set(_string_list(inventory_summary.get("promoted_sources")))
    bounded_sources = set(_string_list(inventory_summary.get("bounded_evidence_sources")))
    if source_id in promoted_sources or source_id in bounded_sources or _int(materialization.get("inventory_runtime_row_count")) > 0:
        return "runtime_ready_context"
    if parser_gate_passed and layer_id == "L1":
        return "exact_authority_ready"
    if _int(materialization.get("downloaded_document_row_count")) > 0 or _int(materialization.get("cleaned_text_row_count")) > 0:
        return "staging_parser_gate_pending"
    if _int(materialization.get("normalized_snapshot_record_count")) > 0 or _int(materialization.get("extended_materialization_record_count")) > 0:
        return "structured_not_promoted"
    if str(availability.get("audit_status") or "") in {"live_pass", "live_pass_probe_only"}:
        return "crawlable_not_parsed_or_not_routed"
    if str(coverage.get("collector_status") or availability.get("collector_status") or "").startswith(("implemented", "partial")):
        return "missing_runtime_route"
    return "not_connected"


def _allowed_claim_scopes(*, layer_id: str, claim_scope: str) -> list[str]:
    if layer_id == "L1":
        return [claim_scope or "company_or_official_fact_after_parser_gate", "management_commentary", "official_product_line"]
    if layer_id == "L2":
        return [claim_scope or "trusted_context", "industry_background", "regulatory_status", "relationship_context", "demand_proxy"]
    if layer_id == "L3":
        return [claim_scope or "market_proxy", "directional_signal", "channel_or_developer_proxy"]
    return ["discovery_lead", "exclusion_note"]


def _forbidden_claim_scopes(*, layer_id: str) -> list[str]:
    common = ["unsupported_exact_company_fact", "undisclosed_product_revenue", "undisclosed_market_share"]
    if layer_id == "L1":
        return ["facts_without_parser_period_unit_citation_gate", "undisclosed_company_metric_inference"]
    if layer_id == "L2":
        return common + ["company_sales_or_margin_without_company_disclosure", "causal_commercial_uptake"]
    if layer_id == "L3":
        return common + ["company_asp_or_inventory_fact", "sales_or_share_from_proxy"]
    return common + ["core_thesis_evidence_without_verification"]


def _specialist_slots(
    *,
    source_id: str,
    claim_scope: str,
    source_families: list[str],
    expected_profile: ExpectedSourceProfile | None,
) -> list[str]:
    if expected_profile:
        return list(expected_profile.specialist_slots)
    text = " ".join([source_id, claim_scope, *source_families]).lower()
    slots: set[str] = set()
    if any(token in text for token in ["financial", "company_reported", "sec_", "xbrl"]):
        slots.add("fundamental")
    if any(token in text for token in ["product", "clinical", "fda", "nhtsa", "patent", "openalex", "developer", "channel"]):
        slots.add("product_technology")
    if any(token in text for token in ["market", "valuation", "price", "ranking", "ecommerce", "app_store"]):
        slots.add("market_valuation")
    if any(token in text for token in ["industry", "macro", "eia", "fred", "bls", "bea", "census", "fdic", "trade"]):
        slots.add("industry_supply_chain")
    if any(token in text for token in ["relationship", "supplier", "customer", "gleif", "ownership", "13f"]):
        slots.add("industry_supply_chain")
        slots.add("capital_macro")
    if not slots:
        slots.add("risk_counterevidence")
    return sorted(slots)


def _memo_usage(*, layer_id: str, evidence_graph_status: str) -> str:
    base = LAYER_DEFINITIONS[layer_id]["memo_usage"]
    if evidence_graph_status in {"not_registered", "not_connected", "missing_runtime_route"}:
        return f"gap_only_until_connected; {base}"
    if evidence_graph_status in {"staging_parser_gate_pending", "crawlable_not_parsed_or_not_routed"}:
        return f"context_gap_or_targeted_repair_candidate; {base}"
    return base


def _blocking_reason(
    *,
    coverage: Mapping[str, Any],
    availability: Mapping[str, Any],
    materialization: Mapping[str, Any],
    evidence_graph_status: str,
) -> str:
    if evidence_graph_status == "not_registered":
        return "source_not_registered_in_current_runtime"
    if evidence_graph_status == "blocked_by_auth_or_policy":
        return _first_nonempty(availability.get("agent_promotion_blocker"), coverage.get("gap_type"), "blocked_by_auth_or_policy")
    if evidence_graph_status == "staging_parser_gate_pending":
        return _first_nonempty(materialization.get("runtime_promotion_status"), coverage.get("parser_status"), availability.get("parser_status"), "parser_gate_pending")
    if evidence_graph_status == "crawlable_not_parsed_or_not_routed":
        return "live_or_probe_available_but_runtime_route_parser_or_inventory_adapter_missing"
    if evidence_graph_status == "structured_not_promoted":
        return _first_nonempty(materialization.get("runtime_promotion_status"), "structured_rows_exist_but_not_promoted_to_runtime")
    if evidence_graph_status == "missing_runtime_route":
        return "collector_exists_but_runtime_route_or_feature_flag_missing"
    return ""


def _next_action(
    *,
    coverage: Mapping[str, Any],
    availability: Mapping[str, Any],
    materialization: Mapping[str, Any],
    expected_profile: ExpectedSourceProfile | None,
) -> str:
    if expected_profile:
        return "add source policy, acquisition route, parser contract, and source-boundary gate"
    return _first_nonempty(
        materialization.get("next_gate"),
        coverage.get("boundary_notes"),
        coverage.get("gap_type"),
        availability.get("availability_decision"),
        "inspect_source_policy_and_runtime_route",
    )


def _load_yaml(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    value = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return value if isinstance(value, dict) else {}


def _load_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    value = json.loads(p.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _first_nonempty(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
