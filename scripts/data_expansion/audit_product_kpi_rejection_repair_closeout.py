from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]

SUMMARY_SCHEMA_VERSION = "fin_agent_product_kpi_repair_closeout_summary_v0.4"
ROW_SCHEMA_VERSION = "fin_agent_product_kpi_repair_closeout_row_v0.4"

DEFAULT_REJECTIONS = Path(
    "Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_monotonic_repair_rejections_v0_3.jsonl"
)
DEFAULT_REPAIR_FACTS = Path(
    "Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_parser_verified_targeted_repair_strict_sentence_v0_1.jsonl"
)
DEFAULT_ACCEPTED_FACTS = Path(
    "Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_parser_verified_final_public_repair_v0_1.jsonl"
)
DEFAULT_OPERATING_REJECTIONS = Path(
    "Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_operating_metric_repair_rejections_v0_1.jsonl"
)
DEFAULT_SENTENCE_REJECTIONS = Path(
    "Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_sentence_repair_rejections_v0_1.jsonl"
)
DEFAULT_OUTPUT_DIR = Path("Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1")
DEFAULT_CLOSEOUT_OUTPUT = DEFAULT_OUTPUT_DIR / "company_product_kpi_repair_rejection_closeout_v0_4.jsonl"
DEFAULT_SUMMARY_OUTPUT = DEFAULT_OUTPUT_DIR / "company_product_kpi_repair_rejection_closeout_summary_v0_4.json"
DEFAULT_REPORT_OUTPUT = Path(
    "Z:/FIN_Insight_Agent/docs/internal/vnext_20260610/product_kpi_repair_rejection_closeout_v0_4_execution.zh-CN.md"
)

