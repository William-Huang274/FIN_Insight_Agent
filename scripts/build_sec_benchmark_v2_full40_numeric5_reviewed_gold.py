from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


REVIEWED_CONTEXT_DIR = REPO_ROOT / "eval" / "sec_cases" / "reviewed_gold_context"
REVIEWED_FACTS_DIR = REPO_ROOT / "eval" / "sec_cases" / "reviewed_gold_facts"
QUALITY_DIR = REPO_ROOT / "reports" / "quality"
METRICS_PATH = REPO_ROOT / "data" / "processed_private" / "structured_objects" / "sec_tech_10k_metrics.jsonl"
EVIDENCE_PATH = REPO_ROOT / "data" / "processed_private" / "evidence_objects" / "sec_tech_10k_evidence.jsonl"

AMZN_MIX_CASE = "AMZN_ADS_SUBSCRIPTION_AWS_MIX_2023_2025_001"
SNOW_CONSUMPTION_CASE = "SNOW_CONSUMPTION_RPO_CUSTOMER_RISK_2023_2025_001"
ADBE_TABLE_CASE = "ADBE_REVENUE_DEFERRED_REVENUE_TABLE_2023_2025_001"
AMZN_CASH_CASE = "AMZN_OPERATING_CASH_FLOW_CAPEX_TABLE_2023_2025_001"
MSFT_CASH_CASE = "MSFT_OPERATING_CASH_FLOW_CAPEX_TABLE_2023_2025_001"

NUMERIC5_CASE_IDS = [
    AMZN_MIX_CASE,
    SNOW_CONSUMPTION_CASE,
    ADBE_TABLE_CASE,
    AMZN_CASH_CASE,
    MSFT_CASH_CASE,
]

AMZN_AWS_SOURCE_CASE = "AMZN_AWS_NUMERIC_2023_2025_001"
SNOW_SOURCE_CASE = "SNOW_NRR_RPO_GROWTH_2023_2025_001"
CAPEX_SOURCE_CASE = "CAPEX_FCF_TABLE_2023_2025_DIAG_001"

AMZN_ADVERTISING_OBJECT_IDS = {
    2023: "AMZN_2025_10K_ITEM8_BLOCK_0011_PART_01_OF_02_METRIC_TABLE_63D63989",
    2024: "AMZN_2025_10K_ITEM8_BLOCK_0011_PART_01_OF_02_METRIC_TABLE_FB40CE57",
    2025: "AMZN_2025_10K_ITEM8_BLOCK_0011_PART_01_OF_02_METRIC_TABLE_3FCC152A",
}

ADBE_TOTAL_REVENUE_OBJECT_IDS = {
    2023: "ADBE_2025_10K_ITEM8_BLOCK_0001_PART_01_OF_03_METRIC_TABLE_BE216C74",
    2024: "ADBE_2025_10K_ITEM8_BLOCK_0001_PART_01_OF_03_METRIC_TABLE_5FBA900A",
    2025: "ADBE_2025_10K_ITEM8_BLOCK_0001_PART_01_OF_03_METRIC_TABLE_CCCEBEE2",
}

ADBE_DEFERRED_REVENUE_OBJECT_IDS = {
    2023: "ADBE_2025_10K_ITEM8_BLOCK_0001_PART_02_OF_03_METRIC_TABLE_2DC3D696",
    2024: "ADBE_2025_10K_ITEM8_BLOCK_0001_PART_02_OF_03_METRIC_TABLE_58D12411",
    2025: "ADBE_2025_10K_ITEM8_BLOCK_0001_PART_02_OF_03_METRIC_TABLE_F5B2DB06",
}


