from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any, Mapping


CAPITAL_MACRO_PACK_SCHEMA_VERSION = "sec_agent_capital_macro_exposure_pack_v0.1"

OWNERSHIP_CLAIM_SCOPE = "lagged_ownership_context_only"
MACRO_DRIVER_CLAIM_SCOPE = "macro_or_industry_context_only"
COMPANY_EXPOSURE_CLAIM_SCOPE = "company_exposure_bridge_context_only"
VERTICAL_OBJECT_CLAIM_SCOPE = "official_object_context_only"

OWNERSHIP_FORBIDDEN_CLAIMS = [
    "realtime_flow",
    "purchase_today",
    "complete_investor_position",
    "short_or_derivative_position",
]
MACRO_FORBIDDEN_CLAIMS = [
    "company_reported_financial_fact",
    "company_sales",
    "company_margin",
    "company_revenue",
    "commercial_success",
]


def build_capital_macro_pack(state: Mapping[str, Any], *, max_items: int = 24) -> dict[str, Any]:
    rows = _candidate_rows(state)
    capital_structures: list[dict[str, Any]] = []
    debt_instruments: list[dict[str, Any]] = []
    credit_facilities: list[dict[str, Any]] = []
    equity_offerings: list[dict[str, Any]] = []
    ownership_positions: list[dict[str, Any]] = []
    insider_transactions: list[dict[str, Any]] = []
    macro_drivers: list[dict[str, Any]] = []
    trade_drivers: list[dict[str, Any]] = []
    industry_drivers: list[dict[str, Any]] = []
    company_exposure_edges: list[dict[str, Any]] = []
    vertical_official_objects: list[dict[str, Any]] = []
    rejected_objects: list[dict[str, Any]] = []

    for index, row in enumerate(rows, start=1):
        ref = _evidence_ref(row, index)
        if _is_capital_structure_candidate(row):
            item, rejection = _capital_structure_from_row(row, ref=ref)
            if rejection:
                rejected_objects.append(rejection)
            elif item:
                capital_structures.append(item)

        if _is_debt_instrument_candidate(row):
            item, rejection = _debt_instrument_from_row(row, ref=ref)
            if rejection:
                rejected_objects.append(rejection)
            elif item:
                debt_instruments.append(item)

        if _is_credit_facility_candidate(row):
            item, rejection = _credit_facility_from_row(row, ref=ref)
            if rejection:
                rejected_objects.append(rejection)
            elif item:
                credit_facilities.append(item)

        if _is_equity_offering_candidate(row):
            item, rejection = _equity_offering_from_row(row, ref=ref)
            if rejection:
                rejected_objects.append(rejection)
            elif item:
                equity_offerings.append(item)

        if _is_ownership_position_candidate(row):
            item, rejection = _ownership_position_from_row(row, ref=ref)
            if rejection:
                rejected_objects.append(rejection)
            elif item:
                ownership_positions.append(item)

        if _is_insider_transaction_candidate(row):
            item, rejection = _insider_transaction_from_row(row, ref=ref)
            if rejection:
                rejected_objects.append(rejection)
            elif item:
                insider_transactions.append(item)

        if _is_macro_driver_candidate(row):
            item, rejection = _macro_driver_from_row(row, ref=ref)
            if rejection:
                rejected_objects.append(rejection)
            elif item:
                macro_drivers.append(item)
                if _first_text(row, "ticker", "company_id", "company"):
                    rejected_objects.append(
                        _rejection(
                            row,
                            ref=ref,
                            object_type="CompanyExposureToDriver",
                            reason="macro_driver_requires_company_exposure_bridge",
                            missing_fields=["exposure_type", "evidence_ref"],
                        )
                    )

        if _is_trade_driver_candidate(row):
            item, rejection = _trade_driver_from_row(row, ref=ref)
            if rejection:
                rejected_objects.append(rejection)
            elif item:
                trade_drivers.append(item)

        if _is_industry_driver_candidate(row):
            item, rejection = _industry_driver_from_row(row, ref=ref)
            if rejection:
                rejected_objects.append(rejection)
            elif item:
                industry_drivers.append(item)

        if _is_company_exposure_candidate(row):
            item, rejection = _company_exposure_from_row(row, ref=ref)
            if rejection:
                rejected_objects.append(rejection)
            elif item:
                company_exposure_edges.append(item)

        if _is_vertical_official_object_candidate(row):
            item, rejection = _vertical_official_object_from_row(row, ref=ref)
            if rejection:
                rejected_objects.append(rejection)
            elif item:
                vertical_official_objects.append(item)

    pack = {
        "schema_version": CAPITAL_MACRO_PACK_SCHEMA_VERSION,
        "pack_id": _stable_id("CapitalMacroExposurePack", [_state_run_id(state), str(len(rows)), _refs_digest(rows)]),
        "status": "pass",
        "policy": "capital_ownership_and_macro_edges_require_parser_gates_no_proxy_promotion",
        "boundary_policy": {
            "ownership_claim_scope": OWNERSHIP_CLAIM_SCOPE,
            "ownership_forbidden_claims": OWNERSHIP_FORBIDDEN_CLAIMS,
            "macro_driver_claim_scope": MACRO_DRIVER_CLAIM_SCOPE,
            "company_exposure_claim_scope": COMPANY_EXPOSURE_CLAIM_SCOPE,
            "macro_forbidden_claims": MACRO_FORBIDDEN_CLAIMS,
            "thirteen_f_policy": "lagged_long_position_context_not_realtime_flow",
            "macro_policy": "macro_or_industry_context_requires_company_exposure_bridge_for_company_thesis",
        },
        "capital_structures": _cap(capital_structures, max_items=max_items),
        "debt_instruments": _cap(debt_instruments, max_items=max_items),
        "credit_facilities": _cap(credit_facilities, max_items=max_items),
        "equity_offerings": _cap(equity_offerings, max_items=max_items),
        "ownership_positions": _cap(ownership_positions, max_items=max_items),
        "insider_transactions": _cap(insider_transactions, max_items=max_items),
        "macro_drivers": _cap(macro_drivers, max_items=max_items),
        "trade_drivers": _cap(trade_drivers, max_items=max_items),
        "industry_drivers": _cap(industry_drivers, max_items=max_items),
        "company_exposure_edges": _cap(company_exposure_edges, max_items=max_items),
        "vertical_official_objects": _cap(vertical_official_objects, max_items=max_items),
        "rejected_objects": _cap(rejected_objects, max_items=max_items),
    }
    pack["summary"] = _summary(pack, input_row_count=len(rows))
    validation = validate_capital_macro_pack(pack)
    pack["validation"] = validation
    pack["status"] = validation["status"]
    return pack


