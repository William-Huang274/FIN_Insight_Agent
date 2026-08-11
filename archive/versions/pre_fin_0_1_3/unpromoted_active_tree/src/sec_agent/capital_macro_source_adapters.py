from __future__ import annotations

import csv
import hashlib
import json
import re
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


CAPITAL_MACRO_SOURCE_ADAPTER_SCHEMA_VERSION = "sec_agent_capital_macro_source_adapter_v0.1"

SEC_13F_SOURCE_ID = "sec_ownership_and_13f"
SEC_FSD_SOURCE_ID = "sec_financial_statement_data_sets"

CASH_TAGS = {
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    "CashAndDueFromBanks",
}
DEBT_TAGS = {
    "DebtCurrent",
    "ShortTermBorrowings",
    "LongTermDebtCurrent",
    "LongTermDebtNoncurrent",
    "LongTermDebtAndFinanceLeaseObligationsCurrent",
    "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
    "LongTermDebtAndFinanceLeaseObligations",
    "LongTermDebt",
    "FinanceLeaseLiabilityCurrent",
    "FinanceLeaseLiabilityNoncurrent",
}
OWNERSHIP_FORMS = {"13F", "13F-HR", "13F-HR/A", "13F-NT", "13F-NT/A", "13D", "13D/A", "13G", "13G/A", "DEF 14A"}
OFFERING_FORMS = {"S-1", "S-1/A", "S-3", "S-3/A", "F-1", "F-1/A", "F-3", "F-3/A", "424B", "424B2", "424B3", "424B4", "424B5", "424B7", "424B8"}
INSIDER_FORMS = {"3", "3/A", "4", "4/A", "5", "5/A", "FORM 3", "FORM 4", "FORM 5"}


def build_capital_macro_source_adapter(
    inputs: Mapping[str, Any],
    *,
    max_items_per_family: int = 5000,
) -> dict[str, Any]:
    """Map materialized public-source rows into CapitalMacroExposurePack inputs.

    This layer is intentionally conservative. It only emits pack input rows when
    the source row has enough source-specific fields for the downstream pack
    gate. Everything else becomes a typed source gap.
    """

    capital_ownership_rows: list[dict[str, Any]] = []
    macro_driver_rows: list[dict[str, Any]] = []
    macro_exposure_rows: list[dict[str, Any]] = []
    vertical_official_object_rows: list[dict[str, Any]] = []
    source_gaps: list[dict[str, Any]] = []

    target_companies = _target_company_rows(inputs)
    ticker_by_cik = _ticker_by_cik(target_companies)
    ticker_by_issuer_name = _ticker_by_issuer_name(target_companies)

    capital_ownership_rows.extend(_mapping_items(inputs.get("capital_ownership_rows")))
    capital_ownership_rows.extend(_mapping_items(inputs.get("preparsed_capital_ownership_rows")))

    sec_text_result = adapt_sec_capital_text_rows(_mapping_items(inputs.get("sec_capital_text_rows")))
    capital_ownership_rows.extend(sec_text_result["capital_ownership_rows"])
    source_gaps.extend(sec_text_result["source_gaps"])

    sec_filing_result = adapt_sec_filing_metadata_rows(_mapping_items(inputs.get("sec_filing_metadata_rows")))
    capital_ownership_rows.extend(sec_filing_result["capital_ownership_rows"])
    source_gaps.extend(sec_filing_result["source_gaps"])

    sec_13f_rows = _mapping_items(inputs.get("sec_13f_rows"))
    if sec_13f_rows:
        sec_13f_result = adapt_sec_13f_rows(sec_13f_rows, ticker_by_issuer_name=ticker_by_issuer_name)
        capital_ownership_rows.extend(sec_13f_result["capital_ownership_rows"])
        source_gaps.extend(sec_13f_result["source_gaps"])

    sec_fsd_rows = _mapping_items(inputs.get("sec_fsd_fact_rows"))
    if sec_fsd_rows:
        sec_fsd_result = adapt_sec_fsd_fact_rows(sec_fsd_rows, ticker_by_cik=ticker_by_cik)
        capital_ownership_rows.extend(sec_fsd_result["capital_ownership_rows"])
        source_gaps.extend(sec_fsd_result["source_gaps"])

    public_rows = [
        *_mapping_items(inputs.get("public_source_normalized_records")),
        *_mapping_items(inputs.get("public_source_endpoint_records")),
        *_mapping_items(inputs.get("public_source_mapping_candidates")),
    ]
    public_result = adapt_public_source_rows(public_rows, target_companies=target_companies)
    macro_driver_rows.extend(public_result["macro_driver_rows"])
    macro_exposure_rows.extend(public_result["macro_exposure_rows"])
    vertical_official_object_rows.extend(public_result["vertical_official_object_rows"])
    source_gaps.extend(public_result["source_gaps"])

    payload = {
        "schema_version": CAPITAL_MACRO_SOURCE_ADAPTER_SCHEMA_VERSION,
        "adapter_id": _stable_id(
            "CapitalMacroSourceAdapter",
            [
                str(inputs.get("run_id") or "capital_macro_source_adapter"),
                str(len(public_rows)),
                str(len(capital_ownership_rows)),
            ],
        ),
        "policy": "source_specific_parser_backfill_to_pack_input_no_proxy_promotion",
        "capital_ownership_rows": _cap(capital_ownership_rows, max_items=max_items_per_family),
        "macro_driver_rows": _cap(macro_driver_rows, max_items=max_items_per_family),
        "macro_exposure_rows": _cap(macro_exposure_rows, max_items=max_items_per_family),
        "vertical_official_object_rows": _cap(vertical_official_object_rows, max_items=max_items_per_family),
        "source_gaps": _cap(source_gaps, max_items=max_items_per_family),
    }
    payload["summary"] = _summary(payload)
    payload["status"] = "pass" if payload["summary"]["pack_input_row_count"] else "gap_only"
    return payload


