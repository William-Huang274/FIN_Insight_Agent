from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


SCHEMA_VERSION = "finsight_capital_funding_ownership_context_row_v0_1"
DEFAULT_ADAPTER_SUMMARY = REPO_ROOT / "data" / "manifests" / "capital_macro_source_adapter_summary_v0_1.json"
DEFAULT_WORKING_CAPITAL_ROWS = REPO_ROOT / "data" / "manifests" / "sec_financial_statement_metric_runtime_rows_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "capital_funding_ownership_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "capital_funding_ownership_context_summary_v0_1.json"


CAPITAL_OBJECT_TYPES = {"DebtInstrument", "CreditFacility", "CapitalStructure"}
WORKING_CAPITAL_METRIC_FAMILIES = {
    "current_assets",
    "cash_and_equivalents",
    "accounts_receivable",
    "inventory",
    "current_liabilities",
    "accounts_payable",
    "deferred_revenue",
    "short_term_debt",
    "operating_cash_flow",
    "capital_expenditure_proxy",
    "financing_cash_flow",
}


def build_capital_funding_ownership_context_rows(
    *,
    capital_ownership_rows: Iterable[Mapping[str, Any]],
    financial_statement_rows: Iterable[Mapping[str, Any]] = (),
    generated_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    generated_at = generated_at or _utc_now()
    rows: list[dict[str, Any]] = []
    rejections: Counter[str] = Counter()
    for raw in capital_ownership_rows:
        row = _project_row(raw, generated_at=generated_at)
        if row is None:
            rejections["unsupported_or_unbound_object"] += 1
            continue
        rows.append(row)
    for raw in financial_statement_rows:
        row = _working_capital_liquidity_row(raw, generated_at=generated_at)
        if row is None:
            continue
        rows.append(row)
    rows.sort(key=lambda item: (str(item.get("ticker") or ""), str(item.get("source_role") or ""), str(item.get("evidence_ref") or "")))
    summary = {
        "schema_version": "finsight_capital_funding_ownership_context_summary_v0_1",
        "generated_at": generated_at,
        "status": "pass",
        "row_count": len(rows),
        "rejected_count": sum(rejections.values()),
        "by_source_role": dict(Counter(str(row.get("source_role") or "") for row in rows)),
        "by_object_type": dict(Counter(str(row.get("object_type") or "") for row in rows)),
        "by_source_id": dict(Counter(str(row.get("source_id") or "") for row in rows).most_common()),
        "by_rejection": dict(rejections),
        "policy": (
            "Capital/ownership rows are parser-backed context rows. Company-disclosed capital structure rows may support "
            "capital facts; working-capital rows may support liquidity/cash-conversion analysis; 13F/ownership rows are "
            "lagged context only and must not be promoted to realtime flow."
        ),
    }
    return rows, summary


def _project_row(raw: Mapping[str, Any], *, generated_at: str) -> dict[str, Any] | None:
    object_type = str(raw.get("object_type") or "")
    ticker = str(raw.get("company_id") or raw.get("ticker") or "").upper().strip()
    if not ticker:
        return None
    if object_type in CAPITAL_OBJECT_TYPES:
        return _capital_structure_row(raw, ticker=ticker, generated_at=generated_at)
    if object_type == "OwnershipPosition":
        return _lagged_ownership_row(raw, ticker=ticker, generated_at=generated_at)
    return None


def _capital_structure_row(raw: Mapping[str, Any], *, ticker: str, generated_at: str) -> dict[str, Any]:
    evidence_ref = str(raw.get("evidence_ref") or _stable_id("capital", ticker, raw.get("object_type"), raw.get("period"), raw.get("source_id")))
    source_id = str(raw.get("source_id") or "sec_financial_statement_data_sets")
    object_type = str(raw.get("object_type") or "")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "evidence_ref": evidence_ref,
        "fact_id": evidence_ref,
        "ticker": ticker,
        "company_name": str(raw.get("company_name") or raw.get("issuer_name") or ""),
        "source_family": "primary_sec_filing",
        "runtime_source_family": "primary_sec_filing",
        "source_layer_id": "L1",
        "source_id": source_id,
        "source_role": "capital_structure_disclosure",
        "runtime_contract": "CapitalStructureDisclosureRow",
        "structured_context_type": _capital_context_type(object_type),
        "parser_status": "parser_pass",
        "structured_fact_status": "bounded_context_fact_materialized",
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "product_binding_status": "not_applicable",
        "counterparty_binding_status": "not_bound",
        "source_url": str(raw.get("source_url") or ""),
        "raw_path": str(raw.get("local_path") or raw.get("input_path") or ""),
        "period": str(raw.get("period") or raw.get("period_end") or raw.get("report_date") or ""),
        "filing_date": str(raw.get("filing_date") or ""),
        "object_type": object_type,
        "metric_name": _capital_metric_name(raw),
        "value": _capital_value(raw),
        "unit": str(raw.get("currency") or raw.get("value_unit") or ""),
        "maturity_date": str(raw.get("maturity_date") or ""),
        "coupon": str(raw.get("coupon") or ""),
        "interest_rate_type": str(raw.get("interest_rate_type") or ""),
        "covenant_flag": str(raw.get("covenant_flag") or ""),
        "exact_value_authority": True,
        "can_support_company_exact_fact": True,
        "claim_types": ["capital_structure_disclosure"],
        "allowed_claims": ["capital_structure_fact", "debt_context", "liquidity_context"],
        "forbidden_claims": [
            "undisclosed_financing_terms",
            "market_implied_credit_spread_without_market_source",
            "realtime_refinancing_access_without_source",
        ],
        "citation_span": _trim(str(raw.get("source_statement") or raw.get("citation_anchor") or evidence_ref)),
        "claim_boundary": (
            "Company-disclosed capital structure/debt/credit context only; do not infer undisclosed financing terms, "
            "credit spread, refinancing access, or market liquidity without a separate source."
        ),
    }