def main() -> None:
    REVIEWED_CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    REVIEWED_FACTS_DIR.mkdir(parents=True, exist_ok=True)
    QUALITY_DIR.mkdir(parents=True, exist_ok=True)

    metrics_by_id = {str(row.get("object_id") or ""): row for row in _read_jsonl(METRICS_PATH)}
    evidence_by_id = {str(row.get("evidence_id") or ""): row for row in _read_jsonl(EVIDENCE_PATH)}

    case_summaries = [
        _write_amzn_mix(metrics_by_id, evidence_by_id),
        _write_snow_consumption(),
        _write_adbe_table(metrics_by_id, evidence_by_id),
        _write_cash_case(AMZN_CASH_CASE, "AMZN"),
        _write_cash_case(MSFT_CASH_CASE, "MSFT"),
    ]
    _write_approval(case_summaries)
    build_report_path = QUALITY_DIR / "sec_benchmark_v2_full40_numeric5_reviewed_gold_build_report.json"
    build_report = {
        "schema_version": "sec_v2_full40_numeric5_reviewed_gold_build_report_v0.1",
        "reviewed_case_ids": NUMERIC5_CASE_IDS,
        "cases": case_summaries,
        "approval_path": str(QUALITY_DIR / "sec_benchmark_v2_full40_numeric5_reviewed_gold_partial_approval.json"),
        "source_policy": "SEC_ONLY",
    }
    build_report_path.write_text(json.dumps(build_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "reviewed_case_count": len(NUMERIC5_CASE_IDS),
                "total_fact_count": sum(int(item["fact_count"]) for item in case_summaries),
                "total_context_row_count": sum(int(item["context_row_count"]) for item in case_summaries),
                "build_report_path": str(build_report_path),
                "approval_path": str(QUALITY_DIR / "sec_benchmark_v2_full40_numeric5_reviewed_gold_partial_approval.json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _write_amzn_mix(metrics_by_id: dict[str, dict[str, Any]], evidence_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    aws_facts = [
        _copy_fact(fact, AMZN_MIX_CASE, "AWS cloud revenue reused from reviewed AMZN AWS case.")
        for fact in _read_reviewed_facts(AMZN_AWS_SOURCE_CASE)
        if fact.get("metric_family") == "cloud_revenue"
    ]
    ad_facts = [
        _fact_from_metric_record(
            AMZN_MIX_CASE,
            metrics_by_id[object_id],
            metric_family="advertising_revenue",
            metric_role="total_value",
            review_note="Reviewed Amazon advertising-services revenue cell from fiscal 2025 comparative net-sales table.",
        )
        for object_id in AMZN_ADVERTISING_OBJECT_IDS.values()
    ]
    facts = _renumber_facts(AMZN_MIX_CASE, [*aws_facts, *ad_facts])
    context_rows = [
        *_copy_context_rows(AMZN_AWS_SOURCE_CASE, AMZN_MIX_CASE, ticker_filter={"AMZN"}, metric_families={"cloud_revenue"}),
        *[_context_from_metric_fact(AMZN_MIX_CASE, fact, evidence_by_id) for fact in ad_facts],
        _review_note_context(
            AMZN_MIX_CASE,
            "AMZN",
            2025,
            "review_note",
            "Advertising services revenue is a net-sales product/service grouping, while AWS revenue is a reportable segment metric. The case must not infer advertising profitability or AWS profitability from advertising revenue.",
        ),
    ]
    return _write_case(AMZN_MIX_CASE, facts, context_rows, "reviewed AMZN AWS cloud revenue plus Amazon advertising-services revenue")


def _write_snow_consumption() -> dict[str, Any]:
    facts = [
        _copy_fact(fact, SNOW_CONSUMPTION_CASE, "Reused reviewed Snowflake product revenue/RPO fact for consumption-risk full40 seed.")
        for fact in _read_reviewed_facts(SNOW_SOURCE_CASE)
        if fact.get("metric_family") in {"product_revenue", "rpo"}
    ]
    context_rows = [
        *_copy_context_rows(SNOW_SOURCE_CASE, SNOW_CONSUMPTION_CASE, ticker_filter={"SNOW"}, metric_families={"product_revenue", "rpo"}),
        *_copy_context_rows("SNOW_RISK_2023_2025_001", SNOW_CONSUMPTION_CASE, ticker_filter={"SNOW"}),
    ]
    return _write_case(SNOW_CONSUMPTION_CASE, _renumber_facts(SNOW_CONSUMPTION_CASE, facts), context_rows, "reviewed Snowflake product revenue/RPO facts plus consumption-risk context")


def _write_adbe_table(metrics_by_id: dict[str, dict[str, Any]], evidence_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    facts = []
    for object_id in ADBE_TOTAL_REVENUE_OBJECT_IDS.values():
        facts.append(
            _fact_from_metric_record(
                ADBE_TABLE_CASE,
                metrics_by_id[object_id],
                metric_family="total_revenue",
                metric_role="total_value",
                review_note="Reviewed Adobe total revenue cell from fiscal 2025 comparative income statement.",
            )
        )
    for object_id in ADBE_DEFERRED_REVENUE_OBJECT_IDS.values():
        facts.append(
            _fact_from_metric_record(
                ADBE_TABLE_CASE,
                metrics_by_id[object_id],
                metric_family="deferred_revenue",
                metric_role="total_value",
                review_note="Reviewed Adobe deferred revenue current-liability cell from fiscal 2025 comparative balance sheet.",
            )
        )
    context_rows = [
        *[_context_from_metric_fact(ADBE_TABLE_CASE, fact, evidence_by_id) for fact in facts],
        _review_note_context(
            ADBE_TABLE_CASE,
            "ADBE",
            2025,
            "review_note",
            "Total revenue is recognized revenue from the income statement. Deferred revenue is a balance-sheet liability and visibility metric, not recognized revenue.",
        ),
    ]
    return _write_case(ADBE_TABLE_CASE, _renumber_facts(ADBE_TABLE_CASE, facts), context_rows, "reviewed Adobe total revenue and deferred revenue table cells")


def _write_cash_case(case_id: str, ticker: str) -> dict[str, Any]:
    facts = [
        _copy_fact(fact, case_id, f"Reused reviewed {ticker} cash-flow/PPE-purchase fact from CAPEX_FCF table case.")
        for fact in _read_reviewed_facts(CAPEX_SOURCE_CASE)
        if fact.get("ticker") == ticker and fact.get("metric_family") in {"cash_flow", "ppe_purchases"}
    ]
    context_rows = _copy_context_rows(CAPEX_SOURCE_CASE, case_id, ticker_filter={ticker}, metric_families={"cash_flow", "ppe_purchases"})
    context_rows.append(
        _review_note_context(
            case_id,
            ticker,
            2025,
            "review_note",
            "Operating cash flow and property/equipment purchases are reviewed input metrics. Any free-cash-flow discussion must be labeled as proxy arithmetic, not a separate SEC standardized metric.",
        )
    )
    return _write_case(case_id, _renumber_facts(case_id, facts), context_rows, f"reviewed {ticker} cash-flow and PPE-purchase cells")


def _fact_from_metric_record(
    case_id: str,
    record: dict[str, Any],
    *,
    metric_family: str,
    metric_role: str,
    review_note: str,
) -> dict[str, Any]:
    period = int(record["period"])
    value = float(record["value"])
    unit = str(record.get("unit") or "")
    raw_value = str(record.get("raw_value") or "")
    return {
        "fact_id": "",
        "review_status": "reviewed_keep",
        "selection_method": "manual_review_structured_object",
        "metric_id": f"{record['ticker']}_{period}_{metric_family}_{metric_role}",
        "ticker": record["ticker"],
        "fiscal_year": period,
        "period": str(period),
        "metric_name": record.get("metric_name"),
        "metric_family": metric_family,
        "metric_role": metric_role,
        "raw_value": raw_value,
        "value": value,
        "unit": unit,
        "display_value_en": _display_value_en(value, unit),
        "object_id": record["object_id"],
        "source_evidence_id": record["source_evidence_id"],
        "section": record.get("section"),
        "row_label": record.get("row_label"),
        "column_label": record.get("column_label"),
        "allowed_claim_roles": [f"{metric_family}_{metric_role}"],
        "disallowed_claim_roles": _disallowed_roles(metric_family),
        "review_note": review_note,
    }


def _copy_fact(fact: dict[str, Any], target_case_id: str, review_note: str) -> dict[str, Any]:
    copied = dict(fact)
    copied["fact_id"] = ""
    copied["review_note"] = review_note
    copied["selection_method"] = "manual_review_reused_reviewed_fact"
    copied["source_case_id"] = fact.get("case_id")
    return copied


def _copy_context_rows(
    source_case_id: str,
    target_case_id: str,
    *,
    ticker_filter: set[str],
    metric_families: set[str] | None = None,
) -> list[dict[str, Any]]:
    path = REVIEWED_CONTEXT_DIR / f"{source_case_id}.jsonl"
    if not path.exists():
        return []
    rows = []
    for row in _read_jsonl(path):
        ticker = str(row.get("ticker") or "").upper()
        family = str(row.get("metric_family") or "")
        if ticker_filter and ticker not in ticker_filter:
            continue
        if metric_families and family and family not in metric_families:
            continue
        copied = dict(row)
        copied["case_id"] = target_case_id
        copied["source_case_id"] = source_case_id
        copied["review_note"] = f"Reused reviewed context from {source_case_id}: {row.get('review_note') or ''}".strip()
        rows.append(copied)
    return rows


def _context_from_metric_fact(case_id: str, fact: dict[str, Any], evidence_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    evidence = evidence_by_id.get(str(fact.get("source_evidence_id") or ""), {})
    return {
        "schema_version": "sec_gold_context_reviewed_v0.1",
        "case_id": case_id,
        "review_status": "reviewed_keep",
        "gold_role": "core_structured_fact",
        "source_kind": "reviewed_table_cell",
        "object_id": fact.get("object_id"),
        "source_evidence_id": fact.get("source_evidence_id"),
        "ticker": fact.get("ticker"),
        "fiscal_year": fact.get("fiscal_year"),
        "source_type": evidence.get("source_type") or "10-K",
        "section": fact.get("section"),
        "source_url": evidence.get("source_url"),
        "local_path": evidence.get("local_path"),
        "metric_name": fact.get("metric_name"),
        "metric_family": fact.get("metric_family"),
        "metric_role": fact.get("metric_role"),
        "raw_value": fact.get("raw_value"),
        "value": fact.get("value"),
        "unit": fact.get("unit"),
        "period": fact.get("period"),
        "row_label": fact.get("row_label"),
        "column_label": fact.get("column_label"),
        "text": (
            f"{fact['ticker']} fiscal {fact['period']} {fact['metric_name']} "
            f"({fact.get('row_label')}): {fact['raw_value']} {fact['unit']}; metric_id={fact['metric_id']}."
        ),
        "review_note": fact.get("review_note"),
    }


def _review_note_context(case_id: str, ticker: str, fiscal_year: int, section: str, text: str) -> dict[str, Any]:
    return {
        "schema_version": "sec_gold_context_reviewed_v0.1",
        "case_id": case_id,
        "review_status": "reviewed_keep",
        "gold_role": "caveat",
        "source_kind": "reviewed_source_policy_note",
        "source_evidence_id": f"REVIEW_NOTE_{case_id}",
        "ticker": ticker,
        "fiscal_year": fiscal_year,
        "source_type": "review_note",
        "section": section,
        "text": text,
        "review_note": "Manual review caveat for full40 numeric seed promotion.",
    }


def _write_case(case_id: str, facts: list[dict[str, Any]], context_rows: list[dict[str, Any]], source_basis: str) -> dict[str, Any]:
    _assert_case_contract(case_id, facts)
    _write_jsonl(REVIEWED_CONTEXT_DIR / f"{case_id}.jsonl", context_rows)
    payload = {
        "schema_version": "sec_gold_facts_reviewed_v0.1",
        "case_id": case_id,
        "benchmark_version": "sec_benchmark_v2_full40",
        "review_status": "reviewed_approved_single_case",
        "review_scope": {
            "source_policy": "SEC_ONLY",
            "allowed_filing_types": ["10-K"],
            "source_basis": source_basis,
            "companies": sorted({str(fact.get("ticker") or "") for fact in facts}),
            "years": sorted({int(fact.get("fiscal_year")) for fact in facts}),
            "metric_families": sorted({str(fact.get("metric_family") or "") for fact in facts}),
        },
        "facts": facts,
    }
    (REVIEWED_FACTS_DIR / f"{case_id}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "case_id": case_id,
        "fact_count": len(facts),
        "context_row_count": len(context_rows),
        "facts_path": str(REVIEWED_FACTS_DIR / f"{case_id}.json"),
        "context_path": str(REVIEWED_CONTEXT_DIR / f"{case_id}.jsonl"),
        "metric_families": sorted({str(fact.get("metric_family") or "") for fact in facts}),
    }


def _assert_case_contract(case_id: str, facts: list[dict[str, Any]]) -> None:
    expected = {
        AMZN_MIX_CASE: {("AMZN", year, family) for year in [2023, 2024, 2025] for family in ["cloud_revenue", "advertising_revenue"]},
        SNOW_CONSUMPTION_CASE: {("SNOW", year, family) for year in [2023, 2024, 2025] for family in ["product_revenue", "rpo"]},
        ADBE_TABLE_CASE: {("ADBE", year, family) for year in [2023, 2024, 2025] for family in ["total_revenue", "deferred_revenue"]},
        AMZN_CASH_CASE: {("AMZN", year, family) for year in [2023, 2024, 2025] for family in ["cash_flow", "ppe_purchases"]},
        MSFT_CASH_CASE: {("MSFT", year, family) for year in [2023, 2024, 2025] for family in ["cash_flow", "ppe_purchases"]},
    }[case_id]
    actual = {
        (str(fact.get("ticker") or ""), int(fact.get("fiscal_year")), str(fact.get("metric_family") or ""))
        for fact in facts
    }
    if actual != expected:
        raise SystemExit(f"{case_id} fact coverage mismatch: missing={sorted(expected - actual)} extra={sorted(actual - expected)}")


def _renumber_facts(case_id: str, facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(facts, key=lambda fact: (str(fact.get("ticker") or ""), int(fact.get("fiscal_year") or 0), str(fact.get("metric_family") or "")))
    for index, fact in enumerate(ordered, start=1):
        fact["fact_id"] = f"{case_id}_FACT_REVIEWED_{index:04d}"
    return ordered


def _write_approval(case_summaries: list[dict[str, Any]]) -> None:
    path = QUALITY_DIR / "sec_benchmark_v2_full40_numeric5_reviewed_gold_partial_approval.json"
    payload = {
        "schema_version": "sec_gold_manual_review_v0.2",
        "review_scope": {
            "gold_context_dir": "eval/sec_cases/reviewed_gold_context",
            "gold_facts_dir": "eval/sec_cases/reviewed_gold_facts",
            "case_count": len(NUMERIC5_CASE_IDS),
            "reviewed_case_ids": NUMERIC5_CASE_IDS,
        },
        "review_decision": {
            "overall_status": "partial_approved_for_mainline_scored_benchmark",
            "allowed_next_step": "case_filtered_full40_numeric5_gold_gate",
            "blocked_next_step": "full40_mainline_scored_test",
            "reason": (
                "Five numeric/table seed cases are promoted with compact reviewed facts. The remaining text seed "
                "cases are still blocked from full40 mainline scoring."
            ),
        },
        "case_reviews": [
            {
                "case_id": item["case_id"],
                "decision": "approved_for_gold_context_mode",
                "mainline_status": "can_enter_case_filtered_scored_gold_context_smoke",
                "evidence_assessment": f"Reviewed numeric/table evidence built for {item['case_id']} with {item['context_row_count']} context rows.",
                "fact_assessment": f"Reviewed facts contain {item['fact_count']} target facts across {', '.join(item['metric_families'])}.",
                "required_fix": "Before full40 promotion, run exact-value ledger, table-cell, caveat/claim, and answer-vs-Judgment-Plan gates.",
            }
            for item in case_summaries
        ],
        "gate": {
            "can_enter_full_mainline_scored_test": False,
            "can_enter_case_filtered_gold_context_scored_smoke": True,
            "approved_case_ids": NUMERIC5_CASE_IDS,
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_reviewed_facts(case_id: str) -> list[dict[str, Any]]:
    return _read_json(REVIEWED_FACTS_DIR / f"{case_id}.json").get("facts") or []


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def _display_value_en(value: float, unit: str) -> str:
    if unit == "usd_millions":
        return f"${value / 1000:.3f} billion"
    if unit == "usd_billions":
        return f"${value:.3f} billion"
    if unit == "percent":
        return f"{value:.1f}%"
    return str(value)


def _disallowed_roles(metric_family: str) -> list[str]:
    common = [
        "total_revenue",
        "advertising_revenue",
        "cloud_revenue",
        "product_revenue",
        "rpo",
        "deferred_revenue",
        "cash_flow",
        "ppe_purchases",
        "free_cash_flow_proxy",
        "market_share",
        "stock_market_causality",
    ]
    return [item for item in common if item != metric_family]


if __name__ == "__main__":
    main()
