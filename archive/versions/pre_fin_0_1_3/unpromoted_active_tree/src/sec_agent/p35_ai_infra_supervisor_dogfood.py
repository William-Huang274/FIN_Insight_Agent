from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]

FRAMEWORK_SCHEMA_VERSION = "fin_insight_p35_ai_infra_decision_surface_framework_v0_1"
GAP_AUDIT_SCHEMA_VERSION = "fin_insight_p35_ai_infra_current_system_gap_audit_v0_1"

DEFAULT_P34_LIVE_ROUTE_ATTEMPT_REPORT_PATH = (
    REPO_ROOT / "docs/project_os/p34_ai_semis_live_route_attempt_report_v0_1.json"
)
DEFAULT_P34_NO_PAID_AUDIT_PATH = (
    REPO_ROOT / "docs/project_os/p34_ai_semis_no_paid_quality_audit_v0_1.json"
)
DEFAULT_P34_ALIGNMENT_PATH = (
    REPO_ROOT / "docs/project_os/p34_ai_semis_goldcase_rag_availability_alignment_v0_1.json"
)
DEFAULT_WORKBUDDY_ROOT = Path("C:/Users/hht13/WorkBuddy")


def build_ai_infra_decision_surface_framework() -> dict[str, Any]:
    """Return the target research contract for the AI infrastructure case."""

    chain_segments = [
        {
            "segment_id": "accelerator",
            "label": "Accelerator",
            "core_entities": ["NVDA", "AMD", "hyperscaler_custom_silicon"],
            "capture_mechanism": "accelerator revenue, system ASP, software ecosystem, supply allocation, and substitution risk",
        },
        {
            "segment_id": "server_oem",
            "label": "Server OEM",
            "core_entities": ["DELL", "SMCI", "HPE"],
            "capture_mechanism": "AI server orders, shipments, backlog conversion, attach economics, cash conversion, and GPU pass-through",
        },
        {
            "segment_id": "foundry_packaging",
            "label": "Foundry / Packaging",
            "core_entities": ["TSMC", "advanced_packaging", "CoWoS"],
            "capture_mechanism": "advanced-node demand, CoWoS capacity, utilization, pricing, customer allocation, and capex recovery",
        },
        {
            "segment_id": "hbm",
            "label": "HBM Memory",
            "core_entities": ["SK_hynix", "Samsung", "Micron"],
            "capture_mechanism": "HBM bit growth, ASP, qualification, long-term agreements, capacity bottlenecks, and margin uplift",
        },
        {
            "segment_id": "semicap",
            "label": "Semicap Equipment",
            "core_entities": ["ASML", "AMAT", "LRCX", "KLAC"],
            "capture_mechanism": "WFE, EUV/DUV, deposition/etch, process control, advanced packaging, memory/HBM process intensity, and export exposure",
        },
    ]

    decision_dimensions = [
        {
            "dimension_id": "demand_proof",
            "label": "Demand proof",
            "question": "Is AI infrastructure demand observable in customer capex, deployment, orders, backlog, shipment, or revenue?",
        },
        {
            "dimension_id": "capture_mechanism",
            "label": "Capture mechanism",
            "question": "How does the demand pool become revenue for this value-chain segment?",
        },
        {
            "dimension_id": "revenue_evidence",
            "label": "Revenue evidence",
            "question": "Is supplier revenue already disclosed, or is the evidence only demand proxy / estimate?",
        },
        {
            "dimension_id": "profit_quality",
            "label": "Profit quality",
            "question": "Does the demand carry pricing power, gross margin, operating leverage, cash conversion, or only pass-through revenue?",
        },
        {
            "dimension_id": "bottleneck_monetization",
            "label": "Bottleneck monetization",
            "question": "Can supply scarcity be monetized by this segment, and who captures the bottleneck rent?",
        },
        {
            "dimension_id": "margin_dilution",
            "label": "Margin dilution",
            "question": "Is growth diluting gross margin, operating margin, or cash flow quality?",
        },
        {
            "dimension_id": "capex_digestion",
            "label": "Capex digestion",
            "question": "Could customer capex growth slow before supplier revenue expectations are digested?",
        },
        {
            "dimension_id": "export_control",
            "label": "Export control",
            "question": "What policy/geography constraint could cap TAM, shipments, customer mix, or installed-base service?",
        },
        {
            "dimension_id": "price_in",
            "label": "Price-in",
            "question": "How much of the business improvement is already reflected in valuation, positioning, and event reaction?",
        },
        {
            "dimension_id": "counter_thesis",
            "label": "Counter-thesis",
            "question": "What evidence would weaken or reverse the current segment judgment?",
        },
        {
            "dimension_id": "source_grade",
            "label": "Source grade",
            "question": "Which claims are official, parsed, secondary estimate, inference, commercial-gap, or attempt-backed gap?",
        },
        {
            "dimension_id": "numeric_sanity",
            "label": "Numeric sanity",
            "question": "Do the segment numbers tie across period, unit, numerator/denominator, and comparable peer scope?",
        },
    ]

    acceptance_gates = [
        "The final report must open with a decision surface before source-boundary prose.",
        "Every segment must have at least one explicit current judgment and one what-would-change signal.",
        "Real demand, demand proxy, lagged read-through, and market price-in must be separated.",
        "Official disclosures, parsed rows, secondary estimates, and analyst inferences must be visibly labeled.",
        "Boundary language must attach to the cell or claim it constrains; it cannot become the main report body.",
        "If current runtime rows cannot support a cell, the supervisor must run a source-hunter supplement before writing the report or mark a typed gap with attempted source path.",
    ]

    return {
        "schema_version": FRAMEWORK_SCHEMA_VERSION,
        "created_at": _utc_now(),
        "artifact_type": "ai_infra_decision_surface_framework",
        "case_question": (
            "Does AI infrastructure demand translate into high-quality revenue and profits across accelerators, "
            "server OEMs, foundry/packaging, HBM, and semicap, and where are demand proxy, margin dilution, "
            "supply bottleneck, capex digestion, export control, and price-in risks?"
        ),
        "north_star_output": {
            "front_office_surface": [
                "TL;DR judgment",
                "segment decision surface",
                "evidence quality matrix",
                "real-demand vs demand-proxy classification",
                "ranked evidence chain",
                "turning signals",
                "source-grade and numeric-sanity appendix",
            ],
            "internal_advantage": [
                "claim-level source lineage",
                "numeric sanity checks",
                "runtime-row versus source-supplement separation",
                "typed gaps that preserve attempted source paths",
                "Workbench reviewable cells and claim cards",
            ],
        },
        "chain_segments": chain_segments,
        "decision_dimensions": decision_dimensions,
        "decision_surface_cells": [
            {
                "cell_id": f"{segment['segment_id']}::{dimension['dimension_id']}",
                "segment_id": segment["segment_id"],
                "dimension_id": dimension["dimension_id"],
                "required_output_fields": [
                    "judgment",
                    "key_numbers",
                    "source_grade",
                    "official_or_estimate",
                    "lineage_or_source_url",
                    "numeric_sanity_status",
                    "cannot_infer",
                    "what_would_change",
                ],
            }
            for segment in chain_segments
            for dimension in decision_dimensions
        ],
        "acceptance_gates": acceptance_gates,
        "method_mapping": {
            "thesis_path_first_research": "used to force answer-first segment judgments",
            "product_to_financial_bridge": "used to bridge product/deployment/HBM/CoWoS evidence into revenue and profit quality",
            "three_statement_peer_panel": "used for margins, cash conversion, capex, and peer comparison",
            "secondary_market_capital_feedback": "used for price-in, ownership, valuation, and event reaction",
            "customer_supplier_readthrough": "used for hyperscaler capex to supplier capture boundaries",
            "bounded_leading_signal_promotion": "used for product/deployment/estimate rows that are strong but not official revenue facts",
        },
        "workbuddy_comparison_role": {
            "used_as": "competitor expression and minimum front-office decision-surface benchmark",
            "not_used_as": "source-of-truth ontology or claim-level authority system",
        },
    }


