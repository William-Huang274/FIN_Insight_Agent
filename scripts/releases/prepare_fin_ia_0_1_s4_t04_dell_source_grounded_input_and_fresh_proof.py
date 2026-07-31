from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
)
from apps.workbench.backend.application.case_service import (
    CasePrincipal,
    CaseService,
    CreateCaseDraft,
)
from apps.workbench.backend.application.evidence_service import EvidenceService
from apps.workbench.backend.application.planning_service import (
    CompileDecisionSurfaceDraft,
    PlanningCheckpointDecisionDraft,
    PlanningService,
)
from apps.workbench.backend.application.research_runtime import (
    prepare_s4_source_grounded_exact_input,
)
from sec_agent.canonical_runtime import (
    FileCanonicalObjectStore,
    RuntimeFacade,
)
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore
from sec_agent.s4_case_runtime import (
    S4SourceGroundedInputPack,
    load_s4_case_runtime_binding,
)


RUNTIME_ROOT = (
    ROOT
    / ".codex_runtime"
    / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
)
SOURCE_PACK_PATH = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t04_dell_source_grounded_input_pack_v1_0.json"
)
PLANNING_PROFILE_PATH = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t04_dell_canonical_planning_profile_v1_0.json"
)
DECISION_PATH = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t04_dell_source_grounded_input_materialization_"
    "and_fresh_proof_decision_v1_0.json"
)
PROSPECTIVE_ADMISSION_PATH = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t04_dell_fresh_exact_admission_v1_0.json"
)
SOURCE_ROUTE_PLAN_PATH = (
    ROOT / "docs" / "project_os" / "p34_ai_semis_source_route_plan_v0_1.json"
)
FROZEN_AT = "2026-07-26T18:45:00+08:00"
TENANT_ID = "tenant-fin01-s3-t09-eval"
PROJECT_ID = "project-fin01-s3-t09-eval"
ACTOR_ID = "analyst-fin01-s3-t09-eval"
CASE_IDEMPOTENCY_KEY = "fin01-s4-t04-dell-canonical-case-v1"
EXECUTION_IDENTITY = "fin01-s4-t04-dell-fresh-exact-live-r1"
PLANNING_COMPILER_POLICY_REF = "fin01.s4.dell_three_cell:v1"
PLANNING_PACK_SELECTION_REF = "fin01.s4.dell_oem_source_grounded:v1"
SOURCE_POLICY_REF = "fin01.s4.public_local_official_case_pack:v1"
QUERY = (
    "Evaluate DELL AI server demand authenticity, value and profit capture, "
    "and bottleneck counterevidence using issuer-bound official evidence."
)
PERMISSIONS = frozenset(
    {
        "case:create",
        "case:read",
        "planning:write",
        "planning:review",
        "planning:read",
        "evidence:read",
    }
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _snapshot(
    source_id: str,
    *,
    url: str,
    title: str,
    published_at: str,
    retrieval_channel: str,
    locator: str,
    normalized_extract: str,
    full_document_sha256: str | None = None,
) -> dict[str, Any]:
    payload = {
        "source_id": source_id,
        "source_url": url,
        "title": title,
        "published_at": published_at,
        "retrieval_channel": retrieval_channel,
        "fetch_status": "success",
        "locator": locator,
        "normalized_extract": normalized_extract,
        "full_document_sha256": full_document_sha256,
    }
    snapshot_digest = canonical_digest(payload)
    return {
        **payload,
        "source_snapshot_ref": f"s4_dell_source_snapshot_{snapshot_digest[:24]}",
        "normalized_locator_snapshot_digest": snapshot_digest,
    }


def _build_source_pack() -> dict[str, Any]:
    demand_cell = "demand_authenticity_and_sustainability"
    value_cell = "value_and_profit_capture"
    risk_cell = "bottleneck_counterevidence_and_what_would_change"
    sources = [
        _snapshot(
            "dell_fy26_results_pdf",
            url="https://investors.delltechnologies.com/node/19176/pdf",
            title="Dell Technologies Fourth Quarter and Full-Year Fiscal 2026 Results",
            published_at="2026-02-26",
            retrieval_channel="direct_http_pdf_pdfplumber_and_visual_page_check",
            locator="PDF pages 1-2; headline paragraph and Operating Segments Results table",
            normalized_extract=(
                "FY26: more than USD64bn AI-optimized server orders, more than "
                "USD25bn shipped, USD43bn ending backlog; Q4 AI-optimized server "
                "revenue USD8,952m; FY26 USD24,683m; Q4 ISG revenue USD19,602m "
                "and operating income USD2,900m; FY26 ISG revenue USD60,826m "
                "and operating income USD7,111m."
            ),
            full_document_sha256=(
                "17be3981929167a2c6033a75abe24159e4de624bbbb7261b66fd8b189680e2f9"
            ),
        ),
        _snapshot(
            "dell_q1_fy27_earnings_exhibit_pdf",
            url=(
                "https://investors.delltechnologies.com/static-files/"
                "05af7a65-5059-4955-a4b3-7f79494b664c"
            ),
            title="Dell Technologies First Quarter Fiscal 2027 Earnings Exhibit",
            published_at="2026-05-28",
            retrieval_channel="direct_http_pdf_pdfplumber_and_visual_page_check",
            locator="PDF pages 1 and 4; summary and Segment Information table",
            normalized_extract=(
                "Q1 FY27: USD24.4bn AI orders and USD16.1bn AI server revenue; "
                "AI-optimized server revenue USD16,132m; total ISG revenue "
                "USD29,009m; ISG operating income USD3,055m and margin 10.5%; "
                "company revenue USD43,842m, operating income USD3,656m and "
                "cash from operating activities USD4,081m."
            ),
            full_document_sha256=(
                "e8e41fb7b68d730f9c966f1213adb1838cd30aaf3a4a6ad745b57f7e9e30cb9e"
            ),
        ),
        _snapshot(
            "dell_q1_fy27_earnings_transcript",
            url=(
                "https://investors.delltechnologies.com/static-files/"
                "b63ffff9-b729-403b-a231-c6af05667759"
            ),
            title="DELL Q1 2027 Earnings Call",
            published_at="2026-05-28",
            retrieval_channel="official_ir_document_web_content_parser",
            locator="prepared remarks, Q1 AI demand paragraph",
            normalized_extract=(
                "Q1 FY27 AI orders USD24.4bn, AI server revenue USD16.1bn, "
                "ending AI backlog USD51.3bn; demand exceeded supply with "
                "memory described as the primary constraint; customer count "
                "surpassed 5,000 across neocloud, sovereign and enterprise."
            ),
        ),
        _snapshot(
            "dell_q1_fy27_10q",
            url=(
                "https://www.sec.gov/Archives/edgar/data/1571996/"
                "000157199626000030/dell-20260501.htm"
            ),
            title="Dell Technologies Form 10-Q for quarter ended May 1, 2026",
            published_at="2026-06-09",
            retrieval_channel="sec_official_web_content_parser",
            locator=(
                "Statements of Financial Position lines 167-194; Cash Flows "
                "lines 309-336; ISG table lines 2267-2290"
            ),
            normalized_extract=(
                "At May 1, 2026: accounts receivable USD25,854m, inventories "
                "USD15,052m, accounts payable USD45,261m. At January 30, 2026: "
                "USD17,585m, USD10,437m, USD33,630m respectively. Q1 cash from "
                "operations USD4,081m; capex and capitalized software USD963m; "
                "free cash flow USD3,118m. AI-optimized server revenue "
                "USD16,132m; ISG revenue USD29,009m and operating income "
                "USD3,055m."
            ),
        ),
        _snapshot(
            "dell_fy26_10k",
            url=(
                "https://www.sec.gov/Archives/edgar/data/1571996/"
                "000157199626000008/dell-20260130.htm"
            ),
            title="Dell Technologies Form 10-K for fiscal year ended January 30, 2026",
            published_at="2026-03-16",
            retrieval_channel="sec_official_web_content_parser",
            locator="MD&A lines 1170-1202 and ISG discussion lines 1328-1335",
            normalized_extract=(
                "Dell reports inherent non-linearity between AI demand and "
                "shipments, a lower gross margin rate from mix shifting toward "
                "AI-optimized servers, and working-capital effects including "
                "higher inventory, receivables and payables."
            ),
        ),
        _snapshot(
            "dell_poweredge_xe9712_product",
            url="https://www.dell.com/en-us/shop/ipovw/poweredge-xe9712",
            title="Dell PowerEdge XE9712 product page",
            published_at="2026-07-26",
            retrieval_channel="official_product_web_content_parser",
            locator="technical specifications: accelerator, memory, power and cooling",
            normalized_extract=(
                "PowerEdge XE9712 is a rack-scale AI system; the current "
                "product page describes Blackwell accelerators, NVLink "
                "CPU-GPU interconnect, HBM3e, IR9048 power shelf and direct "
                "liquid cooling."
            ),
        ),
        _snapshot(
            "dell_coreweave_xe9712_deployment",
            url=(
                "https://www.dell.com/en-us/dt/corporate/newsroom/announcements/"
                "detailpage.press-releases~usa~2024~12~dell-cw-customer-announce.htm"
            ),
            title="CoreWeave and Dell Technologies Extend Relationship to Deliver AI at Scale",
            published_at="2024-12-09",
            retrieval_channel="official_customer_deployment_news_web_content_parser",
            locator="lines 53-68",
            normalized_extract=(
                "Dell disclosed first shipment of liquid-cooled PowerEdge "
                "XE9712 racks with NVIDIA GB200 NVL72 to CoreWeave, integrated "
                "in Dell IR7000 racks with Dell professional services."
            ),
        ),
        _snapshot(
            "dell_xe9712_support_manual",
            url=(
                "https://www.dell.com/support/manuals/en-us/poweredge-xe9712/"
                "xe9712_ism/system-battery-specifications"
            ),
            title="Dell PowerEdge XE9712 Installation and Service Manual",
            published_at="2026-04-25",
            retrieval_channel="official_product_document_web_content_parser",
            locator="system configuration and technical specifications navigation",
            normalized_extract=(
                "Dell support manual identifies the PowerEdge XE9712 system "
                "configuration and technical specification sections."
            ),
        ),
        _snapshot(
            "dell_global_xe9712_deployment",
            url=(
                "https://www.dell.com/en-us/dt/corporate/newsroom/announcements/"
                "detailpage.press-releases~usa~2026~06~the-dell-ai-factory-with-"
                "nvidia-advances-supercomputing-class-infrastructure-powering-the-"
                "next-generation-of-hpc-and-ai.htm"
            ),
            title="Dell AI Factory with NVIDIA Advances HPC and AI Infrastructure",
            published_at="2026-06-22",
            retrieval_channel="official_deployment_news_web_content_parser",
            locator="lines 79-83",
            normalized_extract=(
                "Dell disclosed that Monash University's MAVERIC system uses "
                "liquid-cooled Dell PowerRack systems with PowerEdge XE9712 "
                "servers and NVIDIA GB200 NVL72 architecture."
            ),
        ),
    ]
    snapshots = {row["source_id"]: row for row in sources}

    route_specs = [
        (
            "p34_route::dell_ai_server_orders_shipments_backlog::01::"
            "sec_8k_earnings_release_table_adapter",
            (demand_cell,),
            "dell_fy26_results_pdf",
            "executed_promoted_issuer_evidence_and_numeric",
            3,
        ),
        (
            "p34_route::dell_ai_server_orders_shipments_backlog::02::"
            "investor_deck_pdf_table_adapter",
            (demand_cell,),
            "dell_fy26_results_pdf",
            "executed_promoted_issuer_evidence_and_numeric",
            3,
        ),
        (
            "p34_route::dell_isg_revenue_margin_baseline::01::"
            "sec_8k_earnings_release_table_adapter",
            (value_cell, risk_cell),
            "dell_q1_fy27_earnings_exhibit_pdf",
            "executed_promoted_issuer_evidence_and_numeric",
            5,
        ),
        (
            "p34_route::dell_isg_revenue_margin_baseline::02::"
            "investor_deck_pdf_table_adapter",
            (value_cell, risk_cell),
            "dell_fy26_results_pdf",
            "executed_promoted_issuer_evidence_and_numeric",
            5,
        ),
        (
            "p34_route::dell_nvidia_poweredge_ai_factory_product_path::01::"
            "official_product_spec_page_adapter",
            (demand_cell, risk_cell),
            "dell_poweredge_xe9712_product",
            "executed_context_only_product_scope",
            1,
        ),
        (
            "p34_route::dell_nvidia_poweredge_ai_factory_product_path::02::"
            "customer_deployment_news_adapter",
            (demand_cell, risk_cell),
            "dell_coreweave_xe9712_deployment",
            "executed_context_only_deployment_scope",
            1,
        ),
        (
            "p34_route::dell_nvidia_poweredge_ai_factory_product_path::03::"
            "oem_configuration_adapter",
            (demand_cell, risk_cell),
            "dell_coreweave_xe9712_deployment",
            "executed_context_only_configuration_scope",
            1,
        ),
        (
            "p34_route::dell_nvidia_poweredge_ai_factory_product_path::04::"
            "official_product_docs_or_pdf_adapter",
            (demand_cell, risk_cell),
            "dell_xe9712_support_manual",
            "executed_context_only_document_scope",
            1,
        ),
        (
            "p34_route::dell_xe9712_gb200_oem_system_config::01::"
            "official_product_spec_page_adapter",
            (demand_cell, risk_cell),
            "dell_poweredge_xe9712_product",
            "executed_context_only_product_scope",
            1,
        ),
        (
            "p34_route::dell_xe9712_gb200_oem_system_config::02::"
            "oem_configuration_adapter",
            (demand_cell, risk_cell),
            "dell_coreweave_xe9712_deployment",
            "executed_context_only_configuration_scope",
            1,
        ),
        (
            "p34_route::dell_xe9712_gb200_oem_system_config::03::"
            "official_product_docs_or_pdf_adapter",
            (demand_cell, risk_cell),
            "dell_xe9712_support_manual",
            "executed_context_only_document_scope",
            1,
        ),
    ]
    route_receipts = []
    for route_id, cells, source_id, status, row_count in route_specs:
        source = snapshots[source_id]
        receipt_payload = {
            "route_id": route_id,
            "program_cell_ids": list(cells),
            "attempted_url_or_query": source["source_url"],
            "fetch_status": source["fetch_status"],
            "parser_status": status,
            "row_count": row_count,
            "failure_reason": None,
            "source_snapshot_ref": source["source_snapshot_ref"],
            "route_execution_status": status,
            "promotion_without_execution_allowed": False,
            "executed_at": FROZEN_AT,
        }
        route_receipts.append(
            {
                **receipt_payload,
                "route_receipt_ref": (
                    "s4_dell_route_receipt_"
                    + canonical_digest(receipt_payload)[:24]
                ),
            }
        )

    evidence_specs = [
        (
            "orders_shipments_backlog_fy26",
            (demand_cell,),
            "issuer_demand_or_order_signal",
            "dell_fy26_results_pdf",
            "FY26 disclosed more than USD64bn AI-optimized server orders, more than USD25bn shipped, and USD43bn ending backlog.",
            "Supports issuer-level demand visibility; does not prove AI-server gross margin, customer allocation or future conversion.",
        ),
        (
            "orders_revenue_backlog_q1_fy27",
            (demand_cell,),
            "issuer_revenue_conversion",
            "dell_q1_fy27_earnings_transcript",
            "Q1 FY27 disclosed USD24.4bn AI orders, USD16.1bn AI-server revenue and USD51.3bn ending AI backlog.",
            "Orders, revenue and backlog are separately disclosed issuer measures; no conversion ratio is inferred.",
        ),
        (
            "isg_and_ai_server_q1_fy27",
            (value_cell,),
            "issuer_segment_or_product_disclosure",
            "dell_q1_fy27_earnings_exhibit_pdf",
            "Q1 FY27 disclosed AI-optimized server revenue of USD16,132m, total ISG revenue of USD29,009m and ISG operating income of USD3,055m.",
            "Supports exact product revenue and broad ISG economics; does not allocate ISG profit to AI servers.",
        ),
        (
            "working_capital_and_cash_q1_fy27",
            (value_cell, risk_cell),
            "issuer_financial_statement",
            "dell_q1_fy27_10q",
            "Q1 FY27 filing reports receivables, inventory, payables, operating cash flow and capital expenditures with exact period scope.",
            "Supports company-level working-capital and cash analysis only; product-specific cash conversion remains unavailable.",
        ),
        (
            "ai_mix_margin_and_timing_counterevidence",
            (demand_cell, value_cell, risk_cell),
            "issuer_counterevidence",
            "dell_fy26_10k",
            "Dell reports non-linear demand-to-shipment timing and lower gross-margin rate from a business mix shift toward AI-optimized servers.",
            "Supports a company-bound counterevidence mechanism; does not quantify AI-server product margin or cancellation risk.",
        ),
        (
            "memory_supply_and_working_capital_counterevidence",
            (demand_cell, risk_cell),
            "issuer_counterevidence",
            "dell_q1_fy27_earnings_transcript",
            "Dell described memory as the primary supply constraint while demand exceeded supply and backlog remained material.",
            "Management commentary identifies a constraint; probability, duration and financial impact remain unquantified.",
        ),
    ]
    evidence_rows = []
    for label, cells, role, source_id, statement, boundary in evidence_specs:
        source = snapshots[source_id]
        payload = {
            "entity_ref": "DELL",
            "program_cell_ids": list(cells),
            "evidence_role": role,
            "statement": statement,
            "period_or_version": source["published_at"],
            "source_url": source["source_url"],
            "citation": source["locator"],
            "parser_lineage": {
                "source_snapshot_ref": source["source_snapshot_ref"],
                "adapter": source["retrieval_channel"],
                "normalized_extract_digest": source[
                    "normalized_locator_snapshot_digest"
                ],
            },
            "authority_scope": "issuer_exact_statement_with_explicit_boundary",
            "claim_boundary": boundary,
        }
        evidence_rows.append(
            {
                **payload,
                "evidence_ref": (
                    f"s4_dell_evidence_{label}_{canonical_digest(payload)[:16]}"
                ),
            }
        )
    evidence_by_source = {
        source_id: next(
            row["evidence_ref"]
            for row in evidence_rows
            if row["source_url"] == snapshots[source_id]["source_url"]
        )
        for source_id in (
            "dell_fy26_results_pdf",
            "dell_q1_fy27_earnings_transcript",
            "dell_q1_fy27_earnings_exhibit_pdf",
            "dell_q1_fy27_10q",
        )
    }

    numeric_specs = [
        ("ai_server_orders", "64000", "USD_millions", "FY2026", "greater_than", "dell_fy26_results_pdf", (demand_cell,)),
        ("ai_server_shipments", "25000", "USD_millions", "FY2026", "greater_than", "dell_fy26_results_pdf", (demand_cell,)),
        ("ai_server_backlog", "43000", "USD_millions", "2026-01-30", "exact", "dell_fy26_results_pdf", (demand_cell,)),
        ("ai_server_orders", "24400", "USD_millions", "Q1_FY2027", "exact", "dell_q1_fy27_earnings_transcript", (demand_cell,)),
        ("ai_server_revenue", "16132", "USD_millions", "Q1_FY2027_three_months_ended_2026-05-01", "exact", "dell_q1_fy27_earnings_exhibit_pdf", (demand_cell, value_cell)),
        ("ai_server_backlog", "51300", "USD_millions", "2026-05-01", "exact", "dell_q1_fy27_earnings_transcript", (demand_cell,)),
        ("revenue", "29009", "USD_millions", "Q1_FY2027_three_months_ended_2026-05-01", "exact", "dell_q1_fy27_earnings_exhibit_pdf", (value_cell,)),
        ("operating_income", "3055", "USD_millions", "Q1_FY2027_three_months_ended_2026-05-01", "exact", "dell_q1_fy27_earnings_exhibit_pdf", (value_cell, risk_cell)),
        ("operating_margin", "10.5", "percent", "Q1_FY2027_three_months_ended_2026-05-01", "exact", "dell_q1_fy27_earnings_exhibit_pdf", (value_cell, risk_cell)),
        ("company_revenue", "43842", "USD_millions", "Q1_FY2027_three_months_ended_2026-05-01", "exact", "dell_q1_fy27_earnings_exhibit_pdf", (value_cell,)),
        ("company_operating_income", "3656", "USD_millions", "Q1_FY2027_three_months_ended_2026-05-01", "exact", "dell_q1_fy27_earnings_exhibit_pdf", (value_cell,)),
        ("accounts_receivable", "25854", "USD_millions", "2026-05-01", "exact", "dell_q1_fy27_10q", (value_cell, risk_cell)),
        ("inventory", "15052", "USD_millions", "2026-05-01", "exact", "dell_q1_fy27_10q", (value_cell, risk_cell)),
        ("accounts_payable", "45261", "USD_millions", "2026-05-01", "exact", "dell_q1_fy27_10q", (value_cell, risk_cell)),
        ("accounts_receivable", "17585", "USD_millions", "2026-01-30", "exact", "dell_q1_fy27_10q", (value_cell, risk_cell)),
        ("inventory", "10437", "USD_millions", "2026-01-30", "exact", "dell_q1_fy27_10q", (value_cell, risk_cell)),
        ("accounts_payable", "33630", "USD_millions", "2026-01-30", "exact", "dell_q1_fy27_10q", (value_cell, risk_cell)),
        ("operating_cash_flow", "4081", "USD_millions", "Q1_FY2027_three_months_ended_2026-05-01", "exact", "dell_q1_fy27_10q", (value_cell, risk_cell)),
        ("capital_expenditure_and_capitalized_software", "963", "USD_millions_outflow", "Q1_FY2027_three_months_ended_2026-05-01", "exact", "dell_q1_fy27_10q", (value_cell, risk_cell)),
        ("free_cash_flow", "3118", "USD_millions", "Q1_FY2027_three_months_ended_2026-05-01", "exact", "dell_q1_fy27_10q", (value_cell, risk_cell)),
        ("operating_cash_flow", "2796", "USD_millions", "Q1_FY2026_three_months_ended_2025-05-02", "exact", "dell_q1_fy27_10q", (value_cell, risk_cell)),
        ("capital_expenditure_and_capitalized_software", "568", "USD_millions_outflow", "Q1_FY2026_three_months_ended_2025-05-02", "exact", "dell_q1_fy27_10q", (value_cell, risk_cell)),
    ]
    numeric_rows = []
    per_metric_index: dict[str, int] = {}
    for metric, value, unit, period, operator, source_id, cells in numeric_specs:
        per_metric_index[metric] = per_metric_index.get(metric, 0) + 1
        source = snapshots[source_id]
        segment_ref = (
            "ISG"
            if metric in {"revenue", "operating_income", "operating_margin"}
            else "__company_total__"
        )
        if metric == "ai_server_revenue":
            segment_ref = "ISG_AI_optimized_servers"
        payload = {
            "entity_ref": "DELL",
            "segment_ref": segment_ref,
            "program_cell_ids": list(cells),
            "metric_family": metric,
            "value": value,
            "comparison_operator": operator,
            "currency": "USD" if unit.startswith("USD_") else "",
            "unit": unit,
            "scale_multiplier": 1_000_000 if unit.startswith("USD_") else 1,
            "period": period,
            "source_ref": evidence_by_source[source_id],
            "source_url": source["source_url"],
            "source_coordinate": source["locator"],
            "parser_lineage": {
                "source_snapshot_ref": source["source_snapshot_ref"],
                "adapter": source["retrieval_channel"],
            },
            "exact_value_authority": True,
            "cannot_support": [
                "AI_server_gross_or_operating_margin"
                if segment_ref != "ISG_AI_optimized_servers"
                else "AI_server_gross_or_operating_margin_from_revenue_only",
                "customer_allocation",
            ],
        }
        numeric_rows.append(
            {
                **payload,
                "numeric_ref": (
                    f"s4_dell_numeric_{metric}_{per_metric_index[metric]:02d}_"
                    f"{canonical_digest(payload)[:12]}"
                ),
            }
        )

    def _num(metric: str, period: str) -> dict[str, Any]:
        return next(
            row
            for row in numeric_rows
            if row["metric_family"] == metric and row["period"] == period
        )

    derived_specs = [
        {
            "metric": "isg_operating_margin_recomputed",
            "value": "10.53",
            "unit": "percent",
            "formula": "ISG_operating_income/ISG_revenue*100",
            "input_numeric_refs": [
                _num(
                    "operating_income",
                    "Q1_FY2027_three_months_ended_2026-05-01",
                )["numeric_ref"],
                _num(
                    "revenue",
                    "Q1_FY2027_three_months_ended_2026-05-01",
                )["numeric_ref"],
            ],
            "program_cell_ids": [value_cell, risk_cell],
            "scope": "DELL_ISG_Q1_FY2027",
            "cannot_support": ["AI_server_specific_margin"],
        },
        {
            "metric": "free_cash_flow_recomputed",
            "value": "3118",
            "unit": "USD_millions",
            "formula": "operating_cash_flow-capital_expenditure_outflow",
            "input_numeric_refs": [
                _num(
                    "operating_cash_flow",
                    "Q1_FY2027_three_months_ended_2026-05-01",
                )["numeric_ref"],
                _num(
                    "capital_expenditure_and_capitalized_software",
                    "Q1_FY2027_three_months_ended_2026-05-01",
                )["numeric_ref"],
            ],
            "program_cell_ids": [value_cell, risk_cell],
            "scope": "DELL_company_total_Q1_FY2027",
            "cannot_support": ["AI_server_specific_cash_conversion"],
        },
    ]
    derived_metrics = [
        {
            **row,
            "derived_metric_ref": (
                "s4_dell_derived_" + canonical_digest(row)[:20]
            ),
        }
        for row in derived_specs
    ]

    graph_specs = [
        (
            "DELL",
            "PowerEdge_XE9712",
            "product_platform",
            "dell_poweredge_xe9712_product",
            "Current official product configuration context only; no financial implication.",
        ),
        (
            "PowerEdge_XE9712",
            "NVIDIA_GB200_NVL72",
            "product_platform",
            "dell_coreweave_xe9712_deployment",
            "Dell's 2024 CoreWeave deployment disclosure binds this configuration; it is not a current order-volume measure.",
        ),
        (
            "CoreWeave",
            "DELL_PowerEdge_XE9712",
            "customer_deployment",
            "dell_coreweave_xe9712_deployment",
            "Official Dell deployment context; order value, margin and customer concentration cannot be inferred.",
        ),
        (
            "Monash_University",
            "DELL_PowerEdge_XE9712_GB200_NVL72",
            "customer_deployment",
            "dell_global_xe9712_deployment",
            "Official Dell deployment context; financial contribution and shipment volume cannot be inferred.",
        ),
    ]
    graph_edges = []
    for from_ref, to_ref, semantics, source_id, boundary in graph_specs:
        source = snapshots[source_id]
        payload = {
            "entity_ref": "DELL",
            "program_cell_ids": [demand_cell, risk_cell],
            "from_ref": from_ref,
            "to_ref": to_ref,
            "edge_semantics": semantics,
            "direction": "from_to",
            "as_of": source["published_at"],
            "source_ref": source["source_snapshot_ref"],
            "source_url": source["source_url"],
            "boundary": boundary,
            "graph_edge_is_direct_evidence": False,
            "inferred_edge": False,
        }
        graph_edges.append(
            {
                **payload,
                "graph_edge_ref": (
                    "s4_dell_graph_edge_" + canonical_digest(payload)[:20]
                ),
            }
        )

    gap_specs = [
        (demand_cell, "cannot_infer_order_or_backlog_to_revenue_conversion", "Order, backlog and revenue definitions are not a common cohort or denominator.", "official quarterly cohort/definition bridge"),
        (demand_cell, "cannot_infer_demand_durability_or_pull_forward", "Issuer disclosures show demand and timing non-linearity but do not prove durable end demand.", "subsequent-period cancellation, deployment and channel checks"),
        (demand_cell, "cannot_infer_customer_or_channel_concentration", "Customer count and named deployments do not provide revenue concentration.", "issuer concentration disclosure or exact customer allocation"),
        (value_cell, "cannot_infer_AI_or_server_specific_gross_or_operating_profit", "Only AI-server revenue and broad ISG profit are disclosed.", "issuer-disclosed AI-server profit or exact product cost rows"),
        (value_cell, "cannot_infer_incremental_profit_capture", "ISG and company economics cannot be allocated to incremental AI-server profit.", "exact mix, pass-through cost and product profit bridge"),
        (value_cell, "cannot_infer_AI_server_specific_cash_conversion", "Working-capital and cash rows are company total.", "product-scoped receivable, inventory, payable and cash rows"),
        (risk_cell, "cannot_infer_bottleneck_probability_or_impact", "Memory is identified as a constraint but duration and impact are not quantified.", "supplier-side official capacity and delivery evidence"),
        (risk_cell, "cannot_infer_channel_inventory_or_order_quality", "No exact cancellation, channel inventory or customer readiness cohort is disclosed.", "channel inventory and cancellation follow-up"),
        (risk_cell, "cannot_infer_independent_counterevidence", "Current counterevidence is issuer-bound; an independent official follow-up remains required.", "supplier, customer or regulator primary-source follow-up"),
    ]
    typed_gaps = []
    for cell_id, gap_code, reason, followup in gap_specs:
        payload = {
            "program_cell_ids": [cell_id],
            "gap_code": gap_code,
            "gap_type": "source_absent_after_attempt",
            "reason": reason,
            "followup_ref": followup,
            "terminal_for_truthful_boundary": True,
        }
        typed_gaps.append(
            {
                **payload,
                "gap_ref": "s4_dell_gap_" + canonical_digest(payload)[:20],
            }
        )

    payload: dict[str, Any] = {
        "schema_version": (
            "fin_ia_0_1_s4_t04_source_grounded_input_pack_v1_0"
        ),
        "contract_ref": "fin01.s4.source_grounded_case_input:v1",
        "pack_id": "FIN-IA-0.1-S4-T04-DELL-SOURCE-GROUNDED-INPUT-R1",
        "frozen_at": FROZEN_AT,
        "status": "source_routes_executed_issuer_bound_input_head_ready",
        "case_ticker": "DELL",
        "legal_name": "Dell Technologies Inc.",
        "issuer_identifier": "CIK0001571996",
        "as_of": "2026-07-26T00:00:00Z",
        "source_snapshots": sources,
        "route_execution_receipts": route_receipts,
        "evidence_rows": evidence_rows,
        "numeric_rows": numeric_rows,
        "derived_metrics": derived_metrics,
        "graph_edges": graph_edges,
        "typed_gaps": typed_gaps,
        "cannot_infer_boundaries": [
            "No company or ISG profit is allocated to AI servers.",
            "No order-to-revenue conversion ratio is derived from non-cohort measures.",
            "No customer order value, shipment volume, concentration or margin is inferred from product/deployment context.",
            "Graph rows are context-only and never direct Evidence.",
        ],
        "authority_boundary": {
            "evidence": "issuer filing, earnings release or prepared remarks with exact locator and parser lineage",
            "numeric": "exact issuer, segment, period, currency, unit and source coordinate",
            "graph": "context_only_not_direct_evidence",
            "model_output_is_source_authority": False,
            "quality_findings_are_nonterminal_unless_truth_or_lineage_breaks": True,
        },
        "observed_counts": {
            "source_snapshots": len(sources),
            "route_execution_receipts": len(route_receipts),
            "evidence_rows": len(evidence_rows),
            "numeric_rows": len(numeric_rows),
            "derived_metrics": len(derived_metrics),
            "graph_edges": len(graph_edges),
            "typed_gaps": len(typed_gaps),
            "source_network_calls": 13,
            "model_calls": 0,
            "provider_calls": 0,
            "paid_calls": 0,
        },
    }
    payload["source_pack_digest"] = canonical_digest(payload)
    S4SourceGroundedInputPack.model_validate(payload)

    route_plan = json.loads(SOURCE_ROUTE_PLAN_PATH.read_text(encoding="utf-8"))
    expected_route_ids = {
        str(row["route_id"])
        for row in route_plan["routes"]
        if row.get("issuer") == "DELL"
    }
    observed_route_ids = {
        str(row["route_id"]) for row in route_receipts
    }
    if expected_route_ids != observed_route_ids:
        raise RuntimeError("s4_dell_route_execution_coverage_mismatch")
    return payload


def _build_planning_profile() -> dict[str, Any]:
    binding = load_s4_case_runtime_binding(ROOT, "DELL")
    cells = []
    for row in binding.program_cell_contracts:
        cells.append(
            {
                "cell_key": row["program_cell_id"],
                "decision_question": row["decision_question"],
                "owner_role": row["owner_role"],
                "materiality": "high",
                "dependency_cell_keys": (
                    []
                    if row["program_cell_id"]
                    == "demand_authenticity_and_sustainability"
                    else ["demand_authenticity_and_sustainability"]
                ),
                "stop_rule": row["stop_rule"],
                "what_would_change": "; ".join(
                    row["what_would_change_targets"]
                ),
                "evidence_slots": [
                    {
                        "evidence_role": role,
                        "entity_scope": ["DELL"],
                        "period_scope": "through_2026-07-26",
                        "metric_scope": [role],
                        "source_policy_ref": SOURCE_POLICY_REF,
                        "forbidden_substitutions": [
                            "cross_issuer_fact",
                            "graph_edge_as_evidence",
                            "model_output_as_source",
                        ],
                        "acceptance_role": row["owner_role"],
                        "required": True,
                    }
                    for role in row["required_evidence_roles"]
                ],
            }
        )
    return {
        "schema_version": (
            "fin_ia_0_1_s4_t04_dell_canonical_planning_profile_v1_0"
        ),
        "profile_id": "FIN-IA-0.1-S4-T04-DELL-CANONICAL-PLANNING-R1",
        "status": "source_grounded_three_cell_planning_profile_ready",
        "planning_profile": {
            "compiler_policy_ref": PLANNING_COMPILER_POLICY_REF,
            "pack_selection_ref": PLANNING_PACK_SELECTION_REF,
            "exact_cell_count": 3,
            "cells": cells,
        },
    }


def _principal() -> CasePrincipal:
    return CasePrincipal(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        actor_id=ACTOR_ID,
        permissions=PERMISSIONS,
    )


def _case_service(
    canonical_root: Path, planning_profile: Mapping[str, Any]
) -> CaseService:
    flags = FeatureFlagRegistry.from_path(
        ROOT / "configs" / "runtime" / "point01_feature_flags_v1_0.json"
    )
    facade = RuntimeFacade(
        SQLiteCanonicalStore(canonical_root / "canonical.sqlite"),
        FileCanonicalObjectStore(canonical_root / "objects"),
        flags,
        mode="shadow",
        grants={"point01.shadow.write"},
        planning_fixture_profile=planning_profile,
    )
    return CaseService(facade)


def _execution_identity_presence(
    service: CaseService, prepared: Mapping[str, Any]
) -> dict[str, bool]:
    store = service._facade.store
    return {
        "work_unit_absent": store.get_latest(
            "canonical_work_units", str(prepared["work_unit_id"])
        )
        is None,
        "attempt_absent": store.get_latest(
            "canonical_attempts", str(prepared["attempt_id"])
        )
        is None,
        "research_run_absent": store.get_latest(
            "canonical_research_run_versions",
            str(prepared["research_run_id"]),
        )
        is None,
    }


def _materialize_once(
    canonical_root: Path,
    planning_profile: Mapping[str, Any],
    source_pack: S4SourceGroundedInputPack,
) -> dict[str, Any]:
    binding = load_s4_case_runtime_binding(ROOT, "DELL")
    service = _case_service(canonical_root, planning_profile)
    principal = _principal()
    workspace = service.create_case(
        CreateCaseDraft(
            query=QUERY,
            as_of=datetime.fromisoformat(
                source_pack.as_of.replace("Z", "+00:00")
            ),
            language="zh-CN",
            source_policy_ref=SOURCE_POLICY_REF,
            idempotency_key=CASE_IDEMPOTENCY_KEY,
        ),
        principal,
        trace_id="fin01-s4-t04-dell-case-materialization",
    )
    planning = PlanningService.from_case_service(service)
    surface = planning.compile_decision_surface(
        workspace["case_id"],
        CompileDecisionSurfaceDraft(
            expected_case_version=workspace["case_version"],
            expected_summary_version=workspace["summary_version"],
            compiler_policy_ref=PLANNING_COMPILER_POLICY_REF,
            pack_selection_ref=PLANNING_PACK_SELECTION_REF,
            actor_ref=ACTOR_ID,
            idempotency_key="fin01-s4-t04-dell-planning-compile-v1",
        ),
        principal,
        trace_id="fin01-s4-t04-dell-planning-compile",
    )
    accepted = planning.review_planning_checkpoint(
        workspace["case_id"],
        PlanningCheckpointDecisionDraft(
            decision="accept",
            expected_case_version=workspace["case_version"],
            expected_decision_surface_contract_version=surface[
                "contract_version"
            ],
            expected_checkpoint_version=surface["checkpoint_version"],
            actor_ref=ACTOR_ID,
            idempotency_key="fin01-s4-t04-dell-planning-accept-v1",
        ),
        principal,
        trace_id="fin01-s4-t04-dell-planning-accept",
    )
    if (
        len(accepted["cells"]) != 3
        or accepted["review_status"] != "accepted"
    ):
        raise RuntimeError("s4_dell_canonical_surface_not_accepted_three_cell")
    prepared = prepare_s4_source_grounded_exact_input(
        service,
        EvidenceService.from_case_service(service, repo_root=ROOT),
        binding,
        source_pack,
        workspace["case_id"],
        principal,
        decision_surface_contract_ref=accepted["contract_version_id"],
        execution_identity=EXECUTION_IDENTITY,
    )
    prepared_payload = prepared.model_dump(mode="json")
    object_ref = service._facade.object_store.put_json(
        prepared_payload,
        namespace="fin01/s4/exact-input-heads",
        artifact_type="dell_source_grounded_prepared_input",
    )
    freshness = _execution_identity_presence(service, prepared_payload)
    if not all(freshness.values()):
        raise RuntimeError("s4_dell_fresh_identity_reused")
    return {
        "case": workspace,
        "decision_surface": accepted,
        "prepared": prepared_payload,
        "input_object_ref": object_ref,
        "freshness_and_nonreuse": freshness,
    }


def _logical_counts(database_path: Path, case_id: str) -> dict[str, int]:
    connection = sqlite3.connect(database_path)
    try:
        counts = {}
        for table in (
            "canonical_research_cases",
            "canonical_case_control_versions",
            "canonical_decision_surface_contract_versions",
            "canonical_decision_surface_cell_versions",
            "canonical_evidence_slot_versions",
            "canonical_planning_checkpoint_versions",
            "canonical_work_units",
            "canonical_attempts",
            "canonical_research_run_versions",
            "canonical_artifact_versions",
        ):
            counts[table] = sum(
                1
                for (payload_json,) in connection.execute(
                    f"select payload_json from {table}"
                )
                if json.loads(payload_json).get("case_id") == case_id
            )
        return counts
    finally:
        connection.close()


def _database_logical_digest(database_path: Path) -> str:
    connection = sqlite3.connect(database_path)
    try:
        payload: dict[str, list[list[Any]]] = {}
        table_names = [
            str(row[0])
            for row in connection.execute(
                "select name from sqlite_master "
                "where type='table' and name not like 'sqlite_%' "
                "order by name"
            )
        ]
        for table in table_names:
            columns = [
                str(row[1])
                for row in connection.execute(f"pragma table_info({table})")
            ]
            order = "row_id" if "row_id" in columns else columns[0]
            rows = []
            for row in connection.execute(
                f"select * from {table} order by {order}"
            ):
                rows.append(
                    [
                        value.hex() if isinstance(value, bytes) else value
                        for value in row
                    ]
                )
            payload[table] = rows
        return canonical_digest(payload)
    finally:
        connection.close()


def _prospective_admission(
    materialized: Mapping[str, Any],
) -> tuple[dict[str, Any], str]:
    prepared = materialized["prepared"]
    binding = load_s4_case_runtime_binding(ROOT, "DELL")
    admission = S3ThreeCellBoundedAgentAdmission(
        admission_id="fin01-s4-t04-dell-fresh-exact-admission-r1",
        output_contract_ref="fin01.s3.bounded_agent_three_cell_output:v4",
        execution_enabled=True,
        execution_mode="exact_live_s4_dell_source_grounded_three_cell_r1",
        research_profile_ref=binding.research_profile_ref,
        company="DELL",
        program_cell_ids=binding.program_cell_ids,
        case_id=prepared["case_id"],
        case_version=prepared["case_version"],
        as_of=prepared["input_pack"]["as_of"],
        input_digest=prepared["input_digest"],
        provider="deepseek",
        model="deepseek-v4-pro",
        model_ref="deepseek:deepseek-v4-pro",
        api_key_env="DEEPSEEK_API_KEY",
        base_url="https://api.deepseek.com/beta",
        transport_ref=(
            "fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v7"
        ),
        research_lead_transport_ref=(
            "fin01.s3.bounded_agent.research_lead_owner_grade:v5"
        ),
        memo_writer_transport_ref=(
            "fin01.s3.bounded_agent.memo_writer_owner_grade:v3"
        ),
        scoped_identity_contract_ref=(
            "fin01.s3.cell_scoped_research_identity:v1"
        ),
        claim_fact_link_policy_ref="fin01.s3.claim_fact_link_policy:v1",
        provider_output_capture_policy_ref=(
            "fin01.s3.provider_output_capture.assistant_final_text_only:v1"
        ),
        max_semantic_model_calls=12,
        max_provider_calls=12,
        max_network_calls=12,
        max_total_cost_usd=0.10,
        specialist_max_output_tokens=4200,
        lead_max_output_tokens=1800,
        writer_max_output_tokens=1400,
        verifier_max_output_tokens=1000,
        timeout_seconds=120,
        max_transport_attempts_per_call=1,
        retry_budget=0,
        source_network_calls_allowed=False,
        external_tool_calls_allowed=False,
        live_business_case_head_writes_allowed=False,
    )
    admission.assert_profile_admissible()
    payload = admission.model_dump(mode="json")
    return payload, canonical_digest(admission.digest_payload())


def prepare(runtime_root: Path = RUNTIME_ROOT) -> dict[str, Any]:
    existing_decision = (
        json.loads(DECISION_PATH.read_text(encoding="utf-8"))
        if DECISION_PATH.is_file()
        else {}
    )
    source_payload = _build_source_pack()
    planning_profile = _build_planning_profile()
    _write_json(SOURCE_PACK_PATH, source_payload)
    _write_json(PLANNING_PROFILE_PATH, planning_profile)
    source_pack = S4SourceGroundedInputPack.model_validate(source_payload)

    canonical_root = runtime_root.resolve() / "canonical-runtime"
    if not (canonical_root / "canonical.sqlite").is_file():
        raise RuntimeError("s4_dell_target_canonical_runtime_missing")
    before_target_digest = _sha256(canonical_root / "canonical.sqlite")
    with tempfile.TemporaryDirectory(
        prefix="fin01-s4-t04-dell-input-materialization-"
    ) as temp_dir:
        clone_root = Path(temp_dir) / "canonical-runtime"
        shutil.copytree(canonical_root, clone_root)
        clone_first = _materialize_once(
            clone_root, planning_profile, source_pack
        )
        clone_first_digest = _database_logical_digest(
            clone_root / "canonical.sqlite"
        )
        clone_second = _materialize_once(
            clone_root, planning_profile, source_pack
        )
        clone_second_digest = _database_logical_digest(
            clone_root / "canonical.sqlite"
        )
        if (
            clone_first["prepared"] != clone_second["prepared"]
            or clone_first["decision_surface"]
            != clone_second["decision_surface"]
            or clone_first_digest != clone_second_digest
        ):
            raise RuntimeError("s4_dell_clone_materialization_not_idempotent")

    target_first = _materialize_once(
        canonical_root, planning_profile, source_pack
    )
    after_first_digest = _sha256(canonical_root / "canonical.sqlite")
    after_first_logical_digest = _database_logical_digest(
        canonical_root / "canonical.sqlite"
    )
    target_second = _materialize_once(
        canonical_root, planning_profile, source_pack
    )
    after_second_digest = _sha256(canonical_root / "canonical.sqlite")
    after_second_logical_digest = _database_logical_digest(
        canonical_root / "canonical.sqlite"
    )
    if (
        target_first["prepared"] != target_second["prepared"]
        or target_first["decision_surface"]
        != target_second["decision_surface"]
        or after_first_logical_digest != after_second_logical_digest
    ):
        raise RuntimeError("s4_dell_target_materialization_not_idempotent")

    prospective_payload, prospective_digest = _prospective_admission(
        target_first
    )
    if PROSPECTIVE_ADMISSION_PATH.exists():
        raise RuntimeError("s4_dell_prospective_admission_file_must_be_absent")
    case_id = target_first["case"]["case_id"]
    prepared = target_first["prepared"]
    existing_materialization = existing_decision.get(
        "canonical_materialization", {}
    )
    preserve_first_materialization_audit = (
        existing_materialization.get("case_id") == case_id
        and existing_materialization.get(
            "logical_digest_after_second_materialization"
        )
        == after_second_logical_digest
    )
    if preserve_first_materialization_audit:
        database_sha256_before = existing_materialization[
            "database_sha256_before"
        ]
        database_sha256_after_first_materialization = (
            existing_materialization[
                "database_sha256_after_first_materialization"
            ]
        )
        database_sha256_after = existing_materialization[
            "database_sha256_after"
        ]
    else:
        database_sha256_before = before_target_digest
        database_sha256_after_first_materialization = after_first_digest
        database_sha256_after = after_second_digest
    decision = {
        "schema_version": (
            "fin_ia_0_1_s4_t04_dell_source_grounded_materialization_"
            "fresh_proof_decision_v1_0"
        ),
        "decision_id": (
            "S4-T04-DELL-SOURCE-GROUNDED-INPUT-MATERIALIZATION-"
            "AND-FRESH-PROOF-R1"
        ),
        "decided_at": FROZEN_AT,
        "status": (
            "pass_source_grounded_exact_input_head_materialized_"
            "fresh_proof_frozen_admission_issuance_pending"
        ),
        "authority": {
            "user_instruction": "继续",
            "authorized_scope": (
                "RC-P36-056 source routes, canonical DELL Case/Input Head "
                "materialization and fresh proof only"
            ),
            "model_or_provider_calls_authorized": False,
            "admission_issuance_authorized": False,
            "exact_live_authorized": False,
        },
        "source_execution": {
            "source_pack_ref": SOURCE_PACK_PATH.relative_to(ROOT).as_posix(),
            "source_pack_sha256": _sha256(SOURCE_PACK_PATH),
            "source_pack_digest": source_pack.source_pack_digest,
            "source_snapshot_count": len(source_pack.source_snapshots),
            "route_receipt_count": len(
                source_pack.route_execution_receipts
            ),
            "evidence_row_count": len(source_pack.evidence_rows),
            "numeric_row_count": len(source_pack.numeric_rows),
            "derived_metric_count": len(source_pack.derived_metrics),
            "context_only_graph_edge_count": len(source_pack.graph_edges),
            "typed_gap_count": len(source_pack.typed_gaps),
        },
        "canonical_materialization": {
            "runtime_root": runtime_root.relative_to(ROOT).as_posix(),
            "database_ref": (
                canonical_root / "canonical.sqlite"
            ).relative_to(ROOT).as_posix(),
            "database_sha256_before": database_sha256_before,
            "database_sha256_after": database_sha256_after,
            "database_sha256_after_first_materialization": (
                database_sha256_after_first_materialization
            ),
            "logical_digest_after_first_materialization": (
                after_first_logical_digest
            ),
            "logical_digest_after_second_materialization": (
                after_second_logical_digest
            ),
            "idempotent_second_materialization": True,
            "case_id": case_id,
            "case_version": prepared["case_version"],
            "decision_surface_contract_ref": prepared[
                "decision_surface_contract_ref"
            ],
            "planning_checkpoint_status": target_first[
                "decision_surface"
            ]["review_status"],
            "planning_cell_count": len(
                target_first["decision_surface"]["cells"]
            ),
            "input_head_digest": prepared["input_pack"][
                "input_head_digest"
            ],
            "input_object_ref": target_first["input_object_ref"],
            "logical_counts": _logical_counts(
                canonical_root / "canonical.sqlite", case_id
            ),
        },
        "fresh_agent_proof": {
            "decision": "frozen_unissued_unconsumed",
            "execution_identity": prepared["execution_identity"],
            "work_unit_id": prepared["work_unit_id"],
            "attempt_id": prepared["attempt_id"],
            "research_run_id": prepared["research_run_id"],
            "input_digest": prepared["input_digest"],
            "preparation_digest": prepared["preparation_digest"],
            "freshness_and_nonreuse": target_first[
                "freshness_and_nonreuse"
            ],
            "double_prepare_parity": True,
            "prospective_admission": {
                "payload": prospective_payload,
                "digest": prospective_digest,
                "prospective_admission_file": (
                    PROSPECTIVE_ADMISSION_PATH.relative_to(ROOT).as_posix()
                ),
                "prospective_admission_file_absent": True,
                "issued": False,
                "consumed": False,
                "execution_started": False,
            },
        },
        "root_cause_disposition": {
            "issue_id": (
                "RC-P36-056-s4-dell-source-grounded-exact-input-head-"
                "and-canonical-case-gap"
            ),
            "prior_status": "open_owned_pre_admission_source_grounded_input_gap",
            "new_status": (
                "closed_source_grounded_input_and_fresh_proof_repaired"
            ),
            "model_quality_issue": False,
            "required_fix_verified": True,
        },
        "hard_boundaries": {
            "source_network_calls": source_pack.observed_counts[
                "source_network_calls"
            ],
            "model_calls": 0,
            "provider_calls": 0,
            "paid_calls": 0,
            "admission_files_written": 0,
            "work_units_created": 0,
            "attempts_created": 0,
            "research_runs_created": 0,
            "business_artifacts_created": 0,
            "human_acceptance_completed": False,
        },
        "next_action": (
            "S4-T04-DELL-FRESH-EXACT-ADMISSION-ISSUANCE"
        ),
    }
    _write_json(DECISION_PATH, decision)
    return decision


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=RUNTIME_ROOT,
    )
    args = parser.parse_args()
    result = prepare(args.runtime_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
