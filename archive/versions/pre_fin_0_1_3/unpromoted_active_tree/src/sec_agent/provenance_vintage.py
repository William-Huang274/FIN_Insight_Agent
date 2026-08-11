from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path, PurePath
from typing import Any, Mapping


RAW_SOURCE_PROVENANCE_STORE_SCHEMA_VERSION = "sec_agent_raw_source_provenance_store_v0.1"
ASOF_VINTAGE_LAYER_SCHEMA_VERSION = "sec_agent_asof_vintage_layer_v0.1"

EVIDENCE_ROW_CHANNELS = (
    "runtime_ledger_rows",
    "context_rows",
    "market_snapshot_rows",
    "industry_snapshot_rows",
    "product_evidence_rows",
    "public_source_context_rows",
)
CAPITAL_MACRO_ADAPTER_CHANNELS = (
    "capital_ownership_rows",
    "macro_driver_rows",
    "macro_exposure_rows",
    "vertical_official_object_rows",
    "source_gaps",
)
CAPITAL_MACRO_PACK_CHANNELS = (
    "capital_structures",
    "debt_instruments",
    "credit_facilities",
    "equity_offerings",
    "ownership_positions",
    "insider_transactions",
    "macro_drivers",
    "trade_drivers",
    "industry_drivers",
    "company_exposure_edges",
    "vertical_official_objects",
    "rejected_objects",
)


