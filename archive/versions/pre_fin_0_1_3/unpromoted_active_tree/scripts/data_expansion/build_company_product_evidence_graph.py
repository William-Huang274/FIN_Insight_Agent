from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]

GRAPH_SCHEMA_VERSION = "fin_agent_company_product_evidence_graph_v0.1"
NODE_SCHEMA_VERSION = "fin_agent_company_product_evidence_node_v0.1"
GAP_SCHEMA_VERSION = "fin_agent_company_product_evidence_gap_v0.1"
SUMMARY_SCHEMA_VERSION = "fin_agent_company_product_evidence_graph_summary_v0.1"

DEFAULT_UNIVERSE = REPO_ROOT / "data" / "manifests" / "tier1_tier2_market_universe_v0_1.csv"
DEFAULT_STRATEGY = REPO_ROOT / "configs" / "data_sources" / "product_evidence_strategy_v0_1.yaml"
DEFAULT_STRENGTH_MATRIX = REPO_ROOT / "data" / "manifests" / "public_source_strength_materialization_matrix_v0_1.jsonl"
DEFAULT_NORMALIZED_SNAPSHOT_SUMMARY = REPO_ROOT / "data" / "manifests" / "public_source_normalized_snapshot_summary_v0_1.json"
DEFAULT_SEC_TAXONOMY = (
    Path("Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_taxonomy_normalized_targeted_repair_strict_sentence_v0_1.jsonl")
)
DEFAULT_SEC_FACTS = (
    Path("Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_parser_verified_final_public_repair_v0_1.jsonl")
)
DEFAULT_REPAIR_CANDIDATE_FACTS = (
    Path("Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_parser_verified_targeted_repair_strict_sentence_v0_1.jsonl")
)
DEFAULT_OUTPUT_DIR = Path("Z:/FIN_Insight_Agent/data/manifests/product_evidence_graph_final_public_repair_v0_1")
DEFAULT_REPORT = Path("Z:/FIN_Insight_Agent/docs/internal/vnext_20260610/company_product_evidence_graph_final_public_repair_v0_1_execution.zh-CN.md")

INDUSTRY_SOURCE_IDS = {
    "consumer_electronics_semiconductor_hardware": [
        "sec_edgar_apis",
        "company_ir_reports",
        "company_product_pages",
        "census_data_api",
        "usitc_dataweb_and_trade",
        "openalex_api",
        "patentsview_api",
        "fred_api",
        "bls_public_api",
    ],
    "app_software_consumer_internet": [
        "sec_edgar_apis",
        "company_ir_reports",
        "company_product_pages",
        "openalex_api",
        "common_crawl_index",
        "wikidata",
        "gdelt",
        "fred_api",
        "bls_public_api",
    ],
    "automotive": [
        "sec_edgar_apis",
        "company_ir_reports",
        "company_product_pages",
        "nhtsa_vpic_api",
        "fred_api",
        "bls_public_api",
        "census_data_api",
    ],
    "healthcare_pharma_medtech": [
        "sec_edgar_apis",
        "company_ir_reports",
        "company_product_pages",
        "clinicaltrials_api",
        "openfda_api",
        "cms_public_data",
        "openalex_api",
        "patentsview_api",
    ],
    "retail_cpg": [
        "sec_edgar_apis",
        "company_ir_reports",
        "company_product_pages",
        "fred_api",
        "bls_public_api",
        "bea_data_api",
        "census_data_api",
        "common_crawl_index",
    ],
    "energy_industrials_materials": [
        "sec_edgar_apis",
        "company_ir_reports",
        "company_product_pages",
        "eia_open_data",
        "fred_api",
        "bls_public_api",
        "bea_data_api",
        "census_data_api",
        "usitc_dataweb_and_trade",
    ],
    "banking_financial_services": [
        "sec_edgar_apis",
        "company_ir_reports",
        "fdic_bankfind_api",
        "fred_api",
        "bls_public_api",
        "bea_data_api",
        "sec_ownership_and_13f",
    ],
}