def build_current_system_gap_audit(
    *,
    framework: Mapping[str, Any] | None = None,
    p34_live_route_attempt_report_path: str | Path = DEFAULT_P34_LIVE_ROUTE_ATTEMPT_REPORT_PATH,
    p34_no_paid_audit_path: str | Path = DEFAULT_P34_NO_PAID_AUDIT_PATH,
    p34_alignment_path: str | Path = DEFAULT_P34_ALIGNMENT_PATH,
    workbuddy_root: str | Path = DEFAULT_WORKBUDDY_ROOT,
) -> dict[str, Any]:
    """Compare the target framework with current P34 and local WorkBuddy samples."""

    target = dict(framework or build_ai_infra_decision_surface_framework())
    live_report = _load_json_if_exists(Path(p34_live_route_attempt_report_path))
    quality_audit = _load_json_if_exists(Path(p34_no_paid_audit_path))
    alignment = _load_json_if_exists(Path(p34_alignment_path))
    accepted_rows = [row for row in live_report.get("accepted_runtime_rows") or [] if isinstance(row, Mapping)]
    typed_gaps = [row for row in live_report.get("typed_gaps") or [] if isinstance(row, Mapping)]
    workbuddy_samples = summarize_workbuddy_samples(workbuddy_root)

    current_coverage = _current_p34_coverage_summary(accepted_rows, typed_gaps, quality_audit, alignment)
    missing_cells = _missing_cells_against_framework(target)
    root_causes = [
        {
            "root_cause_id": "p35_case_scope_mismatch",
            "layer": "case_definition",
            "finding": (
                "P34 grew out of the AI/Semis gold case around accelerator, Dell, customer deployment, capex, "
                "semicap read-through, and market boundary. The user case now asks for a full five-segment industry "
                "decision surface that explicitly includes HBM, SMCI/HPE, CoWoS pricing, semicap peer split, and price-in."
            ),
            "why_it_matters": "The current runtime can pass P34 gates while still failing the user's visible question.",
            "repair_direction": "Make the decision surface the upstream contract, not a renderer afterthought.",
        },
        {
            "root_cause_id": "p35_decision_surface_not_runtime_contract",
            "layer": "research_lead_to_writer_contract",
            "finding": (
                "P34 has judgment chains and fact-table blocks, but no segment-by-dimension decision surface with required "
                "fields for every cell. The verifier therefore checks lineage and typed gaps more strongly than front-office completeness."
            ),
            "why_it_matters": "A report can be safe yet incomplete; the user experiences it as boundary-heavy.",
            "repair_direction": "Inject decision-surface cells into Research Lead, source routes, specialist outputs, MemoLogicPlan, and verifier.",
        },
        {
            "root_cause_id": "p35_source_hunter_loop_absent",
            "layer": "source_route_runtime",
            "finding": (
                "Current P34 source routes are predetermined by 20 evidence slots. WorkBuddy instead repeatedly searches and fetches "
                "until the story has enough surface area."
            ),
            "why_it_matters": "Our RAG/graph/sql assets do not automatically compensate when the specific case surface is under-specified.",
            "repair_direction": "Add a supervisor source-hunter loop that opens missing decision-surface cells, tries official first, then graded secondary sources, and writes supplement rows.",
        },
        {
            "root_cause_id": "p35_parser_depth_vs_context_rows",
            "layer": "parser_adapter",
            "finding": (
                "P34 accepted rows include useful official context, but several rows are context_summary rather than extracted value/unit/period/product table cells."
            ),
            "why_it_matters": "Writer receives enough material to say what cannot be inferred, but not enough numbers to rank segments with confidence.",
            "repair_direction": "Prioritize official IR/press/PDF table extraction for HBM, CoWoS, server OEM peers, semicap bookings/backlog, and capex/depreciation.",
        },
        {
            "root_cause_id": "p35_output_product_surface_gap",
            "layer": "deliverable_surface",
            "finding": (
                "WorkBuddy renders polished HTML/ECharts-style artifacts by default. FIN currently projects memo/workpaper text and Workbench review surfaces, "
                "but the report product is not yet optimized for decision scanning."
            ),
            "why_it_matters": "Even when our evidence is better governed, users compare the visible artifact first.",
            "repair_direction": "Treat decision tables, heatmaps, and source-grade appendices as first-class render targets.",
        },
    ]

    return {
        "schema_version": GAP_AUDIT_SCHEMA_VERSION,
        "created_at": _utc_now(),
        "artifact_type": "ai_infra_supervisor_dogfood_gap_audit",
        "status": "current_system_gap_audit_completed_no_paid_llm",
        "scope": {
            "full_chain_run": False,
            "paid_llm_run": False,
            "workbuddy_samples_read": len(workbuddy_samples),
            "p34_runtime_rows_read": len(accepted_rows),
            "p34_typed_gaps_read": len(typed_gaps),
        },
        "target_framework_ref": target.get("schema_version"),
        "current_p34_coverage": current_coverage,
        "missing_decision_surface_cells": missing_cells,
        "workbuddy_sample_summary": workbuddy_samples,
        "root_causes": root_causes,
        "required_next_repairs": [
            "Implement decision-surface schema as runtime input and verifier requirement.",
            "Add source-hunter supplement rows for missing cells before writer.",
            "Promote source supplement rows into a ledger with source grade and numeric-sanity status.",
            "Only then run a scoped writer/report generation pass.",
            "Use Workbench review to accept/reject each decision-surface cell, not only whole memo prose.",
        ],
        "not_run": [
            "paid_llm",
            "true_full_chain",
            "model_comparison",
            "case_expansion",
            "release_eval",
        ],
    }