def _lagged_ownership_row(raw: Mapping[str, Any], *, ticker: str, generated_at: str) -> dict[str, Any]:
    evidence_ref = str(raw.get("evidence_ref") or _stable_id("ownership", ticker, raw.get("investor_id"), raw.get("report_period")))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "evidence_ref": evidence_ref,
        "fact_id": evidence_ref,
        "ticker": ticker,
        "company_name": str(raw.get("issuer_name") or ""),
        "source_family": "public_source_context",
        "runtime_source_family": "public_source_context",
        "source_layer_id": "L3",
        "source_id": str(raw.get("source_id") or "sec_ownership_and_13f"),
        "source_role": "lagged_ownership_context",
        "runtime_contract": "LaggedOwnershipContextRow",
        "structured_context_type": "lagged_ownership_context",
        "parser_status": "parser_pass",
        "structured_fact_status": "bounded_context_fact_materialized",
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "product_binding_status": "not_applicable",
        "counterparty_binding_status": "not_bound",
        "investor_id": str(raw.get("investor_id") or ""),
        "form_type": str(raw.get("form_type") or ""),
        "report_period": str(raw.get("report_period") or ""),
        "filing_date": str(raw.get("filing_date") or ""),
        "lag_days": str(raw.get("lag_days") or ""),
        "not_realtime_flag": bool(raw.get("not_realtime_flag")),
        "shares": str(raw.get("shares") or ""),
        "value": str(raw.get("value") or ""),
        "unit": str(raw.get("value_unit") or ""),
        "object_type": "OwnershipPosition",
        "metric_name": "lagged_13f_long_position",
        "exact_value_authority": False,
        "can_support_company_exact_fact": False,
        "claim_types": ["lagged_ownership_context"],
        "allowed_claims": ["lagged_ownership_context", "ownership_positioning_signal"],
        "forbidden_claims": ["realtime_flow", "current_buying_pressure", "complete_ownership", "intraday_positioning"],
        "citation_span": evidence_ref,
        "claim_boundary": (
            "13F/ownership filing is lagged public context only; do not describe as real-time money flow, "
            "current buying pressure, complete ownership, or current investor demand."
        ),
    }