def build_raw_source_provenance_store(state: Mapping[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for channel, row in _iter_state_rows(state):
        rows.append(_provenance_record(row, channel=channel, state=state))
    for key, path in sorted((state.get("artifact_refs") or {}).items()):
        if not str(path or "").strip():
            continue
        rows.append(_artifact_ref_record(str(key), str(path), state=state))
    for company in _inventory_companies(state):
        for filing in company.get("filings") or []:
            if isinstance(filing, Mapping):
                rows.append(_inventory_filing_record(company, filing, state=state))
    records = _dedupe_records(rows)
    payload = {
        "schema_version": RAW_SOURCE_PROVENANCE_STORE_SCHEMA_VERSION,
        "policy": "per_run_raw_source_provenance_projection_v0_1",
        "record_count": len(records),
        "records": records,
        "summary": {
            "by_source_family": _count_by(records, "source_family"),
            "by_record_type": _count_by(records, "record_type"),
            "by_file_type": _count_by(records, "file_type"),
            "missing_raw_locator_count": len([row for row in records if not _has_raw_locator(row)]),
            "document_id_count": len([row for row in records if row.get("document_id")]),
            "checksum_count": len([row for row in records if row.get("checksum")]),
            "materialized_checksum_count": len([row for row in records if row.get("checksum_materialized")]),
            "parser_lineage_record_count": len([row for row in records if row.get("parser_run_id") or row.get("parser_version")]),
            "license_policy_count": len([row for row in records if row.get("license_policy")]),
            "robots_policy_count": len([row for row in records if row.get("robots_policy")]),
        },
    }
    payload["validation"] = validate_raw_source_provenance_store(payload)
    return payload


def validate_raw_source_provenance_store(payload: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate([item for item in payload.get("records") or [] if isinstance(item, Mapping)]):
        source_id = str(row.get("source_id") or "").strip()
        if not source_id:
            errors.append({"type": "source_id_required", "index": index})
        elif source_id in seen:
            warnings.append({"type": "duplicate_source_id", "source_id": source_id})
        seen.add(source_id)
        if not _has_raw_locator(row):
            warnings.append({"type": "raw_locator_missing", "source_id": source_id, "source_family": row.get("source_family") or ""})
        if str(row.get("source_family") or "") == "primary_sec_filing" and not str(row.get("document_id") or "").strip():
            warnings.append({"type": "primary_sec_document_id_missing", "source_id": source_id})
        if str(row.get("raw_url") or "").startswith("http") and not str(row.get("access_method") or "").strip():
            warnings.append({"type": "access_method_missing_for_url_source", "source_id": source_id})
    return {
        "schema_version": "sec_agent_raw_source_provenance_store_validation_v0.1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
    }


def build_asof_vintage_layer(state: Mapping[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for channel, row in _iter_state_rows(state):
        rows.append(_vintage_record(row, channel=channel, state=state))
    for company in _inventory_companies(state):
        for filing in company.get("filings") or []:
            if isinstance(filing, Mapping):
                rows.append(_inventory_vintage_record(company, filing, state=state))
    records = _dedupe_records(rows, key_fields=("vintage_id", "evidence_ref", "source_id", "ticker", "fiscal_period_end"))
    payload = {
        "schema_version": ASOF_VINTAGE_LAYER_SCHEMA_VERSION,
        "policy": "per_run_asof_vintage_projection_keep_observation_dates_separate_v0_1",
        "record_count": len(records),
        "records": records,
        "summary": {
            "by_source_family": _count_by(records, "source_family"),
            "by_time_basis": _count_by(records, "time_basis"),
            "fiscal_period_record_count": len([row for row in records if row.get("fiscal_period_end") or row.get("fiscal_year")]),
            "market_as_of_record_count": len([row for row in records if row.get("market_as_of_date")]),
            "macro_vintage_record_count": len([row for row in records if row.get("macro_vintage_date")]),
            "retrieved_at_count": len([row for row in records if row.get("retrieved_at")]),
            "parser_run_at_count": len([row for row in records if row.get("parser_run_at")]),
            "missing_time_anchor_count": len([row for row in records if not _has_time_anchor(row)]),
        },
    }
    payload["validation"] = validate_asof_vintage_layer(payload)
    return payload


def validate_asof_vintage_layer(payload: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for index, row in enumerate([item for item in payload.get("records") or [] if isinstance(item, Mapping)]):
        vintage_id = str(row.get("vintage_id") or "").strip()
        source_family = str(row.get("source_family") or "").strip()
        if not vintage_id:
            errors.append({"type": "vintage_id_required", "index": index})
        if not _has_time_anchor(row):
            warnings.append({"type": "time_anchor_missing", "vintage_id": vintage_id, "source_family": source_family})
        if source_family == "market_snapshot" and not str(row.get("market_as_of_date") or row.get("observation_date") or "").strip():
            warnings.append({"type": "market_snapshot_as_of_missing", "vintage_id": vintage_id})
        if source_family == "industry_snapshot" and not str(row.get("macro_vintage_date") or row.get("observation_date") or "").strip():
            warnings.append({"type": "industry_snapshot_vintage_missing", "vintage_id": vintage_id})
        if source_family in {"primary_sec_filing", "company_authored_unaudited_sec_filing"} and not (
            str(row.get("filing_date") or "").strip()
            or str(row.get("accepted_date") or "").strip()
            or str(row.get("fiscal_period_end") or "").strip()
        ):
            warnings.append({"type": "filing_time_anchor_missing", "vintage_id": vintage_id})
    return {
        "schema_version": "sec_agent_asof_vintage_layer_validation_v0.1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
    }


def build_provenance_vintage_layers(state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "raw_source_provenance_store": build_raw_source_provenance_store(state),
        "asof_vintage_layer": build_asof_vintage_layer(state),
    }


def _iter_state_rows(state: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    rows: list[tuple[str, Mapping[str, Any]]] = []
    for channel in EVIDENCE_ROW_CHANNELS:
        for row in state.get(channel) or []:
            if isinstance(row, Mapping):
                rows.append((channel, row))
    adapter = state.get("capital_macro_source_adapter") if isinstance(state.get("capital_macro_source_adapter"), Mapping) else {}
    for child_channel in CAPITAL_MACRO_ADAPTER_CHANNELS:
        for row in adapter.get(child_channel) or []:
            if isinstance(row, Mapping):
                rows.append((f"capital_macro_source_adapter.{child_channel}", row))
    pack = state.get("capital_macro_pack") if isinstance(state.get("capital_macro_pack"), Mapping) else {}
    for child_channel in CAPITAL_MACRO_PACK_CHANNELS:
        for row in pack.get(child_channel) or []:
            if isinstance(row, Mapping):
                rows.append((f"capital_macro_pack.{child_channel}", row))
    for row in state.get("tool_observations") or []:
        if isinstance(row, Mapping):
            rows.append(("tool_observations", row))
    return rows


def _provenance_record(row: Mapping[str, Any], *, channel: str, state: Mapping[str, Any]) -> dict[str, Any]:
    source_family = _source_family(row, channel=channel)
    evidence_ref = _first_text(row, "evidence_ref", "evidence_id", "object_id", "metric_id", "claim_id", "route_id")
    raw_url = _first_text(row, "raw_url", "document_url", "source_url", "url", "logged_url", "source_url_logged", "api_route")
    local_path = _first_text(row, "local_path", "raw_path", "path", "file_path", "html_path", "metadata_path", "cache_path")
    document_id = _first_text(
        row,
        "document_id",
        "accession_number",
        "accession",
        "adsh",
        "rcept_no",
        "filing_id",
        "source_document_id",
    )
    source_provider_id = _first_text(row, "source_id")
    source_id = source_provider_id or _stable_id("source", channel, evidence_ref, raw_url, local_path, document_id)
    if channel.startswith("capital_macro") and evidence_ref:
        source_id = _stable_id("capital_macro_source", source_provider_id, evidence_ref, raw_url, local_path, document_id)
    provided_checksum = _first_text(row, "checksum", "sha256", "content_sha256", "file_sha256")
    materialized_checksum = _file_sha256(local_path) if not provided_checksum else ""
    return {
        "source_id": source_id,
        "source_provider_id": source_provider_id,
        "record_type": "tool_observation" if channel == "tool_observations" else "evidence_row",
        "run_id": str(state.get("run_id") or ""),
        "source_family": source_family,
        "channel": channel,
        "evidence_ref": evidence_ref,
        "ticker": _ticker(row),
        "raw_url": raw_url,
        "local_path": local_path,
        "file_type": _file_type(row, raw_url=raw_url, local_path=local_path),
        "retrieved_at": _first_text(row, "retrieved_at", "downloaded_at", "fetched_at"),
        "source_as_of_date": _first_text(row, "source_as_of_date", "as_of_date", "market_as_of_date", "industry_as_of_date"),
        "checksum": provided_checksum or materialized_checksum,
        "checksum_materialized": bool(materialized_checksum),
        "parser_version": _first_text(row, "parser_version", "schema_version", "extractor_version"),
        "license_policy": _first_text(row, "license_policy", "license", "license_boundary"),
        "robots_policy": _first_text(row, "robots_policy", "robots_boundary"),
        "access_method": _access_method(row, raw_url=raw_url),
        "document_id": document_id,
        "citation_span": _citation_span(row),
        "parser_run_id": _first_text(row, "parser_run_id", "run_id"),
    }


def _artifact_ref_record(key: str, path: str, *, state: Mapping[str, Any]) -> dict[str, Any]:
    materialized_checksum = _file_sha256(path)
    return {
        "source_id": _stable_id("artifact", key, path),
        "record_type": "artifact_ref",
        "run_id": str(state.get("run_id") or ""),
        "source_family": "run_artifact",
        "channel": "artifact_refs",
        "evidence_ref": key,
        "ticker": "",
        "raw_url": "",
        "local_path": path,
        "file_type": _file_type({}, raw_url="", local_path=path),
        "retrieved_at": "",
        "source_as_of_date": "",
        "checksum": materialized_checksum,
        "checksum_materialized": bool(materialized_checksum),
        "parser_version": "",
        "license_policy": "",
        "robots_policy": "",
        "access_method": "local_artifact_ref",
        "document_id": key,
        "citation_span": {},
        "parser_run_id": str(state.get("run_id") or ""),
    }


def _inventory_filing_record(company: Mapping[str, Any], filing: Mapping[str, Any], *, state: Mapping[str, Any]) -> dict[str, Any]:
    ticker = str(company.get("ticker") or "").upper().strip()
    document_id = _first_text(filing, "accession_number", "document_id")
    source_family = _source_family(filing, channel="project_inventory")
    evidence_ref = _stable_id("inventory_filing", ticker, filing.get("year"), filing.get("form_type"), document_id)
    local_path = _first_text(filing, "local_path", "html_path", "metadata_path", "path")
    provided_checksum = _first_text(filing, "checksum", "sha256")
    materialized_checksum = _file_sha256(local_path) if not provided_checksum else ""
    return {
        "source_id": _stable_id("inventory_source", ticker, filing.get("year"), filing.get("form_type"), document_id),
        "record_type": "inventory_filing",
        "run_id": str(state.get("run_id") or ""),
        "source_family": source_family,
        "channel": "project_inventory.companies.filings",
        "evidence_ref": evidence_ref,
        "ticker": ticker,
        "raw_url": _first_text(filing, "raw_url", "source_url", "url"),
        "local_path": local_path,
        "file_type": _file_type(filing, raw_url="", local_path=local_path),
        "retrieved_at": _first_text(filing, "retrieved_at", "downloaded_at"),
        "source_as_of_date": _first_text(filing, "source_as_of_date", "filing_date", "report_date", "period_end"),
        "checksum": provided_checksum or materialized_checksum,
        "checksum_materialized": bool(materialized_checksum),
        "parser_version": _first_text(filing, "parser_version"),
        "license_policy": _first_text(filing, "license_policy"),
        "robots_policy": _first_text(filing, "robots_policy"),
        "access_method": _first_text(filing, "access_method") or "project_inventory_manifest",
        "document_id": document_id,
        "citation_span": {},
        "parser_run_id": str(state.get("run_id") or ""),
    }


def _vintage_record(row: Mapping[str, Any], *, channel: str, state: Mapping[str, Any]) -> dict[str, Any]:
    evidence_ref = _first_text(row, "evidence_ref", "evidence_id", "object_id", "metric_id", "claim_id", "route_id")
    document_id = _first_text(row, "document_id", "accession_number", "accession", "adsh")
    source_provider_id = _first_text(row, "source_id")
    source_id = source_provider_id or _stable_id("source", channel, evidence_ref, document_id)
    if channel.startswith("capital_macro") and evidence_ref:
        source_id = _stable_id("capital_macro_source", source_provider_id, evidence_ref, document_id)
    source_family = _source_family(row, channel=channel)
    market_as_of = _first_text(row, "market_as_of_date", "as_of_date") if source_family == "market_snapshot" else _first_text(row, "market_as_of_date")
    macro_vintage = _first_text(row, "macro_vintage_date", "vintage_date") or (
        _first_text(row, "as_of_date", "source_as_of_date") if source_family == "industry_snapshot" else ""
    )
    if not macro_vintage and _is_macro_context_row(row, source_family=source_family):
        macro_vintage = _first_text(row, "observation_date", "date", "as_of_date", "source_as_of_date")
    fiscal_period_end = _first_text(row, "fiscal_period_end", "period_end", "report_date", "source_period_end", "report_period")
    return {
        "vintage_id": _stable_id("vintage", channel, evidence_ref, source_id, fiscal_period_end, market_as_of, macro_vintage),
        "run_id": str(state.get("run_id") or ""),
        "source_id": source_id,
        "document_id": document_id,
        "evidence_ref": evidence_ref,
        "source_family": source_family,
        "channel": channel,
        "ticker": _ticker(row),
        "fiscal_year": _first_text(row, "fiscal_year", "year", "source_fiscal_year"),
        "fiscal_period": _first_text(row, "fiscal_period", "period", "period_role"),
        "fiscal_period_end": fiscal_period_end,
        "filing_date": _first_text(row, "filing_date"),
        "accepted_date": _first_text(row, "accepted_date", "accepted_at"),
        "reported_date": _first_text(row, "reported_date", "report_date"),
        "observation_date": _first_text(row, "observation_date", "date", "observed_at"),
        "retrieved_at": _first_text(row, "retrieved_at", "downloaded_at", "fetched_at"),
        "source_updated_at": _first_text(row, "source_updated_at", "updated_at"),
        "market_as_of_date": market_as_of,
        "macro_vintage_date": macro_vintage,
        "parser_run_at": _first_text(row, "parser_run_at", "parsed_at"),
        "time_basis": _time_basis(source_family=source_family, fiscal_period_end=fiscal_period_end, market_as_of=market_as_of, macro_vintage=macro_vintage),
    }


def _inventory_vintage_record(company: Mapping[str, Any], filing: Mapping[str, Any], *, state: Mapping[str, Any]) -> dict[str, Any]:
    ticker = str(company.get("ticker") or "").upper().strip()
    source_family = _source_family(filing, channel="project_inventory")
    document_id = _first_text(filing, "accession_number", "document_id")
    fiscal_period_end = _first_text(filing, "period_end", "report_date")
    source_id = _stable_id("inventory_source", ticker, filing.get("year"), filing.get("form_type"), document_id)
    return {
        "vintage_id": _stable_id("inventory_vintage", ticker, filing.get("year"), filing.get("form_type"), fiscal_period_end, document_id),
        "run_id": str(state.get("run_id") or ""),
        "source_id": source_id,
        "evidence_ref": _stable_id("inventory_filing", ticker, filing.get("year"), filing.get("form_type"), document_id),
        "source_family": source_family,
        "channel": "project_inventory.companies.filings",
        "ticker": ticker,
        "fiscal_year": str(filing.get("year") or ""),
        "fiscal_period": str(filing.get("fiscal_period") or ""),
        "fiscal_period_end": fiscal_period_end,
        "filing_date": _first_text(filing, "filing_date"),
        "accepted_date": _first_text(filing, "accepted_date", "accepted_at"),
        "reported_date": _first_text(filing, "reported_date", "report_date"),
        "observation_date": "",
        "retrieved_at": _first_text(filing, "retrieved_at", "downloaded_at"),
        "source_updated_at": _first_text(filing, "source_updated_at", "updated_at"),
        "market_as_of_date": "",
        "macro_vintage_date": "",
        "parser_run_at": _first_text(filing, "parser_run_at", "parsed_at"),
        "time_basis": "fiscal_period",
    }


def _inventory_companies(state: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    inventory = state.get("project_inventory") if isinstance(state.get("project_inventory"), Mapping) else {}
    return [row for row in inventory.get("companies") or [] if isinstance(row, Mapping)]


def _source_family(row: Mapping[str, Any], *, channel: str) -> str:
    family = _first_text(row, "source_family", "runtime_source_family", "source_tier")
    route = _first_text(row, "retrieval_route")
    if route == "market_snapshot" or channel == "market_snapshot_rows":
        return "market_snapshot"
    if route == "industry_snapshot" or channel == "industry_snapshot_rows":
        return "industry_snapshot"
    if route == "milvus_semantic":
        return "milvus_semantic"
    if family:
        return family
    if channel == "runtime_ledger_rows":
        return "primary_sec_filing"
    if channel.startswith("capital_macro_source_adapter") or channel.startswith("capital_macro_pack"):
        return _first_text(row, "source_family") or "capital_macro_pack"
    if channel.startswith("project_inventory"):
        return _first_text(row, "source_tier") or "primary_sec_filing"
    return "unknown"


def _ticker(row: Mapping[str, Any]) -> str:
    return _first_text(row, "ticker", "company_id", "issuer_id", "symbol", "focus_ticker").upper()


def _first_text(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            value = next((item for item in value if str(item or "").strip()), "")
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _file_type(row: Mapping[str, Any], *, raw_url: str, local_path: str) -> str:
    explicit = _first_text(row, "file_type", "document_type", "mime_type").lower()
    if explicit in {"html", "pdf", "xbrl", "json", "csv", "txt", "xml", "jsonl"}:
        return "xbrl" if explicit == "xml" and "xbrl" in (raw_url + local_path).lower() else explicit
    target = raw_url or local_path
    suffix = PurePath(target.split("?", 1)[0]).suffix.lower().lstrip(".")
    if suffix in {"htm", "html"}:
        return "html"
    if suffix in {"xml", "xbrl", "ins"}:
        return "xbrl"
    if suffix in {"pdf", "json", "jsonl", "csv", "txt"}:
        return suffix
    if raw_url.startswith("http"):
        return "html"
    return ""


def _file_sha256(local_path: str) -> str:
    if not str(local_path or "").strip():
        return ""
    path = Path(str(local_path))
    if not path.exists() or not path.is_file():
        return ""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return "sha256:" + hasher.hexdigest()


def _access_method(row: Mapping[str, Any], *, raw_url: str) -> str:
    explicit = _first_text(row, "access_method", "download_strategy", "retrieval_route", "tool_name")
    if explicit:
        return explicit
    if raw_url.startswith("http"):
        return "http"
    return ""


def _citation_span(row: Mapping[str, Any]) -> dict[str, Any]:
    fields = {
        "section": _first_text(row, "section", "section_name", "item"),
        "page": _first_text(row, "page", "page_number"),
        "start_char": _first_text(row, "start_char", "char_start"),
        "end_char": _first_text(row, "end_char", "char_end"),
        "line": _first_text(row, "line", "line_number"),
        "quote": _first_text(row, "quote", "snippet", "source_text", "source_statement"),
    }
    return {key: value for key, value in fields.items() if value}


def _has_raw_locator(row: Mapping[str, Any]) -> bool:
    return bool(
        str(row.get("raw_url") or "").strip()
        or str(row.get("local_path") or "").strip()
        or str(row.get("document_id") or "").strip()
        or str(row.get("evidence_ref") or "").strip()
    )


def _has_time_anchor(row: Mapping[str, Any]) -> bool:
    return any(
        str(row.get(key) or "").strip()
        for key in (
            "fiscal_period_end",
            "filing_date",
            "accepted_date",
            "reported_date",
            "observation_date",
            "retrieved_at",
            "source_updated_at",
            "market_as_of_date",
            "macro_vintage_date",
            "parser_run_at",
            "fiscal_year",
        )
    )


def _time_basis(*, source_family: str, fiscal_period_end: str, market_as_of: str, macro_vintage: str) -> str:
    if source_family == "market_snapshot" or market_as_of:
        return "market_as_of"
    if source_family == "industry_snapshot" or macro_vintage:
        return "macro_vintage"
    if fiscal_period_end:
        return "fiscal_period"
    if source_family in {"primary_sec_filing", "company_authored_unaudited_sec_filing"}:
        return "filing"
    return "source_observation"


def _is_macro_context_row(row: Mapping[str, Any], *, source_family: str) -> bool:
    object_type = _first_text(row, "object_type")
    source_id = _first_text(row, "source_id")
    return (
        object_type in {"MacroDriver", "TradeDriver", "IndustryDriver", "CompanyExposureToDriver"}
        or source_family in {"macro_or_industry_context", "public_source_context"}
        and source_id in {"fred_api", "fred_graph_csv", "bls_public_api", "eia_open_data", "census_data_api", "usitc_dataweb_and_trade"}
    )


def _dedupe_records(rows: list[dict[str, Any]], *, key_fields: tuple[str, ...] = ("source_id", "evidence_ref", "document_id", "local_path", "raw_url")) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for row in rows:
        clean = {key: _jsonable(value) for key, value in row.items()}
        key = tuple(str(clean.get(field) or "") for field in key_fields)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(clean)
    return sorted(deduped, key=lambda item: (str(item.get("source_family") or ""), str(item.get("source_id") or item.get("vintage_id") or "")))


def _count_by(rows: list[Mapping[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "unknown") for row in rows).items()))


def _stable_id(prefix: str, *values: Any) -> str:
    raw = "|".join(str(value or "") for value in values)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(child) for key, child in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value
