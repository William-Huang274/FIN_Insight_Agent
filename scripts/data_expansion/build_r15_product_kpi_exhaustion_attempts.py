from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]

SCHEMA_VERSION = "finsight_r15_product_kpi_exhaustion_attempt_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_r15_product_kpi_exhaustion_attempt_summary_v0_1"

DEFAULT_R15_LEDGER = REPO_ROOT / "data" / "manifests" / "r15_public_source_gap_exhaustion_ledger_v0_1.jsonl"
DEFAULT_PRODUCT_KPI_DIAGNOSTIC = REPO_ROOT / "data" / "manifests" / "product_kpi_deep_gap_diagnostic_v0_1.jsonl"
DEFAULT_VERIFIER_TICKER_SUMMARY = (
    REPO_ROOT / "data" / "manifests" / "product_kpi_source_specific_verifier_ticker_summary_v0_1.jsonl"
)
DEFAULT_NON_US_REJECTIONS = (
    REPO_ROOT / "data" / "manifests" / "non_us_product_kpi_local_disclosure_runtime_rejections_v0_1.jsonl"
)
DEFAULT_OUTPUT = REPO_ROOT / "data" / "manifests" / "r15_product_kpi_exhaustion_attempts_v0_1.jsonl"
DEFAULT_SUMMARY = REPO_ROOT / "data" / "manifests" / "r15_product_kpi_exhaustion_attempts_summary_v0_1.json"
DEFAULT_REPORT = (
    REPO_ROOT / "docs" / "internal" / "vnext_20260610" / "vertical_lanes" / "r15_product_kpi_exhaustion_attempts.zh-CN.md"
)

R15_2_CLUSTERS = {
    "product_kpi_non_us_ir_local_exchange_parser",
    "product_kpi_column_group_schema_verifier",
    "product_kpi_period_version_schema_verifier",
    "product_kpi_sentence_relation_verifier",
    "product_kpi_ir_deck_annual_report_locator",
}

