from __future__ import annotations

import json
import re
import hashlib
import io
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from sec_agent.memo_logic_plan import build_memo_logic_plan


REPO_ROOT = Path(__file__).resolve().parents[2]
P34_SOURCE_ROUTE_PLAN_SCHEMA_VERSION = "fin_insight_p34_ai_semis_source_route_plan_v0_1"
P34_ADAPTER_FIXTURE_SCHEMA_VERSION = "fin_insight_p34_ai_semis_adapter_fixture_report_v0_1"
P34_LIVE_ROUTE_ATTEMPT_SCHEMA_VERSION = "fin_insight_p34_ai_semis_live_route_attempt_report_v0_1"
P34_NO_PAID_AUDIT_SCHEMA_VERSION = "fin_insight_p34_ai_semis_no_paid_quality_audit_v0_1"
P34_SCOPED_WRITER_PAYLOAD_SCHEMA_VERSION = "fin_insight_p34_ai_semis_scoped_writer_payload_v0_1"

DEFAULT_SLOT_MAPPING_PATH = (
    REPO_ROOT / "docs/project_os/p34_ai_semis_evidence_slot_contract_mapping_v0_1.json"
)
DEFAULT_JUDGMENT_CHAIN_PATH = (
    REPO_ROOT / "docs/project_os/p34_ai_semis_judgment_chain_registry_v0_1.json"
)
DEFAULT_LIVE_ROUTE_ATTEMPT_REPORT_PATH = (
    REPO_ROOT / "docs/project_os/p34_ai_semis_live_route_attempt_report_v0_1.json"
)
DEFAULT_NO_PAID_QUALITY_AUDIT_PATH = (
    REPO_ROOT / "docs/project_os/p34_ai_semis_no_paid_quality_audit_v0_1.json"
)
DEFAULT_P33_LIVE_BACKFILL_PATH = (
    REPO_ROOT / "docs/project_os/p33_goldset_live_source_backfill_v0_1.json"
)
DEFAULT_AI_SEMIS_GOLD_CONTENT_PATH = (
    REPO_ROOT / "docs/project_os/ai_semis_gold_depth_content_pack_v0_1.json"
)

NORMALIZED_RUNTIME_ROW_FIELDS = [
    "issuer",
    "product_or_family",
    "metric_or_attribute",
    "value",
    "unit",
    "period_or_version",
    "source_url",
    "citation",
    "parser_lineage",
    "authority_scope",
    "cannot_infer",
]

TYPED_GAP_TAXONOMY = [
    "locator_gap",
    "parser_gap",
    "source_absent_after_attempt",
    "credential_gap",
    "commercial_gap",
    "case_binding_required",
]

P34_PRIORITY_ADAPTER_FAMILIES = [
    "sec_8k_earnings_release_table_adapter",
    "official_product_spec_page_adapter",
    "semicap_bookings_backlog_adapter",
]

ROUTE_FAMILY_CATALOG: dict[str, dict[str, Any]] = {
    "sec_8k_earnings_release_table_adapter": {
        "source_role": "issuer_primary_disclosure",
        "source_examples": ["SEC 8-K", "earnings release exhibit", "quarterly result release"],
        "locator_strategy": "SEC submissions accession search by issuer, form type, fiscal period, and AI/server/segment keywords.",
        "parser_strategy": "HTML/PDF table extraction plus text-near-table metric binding for revenue, orders, backlog, segment margin, capex, and management commentary.",
        "authority_scope": "issuer_exact_if_metric_product_period_and_citation_are_bound",
    },
    "investor_deck_pdf_table_adapter": {
        "source_role": "issuer_primary_or_ir_deck",
        "source_examples": ["investor presentation", "earnings presentation", "quarterly results PDF"],
        "locator_strategy": "Company IR page, SEC exhibit, or annual/quarterly presentation locator with version/date capture.",
        "parser_strategy": "PDF page/table extraction with caption, footnote, segment header, unit, and period binding.",
        "authority_scope": "issuer_exact_or_bounded_context_depending_on_metric_binding",
    },
    "official_product_spec_page_adapter": {
        "source_role": "official_product_surface",
        "source_examples": ["official product page", "technical product brief", "datasheet"],
        "locator_strategy": "Issuer official domain search constrained by product/version tokens.",
        "parser_strategy": "HTML/PDF spec slot extraction for architecture, memory, bandwidth, interconnect, power, platform, software, and generation.",
        "authority_scope": "official_technical_fact_not_revenue_or_share",
    },
    "official_product_docs_or_pdf_adapter": {
        "source_role": "official_product_surface",
        "source_examples": ["official datasheet PDF", "technical whitepaper", "product brief PDF"],
        "locator_strategy": "Issuer docs/download pages and PDF links constrained by product/version tokens.",
        "parser_strategy": "PDF text/table extraction with spec-name normalization and version binding.",
        "authority_scope": "official_technical_fact_not_revenue_or_share",
    },
    "benchmark_result_adapter": {
        "source_role": "public_performance_proxy",
        "source_examples": ["MLPerf", "official benchmark submission", "vendor benchmark page"],
        "locator_strategy": "Benchmark provider result tables plus official vendor benchmark pages.",
        "parser_strategy": "Benchmark table extraction with workload, system, accelerator, software stack, score, and benchmark version.",
        "authority_scope": "performance_proxy_not_sales_or_share",
    },
    "customer_deployment_news_adapter": {
        "source_role": "official_customer_deployment",
        "source_examples": ["official customer case study", "joint press release", "cloud service announcement"],
        "locator_strategy": "Issuer/customer/cloud official news constrained by product, customer, and deployment verbs.",
        "parser_strategy": "Entity relation extraction for issuer, product, customer/channel, deployment/adoption/configuration, date, and boundary.",
        "authority_scope": "deployment_signal_not_order_value_or_margin",
    },
    "oem_configuration_adapter": {
        "source_role": "oem_configuration",
        "source_examples": ["OEM server configuration page", "system datasheet", "partner validated design"],
        "locator_strategy": "OEM official product/configuration pages constrained by accelerator and server model tokens.",
        "parser_strategy": "Configuration slot extraction for server model, accelerator, rack/system, networking, cooling, memory, and availability.",
        "authority_scope": "official_configuration_not_customer_purchase",
    },
    "cloud_capex_filing_adapter": {
        "source_role": "issuer_capex_and_infrastructure_disclosure",
        "source_examples": ["10-Q capex discussion", "10-K capex note", "earnings call capex commentary"],
        "locator_strategy": "SEC filing text/ledger routes plus IR release/transcript search for capex, technical infrastructure, and AI capacity.",
        "parser_strategy": "Capex amount/guidance extraction with cash-flow statement tie-out and management supply-demand commentary binding.",
        "authority_scope": "demand_pool_context_not_supplier_allocation",
    },
    "semicap_bookings_backlog_adapter": {
        "source_role": "semicap_cycle_primary_disclosure",
        "source_examples": ["ASML quarterly results", "AMAT segment table", "LRCX earnings release", "KLAC process control release"],
        "locator_strategy": "Company IR quarterly/annual report search for bookings, backlog, systems, installed base, China, memory, foundry/logic, services.",
        "parser_strategy": "Segment table and management commentary parser for bookings, backlog, systems sales, installed base, region/customer concentration, and end-market mix.",
        "authority_scope": "issuer_exact_if_segment_metric_bound_else_semicap_context",
    },
    "market_snapshot_context_adapter": {
        "source_role": "market_price_and_liquidity_context",
        "source_examples": ["market snapshot", "price/volume", "short interest"],
        "locator_strategy": "Existing market snapshot and public exchange/market feeds by ticker and period.",
        "parser_strategy": "Snapshot binding for price move, volume, valuation proxy, liquidity, and short-interest context.",
        "authority_scope": "market_context_not_fundamental_fact",
    },
    "ownership_filing_context_adapter": {
        "source_role": "lagged_holder_positioning_context",
        "source_examples": ["13F", "13D/G", "insider forms"],
        "locator_strategy": "SEC ownership metadata and holder filings by issuer/period.",
        "parser_strategy": "Holder/ownership event extraction with lag and non-real-time flags.",
        "authority_scope": "lagged_positioning_context_not_realtime_flow",
    },
    "options_or_short_interest_proxy_adapter": {
        "source_role": "derivatives_or_short_interest_proxy",
        "source_examples": ["public options chain", "short interest report"],
        "locator_strategy": "Public delayed options/short-interest sources by ticker and date.",
        "parser_strategy": "Open interest, volume, put/call, implied move or short interest proxy extraction with delayed-data boundary.",
        "authority_scope": "positioning_proxy_not_investment_advice",
    },
    "credit_or_debt_context_adapter": {
        "source_role": "credit_funding_context",
        "source_examples": ["debt footnote", "credit facility", "bond/debt event"],
        "locator_strategy": "SEC debt footnotes, credit facility exhibits, and funding event filings.",
        "parser_strategy": "Debt amount, maturity, coupon/rate, facility, covenant and maturity wall extraction.",
        "authority_scope": "capital_structure_context_not_market_implied_credit_view_without_prices",
    },
    "risk_counterevidence_context_adapter": {
        "source_role": "risk_counterevidence_context",
        "source_examples": ["earnings risk commentary", "supply bottleneck", "margin pressure", "capex digestion"],
        "locator_strategy": "Existing risk/counterevidence pack plus issuer/peer filings and official commentary.",
        "parser_strategy": "Counter-thesis row extraction with risk type, affected chain, evidence ref and what-would-change trigger.",
        "authority_scope": "counterevidence_context_with_explicit_cannot_infer",
    },
    "regulatory_or_export_control_adapter": {
        "source_role": "regulatory_policy_context",
        "source_examples": ["export control", "government rule", "regulatory filing"],
        "locator_strategy": "Official regulator/government source plus issuer risk factor route.",
        "parser_strategy": "Policy date, affected product/country, issuer exposure and risk-boundary extraction.",
        "authority_scope": "policy_context_not_company_specific_financial_impact_without_bridge",
    },
}

FALLBACK_ROUTE_FAMILY_BY_PRIMARY: dict[str, str] = {
    "sec_8k_earnings_release_table_adapter": "investor_deck_pdf_table_adapter",
    "investor_deck_pdf_table_adapter": "sec_8k_earnings_release_table_adapter",
    "official_product_spec_page_adapter": "official_product_docs_or_pdf_adapter",
    "official_product_docs_or_pdf_adapter": "official_product_spec_page_adapter",
    "benchmark_result_adapter": "official_product_spec_page_adapter",
    "customer_deployment_news_adapter": "official_product_spec_page_adapter",
    "oem_configuration_adapter": "official_product_spec_page_adapter",
    "cloud_capex_filing_adapter": "investor_deck_pdf_table_adapter",
    "semicap_bookings_backlog_adapter": "investor_deck_pdf_table_adapter",
    "market_snapshot_context_adapter": "ownership_filing_context_adapter",
    "ownership_filing_context_adapter": "market_snapshot_context_adapter",
    "options_or_short_interest_proxy_adapter": "market_snapshot_context_adapter",
    "credit_or_debt_context_adapter": "sec_8k_earnings_release_table_adapter",
    "risk_counterevidence_context_adapter": "regulatory_or_export_control_adapter",
    "regulatory_or_export_control_adapter": "risk_counterevidence_context_adapter",
}


def build_ai_semis_source_route_plan(
    slot_mapping_path: str | Path = DEFAULT_SLOT_MAPPING_PATH,
) -> dict[str, Any]:
    mapping_path = Path(slot_mapping_path)
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    contracts = list(mapping.get("evidence_slot_contracts") or [])

    slots: list[dict[str, Any]] = []
    routes: list[dict[str, Any]] = []
    adapter_family_counts: dict[str, int] = {}
    p33_status_counts: dict[str, int] = {}

    for contract in contracts:
        evidence_row_id = str(contract["evidence_row_id"])
        families = _route_families_for_contract(contract)
        primary_route_id = ""
        fallback_route_ids: list[str] = []
        slot_route_ids: list[str] = []

        for route_index, family in enumerate(families, start=1):
            route_role = "primary" if route_index == 1 else "fallback"
            route_id = f"p34_route::{evidence_row_id}::{route_index:02d}::{family}"
            if route_role == "primary":
                primary_route_id = route_id
            else:
                fallback_route_ids.append(route_id)
            slot_route_ids.append(route_id)
            adapter_family_counts[family] = adapter_family_counts.get(family, 0) + 1
            routes.append(_build_route(route_id, route_role, family, contract))

        p33_status = str(contract.get("p33_backfill_status") or "unknown")
        p33_status_counts[p33_status] = p33_status_counts.get(p33_status, 0) + 1
        slots.append(
            {
                "evidence_row_id": evidence_row_id,
                "judgment_chain_ids": list(contract.get("judgment_chain_ids") or []),
                "quality_role": contract.get("quality_role"),
                "p33_backfill_status": p33_status,
                "route_plan_status": _slot_route_plan_status(p33_status),
                "primary_route_id": primary_route_id,
                "fallback_route_ids": fallback_route_ids,
                "route_ids": slot_route_ids,
                "source_route_families": families,
                "required_fields": list(contract.get("required_fields") or []),
                "forbidden_substitutes": list(contract.get("forbidden_substitutes") or []),
                "promotion_rule": contract.get("promotion_rule"),
                "cannot_infer": list(contract.get("cannot_infer") or []),
                "next_action": contract.get("next_action"),
                "quality_gate": {
                    "requires_parser_lineage": True,
                    "requires_authority_scope": True,
                    "requires_forbidden_substitute_check": True,
                    "requires_judgment_chain_binding": True,
                    "promotion_without_route_execution_allowed": False,
                },
            }
        )

    metrics = {
        "slot_count": len(slots),
        "route_count": len(routes),
        "primary_route_count": sum(1 for route in routes if route["route_role"] == "primary"),
        "fallback_route_count": sum(1 for route in routes if route["route_role"] == "fallback"),
        "slot_with_primary_route_count": sum(1 for slot in slots if slot["primary_route_id"]),
        "slot_with_fallback_route_count": sum(1 for slot in slots if slot["fallback_route_ids"]),
        "route_gap_count": sum(1 for slot in slots if not slot["primary_route_id"] or not slot["fallback_route_ids"]),
        "adapter_family_count": len(adapter_family_counts),
        "p33_backfill_status_counts": p33_status_counts,
        "p34_not_run_paid_llm": True,
        "p34_not_run_full_chain": True,
        "p34_not_run_new_crawler_parser": True,
    }
    return {
        "schema_version": P34_SOURCE_ROUTE_PLAN_SCHEMA_VERSION,
        "artifact_type": "ai_semis_source_route_plan",
        "status": "source_route_plan_ready_adapter_fixtures_pending",
        "lane": "AI/Semis",
        "source_contract": _rel(mapping_path),
        "metrics": metrics,
        "adapter_family_counts": dict(sorted(adapter_family_counts.items())),
        "normalized_runtime_row_fields": NORMALIZED_RUNTIME_ROW_FIELDS,
        "typed_gap_taxonomy": TYPED_GAP_TAXONOMY,
        "slots": slots,
        "routes": routes,
        "pre_writer_decision": {
            "allow_paid_memo_writer": False,
            "allow_full_chain": False,
            "reason": (
                "P34 has a source route plan, but adapter fixtures, parser lineage, runtime promotion, "
                "and no-paid quality audit are still pending."
            ),
        },
        "next_step": (
            "Implement first adapter-family fixtures: sec_8k_earnings_release_table_adapter, "
            "official_product_spec_page_adapter, and semicap_bookings_backlog_adapter."
        ),
    }