def merge_capital_macro_source_adapter_state(state: Mapping[str, Any], adapter: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(state)
    merged["capital_macro_source_adapter"] = dict(adapter)
    for target_key, adapter_key in (
        ("capital_ownership_rows", "capital_ownership_rows"),
        ("macro_driver_rows", "macro_driver_rows"),
        ("macro_exposure_rows", "macro_exposure_rows"),
        ("vertical_official_object_rows", "vertical_official_object_rows"),
        ("source_gaps", "source_gaps"),
    ):
        merged[target_key] = [*_mapping_items(state.get(target_key)), *_mapping_items(adapter.get(adapter_key))]
    return merged


def adapt_sec_capital_text_rows(rows: Iterable[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    capital_rows: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for row in rows:
        form_type = _first_text(row, "form_type", "filing_type").upper()
        text = _source_text(row)
        ticker = _ticker(row)
        if not text.strip() and form_type not in INSIDER_FORMS and form_type not in OFFERING_FORMS:
            continue
        debt = _debt_instrument_from_text_row(row, text=text, ticker=ticker)
        if debt:
            capital_rows.append(debt)
        elif _looks_like_debt_text(text):
            gaps.append(_gap(row, "parser_failed", "sec_debt_footnote_required_fields_missing", target="sec_debt_footnote"))
        facility = _credit_facility_from_text_row(row, text=text, ticker=ticker)
        if facility:
            capital_rows.append(facility)
        offering = _equity_offering_from_text_or_metadata(row, text=text, ticker=ticker)
        if offering:
            capital_rows.append(offering)
        elif _is_offering_form_or_source(row):
            gaps.append(_gap(row, "parser_failed", "offering_required_amount_security_type_or_date_missing", target="sec_offering"))
        insider = _insider_transaction_from_row(row, ticker=ticker)
        if insider:
            capital_rows.append(insider)
        elif form_type in INSIDER_FORMS:
            gaps.append(_gap(row, "parser_failed", "insider_transaction_required_fields_missing", target="sec_form_3_4_5"))
    return {"capital_ownership_rows": capital_rows, "source_gaps": gaps}


def adapt_sec_filing_metadata_rows(rows: Iterable[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    capital_rows: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for row in rows:
        form_type = _first_text(row, "form_type", "filing_type", "SUBMISSIONTYPE").upper()
        if form_type in OFFERING_FORMS:
            offering = _equity_offering_from_text_or_metadata(row, text=_source_text(row), ticker=_ticker(row))
            if offering:
                capital_rows.append(offering)
            else:
                gaps.append(_gap(row, "parser_failed", "offering_metadata_has_no_amount_or_security_type", target="sec_offering"))
        elif form_type in {"13D", "13D/A", "13G", "13G/A", "DEF 14A"}:
            ownership = _ownership_from_schedule_or_proxy_row(row)
            if ownership:
                capital_rows.append(ownership)
            else:
                gaps.append(_gap(row, "parser_failed", "schedule_or_proxy_ownership_fields_missing", target="sec_13d_13g_proxy"))
        elif form_type in INSIDER_FORMS:
            insider = _insider_transaction_from_row(row, ticker=_ticker(row))
            if insider:
                capital_rows.append(insider)
            else:
                gaps.append(_gap(row, "parser_failed", "insider_transaction_required_fields_missing", target="sec_form_3_4_5"))
    return {"capital_ownership_rows": capital_rows, "source_gaps": gaps}


def adapt_sec_13f_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    ticker_by_issuer_name: Mapping[str, str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    ticker_map = dict(ticker_by_issuer_name or {})
    cover_by_accession: dict[str, Mapping[str, Any]] = {}
    submission_by_accession: dict[str, Mapping[str, Any]] = {}
    capital_rows: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []

    pending_info_rows: list[Mapping[str, Any]] = []
    for row in rows:
        accession = _first_text(row, "ACCESSION_NUMBER", "accession_number", "accession")
        record_type = _first_text(row, "record_type", "table_name", "member_name").lower()
        if "cover" in record_type or _first_text(row, "FILINGMANAGER_NAME", "filing_manager_name"):
            cover_by_accession[accession] = row
        elif "submission" in record_type or _first_text(row, "SUBMISSIONTYPE", "submission_type"):
            submission_by_accession[accession] = row
        elif _first_text(row, "NAMEOFISSUER", "name_of_issuer", "issuer_name"):
            pending_info_rows.append(row)

    for row in pending_info_rows:
        accession = _first_text(row, "ACCESSION_NUMBER", "accession_number", "accession")
        issuer_name = _first_text(row, "NAMEOFISSUER", "name_of_issuer", "issuer_name")
        company_id = _ticker(row) or ticker_map.get(_normalize_name(issuer_name), "")
        if not company_id:
            gaps.append(_gap(row, "alias_gap", "13f_issuer_name_not_mapped_to_target_company", target="sec_13f"))
            continue
        cover = cover_by_accession.get(accession) or {}
        submission = submission_by_accession.get(accession) or {}
        manager = _first_text(cover, "FILINGMANAGER_NAME", "filing_manager_name", "manager_name")
        filing_date = _date_from_any(_first_text(submission, "FILING_DATE", "filing_date", "filed"))
        report_period = _date_from_any(
            _first_text(submission, "PERIODOFREPORT", "period_of_report", "REPORTCALENDARORQUARTER", "report_calendar_or_quarter")
            or _first_text(cover, "REPORTCALENDARORQUARTER", "report_calendar_or_quarter")
        )
        shares = _first_text(row, "SSHPRNAMT", "ssh_prnamt", "shares")
        value = _first_text(row, "VALUE", "value", "market_value")
        if not all([manager, filing_date, report_period, shares, value]):
            gaps.append(_gap(row, "parser_failed", "13f_required_manager_period_or_position_fields_missing", target="sec_13f"))
            continue
        capital_rows.append(
            {
                "evidence_ref": _first_text(row, "evidence_ref", "row_id") or f"13f:{accession}:{_first_text(row, 'INFOTABLE_SK', 'infotable_sk')}",
                "object_type": "OwnershipPosition",
                "source_family": "public_source_context",
                "source_id": SEC_13F_SOURCE_ID,
                "form_type": _first_text(submission, "SUBMISSIONTYPE", "submission_type") or "13F",
                "investor_id": manager,
                "company_id": company_id,
                "issuer_name": issuer_name,
                "cusip": _first_text(row, "CUSIP", "cusip"),
                "shares": shares,
                "value": value,
                "value_unit": "USD_thousands_as_reported_by_13f",
                "filing_date": filing_date,
                "report_period": report_period,
                "lag_days": _lag_days(report_period, filing_date),
                "lag_policy": "sec_13f_lagged_long_position_context_not_realtime_flow",
                "not_realtime_flag": True,
                "claim_scope": "lagged_ownership_context_only",
            }
        )
    return {"capital_ownership_rows": capital_rows, "source_gaps": gaps}


def adapt_sec_fsd_fact_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    ticker_by_cik: Mapping[str, str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    ticker_map = dict(ticker_by_cik or {})
    by_accession: dict[str, dict[str, Any]] = defaultdict(dict)
    meta_by_accession: dict[str, dict[str, str]] = defaultdict(dict)
    gaps: list[dict[str, Any]] = []

    for row in rows:
        accession = _first_text(row, "adsh", "accession_number")
        if not accession:
            continue
        cik = _first_text(row, "cik")
        if cik:
            meta_by_accession[accession]["cik"] = cik
            meta_by_accession[accession]["ticker"] = ticker_map.get(_normalize_cik(cik), _ticker(row))
            meta_by_accession[accession]["period"] = _first_text(row, "period", "ddate")
        tag = _first_text(row, "tag")
        if tag not in CASH_TAGS and tag not in DEBT_TAGS:
            continue
        if _first_text(row, "segments"):
            continue
        value = _first_text(row, "value")
        if not _is_number(value):
            continue
        key = "cash" if tag in CASH_TAGS else "debt"
        by_accession[accession][key] = by_accession[accession].get(key, 0.0) + float(str(value).replace(",", ""))
        meta_by_accession[accession]["period"] = _first_text(row, "ddate", "period") or meta_by_accession[accession].get("period", "")

    capital_rows: list[dict[str, Any]] = []
    for accession, values in by_accession.items():
        meta = meta_by_accession.get(accession) or {}
        company_id = meta.get("ticker") or ""
        if not company_id:
            gaps.append(_gap({"source_id": SEC_FSD_SOURCE_ID, "evidence_ref": accession}, "alias_gap", "fsd_accession_cik_not_mapped_to_target_company", target="sec_fsd_capital_structure"))
            continue
        if "cash" not in values or "debt" not in values:
            gaps.append(_gap({"source_id": SEC_FSD_SOURCE_ID, "evidence_ref": accession, "ticker": company_id}, "parser_failed", "fsd_cash_or_debt_component_missing", target="sec_fsd_capital_structure"))
            continue
        period = _date_from_yyyymmdd(meta.get("period") or "")
        cash = values["cash"]
        debt = values["debt"]
        capital_rows.append(
            {
                "evidence_ref": f"fsd-capital-structure:{accession}",
                "object_type": "CapitalStructure",
                "source_family": "primary_sec_filing",
                "source_id": SEC_FSD_SOURCE_ID,
                "company_id": company_id,
                "cash": _format_number(cash),
                "debt": _format_number(debt),
                "net_debt": _format_number(debt - cash),
                "period": period or meta.get("period") or accession,
                "claim_scope": "company_reported_capital_structure_fact",
            }
        )
        gaps.append(_gap({"source_id": SEC_FSD_SOURCE_ID, "evidence_ref": accession, "ticker": company_id}, "not_disclosed", "fsd_capital_totals_do_not_include_debt_maturity_coupon_or_rate_type", target="sec_debt_footnote_detail"))
    return {"capital_ownership_rows": capital_rows, "source_gaps": gaps}


def adapt_public_source_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    target_companies: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    macro_rows: list[dict[str, Any]] = []
    exposure_rows: list[dict[str, Any]] = []
    vertical_rows: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []

    target_by_ticker = {_ticker(row): row for row in target_companies or [] if _ticker(row)}
    for row in rows:
        source_id = _source_id(row)
        record_type = _first_text(row, "record_type").lower()
        if record_type in {"macro_time_series_observation", "macro_table_observation", "macro_cross_section_observation"}:
            macro = _macro_driver_from_public_row(row)
            if macro:
                macro_rows.append(macro)
                exposure_rows.extend(_company_exposures_for_macro_driver(macro, row=row, target_by_ticker=target_by_ticker))
            else:
                gaps.append(_gap(row, "parser_failed", "macro_driver_required_fields_missing_or_value_unavailable", target=source_id))
        elif record_type == "trade_context_observation":
            trade = _trade_driver_from_public_row(row)
            if trade:
                macro_rows.append(trade)
                exposure_rows.extend(_company_exposures_for_macro_driver(trade, row=row, target_by_ticker=target_by_ticker))
            else:
                gaps.append(_gap(row, "parser_failed", "trade_driver_required_fields_missing_or_value_unavailable", target=source_id))
        elif record_type in {
            "clinical_trial_status_record",
            "fda_product_status_record",
            "vehicle_model_identity_record",
            "institution_reference_record",
            "patent_data_access_metadata_record",
            "research_work_lead_record",
        }:
            vertical = _vertical_official_object_from_public_row(row)
            if vertical:
                vertical_rows.append(vertical)
            else:
                gaps.append(_gap(row, "alias_gap", f"{record_type}_requires_company_or_product_binding", target=source_id))
        elif source_id in {"clinicaltrials_api", "openfda_api", "nhtsa_vpic_api", "fdic_bankfind_api"} and _ticker(row):
            vertical = _vertical_official_object_from_mapping_candidate(row)
            if vertical:
                vertical_rows.append(vertical)
            else:
                gaps.append(_gap(row, "parser_failed", f"{source_id}_mapping_candidate_missing_status_or_identifier", target=source_id))
    return {
        "macro_driver_rows": macro_rows,
        "macro_exposure_rows": exposure_rows,
        "vertical_official_object_rows": vertical_rows,
        "source_gaps": gaps,
    }


def parse_sec_13f_bulk_zip(
    zip_path: str | Path,
    *,
    target_companies: Sequence[Mapping[str, Any]],
    max_positions: int = 5000,
) -> dict[str, list[dict[str, Any]]]:
    path = Path(zip_path)
    if not path.exists():
        return {"capital_ownership_rows": [], "source_gaps": [_gap({"source_id": SEC_13F_SOURCE_ID}, "not_found", f"13f_zip_not_found:{path}", target="sec_13f")]}
    issuer_map = _ticker_by_issuer_name(target_companies)
    cover_by_accession: dict[str, dict[str, str]] = {}
    submission_by_accession: dict[str, dict[str, str]] = {}
    output_rows: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as archive:
        cover_by_accession = {row.get("ACCESSION_NUMBER", ""): row for row in _iter_tsv_member(archive, "COVERPAGE.tsv")}
        submission_by_accession = {row.get("ACCESSION_NUMBER", ""): row for row in _iter_tsv_member(archive, "SUBMISSION.tsv")}
        info_rows: list[dict[str, Any]] = []
        for row in _iter_tsv_member(archive, "INFOTABLE.tsv"):
            issuer_name = row.get("NAMEOFISSUER", "")
            if _normalize_name(issuer_name) not in issuer_map:
                continue
            accession = row.get("ACCESSION_NUMBER", "")
            info_rows.append(
                {
                    "record_type": "INFOTABLE",
                    **row,
                    **{f"cover_{key}": value for key, value in (cover_by_accession.get(accession) or {}).items()},
                    **{f"submission_{key}": value for key, value in (submission_by_accession.get(accession) or {}).items()},
                }
            )
            if len(info_rows) >= max_positions:
                break
    result = adapt_sec_13f_rows(
        [
            *({"record_type": "COVERPAGE", **row} for row in cover_by_accession.values()),
            *({"record_type": "SUBMISSION", **row} for row in submission_by_accession.values()),
            *info_rows,
        ],
        ticker_by_issuer_name=issuer_map,
    )
    output_rows.extend(result["capital_ownership_rows"])
    gaps.extend(result["source_gaps"])
    return {"capital_ownership_rows": output_rows[:max_positions], "source_gaps": gaps}


def parse_sec_fsd_capital_structure_zip(
    zip_path: str | Path,
    *,
    target_companies: Sequence[Mapping[str, Any]],
    max_filings: int = 1000,
) -> dict[str, list[dict[str, Any]]]:
    path = Path(zip_path)
    if not path.exists():
        return {"capital_ownership_rows": [], "source_gaps": [_gap({"source_id": SEC_FSD_SOURCE_ID}, "not_found", f"fsd_zip_not_found:{path}", target="sec_fsd_capital_structure")]}
    ticker_by_cik = _ticker_by_cik(target_companies)
    target_ciks = set(ticker_by_cik)
    sub_rows: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(path) as archive:
        for row in _iter_tsv_member(archive, "sub.txt"):
            cik = _normalize_cik(row.get("cik"))
            if cik not in target_ciks:
                continue
            form = str(row.get("form") or "").upper()
            if form not in {"10-K", "10-Q", "20-F", "40-F"}:
                continue
            accession = str(row.get("adsh") or "")
            sub_rows[accession] = {
                "adsh": accession,
                "cik": cik,
                "ticker": ticker_by_cik.get(cik, ""),
                "period": row.get("period", ""),
                "filed": row.get("filed", ""),
            }
            if len(sub_rows) >= max_filings:
                break
        fact_rows: list[dict[str, Any]] = []
        for row in _iter_tsv_member(archive, "num.txt"):
            accession = str(row.get("adsh") or "")
            if accession not in sub_rows:
                continue
            tag = str(row.get("tag") or "")
            if tag not in CASH_TAGS and tag not in DEBT_TAGS:
                continue
            fact_rows.append({**sub_rows[accession], **row})
    return adapt_sec_fsd_fact_rows(fact_rows, ticker_by_cik=ticker_by_cik)


def _debt_instrument_from_text_row(row: Mapping[str, Any], *, text: str, ticker: str) -> dict[str, Any] | None:
    if not ticker or not _looks_like_debt_text(text):
        return None
    span = _debt_instrument_relation_span(text)
    if not span:
        return None
    amount = _extract_debt_principal(span)
    coupon = _extract_coupon(span)
    maturity = _extract_maturity(span)
    if not all([amount, coupon, maturity]):
        return None
    return {
        "evidence_ref": _evidence_ref(row),
        "object_type": "DebtInstrument",
        "source_family": "primary_sec_filing",
        "source_id": _source_id(row) or "sec_debt_footnote_parser",
        **_source_lineage(row),
        "company_id": ticker,
        "principal": amount["value"],
        "currency": amount["unit"],
        "maturity_date": maturity,
        "coupon": coupon,
        "interest_rate_type": "fixed" if "fixed" in text.lower() or coupon else "not_disclosed",
        "citation_anchor": _first_text(row, "chunk_id", "citation_anchor", "source_url"),
        "source_statement": _clip_statement(span),
        "claim_scope": "company_disclosed_debt_context",
    }


def _credit_facility_from_text_row(row: Mapping[str, Any], *, text: str, ticker: str) -> dict[str, Any] | None:
    lowered = text.lower()
    if not ticker or ("credit facility" not in lowered and "revolving" not in lowered and "revolver" not in lowered and "term loan" not in lowered):
        return None
    span = _credit_facility_relation_span(text)
    if not span:
        return None
    amount = _extract_facility_size(span)
    maturity = _extract_maturity(span)
    if not amount or not maturity:
        return None
    return {
        "evidence_ref": f"{_evidence_ref(row)}:credit_facility",
        "object_type": "CreditFacility",
        "source_family": "primary_sec_filing",
        "source_id": _source_id(row) or "sec_credit_facility_parser",
        **_source_lineage(row),
        "company_id": ticker,
        "facility_size": amount["value"],
        "available_liquidity": _first_text(row, "available_liquidity", "undrawn_amount") or "not_disclosed",
        "maturity_date": maturity,
        "covenant_flag": "mentioned" if "covenant" in lowered else "not_disclosed",
        "citation_anchor": _first_text(row, "chunk_id", "citation_anchor", "source_url"),
        "source_statement": _clip_statement(span),
        "claim_scope": "company_disclosed_credit_facility_context",
    }


def _equity_offering_from_text_or_metadata(row: Mapping[str, Any], *, text: str, ticker: str) -> dict[str, Any] | None:
    if not ticker:
        return None
    form_type = _first_text(row, "form_type", "filing_type", "SUBMISSIONTYPE").upper()
    if not _is_offering_form_or_source(row):
        return None
    amount = _first_text(row, "amount", "offering_amount", "value")
    if not amount:
        parsed_amount = _extract_amount(text)
        amount = parsed_amount["value"] if parsed_amount else ""
    security_type = _first_text(row, "security_type", "security") or _extract_security_type(text)
    filing_date = _date_from_any(_first_text(row, "filing_date", "FILING_DATE", "accepted_date", "date"))
    if not all([form_type, amount, security_type, filing_date]):
        return None
    return {
        "evidence_ref": _evidence_ref(row),
        "object_type": "EquityOffering",
        "source_family": "primary_sec_filing",
        "source_id": _source_id(row) or "sec_offering_parser",
        **_source_lineage(row),
        "company_id": ticker,
        "form_type": form_type,
        "filing_date": filing_date,
        "amount": amount,
        "security_type": security_type,
        "claim_scope": "public_offering_context",
    }


def _insider_transaction_from_row(row: Mapping[str, Any], *, ticker: str) -> dict[str, Any] | None:
    form_type = _first_text(row, "form_type", "filing_type", "SUBMISSIONTYPE").upper()
    if form_type not in INSIDER_FORMS:
        return None
    insider_id = _first_text(row, "insider_id", "insider_name", "owner_name", "reporting_owner")
    transaction_type = _first_text(row, "transaction_type", "transaction_code")
    transaction_date = _date_from_any(_first_text(row, "transaction_date", "date", "filing_date"))
    shares = _first_text(row, "shares", "transaction_shares")
    price = _first_text(row, "price", "transaction_price")
    if not all([ticker, insider_id, transaction_type, transaction_date, shares, price]):
        return None
    return {
        "evidence_ref": _evidence_ref(row),
        "object_type": "InsiderTransaction",
        "source_family": "public_source_context",
        "source_id": _source_id(row) or "sec_form_3_4_5_parser",
        **_source_lineage(row),
        "company_id": ticker,
        "insider_id": insider_id,
        "transaction_type": transaction_type,
        "transaction_date": transaction_date,
        "shares": shares,
        "price": price,
        "form_type": form_type,
        "claim_scope": "public_insider_filing_context",
    }


def _ownership_from_schedule_or_proxy_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    ticker = _ticker(row)
    investor = _first_text(row, "investor_id", "owner_name", "reporting_owner", "manager_name")
    shares = _first_text(row, "shares", "ssh_prnamt")
    value = _first_text(row, "value", "market_value")
    filing_date = _date_from_any(_first_text(row, "filing_date", "FILING_DATE", "accepted_date"))
    report_period = _date_from_any(_first_text(row, "report_period", "period_of_report", "period", "PERIODOFREPORT")) or filing_date
    form_type = _first_text(row, "form_type", "filing_type", "SUBMISSIONTYPE").upper()
    if not all([ticker, investor, shares, value, filing_date, report_period, form_type]):
        return None
    return {
        "evidence_ref": _evidence_ref(row),
        "object_type": "OwnershipPosition",
        "source_family": "public_source_context",
        "source_id": _source_id(row) or "sec_schedule_or_proxy_parser",
        "company_id": ticker,
        "investor_id": investor,
        "shares": shares,
        "value": value,
        "filing_date": filing_date,
        "report_period": report_period,
        "form_type": form_type,
        "lag_days": _lag_days(report_period, filing_date),
        "lag_policy": "public_ownership_filing_not_realtime_flow",
        "not_realtime_flag": True,
        "claim_scope": "lagged_ownership_context_only",
    }


def _macro_driver_from_public_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    value = _first_text(row, "value", "numeric_value")
    attrs = _dict_value(row.get("attributes"))
    if not value:
        value = _first_text(attrs, "value")
    if not _is_observed_value(value):
        return None
    series_id = _first_text(row, "series_id", "external_id") or _first_text(attrs, "route", "metric_name")
    variable = _first_text(row, "variable_name", "metric_name", "external_name") or _first_text(attrs, "metric_name", "route") or series_id
    observed_at = _date_from_any(_first_text(row, "observation_date", "period", "date") or _first_text(attrs, "period", "year"))
    if not all([series_id, variable, observed_at]):
        return None
    return {
        "evidence_ref": _evidence_ref(row),
        "object_type": "MacroDriver",
        "record_type": "macro_time_series_observation",
        "source_family": "industry_snapshot",
        "source_id": _source_id(row),
        "provider": _first_text(row, "provider"),
        "series_id": series_id,
        "variable_name": variable,
        "value": str(value),
        "unit": _first_text(row, "unit") or _first_text(attrs, "unit") or "not_disclosed",
        "date": observed_at,
        "frequency": _infer_frequency(row, attrs),
        "claim_scope": "macro_or_industry_context_only",
        "context_only": True,
        "exact_value_authority": False,
    }


def _trade_driver_from_public_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    value = _first_text(row, "value", "trade_value")
    attrs = _dict_value(row.get("attributes"))
    if not value:
        value = _first_text(attrs, "value")
    if not _is_observed_value(value):
        return None
    series_id = _first_text(row, "series_id", "external_id") or _first_text(attrs, "route", "metric_name")
    code = _first_text(row, "product_or_code", "commodity_code", "hs_code", "external_id") or _first_text(attrs, "commodity_code", "hs_code")
    country = _first_text(row, "country_or_region", "country", "entity_name", "external_name") or "not_disclosed"
    observed_at = _date_from_any(_first_text(row, "observation_date", "period", "date") or _first_text(attrs, "period", "year"))
    if not all([series_id, code, observed_at]):
        return None
    return {
        "evidence_ref": _evidence_ref(row),
        "object_type": "TradeDriver",
        "record_type": "trade_context_observation",
        "source_family": "industry_snapshot",
        "source_id": _source_id(row),
        "series_id": series_id,
        "product_or_code": code,
        "country_or_region": country,
        "value": str(value),
        "unit": _first_text(row, "unit") or _first_text(attrs, "unit") or "not_disclosed",
        "date": observed_at,
        "claim_scope": "trade_context_only",
        "context_only": True,
        "exact_value_authority": False,
    }


def _vertical_official_object_from_public_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    ticker = _ticker(row)
    if not ticker:
        return None
    attrs = _dict_value(row.get("attributes"))
    record_type = _first_text(row, "record_type")
    source_id = _source_id(row)
    observed_at = _date_from_any(
        _first_text(row, "observed_at", "observation_date", "as_of_date", "fetched_at")
        or _first_text(attrs, "start_date", "rcept_dt", "period", "year")
    )
    external_name = _first_text(row, "external_name", "entity_name", "product_name")
    external_id = _first_text(row, "external_id", "identifier")
    status = _first_text(attrs, "overall_status", "status", "active", "registration_status")
    if record_type == "fda_product_status_record":
        products = attrs.get("product_names")
        product_text = ", ".join(str(item) for item in products[:5]) if isinstance(products, list) else _first_text(row, "product_name")
        status = f"FDA product status for {product_text or external_id}".strip()
    elif record_type == "vehicle_model_identity_record":
        status = f"NHTSA vehicle model identity: {_first_text(attrs, 'make_name')} {external_name}".strip()
    elif record_type == "institution_reference_record":
        status = f"FDIC institution reference: {external_name or external_id}".strip()
    elif record_type == "clinical_trial_status_record":
        status = f"ClinicalTrials status {status}: {external_name}".strip()
    elif record_type in {"patent_data_access_metadata_record", "research_work_lead_record"}:
        status = f"Technology signal lead: {external_name or external_id}".strip()
    if not observed_at:
        observed_at = _date_from_any(_first_text(row, "as_of_date", "fetched_at")) or "not_disclosed"
    if not status or observed_at == "not_disclosed":
        return None
    return {
        "evidence_ref": _evidence_ref(row),
        "object_type": "VerticalOfficialObject",
        "record_type": record_type,
        "source_family": "public_source_context",
        "source_id": source_id,
        "company_id": ticker,
        "product_name": _first_text(row, "product_name") or external_name,
        "external_id": external_id,
        "event_or_status": status,
        "observed_at": observed_at,
        "claim_scope": "official_object_context_only",
        "context_only": True,
        "exact_value_authority": False,
    }


def _vertical_official_object_from_mapping_candidate(row: Mapping[str, Any]) -> dict[str, Any] | None:
    ticker = _ticker(row)
    source_id = _source_id(row)
    external_id = _first_text(row, "external_id")
    external_name = _first_text(row, "external_name")
    evidence = _dict_value(row.get("evidence"))
    if not ticker or not source_id or not external_id:
        return None
    if source_id == "clinicaltrials_api":
        status = f"ClinicalTrials sponsor-query candidate with {evidence.get('downloaded_study_count', 'unknown')} downloaded studies"
        object_type = "clinicaltrials_sponsor_context"
    elif source_id == "openfda_api":
        status = f"openFDA sponsor-query candidate with {evidence.get('downloaded_record_count', 'unknown')} downloaded records"
        object_type = "openfda_sponsor_context"
    elif source_id == "nhtsa_vpic_api":
        status = f"NHTSA make-query candidate with {evidence.get('downloaded_model_count', 'unknown')} downloaded models"
        object_type = "nhtsa_make_model_context"
    elif source_id == "fdic_bankfind_api":
        status = f"FDIC institution/subsidiary candidate: {external_name}"
        object_type = "fdic_institution_context"
    else:
        return None
    return {
        "evidence_ref": _evidence_ref(row),
        "object_type": "VerticalOfficialObject",
        "record_type": object_type,
        "source_family": "public_source_context",
        "source_id": source_id,
        "company_id": ticker,
        "event_or_status": status,
        "observed_at": _date.today().isoformat(),
        "external_id": external_id,
        "claim_scope": "official_object_context_only",
        "context_only": True,
        "exact_value_authority": False,
    }


def _company_exposures_for_macro_driver(
    driver: Mapping[str, Any],
    *,
    row: Mapping[str, Any],
    target_by_ticker: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    ticker = _ticker(row)
    if ticker:
        return [
            {
                "evidence_ref": f"{driver['evidence_ref']}:exposure:{ticker}",
                "object_type": "CompanyExposureToDriver",
                "source_family": "industry_snapshot",
                "source_id": _source_id(row),
                "company_id": ticker,
                "driver_id": driver.get("driver_id") or driver.get("trade_driver_id") or _stable_id("Driver", [_evidence_ref(row)]),
                "exposure_type": _first_text(row, "exposure_type", "driver_relationship") or "explicit_source_row_context",
                "claim_scope": "company_exposure_bridge_context_only",
            }
        ]
    source_id = _source_id(row)
    exposures: list[dict[str, Any]] = []
    for company in target_by_ticker.values():
        exposure_type = _industry_exposure_type(company, source_id=source_id, driver=driver)
        if not exposure_type:
            continue
        ticker_value = _ticker(company)
        exposures.append(
            {
                "evidence_ref": f"{driver['evidence_ref']}:playbook_exposure:{ticker_value}",
                "object_type": "CompanyExposureToDriver",
                "source_family": "industry_snapshot",
                "source_id": _source_id(row),
                "company_id": ticker_value,
                "driver_id": driver.get("driver_id") or driver.get("trade_driver_id") or _stable_id("Driver", [_evidence_ref(row)]),
                "exposure_type": exposure_type,
                "claim_scope": "company_exposure_bridge_context_only",
                "context_only": True,
                "exact_value_authority": False,
            }
        )
        if len(exposures) >= 25:
            break
    return exposures


def _industry_exposure_type(company: Mapping[str, Any], *, source_id: str, driver: Mapping[str, Any]) -> str:
    text = " ".join(
        _first_text(company, key).lower()
        for key in ("industry_schema", "sector", "category", "industry", "company_name", "company")
    )
    driver_text = json.dumps(driver, ensure_ascii=True).lower()
    if source_id in {"fred_api", "fred_graph_csv", "bls_public_api"} and any(token in text for token in ("bank", "financial", "insurance")):
        return "rate_cycle_or_credit_condition_context"
    if source_id == "eia_open_data" and any(token in text for token in ("energy", "oil", "gas", "utility", "utilities", "power")):
        return "energy_price_or_supply_context"
    if source_id in {"census_data_api", "usitc_dataweb_and_trade"} and any(token in text for token in ("semiconductor", "hardware", "electronics", "auto", "consumer")):
        if "8542" in driver_text or "trade" in driver_text:
            return "trade_or_end_market_context"
    return ""


def _looks_like_debt_text(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ("senior notes", "debt", "debenture", "term loan", "credit facility", "revolving credit")) and (
        "matur" in lowered or " due " in lowered or "%" in lowered
    )


def _debt_instrument_relation_span(text: str) -> str:
    for window in _local_relation_windows(text, max_sentences=5):
        lowered = window.lower()
        if not any(token in lowered for token in ("senior notes", "senior unsecured notes", "debentures", "debt securities")):
            continue
        if "issued" not in lowered or "principal amount" not in lowered:
            continue
        if any(token in lowered for token in ("redemption price", "loss on extinguishment", "repaid the")):
            continue
        if _extract_debt_principal(window) and _extract_coupon(window) and _extract_maturity(window):
            return window
    return ""


def _credit_facility_relation_span(text: str) -> str:
    for window in _local_relation_windows(text, max_sentences=4):
        lowered = window.lower()
        if not any(token in lowered for token in ("credit facility", "revolving credit", "term loan facility", "term loan agreement", "revolver")):
            continue
        if not _extract_facility_size(window) or not _extract_maturity(window):
            continue
        if any(token in lowered for token in ("at least equal to", "commercial paper notes outstanding")) and "term loan" not in lowered:
            continue
        return window
    return ""


def _local_relation_windows(text: str, *, max_sentences: int) -> list[str]:
    cleaned = _normalize_relation_text(text)
    if not cleaned:
        return []
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+(?=(?:[A-Z0-9$]|\d{4}\s+Senior|On\s+))", cleaned)
        if sentence.strip()
    ]
    windows: list[str] = []
    for start in range(len(sentences)):
        for size in range(1, max_sentences + 1):
            end = start + size
            if end > len(sentences):
                break
            window = " ".join(sentences[start:end])
            if len(window) <= 2500:
                windows.append(window)
    if not windows and len(cleaned) <= 2500:
        windows.append(cleaned)
    return windows


def _normalize_relation_text(text: str) -> str:
    cleaned = re.sub(r"\[TABLE_(?:START|END)[^\]]*\]", " ", text)
    cleaned = re.sub(r"\s*\|\s*", " | ", cleaned)
    cleaned = re.sub(r"(?<=\$)\s+(?=\d)", "", cleaned)
    cleaned = re.sub(r"(?<=\d)\s+(?=%|\b(?:million|billion|thousand|bn|mm)\b)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _extract_amount(text: str) -> dict[str, str] | None:
    pattern = re.compile(r"(?i)(\$|usd\s*)?([0-9][0-9,]*(?:\.[0-9]+)?)\s*(billion|million|thousand|bn|mm|m)?")
    for match in pattern.finditer(text):
        if match.end() < len(text) and text[match.end() : match.end() + 1] == "%":
            continue
        raw = match.group(2).replace(",", "")
        if not _is_number(raw):
            continue
        number = float(raw)
        unit_word = (match.group(3) or "").lower()
        has_currency = bool(match.group(1))
        if not has_currency and not unit_word:
            continue
        unit = {
            "billion": "USD billions",
            "bn": "USD billions",
            "million": "USD millions",
            "mm": "USD millions",
            "m": "USD millions",
            "thousand": "USD thousands",
        }.get(unit_word, "USD")
        return {"value": _format_number(number), "unit": unit}
    return None


def _extract_debt_principal(text: str) -> dict[str, str] | None:
    for pattern in (
        r"(?i)issued.{0,260}aggregate principal amount of\s+(?:approximately\s+)?(?:an?\s+)?(?:\$\s*)?[0-9][0-9,]*(?:\.[0-9]+)?\s*(?:billion|million|thousand|bn|mm)?",
        r"(?i)issued.{0,260}with\s+(?:an?\s+)?aggregate principal amount of\s+(?:approximately\s+)?(?:\$\s*)?[0-9][0-9,]*(?:\.[0-9]+)?\s*(?:billion|million|thousand|bn|mm)?",
        r"(?i)issued.{0,120}(?:\$\s*)?[0-9][0-9,]*(?:\.[0-9]+)?\s*(?:billion|million|thousand|bn|mm).{0,120}(?:senior notes|debentures|debt securities)",
    ):
        match = re.search(pattern, text)
        if match:
            amount = _extract_amount(match.group(0))
            if amount:
                return amount
    return None


def _extract_facility_size(text: str) -> dict[str, str] | None:
    amount_pattern = r"(?:\$\s*)?[0-9][0-9,]*(?:\.[0-9]+)?\s*(?:billion|million|thousand|bn|mm)?"
    for pattern in (
        rf"(?i)(?:provides? for|provided for|access to|has\s+an?|maintains\s+an?|commitments?\s+of)\s+(?:approximately\s+)?(?:an?\s+)?{amount_pattern}.{{0,180}}(?:credit facility|credit agreement|term loan|revolver|commitments?)",
        rf"(?i){amount_pattern}.{{0,120}}(?:five-year|364-day|revolving|syndicated|unsecured|delayed draw).{{0,100}}(?:credit facility|credit agreement|term loan|revolver)",
        rf"(?i)(?:credit facility|credit agreement|term loan|revolver).{{0,140}}(?:of|up to|for)\s+(?:approximately\s+)?{amount_pattern}",
    ):
        match = re.search(pattern, text)
        if match:
            lowered = match.group(0).lower()
            if any(token in lowered for token in ("available under", "remained available", "available liquidity", "borrowings outstanding", "outstanding obligations", "amounts were drawn")):
                continue
            amount = _extract_amount(match.group(0))
            if amount:
                return amount
    return None


def _extract_coupon(text: str) -> str:
    for match in re.finditer(r"(?i)([0-9]+(?:\.[0-9]+)?)\s*%", text):
        raw = match.group(1)
        if not _is_number(raw):
            continue
        value = float(raw)
        if 0 <= value <= 30:
            return f"{raw}%"
    return ""


def _extract_maturity(text: str) -> str:
    date_match = re.search(
        r"(?i)(?:due|matur(?:e|ing|ity)?|expir(?:e|es|ing|ation)?)(?:\s+on|\s+in)?[^0-9a-zA-Z]{0,30}((?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+20\d{2}|20\d{2})",
        text,
    )
    if date_match:
        return _date_from_any(date_match.group(1)) or date_match.group(1)
    year_match = re.search(r"(?i)\b(?:due|matur(?:e|ing|ity)?|expir(?:e|es|ing|ation)?)\D{0,30}(20\d{2})\b", text)
    return f"{year_match.group(1)}-01-01" if year_match else ""


def _clip_statement(text: str, *, max_chars: int = 600) -> str:
    cleaned = _normalize_relation_text(text)
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def _extract_security_type(text: str) -> str:
    lowered = text.lower()
    for label in ("common stock", "preferred stock", "ordinary shares", "american depositary shares", "convertible notes", "senior notes", "units"):
        if label in lowered:
            return label
    return ""


def _is_offering_form_or_source(row: Mapping[str, Any]) -> bool:
    form_type = _first_text(row, "form_type", "filing_type", "SUBMISSIONTYPE").upper()
    if form_type in OFFERING_FORMS:
        return True
    source_id = _source_id(row).lower()
    record_type = _first_text(row, "record_type", "source_row_kind", "target_source").lower()
    return "offering" in source_id or "offering" in record_type


def _target_company_rows(inputs: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = _mapping_items(inputs.get("target_companies"))
    if rows:
        return rows
    rows.extend(_mapping_items(inputs.get("universe_rows")))
    inventory = _mapping_items(inputs.get("public_source_inventory_rows"))
    for row in inventory:
        if _source_id(row) == "sec_universe_identity" and _ticker(row):
            rows.append(
                {
                    "ticker": _ticker(row),
                    "company_name": _first_text(row, "company_name", "external_name"),
                    "cik": (_first_text(row, "external_id").replace("CIK", "") or _first_text(_dict_value(row.get("evidence")), "cik")),
                    "sector": _first_text(row, "sector"),
                    "category": _first_text(row, "category"),
                }
            )
    return rows


def load_jsonl(path: str | Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            if isinstance(item, dict):
                rows.append(item)
            if limit and len(rows) >= limit:
                break
    return rows


def load_universe_csv(path: str | Path, *, manifest_path: str | Path | None = None) -> list[dict[str, Any]]:
    cik_by_ticker: dict[str, str] = {}
    if manifest_path and Path(manifest_path).exists():
        for row in load_jsonl(manifest_path):
            ticker = _ticker(row)
            if ticker:
                cik_by_ticker[ticker] = _first_text(row, "cik")
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            item = {str(key): str(value or "") for key, value in row.items()}
            item["ticker"] = str(item.get("ticker") or "").upper()
            item["cik"] = item.get("cik") or cik_by_ticker.get(item["ticker"], "")
            rows.append(item)
    return rows


def _iter_tsv_member(archive: zipfile.ZipFile, member_name: str) -> Iterable[dict[str, str]]:
    with archive.open(member_name, "r") as handle:
        text = (line.decode("utf-8", errors="replace") for line in handle)
        reader = csv.DictReader(text, delimiter="\t")
        for row in reader:
            yield {str(key): str(value or "") for key, value in row.items()}


def _summary(payload: Mapping[str, Any]) -> dict[str, int]:
    capital = _mapping_items(payload.get("capital_ownership_rows"))
    macro = _mapping_items(payload.get("macro_driver_rows"))
    exposure = _mapping_items(payload.get("macro_exposure_rows"))
    vertical = _mapping_items(payload.get("vertical_official_object_rows"))
    gaps = _mapping_items(payload.get("source_gaps"))
    return {
        "capital_ownership_row_count": len(capital),
        "macro_driver_row_count": len(macro),
        "macro_exposure_row_count": len(exposure),
        "vertical_official_object_row_count": len(vertical),
        "source_gap_count": len(gaps),
        "pack_input_row_count": len(capital) + len(macro) + len(exposure) + len(vertical),
    }


def _gap(row: Mapping[str, Any], gap_type: str, reason: str, *, target: str) -> dict[str, Any]:
    return {
        "schema_version": "sec_agent_capital_macro_source_adapter_gap_v0.1",
        "gap_id": _stable_id("CapitalMacroSourceGap", [_evidence_ref(row), gap_type, reason, target]),
        "gap_type": gap_type,
        "target_source": target,
        "reason": reason,
        "ticker": _ticker(row),
        "source_id": _source_id(row),
        "evidence_ref": _evidence_ref(row),
        "treatment_action": "repair_parser_or_expose_gap_do_not_proxy",
    }


def _target_by_company_name(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {_normalize_name(_first_text(row, "company_name", "company", "external_name")): row for row in rows if _normalize_name(_first_text(row, "company_name", "company", "external_name"))}


def _ticker_by_issuer_name(rows: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in rows:
        ticker = _ticker(row)
        for key in ("company_name", "company", "external_name", "legal_name"):
            name = _normalize_name(_first_text(row, key))
            if name and ticker:
                result[name] = ticker
    return result


def _ticker_by_cik(rows: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in rows:
        cik = _normalize_cik(_first_text(row, "cik"))
        ticker = _ticker(row)
        if cik and ticker:
            result[cik] = ticker
    return result


def _source_text(row: Mapping[str, Any]) -> str:
    values = [_first_text(row, key) for key in ("text", "snippet", "summary", "description", "title", "external_name")]
    return " ".join(value for value in values if value).strip()


def _source_id(row: Mapping[str, Any]) -> str:
    return _first_text(row, "source_id", "underlying_source_id", "snapshot_id")


def _source_lineage(row: Mapping[str, Any]) -> dict[str, str]:
    fields = {
        "source_url": _first_text(row, "source_url", "raw_url", "url", "api_route"),
        "local_path": _first_text(row, "local_path", "raw_path", "path", "file_path"),
        "input_path": _first_text(row, "input_path"),
        "accession_number": _first_text(row, "accession_number", "accession", "ACCESSION_NUMBER", "adsh"),
        "filing_date": _date_from_any(_first_text(row, "filing_date", "FILING_DATE", "filed")),
        "report_date": _date_from_any(_first_text(row, "report_date", "reported_date")),
        "period_end": _date_from_any(_first_text(row, "period_end", "source_period_end", "report_period")),
        "retrieved_at": _first_text(row, "retrieved_at", "downloaded_at", "fetched_at"),
    }
    return {key: value for key, value in fields.items() if value}


def _evidence_ref(row: Mapping[str, Any]) -> str:
    return _first_text(row, "evidence_ref", "evidence_id", "row_id", "record_id", "external_id", "chunk_id", "ACCESSION_NUMBER", "adsh") or _stable_id("source-row", [json.dumps(dict(row), ensure_ascii=True, sort_keys=True)[:500]])


def _ticker(row: Mapping[str, Any]) -> str:
    return _first_text(row, "ticker", "company_id", "issuer_id").upper()


def _first_text(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        if key not in row:
            continue
        value = row.get(key)
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            for item in value:
                text = str(item or "").strip()
                if text:
                    return text
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _dict_value(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _mapping_items(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, Mapping)]


def _cap(values: list[dict[str, Any]], *, max_items: int) -> list[dict[str, Any]]:
    return values[: max(0, int(max_items))]


def _normalize_name(value: Any) -> str:
    text = str(value or "").lower().replace("&", " and ")
    text = re.sub(r"\b(class|cl)\s+[a-z]\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    suffixes = {"the", "inc", "incorporated", "corp", "corporation", "co", "company", "ltd", "limited", "plc", "holdings", "holding", "group", "sa", "ag", "nv", "lp", "llc"}
    return " ".join(token for token in text.split() if token not in suffixes)


def _normalize_cik(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits.lstrip("0") if digits else ""


def _is_number(value: Any) -> bool:
    try:
        float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return False
    return True


def _is_observed_value(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if text.lower() in {"not available", "not applicable", "na", "n/a", "null", "none", "."}:
        return False
    return _is_number(text)


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _date_from_yyyymmdd(value: str) -> str:
    text = str(value or "")
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return _date_from_any(text)


def _date_from_any(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text[:10]):
        return text[:10]
    if re.fullmatch(r"\d{8}", text):
        return _date_from_yyyymmdd(text)
    if re.fullmatch(r"\d{4}", text):
        return f"{text}-01-01"
    if re.fullmatch(r"\d{4}-\d{2}", text):
        return f"{text}-01"
    match = re.fullmatch(r"(?i)(\d{1,2})-([A-Z]{3})-(\d{4})", text)
    if match:
        months = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6, "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}
        month = months.get(match.group(2).upper())
        if month:
            return f"{int(match.group(3)):04d}-{month:02d}-{int(match.group(1)):02d}"
    match = re.search(r"(?i)\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+(\d{1,2}),?\s+(20\d{2})\b", text)
    if match:
        months = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12}
        return f"{int(match.group(3)):04d}-{months[match.group(1).lower()]:02d}-{int(match.group(2)):02d}"
    return ""


def _lag_days(report_period: str, filing_date: str) -> str:
    try:
        start = date.fromisoformat(report_period[:10])
        end = date.fromisoformat(filing_date[:10])
    except ValueError:
        return ""
    return str(max(0, (end - start).days))


def _infer_frequency(row: Mapping[str, Any], attrs: Mapping[str, Any]) -> str:
    text = " ".join([_first_text(row, "series_id", "external_id", "api_route"), _first_text(attrs, "period", "route")]).lower()
    if re.search(r"\d{4}-\d{2}-\d{2}", text) or "monthly" in text:
        return "monthly"
    if re.search(r"\d{4}q[1-4]", text) or "quarter" in text:
        return "quarterly"
    if re.search(r"\d{4}$", text):
        return "annual"
    return _first_text(row, "frequency") or "not_disclosed"


def _stable_id(prefix: str, parts: list[str]) -> str:
    raw = json.dumps([prefix, *[str(part or "") for part in parts]], ensure_ascii=True, sort_keys=True)
    return f"{prefix}::{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]}"


_date = date