FINAL_DIAGNOSTIC_CLASSES = {
    "product_surface_or_taxonomy_available_no_company_kpi_candidate",
    "non_us_local_or_ir_parser_required",
    "verifier_period_or_version_conflict",
    "verifier_business_segment_column_group_required",
    "verifier_sentence_relation_insufficient",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build R15 attempt-backed Product-KPI exhaustion rows.")
    parser.add_argument("--r15-ledger", type=Path, default=DEFAULT_R15_LEDGER)
    parser.add_argument("--product-kpi-diagnostic", type=Path, default=DEFAULT_PRODUCT_KPI_DIAGNOSTIC)
    parser.add_argument("--verifier-ticker-summary", type=Path, default=DEFAULT_VERIFIER_TICKER_SUMMARY)
    parser.add_argument("--non-us-rejections", type=Path, default=DEFAULT_NON_US_REJECTIONS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    rows = build_rows(
        r15_rows=_load_jsonl(args.r15_ledger),
        diagnostic_rows=_load_jsonl(args.product_kpi_diagnostic),
        verifier_rows=_load_jsonl(args.verifier_ticker_summary),
        non_us_rejection_rows=_load_jsonl(args.non_us_rejections),
        generated_at=generated_at,
    )
    summary = build_summary(rows, generated_at=generated_at, output=args.output, report=args.report)
    _write_jsonl(args.output, rows)
    _write_json(args.summary, summary)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(summary), encoding="utf-8", newline="\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and summary["pending_without_boundary_count"]:
        return 1
    return 0


def build_rows(
    *,
    r15_rows: Iterable[Mapping[str, Any]],
    diagnostic_rows: Iterable[Mapping[str, Any]],
    verifier_rows: Iterable[Mapping[str, Any]],
    non_us_rejection_rows: Iterable[Mapping[str, Any]],
    generated_at: str,
) -> list[dict[str, Any]]:
    diagnostic_by_ticker = {_ticker(row): dict(row) for row in diagnostic_rows if _ticker(row)}
    verifier_by_ticker = {_ticker(row): dict(row) for row in verifier_rows if _ticker(row)}
    non_us_rejections_by_ticker: dict[str, list[dict[str, Any]]] = {}
    for row in non_us_rejection_rows:
        ticker = _ticker(row)
        if ticker:
            non_us_rejections_by_ticker.setdefault(ticker, []).append(dict(row))

    out: list[dict[str, Any]] = []
    for row in r15_rows:
        if row.get("r15_stage") != "r15_2":
            continue
        cluster_id = str(row.get("cluster_id") or "")
        if cluster_id not in R15_2_CLUSTERS:
            continue
        ticker = _ticker(row)
        diagnostic = diagnostic_by_ticker.get(ticker, {})
        verifier = verifier_by_ticker.get(ticker, {})
        non_us_rejections = non_us_rejections_by_ticker.get(ticker, [])
        decision = _decision(row=row, diagnostic=diagnostic, verifier=verifier, non_us_rejections=non_us_rejections)
        out.append(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": generated_at,
                "ticker": ticker,
                "company_name": row.get("company_name") or diagnostic.get("company_name") or "",
                "primary_lane_id": row.get("primary_lane_id") or diagnostic.get("primary_lane_id") or "",
                "requirement_id": "product_kpi_exact_slot",
                "cluster_id": cluster_id,
                "provider": decision["provider"],
                "source_id": "company_reported_product_operating_metrics",
                "status": decision["status"],
                "r15_terminal_state": decision["terminal_state"],
                "r15_terminal_reason": decision["terminal_reason"],
                "diagnostic_class": diagnostic.get("diagnostic_class") or "",
                "diagnostic_reason": diagnostic.get("diagnostic_reason") or "",
                "strict_candidate_count": diagnostic.get("strict_candidate_count") or 0,
                "runtime_row_count": diagnostic.get("runtime_row_count") or 0,
                "verifier_class_counts": verifier.get("verifier_class_counts") or diagnostic.get("source_specific_verifier_class_counts") or {},
                "verifier_decision_counts": verifier.get("verifier_decision_counts") or diagnostic.get("source_specific_verifier_decision_counts") or {},
                "top_verifier_reasons": verifier.get("top_verifier_reasons") or diagnostic.get("source_specific_verifier_top_reasons") or {},
                "non_us_rejection_reason_counts": _counter_dict(row.get("rejection_reason") for row in non_us_rejections),
                "sample_non_us_rejections": [
                    {
                        "rejection_reason": item.get("rejection_reason") or "",
                        "report_type": item.get("report_type") or "",
                        "fiscal_year": item.get("fiscal_year"),
                        "source_url": item.get("source_url") or "",
                    }
                    for item in non_us_rejections[:5]
                ],
                "claim_boundary": (
                    "This is an audit/closeout attempt for Product-KPI exact slots, not evidence. "
                    "Only parser-backed value/unit/period/product/citation rows may enter ClaimCards. "
                    "Business segment, geography, percentage/change, detached sentence, or period-conflicting rows stay out."
                ),
                "next_action": decision["next_action"],
            }
        )
    return out


def _decision(
    *,
    row: Mapping[str, Any],
    diagnostic: Mapping[str, Any],
    verifier: Mapping[str, Any],
    non_us_rejections: list[Mapping[str, Any]],
) -> dict[str, str]:
    cluster_id = str(row.get("cluster_id") or "")
    diagnostic_class = str(diagnostic.get("diagnostic_class") or "")
    if diagnostic_class not in FINAL_DIAGNOSTIC_CLASSES:
        return {
            "provider": "product_kpi_diagnostic",
            "status": "diagnostic_class_not_terminal_for_r15_2",
            "terminal_state": "",
            "terminal_reason": "R15-2 row lacks a terminal diagnostic class; rerun diagnostic before closeout.",
            "next_action": "Rerun Product-KPI diagnostic and verifier; do not close this row.",
        }

    if cluster_id == "product_kpi_ir_deck_annual_report_locator":
        return {
            "provider": "sec_ir_annual_report_locator",
            "status": "no_company_disclosed_product_kpi_candidate_after_public_disclosure_scan",
            "terminal_state": "final_public_boundary",
            "terminal_reason": (
                "Official product/taxonomy surface exists, but SEC/IR/local-disclosure scans found no company-disclosed "
                "Product-KPI candidate with value, unit, period, product, and citation. Do not substitute product pages, "
                "generic segment text, or market/proxy evidence."
            ),
            "next_action": (
                "Expose Product-KPI exact gap or use commercial tracker if the research question requires product-level "
                "shipments, ASP, backlog, share, or sell-through."
            ),
        }
    if cluster_id == "product_kpi_non_us_ir_local_exchange_parser":
        reason_counts = _counter_dict(item.get("rejection_reason") for item in non_us_rejections)
        return {
            "provider": "non_us_local_exchange_ir_parser",
            "status": "local_exchange_or_ir_reports_parsed_no_promotable_product_kpi",
            "terminal_state": "final_public_boundary",
            "terminal_reason": (
                "Non-US local exchange/company IR reports were fetched or read from cache and parsed. Rejections were "
                f"{json.dumps(reason_counts, ensure_ascii=False, sort_keys=True)}; no exact value/unit/period/product "
                "row survived the Product-KPI gate."
            ),
            "next_action": (
                "Use accepted business/segment metrics for fundamental mix only; keep product-family KPI exact as gap "
                "unless a later local table parser finds a cited product metric row."
            ),
        }
    if cluster_id == "product_kpi_column_group_schema_verifier":
        return {
            "provider": "product_kpi_source_specific_verifier",
            "status": "mixed_segment_table_column_group_not_promotable_to_product_kpi_exact",
            "terminal_state": "final_public_boundary",
            "terminal_reason": (
                "Source-specific verifier found mixed financial columns or segment-table rows, but no safe product/"
                "category/product-line revenue-level row. Business segment rows may support business mix, not Product-KPI exact."
            ),
            "next_action": (
                "Route validated segment metrics to fundamental/business mix slots; add issuer-specific table parsers only "
                "when they can isolate product/category revenue columns."
            ),
        }
    if cluster_id == "product_kpi_period_version_schema_verifier":
        return {
            "provider": "product_kpi_source_specific_verifier",
            "status": "period_or_version_conflict_not_promotable",
            "terminal_state": "final_public_boundary",
            "terminal_reason": (
                "Candidate rows contain current/prior-year, restatement, or period-after-fiscal-year conflicts. The verifier "
                "cannot bind one value to one product and one reporting period without ambiguity."
            ),
            "next_action": (
                "Keep conflicting candidates out of ClaimCards; promote only after a versioned period/column schema resolves "
                "the cited table."
            ),
        }
    if cluster_id == "product_kpi_sentence_relation_verifier":
        return {
            "provider": "product_kpi_sentence_relation_verifier",
            "status": "local_product_value_relation_not_verified",
            "terminal_state": "final_public_boundary",
            "terminal_reason": (
                "Candidate mentions lack table coordinates or local sentence-neighborhood binding between product, metric, "
                "value, unit, and period. Detached numeric mentions are not Product-KPI exact evidence."
            ),
            "next_action": (
                "Use the row only as debug context; add local citation/table-neighborhood verifier before any promotion."
            ),
        }
    return {
        "provider": "product_kpi_diagnostic",
        "status": "unclassified_r15_2_cluster",
        "terminal_state": "",
        "terminal_reason": "Unclassified R15-2 Product-KPI cluster.",
        "next_action": "Classify the Product-KPI cluster before closeout.",
    }


def build_summary(rows: list[Mapping[str, Any]], *, generated_at: str, output: Path, report: Path) -> dict[str, Any]:
    terminal_rows = [row for row in rows if row.get("r15_terminal_state") in {"final_public_boundary", "not_applicable"}]
    pending_without_boundary = [row for row in rows if not row.get("r15_terminal_state")]
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "row_count": len(rows),
        "terminal_boundary_row_count": len(terminal_rows),
        "pending_without_boundary_count": len(pending_without_boundary),
        "by_cluster": _counter_dict(row.get("cluster_id") for row in rows),
        "by_status": _counter_dict(row.get("status") for row in rows),
        "by_diagnostic_class": _counter_dict(row.get("diagnostic_class") for row in rows),
        "outputs": {"rows": str(output), "report": str(report)},
        "status": "pass" if rows and not pending_without_boundary else "gap",
    }