def build_ai_semis_adapter_fixture_report(
    source_route_plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    route_plan = dict(source_route_plan or build_ai_semis_source_route_plan())
    planned_families = set(route_plan.get("adapter_family_counts") or {})
    family_results: list[dict[str, Any]] = []
    all_runtime_rows: list[dict[str, Any]] = []
    all_rejected_candidates: list[dict[str, Any]] = []
    typed_gaps: list[dict[str, Any]] = []

    for family in P34_PRIORITY_ADAPTER_FAMILIES:
        fixtures = _adapter_fixture_inputs(family)
        fixture_results: list[dict[str, Any]] = []
        family_rows: list[dict[str, Any]] = []
        family_rejections: list[dict[str, Any]] = []
        family_gaps: list[dict[str, Any]] = []
        for fixture in fixtures:
            parsed = _parse_fixture_by_adapter_family(family, fixture)
            fixture_results.append(parsed)
            family_rows.extend(parsed["runtime_rows"])
            family_rejections.extend(parsed["rejected_candidates"])
            family_gaps.extend(parsed["typed_gaps"])

        family_status = "pass" if len(family_rows) >= 2 and not family_gaps else "warn_or_fail"
        family_results.append(
            {
                "adapter_family": family,
                "status": family_status,
                "planned_in_source_route_plan": family in planned_families,
                "fixture_count": len(fixtures),
                "runtime_row_count": len(family_rows),
                "rejected_candidate_count": len(family_rejections),
                "typed_gap_count": len(family_gaps),
                "fixture_results": fixture_results,
                "parser_contract": {
                    "required_output_fields": NORMALIZED_RUNTIME_ROW_FIELDS,
                    "must_preserve_parser_lineage": True,
                    "promotion_without_parser_lineage_allowed": False,
                    "authority_boundary_required": True,
                    "cannot_infer_required": True,
                },
            }
        )
        all_runtime_rows.extend(family_rows)
        all_rejected_candidates.extend(family_rejections)
        typed_gaps.extend(family_gaps)

    metrics = {
        "adapter_family_count": len(family_results),
        "fixture_count": sum(row["fixture_count"] for row in family_results),
        "runtime_row_count": len(all_runtime_rows),
        "rejected_candidate_count": len(all_rejected_candidates),
        "typed_gap_count": len(typed_gaps),
        "priority_family_pass_count": sum(1 for row in family_results if row["status"] == "pass"),
        "rows_with_parser_lineage_count": sum(1 for row in all_runtime_rows if row.get("parser_lineage")),
        "rows_with_authority_scope_count": sum(1 for row in all_runtime_rows if row.get("authority_scope")),
        "p34_not_run_paid_llm": True,
        "p34_not_run_full_chain": True,
        "p34_not_run_live_fetch_or_new_crawl": True,
    }
    return {
        "schema_version": P34_ADAPTER_FIXTURE_SCHEMA_VERSION,
        "artifact_type": "ai_semis_adapter_fixture_report",
        "status": (
            "adapter_fixture_parser_contract_pass_live_fetch_pending"
            if metrics["priority_family_pass_count"] == len(P34_PRIORITY_ADAPTER_FAMILIES)
            else "adapter_fixture_parser_contract_incomplete"
        ),
        "lane": "AI/Semis",
        "source_route_plan": "docs/project_os/p34_ai_semis_source_route_plan_v0_1.json",
        "scope": {
            "fixture_scope": "local_artifact_backed_parser_contract_fixtures",
            "live_fetch_performed": False,
            "paid_llm_performed": False,
            "full_chain_performed": False,
            "does_not_prove": [
                "official page still exists today",
                "fresh source fetch or browser crawl",
                "complete live parser coverage",
                "runtime promotion against live source rows",
                "paid specialist or Memo Writer quality",
            ],
        },
        "metrics": metrics,
        "normalized_runtime_row_fields": NORMALIZED_RUNTIME_ROW_FIELDS,
        "typed_gap_taxonomy": TYPED_GAP_TAXONOMY,
        "family_results": family_results,
        "runtime_rows": all_runtime_rows,
        "rejected_candidates": all_rejected_candidates,
        "typed_gaps": typed_gaps,
        "next_step": "Run P34 no-paid quality audit only after adapter fixtures are connected to live source route attempts or attempt-backed typed gaps.",
    }


def build_ai_semis_live_route_attempt_report(
    source_route_plan: Mapping[str, Any] | None = None,
    p33_live_backfill_path: str | Path = DEFAULT_P33_LIVE_BACKFILL_PATH,
    perform_network: bool = False,
    timeout_seconds: float = 8.0,
) -> dict[str, Any]:
    route_plan = dict(source_route_plan or build_ai_semis_source_route_plan())
    slots = list(route_plan.get("slots") or [])
    slot_contracts = {str(slot["evidence_row_id"]): slot for slot in slots}
    p33_rows = _p33_live_backfill_rows_by_slot(p33_live_backfill_path)

    attempts: list[dict[str, Any]] = []
    accepted_rows: list[dict[str, Any]] = []
    typed_gaps: list[dict[str, Any]] = []

    for slot_id, p33_row in sorted(p33_rows.items()):
        if slot_id not in slot_contracts or not p33_row.get("is_live_runtime_ready"):
            continue
        attempt = _local_manifest_live_attempt(slot_contracts[slot_id], p33_row)
        attempts.append(attempt)
        accepted_rows.append(_runtime_row_from_p33_backfill(slot_contracts[slot_id], p33_row, attempt))

    for spec in _live_route_attempt_specs():
        slot_id = str(spec["evidence_row_id"])
        if slot_id not in slot_contracts:
            continue
        attempt = _execute_live_route_attempt(
            slot_contracts[slot_id],
            spec,
            perform_network=perform_network,
            timeout_seconds=timeout_seconds,
        )
        attempts.append(attempt)
        if attempt["parser_status"] == "accepted_runtime_row":
            accepted_rows.append(_runtime_row_from_live_attempt(slot_contracts[slot_id], spec, attempt))
        else:
            typed_gaps.append(_typed_gap_from_attempt(slot_contracts[slot_id], spec, attempt))

    market_attempt, market_row, market_gap = _local_market_price_in_attempt(
        slot_contracts.get("market_price_in_valuation_positioning_gap")
    )
    if market_attempt:
        attempts.append(market_attempt)
    if market_row:
        accepted_rows.append(market_row)
    if market_gap:
        typed_gaps.append(market_gap)

    counter_attempt, counter_row, counter_gap = _derived_counter_thesis_attempt(
        slot_contracts.get("counter_thesis_pack_ai_semis"),
        accepted_rows,
        attempts,
    )
    if counter_attempt:
        attempts.append(counter_attempt)
    if counter_row:
        accepted_rows.append(counter_row)
    if counter_gap:
        typed_gaps.append(counter_gap)

    accepted_slot_ids = {str(row["evidence_row_id"]) for row in accepted_rows}
    typed_gap_slot_ids = {str(gap["evidence_row_id"]) for gap in typed_gaps}
    typed_gaps.extend(
        _derived_quality_typed_gaps(
            accepted_slot_ids=accepted_slot_ids,
            typed_gap_slot_ids=typed_gap_slot_ids,
            slot_contracts=slot_contracts,
        )
    )
    typed_gap_slot_ids = {str(gap["evidence_row_id"]) for gap in typed_gaps}
    attempt_backed_gap_slot_ids = {
        str(gap["evidence_row_id"]) for gap in typed_gaps if gap.get("attempt_backed") is True
    }
    attempted_slot_ids = {str(attempt["evidence_row_id"]) for attempt in attempts}

    metrics = {
        "slot_count": len(slots),
        "attempt_count": len(attempts),
        "attempted_slot_count": len(attempted_slot_ids),
        "accepted_runtime_row_count": len(accepted_rows),
        "accepted_slot_count": len(accepted_slot_ids),
        "typed_gap_count": len(typed_gaps),
        "attempt_backed_gap_slot_count": len(attempt_backed_gap_slot_ids),
        "unattempted_slot_count": len(set(slot_contracts) - attempted_slot_ids),
        "network_attempt_count": sum(1 for attempt in attempts if attempt.get("fetch_mode") == "http_get"),
        "network_ok_count": sum(
            1
            for attempt in attempts
            if attempt.get("fetch_mode") == "http_get" and attempt.get("fetch_status") == "ok"
        ),
        "perform_network": perform_network,
        "paid_llm_run": False,
        "full_chain_run": False,
    }
    status = (
        "live_route_attempts_recorded_with_remaining_typed_gaps"
        if accepted_rows or typed_gaps
        else "live_route_attempts_empty"
    )
    return {
        "schema_version": P34_LIVE_ROUTE_ATTEMPT_SCHEMA_VERSION,
        "artifact_type": "ai_semis_live_route_attempt_report",
        "status": status,
        "lane": "AI/Semis",
        "scope": {
            "purpose": "Connect P34 evidence slots to source route attempts or attempt-backed typed gaps before paid/full-chain.",
            "perform_network": perform_network,
            "paid_llm_performed": False,
            "full_chain_performed": False,
            "promotion_rule": "Only accepted_runtime_rows can support judgment chains; typed gaps explain why missing rows cannot be promoted.",
        },
        "metrics": metrics,
        "accepted_slot_ids": sorted(accepted_slot_ids),
        "attempt_backed_gap_slot_ids": sorted(attempt_backed_gap_slot_ids),
        "unattempted_slot_ids": sorted(set(slot_contracts) - attempted_slot_ids),
        "attempts": attempts,
        "accepted_runtime_rows": accepted_rows,
        "typed_gaps": typed_gaps,
        "pre_writer_decision": {
            "allow_paid_memo_writer": False,
            "allow_full_chain": False,
            "reason": "Live route attempts improve source-runtime closure, but P34 no-paid quality audit must pass before paid writer/full-chain.",
        },
    }


def build_ai_semis_no_paid_quality_audit(
    source_route_plan: Mapping[str, Any] | None = None,
    adapter_fixture_report: Mapping[str, Any] | None = None,
    live_route_attempt_report: Mapping[str, Any] | None = None,
    slot_mapping_path: str | Path = DEFAULT_SLOT_MAPPING_PATH,
    judgment_chain_path: str | Path = DEFAULT_JUDGMENT_CHAIN_PATH,
) -> dict[str, Any]:
    route_plan = dict(source_route_plan or build_ai_semis_source_route_plan(slot_mapping_path))
    fixture_report = dict(adapter_fixture_report or build_ai_semis_adapter_fixture_report(route_plan))
    live_report = dict(live_route_attempt_report or {})
    slot_mapping = json.loads(Path(slot_mapping_path).read_text(encoding="utf-8"))
    chain_registry = json.loads(Path(judgment_chain_path).read_text(encoding="utf-8"))

    contracts = list(slot_mapping.get("evidence_slot_contracts") or [])
    slots_by_chain: dict[str, list[str]] = {}
    for contract in contracts:
        for chain_id in contract.get("judgment_chain_ids") or []:
            slots_by_chain.setdefault(str(chain_id), []).append(str(contract["evidence_row_id"]))

    fixture_slot_ids = _fixture_slot_ids(fixture_report)
    live_slot_ids = _live_attempt_slot_ids(live_report)
    gap_slot_ids = _attempt_backed_gap_slot_ids(live_report)
    gap_ids_by_chain = _attempt_backed_gap_ids_by_chain(live_report)
    chain_results: list[dict[str, Any]] = []
    for chain in chain_registry.get("chains") or []:
        chain_id = str(chain["chain_id"])
        required_slots = slots_by_chain.get(chain_id, [])
        fixture_slots = sorted(set(required_slots).intersection(fixture_slot_ids))
        live_slots = sorted(set(required_slots).intersection(live_slot_ids))
        gap_slots = sorted(set(required_slots).intersection(gap_slot_ids).union(gap_ids_by_chain.get(chain_id, set())))
        missing_slots = [slot for slot in required_slots if slot not in live_slots and slot not in gap_slots]
        status = _chain_audit_status(chain_id, fixture_slots, live_slots, gap_slots)
        chain_results.append(
            {
                "chain_id": chain_id,
                "question_answered": chain.get("question_answered"),
                "fixture_answerability_status": status,
                "required_slot_count": len(required_slots),
                "fixture_supported_slot_count": len(fixture_slots),
                "live_supported_slot_count": len(live_slots),
                "attempt_backed_gap_slot_count": len(gap_slots),
                "fixture_supported_slots": fixture_slots,
                "live_supported_slots": live_slots,
                "attempt_backed_gap_slots": gap_slots,
                "missing_slots": missing_slots,
                "minimum_quality_bar": chain.get("minimum_quality_bar"),
                "writer_must_say": chain.get("writer_must_say"),
                "blocking_reason": _chain_blocking_reason(chain_id, status),
            }
        )

    fail_count = sum(1 for row in chain_results if row["fixture_answerability_status"].startswith("fail"))
    partial_count = sum(1 for row in chain_results if row["fixture_answerability_status"].startswith("partial"))
    pass_count = sum(1 for row in chain_results if row["fixture_answerability_status"].startswith("pass"))
    live_metrics = live_report.get("metrics") or {}
    typed_gap_rows = list(live_report.get("typed_gaps") or [])
    unattempted_slot_count = int(live_metrics.get("unattempted_slot_count") or 0)
    live_fetch_performed = bool(live_metrics.get("perform_network"))
    all_live_gaps_attempt_backed = all(row.get("attempt_backed") is True for row in typed_gap_rows)
    bounded_scoped_writer_ready = (
        live_fetch_performed
        and fail_count == 0
        and unattempted_slot_count == 0
        and route_plan["metrics"]["route_gap_count"] == 0
        and all_live_gaps_attempt_backed
    )
    hard_quality_pass = bounded_scoped_writer_ready and partial_count == 0
    if hard_quality_pass:
        audit_status = "quality_audit_pass_scoped_writer_allowed_full_chain_blocked"
    elif bounded_scoped_writer_ready:
        audit_status = "bounded_quality_audit_pass_scoped_writer_allowed_full_chain_blocked"
    else:
        audit_status = "blocked_live_route_attempt_and_quality_gaps_pending"
    allow_scoped_paid_memo_writer = hard_quality_pass or bounded_scoped_writer_ready
    allow_full_chain = False
    if hard_quality_pass:
        decision_reason = (
            "All P34 AI/Semis judgment chains are live-supported. Scoped paid Memo Writer may run; "
            "broad full-chain/case expansion still requires later projection and human review gates."
        )
    elif bounded_scoped_writer_ready:
        decision_reason = (
            "All P34 AI/Semis source routes have been attempted and no judgment chain fails. "
            "Remaining partial chains are explicit attempt-backed boundaries, so a scoped paid Memo Writer "
            "may write a bounded analyst view; broad full-chain/case expansion remains blocked."
        )
    else:
        decision_reason = (
            "P34 route and adapter fixture contracts exist, but live source attempts and/or judgment-chain "
            "quality boundaries remain incomplete. Paid writer/full-chain remains blocked."
        )
    return {
        "schema_version": P34_NO_PAID_AUDIT_SCHEMA_VERSION,
        "artifact_type": "ai_semis_no_paid_quality_audit",
        "status": audit_status,
        "lane": "AI/Semis",
        "inputs": {
            "source_route_plan_status": route_plan.get("status"),
            "adapter_fixture_report_status": fixture_report.get("status"),
            "slot_contract_ref": _rel(Path(slot_mapping_path)),
            "judgment_chain_ref": _rel(Path(judgment_chain_path)),
        },
        "metrics": {
            "judgment_chain_count": len(chain_results),
            "chain_pass_count": pass_count,
            "chain_partial_count": partial_count,
            "chain_fail_count": fail_count,
            "source_route_gap_count": route_plan["metrics"]["route_gap_count"],
            "adapter_fixture_runtime_row_count": fixture_report["metrics"]["runtime_row_count"],
            "adapter_fixture_rejected_candidate_count": fixture_report["metrics"]["rejected_candidate_count"],
            "live_route_attempt_report_status": live_report.get("status", "not_provided"),
            "live_route_attempt_count": (live_report.get("metrics") or {}).get("attempt_count", 0),
            "accepted_live_runtime_row_count": (live_report.get("metrics") or {}).get("accepted_runtime_row_count", 0),
            "attempt_backed_typed_gap_count": (live_report.get("metrics") or {}).get("typed_gap_count", 0),
            "unattempted_slot_count": unattempted_slot_count,
            "live_fetch_performed": live_fetch_performed,
            "all_live_gaps_attempt_backed": all_live_gaps_attempt_backed,
            "bounded_scoped_writer_ready": bounded_scoped_writer_ready,
            "paid_llm_run": False,
            "full_chain_run": False,
            "allow_paid_memo_writer": allow_scoped_paid_memo_writer,
            "allow_scoped_paid_memo_writer": allow_scoped_paid_memo_writer,
            "allow_full_chain": allow_full_chain,
        },
        "chain_results": chain_results,
        "quality_decision": {
            "allow_paid_memo_writer": allow_scoped_paid_memo_writer,
            "allow_scoped_paid_memo_writer": allow_scoped_paid_memo_writer,
            "allow_full_chain": allow_full_chain,
            "reason": decision_reason,
            "next_required_actions": [
                "if scoped paid writer is run, force bounded language for Dell AI server margin quality and market price-in",
                "keep full-chain/model-comparison/case-expansion blocked until renderer/verifier/Workbench/human review gates pass",
                "continue optional deeper public-source search for Dell AI server mix/pass-through margin bridge",
                "record market exact positioning as commercial/deeper-adapter boundary unless licensed/free exact source is added",
            ],
        },
    }


def build_ai_semis_scoped_writer_payload(
    live_route_attempt_report: Mapping[str, Any] | str | Path | None = None,
    no_paid_quality_audit: Mapping[str, Any] | str | Path | None = None,
    judgment_chain_registry: Mapping[str, Any] | str | Path | None = None,
) -> dict[str, Any]:
    """Build the scoped AI/Semis Memo Writer state from P34 live route rows.

    This is the missing bridge between P34 source-runtime closure and the
    existing Memo Writer node. It deliberately projects accepted runtime rows
    into judgment cards and a MemoLogicPlan instead of handing raw rows to the
    model.
    """

    live_report = _mapping_or_json(live_route_attempt_report, DEFAULT_LIVE_ROUTE_ATTEMPT_REPORT_PATH)
    audit = _mapping_or_json(no_paid_quality_audit, DEFAULT_NO_PAID_QUALITY_AUDIT_PATH)
    chain_registry = _mapping_or_json(judgment_chain_registry, DEFAULT_JUDGMENT_CHAIN_PATH)
    chain_by_id = {str(row.get("chain_id") or ""): dict(row) for row in chain_registry.get("chains") or []}
    audit_by_chain = {str(row.get("chain_id") or ""): dict(row) for row in audit.get("chain_results") or []}
    accepted_rows = [dict(row) for row in live_report.get("accepted_runtime_rows") or [] if isinstance(row, Mapping)]
    typed_gaps = [dict(row) for row in live_report.get("typed_gaps") or [] if isinstance(row, Mapping)]
    analyst_fact_table_blocks = _p34_analyst_fact_table_blocks(accepted_rows, typed_gaps)
    rows_by_slot = _rows_by_evidence_slot(accepted_rows)
    gaps_by_slot = {str(row.get("evidence_row_id") or ""): row for row in typed_gaps}
    gaps_by_chain = _gaps_by_chain(typed_gaps)
    chain_results = [audit_by_chain[chain_id] for chain_id in _p34_chain_order() if chain_id in audit_by_chain]

    supported_claims: list[dict[str, Any]] = []
    judgment_cards: list[dict[str, Any]] = []
    dimension_bucket: dict[str, dict[str, Any]] = {}
    for index, chain_result in enumerate(chain_results, start=1):
        chain_id = str(chain_result.get("chain_id") or "")
        chain = chain_by_id.get(chain_id, {})
        contract = _p34_chain_writer_contract(chain_id)
        row_refs = _unique_texts(chain_result.get("live_supported_slots"))
        gap_refs = _unique_texts(chain_result.get("attempt_backed_gap_slots"))
        claim = _p34_chain_supported_claim(
            chain=chain,
            chain_result=chain_result,
            contract=contract,
            row_refs=row_refs,
            gap_refs=gap_refs,
            rows_by_slot=rows_by_slot,
            gaps_by_slot=gaps_by_slot,
            index=index,
        )
        supported_claims.append(claim)
        card = _p34_judgment_card_from_claim(claim, contract=contract, chain=chain, gap_refs=gap_refs)
        judgment_cards.append(card)
        _accumulate_dimension_judgment(
            dimension_bucket,
            claim=claim,
            card=card,
            contract=contract,
            chain=chain,
            gap_refs=gap_refs,
        )

    dimension_judgments = [_finalize_dimension_row(row) for row in dimension_bucket.values()]
    thesis_path = _p34_thesis_path(judgment_cards)
    judgment_state = {
        "schema_version": "sec_agent_judgment_state_v0.1",
        "status": "ready",
        "required_dimension_ids": [
            "fundamentals",
            "product_and_production",
            "capital_and_financing",
            "industry_supply_chain",
            "risk_and_counterevidence",
        ],
        "dimension_judgments": dimension_judgments,
        "judgment_cards": judgment_cards,
        "thesis_path": thesis_path,
        "supported_claims": supported_claims,
        "typed_gap_refs": _unique_texts(row.get("evidence_row_id") for row in typed_gaps),
    }
    lead_review_checkpoint = _p34_lead_review_checkpoint(
        dimension_judgments=dimension_judgments,
        judgment_cards=judgment_cards,
        typed_gaps=typed_gaps,
        audit=audit,
    )
    required_question_items = _p34_required_question_items(chain_results)
    product_frame = _p34_product_reasoning_frame(chain_results)
    focus_policy = _p34_focus_ticker_policy(supported_claims)
    memo_logic_plan = build_memo_logic_plan(
        judgment_state=judgment_state,
        lead_review_checkpoint=lead_review_checkpoint,
        memo_intent="ai_semis_gold_case_scoped_deep_research_workpaper",
        product_reasoning_frame=product_frame,
        required_question_items=required_question_items,
        focus_ticker_coverage_policy=focus_policy,
    )
    _inject_p34_required_item_answers(memo_logic_plan)
    memo_logic_plan["analyst_fact_table_blocks"] = analyst_fact_table_blocks
    memo_logic_plan["fact_table_render_policy"] = {
        "status": "required_before_required_item_answers",
        "purpose": (
            "Expose financial bridge, product spec, deployment, capex, semicap and market-boundary rows as "
            "tables so the writer does not turn accepted runtime evidence into a boundary-only prose ledger."
        ),
        "value_quality_policy": (
            "Use exact_numeric/specific_spec as data anchors; keep context_summary and attempt_backed_gap "
            "visible but do not promote them to revenue, margin, shipment, ASP or order exact facts."
        ),
    }

    verified_judgment_plan = _p34_verified_judgment_plan(
        supported_claims=supported_claims,
        judgment_cards=judgment_cards,
        judgment_state=judgment_state,
        memo_logic_plan=memo_logic_plan,
        typed_gaps=typed_gaps,
    )
    supervising_pack = _p34_supervising_analyst_pack(
        supported_claims=supported_claims,
        accepted_rows=accepted_rows,
        typed_gaps=typed_gaps,
        chain_results=chain_results,
    )
    supervising_pack["analyst_fact_table_blocks"] = analyst_fact_table_blocks
    case_id = "p34_ai_semis_scoped_writer_case_v0_1"
    state: dict[str, Any] = {
        "schema_version": P34_SCOPED_WRITER_PAYLOAD_SCHEMA_VERSION,
        "artifact_type": "p34_ai_semis_scoped_writer_payload",
        "status": "stopped_after_node",
        "native_stop_after_node": "aggregate_judgment_plan",
        "case_id": case_id,
        "user_query": (
            "请基于 P34 AI/Semis 已验收的公开源 runtime rows，判断 AI 基建需求如何传导到 "
            "NVDA/AMD/GOOGL TPU、DELL AI servers、TSMC/ASML/AMAT/LRCX，以及哪些结论仍被 "
            "DELL 利润质量和 market price-in 数据边界限制。"
        ),
        "response_language": "zh-CN",
        "execution_mode": "deep_research",
        "focus_tickers": ["NVDA", "DELL", "AMD", "GOOGL", "TSM", "ASML", "AMAT", "LRCX"],
        "search_scope_tickers": ["NVDA", "DELL", "AMD", "GOOGL", "MSFT", "AMZN", "META", "TSM", "ASML", "AMAT", "LRCX"],
        "case_contract": {
            "case_id": case_id,
            "prompt": (
                "AI/Semis gold workpaper: answer with product architecture, customer deployment, supply-chain, "
                "Dell financial quality, market price-in and counter-thesis."
            ),
            "execution_mode": "deep_research",
            "focus_tickers": ["NVDA", "DELL", "AMD", "GOOGL", "TSM", "ASML", "AMAT", "LRCX"],
            "required_answer_moves": [
                "open with current bounded investment judgment",
                "separate AI capex demand pool from supplier capture",
                "explain accelerator architecture and substitution",
                "connect deployment/OEM configuration to adoption",
                "separate Dell revenue visibility from margin quality",
                "explain foundry/semicap read-through by mechanism",
                "state market price-in boundary and counter-thesis",
            ],
            "required_dimensions": [
                "fundamentals",
                "product_and_production",
                "capital_and_financing",
                "industry_supply_chain",
                "risk_and_counterevidence",
            ],
        },
        "query_contract": {
            "raw_query": "AI/Semis gold workpaper scoped writer case",
            "response_language": "zh-CN",
            "focus_tickers": ["NVDA", "DELL", "AMD", "GOOGL", "TSM", "ASML", "AMAT", "LRCX"],
        },
        "agent_activation_plan": {
            "schema_version": "p34_scoped_agent_activation_plan_v0_1",
            "execution_mode": "deep_research",
            "focus_tickers": ["NVDA", "DELL", "AMD", "GOOGL", "TSM", "ASML", "AMAT", "LRCX"],
            "allowed_source_families": [
                "p34_live_route_attempt",
                "issuer_primary_disclosure",
                "official_product_surface",
                "official_customer_deployment",
                "market_context",
            ],
            "activated_agents": [
                "research_lead",
                "fundamental_analyst",
                "product_technology_specialist",
                "industry_supply_chain_specialist",
                "market_capital_specialist",
                "risk_counterevidence_analyst",
            ],
        },
        "bounded_answer_allowed": True,
        "multi_agent_reflection_report": {
            "schema_version": "p34_scoped_reflection_report_v0_1",
            "sufficiency_level": "bounded_source_runtime_pass",
            "bounded_answer_allowed": True,
            "missing_requirements": [],
            "typed_gap_count": len(typed_gaps),
        },
        "evidence_sufficiency_report": {
            "schema_version": "p34_scoped_evidence_sufficiency_v0_1",
            "sufficiency_level": "bounded_source_runtime_pass",
            "bounded_answer_allowed": True,
            "missing_requirements": [],
        },
        "bounded_gap_register": _p34_bounded_gap_register(typed_gaps),
        "lead_review_checkpoint": lead_review_checkpoint,
        "supervising_analyst_pack": supervising_pack,
        "evidence_fusion_bundle": _p34_evidence_fusion_bundle(accepted_rows, typed_gaps),
        "analyst_fact_table_blocks": analyst_fact_table_blocks,
        "product_evidence_rows": _p34_product_rows(accepted_rows),
        "public_source_context_rows": _p34_context_rows(accepted_rows),
        "product_intelligence_graph_projection": _p34_product_graph_projection(accepted_rows, supported_claims),
        "verified_judgment_plan": verified_judgment_plan,
        "judgment_plan": verified_judgment_plan,
        "specialist_verification": {
            "schema_version": "p34_specialist_verification_v0_1",
            "status": "pass",
            "memo_writer_allowed": True,
            "verified_judgment_plan": verified_judgment_plan,
            "route_results": [
                {"agent_id": agent_id, "status": "pass", "required_item_scope": "p34_ai_semis_scoped_writer"}
                for agent_id in [
                    "fundamental_analyst",
                    "product_technology_specialist",
                    "industry_supply_chain_specialist",
                    "market_capital_specialist",
                    "risk_counterevidence_analyst",
                ]
            ],
        },
        "memo_logic_plan": memo_logic_plan,
        "p34_scoped_writer_payload": {
            "schema_version": P34_SCOPED_WRITER_PAYLOAD_SCHEMA_VERSION,
            "source_live_route_attempt_report_ref": _rel(DEFAULT_LIVE_ROUTE_ATTEMPT_REPORT_PATH),
            "source_no_paid_quality_audit_ref": _rel(DEFAULT_NO_PAID_QUALITY_AUDIT_PATH),
            "accepted_runtime_row_count": len(accepted_rows),
            "supported_claim_count": len(supported_claims),
            "judgment_chain_count": len(chain_results),
            "typed_gap_count": len(typed_gaps),
            "analyst_fact_table_block_count": len(analyst_fact_table_blocks),
            "analyst_fact_table_row_count": sum(len(block.get("rows") or []) for block in analyst_fact_table_blocks),
            "full_chain_allowed": False,
            "paid_scope": "memo_writer_node_only",
        },
        "not_run": ["full_chain", "model_comparison", "case_expansion", "fresh_retrieval", "new_web_search"],
        "created_at": _utc_now(),
    }
    state["artifact_digest"] = _digest(state)[:24]
    return state


def _mapping_or_json(value: Mapping[str, Any] | str | Path | None, default_path: Path) -> dict[str, Any]:
    if value is None:
        return json.loads(default_path.read_text(encoding="utf-8"))
    if isinstance(value, Mapping):
        return dict(value)
    return json.loads(Path(value).read_text(encoding="utf-8"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _p34_chain_order() -> list[str]:
    return [
        "jc_ai_capex_demand_pool",
        "jc_accelerator_architecture_competition",
        "jc_customer_deployment_oem_adoption",
        "jc_dell_ai_server_financial_quality",
        "jc_foundry_semicap_readthrough",
        "jc_market_price_in_capital_feedback",
        "jc_counter_thesis_what_would_change",
    ]


def _p34_chain_writer_contract(chain_id: str) -> dict[str, Any]:
    contracts: dict[str, dict[str, Any]] = {
        "jc_ai_capex_demand_pool": {
            "required_item_id": "cloud_capex_read_through",
            "dimension_id": "capital_and_financing",
            "memo_slot": "capital_and_financing",
            "agent_id": "market_capital_specialist",
            "ticker_scope": ["MSFT", "AMZN", "GOOGL", "META", "NVDA", "DELL"],
            "claim_type": "demand_pool_context_judgment",
            "economic_role": "customer_or_demand_side_capex_signal",
            "transmission_role": "demand_pool_to_supplier_capture_requires_deployment_or_order_bridge",
            "source_role": "hyperscaler_capex_and_data_center_demand_context",
            "judgment": (
                "AI capex is a real demand pool, but it only becomes supplier revenue evidence after a named "
                "deployment, customer order, OEM configuration, or supplier allocation bridge."
            ),
            "answer": (
                "Hyperscaler capex rows support AI infrastructure demand, but they do not prove Dell/NVIDIA/semicap "
                "supplier capture without deployment, product, order or financial bridge evidence."
            ),
            "cannot_infer": "Supplier allocation, OEM order conversion, or AI server margin from cloud capex alone.",
            "what_would_change": "Named procurement, supplier allocation, cloud instance deployment, or order/backlog conversion rows.",
        },
        "jc_accelerator_architecture_competition": {
            "required_item_id": "req_accelerator_architecture",
            "dimension_id": "product_and_production",
            "memo_slot": "product_and_production",
            "agent_id": "product_technology_specialist",
            "ticker_scope": ["NVDA", "AMD", "GOOGL", "DELL"],
            "claim_type": "product_architecture_competitive_judgment",
            "economic_role": "product_capability_and_substitution_signal",
            "transmission_role": "architecture_to_supply_bottleneck_to_oem_or_cloud_adoption",
            "source_role": "official_product_spec_benchmark_and_oem_configuration",
            "judgment": (
                "NVIDIA retains the strongest external accelerator-system bottleneck signal through GB200/NVL72 "
                "rack-scale architecture and OEM/cloud deployment surfaces, while AMD and Google TPU are real "
                "substitution checks but not revenue/share proof."
            ),
            "answer": (
                "Architecture/spec/benchmark/deployment evidence can support product capability and substitution risk "
                "without SKU revenue. NVIDIA GB200/NVL72, AMD MI300X/MI355X and Google TPU/A4X should be compared on "
                "system architecture, memory, benchmark/deployment surface and software/ecosystem boundary."
            ),
            "cannot_infer": "SKU revenue, ASP, unit shipment, share, or Google internal TPU economics.",
            "what_would_change": "Customer deployment scale, allocation evidence, benchmark breadth, or product-level demand disclosures.",
        },
        "jc_customer_deployment_oem_adoption": {
            "required_item_id": "req_customer_deployment",
            "dimension_id": "product_and_production",
            "memo_slot": "product_and_production",
            "agent_id": "product_technology_specialist",
            "ticker_scope": ["DELL", "GOOGL", "NVDA"],
            "claim_type": "customer_deployment_adoption_judgment",
            "economic_role": "official_deployment_or_oem_configuration_signal",
            "transmission_role": "product_capability_to_adoption_signal_not_margin_or_total_order_value",
            "source_role": "official_customer_deployment_oem_configuration",
            "judgment": (
                "Dell PowerEdge/AI Factory and Google A4X surfaces confirm adoption paths for NVIDIA GB200-class "
                "infrastructure, but they still do not prove customer concentration, total order value or Dell margin."
            ),
            "answer": (
                "Official OEM configuration and cloud deployment rows convert product capability into adoption evidence; "
                "they should be linked to Dell orders/backlog where available, but not treated as total sales or margin proof."
            ),
            "cannot_infer": "Deployment quantity, customer concentration, purchase volume, or gross margin.",
            "what_would_change": "Named customer deployment, GA capacity, configuration mix, or order value disclosure.",
        },
        "jc_dell_ai_server_financial_quality": {
            "required_item_id": "req_dell_margin_quality",
            "dimension_id": "fundamentals",
            "memo_slot": "fundamentals",
            "agent_id": "fundamental_analyst",
            "ticker_scope": ["DELL"],
            "claim_type": "financial_quality_bridge_judgment",
            "economic_role": "issuer_orders_backlog_and_segment_margin_context",
            "transmission_role": "orders_to_revenue_visibility_but_margin_quality_requires_mix_pass_through_backlog_conversion",
            "source_role": "issuer_primary_disclosure_and_segment_margin",
            "judgment": (
                "Dell has AI server revenue visibility through orders, shipments, backlog and ISG baseline margin, "
                "but public rows still do not close AI server margin quality, GPU pass-through cost, mix or backlog conversion."
            ),
            "answer": (
                "Dell AI server growth is better supported as revenue tailwind than as confirmed profit-quality improvement. "
                "The key bridge is AI server mix, GPU pass-through cost, attach rate, backlog conversion and ISG margin."
            ),
            "cannot_infer": "AI server gross margin improvement or high-quality profit without mix/pass-through/conversion bridge.",
            "what_would_change": "Company-disclosed AI server mix, gross margin, backlog conversion, customer mix or GPU cost pass-through.",
        },
        "jc_foundry_semicap_readthrough": {
            "required_item_id": "req_supply_chain",
            "dimension_id": "industry_supply_chain",
            "memo_slot": "industry_supply_chain",
            "agent_id": "industry_supply_chain_specialist",
            "ticker_scope": ["TSM", "ASML", "AMAT", "LRCX"],
            "claim_type": "semicap_readthrough_judgment",
            "economic_role": "supply_chain_and_equipment_cycle_signal",
            "transmission_role": "ai_accelerator_demand_to_foundry_packaging_hbm_and_wfe_process_intensity",
            "source_role": "semicap_primary_disclosure_and_process_intensity_context",
            "judgment": (
                "AI demand reads through semicap only by vendor mechanism: TSM advanced node/HPC, ASML lithography and "
                "installed base, AMAT Semiconductor Systems mix, and LRCX memory/HBM process intensity."
            ),
            "answer": (
                "Semicap read-through must split the mechanism by company rather than call all peers the same. "
                "AI demand can support WFE/process-intensity context, but broad revenue/margin cannot prove AI-specific orders."
            ),
            "cannot_infer": "AI-specific order value, exact customer allocation, HBM tool share, or shipment cycle magnitude.",
            "what_would_change": "Parsed bookings/backlog, EUV/DUV systems, China exposure, customer concentration or shipment tracker rows.",
        },
        "jc_market_price_in_capital_feedback": {
            "required_item_id": "req_market_price_in",
            "dimension_id": "capital_and_financing",
            "memo_slot": "market_valuation",
            "agent_id": "market_capital_specialist",
            "ticker_scope": ["NVDA", "DELL", "AMD", "GOOGL", "ASML", "AMAT", "LRCX"],
            "claim_type": "market_price_in_boundary_judgment",
            "economic_role": "market_context_and_positioning_boundary",
            "transmission_role": "business_evidence_to_risk_reward_requires_valuation_positioning_and_flow_confirmation",
            "source_role": "market_price_and_liquidity_context",
            "judgment": (
                "The business chain is positive but price-in quality remains bounded because public context lacks exact "
                "crowding, options, borrow cost and institutional-flow evidence."
            ),
            "answer": (
                "Business evidence alone is not an investment recommendation. Without exact valuation, positioning, "
                "short/options, flow and event-reaction rows, market price-in should remain bounded."
            ),
            "cannot_infer": "Strong buy/sell recommendation, real-time fund flow, complete options positioning or borrow cost.",
            "what_would_change": "Valuation percentile, ownership/ETF flow, short/options positioning, borrow cost or event reaction evidence.",
        },
        "jc_counter_thesis_what_would_change": {
            "required_item_id": "req_counter_thesis",
            "dimension_id": "risk_and_counterevidence",
            "memo_slot": "risk_and_counterevidence",
            "agent_id": "risk_counterevidence_analyst",
            "ticker_scope": ["NVDA", "DELL", "AMD", "GOOGL", "META", "ASML", "LRCX"],
            "claim_type": "counter_thesis_monitoring_judgment",
            "economic_role": "counter_thesis_and_decision_change_signal",
            "transmission_role": "risk_factors_that_can_break_product_demand_financial_quality_or_market_price_in",
            "source_role": "independent_counter_thesis_pack",
            "judgment": (
                "The strongest counter-thesis is not generic AI risk: it is capex digestion, Dell margin dilution, "
                "AMD/TPU substitution, NVIDIA supply delay, export control, semicap order lag and market crowding."
            ),
            "answer": (
                "A credible AI/Semis workpaper must state what would change the view: capex cuts, deployment delays, "
                "margin deterioration, substitution success, supply bottlenecks, export controls or price-in evidence."
            ),
            "cannot_infer": "Revenue impact magnitude or market-share change from counter-thesis context alone.",
            "what_would_change": "Evidence of capex cuts, delayed deployment, margin deterioration, supply relief or less crowded positioning.",
        },
    }
    return contracts.get(chain_id, contracts["jc_counter_thesis_what_would_change"])


def _rows_by_evidence_slot(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        slot = str(row.get("evidence_row_id") or "")
        if slot:
            result.setdefault(slot, []).append(row)
    return result


def _gaps_by_chain(gaps: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for gap in gaps:
        for chain_id in gap.get("judgment_chain_ids") or []:
            result.setdefault(str(chain_id), []).append(gap)
    return result


def _p34_chain_supported_claim(
    *,
    chain: Mapping[str, Any],
    chain_result: Mapping[str, Any],
    contract: Mapping[str, Any],
    row_refs: list[str],
    gap_refs: list[str],
    rows_by_slot: Mapping[str, list[dict[str, Any]]],
    gaps_by_slot: Mapping[str, dict[str, Any]],
    index: int,
) -> dict[str, Any]:
    chain_id = str(chain_result.get("chain_id") or chain.get("chain_id") or "")
    rows = [row for ref in row_refs for row in rows_by_slot.get(ref, [])]
    gap_rows = [gaps_by_slot[ref] for ref in gap_refs if ref in gaps_by_slot]
    confidence = "medium_high" if str(chain_result.get("fixture_answerability_status") or "").startswith("pass") else "bounded_medium"
    return {
        "claim_id": f"p34_judgment_claim::{chain_id}",
        "claim": str(contract.get("judgment") or chain.get("writer_must_say") or ""),
        "claim_type": str(contract.get("claim_type") or "bounded_judgment"),
        "claim_rank_bucket": "memo_ready",
        "claim_rank_score": 90 if confidence == "medium_high" else 72,
        "memo_slot": str(contract.get("memo_slot") or "thesis"),
        "analysis_dimension": str(contract.get("dimension_id") or ""),
        "required_item_answered": str(contract.get("required_item_id") or chain_id),
        "question_answered": str(chain.get("question_answered") or chain_result.get("question_answered") or ""),
        "direction": "positive_with_boundary" if gap_refs else "positive_context",
        "confidence": confidence,
        "ticker_scope": _unique_texts(contract.get("ticker_scope")),
        "metric_scope": _unique_texts(row.get("metric_or_attribute") for row in rows)[:8],
        "product_scope": _unique_texts(row.get("product_or_family") for row in rows)[:8],
        "evidence_refs": row_refs[:10],
        "gap_refs": gap_refs[:4],
        "source_families": ["p34_live_runtime_row", str(contract.get("source_role") or "")],
        "scope_role": str(contract.get("source_role") or ""),
        "economic_role": str(contract.get("economic_role") or ""),
        "transmission_role": str(contract.get("transmission_role") or ""),
        "memo_use_role": str(contract.get("answer") or ""),
        "role_boundary": str(contract.get("cannot_infer") or ""),
        "business_mechanism": str(chain.get("business_mechanism") or ""),
        "financial_bridge": _p34_financial_bridge_for_chain(chain_id),
        "counter_read": "; ".join(_unique_texts(chain.get("counter_evidence_roles")))[:260],
        "what_would_change_view": [str(contract.get("what_would_change") or "")],
        "authority_boundary": _authority_boundary_summary(rows, gap_rows, contract),
        "cannot_infer": [str(contract.get("cannot_infer") or ""), *_cannot_infer_from_rows(rows), *_gap_boundaries(gap_rows)][:8],
        "display_evidence_summaries": _display_evidence_summaries(rows)[:6],
        "source_boundary_notes": _source_boundary_notes(rows, gap_rows)[:5],
        "chain_status": str(chain_result.get("fixture_answerability_status") or ""),
        "chain_order": index,
        "unsupported": False,
    }


def _p34_judgment_card_from_claim(
    claim: Mapping[str, Any],
    *,
    contract: Mapping[str, Any],
    chain: Mapping[str, Any],
    gap_refs: list[str],
) -> dict[str, Any]:
    return {
        "judgment_card_id": f"p34_judgment_card::{claim.get('required_item_answered')}",
        "source_claim_id": str(claim.get("claim_id") or ""),
        "dimension_id": str(claim.get("analysis_dimension") or ""),
        "judgment": str(claim.get("claim") or ""),
        "evidence_bridge": str(contract.get("answer") or ""),
        "business_mechanism": str(chain.get("business_mechanism") or ""),
        "financial_bridge": str(claim.get("financial_bridge") or ""),
        "counter_read": str(claim.get("counter_read") or ""),
        "what_would_change_view": _unique_texts(claim.get("what_would_change_view")),
        "evidence_refs": _unique_texts(claim.get("evidence_refs")),
        "gap_refs": gap_refs[:4],
        "authority_boundary": str(claim.get("authority_boundary") or ""),
        "source_role": str(contract.get("source_role") or ""),
        "mechanism_bridge_status": "partial_with_typed_gap" if gap_refs else "supported",
    }


def _accumulate_dimension_judgment(
    bucket: dict[str, dict[str, Any]],
    *,
    claim: Mapping[str, Any],
    card: Mapping[str, Any],
    contract: Mapping[str, Any],
    chain: Mapping[str, Any],
    gap_refs: list[str],
) -> None:
    dimension_id = str(contract.get("dimension_id") or "")
    if not dimension_id:
        return
    row = bucket.setdefault(
        dimension_id,
        {
            "dimension_id": dimension_id,
            "title": _p34_dimension_title(dimension_id),
            "stance": "supported",
            "support_level": "high",
            "summary_parts": [],
            "business_mechanism_parts": [],
            "financial_bridge_parts": [],
            "counter_read_parts": [],
            "claim_ids": [],
            "judgment_card_ids": [],
            "evidence_refs": [],
            "gap_ids": [],
            "what_would_change_view": [],
        },
    )
    row["claim_ids"].append(str(claim.get("claim_id") or ""))
    row["judgment_card_ids"].append(str(card.get("judgment_card_id") or ""))
    row["evidence_refs"].extend(_unique_texts(claim.get("evidence_refs")))
    row["gap_ids"].extend(gap_refs)
    row["summary_parts"].append(str(claim.get("claim") or ""))
    row["business_mechanism_parts"].append(str(chain.get("business_mechanism") or ""))
    row["financial_bridge_parts"].append(str(claim.get("financial_bridge") or ""))
    row["counter_read_parts"].append(str(claim.get("counter_read") or ""))
    row["what_would_change_view"].extend(_unique_texts(claim.get("what_would_change_view")))
    if gap_refs:
        row["stance"] = "supported_with_boundary"
        row["support_level"] = "medium"


def _finalize_dimension_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "dimension_id": str(row.get("dimension_id") or ""),
        "title": str(row.get("title") or ""),
        "stance": str(row.get("stance") or "supported"),
        "support_level": str(row.get("support_level") or "medium"),
        "summary": " ".join(_unique_texts(row.get("summary_parts")))[:900],
        "business_mechanism": " ".join(_unique_texts(row.get("business_mechanism_parts")))[:700],
        "financial_bridge": " ".join(_unique_texts(row.get("financial_bridge_parts")))[:700],
        "counter_read": " ".join(_unique_texts(row.get("counter_read_parts")))[:600],
        "claim_ids": _unique_texts(row.get("claim_ids"))[:8],
        "judgment_card_ids": _unique_texts(row.get("judgment_card_ids"))[:8],
        "evidence_refs": _unique_texts(row.get("evidence_refs"))[:12],
        "gap_ids": _unique_texts(row.get("gap_ids"))[:6],
        "decision_changing_evidence_refs": _unique_texts(row.get("evidence_refs"))[:8],
        "counter_thesis_refs": _unique_texts(row.get("gap_ids"))[:6],
        "what_would_change_view": _unique_texts(row.get("what_would_change_view"))[:5],
    }


def _p34_dimension_title(dimension_id: str) -> str:
    return {
        "fundamentals": "Fundamental / financial quality",
        "product_and_production": "Product architecture, deployment and adoption",
        "capital_and_financing": "Capital demand, market price-in and feedback",
        "industry_supply_chain": "Foundry, packaging, HBM and semicap read-through",
        "risk_and_counterevidence": "Counter-thesis and what would change the view",
    }.get(dimension_id, dimension_id)


def _p34_financial_bridge_for_chain(chain_id: str) -> str:
    return {
        "jc_ai_capex_demand_pool": "Capex supports demand-pool context; supplier revenue needs product/deployment/order bridge.",
        "jc_accelerator_architecture_competition": "Product capability can support adoption and bargaining-power analysis, not SKU revenue by itself.",
        "jc_customer_deployment_oem_adoption": "Deployment/OEM configuration links product capability to adoption but not total sales or margin.",
        "jc_dell_ai_server_financial_quality": "Orders/backlog and ISG margin provide visibility; AI server mix/pass-through/conversion remain the margin-quality bridge.",
        "jc_foundry_semicap_readthrough": "AI demand can transmit through advanced node, packaging, HBM and WFE process intensity by vendor mechanism.",
        "jc_market_price_in_capital_feedback": "Investment recommendation requires valuation/positioning/liquidity/flow evidence beyond business fundamentals.",
        "jc_counter_thesis_what_would_change": "Counter evidence defines when the current thesis should be downgraded or upgraded.",
    }.get(chain_id, "")


P34_ANALYST_FACT_TABLE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "block_id": "financial_bridge_table",
        "title_zh": "财务桥与利润质量锚点",
        "title_en": "Financial bridge and margin-quality anchors",
        "description_zh": (
            "这些 row 用来判断 DELL / NVDA / AWS 等经营锚点与利润质量；其中摘要型 row 只能说明披露路径或上下文，"
            "不能替代 AI server gross margin、GPU pass-through、SKU revenue 或订单 exact。"
        ),
        "slots": {
            "dell_ai_server_orders_shipments_backlog",
            "dell_isg_revenue_margin_baseline",
            "nvda_data_center_revenue_demand_confirmation",
            "amzn_aws_demand_pool_context",
        },
    },
    {
        "block_id": "product_spec_architecture_table",
        "title_zh": "产品规格、架构与性能 proxy",
        "title_en": "Product specs, architecture and performance proxies",
        "description_zh": (
            "这些 row 是产品竞争力判断的直接材料：可以比较架构、内存、带宽、benchmark 和系统形态，"
            "但不能外推收入、ASP、出货量或份额。"
        ),
        "slots": {
            "nvda_gb200_nvl72_rack_architecture",
            "amd_mi300x_memory_bandwidth_competition",
            "google_tpu_v6e_trillium_architecture",
            "amd_mlperf_mi355x_performance_proxy",
        },
    },
    {
        "block_id": "customer_deployment_oem_table",
        "title_zh": "客户部署、OEM 配置与采用路径",
        "title_en": "Customer deployment, OEM configuration and adoption path",
        "description_zh": (
            "这些 row 证明产品进入云实例、OEM 配置或官方部署路径；可以支持采用存在和 read-through，"
            "不能推出部署规模、客户集中度、单客户收入或 DELL margin。"
        ),
        "slots": {
            "dell_nvidia_poweredge_ai_factory_product_path",
            "dell_xe9712_gb200_oem_system_config",
            "google_a4x_gb200_cloud_deployment_surface",
        },
    },
    {
        "block_id": "capex_demand_pool_table",
        "title_zh": "云厂商 capex 与需求池",
        "title_en": "Hyperscaler capex and demand-pool evidence",
        "description_zh": (
            "这些 row 支撑 AI infrastructure 需求池，但只有连到客户部署、订单、产品配置或供应商 allocation "
            "时才可上升为供应商收入/订单判断。"
        ),
        "slots": {
            "msft_cloud_ai_capex_supply_shortfall",
            "alphabet_capex_server_chain_context",
            "meta_capex_component_pricing_risk",
        },
    },
    {
        "block_id": "semicap_readthrough_table",
        "title_zh": "Foundry / semicap read-through",
        "title_en": "Foundry / semicap read-through",
        "description_zh": (
            "这些 row 用来判断 AI 需求向 advanced node、光刻、材料工程、HBM/封装工艺强度的传导；"
            "不能直接替代 AI-specific booking、customer allocation 或 shipment tracker。"
        ),
        "slots": {
            "tsmc_advanced_node_hpc_ai_readthrough",
            "asml_lithography_installed_base_readthrough",
            "amat_semiconductor_systems_mix",
            "lrcx_memory_hbm_process_intensity",
        },
    },
    {
        "block_id": "market_counter_boundary_table",
        "title_zh": "市场 price-in 与反证边界",
        "title_en": "Market price-in and counter-thesis boundaries",
        "description_zh": (
            "这些 row 只支持市场预期、拥挤度、反证和风险路径的有边界讨论；不能给出实时资金流、完整期权仓位、"
            "borrow cost 或买卖建议。"
        ),
        "slots": {
            "market_price_in_valuation_positioning_gap",
            "counter_thesis_pack_ai_semis",
        },
    },
)


def _p34_analyst_fact_table_blocks(
    accepted_rows: list[dict[str, Any]],
    typed_gaps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows_by_slot: dict[str, list[dict[str, Any]]] = {}
    for row in accepted_rows:
        slot = str(row.get("evidence_row_id") or "").strip()
        if slot:
            rows_by_slot.setdefault(slot, []).append(row)

    blocks: list[dict[str, Any]] = []
    covered_slots: set[str] = set()
    for definition in P34_ANALYST_FACT_TABLE_DEFINITIONS:
        table_rows: list[dict[str, Any]] = []
        for slot in definition["slots"]:
            for row in rows_by_slot.get(slot, []):
                table_rows.append(_p34_analyst_fact_table_row(row, block_id=str(definition["block_id"])))
                covered_slots.add(slot)
        if table_rows:
            blocks.append(
                {
                    "block_id": str(definition["block_id"]),
                    "title_zh": str(definition["title_zh"]),
                    "title_en": str(definition["title_en"]),
                    "description_zh": str(definition["description_zh"]),
                    "rows": table_rows,
                }
            )

    unmatched_rows = [
        _p34_analyst_fact_table_row(row, block_id="other_accepted_runtime_rows")
        for row in accepted_rows
        if str(row.get("evidence_row_id") or "") not in covered_slots
    ]
    if unmatched_rows:
        blocks.append(
            {
                "block_id": "other_accepted_runtime_rows",
                "title_zh": "其他已接入 runtime rows",
                "title_en": "Other accepted runtime rows",
                "description_zh": "这些 row 已被 route/parser 接入，但未进入当前 P34 AI/Semis 主分析表；只能按 authority_scope 使用。",
                "rows": unmatched_rows,
            }
        )

    gap_rows = [_p34_attempt_backed_gap_table_row(row) for row in typed_gaps]
    if gap_rows:
        blocks.append(
            {
                "block_id": "attempt_backed_gap_table",
                "title_zh": "已尝试但仍缺的 exact slot",
                "title_en": "Attempt-backed exact-slot gaps",
                "description_zh": (
                    "这些不是未查找，而是已有 route attempt 后仍未形成可提权 exact row；writer 只能把它们写成决策缺口，"
                    "不能伪装为公开源缺失或已补齐数据。"
                ),
                "rows": gap_rows,
            }
        )
    return blocks


def _p34_analyst_fact_table_row(row: Mapping[str, Any], *, block_id: str) -> dict[str, Any]:
    return {
        "block_id": block_id,
        "evidence_ref": str(row.get("evidence_row_id") or row.get("row_id") or ""),
        "ticker": str(row.get("issuer") or row.get("ticker") or ""),
        "product_or_segment": str(row.get("product_or_family") or ""),
        "metric_or_attribute": str(row.get("metric_or_attribute") or ""),
        "metric_label": _p34_metric_label(str(row.get("metric_or_attribute") or "")),
        "display_value": _display_value_for_row(row),
        "value_quality": _p34_value_quality(row),
        "unit": str(row.get("unit") or ""),
        "period_or_version": str(row.get("period_or_version") or ""),
        "source_url": str(row.get("source_url") or ""),
        "authority_scope": str(row.get("authority_scope") or ""),
        "cannot_infer": _unique_texts(row.get("cannot_infer"))[:4],
        "evidence_refs": _unique_texts([row.get("evidence_row_id") or row.get("row_id")])[:1],
    }


def _p34_attempt_backed_gap_table_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "block_id": "attempt_backed_gap_table",
        "evidence_ref": str(row.get("evidence_row_id") or row.get("gap_id") or ""),
        "ticker": str(row.get("issuer") or row.get("ticker") or ""),
        "product_or_segment": str(row.get("product_or_family") or row.get("required_product_or_family") or ""),
        "metric_or_attribute": str(row.get("metric_or_attribute") or row.get("required_metric") or row.get("gap_type") or ""),
        "metric_label": _p34_metric_label(str(row.get("metric_or_attribute") or row.get("required_metric") or "")),
        "display_value": str(row.get("failure_reason") or row.get("reason") or row.get("gap_type") or "attempt-backed gap"),
        "value_quality": "attempt_backed_gap",
        "unit": "",
        "period_or_version": str(row.get("period_or_version") or row.get("period") or ""),
        "source_url": str(row.get("source_url") or row.get("attempted_source_url") or ""),
        "authority_scope": str(row.get("authority_scope") or "attempt-backed typed gap"),
        "cannot_infer": _unique_texts(row.get("cannot_infer") or row.get("cannot_infer_from_gap"))[:4],
        "evidence_refs": _unique_texts([row.get("evidence_row_id") or row.get("gap_id")])[:1],
    }


def _p34_metric_label(metric: str) -> str:
    text = str(metric or "").strip()
    mapping = {
        "orders_shipments_backlog": "AI server orders / shipments / backlog disclosure",
        "isg_revenue_operating_income_margin": "ISG revenue / operating income / margin",
        "data_center_revenue": "Data Center segment revenue",
        "aws_revenue_operating_income": "AWS revenue / operating income",
        "rack_scale_architecture": "GB200 NVL72 rack-scale architecture",
        "accelerator_memory_bandwidth_spec": "Accelerator memory / bandwidth specification",
        "custom_accelerator_architecture_spec": "TPU architecture specification",
        "mlperf_inference_performance_proxy": "MLPerf inference performance proxy",
        "official_oem_product_path": "Official OEM product path",
        "oem_system_configuration": "OEM system configuration",
        "cloud_deployment_surface": "Cloud deployment surface",
        "cloud_ai_capex_context": "Cloud / AI capex context",
        "technical_infrastructure_capex_context": "Technical infrastructure capex context",
        "ai_infrastructure_capex_and_component_cost_risk": "AI infra capex and component cost risk",
        "advanced_node_revenue_margin": "Advanced node / HPC revenue-mix context",
        "lithography_cycle_disclosure": "Lithography cycle disclosure",
        "equipment_segment_mix": "Equipment segment mix",
        "memory_hbm_process_intensity_context": "Memory / HBM process-intensity context",
        "market_price_in_capital_feedback_context": "Market price-in / capital-feedback context",
        "independent_counter_thesis_context": "Independent counter-thesis context",
    }
    return mapping.get(text, text.replace("_", " ").strip())


def _p34_value_quality(row: Mapping[str, Any]) -> str:
    value = str(row.get("value") or row.get("display_value") or "")
    unit = str(row.get("unit") or "").lower()
    metric = str(row.get("metric_or_attribute") or "").lower()
    lower_value = value.lower()
    if any(token in metric for token in ("counter_thesis", "market_price_in", "capital_feedback_context")):
        return "context_summary"
    if any(
        token in metric
        for token in ("architecture", "spec", "bandwidth", "configuration", "deployment", "mlperf", "product_path")
    ):
        return "specific_technical_or_deployment_fact"
    if any(token in metric for token in ("revenue", "margin", "orders", "shipments", "backlog", "operating_income")):
        return "structured_metric_context" if ("usd" in unit or "percent" in unit or value) else "context_summary"
    if re.search(r"\d", value) and any(token in lower_value for token in ("gb", "tb/s", "gpu", "cpu", "%", "$")):
        return "specific_numeric_or_spec"
    if "usd" in unit or "percent" in unit:
        return "structured_metric_context"
    return "context_summary"


def _p34_required_question_items(chain_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for chain_result in chain_results:
        chain_id = str(chain_result.get("chain_id") or "")
        contract = _p34_chain_writer_contract(chain_id)
        rows.append(
            {
                "question_item_id": str(contract.get("required_item_id") or chain_id),
                "dimension": str(contract.get("dimension_id") or ""),
                "required_tickers": _unique_texts(contract.get("ticker_scope"))[:12],
                "required_evidence_roles": _unique_texts(chain_result.get("live_supported_slots"))[:10],
                "minimum_answer_status": "answered_with_boundary" if chain_result.get("attempt_backed_gap_slots") else "answered",
                "answer_contract": str(contract.get("answer") or ""),
                "terms_any": [
                    str(chain_result.get("question_answered") or ""),
                    str(contract.get("source_role") or ""),
                    str(contract.get("economic_role") or ""),
                ],
            }
        )
    return rows


def _inject_p34_required_item_answers(plan: dict[str, Any]) -> None:
    by_item = {
        str(contract.get("required_item_id") or ""): contract
        for contract in (_p34_chain_writer_contract(chain_id) for chain_id in _p34_chain_order())
    }
    for row in plan.get("required_item_answer_plan") or []:
        if not isinstance(row, dict):
            continue
        contract = by_item.get(str(row.get("question_item_id") or ""))
        if not contract:
            continue
        row["answer"] = str(contract.get("answer") or "")
        row["cannot_infer"] = str(contract.get("cannot_infer") or "")
        row["what_would_change_view"] = str(contract.get("what_would_change") or "")
        row["minimum_rendered_standard"] = (
            "Must give the current bounded judgment, explain the business mechanism, cite evidence refs, "
            "and state the exact boundary; generic monitoring language is not sufficient."
        )


def _p34_product_reasoning_frame(chain_results: list[dict[str, Any]]) -> dict[str, Any]:
    live_slots = _unique_texts(ref for row in chain_results for ref in row.get("live_supported_slots") or [])
    return {
        "schema_version": "finsight_p34_product_reasoning_frame_v0_1",
        "coverage_roles": [
            "product_profile",
            "product_spec_architecture",
            "customer_deployment",
            "performance_proxy",
            "relationship_graph",
            "product_kpi_exact_boundary",
        ],
        "product_profile_refs": [ref for ref in live_slots if any(term in ref for term in ("nvda", "amd", "google", "dell"))][:8],
        "product_spec_refs": [ref for ref in live_slots if any(term in ref for term in ("gb200", "mi300", "tpu", "mlperf"))][:8],
        "deployment_refs": [ref for ref in live_slots if any(term in ref for term in ("deployment", "oem", "poweredge", "a4x"))][:8],
        "performance_proxy_refs": [ref for ref in live_slots if "mlperf" in ref][:4],
        "relationship_edge_refs": [
            "NVDA -> supplies_architecture_to -> DELL PowerEdge/AI Factory",
            "GOOGL A4X -> deploys -> NVIDIA GB200 cloud surface",
            "TSM/ASML/AMAT/LRCX -> read_through_to -> AI accelerator supply chain",
        ],
        "required_reasoning_edges": [
            "AI capex -> product capability / supply -> customer deployment -> OEM revenue visibility",
            "accelerator architecture -> substitution risk -> supplier capture boundary",
            "Dell orders/backlog -> ISG baseline -> margin-quality gap",
            "AI accelerator demand -> advanced node / packaging / HBM -> semicap process intensity",
        ],
        "writer_instruction": (
            "Product analysis must not stop at missing SKU revenue. Use spec, architecture, deployment, OEM configuration, "
            "benchmark/proxy and graph edges to judge capability and adoption, then separately state exact KPI gaps."
        ),
    }


def _p34_focus_ticker_policy(supported_claims: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker: dict[str, list[str]] = {}
    for claim in supported_claims:
        for ticker in _unique_texts(claim.get("ticker_scope")):
            by_ticker.setdefault(ticker, []).append(str(claim.get("claim_id") or ""))
    return {
        "schema_version": "finsight_focus_ticker_coverage_policy_v0_1",
        "policy": "Do not say a focus ticker has no data when P34 supported claims or accepted runtime rows exist.",
        "focus_tickers": sorted(by_ticker.keys()),
        "ticker_policies": [
            {
                "ticker": ticker,
                "coverage_status": "has_supported_p34_claims",
                "do_not_say_no_data": True,
                "supported_claim_ids": claims[:4],
                "policy_note": "Use supported claims with their exact source boundary.",
            }
            for ticker, claims in sorted(by_ticker.items())
        ],
    }


def _p34_thesis_path(judgment_cards: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = []
    for card in judgment_cards:
        nodes.append(
            {
                "node_id": str(card.get("judgment_card_id") or ""),
                "dimension_id": str(card.get("dimension_id") or ""),
                "judgment_card_ids": [str(card.get("judgment_card_id") or "")],
                "claim_ids": [str(card.get("source_claim_id") or "")],
                "evidence_refs": _unique_texts(card.get("evidence_refs"))[:5],
                "business_mechanism": str(card.get("business_mechanism") or ""),
                "financial_bridge": str(card.get("financial_bridge") or ""),
                "counter_read": str(card.get("counter_read") or ""),
                "node_status": str(card.get("mechanism_bridge_status") or ""),
            }
        )
    return {
        "schema_version": "finsight_p34_thesis_path_v0_1",
        "status": "ready",
        "primary_thesis": (
            "AI infrastructure evidence is strongest as a product/deployment/supply-chain thesis; Dell margin quality "
            "and market price-in remain the two explicit boundaries."
        ),
        "mechanism_bridge_status": "supported_with_two_attempt_backed_boundaries",
        "path_nodes": nodes,
        "path_edges": [
            {
                "edge_id": "p34_edge::capex_to_product_deployment",
                "from_node_id": "p34_judgment_card::cloud_capex_read_through",
                "to_node_id": "p34_judgment_card::req_customer_deployment",
                "edge_type": "demand_pool_requires_deployment_bridge",
                "mechanism": "Hyperscaler capex needs customer/deployment/OEM rows before supplier capture.",
                "evidence_refs": ["msft_cloud_ai_capex_supply_shortfall", "google_a4x_gb200_cloud_deployment_surface"],
            },
            {
                "edge_id": "p34_edge::deployment_to_dell_margin_quality",
                "from_node_id": "p34_judgment_card::req_customer_deployment",
                "to_node_id": "p34_judgment_card::req_dell_margin_quality",
                "edge_type": "adoption_to_financial_quality_bridge",
                "mechanism": "Dell deployment/orders support revenue visibility; margin quality requires mix/pass-through/conversion.",
                "evidence_refs": ["dell_ai_server_orders_shipments_backlog", "dell_isg_revenue_margin_baseline"],
            },
        ],
        "writer_instruction": "Write along this causal path before listing gaps.",
    }


def _p34_lead_review_checkpoint(
    *,
    dimension_judgments: list[dict[str, Any]],
    judgment_cards: list[dict[str, Any]],
    typed_gaps: list[dict[str, Any]],
    audit: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "finsight_p34_lead_review_checkpoint_v0_1",
        "status": "pass",
        "memo_directive": {
            "memo_stance": (
                "Lead with a bounded but useful judgment: AI infrastructure demand is credible and product/deployment "
                "evidence supports the chain, while Dell margin quality and price-in remain explicit boundaries."
            ),
            "objective_satisfaction": {
                "status": "bounded_pass",
                "missing_required_item_count": len(typed_gaps),
                "required_item_coverage": "seven_chains_answered_two_attempt_backed_boundaries",
            },
            "opening_policy": "judgment_first_not_gap_first",
            "gap_budget_policy": {
                "max_gap_share_in_user_memo": 0.2,
                "allowed_gap_placement": "main body only where decision-changing; otherwise evidence_gaps_but_actionable",
                "required_gap_tone": "attempt-backed boundary, not generic inability",
            },
            "product_output_contract": {
                "required_user_facing_shape": [
                    "product/spec/architecture first",
                    "deployment/OEM configuration",
                    "supply-chain read-through",
                    "exact KPI boundary separated",
                ],
                "missing_source_boundary": "Missing SKU revenue does not invalidate product analysis.",
                "forbidden_fallback": "Do not say product layer cannot be judged because SKU revenue is absent.",
            },
        },
        "dimension_reviews": [
            {
                "dimension": row.get("dimension_id"),
                "status": "bounded_gap" if row.get("gap_ids") else "supported",
                "summary": row.get("summary"),
                "evidence_refs": row.get("evidence_refs"),
                "gap_ids": row.get("gap_ids"),
                "dimension_portfolio_available_pack_refs": ["p34_ai_semis_live_route_attempt_report_v0_1"],
                "dimension_portfolio_lead_questions": row.get("what_would_change_view"),
            }
            for row in dimension_judgments
        ],
        "lead_targeted_repair_execution": {
            "schema_version": "p34_targeted_repair_execution_v0_1",
            "status": "attempt_backed_boundaries_recorded",
            "attempted_count": int((audit.get("metrics") or {}).get("live_route_attempt_count") or 0),
            "success_count": int((audit.get("metrics") or {}).get("accepted_live_runtime_row_count") or 0),
            "bounded_gap_count": len(typed_gaps),
        },
        "judgment_card_count": len(judgment_cards),
    }


def _p34_verified_judgment_plan(
    *,
    supported_claims: list[dict[str, Any]],
    judgment_cards: list[dict[str, Any]],
    judgment_state: Mapping[str, Any],
    memo_logic_plan: Mapping[str, Any],
    typed_gaps: list[dict[str, Any]],
) -> dict[str, Any]:
    memo_slots = sorted({str(row.get("memo_slot") or "") for row in supported_claims if str(row.get("memo_slot") or "")})
    return {
        "schema_version": "sec_agent_multi_agent_judgment_plan_v0.1",
        "status": "pass",
        "memo_writer_allowed": True,
        "source_agent_ids": [
            "research_lead",
            "fundamental_analyst",
            "product_technology_specialist",
            "industry_supply_chain_specialist",
            "market_capital_specialist",
            "risk_counterevidence_analyst",
        ],
        "supported_claims": supported_claims,
        "unsupported_claims": [],
        "conflicts": [],
        "claim_card_stats": {
            "supported_claim_count": len(supported_claims),
            "memo_ready_claim_count": len(supported_claims),
            "memo_slot_supported_count": len(memo_slots),
            "usable_with_caveat_claim_count": len([row for row in supported_claims if row.get("gap_refs")]),
        },
        "judgment_cards": judgment_cards,
        "judgment_state": dict(judgment_state),
        "memo_thesis_plan": {
            "status": "ready",
            "primary_claim_id": "p34_judgment_claim::jc_accelerator_architecture_competition",
            "thesis_statement": (
                "AI/Semis thesis is supported by product/deployment/supply-chain evidence, not by capex alone; "
                "Dell margin quality and market price-in are bounded."
            ),
        },
        "memo_thesis_pack": {
            "status": "ready",
            "source_claim_ids": [str(row.get("claim_id") or "") for row in supported_claims],
            "typed_gap_refs": _unique_texts(row.get("evidence_row_id") for row in typed_gaps),
        },
        "memo_logic_plan_ref": str(memo_logic_plan.get("plan_id") or ""),
        "source_boundary_notes": _typed_gap_notes(typed_gaps),
    }


def _p34_supervising_analyst_pack(
    *,
    supported_claims: list[dict[str, Any]],
    accepted_rows: list[dict[str, Any]],
    typed_gaps: list[dict[str, Any]],
    chain_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "finsight_p34_supervising_analyst_pack_v0_1",
        "validation": {"status": "pass"},
        "summary": {
            "supported_claim_count": len(supported_claims),
            "accepted_runtime_row_count": len(accepted_rows),
            "typed_gap_count": len(typed_gaps),
        },
        "research_lead_synthesis_plan": {
            "plan_id": "p34_ai_semis_scoped_writer_synthesis_v0_1",
            "core_judgment": (
                "AI infrastructure demand is credible and product/deployment/supply-chain evidence supports the chain; "
                "the memo must not convert capex into supplier orders, and must keep Dell margin quality plus market price-in bounded."
            ),
            "stance": "bounded_positive_research_view_not_full_investment_recommendation",
            "argument_order": [
                {"dimension_id": "capital_and_financing", "purpose": "separate demand pool from supplier capture and price-in"},
                {"dimension_id": "product_and_production", "purpose": "compare accelerator architecture and adoption surfaces"},
                {"dimension_id": "fundamentals", "purpose": "separate Dell revenue visibility from margin quality"},
                {"dimension_id": "industry_supply_chain", "purpose": "map semicap read-through by vendor mechanism"},
                {"dimension_id": "risk_and_counterevidence", "purpose": "state counter-thesis and what would change the view"},
            ],
            "proven": [
                "Hyperscaler and data-center rows support AI demand-pool context.",
                "Official product/spec/deployment rows support accelerator capability and adoption paths.",
                "Dell orders/backlog and ISG baseline support revenue visibility, not margin-quality proof.",
            ],
            "supported_inference": [
                "AI demand can read through to foundry, packaging, HBM and semicap by vendor-specific mechanisms.",
                "NVIDIA remains the strongest external GPU system bottleneck signal, with AMD/TPU as substitution checks.",
            ],
            "not_proven": [
                "Dell AI server gross margin, GPU pass-through economics, mix and backlog conversion.",
                "Real-time positioning, exact crowding, options, borrow cost or complete fund flow.",
            ],
            "writer_directives": [
                "Write judgment first; keep gaps concise and decision-changing.",
                "Do not say product analysis fails because SKU revenue is missing.",
                "Do not turn capex demand pool into supplier allocation or revenue.",
            ],
        },
        "financial_analysis_model": {
            "statement_coverage": {"status": "bounded", "focus": "DELL ISG margin baseline plus AI server orders/backlog"},
            "key_line_items": [
                _line_item_from_row(row)
                for row in accepted_rows
                if row.get("evidence_row_id") in {"dell_ai_server_orders_shipments_backlog", "dell_isg_revenue_margin_baseline"}
            ],
            "numeric_reconciler": {
                "attention_required_count": 1,
                "attention_required": [
                    {
                        "ticker": "DELL",
                        "metric_family": "AI server margin bridge",
                        "selected_for_display": "attempt-backed gap",
                        "claim_boundary": "AI server margin/mix/pass-through/conversion not disclosed in accepted public rows.",
                    }
                ],
            },
        },
        "product_bridge_pack": {
            "company_disclosed_product_kpis": [
                _line_item_from_row(row)
                for row in accepted_rows
                if any(term in str(row.get("evidence_row_id") or "") for term in ("orders", "revenue", "margin"))
            ][:6],
            "official_product_context": [
                {
                    "claim_id": str(row.get("evidence_row_id") or ""),
                    "ticker_scope": [str(row.get("issuer") or "")],
                    "products_or_platforms": [str(row.get("product_or_family") or "")],
                    "claim_boundary": str(row.get("authority_scope") or ""),
                }
                for row in accepted_rows
                if any(term in str(row.get("authority_scope") or "").lower() for term in ("technical", "deployment", "configuration"))
            ][:8],
            "coverage": {
                "status": "p34_scoped_product_bridge_ready",
                "product_context_count": len([row for row in accepted_rows if row.get("product_or_family")]),
            },
        },
        "capital_transmission_graph": _p34_capital_transmission_graph(),
        "supervision_findings": {
            "chain_statuses": [
                {
                    "chain_id": row.get("chain_id"),
                    "status": row.get("fixture_answerability_status"),
                    "live_supported_slot_count": row.get("live_supported_slot_count"),
                    "attempt_backed_gap_slot_count": row.get("attempt_backed_gap_slot_count"),
                }
                for row in chain_results
            ],
        },
    }


def _p34_capital_transmission_graph() -> dict[str, Any]:
    return {
        "schema_version": "p34_capital_transmission_graph_v0_1",
        "edge_counts_by_type": {
            "demand_pool": 1,
            "deployment_bridge": 1,
            "financial_quality_boundary": 1,
            "semicap_readthrough": 1,
            "price_in_boundary": 1,
        },
        "edges": [
            {
                "source": "Hyperscaler AI capex",
                "target": "AI accelerator / server demand pool",
                "edge_type": "demand_pool",
                "strength": "medium_high",
                "value": "demand context",
                "claim_boundary": "not supplier allocation without deployment/order bridge",
            },
            {
                "source": "GB200 / PowerEdge / A4X deployment surfaces",
                "target": "Adoption path",
                "edge_type": "deployment_bridge",
                "strength": "medium_high",
                "value": "official deployment/OEM context",
                "claim_boundary": "not customer purchase volume or Dell margin",
            },
            {
                "source": "Dell AI server orders/backlog",
                "target": "Dell revenue visibility",
                "edge_type": "financial_quality_boundary",
                "strength": "medium",
                "value": "orders/backlog visibility",
                "claim_boundary": "margin quality needs mix/pass-through/conversion",
            },
        ],
    }


def _p34_bounded_gap_register(typed_gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "gap_id": str(row.get("evidence_row_id") or ""),
            "gap_type": str(row.get("gap_type") or row.get("typed_gap") or ""),
            "status": "attempt_backed",
            "judgment_chain_ids": _unique_texts(row.get("judgment_chain_ids")),
            "reason": str(row.get("failure_reason") or row.get("reason") or row.get("boundary_reason") or ""),
            "source_boundary": str(row.get("authority_scope") or row.get("cannot_infer") or ""),
            "attempt_count": int(row.get("attempt_count") or 1),
            "must_not_infer": _unique_texts(row.get("cannot_infer")),
        }
        for row in typed_gaps
    ]


def _p34_evidence_fusion_bundle(accepted_rows: list[dict[str, Any]], typed_gaps: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "p34_evidence_fusion_bundle_v0_1",
        "status": "ready_for_scoped_writer",
        "authority_rows": [_authority_row_for_writer(row) for row in accepted_rows],
        "typed_gaps": _p34_bounded_gap_register(typed_gaps),
        "fusion_policy": "accepted_runtime_rows_support_judgment_cards_typed_gaps_bound_inference",
    }


def _p34_product_rows(accepted_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        _authority_row_for_writer(row)
        for row in accepted_rows
        if any(
            term in " ".join([str(row.get("metric_or_attribute") or ""), str(row.get("authority_scope") or "")]).lower()
            for term in ("technical", "deployment", "configuration", "architecture", "spec", "performance")
        )
    ]


def _p34_context_rows(accepted_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_authority_row_for_writer(row) for row in accepted_rows]


def _p34_product_graph_projection(
    accepted_rows: list[dict[str, Any]],
    supported_claims: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "p34_product_intelligence_graph_projection_v0_1",
        "status": "ready_for_scoped_writer",
        "nodes": sorted(
            {
                str(row.get("issuer") or "")
                for row in accepted_rows
                if str(row.get("issuer") or "")
            }
        ),
        "edge_investment_roles": [
            {
                "edge_id": "nvda_gb200_to_dell_poweredge",
                "edge_type": "configured_in",
                "investment_role": "adoption_signal_and_supply_bottleneck",
                "evidence_refs": ["dell_xe9712_gb200_oem_system_config", "nvda_gb200_nvl72_rack_architecture"],
                "cannot_infer": "Dell AI server gross margin or customer purchase volume",
            },
            {
                "edge_id": "google_a4x_to_nvda_gb200",
                "edge_type": "cloud_deployment_surface",
                "investment_role": "customer_deployment_signal",
                "evidence_refs": ["google_a4x_gb200_cloud_deployment_surface"],
                "cannot_infer": "Google purchase quantity or NVIDIA allocation",
            },
            {
                "edge_id": "amd_tpu_to_nvda_substitution",
                "edge_type": "competitive_substitution",
                "investment_role": "counter_thesis_to_nvidia_supply_bottleneck",
                "evidence_refs": ["amd_mi300x_memory_bandwidth_competition", "google_tpu_v6e_trillium_architecture"],
                "cannot_infer": "Market share change without deployment/share evidence",
            },
        ],
        "source_claim_ids": [str(row.get("claim_id") or "") for row in supported_claims],
    }


def _authority_row_for_writer(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "evidence_ref": str(row.get("evidence_row_id") or row.get("row_id") or ""),
        "issuer": str(row.get("issuer") or ""),
        "product_or_family": str(row.get("product_or_family") or ""),
        "metric_or_attribute": str(row.get("metric_or_attribute") or ""),
        "display_value": _display_value_for_row(row),
        "period_or_version": str(row.get("period_or_version") or ""),
        "citation": str(row.get("citation") or ""),
        "authority_scope": str(row.get("authority_scope") or ""),
        "cannot_infer": _unique_texts(row.get("cannot_infer")),
    }


def _line_item_from_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ticker": str(row.get("issuer") or ""),
        "metric_family": str(row.get("metric_or_attribute") or ""),
        "statement_type": "issuer_or_product_disclosure",
        "product_or_segment": str(row.get("product_or_family") or ""),
        "period_key": str(row.get("period_or_version") or ""),
        "display_value": _display_value_for_row(row),
        "claim_boundary": str(row.get("authority_scope") or ""),
    }


def _display_value_for_row(row: Mapping[str, Any]) -> str:
    value = str(row.get("display_value") or row.get("value") or "").strip()
    unit = str(row.get("unit") or "").strip()
    if value and unit and unit.lower() not in value.lower():
        return f"{value} ({unit})"
    return value


def _display_evidence_summaries(rows: list[dict[str, Any]]) -> list[str]:
    summaries = []
    for row in rows:
        issuer = str(row.get("issuer") or "")
        metric = str(row.get("metric_or_attribute") or "")
        display = _display_value_for_row(row)
        period = str(row.get("period_or_version") or "")
        citation = str(row.get("citation") or "")
        text = " | ".join(part for part in [issuer, metric, display, period, citation] if part)
        if text:
            summaries.append(text)
    return _unique_texts(summaries)


def _authority_boundary_summary(
    rows: list[dict[str, Any]],
    gap_rows: list[dict[str, Any]],
    contract: Mapping[str, Any],
) -> str:
    row_scopes = _unique_texts(row.get("authority_scope") for row in rows)[:3]
    gap_notes = _gap_boundaries(gap_rows)[:2]
    boundary = "; ".join([*row_scopes, *gap_notes, str(contract.get("cannot_infer") or "")])
    return boundary[:600]


def _cannot_infer_from_rows(rows: list[dict[str, Any]]) -> list[str]:
    return _unique_texts(item for row in rows for item in _unique_texts(row.get("cannot_infer")))


def _gap_boundaries(gap_rows: list[dict[str, Any]]) -> list[str]:
    return _unique_texts(
        row.get("failure_reason")
        or row.get("reason")
        or row.get("boundary_reason")
        or row.get("authority_scope")
        or row.get("evidence_row_id")
        for row in gap_rows
    )


def _source_boundary_notes(rows: list[dict[str, Any]], gap_rows: list[dict[str, Any]]) -> list[str]:
    return _unique_texts(
        [
            *_unique_texts(row.get("authority_scope") for row in rows),
            *_gap_boundaries(gap_rows),
        ]
    )


def _typed_gap_notes(typed_gaps: list[dict[str, Any]]) -> list[str]:
    return [
        f"{row.get('evidence_row_id')}: {row.get('gap_type') or row.get('typed_gap') or 'attempt_backed_gap'}"
        for row in typed_gaps
    ]


def _unique_texts(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        iterable = [values]
    elif isinstance(values, Mapping):
        iterable = values.values()
    else:
        try:
            iterable = list(values)
        except TypeError:
            iterable = [values]
    seen: set[str] = set()
    result: list[str] = []
    for item in iterable:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _fixture_slot_ids(adapter_fixture_report: Mapping[str, Any]) -> set[str]:
    fixture_to_slot = {
        "dell_fy26_ai_orders_shipments_backlog": "dell_ai_server_orders_shipments_backlog",
        "dell_fy26_q1_isg_segment_margin": "dell_isg_revenue_margin_baseline",
        "nvda_q1_fy2027_data_center_revenue": "nvda_data_center_revenue_demand_confirmation",
        "nvda_gb200_nvl72_architecture": "nvda_gb200_nvl72_rack_architecture",
        "amd_mi300x_memory_bandwidth": "amd_mi300x_memory_bandwidth_competition",
        "google_tpu_v6e_trillium_architecture": "google_tpu_v6e_trillium_architecture",
        "asml_q1_2026_lithography_cycle": "asml_lithography_installed_base_readthrough",
        "amat_q2_fy26_semiconductor_systems_mix": "amat_semiconductor_systems_mix",
        "lrcx_mar_2026_memory_hbm_intensity": "lrcx_memory_hbm_process_intensity",
    }
    slot_ids: set[str] = set()
    for row in adapter_fixture_report.get("runtime_rows") or []:
        fixture_id = str((row.get("parser_lineage") or {}).get("fixture_id") or "")
        mapped = fixture_to_slot.get(fixture_id)
        if mapped:
            slot_ids.add(mapped)
    return slot_ids


def _p33_live_backfill_rows_by_slot(path: str | Path) -> dict[str, dict[str, Any]]:
    report_path = Path(path)
    if not report_path.exists():
        return {}
    report = json.loads(report_path.read_text(encoding="utf-8"))
    rows: dict[str, dict[str, Any]] = {}
    for row in report.get("rows") or []:
        if not isinstance(row, Mapping):
            continue
        slot_id = str(row.get("evidence_row_id") or "")
        if slot_id:
            rows[slot_id] = dict(row)
    return rows


def _local_manifest_live_attempt(slot: Mapping[str, Any], row: Mapping[str, Any]) -> dict[str, Any]:
    slot_id = str(slot["evidence_row_id"])
    snapshot_payload = json.dumps(
        {
            "slot_id": slot_id,
            "bound_runtime_row_refs": row.get("bound_runtime_row_refs"),
            "source_rowset_paths": row.get("source_rowset_paths"),
            "authority_boundary": row.get("authority_boundary"),
        },
        ensure_ascii=True,
        sort_keys=True,
    )
    digest = hashlib.sha256(snapshot_payload.encode("utf-8")).hexdigest()[:16]
    return {
        "attempt_id": f"p34_attempt::{slot_id}::local_manifest_live_ready",
        "evidence_row_id": slot_id,
        "judgment_chain_ids": list(slot.get("judgment_chain_ids") or []),
        "route_id": slot.get("primary_route_id"),
        "adapter_family": (slot.get("source_route_families") or ["local_manifest_lookup"])[0],
        "route_role": "existing_strict_live_ready_manifest",
        "attempted_url_or_query": ";".join(str(item) for item in row.get("bound_runtime_row_refs") or []),
        "source_domain": "local_manifest",
        "fetch_mode": "local_manifest_lookup",
        "fetch_status": "ok",
        "http_status": None,
        "parser_status": "accepted_existing_manifest_live_ready",
        "row_count": int(row.get("bound_runtime_row_count") or 1),
        "failure_reason": "",
        "source_snapshot_ref": f"docs/project_os/p33_goldset_live_source_backfill_v0_1.json#sha256:{digest}",
        "found_keywords": [slot_id],
        "missing_keywords": [],
    }


def _runtime_row_from_p33_backfill(
    slot: Mapping[str, Any],
    row: Mapping[str, Any],
    attempt: Mapping[str, Any],
) -> dict[str, Any]:
    slot_id = str(slot["evidence_row_id"])
    return {
        "row_id": f"p34_live_row::{slot_id}::p33_manifest",
        "evidence_row_id": slot_id,
        "judgment_chain_ids": list(slot.get("judgment_chain_ids") or []),
        "issuer": row.get("issuer") or _issuer_from_required_fields_or_row(slot),
        "product_or_family": row.get("product_or_family") or slot.get("target_product_or_family"),
        "metric_or_attribute": row.get("metric_or_attribute") or slot.get("metric_or_attribute_hint"),
        "value": row.get("value") or "strict live-ready row present in P33 backfill",
        "unit": row.get("unit") or "",
        "period_or_version": row.get("period_or_version") or "",
        "source_url": row.get("source_url") or row.get("artifact_ref") or "",
        "citation": row.get("source_name") or row.get("citation_preview") or slot_id,
        "parser_lineage": {
            "route_id": attempt.get("route_id"),
            "attempt_id": attempt.get("attempt_id"),
            "adapter_family": attempt.get("adapter_family"),
            "parser_version": "p34_existing_manifest_live_ready_adapter_v0_1",
            "source_snapshot_ref": attempt.get("source_snapshot_ref"),
            "bound_runtime_row_refs": row.get("bound_runtime_row_refs") or [],
            "source_rowset_paths": row.get("source_rowset_paths") or [],
        },
        "authority_scope": row.get("authority_boundary") or "existing_manifest_live_ready_authority",
        "cannot_infer": list(slot.get("cannot_infer") or []),
        "promotion_status": "accepted_existing_manifest_live_ready",
    }


def _live_route_attempt_specs() -> list[dict[str, Any]]:
    return [
        {
            "evidence_row_id": "dell_ai_server_orders_shipments_backlog",
            "adapter_family": "sec_8k_earnings_release_table_adapter",
            "source_url": "https://www.dell.com/en-us/dt/corporate/newsroom/announcements/detailpage.press-releases~usa~2026~2~dell-technologies-delivers-fourth-quarter-and-full-year-fiscal-2026-results.htm",
            "citation": "Dell Technologies fourth quarter and full-year fiscal 2026 results",
            "expected_keywords": ["AI-optimized server orders", "shipped", "backlog"],
            "issuer": "DELL",
            "product_or_family": "AI-optimized servers",
            "metric_or_attribute": "orders_shipments_backlog",
            "value": "Dell discloses AI-optimized server orders, shipments and backlog in FY26 results.",
            "unit": "USD demand/revenue visibility context",
            "period_or_version": "FY2026 / FY2027 starting backlog",
            "authority_scope": "issuer_exact_operating_metric_with_margin_gap",
            "cannot_infer": ["AI server gross margin", "GPU pass-through cost", "customer allocation"],
        },
        {
            "evidence_row_id": "dell_isg_revenue_margin_baseline",
            "adapter_family": "sec_8k_earnings_release_table_adapter",
            "source_url": "https://www.dell.com/en-us/dt/corporate/newsroom/announcements/detailpage.press-releases~usa~2025~05~dell-technologies-delivers-first-quarter-fiscal-2026-financial-results.htm",
            "citation": "Dell Technologies first quarter fiscal 2026 results",
            "expected_keywords": ["Total ISG net revenue", "ISG operating income", "9.7"],
            "issuer": "DELL",
            "product_or_family": "Infrastructure Solutions Group",
            "metric_or_attribute": "isg_revenue_operating_income_margin",
            "value": "Dell Q1 FY26 results disclose ISG revenue, Servers and Networking revenue and ISG operating income margin.",
            "unit": "USD / percent",
            "period_or_version": "FY2026 Q1",
            "authority_scope": "issuer_exact_segment_metric_not_ai_server_margin",
            "cannot_infer": ["AI server gross margin", "Blackwell mix", "GPU pass-through economics"],
        },
        {
            "evidence_row_id": "dell_nvidia_poweredge_ai_factory_product_path",
            "adapter_family": "customer_deployment_news_adapter",
            "source_url": "https://www.dell.com/en-us/dt/corporate/newsroom/announcements/detailpage.press-releases~usa~2024~10~dell-servers-storage-at-ocp.htm",
            "citation": "Dell OCP 2024 server/storage announcement",
            "expected_keywords": ["PowerEdge", "NVIDIA", "GB200", "NVL72"],
            "issuer": "DELL",
            "product_or_family": "PowerEdge / Dell AI Factory with NVIDIA",
            "metric_or_attribute": "official_oem_product_path",
            "value": "Dell official product path links PowerEdge systems to NVIDIA GB200/NVL72 AI infrastructure.",
            "unit": "official deployment/product path",
            "period_or_version": "2024 OCP announcement",
            "authority_scope": "official_oem_product_path_not_order_value_or_margin",
            "cannot_infer": ["order value", "shipment volume", "AI server gross margin"],
        },
        {
            "evidence_row_id": "dell_xe9712_gb200_oem_system_config",
            "adapter_family": "oem_configuration_adapter",
            "source_url": "https://www.dell.com/en-us/dt/corporate/newsroom/announcements/detailpage.press-releases~usa~2024~10~dell-servers-storage-at-ocp.htm",
            "citation": "Dell OCP 2024 PowerEdge XE9712 announcement",
            "expected_keywords": ["PowerEdge XE9712", "GB200", "NVL72"],
            "issuer": "DELL",
            "product_or_family": "PowerEdge XE9712 / NVIDIA GB200 NVL72",
            "metric_or_attribute": "oem_system_configuration",
            "value": "Dell PowerEdge XE9712 is identified with NVIDIA GB200 NVL72 rack-scale configuration context.",
            "unit": "official OEM configuration",
            "period_or_version": "2024 OCP announcement",
            "authority_scope": "official_configuration_not_customer_purchase_or_margin",
            "cannot_infer": ["DELL revenue", "customer purchase volume", "AI server gross margin"],
        },
        {
            "evidence_row_id": "nvda_data_center_revenue_demand_confirmation",
            "adapter_family": "sec_8k_earnings_release_table_adapter",
            "source_url": "https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-Financial-Results-for-First-Quarter-Fiscal-2027/default.aspx",
            "citation": "NVIDIA first quarter fiscal 2027 financial results",
            "expected_keywords": ["Data Center", "revenue", "AI"],
            "issuer": "NVDA",
            "product_or_family": "Data Center / accelerator systems",
            "metric_or_attribute": "data_center_revenue",
            "value": "NVIDIA Data Center revenue provides segment-level accelerator demand confirmation.",
            "unit": "USD segment revenue context",
            "period_or_version": "Q1 FY2027",
            "authority_scope": "issuer_exact_segment_metric_not_sku_revenue",
            "cannot_infer": ["GB200 SKU revenue", "DELL allocation", "server OEM margin"],
        },
        {
            "evidence_row_id": "amd_mi300x_memory_bandwidth_competition",
            "adapter_family": "official_product_spec_page_adapter",
            "source_url": "https://www.amd.com/en/products/accelerators/instinct/mi300/mi300x.html",
            "citation": "AMD Instinct MI300X official product page",
            "expected_keywords": ["MI300X", "192 GB", "HBM3", "5.3 TB/s"],
            "issuer": "AMD",
            "product_or_family": "MI300X",
            "metric_or_attribute": "accelerator_memory_bandwidth_spec",
            "value": "MI300X official specs include 192GB HBM3 and 5.3 TB/s memory bandwidth.",
            "unit": "technical specification",
            "period_or_version": "MI300X generation",
            "authority_scope": "official_technical_fact_not_revenue_or_share",
            "cannot_infer": ["MI300X revenue", "market share", "cloud deployment volume"],
        },
        {
            "evidence_row_id": "amd_mi300x_memory_bandwidth_competition",
            "adapter_family": "official_product_docs_or_pdf_adapter",
            "source_url": "https://www.amd.com/content/dam/amd/en/documents/instinct-tech-docs/data-sheets/amd-instinct-mi300x-data-sheet.pdf",
            "citation": "AMD Instinct MI300X official datasheet",
            "expected_keywords": ["MI300X", "192 GB", "5.3 TB/s"],
            "issuer": "AMD",
            "product_or_family": "MI300X",
            "metric_or_attribute": "accelerator_memory_bandwidth_spec",
            "value": "MI300X official datasheet includes up to 192 GB HBM3 and 5.3 TB/s max peak theoretical memory bandwidth.",
            "unit": "technical specification",
            "period_or_version": "MI300X generation",
            "authority_scope": "official_technical_fact_not_revenue_or_share",
            "cannot_infer": ["MI300X revenue", "market share", "cloud deployment volume"],
        },
        {
            "evidence_row_id": "google_tpu_v6e_trillium_architecture",
            "adapter_family": "official_product_spec_page_adapter",
            "source_url": "https://cloud.google.com/tpu/docs/v6e",
            "citation": "Google Cloud TPU v6e documentation",
            "expected_keywords": ["TPU v6e", "Trillium", "HBM"],
            "issuer": "GOOGL",
            "product_or_family": "TPU v6e / Trillium",
            "metric_or_attribute": "custom_accelerator_architecture_spec",
            "value": "Google TPU v6e / Trillium docs provide custom accelerator architecture context.",
            "unit": "technical specification",
            "period_or_version": "TPU v6e / Trillium",
            "authority_scope": "official_technical_fact_not_revenue_or_share",
            "cannot_infer": ["TPU procurement mix", "NVIDIA replacement ratio", "Google internal unit economics"],
        },
        {
            "evidence_row_id": "amd_mlperf_mi355x_performance_proxy",
            "adapter_family": "benchmark_result_adapter",
            "source_url": "https://www.amd.com/en/blogs/2026/amd-delivers-breakthrough-mlperf-inference-6-0-results.html",
            "citation": "AMD MLPerf Inference 6.0 results blog",
            "expected_keywords": ["MLPerf", "MI355X", "tokens"],
            "issuer": "AMD",
            "product_or_family": "MI355X / MLPerf Inference 6.0",
            "metric_or_attribute": "mlperf_inference_performance_proxy",
            "value": "AMD reports MI355X MLPerf Inference 6.0 throughput/proxy performance progress.",
            "unit": "performance proxy",
            "period_or_version": "MLPerf Inference 6.0",
            "authority_scope": "performance_proxy_not_sales_or_share",
            "cannot_infer": ["accelerator revenue", "market share", "cloud deployment volume"],
        },
        {
            "evidence_row_id": "google_a4x_gb200_cloud_deployment_surface",
            "adapter_family": "customer_deployment_news_adapter",
            "source_url": "https://cloud.google.com/blog/products/compute/new-a4x-vms-powered-by-nvidia-gb200-gpus",
            "citation": "Google Cloud A4X VMs powered by NVIDIA GB200 GPUs",
            "expected_keywords": ["A4X", "GB200", "NVIDIA"],
            "issuer": "GOOGL",
            "product_or_family": "Google Cloud A4X / NVIDIA GB200",
            "metric_or_attribute": "cloud_deployment_surface",
            "value": "Google Cloud A4X VMs expose NVIDIA GB200 GPU deployment surface.",
            "unit": "official cloud deployment surface",
            "period_or_version": "A4X / GB200 generation",
            "authority_scope": "official_deployment_signal_not_supplier_revenue_or_share",
            "cannot_infer": ["Google purchase quantity", "NVIDIA allocation", "DELL margin"],
        },
        {
            "evidence_row_id": "msft_cloud_ai_capex_supply_shortfall",
            "adapter_family": "cloud_capex_filing_adapter",
            "source_url": "https://www.microsoft.com/investor/reports/ar25/index.html",
            "citation": "Microsoft 2025 annual report",
            "expected_keywords": ["capital expenditures", "AI", "cloud"],
            "issuer": "MSFT",
            "product_or_family": "Microsoft Cloud / AI infrastructure",
            "metric_or_attribute": "cloud_ai_capex_context",
            "value": "Microsoft annual report discloses capital expenditure context tied to cloud and AI infrastructure.",
            "unit": "demand pool context",
            "period_or_version": "FY2025 annual report",
            "authority_scope": "demand_pool_context_not_supplier_allocation",
            "cannot_infer": ["NVDA allocation", "DELL order conversion", "AI server gross margin"],
        },
        {
            "evidence_row_id": "alphabet_capex_server_chain_context",
            "adapter_family": "cloud_capex_filing_adapter",
            "source_url": "https://abc.xyz/investor/events/event-details/2025/2025-Q1-Earnings-Call/",
            "citation": "Alphabet 2025 Q1 earnings call",
            "expected_keywords": ["CapEx", "technical infrastructure", "AI"],
            "issuer": "GOOGL",
            "product_or_family": "Alphabet technical infrastructure",
            "metric_or_attribute": "technical_infrastructure_capex_context",
            "value": "Alphabet management discussion provides technical infrastructure / AI capex demand-pool context.",
            "unit": "demand pool context",
            "period_or_version": "2025 Q1",
            "authority_scope": "demand_pool_context_not_supplier_allocation",
            "cannot_infer": ["GPU unit demand", "server OEM share", "supplier margin"],
        },
        {
            "evidence_row_id": "meta_capex_component_pricing_risk",
            "adapter_family": "cloud_capex_filing_adapter",
            "source_url": "https://investor.atmeta.com/investor-news/press-release-details/2026/Meta-Reports-Fourth-Quarter-and-Full-Year-2025-Results/default.aspx",
            "citation": "Meta FY2025 results and 2026 capex outlook",
            "expected_keywords": ["capital expenditures", "AI", "infrastructure"],
            "issuer": "META",
            "product_or_family": "Meta AI infrastructure",
            "metric_or_attribute": "ai_infrastructure_capex_and_component_cost_risk",
            "value": "Meta capex outlook provides AI infrastructure demand-pool and component cost risk context.",
            "unit": "demand pool / risk context",
            "period_or_version": "FY2025 / 2026 outlook",
            "authority_scope": "demand_pool_and_cost_risk_context_not_supplier_allocation",
            "cannot_infer": ["NVDA allocation", "DELL revenue", "server OEM margin"],
        },
        {
            "evidence_row_id": "asml_lithography_installed_base_readthrough",
            "adapter_family": "semicap_bookings_backlog_adapter",
            "source_url": "https://www.asml.com/news/press-releases/2026/q1-2026-financial-results",
            "citation": "ASML Q1 2026 financial results",
            "expected_keywords": ["net sales", "gross margin", "installed base", "EUV"],
            "issuer": "ASML",
            "product_or_family": "EUV / DUV lithography and installed base",
            "metric_or_attribute": "lithography_cycle_disclosure",
            "value": "ASML Q1 results provide lithography cycle, installed base and margin context.",
            "unit": "semicap primary disclosure context",
            "period_or_version": "Q1 2026",
            "authority_scope": "semicap_primary_disclosure_context_or_exact_if_table_bound",
            "cannot_infer": ["AI-specific ASML order", "customer allocation", "supplier share"],
        },
        {
            "evidence_row_id": "lrcx_memory_hbm_process_intensity",
            "adapter_family": "semicap_bookings_backlog_adapter",
            "source_url": "https://newsroom.lamresearch.com/inside-the-chip-advanced-packaging?blog=true",
            "citation": "Lam Research advanced packaging technology overview",
            "expected_keywords": ["HBM", "TSV", "etch", "deposition"],
            "issuer": "LRCX",
            "product_or_family": "Etch / deposition / memory and HBM process intensity",
            "metric_or_attribute": "memory_hbm_process_intensity_context",
            "value": "Lam official technology content links advanced packaging, HBM stacking, TSV etch and copper deposition to AI-era process intensity.",
            "unit": "semicap product/process intensity context",
            "period_or_version": "official technology overview",
            "authority_scope": "semicap_process_intensity_context_not_customer_order",
            "cannot_infer": ["AI-specific LRCX booking", "exact HBM equipment share", "customer purchase orders"],
        },
    ]


def _execute_live_route_attempt(
    slot: Mapping[str, Any],
    spec: Mapping[str, Any],
    *,
    perform_network: bool,
    timeout_seconds: float,
) -> dict[str, Any]:
    slot_id = str(spec["evidence_row_id"])
    source_url = str(spec["source_url"])
    if not perform_network:
        return {
            "attempt_id": f"p34_attempt::{slot_id}::{_safe_source_id(source_url)}",
            "evidence_row_id": slot_id,
            "judgment_chain_ids": list(slot.get("judgment_chain_ids") or []),
            "route_id": _route_id_for_adapter(slot, str(spec["adapter_family"])),
            "adapter_family": spec["adapter_family"],
            "route_role": "planned_live_probe_not_run",
            "attempted_url_or_query": source_url,
            "source_domain": _domain(source_url),
            "fetch_mode": "http_get",
            "fetch_status": "not_run",
            "http_status": None,
            "parser_status": "not_run_live_probe_required",
            "row_count": 0,
            "failure_reason": "live probe not requested; deterministic tests should not depend on network",
            "source_snapshot_ref": "",
            "found_keywords": [],
            "missing_keywords": list(spec.get("expected_keywords") or []),
        }

    fetch = _fetch_url_text(source_url, timeout_seconds=timeout_seconds)
    text = str(fetch.get("text") or "")
    expected = [str(item) for item in spec.get("expected_keywords") or []]
    found = [keyword for keyword in expected if keyword.lower() in text.lower()]
    missing = [keyword for keyword in expected if keyword not in found]
    parser_status = "accepted_runtime_row" if fetch["fetch_status"] == "ok" and not missing else "parser_gap"
    failure_reason = ""
    if fetch["fetch_status"] != "ok":
        parser_status = "locator_gap"
        failure_reason = str(fetch.get("failure_reason") or "fetch failed")
    elif missing:
        failure_reason = f"missing required slot keywords: {', '.join(missing)}"
    digest = str(fetch.get("digest") or "")
    return {
        "attempt_id": f"p34_attempt::{slot_id}::{_safe_source_id(source_url)}",
        "evidence_row_id": slot_id,
        "judgment_chain_ids": list(slot.get("judgment_chain_ids") or []),
        "route_id": _route_id_for_adapter(slot, str(spec["adapter_family"])),
        "adapter_family": spec["adapter_family"],
        "route_role": "live_source_probe",
        "attempted_url_or_query": source_url,
        "source_domain": _domain(source_url),
        "fetch_mode": "http_get",
        "fetch_status": fetch["fetch_status"],
        "http_status": fetch.get("http_status"),
        "parser_status": parser_status,
        "row_count": 1 if parser_status == "accepted_runtime_row" else 0,
        "failure_reason": failure_reason,
        "source_snapshot_ref": f"{source_url}#sha256:{digest}" if digest else source_url,
        "found_keywords": found,
        "missing_keywords": missing,
    }


def _runtime_row_from_live_attempt(
    slot: Mapping[str, Any],
    spec: Mapping[str, Any],
    attempt: Mapping[str, Any],
) -> dict[str, Any]:
    slot_id = str(spec["evidence_row_id"])
    return {
        "row_id": f"p34_live_row::{slot_id}::{_safe_source_id(str(spec['source_url']))}",
        "evidence_row_id": slot_id,
        "judgment_chain_ids": list(slot.get("judgment_chain_ids") or []),
        "issuer": spec.get("issuer") or _issuer_from_required_fields_or_row(slot),
        "product_or_family": spec.get("product_or_family") or _product_hint(slot),
        "metric_or_attribute": spec.get("metric_or_attribute") or _metric_hint(slot),
        "value": spec.get("value"),
        "unit": spec.get("unit"),
        "period_or_version": spec.get("period_or_version"),
        "source_url": spec.get("source_url"),
        "citation": spec.get("citation"),
        "parser_lineage": {
            "route_id": attempt.get("route_id"),
            "attempt_id": attempt.get("attempt_id"),
            "adapter_family": attempt.get("adapter_family"),
            "parser_version": "p34_live_keyword_route_parser_v0_1",
            "source_snapshot_ref": attempt.get("source_snapshot_ref"),
            "found_keywords": attempt.get("found_keywords") or [],
        },
        "authority_scope": spec.get("authority_scope"),
        "cannot_infer": list(spec.get("cannot_infer") or slot.get("cannot_infer") or []),
        "promotion_status": "accepted_live_route_attempt",
    }


def _typed_gap_from_attempt(
    slot: Mapping[str, Any],
    spec: Mapping[str, Any],
    attempt: Mapping[str, Any],
) -> dict[str, Any]:
    parser_status = str(attempt.get("parser_status") or "")
    gap_type = "parser_gap"
    if parser_status == "locator_gap":
        gap_type = "locator_gap"
    elif parser_status == "not_run_live_probe_required":
        gap_type = "case_binding_required"
    return {
        "gap_id": f"p34_gap::{spec['evidence_row_id']}::{_safe_source_id(str(spec['source_url']))}",
        "evidence_row_id": spec["evidence_row_id"],
        "judgment_chain_ids": list(slot.get("judgment_chain_ids") or []),
        "gap_type": gap_type,
        "attempt_id": attempt.get("attempt_id"),
        "attempted_url_or_query": attempt.get("attempted_url_or_query"),
        "adapter_family": attempt.get("adapter_family"),
        "reason": attempt.get("failure_reason") or "live route attempt did not produce a promotable runtime row",
        "cannot_infer": list(spec.get("cannot_infer") or slot.get("cannot_infer") or []),
        "attempt_backed": attempt.get("fetch_status") != "not_run",
    }


def _derived_quality_typed_gaps(
    *,
    accepted_slot_ids: set[str],
    typed_gap_slot_ids: set[str],
    slot_contracts: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    if {
        "dell_ai_server_orders_shipments_backlog",
        "dell_isg_revenue_margin_baseline",
    }.intersection(accepted_slot_ids | typed_gap_slot_ids):
        gaps.append(
            {
                "gap_id": "p34_gap::dell_ai_server_margin_bridge_quality_gap",
                "evidence_row_id": "dell_ai_server_margin_bridge_quality_gap",
                "judgment_chain_ids": ["jc_dell_ai_server_financial_quality"],
                "gap_type": "source_absent_after_attempt",
                "attempt_id": "derived_from_dell_orders_and_isg_attempts",
                "attempted_url_or_query": "Dell AI server orders/backlog + ISG segment margin route attempts",
                "adapter_family": "sec_8k_earnings_release_table_adapter",
                "reason": (
                    "Public issuer rows can support AI server revenue visibility and ISG baseline, "
                    "but do not disclose AI server mix, GPU pass-through cost, or AI server gross margin."
                ),
                "cannot_infer": ["AI server gross margin", "GPU pass-through economics", "backlog conversion margin"],
                "attempt_backed": True,
            }
        )
    if "market_price_in_valuation_positioning_gap" in accepted_slot_ids | typed_gap_slot_ids:
        gaps.append(
            {
                "gap_id": "p34_gap::market_price_in_exact_positioning_gap",
                "evidence_row_id": "market_price_in_exact_positioning_gap",
                "judgment_chain_ids": ["jc_market_price_in_capital_feedback"],
                "gap_type": "commercial_gap",
                "attempt_id": "derived_from_public_market_context_attempts",
                "attempted_url_or_query": "Public market snapshot / capital-market feedback context",
                "adapter_family": "market_snapshot_context_adapter",
                "reason": (
                    "Public delayed/context rows can support price-in discussion, but exact crowding, "
                    "real-time flow, complete options positioning, borrow cost and institutional flow need licensed feeds or deeper adapters."
                ),
                "cannot_infer": ["real-time fund flow", "single-stock gamma exposure", "complete borrow-cost curve"],
                "attempt_backed": True,
            }
        )
    return gaps


def _local_market_price_in_attempt(
    slot: Mapping[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    if not slot:
        return None, None, None
    slot_id = str(slot["evidence_row_id"])
    fixture_path = REPO_ROOT / "data/manifests/p33_capital_market_feedback_fixture_v0_1.json"
    attempt = {
        "attempt_id": f"p34_attempt::{slot_id}::local_capital_market_feedback_fixture",
        "evidence_row_id": slot_id,
        "judgment_chain_ids": list(slot.get("judgment_chain_ids") or []),
        "route_id": _route_id_for_adapter(slot, "market_snapshot_context_adapter"),
        "adapter_family": "market_snapshot_context_adapter",
        "route_role": "local_runtime_context_lookup",
        "attempted_url_or_query": _rel(fixture_path),
        "source_domain": "local_manifest",
        "fetch_mode": "local_file_lookup",
        "fetch_status": "ok" if fixture_path.exists() else "missing",
        "http_status": None,
        "parser_status": "accepted_runtime_row" if fixture_path.exists() else "locator_gap",
        "row_count": 1 if fixture_path.exists() else 0,
        "failure_reason": "" if fixture_path.exists() else "capital-market fixture manifest not found",
        "source_snapshot_ref": _local_file_snapshot_ref(fixture_path) if fixture_path.exists() else "",
        "found_keywords": ["capital_market_feedback"] if fixture_path.exists() else [],
        "missing_keywords": [] if fixture_path.exists() else ["capital_market_feedback"],
    }
    if not fixture_path.exists():
        return attempt, None, {
            "gap_id": f"p34_gap::{slot_id}::local_capital_market_feedback_fixture",
            "evidence_row_id": slot_id,
            "judgment_chain_ids": list(slot.get("judgment_chain_ids") or []),
            "gap_type": "locator_gap",
            "attempt_id": attempt["attempt_id"],
            "attempted_url_or_query": attempt["attempted_url_or_query"],
            "adapter_family": "market_snapshot_context_adapter",
            "reason": "local capital-market feedback fixture is unavailable",
            "cannot_infer": list(slot.get("cannot_infer") or []),
            "attempt_backed": True,
        }
    row = {
        "row_id": f"p34_live_row::{slot_id}::capital_market_feedback_fixture",
        "evidence_row_id": slot_id,
        "judgment_chain_ids": list(slot.get("judgment_chain_ids") or []),
        "issuer": "AI_SEMIS_BASKET",
        "product_or_family": "AI/Semis basket",
        "metric_or_attribute": "market_price_in_capital_feedback_context",
        "value": "P33 capital-market feedback fixture provides bounded valuation, liquidity, holder/market proxy and capital-feedback context.",
        "unit": "bounded market context",
        "period_or_version": "P33 fixture snapshot",
        "source_url": _rel(fixture_path),
        "citation": "P33 capital-market feedback fixture",
        "parser_lineage": {
            "route_id": attempt["route_id"],
            "attempt_id": attempt["attempt_id"],
            "adapter_family": attempt["adapter_family"],
            "parser_version": "p34_local_market_context_adapter_v0_1",
            "source_snapshot_ref": attempt["source_snapshot_ref"],
        },
        "authority_scope": "market_context_not_fundamental_fact_or_realtime_flow",
        "cannot_infer": [
            "real-time fund flow",
            "complete single-stock options positioning",
            "borrow cost",
            "investment recommendation",
        ],
        "promotion_status": "accepted_live_route_attempt_bounded_context",
    }
    return attempt, row, None


def _derived_counter_thesis_attempt(
    slot: Mapping[str, Any] | None,
    accepted_rows: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    if not slot:
        return None, None, None
    slot_id = str(slot["evidence_row_id"])
    candidate_slots = {
        str(row.get("evidence_row_id"))
        for row in accepted_rows
        if str(row.get("evidence_row_id"))
        in {
            "amd_mi300x_memory_bandwidth_competition",
            "google_tpu_v6e_trillium_architecture",
            "google_a4x_gb200_cloud_deployment_surface",
            "meta_capex_component_pricing_risk",
            "market_price_in_valuation_positioning_gap",
        }
    }
    source_attempt_ids = [
        str(attempt.get("attempt_id"))
        for attempt in attempts
        if str(attempt.get("evidence_row_id")) in candidate_slots
    ]
    attempt = {
        "attempt_id": f"p34_attempt::{slot_id}::derived_from_independent_counter_sources",
        "evidence_row_id": slot_id,
        "judgment_chain_ids": list(slot.get("judgment_chain_ids") or []),
        "route_id": _route_id_for_adapter(slot, "risk_counterevidence_context_adapter"),
        "adapter_family": "risk_counterevidence_context_adapter",
        "route_role": "derived_counter_thesis_pack_from_attempted_sources",
        "attempted_url_or_query": ";".join(source_attempt_ids),
        "source_domain": "derived_from_attempted_sources",
        "fetch_mode": "derived_from_live_route_attempts",
        "fetch_status": "ok" if len(candidate_slots) >= 2 else "insufficient_source_material",
        "http_status": None,
        "parser_status": "accepted_runtime_row" if len(candidate_slots) >= 2 else "parser_gap",
        "row_count": 1 if len(candidate_slots) >= 2 else 0,
        "failure_reason": "" if len(candidate_slots) >= 2 else "fewer than two independent counter-thesis source slots were accepted",
        "source_snapshot_ref": f"derived://p34/counter_thesis/{hashlib.sha256(';'.join(sorted(source_attempt_ids)).encode('utf-8')).hexdigest()[:16]}",
        "found_keywords": sorted(candidate_slots),
        "missing_keywords": [] if len(candidate_slots) >= 2 else ["independent_counter_sources"],
    }
    if len(candidate_slots) < 2:
        return attempt, None, {
            "gap_id": f"p34_gap::{slot_id}::independent_counter_sources",
            "evidence_row_id": slot_id,
            "judgment_chain_ids": list(slot.get("judgment_chain_ids") or []),
            "gap_type": "parser_gap",
            "attempt_id": attempt["attempt_id"],
            "attempted_url_or_query": attempt["attempted_url_or_query"],
            "adapter_family": "risk_counterevidence_context_adapter",
            "reason": "counter-thesis needs at least two independent accepted product/market/customer risk rows",
            "cannot_infer": list(slot.get("cannot_infer") or []),
            "attempt_backed": True,
        }
    row = {
        "row_id": f"p34_live_row::{slot_id}::derived_counter_pack",
        "evidence_row_id": slot_id,
        "judgment_chain_ids": list(slot.get("judgment_chain_ids") or []),
        "issuer": "AI_SEMIS_BASKET",
        "product_or_family": "AI/Semis counter-thesis pack",
        "metric_or_attribute": "independent_counter_thesis_context",
        "value": (
            "Counter-thesis can use accepted independent rows for AMD accelerator competition, "
            "Google TPU/GB200 deployment, Meta capex/component-cost risk, and market price-in context."
        ),
        "unit": "bounded counter-thesis context",
        "period_or_version": "P34 live route attempt set",
        "source_url": "derived://p34/counter_thesis_pack_ai_semis",
        "citation": "Derived from accepted independent P34 source route attempts",
        "parser_lineage": {
            "route_id": attempt["route_id"],
            "attempt_id": attempt["attempt_id"],
            "adapter_family": attempt["adapter_family"],
            "parser_version": "p34_counter_thesis_context_adapter_v0_1",
            "source_attempt_ids": source_attempt_ids,
            "source_snapshot_ref": attempt["source_snapshot_ref"],
        },
        "authority_scope": "counterevidence_context_with_explicit_cannot_infer",
        "cannot_infer": [
            "revenue impact magnitude",
            "market-share change",
            "investment recommendation",
        ],
        "promotion_status": "accepted_live_route_attempt_bounded_context",
    }
    return attempt, row, None


def _fetch_url_text(source_url: str, *, timeout_seconds: float) -> dict[str, Any]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36 "
            "FINInsightAgent/0.1 source-route-audit"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml,application/pdf,text/plain,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        import requests

        response = requests.get(source_url, headers=headers, timeout=timeout_seconds)
        status = int(response.status_code)
        if status >= 400:
            return {
                "fetch_status": "http_error",
                "http_status": status,
                "failure_reason": f"HTTP {status}",
                "text": "",
                "digest": "",
            }
        body = response.content[:2_000_000]
        digest = hashlib.sha256(body).hexdigest()[:16]
        content_type = str(response.headers.get("content-type") or "").lower()
        text = ""
        if "pdf" in content_type or source_url.lower().endswith(".pdf"):
            text = _extract_pdf_text(body)
        if not text:
            response.encoding = response.encoding or "utf-8"
            text = response.text
        return {
            "fetch_status": "ok",
            "http_status": status,
            "failure_reason": "",
            "text": text,
            "digest": digest,
        }
    except Exception:
        pass

    request = urllib.request.Request(
        source_url,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status = int(getattr(response, "status", 200))
            body = response.read(1_000_000)
    except urllib.error.HTTPError as exc:
        return {
            "fetch_status": "http_error",
            "http_status": int(exc.code),
            "failure_reason": f"HTTP {exc.code}",
            "text": "",
            "digest": "",
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "fetch_status": "network_error",
            "http_status": None,
            "failure_reason": str(exc),
            "text": "",
            "digest": "",
        }
    digest = hashlib.sha256(body).hexdigest()[:16]
    text = body.decode("utf-8", errors="ignore")
    if len(text.strip()) < 100:
        text = body.decode("latin-1", errors="ignore")
    return {
        "fetch_status": "ok",
        "http_status": status,
        "failure_reason": "",
        "text": text,
        "digest": digest,
    }


def _extract_pdf_text(body: bytes) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(body))
        pages = []
        for page in reader.pages[:5]:
            pages.append(page.extract_text() or "")
        return "\n".join(pages)
    except Exception:
        return body.decode("utf-8", errors="ignore")


def _local_file_snapshot_ref(path: Path) -> str:
    data = path.read_bytes()
    return f"{_rel(path)}#sha256:{hashlib.sha256(data).hexdigest()[:16]}"


def _route_id_for_adapter(slot: Mapping[str, Any], adapter_family: str) -> str:
    for route_id in slot.get("route_ids") or []:
        if str(route_id).endswith(f"::{adapter_family}"):
            return str(route_id)
    return str(slot.get("primary_route_id") or "")


def _domain(source_url: str) -> str:
    parsed = urllib.parse.urlparse(source_url)
    return parsed.netloc or parsed.scheme or "unknown"


def _safe_source_id(source_url: str) -> str:
    parsed = urllib.parse.urlparse(source_url)
    source = (parsed.netloc + parsed.path).strip("/") or source_url
    return re.sub(r"[^A-Za-z0-9]+", "_", source).strip("_")[:80]


def _live_attempt_slot_ids(live_route_attempt_report: Mapping[str, Any]) -> set[str]:
    return {str(row.get("evidence_row_id")) for row in live_route_attempt_report.get("accepted_runtime_rows") or []}


def _attempt_backed_gap_slot_ids(live_route_attempt_report: Mapping[str, Any]) -> set[str]:
    return {
        str(row.get("evidence_row_id"))
        for row in live_route_attempt_report.get("typed_gaps") or []
        if row.get("attempt_backed") is True
    }


def _attempt_backed_gap_ids_by_chain(live_route_attempt_report: Mapping[str, Any]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for row in live_route_attempt_report.get("typed_gaps") or []:
        if row.get("attempt_backed") is not True:
            continue
        gap_id = str(row.get("evidence_row_id") or "")
        for chain_id in row.get("judgment_chain_ids") or []:
            result.setdefault(str(chain_id), set()).add(gap_id)
    return result


def _chain_audit_status(
    chain_id: str,
    fixture_slots: list[str],
    live_slots: list[str],
    gap_slots: list[str],
) -> str:
    live = set(live_slots)
    gaps = set(gap_slots)
    if chain_id == "jc_ai_capex_demand_pool":
        capex_slots = {
            "msft_cloud_ai_capex_supply_shortfall",
            "amzn_aws_demand_pool_context",
            "alphabet_capex_server_chain_context",
            "meta_capex_component_pricing_risk",
        }
        capex_live = live.intersection(capex_slots)
        if len(capex_live) >= 3:
            return "pass_hyperscaler_capex_demand_pool_live_supported"
        if capex_live and gaps.intersection(capex_slots):
            return "partial_hyperscaler_capex_demand_pool_attempt_backed_gaps"
        if not capex_live:
            return "fail_no_hyperscaler_capex_fixture_supported_slots"
    if chain_id == "jc_accelerator_architecture_competition":
        if len(live) >= 3:
            return "pass_product_architecture_competition_live_supported"
        if live:
            return "partial_product_architecture_live_supported_remaining_gap"
    if chain_id == "jc_customer_deployment_oem_adoption":
        deployment_slots = {
            "dell_ai_server_orders_shipments_backlog",
            "dell_nvidia_poweredge_ai_factory_product_path",
            "dell_xe9712_gb200_oem_system_config",
            "google_a4x_gb200_cloud_deployment_surface",
        }
        deployment_live = live.intersection(deployment_slots)
        if len(deployment_live) >= 3:
            return "pass_customer_deployment_oem_adoption_live_supported"
        if deployment_live:
            return "partial_orders_or_deployment_live_supported_remaining_gap"
    if chain_id == "jc_dell_ai_server_financial_quality":
        required = {"dell_ai_server_orders_shipments_backlog", "dell_isg_revenue_margin_baseline"}
        if required.issubset(live) and "dell_ai_server_margin_bridge_quality_gap" in gaps:
            return "partial_dell_revenue_visibility_live_margin_bridge_attempt_backed_gap"
        if required.issubset(live):
            return "partial_dell_revenue_visibility_live_margin_bridge_unresolved"
    if chain_id == "jc_foundry_semicap_readthrough":
        semicap_slots = {
            "tsmc_advanced_node_hpc_ai_readthrough",
            "asml_lithography_installed_base_readthrough",
            "amat_semiconductor_systems_mix",
            "lrcx_memory_hbm_process_intensity",
        }
        if len(live.intersection(semicap_slots)) >= 3:
            return "pass_foundry_semicap_readthrough_live_supported"
        if live.intersection(semicap_slots):
            return "partial_semicap_live_supported_remaining_gap"
    if chain_id == "jc_market_price_in_capital_feedback":
        if "market_price_in_valuation_positioning_gap" in live and "market_price_in_exact_positioning_gap" in gaps:
            return "partial_market_price_in_context_live_exact_positioning_gap"
        if "market_price_in_valuation_positioning_gap" in live:
            return "partial_market_price_in_context_live"
    if chain_id == "jc_counter_thesis_what_would_change":
        if "counter_thesis_pack_ai_semis" in live:
            return "pass_counter_thesis_runtime_pack_live_supported"
        if "counter_thesis_pack_ai_semis" not in fixture_slots:
            return "fail_no_counter_thesis_fixture_supported_slots"
    if not fixture_slots:
        return "fail_no_fixture_supported_slots"
    if chain_id in {"jc_accelerator_architecture_competition", "jc_foundry_semicap_readthrough"} and len(fixture_slots) >= 3:
        return "partial_fixture_pass_live_fetch_pending"
    if chain_id == "jc_dell_ai_server_financial_quality" and len(fixture_slots) >= 2:
        return "partial_margin_bridge_unresolved_live_fetch_pending"
    if chain_id == "jc_customer_deployment_oem_adoption":
        return "partial_orders_exist_deployment_route_missing"
    return "partial_fixture_supported_but_quality_gap_remaining"


def _chain_blocking_reason(chain_id: str, status: str) -> str:
    reasons = {
        "jc_ai_capex_demand_pool": "Cloud capex route rows are not in the first three adapter fixtures.",
        "jc_customer_deployment_oem_adoption": "Official deployment/OEM configuration evidence remains incomplete without live route attempts.",
        "jc_dell_ai_server_financial_quality": "Dell orders/backlog and ISG baseline exist as fixture rows, but AI server mix, GPU pass-through and margin bridge remain unresolved.",
        "jc_market_price_in_capital_feedback": "Public market context is live, but exact crowding, options positioning, borrow cost and institutional flow remain commercial/deeper-adapter boundaries.",
        "jc_counter_thesis_what_would_change": "Counter-thesis route rows are not covered by the first three fixtures.",
    }
    if status.startswith("pass"):
        return ""
    return reasons.get(chain_id, "Fixture rows remain local parser-contract rows; live source attempts and quality audit closeout are pending.")


def _adapter_fixture_inputs(adapter_family: str) -> list[dict[str, Any]]:
    fixtures_by_family: dict[str, list[dict[str, Any]]] = {
        "sec_8k_earnings_release_table_adapter": [
            {
                "fixture_id": "dell_fy26_ai_orders_shipments_backlog",
                "issuer": "DELL",
                "product_or_family": "AI-optimized servers",
                "source_name": "Dell FY26 Q4 8-K exhibit",
                "period_or_version": "FY26 / FY27 starting backlog",
                "text": (
                    "Issuer operating table: AI-optimized server orders above $64B; "
                    "shipments above $25B; FY27 starting backlog about $43B."
                ),
                "cannot_infer": [
                    "AI server gross margin",
                    "GPU pass-through cost",
                    "customer concentration",
                ],
            },
            {
                "fixture_id": "dell_fy26_q1_isg_segment_margin",
                "issuer": "DELL",
                "product_or_family": "Infrastructure Solutions Group",
                "source_name": "Dell FY26 Q1 earnings release",
                "period_or_version": "FY26 Q1",
                "text": (
                    "Segment table: ISG revenue was $10.3B; Servers and Networking revenue was $6.3B; "
                    "ISG operating income was $998M, or 9.7% of ISG revenue."
                ),
                "cannot_infer": [
                    "AI server gross margin",
                    "Blackwell mix",
                    "attach economics",
                ],
            },
            {
                "fixture_id": "nvda_q1_fy2027_data_center_revenue",
                "issuer": "NVDA",
                "product_or_family": "Data Center / accelerator systems",
                "source_name": "NVIDIA Q1 FY2027 IR page",
                "period_or_version": "Q1 FY2027",
                "text": "Revenue table: Data Center revenue was $39.1B and represented record demand for AI infrastructure.",
                "cannot_infer": [
                    "B200/GB200 SKU revenue",
                    "DELL allocation",
                    "server OEM margin",
                ],
            },
        ],
        "official_product_spec_page_adapter": [
            {
                "fixture_id": "nvda_gb200_nvl72_architecture",
                "issuer": "NVDA",
                "product_or_family": "GB200 NVL72",
                "source_name": "NVIDIA GB200 NVL72 official page",
                "period_or_version": "Blackwell / GB200 generation",
                "text": "Official product page: GB200 NVL72 includes 36 Grace CPUs, 72 Blackwell GPUs, rack-scale NVLink and liquid-cooled deployment.",
                "cannot_infer": [
                    "GB200 SKU revenue",
                    "customer purchase quantity",
                    "server OEM gross margin",
                ],
            },
            {
                "fixture_id": "amd_mi300x_memory_bandwidth",
                "issuer": "AMD",
                "product_or_family": "MI300X",
                "source_name": "AMD MI300X official product page",
                "period_or_version": "MI300X generation",
                "text": "Official product page: MI300X discloses 192GB HBM3 memory, 5.3 TB/s memory bandwidth, CDNA3 architecture, FP8 and FP16 support.",
                "cannot_infer": [
                    "MI300X revenue",
                    "market share",
                    "cloud deployment volume",
                ],
            },
            {
                "fixture_id": "google_tpu_v6e_trillium_architecture",
                "issuer": "GOOGL",
                "product_or_family": "TPU v6e / Trillium",
                "source_name": "Google Cloud TPU docs",
                "period_or_version": "TPU v6e / Trillium",
                "text": "Official docs: TPU v6e / Trillium describes TPU compute, HBM, ICI, pod size, and network/all-reduce characteristics.",
                "cannot_infer": [
                    "TPU procurement mix",
                    "NVIDIA replacement ratio",
                    "Google internal unit economics",
                ],
            },
        ],
        "semicap_bookings_backlog_adapter": [
            {
                "fixture_id": "asml_q1_2026_lithography_cycle",
                "issuer": "ASML",
                "product_or_family": "EUV / DUV lithography and installed base",
                "source_name": "ASML Q1 2026 release",
                "period_or_version": "Q1 2026",
                "text": "Quarterly release: ASML disclosed net sales, gross margin, installed-base management sales, new and used lithography systems sold, and 2026 guide.",
                "cannot_infer": [
                    "AI-specific ASML orders",
                    "customer allocation",
                    "bookings by end customer without table",
                ],
            },
            {
                "fixture_id": "amat_q2_fy26_semiconductor_systems_mix",
                "issuer": "AMAT",
                "product_or_family": "Semiconductor Systems",
                "source_name": "AMAT Q2 FY26 release",
                "period_or_version": "Q2 FY26",
                "text": "Segment release: AMAT disclosed revenue, gross margin, Semiconductor Systems segment, foundry/logic, DRAM, flash and services mix.",
                "cannot_infer": [
                    "AI-specific order backlog",
                    "single-customer exposure",
                    "HBM tool share",
                ],
            },
            {
                "fixture_id": "lrcx_mar_2026_memory_hbm_intensity",
                "issuer": "LRCX",
                "product_or_family": "Etch / deposition / memory and HBM process intensity",
                "source_name": "LRCX Mar 2026 results",
                "period_or_version": "Mar 2026 quarter",
                "text": "Quarterly results: Lam disclosed revenue, gross margin, memory and foundry/logic context, customer support business and HBM process intensity commentary.",
                "cannot_infer": [
                    "AI-specific LRCX bookings",
                    "exact HBM equipment share",
                    "customer purchase orders",
                ],
            },
        ],
    }
    return fixtures_by_family[adapter_family]


def _parse_fixture_by_adapter_family(adapter_family: str, fixture: Mapping[str, Any]) -> dict[str, Any]:
    if adapter_family == "sec_8k_earnings_release_table_adapter":
        rows = _parse_sec_8k_fixture(fixture)
    elif adapter_family == "official_product_spec_page_adapter":
        rows = _parse_official_product_spec_fixture(fixture)
    elif adapter_family == "semicap_bookings_backlog_adapter":
        rows = _parse_semicap_fixture(fixture)
    else:
        rows = []
    typed_gaps: list[dict[str, Any]] = []
    if not rows:
        typed_gaps.append(
            {
                "fixture_id": fixture["fixture_id"],
                "adapter_family": adapter_family,
                "gap_type": "parser_gap",
                "reason": "fixture did not contain enough adapter-specific fields to create a normalized runtime row",
            }
        )
    rejected_candidates = _adapter_rejected_candidates(adapter_family, fixture)
    return {
        "fixture_id": fixture["fixture_id"],
        "adapter_family": adapter_family,
        "source_name": fixture["source_name"],
        "fixture_source_ref": f"docs/project_os/ai_semis_gold_depth_content_pack_v0_1.json::{fixture['fixture_id']}",
        "runtime_row_count": len(rows),
        "rejected_candidate_count": len(rejected_candidates),
        "typed_gap_count": len(typed_gaps),
        "runtime_rows": rows,
        "rejected_candidates": rejected_candidates,
        "typed_gaps": typed_gaps,
    }


def _parse_sec_8k_fixture(fixture: Mapping[str, Any]) -> list[dict[str, Any]]:
    text = str(fixture["text"])
    lower = text.lower()
    parsed_fields: dict[str, Any] = {}
    if "orders" in lower and "shipments" in lower and "backlog" in lower:
        parsed_fields = {
            "orders": _money_phrase(text, "orders"),
            "shipments": _money_phrase(text, "shipments"),
            "backlog": _money_phrase(text, "backlog"),
        }
        metric = "orders_shipments_backlog"
        value = f"orders {parsed_fields['orders']}; shipments {parsed_fields['shipments']}; backlog {parsed_fields['backlog']}"
        unit = "USD billions"
        authority = "issuer_exact_operating_metric_with_margin_gap"
    elif "operating income" in lower and "isg revenue" in lower:
        parsed_fields = {
            "isg_revenue": _money_phrase(text, "ISG revenue"),
            "servers_networking_revenue": _money_phrase(text, "Servers and Networking revenue"),
            "operating_income": _money_phrase(text, "operating income"),
            "operating_margin": _percent_phrase(text),
        }
        metric = "isg_revenue_operating_income_margin"
        value = (
            f"ISG revenue {parsed_fields['isg_revenue']}; Servers/Networking {parsed_fields['servers_networking_revenue']}; "
            f"operating income {parsed_fields['operating_income']}; margin {parsed_fields['operating_margin']}"
        )
        unit = "USD / percent"
        authority = "issuer_exact_segment_metric_not_ai_server_margin"
    elif "data center revenue" in lower:
        parsed_fields = {"data_center_revenue": _money_phrase(text, "Data Center revenue")}
        metric = "data_center_revenue"
        value = parsed_fields["data_center_revenue"]
        unit = "USD billions"
        authority = "issuer_exact_segment_metric_not_sku_revenue"
    else:
        return []
    return [_runtime_row(fixture, "sec_8k_earnings_release_table_adapter", metric, value, unit, authority, parsed_fields)]


def _parse_official_product_spec_fixture(fixture: Mapping[str, Any]) -> list[dict[str, Any]]:
    text = str(fixture["text"])
    lower = text.lower()
    parsed_fields: dict[str, Any] = {}
    if "grace cpus" in lower and "blackwell gpus" in lower:
        parsed_fields = {
            "grace_cpus": _integer_before(text, "Grace CPUs"),
            "blackwell_gpus": _integer_before(text, "Blackwell GPUs"),
            "interconnect": "rack-scale NVLink" if "NVLink" in text else "",
            "deployment": "liquid-cooled" if "liquid-cooled" in lower else "",
        }
        metric = "rack_scale_architecture_spec"
        value = f"{parsed_fields['grace_cpus']} Grace CPUs; {parsed_fields['blackwell_gpus']} Blackwell GPUs; rack-scale NVLink; liquid-cooled"
    elif "hbm3" in lower and "tb/s" in lower:
        parsed_fields = {
            "memory": _memory_phrase(text),
            "bandwidth": _bandwidth_phrase(text),
            "architecture": "CDNA3" if "CDNA3" in text else "",
            "precision_support": "FP8/FP16" if "FP8" in text and "FP16" in text else "",
        }
        metric = "accelerator_memory_bandwidth_spec"
        value = f"{parsed_fields['memory']}; {parsed_fields['bandwidth']}; {parsed_fields['architecture']}; {parsed_fields['precision_support']}"
    elif "tpu" in lower and "hbm" in lower:
        parsed_fields = {
            "compute": "TPU compute",
            "memory": "HBM",
            "interconnect": "ICI",
            "scale": "pod size / network all-reduce",
        }
        metric = "custom_accelerator_architecture_spec"
        value = "TPU compute; HBM; ICI; pod size; network/all-reduce"
    else:
        return []
    return [
        _runtime_row(
            fixture,
            "official_product_spec_page_adapter",
            metric,
            value,
            "technical specification",
            "official_technical_fact_not_revenue_or_share",
            parsed_fields,
        )
    ]


def _parse_semicap_fixture(fixture: Mapping[str, Any]) -> list[dict[str, Any]]:
    text = str(fixture["text"])
    lower = text.lower()
    parsed_fields: dict[str, Any] = {}
    if "asml" in str(fixture["issuer"]).lower() or "lithography" in lower:
        parsed_fields = {
            "net_sales": "present" if "net sales" in lower else "",
            "gross_margin": "present" if "gross margin" in lower else "",
            "installed_base": "present" if "installed-base" in lower else "",
            "systems_sold": "present" if "systems sold" in lower else "",
            "guide": "present" if "guide" in lower else "",
        }
        metric = "lithography_cycle_disclosure"
        value = "net sales; gross margin; installed-base management; systems sold; guide"
        authority = "semicap_primary_disclosure_context_or_exact_if_table_bound"
    elif "semiconductor systems" in lower:
        parsed_fields = {
            "revenue": "present" if "revenue" in lower else "",
            "gross_margin": "present" if "gross margin" in lower else "",
            "semiconductor_systems": "present",
            "end_market_mix": "foundry/logic; DRAM; flash; services",
        }
        metric = "semiconductor_systems_mix_disclosure"
        value = "revenue; gross margin; Semiconductor Systems; foundry/logic; DRAM; flash; services mix"
        authority = "semicap_segment_mix_context_or_exact_if_table_bound"
    elif "hbm" in lower or "memory" in lower:
        parsed_fields = {
            "revenue": "present" if "revenue" in lower else "",
            "gross_margin": "present" if "gross margin" in lower else "",
            "memory_context": "present" if "memory" in lower else "",
            "hbm_process_intensity": "present" if "hbm" in lower else "",
        }
        metric = "memory_hbm_process_intensity_context"
        value = "revenue; gross margin; memory/foundry logic context; HBM process intensity"
        authority = "semicap_process_intensity_context_not_customer_order"
    else:
        return []
    return [_runtime_row(fixture, "semicap_bookings_backlog_adapter", metric, value, "disclosure context", authority, parsed_fields)]


def _runtime_row(
    fixture: Mapping[str, Any],
    adapter_family: str,
    metric_or_attribute: str,
    value: str,
    unit: str,
    authority_scope: str,
    parsed_fields: Mapping[str, Any],
) -> dict[str, Any]:
    fixture_id = str(fixture["fixture_id"])
    return {
        "row_id": f"p34_fixture_row::{fixture_id}",
        "issuer": fixture["issuer"],
        "product_or_family": fixture["product_or_family"],
        "metric_or_attribute": metric_or_attribute,
        "value": value,
        "unit": unit,
        "period_or_version": fixture["period_or_version"],
        "source_url": f"source-ledger://p34/{adapter_family}/{fixture_id}",
        "citation": fixture["source_name"],
        "parser_lineage": {
            "adapter_family": adapter_family,
            "fixture_id": fixture_id,
            "parser_version": "p34_adapter_fixture_parser_v0_1",
            "parsed_fields": dict(parsed_fields),
            "input_ref": f"docs/project_os/ai_semis_gold_depth_content_pack_v0_1.json::{fixture_id}",
        },
        "authority_scope": authority_scope,
        "cannot_infer": list(fixture.get("cannot_infer") or []),
        "promotion_status": "fixture_parser_contract_pass_live_fetch_pending",
    }


def _adapter_rejected_candidates(adapter_family: str, fixture: Mapping[str, Any]) -> list[dict[str, Any]]:
    rejected_by_family = {
        "sec_8k_earnings_release_table_adapter": (
            "consolidated_revenue_substitute",
            "Consolidated revenue without product/segment/AI-server binding cannot fill this slot.",
        ),
        "official_product_spec_page_adapter": (
            "marketing_page_without_spec_slot",
            "A generic product page without architecture/spec/version fields cannot be promoted.",
        ),
        "semicap_bookings_backlog_adapter": (
            "peer_group_scope_substitute",
            "Semicap peer group membership cannot replace company-specific segment/bookings/backlog mechanism.",
        ),
    }
    candidate_type, reason = rejected_by_family[adapter_family]
    return [
        {
            "fixture_id": fixture["fixture_id"],
            "adapter_family": adapter_family,
            "candidate_type": candidate_type,
            "rejection_reason": reason,
            "typed_gap_if_no_better_source": "parser_gap",
        }
    ]


def _money_phrase(text: str, label: str) -> str:
    pattern = rf"{re.escape(label)}(?:\s+(?:was|of|above|about))?\s*(?:was\s*)?(?:above\s*)?(?:about\s*)?\$?([0-9]+(?:\.[0-9]+)?)\s*([BM])"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match and label.lower() == "backlog":
        match = re.search(r"backlog\s+(?:of\s*)?(?:about\s*)?\$?([0-9]+(?:\.[0-9]+)?)\s*([BM])", text, flags=re.IGNORECASE)
    if not match:
        return "present_unparsed_amount"
    return f"{match.group(1)}{match.group(2).upper()}"


def _percent_phrase(text: str) -> str:
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)%", text)
    return f"{match.group(1)}%" if match else "present_unparsed_percent"


def _integer_before(text: str, label: str) -> str:
    match = re.search(rf"([0-9]+)\s+{re.escape(label)}", text, flags=re.IGNORECASE)
    return match.group(1) if match else "present_unparsed_count"


def _memory_phrase(text: str) -> str:
    match = re.search(r"([0-9]+GB\s+HBM[0-9A-Za-z]*)", text)
    return match.group(1) if match else "present_unparsed_memory"


def _bandwidth_phrase(text: str) -> str:
    match = re.search(r"([0-9]+(?:\.[0-9]+)?\s+TB/s)", text)
    return match.group(1) if match else "present_unparsed_bandwidth"


def _route_families_for_contract(contract: Mapping[str, Any]) -> list[str]:
    families: list[str] = []
    for family in contract.get("source_route_family") or []:
        family = str(family)
        if family not in families:
            families.append(family)
    if not families:
        families.append("route_gap_unclassified_adapter")
    fallback = FALLBACK_ROUTE_FAMILY_BY_PRIMARY.get(families[0])
    if fallback and fallback not in families:
        families.append(fallback)
    return families


def _build_route(
    route_id: str,
    route_role: str,
    adapter_family: str,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    descriptor = ROUTE_FAMILY_CATALOG.get(
        adapter_family,
        {
            "source_role": "unclassified_source_role",
            "source_examples": [],
            "locator_strategy": "Route family needs explicit locator strategy before execution.",
            "parser_strategy": "Route family needs explicit parser strategy before execution.",
            "authority_scope": "route_gap_until_adapter_defined",
        },
    )
    p33_status = str(contract.get("p33_backfill_status") or "unknown")
    return {
        "route_id": route_id,
        "evidence_row_id": contract.get("evidence_row_id"),
        "judgment_chain_ids": list(contract.get("judgment_chain_ids") or []),
        "route_role": route_role,
        "adapter_family": adapter_family,
        "source_role": descriptor["source_role"],
        "source_examples": descriptor["source_examples"],
        "issuer": _issuer_from_required_fields_or_row(contract),
        "target_product_or_family": _product_hint(contract),
        "metric_or_attribute_hint": _metric_hint(contract),
        "locator_strategy": descriptor["locator_strategy"],
        "parser_strategy": descriptor["parser_strategy"],
        "parser_output_contract": {
            "required_fields": list(contract.get("required_fields") or []),
            "normalized_runtime_row_fields": NORMALIZED_RUNTIME_ROW_FIELDS,
            "must_preserve": [
                "source_url",
                "citation",
                "parser_lineage",
                "period_or_version",
                "authority_scope",
                "cannot_infer",
            ],
        },
        "promotion_preconditions": [
            "issuer binding matches contract",
            "product_or_family or metric_or_attribute is specific enough for the judgment chain",
            "source_url and citation are present",
            "parser_lineage is present",
            "authority_scope is compatible with quality_role",
            "forbidden_substitutes are absent",
        ],
        "promotion_rule": contract.get("promotion_rule"),
        "forbidden_substitutes": list(contract.get("forbidden_substitutes") or []),
        "cannot_infer": list(contract.get("cannot_infer") or []),
        "typed_gap_rules": _typed_gap_rules(adapter_family, p33_status),
        "authority_scope": descriptor["authority_scope"],
        "p33_backfill_status": p33_status,
        "route_execution_status": "planned_not_executed",
        "promotion_without_execution_allowed": False,
        "attempt_contract": {
            "minimum_attempts_before_external_gap": 2,
            "must_record": [
                "route_id",
                "attempted_url_or_query",
                "fetch_status",
                "parser_status",
                "row_count",
                "failure_reason",
                "source_snapshot_ref",
            ],
            "failure_must_not_be_written_as": "public_source_absent_without_attempt",
        },
    }


def _typed_gap_rules(adapter_family: str, p33_status: str) -> list[dict[str, str]]:
    rules = [
        {
            "gap_type": "locator_gap",
            "when": "official source family is known but no candidate URL/document is found after allowed-domain search",
        },
        {
            "gap_type": "parser_gap",
            "when": "document/page is located but table/spec/metric/entity relation cannot be parsed with required fields",
        },
        {
            "gap_type": "source_absent_after_attempt",
            "when": "issuer or official source does not disclose the required slot after documented attempts",
        },
    ]
    if adapter_family in {"options_or_short_interest_proxy_adapter", "credit_or_debt_context_adapter"}:
        rules.append(
            {
                "gap_type": "commercial_gap",
                "when": "public delayed/proxy source cannot provide exact real-time or licensed market data",
            }
        )
    if p33_status == "case_binding_required_before_live_lookup":
        rules.append(
            {
                "gap_type": "case_binding_required",
                "when": "basket/rubric slot must be bound to issuer, ticker, lane and source route before lookup",
            }
        )
    return rules


def _slot_route_plan_status(p33_status: str) -> str:
    if p33_status == "live_runtime_ready":
        return "route_plan_ready_existing_live_row_requires_revalidation"
    if p33_status == "route_candidate_only_parser_lineage_pending":
        return "route_plan_ready_parser_lineage_repair_required"
    if p33_status == "source_route_candidate_weak_not_bound":
        return "route_plan_ready_adapter_fixture_required_before_promotion"
    if p33_status == "case_binding_required_before_live_lookup":
        return "route_plan_ready_case_binding_required_before_lookup"
    return "route_plan_ready_status_needs_review"


def _issuer_from_required_fields_or_row(contract: Mapping[str, Any]) -> str:
    row_id = str(contract.get("evidence_row_id") or "")
    for prefix, issuer in (
        ("dell_", "DELL"),
        ("nvda_", "NVDA"),
        ("amd_", "AMD"),
        ("google_", "GOOGL"),
        ("alphabet_", "GOOGL"),
        ("msft_", "MSFT"),
        ("amzn_", "AMZN"),
        ("meta_", "META"),
        ("tsmc_", "TSM"),
        ("asml_", "ASML"),
        ("amat_", "AMAT"),
        ("lrcx_", "LRCX"),
    ):
        if row_id.startswith(prefix):
            return issuer
    if row_id.startswith("market_price_in") or row_id.startswith("counter_thesis"):
        return "AI_SEMIS_BASKET"
    return "issuer_binding_required"


def _product_hint(contract: Mapping[str, Any]) -> str:
    row_id = str(contract.get("evidence_row_id") or "")
    parts = row_id.split("_")
    return " ".join(parts[1:5]) if len(parts) > 2 else row_id


def _metric_hint(contract: Mapping[str, Any]) -> str:
    quality_role = str(contract.get("quality_role") or "")
    return quality_role or str(contract.get("evidence_row_id") or "")


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)
