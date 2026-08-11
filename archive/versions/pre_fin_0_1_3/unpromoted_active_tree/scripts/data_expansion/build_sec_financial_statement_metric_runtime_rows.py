from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


SCHEMA_VERSION = "finsight_sec_financial_statement_metric_runtime_row_v0_2"
SUMMARY_SCHEMA_VERSION = "finsight_sec_financial_statement_metric_runtime_summary_v0_2"

DEFAULT_INPUT_FACTS = REPO_ROOT / "data" / "staging" / "structured_financial_facts" / "sec_companyfacts_financial_fact_rows_v0_1.jsonl"
DEFAULT_COMPANY_ASSIGNMENTS = REPO_ROOT / "data" / "manifests" / "vertical_source_lane_company_assignments_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "sec_financial_statement_metric_runtime_rows_v0_1.jsonl"
DEFAULT_OUTPUT_REJECTIONS = REPO_ROOT / "data" / "manifests" / "sec_financial_statement_metric_runtime_rejections_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "sec_financial_statement_metric_runtime_summary_v0_1.json"

METRIC_FAMILIES = {
    "revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "operating_cash_flow",
    "investing_cash_flow",
    "financing_cash_flow",
    "capital_expenditure_proxy",
    "r_and_d",
    "assets",
    "current_assets",
    "cash_and_equivalents",
    "accounts_receivable",
    "inventory",
    "liabilities",
    "current_liabilities",
    "accounts_payable",
    "deferred_revenue",
    "short_term_debt",
    "equity",
    "shares_outstanding",
}
POINT_IN_TIME_METRICS = {
    "assets",
    "current_assets",
    "cash_and_equivalents",
    "accounts_receivable",
    "inventory",
    "liabilities",
    "current_liabilities",
    "accounts_payable",
    "deferred_revenue",
    "short_term_debt",
    "equity",
    "shares_outstanding",
}
FORM_PRIORITY = {"10-K": 4, "20-F": 4, "40-F": 4, "10-Q": 2, "10-Q/A": 1, "10-K/A": 3, "20-F/A": 3, "40-F/A": 3}
CANONICAL_CONCEPTS = {
    "revenue": {
        "revenuefromcontractwithcustomerexcludingassessedtax",
        "revenuefromcontractwithcustomerincludingassessedtax",
        "revenues",
        "salesrevenuenet",
        "revenue",
        "revenuefromcontractswithcustomers",
    },
    "gross_profit": {"grossprofit"},
    "operating_income": {"operatingincomeloss", "profitlossfromoperatingactivities"},
    "net_income": {
        "netincomeloss",
        "profitloss",
        "profitlosstoownersofparent",
    },
    "operating_cash_flow": {
        "netcashprovidedbyusedinoperatingactivities",
        "cashflowsfromusedinoperatingactivities",
    },
    "investing_cash_flow": {
        "netcashprovidedbyusedininvestingactivities",
        "cashflowsfromusedininvestingactivities",
    },
    "financing_cash_flow": {
        "netcashprovidedbyusedinfinancingactivities",
        "cashflowsfromusedinfinancingactivities",
    },
    "capital_expenditure_proxy": {
        "paymentstoacquirepropertyplantandequipment",
        "purchaseofpropertyplantandequipment",
        "purchaseofpropertyplantandequipmentclassifiedasinvestingactivities",
        "paymentstoacquireproductiveassets",
        "paymentstoacquirepropertyplantandequipmentandintangibleassets",
    },
    "r_and_d": {
        "researchanddevelopmentexpense",
        "researchanddevelopmentexpenseexcludingacquiredinprocesscost",
    },
    "assets": {"assets"},
    "current_assets": {"assetscurrent"},
    "cash_and_equivalents": {
        "cashandcashequivalentsatcarryingvalue",
        "cashcashequivalentsrestrictedcashandrestrictedcashequivalents",
        "cashcashequivalentsandshortterminvestments",
    },
    "accounts_receivable": {
        "accountsreceivablenetcurrent",
        "receivablesnetcurrent",
        "accountsnotesandloansreceivablenetcurrent",
    },
    "inventory": {
        "inventorynet",
        "inventorycurrent",
        "inventoriesnet",
    },
    "liabilities": {"liabilities"},
    "current_liabilities": {"liabilitiescurrent"},
    "accounts_payable": {
        "accountspayablecurrent",
        "accountspayableandaccruedliabilitiescurrent",
        "accountspayabletradecurrent",
    },
    "deferred_revenue": {
        "contractwithcustomerliabilitycurrent",
        "contractwithcustomerliability",
        "deferredrevenuecurrent",
        "deferredrevenue",
    },
    "short_term_debt": {
        "shorttermborrowings",
        "shorttermdebt",
        "shorttermdebtcurrent",
        "longtermdebtcurrent",
        "currentportionoflongtermdebt",
        "currentmaturitiesoflongtermdebt",
    },
    "equity": {
        "stockholdersequity",
        "stockholdersequityincludingportionattributabletononcontrollinginterest",
        "equity",
        "equityattributabletoownersofparent",
    },
    "shares_outstanding": {"entitycommonstocksharesoutstanding"},
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Project SEC CompanyFacts financial statement rows into L1 exact-slot runtime rows."
    )
    parser.add_argument("--input-facts", type=Path, default=DEFAULT_INPUT_FACTS)
    parser.add_argument("--company-assignments", type=Path, default=DEFAULT_COMPANY_ASSIGNMENTS)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-rejections", type=Path, default=DEFAULT_OUTPUT_REJECTIONS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--tickers", nargs="*", default=[])
    parser.add_argument("--max-metrics-per-ticker", type=int, default=24)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    assignments = _load_jsonl(args.company_assignments)
    universe = _ticker_universe(assignments, tickers=args.tickers)
    result = build_sec_financial_statement_metric_runtime_rows(
        fact_rows=_iter_jsonl(args.input_facts),
        universe=universe,
        generated_at=generated_at,
        max_metrics_per_ticker=args.max_metrics_per_ticker,
    )
    summary = build_summary(
        rows=result["rows"],
        rejections=result["rejections"],
        universe=universe,
        generated_at=generated_at,
        input_facts=args.input_facts,
        output_rows=args.output_rows,
        output_rejections=args.output_rejections,
    )
    _write_jsonl(args.output_rows, result["rows"])
    _write_jsonl(args.output_rejections, result["rejections"])
    _write_json(args.output_summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and not result["rows"]:
        return 1
    return 0


def build_sec_financial_statement_metric_runtime_rows(
    *,
    fact_rows: Iterable[Mapping[str, Any]],
    universe: set[str],
    generated_at: str,
    max_metrics_per_ticker: int = 13,
) -> dict[str, list[dict[str, Any]]]:
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    rejections: list[dict[str, Any]] = []
    rejection_limit = 2000
    for row in fact_rows:
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker or ticker not in universe:
            continue
        reason = _candidate_rejection_reason(row)
        if reason:
            if len(rejections) < rejection_limit:
                rejections.append(_rejection_row(row, reason, generated_at))
            continue
        metric_family = _canonical_metric_family(row)
        key = (ticker, metric_family)
        previous = selected.get(key)
        if previous is None or _candidate_score(row) > _candidate_score(previous):
            selected[key] = dict(row)

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in selected.values():
        grouped.setdefault(str(row.get("ticker") or "").upper(), []).append(row)

    out: list[dict[str, Any]] = []
    for ticker, rows in sorted(grouped.items()):
        ranked = sorted(rows, key=_metric_rank, reverse=True)[: max(1, max_metrics_per_ticker)]
        for row in ranked:
            out.append(_runtime_row(row, generated_at=generated_at))
    return {"rows": out, "rejections": rejections}


def build_summary(
    *,
    rows: list[dict[str, Any]],
    rejections: list[dict[str, Any]],
    universe: set[str],
    generated_at: str,
    input_facts: Path,
    output_rows: Path,
    output_rejections: Path,
) -> dict[str, Any]:
    row_tickers = {str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")}
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if rows else "gap",
        "input_facts": str(input_facts),
        "universe_ticker_count": len(universe),
        "runtime_row_count": len(rows),
        "runtime_ticker_count": len(row_tickers),
        "uncovered_ticker_count": len(universe - row_tickers),
        "uncovered_tickers": sorted(universe - row_tickers),
        "metric_family_counts": dict(sorted(Counter(str(row.get("metric_family") or "") for row in rows).items())),
        "form_type_counts": dict(sorted(Counter(str(row.get("filing_type") or "") for row in rows).items())),
        "rejection_sample_count": len(rejections),
        "rejection_reason_counts": dict(sorted(Counter(str(row.get("rejection_reason") or "") for row in rejections).items())),
        "outputs": {"rows": str(output_rows), "rejections": str(output_rejections)},
        "claim_boundary": (
            "Rows are SEC CompanyFacts/company-reported structured financial statement facts. They can support "
            "consolidated fundamental analysis, but cannot stand in for product KPI, product sales, market share, "
            "ASP, channel inventory, or sell-through."
        ),
    }


def _candidate_rejection_reason(row: Mapping[str, Any]) -> str:
    metric_family = _canonical_metric_family(row)
    if metric_family not in METRIC_FAMILIES:
        return "concept_not_in_canonical_statement_focus"
    for field in ("ticker", "source_url", "value", "unit", "period_end", "fiscal_year", "form_type", "accession_number"):
        if _blank(row.get(field)):
            return f"missing_{field}"
    try:
        float(row.get("value"))
    except (TypeError, ValueError):
        return "value_not_numeric"
    return ""


def _candidate_score(row: Mapping[str, Any]) -> tuple[int, int, int, str, str, str]:
    metric_family = _canonical_metric_family(row)
    fiscal_year = _int(row.get("fiscal_year"))
    form_type = str(row.get("form_type") or "").upper()
    period_role, _, _ = _normalized_period_semantics(row)
    if metric_family in POINT_IN_TIME_METRICS:
        period_priority = 4 if period_role == "instant" else 0
    else:
        period_priority = {"annual": 4, "ytd": 2, "qtd": 1}.get(period_role, 0)
    return (
        period_priority,
        fiscal_year,
        FORM_PRIORITY.get(form_type, 0),
        str(row.get("filed_date") or ""),
        str(row.get("period_end") or row.get("end_date") or ""),
        str(row.get("fact_id") or ""),
    )


def _metric_rank(row: Mapping[str, Any]) -> tuple[int, tuple[int, int, int, str, str, str]]:
    metric_order = {
        "revenue": 100,
        "gross_profit": 95,
        "operating_income": 90,
        "net_income": 85,
        "operating_cash_flow": 80,
        "capital_expenditure_proxy": 75,
        "investing_cash_flow": 70,
        "financing_cash_flow": 65,
        "r_and_d": 60,
        "assets": 55,
        "current_assets": 54,
        "cash_and_equivalents": 53,
        "accounts_receivable": 52,
        "inventory": 51,
        "liabilities": 50,
        "current_liabilities": 49,
        "accounts_payable": 48,
        "deferred_revenue": 47,
        "short_term_debt": 46,
        "equity": 45,
        "shares_outstanding": 40,
    }.get(_canonical_metric_family(row), 0)
    return metric_order, _candidate_score(row)


def _runtime_row(fact: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    ticker = str(fact.get("ticker") or "").strip().upper()
    metric_family = _canonical_metric_family(fact)
    metric_name = str(fact.get("label") or fact.get("concept") or metric_family).strip()
    period_role, duration_days, duration_months = _normalized_period_semantics(fact)
    raw_fiscal_period = str(fact.get("raw_fiscal_period") or fact.get("fiscal_period") or "").upper().strip()
    fiscal_period = _canonical_fiscal_period(
        raw_fiscal_period=raw_fiscal_period,
        period_role=period_role,
        form_type=str(fact.get("form_type") or ""),
    )
    period = _period_label(fact, fiscal_period=fiscal_period)
    statement = _statement_or_section(metric_family)
    source_url = str(fact.get("source_url") or "").strip()
    accession_number = str(fact.get("accession_number") or "").strip()
    concept = f"{fact.get('taxonomy')}:{fact.get('concept')}"
    citation_span = (
        f"SEC CompanyFacts {fact.get('form_type')} {accession_number} reports {concept} "
        f"({metric_name}) = {fact.get('value')} {fact.get('unit')} for {period}; "
        f"period_end={fact.get('period_end') or fact.get('end_date')}; filed={fact.get('filed_date')}."
    )
    evidence_ref = _stable_ref("sec_financial_statement_metric", [ticker, metric_family, accession_number, concept, period])
    text = f"{ticker} reported {metric_name} of {fact.get('value')} {fact.get('unit')} for {period}."
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "snapshot_id": evidence_ref,
        "source_id": "sec_financial_statement_data_sets",
        "underlying_source_id": "sec_companyfacts_api",
        "source_class": "company_reported_structured_financial_fact",
        "source_family": "company_reported_structured_fact",
        "runtime_source_family": "company_reported_structured_fact",
        "source_layer_id": "L1",
        "source_layer": "L1",
        "layer_id": "L1",
        "source_specific_parser": "sec_companyfacts_financial_statement_metric_projector_v0_2",
        "source_specific_resolver": "sec_cik_to_issuer_resolver_v0_1",
        "parser_status": "value_unit_period_product_citation_parser_pass",
        "structured_fact_status": "exact_fact_materialized",
        "runtime_ready_context": True,
        "bounded_structured_context": True,
        "exact_value_authority": True,
        "can_support_company_exact_fact": True,
        "ticker": ticker,
        "company": fact.get("company_name") or fact.get("entity_name") or "",
        "company_name": fact.get("company_name") or fact.get("entity_name") or "",
        "issuer_id": fact.get("issuer_id") or fact.get("cik") or "",
        "cik": fact.get("cik") or "",
        "source_url": source_url,
        "snapshot_url": source_url,
        "api_url": source_url,
        "citation": {"url": source_url, "source_url": source_url, "title": citation_span, "span": citation_span},
        "source_title": f"{ticker} SEC CompanyFacts {metric_name}",
        "source_document_id": accession_number,
        "filing_type": fact.get("form_type") or "",
        "filing_date": fact.get("filed_date") or "",
        "source_filed_at": fact.get("source_filed_at") or fact.get("filed_date") or "",
        "published_at": fact.get("published_at") or fact.get("filed_date") or "",
        "as_of_date": "",
        "snapshot_at": fact.get("snapshot_at") or generated_at,
        "period": period,
        "period_start": fact.get("start_date") or "",
        "period_end": fact.get("period_end") or fact.get("end_date") or "",
        "period_role": period_role,
        "duration_days": duration_days,
        "duration_months": duration_months,
        "fiscal_year": fact.get("fiscal_year"),
        "fiscal_period": fiscal_period,
        "raw_fiscal_period": raw_fiscal_period,
        "statement_or_section": statement,
        "metric_family": metric_family,
        "metric_name": metric_name,
        "canonical_metric_id": f"financial_metric:{metric_family}",
        "value": fact.get("value"),
        "unit": fact.get("unit") or "",
        "raw_value_text": fact.get("value_text") or str(fact.get("value") or ""),
        "concept": fact.get("concept") or "",
        "taxonomy": fact.get("taxonomy") or "",
        "product_or_segment": "Consolidated company",
        "product_family": "Consolidated company",
        "citation_span": citation_span,
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "product_binding_status": "not_applicable",
        "counterparty_binding_status": "not_bound",
        "entity_binding": {
            "issuer_ticker": ticker,
            "issuer_binding_status": "issuer_mentioned_in_snapshot",
            "product_binding_status": "not_applicable",
            "counterparty_binding_status": "not_bound",
            "resolver_status": "sec_cik_companyfacts_bound_to_issuer",
            "binding_claim_boundary": "SEC CIK/companyfacts issuer binding only; product-level claims require product KPI rows.",
        },
        "allowed_claims": ["company_reported_financial_statement_fact", f"financial_metric:{metric_family}"],
        "forbidden_claims": ["product_sales_without_product_kpi", "market_share", "asp", "channel_inventory", "sell_through"],
        "claim_boundary": (
            "SEC CompanyFacts structured financial statement fact; supports consolidated financial analysis only. "
            "It cannot be used as product KPI or market-share evidence."
        ),
        "text": text,
        "preview": text,
    }


def _statement_or_section(metric_family: str) -> str:
    if metric_family in {"revenue", "gross_profit", "operating_income", "net_income", "r_and_d"}:
        return "income_statement"
    if metric_family in {
        "assets",
        "current_assets",
        "cash_and_equivalents",
        "accounts_receivable",
        "inventory",
        "liabilities",
        "current_liabilities",
        "accounts_payable",
        "deferred_revenue",
        "short_term_debt",
        "equity",
        "shares_outstanding",
    }:
        return "balance_sheet"
    if metric_family in {"operating_cash_flow", "investing_cash_flow", "financing_cash_flow", "capital_expenditure_proxy"}:
        return "cash_flow_statement"
    return "financial_statement"


def _canonical_metric_family(row: Mapping[str, Any]) -> str:
    concept = _normalize_concept(row.get("concept"))
    taxonomy = str(row.get("taxonomy") or "").lower()
    for metric_family, concepts in CANONICAL_CONCEPTS.items():
        if concept in concepts:
            return metric_family
    if taxonomy.startswith("dei") and concept == "entitycommonstocksharesoutstanding":
        return "shares_outstanding"
    return ""


def _normalize_concept(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _period_label(row: Mapping[str, Any], *, fiscal_period: str | None = None) -> str:
    fiscal_year = row.get("fiscal_year")
    fiscal_period = str(fiscal_period if fiscal_period is not None else row.get("fiscal_period") or "").strip()
    period_end = str(row.get("period_end") or row.get("end_date") or "").strip()
    if fiscal_year and fiscal_period:
        return f"FY{fiscal_year}-{fiscal_period}"
    if fiscal_year:
        return f"FY{fiscal_year}"
    return period_end


def _normalized_period_semantics(row: Mapping[str, Any]) -> tuple[str, int | None, int | None]:
    start_text = str(row.get("start_date") or "").strip()
    end_text = str(row.get("period_end") or row.get("end_date") or "").strip()
    if not start_text:
        return "instant", None, None
    try:
        start = date.fromisoformat(start_text)
        end = date.fromisoformat(end_text)
    except ValueError:
        role = str(row.get("period_role") or "period").lower().strip()
        return role, _int_or_none(row.get("duration_days")), _int_or_none(row.get("duration_months"))
    if end < start:
        return "period", None, None
    duration_days = (end - start).days + 1
    duration_months = max(1, round(duration_days / 30.4375))
    if 330 <= duration_days <= 380:
        role = "annual"
    elif 75 <= duration_days <= 110:
        role = "qtd"
    elif 111 <= duration_days < 330:
        role = "ytd"
    else:
        role = "period"
    return role, duration_days, duration_months


def _canonical_fiscal_period(*, raw_fiscal_period: str, period_role: str, form_type: str) -> str:
    if period_role == "annual":
        return "FY"
    if period_role == "qtd":
        if raw_fiscal_period in {"Q1", "Q2", "Q3", "Q4"}:
            return raw_fiscal_period
        if raw_fiscal_period == "FY" and form_type.upper() in {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}:
            return "Q4"
    return raw_fiscal_period


def _ticker_universe(assignments: Iterable[Mapping[str, Any]], *, tickers: Iterable[str]) -> set[str]:
    filters = {str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()}
    universe = {str(row.get("ticker") or "").strip().upper() for row in assignments if str(row.get("ticker") or "").strip()}
    return universe.intersection(filters) if filters else universe


def _rejection_row(row: Mapping[str, Any], reason: str, generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": "finsight_sec_financial_statement_metric_runtime_rejection_v0_1",
        "generated_at": generated_at,
        "rejection_reason": reason,
        "fact_id": row.get("fact_id"),
        "ticker": row.get("ticker"),
        "metric_family": row.get("metric_family"),
        "concept": row.get("concept"),
        "form_type": row.get("form_type"),
        "fiscal_year": row.get("fiscal_year"),
    }


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            value = json.loads(text)
            if isinstance(value, Mapping):
                yield dict(value)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return list(_iter_jsonl(path) or [])


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _stable_ref(prefix: str, parts: Iterable[Any]) -> str:
    digest = hashlib.sha1("||".join(str(part or "") for part in parts).encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