def validate_capital_macro_pack(payload: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if str(payload.get("schema_version") or "") != CAPITAL_MACRO_PACK_SCHEMA_VERSION:
        errors.append({"type": "invalid_schema_version", "schema_version": str(payload.get("schema_version") or "")})

    for index, item in enumerate(_mapping_items(payload.get("debt_instruments")), start=1):
        missing = _missing_fields(item, ["debt_instrument_id", "company_id", "principal", "currency", "maturity_date", "coupon", "interest_rate_type", "source_id"])
        if missing:
            errors.append({"type": "debt_instrument_required_fields_missing", "index": index, "missing_fields": missing})

    for index, item in enumerate(_mapping_items(payload.get("ownership_positions")), start=1):
        missing = _missing_fields(
            item,
            [
                "ownership_position_id",
                "investor_id",
                "company_id",
                "shares",
                "value",
                "filing_date",
                "report_period",
                "form_type",
                "lag_policy",
                "lag_days",
                "not_realtime_flag",
                "source_id",
            ],
        )
        if missing:
            errors.append({"type": "ownership_position_required_fields_missing", "index": index, "missing_fields": missing})
        if item.get("not_realtime_flag") is not True:
            errors.append({"type": "ownership_position_not_realtime_flag_required", "index": index})
        if _contains_scope(item, OWNERSHIP_FORBIDDEN_CLAIMS):
            errors.append({"type": "ownership_position_forbidden_claim_scope", "index": index})

    for index, item in enumerate(_mapping_items(payload.get("macro_drivers")), start=1):
        missing = _missing_fields(item, ["driver_id", "series_id", "variable_name", "value", "date", "frequency", "source_id"])
        if missing:
            errors.append({"type": "macro_driver_required_fields_missing", "index": index, "missing_fields": missing})
        if _contains_scope(item, MACRO_FORBIDDEN_CLAIMS):
            errors.append({"type": "macro_driver_forbidden_claim_scope", "index": index})

    for index, item in enumerate(_mapping_items(payload.get("company_exposure_edges")), start=1):
        missing = _missing_fields(item, ["exposure_id", "company_id", "driver_id", "exposure_type", "evidence_ref", "source_id", "claim_scope"])
        if missing:
            errors.append({"type": "company_exposure_required_fields_missing", "index": index, "missing_fields": missing})
        if str(item.get("claim_scope") or "") != COMPANY_EXPOSURE_CLAIM_SCOPE:
            errors.append({"type": "company_exposure_claim_scope_invalid", "index": index, "claim_scope": str(item.get("claim_scope") or "")})

    for index, item in enumerate(_mapping_items(payload.get("vertical_official_objects")), start=1):
        missing = _missing_fields(item, ["object_id", "company_id", "object_type", "event_or_status", "observed_at", "source_id", "claim_scope"])
        if missing:
            errors.append({"type": "vertical_official_object_required_fields_missing", "index": index, "missing_fields": missing})
        if _contains_scope(item, MACRO_FORBIDDEN_CLAIMS):
            errors.append({"type": "vertical_official_object_forbidden_claim_scope", "index": index})

    return {
        "schema_version": "sec_agent_capital_macro_exposure_pack_validation_v0.1",
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "warnings": warnings,
    }


def compact_capital_macro_pack(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": str(payload.get("schema_version") or CAPITAL_MACRO_PACK_SCHEMA_VERSION),
        "pack_id": str(payload.get("pack_id") or ""),
        "status": str(payload.get("status") or ""),
        "summary": dict(payload.get("summary") or {}) if isinstance(payload.get("summary"), Mapping) else {},
        "boundary_policy": dict(payload.get("boundary_policy") or {}) if isinstance(payload.get("boundary_policy"), Mapping) else {},
    }


def _candidate_rows(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in (
        "capital_ownership_rows",
        "ownership_rows",
        "macro_exposure_rows",
        "macro_driver_rows",
        "vertical_official_object_rows",
    ):
        rows.extend(_mapping_items(state.get(key)))
    rows.extend(row for row in _mapping_items(state.get("runtime_ledger_rows")) if _is_capital_metric(row))
    rows.extend(row for row in _mapping_items(state.get("industry_snapshot_rows")) if _is_macro_or_industry_row(row))
    rows.extend(row for row in _mapping_items(state.get("public_source_context_rows")) if _is_macro_or_vertical_public_row(row))
    rows.extend(
        row
        for row in _mapping_items(state.get("context_rows"))
        if _is_capital_metric(row)
        or _is_macro_or_industry_row(row)
        or _is_ownership_position_candidate(row)
        or _is_debt_instrument_candidate(row)
        or _is_vertical_official_object_candidate(row)
    )
    return rows


def _capital_structure_from_row(row: Mapping[str, Any], *, ref: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    company_id = _company_id(row)
    period = _first_text(row, "period", "period_role", "fiscal_year", "source_fiscal_year")
    cash = _first_scalar(row, "cash", "cash_and_equivalents")
    debt = _first_scalar(row, "debt", "total_debt")
    net_debt = _first_scalar(row, "net_debt")
    missing = [field for field, value in {"company_id": company_id, "cash": cash, "debt": debt, "net_debt": net_debt, "period": period}.items() if value == ""]
    if missing:
        return None, _rejection(row, ref=ref, object_type="CapitalStructure", reason="capital_structure_required_fields_missing", missing_fields=missing)
    return (
        {
            "capital_structure_id": _first_text(row, "capital_structure_id") or _stable_id("CapitalStructure", [company_id, period, ref]),
            "company_id": company_id,
            "cash": cash,
            "debt": debt,
            "net_debt": net_debt,
            "period": period,
            "source_id": _source_id(row, ref=ref),
            "source_family": _source_family(row),
            "evidence_refs": [ref],
            "claim_scope": "company_disclosed_capital_structure_fact",
        },
        None,
    )


def _debt_instrument_from_row(row: Mapping[str, Any], *, ref: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    company_id = _company_id(row)
    principal = _first_scalar(row, "principal", "amount", "debt_amount", "value")
    maturity = _first_text(row, "maturity_date", "maturity")
    coupon = _first_text(row, "coupon", "interest_rate", "rate")
    rate_type = _first_text(row, "interest_rate_type", "rate_type") or "not_disclosed"
    currency = _first_text(row, "currency") or "not_disclosed"
    missing = [field for field, value in {"company_id": company_id, "principal": principal, "maturity_date": maturity, "coupon": coupon}.items() if value == ""]
    if missing:
        return None, _rejection(row, ref=ref, object_type="DebtInstrument", reason="debt_instrument_required_fields_missing", missing_fields=missing)
    return (
        {
            "debt_instrument_id": _first_text(row, "debt_instrument_id") or _stable_id("DebtInstrument", [company_id, principal, maturity, coupon, ref]),
            "company_id": company_id,
            "principal": principal,
            "currency": currency,
            "maturity_date": maturity,
            "coupon": coupon,
            "interest_rate_type": rate_type,
            "source_id": _source_id(row, ref=ref),
            "source_family": _source_family(row),
            "evidence_refs": [ref],
            "claim_scope": "company_disclosed_debt_context",
        },
        None,
    )


def _credit_facility_from_row(row: Mapping[str, Any], *, ref: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    company_id = _company_id(row)
    facility_size = _first_scalar(row, "facility_size", "commitment", "amount", "value")
    available = _first_scalar(row, "available_liquidity", "availability", "undrawn_amount")
    maturity = _first_text(row, "maturity_date", "maturity")
    missing = [field for field, value in {"company_id": company_id, "facility_size": facility_size, "maturity_date": maturity}.items() if value == ""]
    if missing:
        return None, _rejection(row, ref=ref, object_type="CreditFacility", reason="credit_facility_required_fields_missing", missing_fields=missing)
    return (
        {
            "credit_facility_id": _first_text(row, "credit_facility_id") or _stable_id("CreditFacility", [company_id, facility_size, maturity, ref]),
            "company_id": company_id,
            "facility_size": facility_size,
            "available_liquidity": available or "not_disclosed",
            "maturity_date": maturity,
            "covenant_flag": _first_text(row, "covenant_flag", "covenant_status") or "not_disclosed",
            "source_id": _source_id(row, ref=ref),
            "source_family": _source_family(row),
            "evidence_refs": [ref],
            "claim_scope": "company_disclosed_credit_facility_context",
        },
        None,
    )


def _equity_offering_from_row(row: Mapping[str, Any], *, ref: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    company_id = _company_id(row)
    form_type = _first_text(row, "form_type", "filing_type")
    filing_date = _first_text(row, "filing_date", "accepted_date", "date")
    amount = _first_scalar(row, "amount", "offering_amount", "value")
    security_type = _first_text(row, "security_type", "security")
    missing = [field for field, value in {"company_id": company_id, "form_type": form_type, "filing_date": filing_date, "amount": amount, "security_type": security_type}.items() if value == ""]
    if missing:
        return None, _rejection(row, ref=ref, object_type="EquityOffering", reason="equity_offering_required_fields_missing", missing_fields=missing)
    return (
        {
            "equity_offering_id": _first_text(row, "equity_offering_id") or _stable_id("EquityOffering", [company_id, form_type, filing_date, amount, ref]),
            "company_id": company_id,
            "form_type": form_type,
            "filing_date": filing_date,
            "amount": amount,
            "security_type": security_type,
            "source_id": _source_id(row, ref=ref),
            "source_family": _source_family(row),
            "evidence_refs": [ref],
            "claim_scope": "public_offering_context",
        },
        None,
    )


def _ownership_position_from_row(row: Mapping[str, Any], *, ref: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if _contains_scope(row, OWNERSHIP_FORBIDDEN_CLAIMS) or bool(row.get("exact_value_authority")) and str(row.get("claim_scope") or "") == "realtime_flow":
        return None, _rejection(row, ref=ref, object_type="OwnershipPosition", reason="ownership_realtime_flow_promotion_forbidden")
    investor_id = _first_text(row, "investor_id", "manager_cik", "manager_name", "owner_name")
    company_id = _company_id(row)
    shares = _first_scalar(row, "shares", "ssh_prnamt")
    value = _first_scalar(row, "value", "market_value", "put_call_value")
    filing_date = _first_text(row, "filing_date", "accepted_date")
    report_period = _first_text(row, "report_period", "period_of_report", "period")
    form_type = _first_text(row, "form_type", "filing_type") or "13F"
    lag_days = _first_scalar(row, "lag_days") or _lag_days(report_period, filing_date)
    not_realtime = row.get("not_realtime_flag")
    if not_realtime is None:
        not_realtime = True if form_type.upper() in {"13F", "13D", "13G", "DEF 14A", "PROXY"} else None
    missing = [
        field
        for field, value in {
            "investor_id": investor_id,
            "company_id": company_id,
            "shares": shares,
            "value": value,
            "filing_date": filing_date,
            "report_period": report_period,
            "lag_days": lag_days,
        }.items()
        if value == ""
    ]
    if missing or not_realtime is not True:
        if not_realtime is not True:
            missing.append("not_realtime_flag")
        return None, _rejection(row, ref=ref, object_type="OwnershipPosition", reason="ownership_lag_gate_failed", missing_fields=missing)
    return (
        {
            "ownership_position_id": _first_text(row, "ownership_position_id") or _stable_id("OwnershipPosition", [investor_id, company_id, report_period, filing_date, ref]),
            "investor_id": investor_id,
            "company_id": company_id,
            "shares": shares,
            "value": value,
            "filing_date": filing_date,
            "report_period": report_period,
            "form_type": form_type,
            "lag_policy": _first_text(row, "lag_policy") or "lagged_public_ownership_filing_not_realtime_flow",
            "lag_days": lag_days,
            "not_realtime_flag": True,
            "source_id": _source_id(row, ref=ref),
            "source_family": _source_family(row),
            "evidence_refs": [ref],
            "claim_scope": OWNERSHIP_CLAIM_SCOPE,
            "forbidden_claims": OWNERSHIP_FORBIDDEN_CLAIMS,
        },
        None,
    )


def _insider_transaction_from_row(row: Mapping[str, Any], *, ref: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    insider_id = _first_text(row, "insider_id", "insider_name", "owner_name")
    company_id = _company_id(row)
    transaction_type = _first_text(row, "transaction_type", "transaction_code")
    transaction_date = _first_text(row, "transaction_date", "date")
    shares = _first_scalar(row, "shares", "transaction_shares")
    price = _first_scalar(row, "price", "transaction_price")
    form_type = _first_text(row, "form_type", "filing_type")
    missing = [field for field, value in {"insider_id": insider_id, "company_id": company_id, "transaction_type": transaction_type, "transaction_date": transaction_date, "shares": shares, "price": price, "form_type": form_type}.items() if value == ""]
    if missing:
        return None, _rejection(row, ref=ref, object_type="InsiderTransaction", reason="insider_transaction_required_fields_missing", missing_fields=missing)
    return (
        {
            "insider_transaction_id": _first_text(row, "insider_transaction_id") or _stable_id("InsiderTransaction", [insider_id, company_id, transaction_date, transaction_type, ref]),
            "insider_id": insider_id,
            "company_id": company_id,
            "transaction_type": transaction_type,
            "transaction_date": transaction_date,
            "shares": shares,
            "price": price,
            "form_type": form_type,
            "source_id": _source_id(row, ref=ref),
            "source_family": _source_family(row),
            "evidence_refs": [ref],
            "claim_scope": "public_insider_filing_context",
        },
        None,
    )


def _macro_driver_from_row(row: Mapping[str, Any], *, ref: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if _contains_scope(row, MACRO_FORBIDDEN_CLAIMS):
        return None, _rejection(row, ref=ref, object_type="MacroDriver", reason="macro_driver_company_fact_promotion_forbidden")
    series_id = _first_text(row, "series_id", "metric_name", "variable_name")
    variable = _first_text(row, "variable_name", "metric_name", "metric")
    value = _first_scalar(row, "value", "numeric_value")
    observed_date = _first_text(row, "date", "observation_date", "as_of_date", "period")
    frequency = _first_text(row, "frequency") or "not_disclosed"
    missing = [field for field, value_item in {"series_id": series_id, "variable_name": variable, "value": value, "date": observed_date}.items() if value_item == ""]
    if missing:
        return None, _rejection(row, ref=ref, object_type="MacroDriver", reason="macro_driver_required_fields_missing", missing_fields=missing)
    return (
        {
            "driver_id": _first_text(row, "driver_id") or _stable_id("MacroDriver", [series_id, variable, observed_date, ref]),
            "series_id": series_id,
            "variable_name": variable,
            "value": value,
            "date": observed_date,
            "frequency": frequency,
            "source_id": _source_id(row, ref=ref),
            "source_family": _source_family(row) or "industry_snapshot",
            "evidence_refs": [ref],
            "claim_scope": MACRO_DRIVER_CLAIM_SCOPE,
            "context_only": True,
            "exact_value_authority": False,
            "forbidden_claims": MACRO_FORBIDDEN_CLAIMS,
        },
        None,
    )


def _trade_driver_from_row(row: Mapping[str, Any], *, ref: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    series_id = _first_text(row, "series_id", "trade_series_id")
    product_code = _first_text(row, "product_or_code", "commodity_code", "hs_code")
    country = _first_text(row, "country_or_region", "country", "region")
    value = _first_scalar(row, "value", "trade_value")
    observed_date = _first_text(row, "date", "observation_date", "period")
    missing = [field for field, value_item in {"series_id": series_id, "product_or_code": product_code, "country_or_region": country, "value": value, "date": observed_date}.items() if value_item == ""]
    if missing:
        return None, _rejection(row, ref=ref, object_type="TradeDriver", reason="trade_driver_required_fields_missing", missing_fields=missing)
    return (
        {
            "trade_driver_id": _first_text(row, "trade_driver_id") or _stable_id("TradeDriver", [series_id, product_code, country, observed_date, ref]),
            "series_id": series_id,
            "product_or_code": product_code,
            "country_or_region": country,
            "value": value,
            "date": observed_date,
            "source_id": _source_id(row, ref=ref),
            "source_family": _source_family(row),
            "evidence_refs": [ref],
            "claim_scope": "trade_context_only",
            "context_only": True,
            "exact_value_authority": False,
        },
        None,
    )


def _industry_driver_from_row(row: Mapping[str, Any], *, ref: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    industry_schema = _first_text(row, "industry_schema", "industry")
    driver_name = _first_text(row, "driver_name", "metric_name", "metric")
    value = _first_scalar(row, "value", "numeric_value")
    observed_date = _first_text(row, "date", "observation_date", "period")
    missing = [field for field, value_item in {"industry_schema": industry_schema, "driver_name": driver_name, "value": value, "date": observed_date}.items() if value_item == ""]
    if missing:
        return None, _rejection(row, ref=ref, object_type="IndustryDriver", reason="industry_driver_required_fields_missing", missing_fields=missing)
    return (
        {
            "industry_driver_id": _first_text(row, "industry_driver_id") or _stable_id("IndustryDriver", [industry_schema, driver_name, observed_date, ref]),
            "industry_schema": industry_schema,
            "driver_name": driver_name,
            "value": value,
            "date": observed_date,
            "source_id": _source_id(row, ref=ref),
            "source_family": _source_family(row),
            "evidence_refs": [ref],
            "claim_scope": "industry_context_only",
            "context_only": True,
            "exact_value_authority": False,
        },
        None,
    )


def _company_exposure_from_row(row: Mapping[str, Any], *, ref: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    company_id = _company_id(row)
    driver_id = _first_text(row, "driver_id")
    exposure_type = _first_text(row, "exposure_type", "driver_relationship", "mechanism")
    evidence_ref = _first_text(row, "evidence_ref") or ref
    missing = [field for field, value in {"company_id": company_id, "driver_id": driver_id, "exposure_type": exposure_type, "evidence_ref": evidence_ref}.items() if value == ""]
    if missing:
        return None, _rejection(row, ref=ref, object_type="CompanyExposureToDriver", reason="company_exposure_required_fields_missing", missing_fields=missing)
    return (
        {
            "exposure_id": _first_text(row, "exposure_id") or _stable_id("CompanyExposureToDriver", [company_id, driver_id, exposure_type, evidence_ref]),
            "company_id": company_id,
            "driver_id": driver_id,
            "exposure_type": exposure_type,
            "evidence_ref": evidence_ref,
            "source_id": _source_id(row, ref=ref),
            "source_family": _source_family(row),
            "claim_scope": COMPANY_EXPOSURE_CLAIM_SCOPE,
            "evidence_refs": [evidence_ref],
            "context_only": True,
            "exact_value_authority": False,
        },
        None,
    )


def _vertical_official_object_from_row(row: Mapping[str, Any], *, ref: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if _contains_scope(row, MACRO_FORBIDDEN_CLAIMS):
        return None, _rejection(row, ref=ref, object_type="VerticalOfficialObject", reason="vertical_object_company_sales_promotion_forbidden")
    company_id = _company_id(row)
    object_type = _first_text(row, "object_type", "record_type", "source_class") or "official_vertical_object"
    status = _first_text(row, "event_or_status", "status", "regulatory_status", "summary", "description")
    observed_at = _first_text(row, "observed_at", "as_of_date", "date", "source_date")
    missing = [field for field, value in {"company_id": company_id, "object_type": object_type, "event_or_status": status, "observed_at": observed_at}.items() if value == ""]
    if missing:
        return None, _rejection(row, ref=ref, object_type="VerticalOfficialObject", reason="vertical_official_object_required_fields_missing", missing_fields=missing)
    return (
        {
            "object_id": _first_text(row, "object_id") or _stable_id("VerticalOfficialObject", [company_id, object_type, observed_at, ref]),
            "company_id": company_id,
            "object_type": object_type,
            "event_or_status": _truncate(status, 300),
            "observed_at": observed_at,
            "source_id": _source_id(row, ref=ref),
            "source_family": _source_family(row),
            "evidence_refs": [ref],
            "claim_scope": VERTICAL_OBJECT_CLAIM_SCOPE,
            "context_only": True,
            "exact_value_authority": False,
            "forbidden_claims": MACRO_FORBIDDEN_CLAIMS,
        },
        None,
    )


def _rejection(row: Mapping[str, Any], *, ref: str, object_type: str, reason: str, missing_fields: list[str] | None = None) -> dict[str, Any]:
    return {
        "object_type": object_type,
        "evidence_ref": ref,
        "reason": reason,
        "missing_fields": list(missing_fields or []),
        "source_family": _source_family(row),
        "claim_scope": _first_text(row, "claim_scope", "source_claim_scope"),
    }


def _summary(pack: Mapping[str, Any], *, input_row_count: int) -> dict[str, int]:
    return {
        "input_row_count": input_row_count,
        "capital_structure_count": len(pack.get("capital_structures") or []),
        "debt_instrument_count": len(pack.get("debt_instruments") or []),
        "credit_facility_count": len(pack.get("credit_facilities") or []),
        "equity_offering_count": len(pack.get("equity_offerings") or []),
        "ownership_position_count": len(pack.get("ownership_positions") or []),
        "insider_transaction_count": len(pack.get("insider_transactions") or []),
        "macro_driver_count": len(pack.get("macro_drivers") or []),
        "trade_driver_count": len(pack.get("trade_drivers") or []),
        "industry_driver_count": len(pack.get("industry_drivers") or []),
        "company_exposure_edge_count": len(pack.get("company_exposure_edges") or []),
        "vertical_official_object_count": len(pack.get("vertical_official_objects") or []),
        "rejected_object_count": len(pack.get("rejected_objects") or []),
    }


def _is_capital_structure_candidate(row: Mapping[str, Any]) -> bool:
    return _row_type(row) == "capitalstructure" or all(_first_scalar(row, key) != "" for key in ("cash", "debt", "net_debt"))


def _is_debt_instrument_candidate(row: Mapping[str, Any]) -> bool:
    text = _joined_text(row)
    return _row_type(row) == "debtinstrument" or ("debt" in text and ("maturity" in text or "coupon" in text))


def _is_credit_facility_candidate(row: Mapping[str, Any]) -> bool:
    text = _joined_text(row)
    return _row_type(row) == "creditfacility" or "credit facility" in text or "revolver" in text


def _is_equity_offering_candidate(row: Mapping[str, Any]) -> bool:
    form = _first_text(row, "form_type", "filing_type").upper()
    return _row_type(row) == "equityoffering" or form in {"S-1", "S-3", "424B", "424B5", "F-1", "F-3"} or "offering" in _joined_text(row)


def _is_ownership_position_candidate(row: Mapping[str, Any]) -> bool:
    form = _first_text(row, "form_type", "filing_type").upper()
    return _row_type(row) == "ownershipposition" or form in {"13F", "13F-HR", "13D", "13G", "DEF 14A", "PROXY"} or bool(_first_text(row, "manager_cik", "investor_id", "owner_name"))


def _is_insider_transaction_candidate(row: Mapping[str, Any]) -> bool:
    form = _first_text(row, "form_type", "filing_type").upper()
    return _row_type(row) == "insidertransaction" or form in {"3", "4", "5", "FORM 3", "FORM 4", "FORM 5"}


def _is_macro_driver_candidate(row: Mapping[str, Any]) -> bool:
    if _row_type(row) == "macrodriver":
        return True
    return _source_family(row) == "industry_snapshot" and (
        _first_text(row, "record_type") == "macro_time_series_observation"
        or bool(_first_text(row, "series_id"))
        or "macro" in _first_text(row, "claim_scope", "source_claim_scope")
    )


def _is_trade_driver_candidate(row: Mapping[str, Any]) -> bool:
    return _row_type(row) == "tradedriver" or bool(_first_text(row, "trade_series_id", "hs_code", "commodity_code"))


def _is_industry_driver_candidate(row: Mapping[str, Any]) -> bool:
    return _row_type(row) == "industrydriver" or (bool(_first_text(row, "industry_schema")) and bool(_first_text(row, "driver_name")))


def _is_company_exposure_candidate(row: Mapping[str, Any]) -> bool:
    return _row_type(row) == "companyexposuretodriver" or bool(_first_text(row, "exposure_id", "exposure_type"))


def _is_vertical_official_object_candidate(row: Mapping[str, Any]) -> bool:
    text = _joined_text(row)
    if _row_type(row) == "verticalofficialobject":
        return True
    return _source_family(row) == "public_source_context" and any(token in text for token in ("openfda", "clinical", "nhtsa", "patent", "regulatory", "recall"))


def _is_capital_metric(row: Mapping[str, Any]) -> bool:
    text = _joined_text(row)
    return any(token in text for token in ("total_debt", "net_debt", "cash_and_equivalents", "credit facility", "maturity", "coupon", "offering"))


def _is_macro_or_industry_row(row: Mapping[str, Any]) -> bool:
    text = _joined_text(row)
    return _source_family(row) == "industry_snapshot" or any(token in text for token in ("macro", "fred", "eia", "census", "bea", "bls", "interest rate", "oil price"))


def _is_macro_or_vertical_public_row(row: Mapping[str, Any]) -> bool:
    text = _joined_text(row)
    return any(token in text for token in ("macro_industry_indicator", "macro_time_series", "official_product_status", "openfda", "clinical", "nhtsa", "patent"))


def _company_id(row: Mapping[str, Any]) -> str:
    return _first_text(row, "company_id", "issuer_id", "cik", "ticker", "company")


def _source_id(row: Mapping[str, Any], *, ref: str) -> str:
    return _first_text(row, "source_id", "underlying_source_id", "snapshot_id", "url", "filing_url") or ref


def _source_family(row: Mapping[str, Any]) -> str:
    return _first_text(row, "source_family", "runtime_source_family", "source_tier")


def _evidence_ref(row: Mapping[str, Any], index: int) -> str:
    return _first_text(row, "evidence_ref", "evidence_id", "metric_id", "fact_id", "row_id", "source_id", "id") or f"capital_macro_pack_row_{index}"


def _row_type(row: Mapping[str, Any]) -> str:
    return _first_text(row, "object_type", "row_type", "record_type", "node_type", "edge_type").replace("_", "").replace("-", "").lower()


def _lag_days(report_period: str, filing_date: str) -> str:
    try:
        start = date.fromisoformat(str(report_period)[:10])
        end = date.fromisoformat(str(filing_date)[:10])
    except ValueError:
        return ""
    return str(max(0, (end - start).days))


def _missing_fields(item: Mapping[str, Any], fields: list[str]) -> list[str]:
    return [field for field in fields if _empty(item.get(field))]


def _contains_scope(item: Mapping[str, Any], needles: list[str]) -> bool:
    text = " ".join(
        [
            _first_text(item, "claim_scope", "source_claim_scope", "claim_type", "metric", "metric_name", "summary"),
            " ".join(_strings(item.get("allowed_claims"))),
            " ".join(_strings(item.get("claim_types"))),
        ]
    ).lower()
    return any(str(needle or "").lower() in text for needle in needles)


def _joined_text(row: Mapping[str, Any]) -> str:
    return " ".join(
        str(row.get(key) or "").lower()
        for key in (
            "object_type",
            "row_type",
            "record_type",
            "source_family",
            "source_id",
            "form_type",
            "metric",
            "metric_name",
            "claim_scope",
            "source_claim_scope",
            "summary",
            "description",
        )
    )


def _cap(values: list[dict[str, Any]], *, max_items: int) -> list[dict[str, Any]]:
    return values[: max(0, int(max_items or 0))]


def _mapping_items(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, Mapping)]


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


def _first_scalar(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        if key not in row:
            continue
        value = row.get(key)
        if value is None or isinstance(value, (list, tuple, set, dict)):
            continue
        text = str(value).strip()
        if text or value == 0:
            return text
    return ""


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        raw = [str(item or "").strip() for item in value]
    else:
        raw = [str(value or "").strip()]
    result: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _truncate(text: str, limit: int) -> str:
    value = str(text or "").strip()
    return value if len(value) <= limit else value[: max(0, limit - 3)].rstrip() + "..."


def _stable_id(prefix: str, parts: list[str]) -> str:
    raw = json.dumps([prefix, *[str(part or "") for part in parts]], ensure_ascii=True, sort_keys=True)
    return f"{prefix}::{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]}"


def _refs_digest(rows: list[Mapping[str, Any]]) -> str:
    refs = [_evidence_ref(row, index) for index, row in enumerate(rows, start=1)]
    return hashlib.sha1(json.dumps(refs, ensure_ascii=True).encode("utf-8")).hexdigest()[:16]


def _state_run_id(state: Mapping[str, Any]) -> str:
    return str(state.get("run_id") or state.get("trace_id") or "runtime_state")