PUBLIC_SOURCE_METRIC_COVERAGE = {
    "clinicaltrials_api": {"pipeline_status", "trial_phase", "trial_sponsor", "indication_context"},
    "openfda_api": {"label_status", "adverse_event_context", "recall_or_enforcement_context", "product_status"},
    "cms_public_data": {"payer_context", "utilization_context"},
    "nhtsa_vpic_api": {"vehicle_model_identity", "make_model_year_context"},
    "fdic_bankfind_api": {"bank_institution_identity", "branch_and_institution_context"},
    "eia_open_data": {"energy_price_volume_context", "industry_supply_demand_context"},
    "census_data_api": {"trade_or_industry_context"},
    "usitc_dataweb_and_trade": {"trade_or_industry_context"},
    "fred_api": {"macro_industry_context"},
    "bls_public_api": {"macro_industry_context"},
    "bea_data_api": {"macro_industry_context"},
    "openalex_api": {"research_activity_context"},
    "patentsview_api": {"ip_activity_context"},
    "common_crawl_index": {"web_presence_lead"},
    "gdelt": {"event_lead"},
    "wikidata": {"entity_resolver_context"},
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build company-level product evidence graph and public/commercial gap ledger.")
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--strategy-config", type=Path, default=DEFAULT_STRATEGY)
    parser.add_argument("--strength-matrix", type=Path, default=DEFAULT_STRENGTH_MATRIX)
    parser.add_argument("--normalized-snapshot-summary", type=Path, default=DEFAULT_NORMALIZED_SNAPSHOT_SUMMARY)
    parser.add_argument("--sec-taxonomy", type=Path, default=DEFAULT_SEC_TAXONOMY)
    parser.add_argument("--sec-facts", type=Path, default=DEFAULT_SEC_FACTS)
    parser.add_argument("--repair-candidate-facts", type=Path, default=DEFAULT_REPAIR_CANDIDATE_FACTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = datetime.now(timezone.utc).isoformat()
    universe_rows = load_universe(_resolve(args.universe))
    strategy = _load_yaml(_resolve(args.strategy_config))
    source_matrix = {str(row.get("source_id") or ""): row for row in _iter_jsonl(_resolve(args.strength_matrix))}
    snapshot_summary = _read_json(_resolve(args.normalized_snapshot_summary))
    taxonomy_rows = list(_iter_jsonl(_resolve(args.sec_taxonomy)))
    sec_fact_rows = list(_iter_jsonl(_resolve(args.sec_facts)))
    accepted_fact_ids = {
        str(value)
        for row in sec_fact_rows
        for value in (row.get("fact_id"), row.get("source_repair_fact_id"))
        if value
    }
    repair_candidate_rows = load_repair_candidates(_resolve(args.repair_candidate_facts), accepted_fact_ids)

    graph_rows, node_rows, gap_rows = build_evidence_graph(
        universe_rows=universe_rows,
        strategy=strategy,
        source_matrix=source_matrix,
        snapshot_summary=snapshot_summary,
        taxonomy_rows=taxonomy_rows,
        sec_fact_rows=sec_fact_rows,
        repair_candidate_rows=repair_candidate_rows,
        generated_at=generated_at,
    )
    output_dir = _resolve(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    graph_output = output_dir / "company_product_evidence_graph_v0_1.jsonl"
    node_output = output_dir / "company_product_evidence_nodes_v0_1.jsonl"
    gap_output = output_dir / "company_product_evidence_gaps_v0_1.jsonl"
    summary_output = output_dir / "company_product_evidence_graph_summary_v0_1.json"
    report_output = _resolve(args.report_output)
    summary = build_summary(
        graph_rows=graph_rows,
        node_rows=node_rows,
        gap_rows=gap_rows,
        output_dir=output_dir,
        graph_output=graph_output,
        node_output=node_output,
        gap_output=gap_output,
        summary_output=summary_output,
        report_output=report_output,
        generated_at=generated_at,
    )
    _write_jsonl(graph_output, graph_rows)
    _write_jsonl(node_output, node_rows)
    _write_jsonl(gap_output, gap_rows)
    _write_json(summary_output, summary)
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(render_report(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def build_evidence_graph(
    *,
    universe_rows: list[dict[str, Any]],
    strategy: dict[str, Any],
    source_matrix: dict[str, dict[str, Any]],
    snapshot_summary: dict[str, Any],
    taxonomy_rows: list[dict[str, Any]],
    sec_fact_rows: list[dict[str, Any]],
    repair_candidate_rows: list[dict[str, Any]],
    generated_at: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    taxonomy_by_ticker = group_rows(taxonomy_rows, "ticker")
    sec_facts_by_ticker = group_rows(sec_fact_rows, "ticker")
    repair_by_ticker = group_rows(repair_candidate_rows, "ticker")
    industry_by_ticker = infer_industry_by_ticker(universe_rows, taxonomy_by_ticker)
    normalized_sources = set((snapshot_summary.get("successful_sources") or []))
    industry_plan = strategy.get("industry_source_plan") or {}

    graph_rows: list[dict[str, Any]] = []
    node_rows: list[dict[str, Any]] = []
    gap_rows: list[dict[str, Any]] = []
    for company in universe_rows:
        ticker = str(company.get("ticker") or "").strip()
        if not ticker:
            continue
        industry_schema = industry_by_ticker.get(ticker) or "unrouted"
        taxonomy_count = len(taxonomy_by_ticker.get(ticker, []))
        fact_rows = sec_facts_by_ticker.get(ticker, [])
        monotonic_repair_fact_count = sum(
            1 for row in fact_rows if row.get("repair_promotion_status") == "monotonic_repair_promoted"
        )
        operating_metric_repair_fact_count = sum(
            1 for row in fact_rows if row.get("repair_promotion_status") == "operating_metric_repair_promoted"
        )
        sentence_repair_fact_count = sum(
            1 for row in fact_rows if row.get("repair_promotion_status") == "sentence_repair_promoted"
        )
        repair_rows = repair_by_ticker.get(ticker, [])
        company_nodes: list[dict[str, Any]] = []
        if taxonomy_count:
            company_nodes.append(
                graph_node(
                    ticker=ticker,
                    company=company,
                    industry_schema=industry_schema,
                    source_id="sec_product_taxonomy_normalized",
                    evidence_layer="company_disclosed_taxonomy",
                    signal_strength="S5_primary_authority_taxonomy",
                    promotion_status="runtime_context_taxonomy_only",
                    record_count=taxonomy_count,
                    allowed_claims=["product taxonomy", "product/segment retrieval planning"],
                    forbidden_claims=["product sales", "market share", "demand proof"],
                    source_paths=["sec_taxonomy"],
                    generated_at=generated_at,
                )
            )
        if fact_rows:
            fact_node = graph_node(
                ticker=ticker,
                company=company,
                industry_schema=industry_schema,
                source_id="sec_product_kpi_parser_verified",
                evidence_layer="company_disclosed_verified_product_kpi",
                signal_strength="S5_primary_authority_parser_verified",
                promotion_status="runtime_fact_allowed",
                record_count=len(fact_rows),
                allowed_claims=sorted({str(row.get("metric_family") or "") for row in fact_rows if row.get("metric_family")}),
                forbidden_claims=["market share", "channel inventory", "undisclosed SKU economics"],
                source_paths=["sec_facts"],
                generated_at=generated_at,
            )
            fact_node["baseline_parser_fact_count"] = (
                len(fact_rows)
                - monotonic_repair_fact_count
                - operating_metric_repair_fact_count
                - sentence_repair_fact_count
            )
            fact_node["monotonic_repair_fact_count"] = monotonic_repair_fact_count
            fact_node["operating_metric_repair_fact_count"] = operating_metric_repair_fact_count
            fact_node["sentence_repair_fact_count"] = sentence_repair_fact_count
            company_nodes.append(fact_node)
        if repair_rows:
            company_nodes.append(
                graph_node(
                    ticker=ticker,
                    company=company,
                    industry_schema=industry_schema,
                    source_id="sec_targeted_repair_candidate_review",
                    evidence_layer="company_disclosed_repair_candidate",
                    signal_strength="S5_candidate_needs_review",
                    promotion_status="review_queue_not_runtime_fact",
                    record_count=len(repair_rows),
                    allowed_claims=["candidate product-KPI evidence for manual/parser review"],
                    forbidden_claims=["runtime product KPI fact"],
                    source_paths=["repair_candidate_facts"],
                    generated_at=generated_at,
                )
            )

        public_source_ids = industry_public_sources(industry_schema)
        checked_public_sources: list[str] = []
        for source_id in public_source_ids:
            matrix_row = source_matrix.get(source_id, {})
            if not matrix_row:
                continue
            materialized = source_is_materialized(matrix_row, normalized_sources)
            if materialized:
                checked_public_sources.append(source_id)
            company_nodes.append(
                graph_node(
                    ticker=ticker,
                    company=company,
                    industry_schema=industry_schema,
                    source_id=source_id,
                    evidence_layer=public_evidence_layer(matrix_row),
                    signal_strength=str(matrix_row.get("information_strength_tier") or ""),
                    promotion_status="context_or_lead_available" if materialized else "source_not_materialized_or_parser_pending",
                    record_count=source_record_count(matrix_row),
                    allowed_claims=sorted(PUBLIC_SOURCE_METRIC_COVERAGE.get(source_id, {"context_or_lead"})),
                    forbidden_claims=public_forbidden_claims(source_id),
                    source_paths=["public_source_strength_materialization_matrix", "public_source_normalized_snapshot"]
                    if materialized
                    else ["public_source_strength_materialization_matrix"],
                    generated_at=generated_at,
                )
            )

        industry_config = industry_plan.get(industry_schema) or {}
        for metric in industry_config.get("external_metrics") or []:
            if metric_publicly_filled(metric, fact_rows, checked_public_sources):
                continue
            commercial_sources = list(industry_config.get("commercial_market_tracker_sources") or [])
            if not commercial_sources:
                continue
            gap_rows.append(
                {
                    "schema_version": GAP_SCHEMA_VERSION,
                    "gap_id": stable_id("PRODUCTEVIDENCEGAP", ticker, industry_schema, metric),
                    "generated_at": generated_at,
                    "ticker": ticker,
                    "company": company.get("company_name"),
                    "industry_schema": industry_schema,
                    "gap_type": "commercial_market_tracker_gap_after_public_source_check",
                    "missing_metric": metric,
                    "public_sources_checked": checked_public_sources,
                    "commercial_sources_that_would_fill": commercial_sources,
                    "gap_status": "expose_to_agent_as_gap_not_fallback",
                    "why_public_sources_do_not_fill": public_gap_reason(metric),
                    "runtime_use_boundary": "May tell the analyst this public-evidence graph lacks a direct measurement; cannot synthesize the missing metric from proxies.",
                }
            )
        if not fact_rows:
            gap_rows.append(
                {
                    "schema_version": GAP_SCHEMA_VERSION,
                    "gap_id": stable_id("PRODUCTEVIDENCEGAP", ticker, "sec_product_kpi_missing"),
                    "generated_at": generated_at,
                    "ticker": ticker,
                    "company": company.get("company_name"),
                    "industry_schema": industry_schema,
                    "gap_type": "company_disclosed_product_kpi_not_verified",
                    "missing_metric": "company_disclosed_product_kpi",
                    "public_sources_checked": ["sec_edgar_apis", *checked_public_sources],
                    "commercial_sources_that_would_fill": [],
                    "gap_status": "public_source_gap_or_parser_review_required",
                    "why_public_sources_do_not_fill": "SEC/global filings may have taxonomy or context, but no parser-verified product KPI fact passed value/unit/period/product/citation gates.",
                    "runtime_use_boundary": "Agent may use taxonomy and public context, but must not state a company-disclosed product KPI as fact.",
                }
            )
        node_rows.extend(company_nodes)
        graph_rows.append(
            {
                "schema_version": GRAPH_SCHEMA_VERSION,
                "graph_id": stable_id("PRODUCTEVIDENCEGRAPH", ticker),
                "generated_at": generated_at,
                "ticker": ticker,
                "company": company.get("company_name"),
                "country": company.get("country"),
                "universe_tier": company.get("universe_tier"),
                "industry_schema": industry_schema,
                "sec_taxonomy_node_count": taxonomy_count,
                "sec_verified_product_kpi_fact_count": len(fact_rows),
                "monotonic_repair_fact_count": monotonic_repair_fact_count,
                "operating_metric_repair_fact_count": operating_metric_repair_fact_count,
                "sentence_repair_fact_count": sentence_repair_fact_count,
                "sec_repair_candidate_count": len(repair_rows),
                "evidence_node_count": len(company_nodes),
                "runtime_fact_node_count": sum(1 for node in company_nodes if node.get("promotion_status") == "runtime_fact_allowed"),
                "context_or_lead_node_count": sum(1 for node in company_nodes if node.get("promotion_status") == "context_or_lead_available"),
                "commercial_gap_count": sum(1 for gap in gap_rows if gap.get("ticker") == ticker and gap.get("gap_type") == "commercial_market_tracker_gap_after_public_source_check"),
                "company_disclosed_kpi_gap": not bool(fact_rows),
                "runtime_use_boundary": "Use runtime_fact_allowed nodes for facts; use context_or_lead_available nodes only as bounded context; expose gaps explicitly instead of proxy fallback.",
            }
        )
    return graph_rows, node_rows, gap_rows


def graph_node(
    *,
    ticker: str,
    company: dict[str, Any],
    industry_schema: str,
    source_id: str,
    evidence_layer: str,
    signal_strength: str,
    promotion_status: str,
    record_count: int,
    allowed_claims: list[str],
    forbidden_claims: list[str],
    source_paths: list[str],
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": NODE_SCHEMA_VERSION,
        "node_id": stable_id("PRODUCTEVIDENCENODE", ticker, source_id, evidence_layer),
        "generated_at": generated_at,
        "ticker": ticker,
        "company": company.get("company_name"),
        "industry_schema": industry_schema,
        "source_id": source_id,
        "evidence_layer": evidence_layer,
        "signal_strength": signal_strength,
        "promotion_status": promotion_status,
        "record_count": record_count,
        "allowed_claims": allowed_claims,
        "forbidden_claims": forbidden_claims,
        "source_paths": source_paths,
        "runtime_use_boundary": node_runtime_boundary(promotion_status),
    }


def load_repair_candidates(path: Path, accepted_fact_ids: set[str]) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for row in _iter_jsonl(path):
        fact_id = str(row.get("fact_id") or "")
        if fact_id and fact_id not in accepted_fact_ids:
            row = dict(row)
            row["promotion_status"] = "repair_candidate_review_required"
            rows.append(row)
    return rows


def load_universe(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def infer_industry_by_ticker(universe_rows: list[dict[str, Any]], taxonomy_by_ticker: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for ticker, rows in taxonomy_by_ticker.items():
        counts = Counter(str(row.get("industry_schema") or "") for row in rows if row.get("industry_schema"))
        if counts:
            out[ticker] = counts.most_common(1)[0][0]
    for row in universe_rows:
        ticker = str(row.get("ticker") or "").strip()
        if ticker in out:
            continue
        out[ticker] = infer_industry_from_category(" ".join(str(row.get(key) or "") for key in ("sector", "category")))
    return out


def infer_industry_from_category(text: str) -> str:
    lower = text.lower()
    if any(term in lower for term in ("pharma", "health", "biotech", "medical")):
        return "healthcare_pharma_medtech"
    if any(term in lower for term in ("auto", "vehicle", "battery")):
        return "automotive"
    if any(term in lower for term in ("software", "saas", "cloud", "internet", "cyber", "ecommerce")):
        return "app_software_consumer_internet"
    if any(term in lower for term in ("semiconductor", "hardware", "memory", "foundry", "electronics")):
        return "consumer_electronics_semiconductor_hardware"
    if any(term in lower for term in ("retail", "consumer", "restaurant", "food", "apparel", "cpg")):
        return "retail_cpg"
    if any(term in lower for term in ("bank", "financial", "insurance", "payments", "asset management")):
        return "banking_financial_services"
    if any(term in lower for term in ("energy", "industrial", "materials", "utility", "mining", "aerospace", "defense")):
        return "energy_industrials_materials"
    return "unrouted"


def industry_public_sources(industry_schema: str) -> list[str]:
    return INDUSTRY_SOURCE_IDS.get(industry_schema, ["sec_edgar_apis", "company_ir_reports", "fred_api", "bls_public_api"])


def source_is_materialized(row: dict[str, Any], normalized_sources: set[str]) -> bool:
    status = str(row.get("materialization_status") or "")
    if status.startswith("materialized") or row.get("source_id") in normalized_sources:
        return True
    return bool(row.get("normalized_snapshot_record_count") or row.get("extended_materialization_record_count") or row.get("industry_snapshot_observation_count"))


def source_record_count(row: dict[str, Any]) -> int:
    keys = (
        "normalized_snapshot_record_count",
        "extended_materialization_record_count",
        "industry_snapshot_observation_count",
        "downloaded_document_row_count",
        "sec_structured_fact_row_count",
        "sec_annual_ledger_fact_count",
        "inventory_runtime_row_count",
    )
    return sum(int(row.get(key) or 0) for key in keys)


def public_evidence_layer(row: dict[str, Any]) -> str:
    tier = str(row.get("information_strength_tier") or "")
    if tier.startswith("S5"):
        return "primary_or_company_disclosure_context"
    if tier.startswith("S4"):
        return "official_company_product_surface"
    if tier.startswith("S3"):
        return "official_regulatory_product_context"
    if tier.startswith("S2"):
        return "official_macro_industry_context"
    return "resolver_or_lead"


def public_forbidden_claims(source_id: str) -> list[str]:
    if source_id in {"clinicaltrials_api", "openfda_api", "nhtsa_vpic_api", "fdic_bankfind_api"}:
        return ["company product sales", "market share", "profitability", "causal demand proof"]
    if source_id in {"fred_api", "bls_public_api", "bea_data_api", "eia_open_data", "census_data_api", "usitc_dataweb_and_trade"}:
        return ["company-specific product sales", "company margins", "company market share"]
    return ["unverified company KPI", "market share proof"]


def metric_publicly_filled(metric: str, fact_rows: list[dict[str, Any]], checked_public_sources: list[str]) -> bool:
    metric_lower = str(metric).lower()
    if any(metric_lower in str(row.get("metric_family") or "").lower() for row in fact_rows):
        return True
    if metric_lower in {"production", "throughput", "commodity_volume"} and "eia_open_data" in checked_public_sources:
        return False
    return False


def public_gap_reason(metric: str) -> str:
    reasons = {
        "shipments": "Public trade or macro data can show category flows, but not company/vendor product shipments without a tracker or company disclosure.",
        "vendor_share": "Public sources do not provide complete vendor share with issuer/product mapping.",
        "ASP": "Public sources may expose prices or trade values, but not reliable company product ASP.",
        "channel_inventory": "Channel inventory is not observable from free official sources at company-product level.",
        "tracker_forecast": "Forecast trackers are commercial or analyst products under current policy.",
        "downloads": "Free public surfaces may show rank or limited metadata, not complete app downloads.",
        "active_users": "Company-level active users are company-disclosed or commercial-estimated; public proxies are directional only.",
        "app_revenue_estimates": "App revenue estimates are commercial tracker data under current policy.",
        "web_traffic": "Free web signals are proxy-only and not a company-disclosed operating KPI.",
        "registrations": "NHTSA identifies models and recalls, but comprehensive registrations require mobility/registration datasets.",
        "prescriptions": "openFDA/ClinicalTrials support regulatory context; prescription volume requires IQVIA/Symphony-like data.",
        "POS_sell_through": "POS sell-through and scanner/panel data are commercial retail datasets.",
        "scanner_sales": "Scanner sales are commercial retail datasets.",
        "consumer_panel": "Consumer panel data is commercial under current policy.",
        "price_promotion": "Public pages can expose some price points, but systematic promotion measurement requires retail data.",
    }
    return reasons.get(str(metric), "Public/free sources checked do not provide a direct, company-product-level measured series for this metric.")


def node_runtime_boundary(promotion_status: str) -> str:
    if promotion_status == "runtime_fact_allowed":
        return "May support factual research claims within the listed allowed_claims."
    if promotion_status == "review_queue_not_runtime_fact":
        return "Review/candidate only; cannot be used as a fact."
    if promotion_status == "context_or_lead_available":
        return "Context/lead only unless a downstream source-specific parser promotes it."
    return "Not runtime evidence until source-specific parser or materialization gate passes."


def build_summary(
    *,
    graph_rows: list[dict[str, Any]],
    node_rows: list[dict[str, Any]],
    gap_rows: list[dict[str, Any]],
    output_dir: Path,
    graph_output: Path,
    node_output: Path,
    gap_output: Path,
    summary_output: Path,
    report_output: Path,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "pass",
        "generated_at": generated_at,
        "company_count": len(graph_rows),
        "evidence_node_count": len(node_rows),
        "gap_count": len(gap_rows),
        "companies_with_sec_verified_product_kpi": sum(1 for row in graph_rows if int(row.get("sec_verified_product_kpi_fact_count") or 0) > 0),
        "companies_with_sec_taxonomy": sum(1 for row in graph_rows if int(row.get("sec_taxonomy_node_count") or 0) > 0),
        "companies_with_repair_candidates": sum(1 for row in graph_rows if int(row.get("sec_repair_candidate_count") or 0) > 0),
        "companies_with_monotonic_repair_facts": sum(1 for row in graph_rows if int(row.get("monotonic_repair_fact_count") or 0) > 0),
        "monotonic_repair_fact_count": sum(int(row.get("monotonic_repair_fact_count") or 0) for row in graph_rows),
        "companies_with_operating_metric_repair_facts": sum(
            1 for row in graph_rows if int(row.get("operating_metric_repair_fact_count") or 0) > 0
        ),
        "operating_metric_repair_fact_count": sum(int(row.get("operating_metric_repair_fact_count") or 0) for row in graph_rows),
        "companies_with_sentence_repair_facts": sum(1 for row in graph_rows if int(row.get("sentence_repair_fact_count") or 0) > 0),
        "sentence_repair_fact_count": sum(int(row.get("sentence_repair_fact_count") or 0) for row in graph_rows),
        "companies_with_company_disclosed_kpi_gap": sum(1 for row in graph_rows if row.get("company_disclosed_kpi_gap")),
        "industry_schema_counts": dict(sorted(Counter(str(row.get("industry_schema") or "") for row in graph_rows).items())),
        "node_layer_counts": dict(sorted(Counter(str(row.get("evidence_layer") or "") for row in node_rows).items())),
        "node_promotion_counts": dict(sorted(Counter(str(row.get("promotion_status") or "") for row in node_rows).items())),
        "gap_type_counts": dict(sorted(Counter(str(row.get("gap_type") or "") for row in gap_rows).items())),
        "outputs": {
            "output_dir": _repo_path(output_dir),
            "graph": _repo_path(graph_output),
            "nodes": _repo_path(node_output),
            "gaps": _repo_path(gap_output),
            "summary": _repo_path(summary_output),
            "report": _repo_path(report_output),
        },
        "promotion_boundary": [
            "SEC parser-verified product KPI facts are the only company product KPI fact layer.",
            "Monotonic repair promoted rows can enter that fact layer only when they carry repair_promotion_status=monotonic_repair_promoted.",
            "Operating metric repair rows can enter that fact layer only when public-disclosure unit/value/product binding is source-specifically verified.",
            "Sentence repair rows can enter that fact layer only when local product-value-revenue relation is verified; otherwise they remain rejected.",
            "Targeted repair rows are review candidates, not runtime facts.",
            "Official/regulatory/macro sources provide context, identity, status, or proxy evidence only.",
            "Commercial gaps are exposed only after public/free sources are recorded as checked; they must not become proxy fallbacks.",
        ],
    }


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Company Product Evidence Graph 执行报告",
        "",
        f"- 生成时间：`{summary['generated_at']}`",
        f"- 公司数：`{summary['company_count']}`",
        f"- Evidence nodes：`{summary['evidence_node_count']}`，gaps：`{summary['gap_count']}`",
        f"- SEC verified product-KPI 覆盖公司：`{summary['companies_with_sec_verified_product_kpi']}`",
        f"- Monotonic repair facts：`{summary['monotonic_repair_fact_count']}` / companies `({summary['companies_with_monotonic_repair_facts']})`",
        f"- Operating metric repair facts：`{summary['operating_metric_repair_fact_count']}` / companies `({summary['companies_with_operating_metric_repair_facts']})`",
        f"- Sentence repair facts：`{summary['sentence_repair_fact_count']}` / companies `({summary['companies_with_sentence_repair_facts']})`",
        f"- SEC taxonomy 覆盖公司：`{summary['companies_with_sec_taxonomy']}`",
        f"- Repair candidates 覆盖公司：`{summary['companies_with_repair_candidates']}`（review only）",
        f"- Company disclosed KPI gap 公司：`{summary['companies_with_company_disclosed_kpi_gap']}`",
        "",
        "## Boundary",
        "",
    ]
    lines.extend(f"- {item}" for item in summary["promotion_boundary"])
    lines.extend(
        [
            "",
            "## Counts",
            "",
            f"- Industry schema counts：`{json.dumps(summary['industry_schema_counts'], ensure_ascii=False, sort_keys=True)}`",
            f"- Node layer counts：`{json.dumps(summary['node_layer_counts'], ensure_ascii=False, sort_keys=True)}`",
            f"- Node promotion counts：`{json.dumps(summary['node_promotion_counts'], ensure_ascii=False, sort_keys=True)}`",
            f"- Gap type counts：`{json.dumps(summary['gap_type_counts'], ensure_ascii=False, sort_keys=True)}`",
        ]
    )
    return "\n".join(lines) + "\n"


def group_rows(rows: Iterable[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = str(row.get(key) or "").strip()
        if value:
            grouped[value].append(row)
    return grouped


def stable_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha1("||".join(str(part or "") for part in parts).encode("utf-8")).hexdigest()[:14]
    return f"{prefix}::{digest}"


def _resolve(path: Path) -> Path:
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