def summarize_workbuddy_samples(workbuddy_root: str | Path = DEFAULT_WORKBUDDY_ROOT) -> list[dict[str, Any]]:
    root = Path(workbuddy_root)
    samples: list[dict[str, Any]] = []
    if not root.exists():
        return samples

    html_paths = sorted(set(root.glob("*/*.html")) | set(root.glob("*/outputs/*.html")))
    for path in html_paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        plain = _strip_html(text)
        samples.append(
            {
                "path": str(path),
                "title": _first_match(text, r"<title>(.*?)</title>"),
                "h1": _html_headings(text, "h1")[:3],
                "h2": _html_headings(text, "h2")[:12],
                "h3": _html_headings(text, "h3")[:12],
                "table_count": text.lower().count("<table"),
                "echarts_count": text.lower().count("echarts"),
                "contains_tldr": "TL;DR" in plain or "核心结论" in plain,
                "contains_risk_matrix": "风险矩阵" in plain or "Risk" in plain,
                "contains_source_boundary": "官方" in plain or "估算" in plain or "来源" in plain,
                "plain_text_chars": len(plain),
            }
        )
    return samples


def _current_p34_coverage_summary(
    accepted_rows: list[Mapping[str, Any]],
    typed_gaps: list[Mapping[str, Any]],
    quality_audit: Mapping[str, Any],
    alignment: Mapping[str, Any],
) -> dict[str, Any]:
    issuers = sorted({str(row.get("issuer") or "").upper() for row in accepted_rows if row.get("issuer")})
    chain_results = quality_audit.get("chain_results") or []
    if isinstance(quality_audit.get("metrics"), Mapping):
        metrics = dict(quality_audit["metrics"])
    else:
        metrics = {}
    availability = alignment.get("current_data_availability") or {}
    if not isinstance(availability, Mapping):
        availability = {}
    return {
        "accepted_row_count": len(accepted_rows),
        "typed_gap_count": len(typed_gaps),
        "issuer_count": len(issuers),
        "issuers": issuers,
        "quality_audit_status": quality_audit.get("status", "missing"),
        "chain_pass_count": metrics.get("chain_pass_count"),
        "chain_partial_count": metrics.get("chain_partial_count"),
        "chain_fail_count": metrics.get("chain_fail_count"),
        "full_chain_allowed": metrics.get("allow_full_chain"),
        "analyst_fact_table_row_count": availability.get("analyst_fact_table_row_count"),
        "rows_by_value_quality": availability.get("analyst_fact_rows_by_value_quality"),
        "observable_strengths": [
            "P34 has a bounded judgment-chain audit and a fact-table projection.",
            "P34 preserves two attempt-backed typed gaps rather than hiding them.",
            "P34 can distinguish product/deployment facts from revenue and margin claims.",
        ],
        "observable_limits": [
            "HBM producers are not covered as first-class segment rows.",
            "SMCI/HPE are not covered as first-class server OEM peer rows.",
            "CoWoS capacity/pricing/customer allocation are not extracted into exact rows.",
            "Semicap lacks full ASML/AMAT/LRCX/KLAC bookings/backlog/China/WFE peer panel.",
            "Price-in remains bounded fixture/context rather than live market/holder/valuation pack.",
        ],
    }