REVENUE_TABLE_REPAIR_TICKERS = {"DRI", "TSN", "LSCC", "ICE"}
RESTATEMENT_OR_VERSION_TICKERS = {"GPC"}
REGION_SCHEMA_TICKERS = {"AMGN", "AOS", "CPRT", "BIIB", "BSX", "GILD", "JNJ", "ZTS"}
TRUNCATED_OR_NON_REVENUE_TABLE_TICKERS = {"AAPL", "DRI", "ED", "IP", "LSCC", "NEM", "SHW", "TSN"}
FINANCIAL_OR_NON_PRODUCT_ROW_LABEL_RE = re.compile(
    r"credit facility|letters of credit|cash and cash equivalents|operating activities|investing activities|"
    r"financing activities|foreign currency exchange|capital projects|ground lease|capital improvements|"
    r"redevelopment|start-up capital|senior notes|common stock|credit facilities|term loans|"
    r"securiti[sz]ation|securitized debt|noncontrolling interest|distributions|debt obligations|"
    r"lease obligations|cost of sales|consolidated revenues",
    re.IGNORECASE,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify v0.3 product KPI repair rejections for v0.4 closeout.")
    parser.add_argument("--rejections", type=Path, default=DEFAULT_REJECTIONS)
    parser.add_argument("--repair-facts", type=Path, default=DEFAULT_REPAIR_FACTS)
    parser.add_argument("--accepted-facts", type=Path, default=DEFAULT_ACCEPTED_FACTS)
    parser.add_argument("--operating-rejections", type=Path, default=DEFAULT_OPERATING_REJECTIONS)
    parser.add_argument("--sentence-rejections", type=Path, default=DEFAULT_SENTENCE_REJECTIONS)
    parser.add_argument("--closeout-output", type=Path, default=DEFAULT_CLOSEOUT_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = datetime.now(timezone.utc).isoformat()
    rejection_rows = list(_iter_jsonl(_resolve(args.rejections)))
    repair_by_id = {str(row.get("fact_id") or ""): row for row in _iter_jsonl(_resolve(args.repair_facts))}
    accepted_fact_ids = load_accepted_fact_ids(_resolve(args.accepted_facts))
    phase_rejections = load_phase_rejections(
        operating_path=_resolve(args.operating_rejections),
        sentence_path=_resolve(args.sentence_rejections),
    )
    closeout_rows = classify_rejections(
        rejection_rows,
        repair_by_id,
        generated_at,
        accepted_fact_ids=accepted_fact_ids,
        phase_rejections=phase_rejections,
    )
    summary = build_summary(
        closeout_rows=closeout_rows,
        generated_at=generated_at,
        paths={
            "rejections": _repo_path(_resolve(args.rejections)),
            "repair_facts": _repo_path(_resolve(args.repair_facts)),
            "accepted_facts": _repo_path(_resolve(args.accepted_facts)),
            "operating_rejections": _repo_path(_resolve(args.operating_rejections)),
            "sentence_rejections": _repo_path(_resolve(args.sentence_rejections)),
            "closeout": _repo_path(_resolve(args.closeout_output)),
            "summary": _repo_path(_resolve(args.summary_output)),
            "report": _repo_path(_resolve(args.report_output)),
        },
    )
    _write_jsonl(_resolve(args.closeout_output), closeout_rows)
    _write_json(_resolve(args.summary_output), summary)
    report_output = _resolve(args.report_output)
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(render_report(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def classify_rejections(
    rejection_rows: list[dict[str, Any]],
    repair_by_id: dict[str, dict[str, Any]],
    generated_at: str,
    accepted_fact_ids: set[str] | None = None,
    phase_rejections: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    accepted_fact_ids = accepted_fact_ids or set()
    phase_rejections = phase_rejections or {}
    out: list[dict[str, Any]] = []
    for rejection in rejection_rows:
        full = repair_by_id.get(str(rejection.get("fact_id") or ""), {})
        fact_id = str(rejection.get("fact_id") or "")
        decision = classify_with_final_phase_outcome(
            rejection=rejection,
            full=full,
            fact_id=fact_id,
            accepted_fact_ids=accepted_fact_ids,
            phase_rejections=phase_rejections,
        )
        row = {
            "schema_version": ROW_SCHEMA_VERSION,
            "closeout_id": stable_id("PRODUCTKPICLOSEOUT", rejection.get("fact_id"), decision["closeout_reason"]),
            "generated_at": generated_at,
            "ticker": rejection.get("ticker"),
            "company": rejection.get("company"),
            "fact_id": rejection.get("fact_id"),
            "source_document_id": rejection.get("source_document_id"),
            "source_id": rejection.get("source_id"),
            "v0_3_rejection_reason": rejection.get("rejection_reason"),
            "metric_family": full.get("metric_family", rejection.get("metric_family")),
            "product_or_segment": full.get("product_or_segment", rejection.get("product_or_segment")),
            "product_node_id": full.get("product_node_id", rejection.get("product_node_id")),
            "period": full.get("period", rejection.get("period")),
            "unit": full.get("unit", rejection.get("unit")),
            "unit_category": full.get("unit_category"),
            "value": full.get("value", rejection.get("value")),
            "row_label": full.get("row_label", rejection.get("row_label")),
            "column_label": full.get("column_label", rejection.get("column_label")),
            "raw_value_text": full.get("raw_value_text"),
            "action_class": decision["action_class"],
            "target_phase": decision["target_phase"],
            "closeout_reason": decision["closeout_reason"],
            "runtime_boundary": decision["runtime_boundary"],
        }
        out.append(row)
    return out


def classify_with_final_phase_outcome(
    *,
    rejection: dict[str, Any],
    full: dict[str, Any],
    fact_id: str,
    accepted_fact_ids: set[str],
    phase_rejections: dict[str, dict[str, str]],
) -> dict[str, str]:
    base_decision = classify_rejection(rejection, full)
    if base_decision["action_class"] in {"already_covered_not_gap", "correctly_rejected_cell_not_gap"}:
        return base_decision
    if fact_id in accepted_fact_ids:
        return decision(
            "final_accepted_not_gap",
            "closeout_only",
            "fact_promoted_or_accepted_in_final_public_repair_layer",
            "Use the accepted final public repair fact layer; do not duplicate this rejection row.",
        )
    phase_rejection = phase_rejections.get(fact_id)
    if not phase_rejection:
        return base_decision
    phase = phase_rejection.get("phase", "phase_repair")
    reason = phase_rejection.get("reason", "phase_rejection")
    if reason in {"operating_metric_claim_already_covered", "sentence_claim_already_covered"}:
        return decision(
            "already_covered_not_gap",
            "closeout_only",
            f"{phase}_{reason}",
            "Do not duplicate runtime facts; use existing accepted fact layer.",
        )
    return decision(
        "phase_verified_rejection_not_gap",
        "final_gap_or_review_only",
        f"{phase}_{reason}",
        "A phase-specific verifier rejected this row; keep it out of runtime facts unless the schema/parser gate changes.",
    )


def classify_rejection(rejection: dict[str, Any], full: dict[str, Any]) -> dict[str, str]:
    reason = str(rejection.get("rejection_reason") or "")
    ticker = str(rejection.get("ticker") or full.get("ticker") or "")
    metric_family = str(full.get("metric_family") or rejection.get("metric_family") or "")
    source_id = str(full.get("source_id") or rejection.get("source_id") or "")
    unit = str(full.get("unit") or rejection.get("unit") or "")
    unit_category = str(full.get("unit_category") or "")
    citation = str(full.get("citation_span") or "")

    if reason in {"claim_already_covered_by_baseline", "duplicate_promoted_semantic_fact"}:
        return decision(
            "already_covered_not_gap",
            "closeout_only",
            "baseline_or_promoted_claim_already_covers_semantic_fact",
            "Do not duplicate runtime facts; use existing accepted fact layer.",
        )
    if reason in {
        "non_sales_percentage_value_in_mixed_table",
        "no_high_confidence_sales_value_in_mixed_table",
        "non_sales_operating_income_value_in_mixed_table",
    }:
        return decision(
            "correctly_rejected_cell_not_gap",
            "closeout_only",
            "mixed_table_percentage_or_no_level_sales_value",
            "May be used only as rejected parser audit evidence, not as product KPI fact.",
        )
    if reason in {"non_positive_value", "change_or_growth_column", "change_or_growth_row"}:
        return decision(
            "not_promotable_public_disclosure_cell",
            "final_gap_or_review_only",
            "change_or_negative_cell_not_level_metric",
            "Do not state as product KPI level; keep as review-only context if needed.",
        )
    if reason == "not_currency_revenue":
        if metric_family == "product_revenue" and (unit == "percent_of_revenue" or unit_category == "percent_of_revenue"):
            return decision(
                "not_promotable_public_disclosure_cell",
                "final_gap_or_review_only",
                "percentage_or_change_cell_not_revenue_level_fact",
                "May support directional commentary only if separately verified; cannot be revenue amount.",
            )
        return decision(
            "operating_metric_candidate",
            "operating_metric_repair",
            "non_currency_metric_requires_operating_metric_schema",
            "Do not coerce into revenue; promote only through operating metric fact layer.",
        )
    if reason == "not_product_revenue":
        if ticker == "WBD" and metric_family == "subscribers_or_arpu":
            return decision(
                "operating_metric_candidate",
                "operating_metric_repair",
                "subscriber_table_unit_correction_candidate",
                "Can support company-disclosed subscribers if unit is corrected and citation verifies subscribers in millions.",
            )
        if ticker == "ED" and metric_family == "unit_sales_or_deliveries":
            return decision(
                "operating_metric_candidate",
                "operating_metric_repair",
                "gas_delivered_row_subrow_ambiguity_candidate",
                "Promote only if row/subrow parser uniquely binds Gas Delivered MDt rather than customer count.",
            )
        return decision(
            "operating_metric_candidate",
            "operating_metric_repair",
            "non_revenue_metric_requires_operating_metric_gate",
            "Do not coerce into revenue; promote only through operating metric fact layer.",
        )
    if reason == "not_structured_table_metric":
        if source_id.endswith("structured_sentence_metric_parser") and metric_family == "product_revenue" and unit == "USD":
            return decision(
                "sentence_verifier_candidate",
                "sentence_local_verifier",
                "sentence_currency_revenue_requires_local_relation_verifier",
                "Can become runtime fact only if product, value, period, and revenue relation are local and non-conflicting.",
            )
        return decision(
            "sentence_or_unstructured_review_only",
            "sentence_closeout",
            "sentence_percentage_or_unstructured_candidate_not_level_fact",
            "Keep review-only unless a stricter local verifier proves the relation.",
        )
    if reason in {"missing_strong_revenue_table_context", "forbidden_financial_statement_context"}:
        row_label = str(full.get("row_label") or rejection.get("row_label") or "")
        if ticker == "ES" and re.search(r"\bwholesale transmission revenues\b", row_label, re.IGNORECASE):
            return decision(
                "already_covered_not_gap",
                "closeout_only",
                "source_specific_revenue_claim_already_covered",
                "Use the promoted ES customer-contract revenue fact; do not duplicate the residual truncated table row.",
            )
        if ticker == "ICE" and re.search(r"\bcds clearing\b", row_label, re.IGNORECASE):
            return decision(
                "period_column_group_candidate",
                "period_alignment_repair",
                "ice_cds_clearing_column_group_ambiguous",
                "Do not promote ICE CDS clearing rows until the parser can bind the fiscal period and comparison column unambiguously.",
            )
        if ticker == "TSN":
            return decision(
                "not_promotable_public_disclosure_cell",
                "final_gap_or_review_only",
                "truncated_segment_table_context_not_locally_verifiable",
                "Do not promote TSN segment rows unless the local citation preserves the Sales | Operating Income table header.",
            )
        if ticker in TRUNCATED_OR_NON_REVENUE_TABLE_TICKERS:
            return decision(
                "not_promotable_public_disclosure_cell",
                "final_gap_or_review_only",
                "truncated_or_non_revenue_table_context_not_locally_verifiable",
                "The local citation is truncated, non-revenue, price/volume, utility-mixed, asset-table, or prior-year column context; do not promote without a stronger source-specific parser.",
            )
        if ticker in REVENUE_TABLE_REPAIR_TICKERS:
            return decision(
                "revenue_table_schema_candidate",
                "revenue_table_schema_repair",
                "source_specific_column_group_repair_candidate",
                "Can support revenue only after source-specific table layout selects sales block and rejects income/change blocks.",
            )
        if ticker in RESTATEMENT_OR_VERSION_TICKERS:
            return decision(
                "versioned_schema_required",
                "final_gap_or_schema_backlog",
                "public_disclosure_restatement_conflict_requires_versioned_schema",
                "Do not auto-select among conflicting same-period public disclosure values without source-version schema.",
            )
        if ticker in REGION_SCHEMA_TICKERS or has_region_product_label(full):
            return decision(
                "region_schema_candidate",
                "region_schema_repair",
                "product_region_revenue_requires_region_dimension",
                "May support region/product-region revenue, not total product revenue.",
            )
        return decision(
            "revenue_table_schema_candidate",
            "revenue_table_schema_repair",
            "source_specific_revenue_table_context_candidate",
            "Promote only after audited source-specific table signature removes false positives.",
        )
    if reason == "not_bound_to_structured_row_label":
        if is_financial_or_non_product_row_label(full) or (ticker == "ED" and str(full.get("row_label") or "").lower() == "total sales"):
            return decision(
                "not_promotable_public_disclosure_cell",
                "final_gap_or_review_only",
                "row_label_is_financial_or_company_total_not_product_kpi",
                "This row is a financial statement, financing, cash-flow, company total, or cost row; do not repair it into a product KPI.",
            )
        return decision(
            "taxonomy_binding_candidate",
            "taxonomy_or_binding_repair",
            "row_label_not_bound_to_product_alias",
            "Promote only if taxonomy alias and row label can be safely rebound; otherwise review-only.",
        )
    if reason == "geographic_segment_without_geographic_revenue_context":
        return decision(
            "region_schema_candidate",
            "region_schema_repair",
            "geographic_revenue_context_requires_region_gate",
            "May support geographic segment revenue only after explicit geographic revenue context is verified.",
        )
    if reason == "period_after_fiscal_year":
        return decision(
            "period_column_group_candidate",
            "period_alignment_repair",
            "period_or_source_fiscal_year_alignment_required",
            "Promote only if column group maps fiscal period unambiguously and not beyond source fiscal-year boundary.",
        )
    return decision(
        "unclassified_review_required",
        "manual_review",
        "unclassified_rejection_reason",
        "Do not promote until classified by an explicit v0.4 rule.",
    )


def has_region_product_label(row: dict[str, Any]) -> bool:
    label = " ".join(str(row.get(key) or "") for key in ("row_label", "product_or_segment"))
    return bool(re.search(r"\b(?:u\.s\.|us|row|international|north america|europe|asia)\b", label, re.IGNORECASE))


def is_financial_or_non_product_row_label(row: dict[str, Any]) -> bool:
    return FINANCIAL_OR_NON_PRODUCT_ROW_LABEL_RE.search(str(row.get("row_label") or "")) is not None


def decision(action_class: str, target_phase: str, closeout_reason: str, runtime_boundary: str) -> dict[str, str]:
    return {
        "action_class": action_class,
        "target_phase": target_phase,
        "closeout_reason": closeout_reason,
        "runtime_boundary": runtime_boundary,
    }


def build_summary(*, closeout_rows: list[dict[str, Any]], generated_at: str, paths: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "pass",
        "generated_at": generated_at,
        "closeout_row_count": len(closeout_rows),
        "ticker_count": len({row.get("ticker") for row in closeout_rows if row.get("ticker")}),
        "action_class_counts": dict(sorted(Counter(str(row.get("action_class") or "") for row in closeout_rows).items())),
        "target_phase_counts": dict(sorted(Counter(str(row.get("target_phase") or "") for row in closeout_rows).items())),
        "closeout_reason_counts": dict(sorted(Counter(str(row.get("closeout_reason") or "") for row in closeout_rows).items())),
        "top_ticker_counts": dict(Counter(str(row.get("ticker") or "") for row in closeout_rows).most_common(25)),
        "outputs": paths,
        "boundary": [
            "Closeout rows are not runtime facts.",
            "Rows marked repair candidates must still pass their phase-specific promotion gates before entering any accepted fact layer.",
            "Rows marked already covered or correctly rejected are excluded from unresolved public gaps.",
            "Rows marked commercial or schema backlog must not be replaced by weak proxy fallback.",
        ],
    }


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Product KPI Repair Rejection Closeout v0.4 执行报告",
        "",
        f"- 生成时间：`{summary['generated_at']}`",
        f"- Closeout rows：`{summary['closeout_row_count']}` / tickers `({summary['ticker_count']})`",
        "",
        "## 分类",
        "",
        f"- Action classes：`{json.dumps(summary['action_class_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- Target phases：`{json.dumps(summary['target_phase_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- Closeout reasons：`{json.dumps(summary['closeout_reason_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- Top tickers：`{json.dumps(summary['top_ticker_counts'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Boundary",
        "",
    ]
    lines.extend(f"- {item}" for item in summary["boundary"])
    return "\n".join(lines) + "\n"


def load_accepted_fact_ids(path: Path) -> set[str]:
    accepted: set[str] = set()
    for row in _iter_jsonl(path):
        for key in ("fact_id", "source_repair_fact_id"):
            value = str(row.get(key) or "").strip()
            if value:
                accepted.add(value)
    return accepted


def load_phase_rejections(*, operating_path: Path, sentence_path: Path) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in _iter_jsonl(operating_path):
        fact_id = str(row.get("fact_id") or "").strip()
        if fact_id:
            out[fact_id] = {
                "phase": "operating_metric_repair",
                "reason": str(row.get("rejection_reason") or "operating_metric_repair_rejected"),
            }
    for row in _iter_jsonl(sentence_path):
        fact_id = str(row.get("fact_id") or "").strip()
        if fact_id:
            out[fact_id] = {
                "phase": "sentence_local_verifier",
                "reason": str(row.get("rejection_reason") or "sentence_local_verifier_rejected"),
            }
    return out


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
