"""Materialize lane-specific customer/adoption operating-footprint signals.

This projector intentionally stays narrower than generic financial statement
facts. It only admits issuer-bound, parser-backed SEC CompanyFacts rows that
represent operating footprint for industries where a "customer deployment page"
is not the natural disclosure unit: bank deposits, insurance premiums, REIT
property footprint, energy reserves/production, etc.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.layer_acceptance_gates import load_jsonl  # noqa: E402


SCHEMA_VERSION = "finsight_customer_operating_footprint_signal_row_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_customer_operating_footprint_signal_summary_v0_1"

MANIFEST_DIR = REPO_ROOT / "data" / "manifests"
DEFAULT_FACTS = REPO_ROOT / "data" / "staging" / "structured_financial_facts" / "sec_companyfacts_financial_fact_rows_v0_1.jsonl"
DEFAULT_RAW_COMPANYFACTS_DIR = REPO_ROOT / "data" / "raw_private" / "structured_financial_facts" / "sec"
DEFAULT_DEPTH_MATRIX = MANIFEST_DIR / "second_third_layer_depth_parity_matrix_v0_1.jsonl"
DEFAULT_LANE_ASSIGNMENTS = MANIFEST_DIR / "vertical_source_lane_company_assignments_v0_1.jsonl"
DEFAULT_FAMILY_ASSIGNMENTS = MANIFEST_DIR / "company_product_family_assignments_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = MANIFEST_DIR / "customer_operating_footprint_signal_runtime_rows_v0_1.jsonl"
DEFAULT_OUTPUT_REJECTIONS = MANIFEST_DIR / "customer_operating_footprint_signal_rejections_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = MANIFEST_DIR / "customer_operating_footprint_signal_summary_v0_1.json"
OUTPUT_SOURCE_FILE = DEFAULT_OUTPUT_ROWS.name

ANNUAL_FORMS = {"10-K", "20-F", "40-F"}
ACCEPTED_FORMS = ANNUAL_FORMS | {"10-Q"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build strict customer operating-footprint signal rows.")
    parser.add_argument("--facts", type=Path, default=DEFAULT_FACTS)
    parser.add_argument("--raw-companyfacts-dir", type=Path, default=DEFAULT_RAW_COMPANYFACTS_DIR)
    parser.add_argument("--use-staging-facts", action="store_true")
    parser.add_argument("--depth-matrix", type=Path, default=DEFAULT_DEPTH_MATRIX)
    parser.add_argument("--lane-assignments", type=Path, default=DEFAULT_LANE_ASSIGNMENTS)
    parser.add_argument("--family-assignments", type=Path, default=DEFAULT_FAMILY_ASSIGNMENTS)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-rejections", type=Path, default=DEFAULT_OUTPUT_REJECTIONS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument(
        "--all-tickers",
        action="store_true",
        help="Project all tickers in the company context. Slower; use for full rebuilds.",
    )
    parser.add_argument(
        "--current-depth-gaps-only",
        action="store_true",
        help="Diagnostic mode: project only tickers that currently fail customer-deployment depth.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    target_tickers = _target_tickers(args.depth_matrix, all_tickers=args.all_tickers, current_gaps_only=args.current_depth_gaps_only)
    company_context = _company_context(args.lane_assignments, args.family_assignments)
    fact_rows = (
        load_jsonl(args.facts)
        if args.use_staging_facts
        else _iter_raw_companyfacts_rows(args.raw_companyfacts_dir, set(company_context) if target_tickers is None else target_tickers)
    )
    result = build_customer_operating_footprint_signal_rows(
        fact_rows=fact_rows,
        company_context=company_context,
        generated_at=generated_at,
        target_tickers=target_tickers,
    )
    rows = result["rows"]
    rejections = result["rejections"]
    args.output_rows.parent.mkdir(parents=True, exist_ok=True)
    args.output_rows.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    args.output_rejections.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rejections),
        encoding="utf-8",
    )
    summary = _summary(
        rows=rows,
        rejections=rejections,
        generated_at=generated_at,
        target_tickers=target_tickers,
        output_rows=args.output_rows,
        output_rejections=args.output_rejections,
    )
    args.output_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if rows else 1


def build_customer_operating_footprint_signal_rows(
    *,
    fact_rows: Iterable[Mapping[str, Any]],
    company_context: Mapping[str, Mapping[str, Any]],
    generated_at: str,
    target_tickers: set[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    selected: dict[tuple[str, str], Mapping[str, Any]] = {}
    classifications: dict[tuple[str, str], dict[str, str]] = {}
    rejections: list[dict[str, Any]] = []
    rejection_limit = 3000

    for fact in fact_rows:
        ticker = str(fact.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        if target_tickers is not None and ticker not in target_tickers:
            continue
        context = company_context.get(ticker, {})
        classification = _classify_operating_footprint(fact, context)
        if classification is None:
            if len(rejections) < rejection_limit and _looks_operating_adjacent(fact):
                rejections.append(_rejection_row(fact, generated_at, "not_strict_customer_operating_footprint"))
            continue
        reason = _required_field_rejection(fact)
        if reason:
            if len(rejections) < rejection_limit:
                rejections.append(_rejection_row(fact, generated_at, reason))
            continue
        key = (ticker, classification["metric_family"])
        previous = selected.get(key)
        if previous is None or _candidate_score(fact, classification) > _candidate_score(previous, classifications[key]):
            selected[key] = dict(fact)
            classifications[key] = classification

    rows: list[dict[str, Any]] = []
    for key, fact in sorted(selected.items()):
        rows.append(_runtime_row(fact, classifications[key], generated_at=generated_at, context=company_context.get(key[0], {})))
    return {"rows": rows, "rejections": rejections}


def _customer_depth_gap_tickers(depth_matrix: Path) -> set[str]:
    tickers: set[str] = set()
    for row in load_jsonl(depth_matrix):
        dimension = (row.get("dimensions") or {}).get("customer_deployment_depth") or {}
        if not dimension.get("target_depth_met"):
            ticker = str(row.get("ticker") or "").strip().upper()
            if ticker:
                tickers.add(ticker)
    return tickers


def _target_tickers(depth_matrix: Path, *, all_tickers: bool, current_gaps_only: bool) -> set[str] | None:
    if all_tickers:
        return None
    gap_tickers = _customer_depth_gap_tickers(depth_matrix)
    if current_gaps_only:
        return gap_tickers
    return gap_tickers | _matrix_tickers_using_this_projection(depth_matrix)


def _matrix_tickers_using_this_projection(depth_matrix: Path) -> set[str]:
    tickers: set[str] = set()
    for row in load_jsonl(depth_matrix):
        customer_depth = ((row.get("dimensions") or {}).get("customer_deployment_depth") or {})
        source_files = customer_depth.get("source_files") or {}
        if int(source_files.get(OUTPUT_SOURCE_FILE) or 0) <= 0:
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        if ticker:
            tickers.add(ticker)
    return tickers


def _company_context(lane_assignments: Path, family_assignments: Path) -> dict[str, dict[str, Any]]:
    context: dict[str, dict[str, Any]] = {}
    for path in (lane_assignments, family_assignments):
        if not path.exists():
            continue
        for row in load_jsonl(path):
            ticker = str(row.get("ticker") or "").strip().upper()
            if ticker:
                context.setdefault(ticker, {}).update(row)
    return context


def _iter_raw_companyfacts_rows(raw_companyfacts_dir: Path, tickers: set[str] | None) -> Iterable[dict[str, Any]]:
    if tickers is None:
        ticker_dirs = sorted(path for path in raw_companyfacts_dir.iterdir() if path.is_dir())
    else:
        ticker_dirs = [raw_companyfacts_dir / ticker for ticker in sorted(tickers)]
    for ticker_dir in ticker_dirs:
        ticker = ticker_dir.name.upper()
        payload_path = ticker_dir / "sec_companyfacts.json"
        if not payload_path.exists():
            continue
        try:
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        cik = str(payload.get("cik") or "").zfill(10)
        source_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json" if cik.strip("0") else ""
        company_name = payload.get("entityName") or payload.get("entity_name") or ""
        for taxonomy, concepts in (payload.get("facts") or {}).items():
            if not isinstance(concepts, Mapping):
                continue
            for concept, concept_payload in concepts.items():
                if not isinstance(concept_payload, Mapping):
                    continue
                label = concept_payload.get("label") or concept
                description = concept_payload.get("description") or ""
                for unit, unit_facts in (concept_payload.get("units") or {}).items():
                    if not isinstance(unit_facts, list):
                        continue
                    for fact in unit_facts:
                        if not isinstance(fact, Mapping):
                            continue
                        value = fact.get("val")
                        if not isinstance(value, (int, float)):
                            continue
                        yield {
                            "ticker": ticker,
                            "cik": cik,
                            "issuer_id": cik,
                            "company_name": company_name,
                            "entity_name": company_name,
                            "taxonomy": taxonomy,
                            "concept": concept,
                            "label": label,
                            "description": description,
                            "unit": unit,
                            "value": value,
                            "value_text": str(value),
                            "period_end": fact.get("end") or "",
                            "end_date": fact.get("end") or "",
                            "start_date": fact.get("start") or "",
                            "fiscal_year": fact.get("fy"),
                            "fiscal_period": fact.get("fp") or "",
                            "form_type": fact.get("form") or "",
                            "accession_number": fact.get("accn") or "",
                            "filed_date": fact.get("filed") or "",
                            "frame": fact.get("frame") or "",
                            "source_url": source_url,
                            "fact_source": "sec_companyfacts",
                            "source_family": "sec_companyfacts_structured_fact",
                        }


def _classify_operating_footprint(fact: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, str] | None:
    concept = _normalized_concept(fact)
    unit = str(fact.get("unit") or "").strip()
    sector = str(context.get("sector") or "").strip().lower()
    family = str(context.get("family_id") or "").strip().lower()

    contract_classification = _customer_contract_footprint_classification(concept)
    if contract_classification:
        return contract_classification

    if _is_forbidden_ordinary_statement_or_capital_row(concept):
        return None

    if sector == "financials":
        if _is_insurance_premium_concept(concept):
            return {
                "source_role": "financial_services_operating_metric",
                "metric_family": "insurance_premiums_or_policies",
                "signal_authority_type": "insurance_policy_premium_operating_footprint",
            }
        if concept == "deposits":
            return {
                "source_role": "financial_services_operating_metric",
                "metric_family": "deposits",
                "signal_authority_type": "bank_deposit_operating_footprint",
            }
        if _is_bank_loan_balance_concept(concept):
            return {
                "source_role": "financial_services_operating_metric",
                "metric_family": "loan_balance",
                "signal_authority_type": "bank_loan_operating_footprint",
            }
        if any(token in concept for token in ("assetsundermanagement", "assetsundercustody", "assetsunderadministration", "clientassets")):
            return {
                "source_role": "financial_services_operating_metric",
                "metric_family": "client_assets",
                "signal_authority_type": "asset_management_client_asset_footprint",
            }

    if sector == "real estate" or "real_estate" in family:
        if concept in {
            "numberofrealestateproperties",
            "secscheduleiiirealestatenumberofunits",
            "netrentablearea",
            "areaofrealestateproperty",
        }:
            return {
                "source_role": "real_estate_operating_footprint",
                "metric_family": "real_estate_footprint",
                "signal_authority_type": "real_estate_property_or_area_footprint",
            }

    if sector == "energy" or family == "upstream_oil_gas":
        if "proveddevelopedandundevelopedreserve" in concept and unit.upper() not in {"", "USD"}:
            return {
                "source_role": "production_or_throughput",
                "metric_family": "production_or_throughput",
                "signal_authority_type": "energy_reserve_or_production_footprint",
            }

    if sector == "utilities" or "utility" in family:
        if unit.upper() not in {"", "USD"} and any(
            token in concept
            for token in (
                "numberofcustomers",
                "electriccustomers",
                "gascustomers",
                "customersserved",
                "megawatthours",
                "generatingcapacity",
                "ownedgeneratingcapacity",
            )
        ):
            return {
                "source_role": "mw_or_generation_capacity",
                "metric_family": "mw_or_generation_capacity",
                "signal_authority_type": "utility_customer_generation_footprint",
            }

    if family == "homebuilding_residential" and unit.upper() not in {"", "USD"}:
        if any(token in concept for token in ("homesdelivered", "homesclosed", "neworders", "backlog", "homesettlements")):
            return {
                "source_role": "unit_sales_or_deliveries",
                "metric_family": "unit_sales_or_deliveries",
                "signal_authority_type": "homebuilding_order_or_delivery_footprint",
            }

    if family == "healthcare_facilities_services" and unit.upper() not in {"", "USD"}:
        if any(token in concept for token in ("patient", "admissions", "beds", "visits")):
            return {
                "source_role": "patient_volume",
                "metric_family": "patient_volume",
                "signal_authority_type": "healthcare_patient_volume_footprint",
            }

    if unit.upper() not in {"", "USD"} and concept in {"numberofstores", "numberofretailstores"}:
        return {
            "source_role": "store_or_location_footprint",
            "metric_family": "store_or_location_count",
            "signal_authority_type": "retail_or_distribution_location_footprint",
        }

    if "mining_materials" in family and unit.upper() not in {"", "USD"}:
        if any(token in concept for token in ("tons", "tonnes", "copperproduction", "steelshipments", "productionvolume", "shipments")):
            return {
                "source_role": "production_or_throughput",
                "metric_family": "production_or_throughput",
                "signal_authority_type": "materials_production_or_shipment_footprint",
            }

    return None


def _is_insurance_premium_concept(concept: str) -> bool:
    return bool(
        re.fullmatch(r"(direct|assumed|ceded)?premiumsearned(net)?", concept)
        or re.fullmatch(r"(direct|assumed|ceded)?premiumswritten(net)?", concept)
        or "supplementaryinsuranceinformationpremiumswritten" in concept
        or "supplementalinformationforpropertycasualtyinsuranceunderwriterspremiumswritten" in concept
    )


def _is_bank_loan_balance_concept(concept: str) -> bool:
    return bool(
        re.fullmatch(r"loans(andleases)?receivable(net|heldforinvestment|recordedinvestment)?", concept)
        or re.fullmatch(r"loansandleasesreceivablenetreportedamount", concept)
    )


def _customer_contract_footprint_classification(concept: str) -> dict[str, str] | None:
    """Classify strict customer-contract footprints before generic liability rejection.

    These concepts are issuer-bound exact rows about contract liabilities/assets,
    remaining performance obligations, airline traffic liabilities, or customer
    advances/deposits. They are customer/demand footprint signals, not product
    revenue, customer names, order value, backlog, or deployment proof.
    """
    if "tax" in concept:
        return None
    contract_liability_concepts = {
        "contractwithcustomerliability",
        "contractwithcustomerliabilitycurrent",
        "contractwithcustomerliabilitynoncurrent",
        "contractwithcustomerrefundliability",
        "contractwithcustomerrefundliabilitycurrent",
        "contractwithcustomerrefundliabilitynoncurrent",
        "deferredrevenue",
        "deferredrevenuecurrent",
        "deferredrevenuenoncurrent",
        "airtrafficliabilitycurrent",
        "airtrafficliabilitynoncurrent",
        "airtrafficliability",
        "customeradvancesforconstruction",
        "customeradvancescurrent",
        "customeradvancesnoncurrent",
        "customeradvances",
        "customeradvancesanddeposits",
        "customerdepositscurrent",
        "customerdepositsnoncurrent",
        "customerdeposits",
        "depositsfromcustomers",
        "currentdepositsfromcustomers",
        "noncurrentdepositsfromcustomers",
    }
    rpo_concepts = {
        "revenueremainingperformanceobligation",
        "revenueremainingperformanceobligationpercentage",
        "transactionpriceallocatedtoremainingperformanceobligations",
    }
    contract_asset_concepts = {
        "contractwithcustomerassetnetcurrent",
        "contractwithcustomerassetnetnoncurrent",
        "contractwithcustomerassetnet",
        "capitalizedcontractcostnetcurrent",
        "capitalizedcontractcostnetnoncurrent",
        "capitalizedcontractcostnet",
    }
    if concept in rpo_concepts:
        return {
            "source_role": "customer_contract_liability_footprint",
            "metric_family": "remaining_performance_obligation",
            "signal_authority_type": "customer_contract_rpo_footprint",
        }
    if concept in contract_liability_concepts:
        return {
            "source_role": "customer_contract_liability_footprint",
            "metric_family": "customer_contract_liability_or_deposit",
            "signal_authority_type": "customer_contract_liability_footprint",
        }
    if concept in contract_asset_concepts:
        return {
            "source_role": "customer_contract_asset_footprint",
            "metric_family": "customer_contract_asset_or_cost",
            "signal_authority_type": "customer_contract_asset_footprint",
        }
    return None


def _is_forbidden_ordinary_statement_or_capital_row(concept: str) -> bool:
    forbidden_fragments = {
        "publicfloat",
        "sharesoutstanding",
        "costof",
        "depreciation",
        "amortization",
        "accountspayable",
        "accountsreceivable",
        "liability",
        "liabilities",
        "tax",
        "cash",
        "assetretirement",
        "creditfacility",
        "lineofcredit",
        "goodwill",
        "fairvalue",
        "allowance",
        "securities",
        "derivative",
        "depositsonflight",
        "payments",
        "proceeds",
        "interestexpense",
        "interestincome",
        "bankownedlifeinsurance",
        "loansreceivablefairvalue",
        "depositsassets",
        "depositsfromcustomers",
        "margindeposits",
        "securitydeposits",
        "earnestmoneydeposits",
    }
    return any(fragment in concept for fragment in forbidden_fragments)


def _required_field_rejection(fact: Mapping[str, Any]) -> str:
    for field in ("ticker", "source_url", "value", "unit", "period_end", "fiscal_year", "form_type", "accession_number"):
        if _blank(fact.get(field)):
            return f"missing_{field}"
    if str(fact.get("form_type") or "").upper() not in ACCEPTED_FORMS:
        return "form_type_not_periodic_filing"
    try:
        float(fact.get("value"))
    except (TypeError, ValueError):
        return "value_not_numeric"
    return ""


def _candidate_score(fact: Mapping[str, Any], classification: Mapping[str, str]) -> tuple[int, int, int, str, str]:
    fiscal_year = _int(fact.get("fiscal_year"))
    form_type = str(fact.get("form_type") or "").upper()
    concept = _normalized_concept(fact)
    return (
        fiscal_year,
        3 if form_type in ANNUAL_FORMS else 2 if form_type == "10-Q" else 0,
        _concept_preference(concept, classification),
        str(fact.get("period_end") or fact.get("end_date") or ""),
        str(fact.get("filed_date") or ""),
    )


def _concept_preference(concept: str, classification: Mapping[str, str]) -> int:
    metric_family = classification.get("metric_family")
    if metric_family == "insurance_premiums_or_policies":
        order = {
            "directpremiumswritten": 100,
            "directpremiumsearned": 95,
            "premiumswrittennet": 90,
            "premiumsearnednet": 85,
            "supplementaryinsuranceinformationpremiumswritten": 80,
            "supplementalinformationforpropertycasualtyinsuranceunderwriterspremiumswritten": 80,
            "assumedpremiumswritten": 65,
            "assumedpremiumsearned": 60,
            "cededpremiumswritten": 40,
            "cededpremiumsearned": 35,
        }
        return order.get(concept, 0)
    if metric_family == "real_estate_footprint":
        return {
            "netrentablearea": 100,
            "areaofrealestateproperty": 95,
            "secscheduleiiirealestatenumberofunits": 90,
            "numberofrealestateproperties": 85,
        }.get(concept, 0)
    if metric_family == "production_or_throughput":
        if "reserveproduction" in concept:
            return 100
        if "reservenet" in concept:
            return 90
        return 70
    if metric_family == "remaining_performance_obligation":
        return 100
    if metric_family == "customer_contract_liability_or_deposit":
        if "airtrafficliability" in concept:
            return 100
        if "contractwithcustomerliability" in concept:
            return 95
        if (
            "customeradvances" in concept
            or "customerdeposits" in concept
            or "depositsfromcustomers" in concept
            or "customeradvancesanddeposits" in concept
        ):
            return 90
        if "deferredrevenue" in concept:
            return 85
        if "refundliability" in concept:
            return 70
        return 60
    if metric_family == "customer_contract_asset_or_cost":
        if "contractwithcustomerasset" in concept:
            return 80
        if "capitalizedcontractcostnet" in concept:
            return 60
        return 40
    if metric_family == "deposits":
        return 100 if concept == "deposits" else 0
    if metric_family == "store_or_location_count":
        return 85
    return 50


def _runtime_row(
    fact: Mapping[str, Any],
    classification: Mapping[str, str],
    *,
    generated_at: str,
    context: Mapping[str, Any],
) -> dict[str, Any]:
    ticker = str(fact.get("ticker") or "").strip().upper()
    concept = f"{fact.get('taxonomy')}:{fact.get('concept')}"
    period = _period_label(fact)
    evidence_ref = _stable_ref(
        "customer_operating_footprint_signal",
        [ticker, classification["metric_family"], str(fact.get("accession_number") or ""), concept, period],
    )
    metric_name = str(fact.get("label") or fact.get("concept") or classification["metric_family"]).strip()
    source_url = str(fact.get("source_url") or "").strip()
    citation_span = (
        f"SEC CompanyFacts {fact.get('form_type')} {fact.get('accession_number')} reports {concept} "
        f"({metric_name}) = {fact.get('value')} {fact.get('unit')} for {period}; "
        f"period_end={fact.get('period_end') or fact.get('end_date')}; filed={fact.get('filed_date')}."
    )
    text = f"{ticker} reported {metric_name} of {fact.get('value')} {fact.get('unit')} for {period}."
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "snapshot_id": evidence_ref,
        "source_id": "sec_companyfacts_operating_footprint",
        "underlying_source_id": "sec_companyfacts_api",
        "source_class": "company_reported_structured_operating_footprint",
        "source_family": "company_reported_structured_fact",
        "runtime_source_family": "company_reported_structured_fact",
        "source_layer_id": "L2",
        "source_layer": "L2",
        "layer_id": "L2",
        "source_role": classification["source_role"],
        "signal_authority_type": classification["signal_authority_type"],
        "source_specific_parser": "sec_companyfacts_customer_operating_footprint_projector_v0_1",
        "source_specific_resolver": "sec_cik_to_issuer_resolver_v0_1",
        "parser_status": "value_unit_period_product_citation_parser_pass",
        "structured_fact_status": "exact_fact_materialized",
        "runtime_ready_context": True,
        "bounded_structured_context": True,
        "exact_value_authority": True,
        "can_support_company_exact_fact": True,
        "ticker": ticker,
        "company": fact.get("company_name") or fact.get("entity_name") or context.get("company_name") or "",
        "company_name": fact.get("company_name") or fact.get("entity_name") or context.get("company_name") or "",
        "issuer_id": fact.get("issuer_id") or fact.get("cik") or "",
        "cik": fact.get("cik") or "",
        "source_url": source_url,
        "snapshot_url": source_url,
        "api_url": source_url,
        "citation": {"url": source_url, "source_url": source_url, "title": citation_span, "span": citation_span},
        "source_title": f"{ticker} SEC CompanyFacts {metric_name}",
        "source_document_id": fact.get("accession_number") or "",
        "filing_type": fact.get("form_type") or "",
        "filing_date": fact.get("filed_date") or "",
        "period": period,
        "period_end": fact.get("period_end") or fact.get("end_date") or "",
        "fiscal_year": fact.get("fiscal_year"),
        "fiscal_period": fact.get("fiscal_period") or "",
        "metric_family": classification["metric_family"],
        "metric_name": metric_name,
        "canonical_metric_id": f"operating_footprint:{classification['metric_family']}",
        "value": fact.get("value"),
        "unit": fact.get("unit") or "",
        "raw_value_text": fact.get("value_text") or str(fact.get("value") or ""),
        "concept": fact.get("concept") or "",
        "taxonomy": fact.get("taxonomy") or "",
        "product_or_segment": _product_or_segment(classification, context),
        "product_family": context.get("family_id") or _product_or_segment(classification, context),
        "citation_span": citation_span,
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "product_binding_status": "company_or_lane_operating_footprint",
        "counterparty_binding_status": "not_bound",
        "entity_binding": {
            "issuer_ticker": ticker,
            "issuer_binding_status": "sec_cik_companyfacts_bound_to_issuer",
            "product_binding_status": "company_or_lane_operating_footprint",
            "counterparty_binding_status": "not_bound",
            "resolver_status": "sec_cik_companyfacts_bound_to_issuer",
            "binding_claim_boundary": "Issuer-bound structured operating-footprint signal; no customer names or undisclosed order values.",
        },
        "allowed_claims": [
            "company_disclosed_industry_operating_metric",
            "company_reported_operating_footprint_signal",
            classification["signal_authority_type"],
        ],
        "claim_types": ["company_disclosed_industry_operating_metric", "company_reported_operating_footprint_signal"],
        "forbidden_claims": [
            "customer_name",
            "undisclosed_customer_win",
            "order_value_without_order_source",
            "product_revenue_without_product_kpi",
            "market_share",
            "asp",
            "channel_inventory",
            "sell_through",
            "backlog_without_rpo_or_order_source",
        ],
        "claim_boundary": (
            "CompanyFacts operating-footprint row. It can support bounded adoption/activity context for the issuer's "
            "industry, but cannot prove customer names, deployment wins, order value, product revenue, ASP, market "
            "share, inventory, sell-through, or backlog unless those exact fields are separately disclosed."
        ),
        "text": text,
        "preview": text,
    }


def _product_or_segment(classification: Mapping[str, str], context: Mapping[str, Any]) -> str:
    family = str(context.get("family_id") or "")
    if family:
        return family
    return classification["metric_family"]


def _summary(
    *,
    rows: list[dict[str, Any]],
    rejections: list[dict[str, Any]],
    generated_at: str,
    target_tickers: set[str] | None,
    output_rows: Path,
    output_rejections: Path,
) -> dict[str, Any]:
    row_tickers = {str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")}
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if rows else "gap",
        "target_ticker_count": len(target_tickers) if target_tickers is not None else None,
        "runtime_row_count": len(rows),
        "runtime_ticker_count": len(row_tickers),
        "runtime_tickers": sorted(row_tickers),
        "metric_family_counts": dict(sorted(Counter(str(row.get("metric_family") or "") for row in rows).items())),
        "source_role_counts": dict(sorted(Counter(str(row.get("source_role") or "") for row in rows).items())),
        "signal_authority_type_counts": dict(sorted(Counter(str(row.get("signal_authority_type") or "") for row in rows).items())),
        "rejection_sample_count": len(rejections),
        "rejection_reason_counts": dict(sorted(Counter(str(row.get("rejection_reason") or "") for row in rejections).items())),
        "outputs": {"rows": str(output_rows), "rejections": str(output_rejections)},
        "claim_boundary": (
            "Rows are strict issuer-bound CompanyFacts operating-footprint facts for industry activity/adoption context. "
            "They do not carry product revenue, market share, ASP, channel inventory, sell-through, customer names, or order value authority."
        ),
    }


def _rejection_row(fact: Mapping[str, Any], generated_at: str, reason: str) -> dict[str, Any]:
    return {
        "schema_version": "finsight_customer_operating_footprint_signal_rejection_v0_1",
        "generated_at": generated_at,
        "ticker": str(fact.get("ticker") or "").strip().upper(),
        "concept": fact.get("concept") or "",
        "label": fact.get("label") or "",
        "unit": fact.get("unit") or "",
        "period_end": fact.get("period_end") or "",
        "fiscal_year": fact.get("fiscal_year"),
        "form_type": fact.get("form_type") or "",
        "rejection_reason": reason,
        "claim_boundary": "Rejected rows are not admitted to customer/adoption operating-footprint authority.",
    }


def _looks_operating_adjacent(fact: Mapping[str, Any]) -> bool:
    haystack = " ".join(str(fact.get(field) or "") for field in ("concept", "label", "description")).lower()
    return any(
        token in haystack
        for token in (
            "deposit",
            "loan",
            "premium",
            "policy",
            "customer",
            "property",
            "rentable",
            "reserve",
            "production",
            "passenger",
            "capacity",
            "backlog",
            "orders",
            "patient",
        )
    )


def _normalized_concept(fact: Mapping[str, Any]) -> str:
    return re.sub(r"[^a-z0-9]", "", str(fact.get("concept") or "").lower())


def _period_label(fact: Mapping[str, Any]) -> str:
    fy = fact.get("fiscal_year")
    fp = str(fact.get("fiscal_period") or "").strip()
    if fy and fp:
        return f"FY{fy}-{fp}"
    if fy:
        return f"FY{fy}"
    return str(fact.get("period_end") or fact.get("end_date") or "")


def _stable_ref(prefix: str, parts: Iterable[str]) -> str:
    digest = hashlib.sha256("||".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _blank(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