def _working_capital_liquidity_row(raw: Mapping[str, Any], *, generated_at: str) -> dict[str, Any] | None:
    metric_family = str(raw.get("metric_family") or "")
    if metric_family not in WORKING_CAPITAL_METRIC_FAMILIES:
        return None
    ticker = str(raw.get("ticker") or "").upper().strip()
    if not ticker:
        return None
    evidence_ref = str(raw.get("evidence_ref") or _stable_id("working_capital", ticker, metric_family, raw.get("period")))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "evidence_ref": evidence_ref,
        "fact_id": evidence_ref,
        "ticker": ticker,
        "company_name": str(raw.get("company_name") or raw.get("company") or ""),
        "source_family": "company_reported_structured_fact",
        "runtime_source_family": "company_reported_structured_fact",
        "source_layer_id": "L1",
        "source_id": str(raw.get("source_id") or "sec_financial_statement_data_sets"),
        "source_role": "working_capital_liquidity",
        "runtime_contract": "WorkingCapitalLiquidityRow",
        "structured_context_type": "working_capital_liquidity_fact",
        "parser_status": "parser_pass",
        "structured_fact_status": "exact_fact_materialized",
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "product_binding_status": "not_applicable",
        "counterparty_binding_status": "not_bound",
        "source_url": str(raw.get("source_url") or raw.get("snapshot_url") or ""),
        "raw_path": str(raw.get("raw_path") or ""),
        "period": str(raw.get("period") or ""),
        "period_end": str(raw.get("period_end") or ""),
        "filing_date": str(raw.get("filing_date") or ""),
        "filing_type": str(raw.get("filing_type") or ""),
        "object_type": "WorkingCapitalLiquidityMetric",
        "metric_family": metric_family,
        "metric_name": str(raw.get("metric_name") or metric_family),
        "statement_or_section": str(raw.get("statement_or_section") or "financial_statement"),
        "value": str(raw.get("value") or ""),
        "unit": str(raw.get("unit") or ""),
        "concept": str(raw.get("concept") or ""),
        "exact_value_authority": True,
        "can_support_company_exact_fact": True,
        "claim_types": ["working_capital_liquidity"],
        "allowed_claims": [
            "working_capital_liquidity_fact",
            "cash_conversion_context",
            "liquidity_context",
            "capital_allocation_context",
        ],
        "forbidden_claims": [
            "product_sales_without_product_kpi",
            "market_share",
            "asp",
            "channel_inventory",
            "sell_through",
            "undisclosed_financing_terms",
            "realtime_refinancing_access_without_source",
        ],
        "citation_span": _trim(str(raw.get("citation_span") or evidence_ref)),
        "claim_boundary": (
            "Company-reported structured financial statement fact for working-capital/liquidity analysis only. "
            "It can support AR/inventory/AP/deferred revenue/current-liability/cash-flow analysis, but cannot "
            "prove product demand, product sales, ASP, market share, channel inventory, sell-through, or backlog."
        ),
    }


def write_outputs(rows: list[dict[str, Any]], summary: Mapping[str, Any], *, output_rows: Path, output_summary: Path) -> dict[str, str]:
    output_rows.parent.mkdir(parents=True, exist_ok=True)
    output_summary.parent.mkdir(parents=True, exist_ok=True)
    output_rows.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    output_summary.write_text(json.dumps(dict(summary), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"rows": str(output_rows), "summary": str(output_summary)}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                payload = json.loads(text)
                if isinstance(payload, dict):
                    rows.append(payload)
    return rows


def _capital_context_type(object_type: str) -> str:
    return {
        "DebtInstrument": "debt_instrument_context",
        "CreditFacility": "credit_facility_context",
        "CapitalStructure": "capital_structure_context",
    }.get(object_type, "capital_structure_context")


def _capital_metric_name(raw: Mapping[str, Any]) -> str:
    object_type = str(raw.get("object_type") or "")
    if object_type == "DebtInstrument":
        return "debt_instrument_principal_coupon_maturity"
    if object_type == "CreditFacility":
        return "credit_facility_size_maturity_covenant"
    if object_type == "CapitalStructure":
        return "cash_debt_net_debt"
    return "capital_structure_metric"


def _capital_value(raw: Mapping[str, Any]) -> str:
    for key in ("principal", "facility_size", "debt", "net_debt", "cash", "value"):
        value = raw.get(key)
        if value not in (None, "", [], {}):
            return str(value)
    return ""


def _trim(text: str, limit: int = 600) -> str:
    clean = " ".join(text.split())
    return clean[:limit]


def _stable_id(*parts: Any) -> str:
    raw = "\x1f".join(str(part or "") for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Project K5/K6 capital macro adapter rows into R18 source-role context rows.")
    parser.add_argument("--adapter-summary", type=Path, default=DEFAULT_ADAPTER_SUMMARY)
    parser.add_argument("--capital-ownership-rows", type=Path, default=None)
    parser.add_argument("--financial-statement-rows", type=Path, default=DEFAULT_WORKING_CAPITAL_ROWS)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = _read_json(args.adapter_summary)
    outputs = summary.get("outputs") if isinstance(summary.get("outputs"), Mapping) else {}
    input_path = args.capital_ownership_rows or Path(str(outputs.get("capital_ownership_rows") or ""))
    rows, out_summary = build_capital_funding_ownership_context_rows(
        capital_ownership_rows=_read_jsonl(input_path),
        financial_statement_rows=_read_jsonl(args.financial_statement_rows),
    )
    written = write_outputs(rows, out_summary, output_rows=args.output_rows, output_summary=args.output_summary)
    print(json.dumps({"status": out_summary["status"], "row_count": out_summary["row_count"], "written": written}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