def _missing_cells_against_framework(framework: Mapping[str, Any]) -> list[dict[str, str]]:
    missing_by_segment = {
        "accelerator": [
            "price_in",
            "export_control",
            "numeric_sanity",
        ],
        "server_oem": [
            "profit_quality",
            "margin_dilution",
            "cash_conversion",
            "peer_panel",
            "price_in",
        ],
        "foundry_packaging": [
            "bottleneck_monetization",
            "profit_quality",
            "capex_recovery",
            "customer_allocation",
            "numeric_sanity",
        ],
        "hbm": [
            "demand_proof",
            "revenue_evidence",
            "profit_quality",
            "bottleneck_monetization",
            "price_in",
            "numeric_sanity",
        ],
        "semicap": [
            "revenue_evidence",
            "profit_quality",
            "capex_digestion",
            "export_control",
            "peer_panel",
            "numeric_sanity",
        ],
    }
    rows: list[dict[str, str]] = []
    for segment_id, dimensions in missing_by_segment.items():
        for dimension_id in dimensions:
            rows.append(
                {
                    "segment_id": segment_id,
                    "dimension_id": dimension_id,
                    "status": "not_sufficiently_covered_by_current_p34_runtime_rows",
                }
            )
    return rows


def _load_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _strip_html(text: str) -> str:
    stripped = re.sub(r"(?is)<script.*?</script>", " ", text)
    stripped = re.sub(r"(?is)<style.*?</style>", " ", stripped)
    stripped = re.sub(r"(?is)<[^>]+>", " ", stripped)
    return re.sub(r"\s+", " ", stripped).strip()


def _first_match(text: str, pattern: str) -> str:
    match = re.search(pattern, text, re.I | re.S)
    if not match:
        return ""
    return _clean_html_text(match.group(1))


def _html_headings(text: str, tag: str) -> list[str]:
    return [_clean_html_text(match) for match in re.findall(fr"(?is)<{tag}[^>]*>(.*?)</{tag}>", text)]


def _clean_html_text(text: str) -> str:
    cleaned = re.sub(r"(?is)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