def render_report(summary: Mapping[str, Any]) -> str:
    lines = [
        "# R15 Product-KPI Exhaustion Attempts",
        "",
        f"- generated_at: `{summary.get('generated_at')}`",
        f"- status: `{summary.get('status')}`",
        f"- row_count: `{summary.get('row_count')}`",
        f"- terminal_boundary_row_count: `{summary.get('terminal_boundary_row_count')}`",
        f"- pending_without_boundary_count: `{summary.get('pending_without_boundary_count')}`",
        "",
        "## By Cluster",
        "",
        "| cluster | count |",
        "| --- | ---: |",
    ]
    for key, value in sorted((summary.get("by_cluster") or {}).items()):
        lines.append(f"| `{key}` | {value} |")
    lines.extend(["", "## By Status", "", "| status | count |", "| --- | ---: |"])
    for key, value in sorted((summary.get("by_status") or {}).items()):
        lines.append(f"| `{key}` | {value} |")
    lines.extend(["", "## By Diagnostic Class", "", "| diagnostic_class | count |", "| --- | ---: |"])
    for key, value in sorted((summary.get("by_diagnostic_class") or {}).items()):
        lines.append(f"| `{key}` | {value} |")
    lines.append("")
    return "\n".join(lines)


def _counter_dict(values: Iterable[Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        key = str(value or "")
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


def _ticker(row: Mapping[str, Any]) -> str:
    return str(row.get("ticker") or "").upper().strip()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            value = json.loads(text)
            if isinstance(value, Mapping):
                rows.append(dict(value))
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
