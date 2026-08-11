from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

from env_loader import load_env_file


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "fin_agent_public_source_normalized_snapshot_v0.1"
RECORD_SCHEMA_VERSION = "fin_agent_public_source_normalized_record_v0.1"
EVIDENCE_SCHEMA_VERSION = "fin_agent_public_source_evidence_row_v0.1"
DEFAULT_USER_AGENT = "FinSight-Agent/0.1 public-source-normalizer contact@example.com"
SECRET_QUERY_PARAMS = {"api_key", "key", "userid", "crtfc_key", "registrationkey"}


ProfileParser = Callable[[Any, dict[str, Any]], list[dict[str, Any]]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download small normalized snapshots for public/free-key data sources."
    )
    parser.add_argument("--access-plan", default="data/manifests/public_source_access_plan_v0_1.jsonl")
    parser.add_argument("--snapshot-id", default="public_source_normalized_smoke_v0_1")
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--output-root", default="data/processed_private/public_sources")
    parser.add_argument("--manifest-output", default="data/manifests/public_source_normalized_snapshot_summary_v0_1.json")
    parser.add_argument("--source-id-filter", default="", help="Comma-separated source_id filter.")
    parser.add_argument("--collector-line-filter", default="", help="Comma-separated collector line filter.")
    parser.add_argument("--max-records-per-source", type=int, default=25)
    parser.add_argument("--timeout-s", type=float, default=30.0)
    parser.add_argument("--allow-source-failures", action="store_true")
    parser.add_argument("--skip-live", action="store_true")
    parser.add_argument("--env-file", default=".env")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    loaded_env_keys = load_env_file(_resolve(args.env_file))
    access_plan_path = _resolve(args.access_plan)
    access_rows = _read_jsonl(access_plan_path)
    access_by_source = {str(row.get("source_id") or ""): row for row in access_rows}
    source_filter = set(_split_csv(args.source_id_filter))
    collector_line_filter = set(_split_csv(args.collector_line_filter))
    snapshot_id = args.snapshot_id
    as_of_date = args.as_of_date or datetime.now(timezone.utc).date().isoformat()
    fetched_at = datetime.now(timezone.utc).isoformat()
    output_dir = _resolve(args.output_root) / snapshot_id
    output_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    selected_profiles = _selected_profiles(source_filter=source_filter, collector_line_filter=collector_line_filter)

    for source_id, profile in selected_profiles:
        plan_row = access_by_source.get(source_id, {})
        if not plan_row:
            failures.append(_failure_row(source_id, profile, "missing_access_plan_row", "Source not found in access plan."))
            continue
        try:
            source_records = collect_source(
                source_id=source_id,
                profile=profile,
                plan_row=plan_row,
                snapshot_id=snapshot_id,
                as_of_date=as_of_date,
                fetched_at=fetched_at,
                timeout_s=args.timeout_s,
                max_records=max(args.max_records_per_source, 0),
                skip_live=args.skip_live,
            )
            records.extend(source_records)
            if not args.skip_live:
                evidence_rows.append(build_evidence_row(source_id, profile, plan_row, source_records, snapshot_id=snapshot_id, as_of_date=as_of_date, fetched_at=fetched_at))
        except Exception as exc:  # noqa: BLE001
            failures.append(_failure_row(source_id, profile, "download_or_parse_failed", _redact_text(str(exc))))

    records_path = output_dir / "normalized_records.jsonl"
    evidence_path = output_dir / "evidence_rows.jsonl"
    failures_path = output_dir / "failures.jsonl"
    metadata_path = output_dir / "metadata.json"
    manifest_output = _resolve(args.manifest_output)
    _write_jsonl(records_path, records)
    _write_jsonl(evidence_path, evidence_rows)
    _write_jsonl(failures_path, failures)
    summary = build_summary(
        access_plan_path=access_plan_path,
        snapshot_id=snapshot_id,
        as_of_date=as_of_date,
        fetched_at=fetched_at,
        loaded_env_keys=loaded_env_keys,
        selected_profiles=selected_profiles,
        records=records,
        evidence_rows=evidence_rows,
        failures=failures,
        records_path=records_path,
        evidence_path=evidence_path,
        failures_path=failures_path,
        metadata_path=metadata_path,
        manifest_output=manifest_output,
        skip_live=args.skip_live,
    )
    metadata_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if failures and not args.allow_source_failures:
        return 2
    return 0


def collect_source(
    *,
    source_id: str,
    profile: dict[str, Any],
    plan_row: dict[str, Any],
    snapshot_id: str,
    as_of_date: str,
    fetched_at: str,
    timeout_s: float,
    max_records: int,
    skip_live: bool,
) -> list[dict[str, Any]]:
    if skip_live:
        return []
    request_spec = prepare_request(profile)
    response = requests.request(
        request_spec["method"],
        request_spec["url"],
        params=request_spec["params"],
        headers=request_spec["headers"],
        json=request_spec["json_body"],
        timeout=timeout_s,
    )
    response.raise_for_status()
    api_route = _redact_url(response.url or request_spec["logged_url"])
    response_format = str(profile.get("response_format") or "json")
    if response_format in {"csv", "text"}:
        payload = response.text
    else:
        payload = response.json()
    context = {
        "source_id": source_id,
        "profile": profile,
        "plan_row": plan_row,
        "snapshot_id": snapshot_id,
        "as_of_date": as_of_date,
        "fetched_at": fetched_at,
        "api_route": api_route,
    }
    records = profile["parser"](payload, context)
    if max_records > 0:
        records = records[:max_records]
    return records


def prepare_request(profile: dict[str, Any]) -> dict[str, Any]:
    method = str(profile.get("method") or "GET").upper()
    url = str(profile["url"])
    params = {str(key): value for key, value in (profile.get("params") or {}).items()}
    headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json,text/csv,*/*"}
    headers.update({str(key): str(value) for key, value in (profile.get("headers") or {}).items()})
    json_body = _copy_json_value(profile.get("json_body"))
    env_var = str(profile.get("env_var") or "")
    env_param = str(profile.get("env_param") or "")
    env_location = str(profile.get("env_location") or "query")
    env_required = bool(profile.get("env_required", True))
    if env_var:
        env_value = os.environ.get(env_var, "").strip()
        if env_value:
            if not env_param:
                raise RuntimeError(f"Probe profile {profile.get('source_id')} is missing env_param")
            if env_location == "header":
                headers[env_param] = env_value
            elif env_location == "json":
                if not isinstance(json_body, dict):
                    raise RuntimeError(f"Probe profile {profile.get('source_id')} is missing JSON body")
                json_body[env_param] = env_value
            else:
                params[env_param] = env_value
        elif env_required:
            raise RuntimeError(f"Missing required environment variable {env_var}")
    logged_url = _full_url(url, _redacted_params(params))
    return {
        "method": method,
        "url": url,
        "params": params,
        "headers": headers,
        "json_body": json_body,
        "logged_url": logged_url,
    }


def build_evidence_row(
    source_id: str,
    profile: dict[str, Any],
    plan_row: dict[str, Any],
    records: list[dict[str, Any]],
    *,
    snapshot_id: str,
    as_of_date: str,
    fetched_at: str,
) -> dict[str, Any]:
    record_type_counts = dict(sorted(Counter(str(row.get("record_type") or "") for row in records).items()))
    latest_observation = _latest_value([row.get("observation_date") or row.get("period") for row in records])
    source_families = plan_row.get("source_families") or []
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "evidence_id": f"PUBLICSOURCE::{source_id}::{snapshot_id}",
        "snapshot_id": snapshot_id,
        "source_id": source_id,
        "provider": plan_row.get("provider") or profile.get("provider"),
        "collector_line": profile.get("collector_line"),
        "source_families": source_families,
        "primary_source_family": profile.get("source_family") or (source_families[0] if source_families else None),
        "claim_scope": plan_row.get("claim_scope"),
        "as_of_date": as_of_date,
        "fetched_at": fetched_at,
        "normalized_record_count": len(records),
        "record_type_counts": record_type_counts,
        "latest_observation_or_period": latest_observation,
        "api_route": records[0].get("api_route") if records else None,
        "summary": f"{source_id} normalized {len(records)} records for {profile.get('collector_line')} smoke ingestion.",
        "caveats": [
            str(plan_row.get("boundary_notes") or "Public source boundary must be checked before downstream use."),
            "This is a bounded normalized smoke artifact, not a production collector guarantee.",
            "Do not use context-only public data to overwrite company-reported financial or product-sales facts.",
        ],
        "sample_fields": sorted({key for row in records[:5] for key in row.keys()})[:40],
    }


def build_summary(
    *,
    access_plan_path: Path,
    snapshot_id: str,
    as_of_date: str,
    fetched_at: str,
    loaded_env_keys: list[str],
    selected_profiles: list[tuple[str, dict[str, Any]]],
    records: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    records_path: Path,
    evidence_path: Path,
    failures_path: Path,
    metadata_path: Path,
    manifest_output: Path,
    skip_live: bool,
) -> dict[str, Any]:
    successful_sources = sorted({str(row.get("source_id") or "") for row in evidence_rows})
    failed_sources = sorted({str(row.get("source_id") or "") for row in failures})
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "skipped" if skip_live else ("pass" if not failures else "partial" if evidence_rows else "fail"),
        "snapshot_id": snapshot_id,
        "as_of_date": as_of_date,
        "generated_at": fetched_at,
        "inputs": {
            "access_plan": _repo_path(access_plan_path),
            "loaded_env_key_names": sorted(loaded_env_keys),
        },
        "outputs": {
            "normalized_records": _repo_path(records_path),
            "evidence_rows": _repo_path(evidence_path),
            "failures": _repo_path(failures_path),
            "metadata": _repo_path(metadata_path),
            "manifest_summary": _repo_path(manifest_output),
        },
        "selected_source_count": len(selected_profiles),
        "successful_source_count": len(successful_sources),
        "failed_source_count": len(failed_sources),
        "normalized_record_count": len(records),
        "evidence_row_count": len(evidence_rows),
        "collector_line_counts": dict(sorted(Counter(str(row.get("collector_line") or "") for row in records).items())),
        "source_record_counts": dict(sorted(Counter(str(row.get("source_id") or "") for row in records).items())),
        "source_family_counts": dict(sorted(Counter(str(row.get("source_family") or "") for row in records).items())),
        "record_type_counts": dict(sorted(Counter(str(row.get("record_type") or "") for row in records).items())),
        "successful_sources": successful_sources,
        "failed_sources": failures,
        "claim_boundary": [
            "macro_industry records are context only.",
            "identity_product_disclosure records support identifiers, legal-entity mappings, regulatory/product status, or primary-disclosure metadata only.",
            "Company-level product sales, product revenue, deliveries, subscribers, backlog, or ARPU still require company-reported product operating metrics.",
        ],
    }


def parse_fred_observations(payload: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("observations") if isinstance(payload, dict) else []
    records: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        value = _parse_float(row.get("value"))
        if value is None:
            continue
        records.append(
            _record(
                context,
                record_type="macro_time_series_observation",
                source_family="macro_industry_indicator",
                record_key=str(row.get("date") or len(records)),
                series_id=str(context["profile"].get("series_id") or context["profile"].get("params", {}).get("series_id") or ""),
                observation_date=row.get("date"),
                value=value,
                unit=context["profile"].get("unit"),
                attributes={"provider_realtime_start": row.get("realtime_start"), "provider_realtime_end": row.get("realtime_end")},
            )
        )
    return records


def parse_fred_graph_csv(payload: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(payload, str):
        return []
    series_id = str(context["profile"].get("series_id") or context["profile"].get("params", {}).get("id") or "")
    records: list[dict[str, Any]] = []
    for row in csv.DictReader(payload.splitlines()):
        date_value = row.get("observation_date")
        value = _parse_float(row.get(series_id))
        if not date_value or value is None:
            continue
        records.append(
            _record(
                context,
                record_type="macro_time_series_observation",
                source_family="macro_industry_indicator",
                record_key=f"{series_id}:{date_value}",
                series_id=series_id,
                observation_date=date_value,
                value=value,
                unit=context["profile"].get("unit"),
                attributes={"route_type": "fred_graph_csv"},
            )
        )
    return records


def parse_bls_payload(payload: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
    series = ((payload.get("Results") or {}).get("series") or []) if isinstance(payload, dict) else []
    records: list[dict[str, Any]] = []
    for item in series if isinstance(series, list) else []:
        if not isinstance(item, dict):
            continue
        series_id = str(item.get("seriesID") or "")
        for obs in item.get("data") or []:
            if not isinstance(obs, dict):
                continue
            year = str(obs.get("year") or "")
            period = str(obs.get("period") or "")
            period_name = str(obs.get("periodName") or "")
            value = _parse_float(obs.get("value"))
            if not year or value is None:
                continue
            records.append(
                _record(
                    context,
                    record_type="macro_time_series_observation",
                    source_family="macro_industry_indicator",
                    record_key=f"{series_id}:{year}:{period}",
                    series_id=series_id,
                    observation_date=_normalize_bls_period(year, period),
                    period=f"{year}-{period}",
                    value=value,
                    unit=context["profile"].get("unit"),
                    attributes={"period_name": period_name, "footnotes": obs.get("footnotes") or []},
                )
            )
    return records


def parse_bea_payload(payload: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
    results = ((payload.get("BEAAPI") or {}).get("Results") or {}) if isinstance(payload, dict) else {}
    rows = results.get("Data") if isinstance(results, dict) else []
    records: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        value = _parse_float(row.get("DataValue"))
        if value is None:
            continue
        line_number = str(row.get("LineNumber") or row.get("Line") or "")
        time_period = str(row.get("TimePeriod") or "")
        table = str(row.get("TableName") or context["profile"].get("params", {}).get("TableName") or "")
        records.append(
            _record(
                context,
                record_type="macro_table_observation",
                source_family="macro_industry_indicator",
                record_key=f"{table}:{line_number}:{time_period}",
                series_id=f"BEA::{table}::{line_number}",
                period=time_period,
                observation_date=_normalize_period_to_date(time_period),
                metric_name=str(row.get("LineDescription") or ""),
                value=value,
                unit=str(row.get("UNIT_MULT") or context["profile"].get("unit") or ""),
                attributes={"table_name": table, "line_number": line_number, "cl_unit": row.get("CL_UNIT")},
            )
        )
    return records


def parse_census_payload(payload: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], list):
        return []
    headers = [str(item) for item in payload[0]]
    records: list[dict[str, Any]] = []
    for index, values in enumerate(payload[1:], start=1):
        row = {headers[i]: values[i] for i in range(min(len(headers), len(values)))}
        value = _parse_float(row.get("B01001_001E"))
        records.append(
            _record(
                context,
                record_type="macro_cross_section_observation",
                source_family="macro_industry_indicator",
                record_key=str(row.get("us") or index),
                series_id="CENSUS::ACS5::B01001_001E",
                period="2023",
                observation_date="2023-01-01",
                metric_name="ACS 5-year total population estimate",
                value=value,
                unit="persons",
                entity_name=str(row.get("NAME") or ""),
                attributes=row,
            )
        )
    return records


def parse_eia_payload(payload: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
    response = payload.get("response") if isinstance(payload, dict) else {}
    rows = response.get("data") if isinstance(response, dict) else []
    records: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        period = str(row.get("period") or "")
        for field in _profile_data_fields(context["profile"]):
            value = _parse_float(row.get(field))
            if value is None:
                continue
            series_id = str(row.get("msn") or row.get("series") or row.get("series_id") or f"EIA::{context['profile'].get('dataset_id')}::{field}")
            records.append(
                _record(
                    context,
                    record_type="macro_time_series_observation",
                    source_family="macro_industry_indicator",
                    record_key=f"{series_id}:{period}:{field}",
                    series_id=series_id,
                    period=period,
                    observation_date=_normalize_period_to_date(period),
                    metric_name=field,
                    value=value,
                    unit=str(row.get("unit") or row.get(f"{field}-units") or context["profile"].get("unit") or ""),
                    attributes={
                        "series_description": row.get("seriesDescription") or row.get("series-description"),
                        "stateid": row.get("stateid"),
                        "sectorid": row.get("sectorid"),
                    },
                )
            )
    return records


def parse_fdic_payload(payload: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("data") if isinstance(payload, dict) else []
    records: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        data = row.get("data") if isinstance(row, dict) else {}
        if not isinstance(data, dict):
            continue
        cert = str(data.get("CERT") or "")
        records.append(
            _record(
                context,
                record_type="institution_reference_record",
                source_family="macro_industry_indicator",
                record_key=cert or str(len(records)),
                identifier_type="FDIC_CERT",
                identifier=cert,
                entity_name=str(data.get("NAME") or ""),
                status=str(data.get("ACTIVE") or ""),
                attributes={key.lower(): data.get(key) for key in sorted(data.keys())},
            )
        )
    return records


def parse_sec_submissions_payload(payload: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    recent = ((payload.get("filings") or {}).get("recent") or {}) if isinstance(payload.get("filings"), dict) else {}
    forms = recent.get("form") if isinstance(recent, dict) else []
    accession_numbers = recent.get("accessionNumber") if isinstance(recent, dict) else []
    filing_dates = recent.get("filingDate") if isinstance(recent, dict) else []
    records: list[dict[str, Any]] = []
    for index, form in enumerate(forms if isinstance(forms, list) else []):
        accession = _list_get(accession_numbers, index)
        filing_date = _list_get(filing_dates, index)
        records.append(
            _record(
                context,
                record_type="filing_metadata_record",
                source_family="sec_submissions_metadata",
                record_key=str(accession or index),
                identifier_type="CIK",
                identifier=str(payload.get("cik") or ""),
                entity_name=str(payload.get("name") or ""),
                status=str(form or ""),
                observation_date=filing_date,
                attributes={"accession_number": accession, "filing_date": filing_date, "form": form},
            )
        )
    return records


def parse_clinicaltrials_payload(payload: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
    studies = payload.get("studies") if isinstance(payload, dict) else []
    records: list[dict[str, Any]] = []
    for study in studies if isinstance(studies, list) else []:
        protocol = study.get("protocolSection") if isinstance(study, dict) else {}
        if not isinstance(protocol, dict):
            continue
        ident = protocol.get("identificationModule") or {}
        status = protocol.get("statusModule") or {}
        sponsors = protocol.get("sponsorCollaboratorsModule") or {}
        nct_id = str(ident.get("nctId") or "")
        records.append(
            _record(
                context,
                record_type="clinical_trial_status_record",
                source_family="official_product_status",
                record_key=nct_id or str(len(records)),
                identifier_type="NCT_ID",
                identifier=nct_id,
                product_name=str(ident.get("briefTitle") or ""),
                entity_name=str((sponsors.get("leadSponsor") or {}).get("name") or ""),
                status=str(status.get("overallStatus") or ""),
                observation_date=status.get("startDateStruct", {}).get("date") if isinstance(status.get("startDateStruct"), dict) else None,
                attributes={
                    "brief_title": ident.get("briefTitle"),
                    "official_title": ident.get("officialTitle"),
                    "phases": protocol.get("designModule", {}).get("phases") if isinstance(protocol.get("designModule"), dict) else None,
                },
            )
        )
    return records


def parse_cms_catalog_payload(payload: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
    dataset_rows = payload.get("dataset") if isinstance(payload, dict) else []
    records: list[dict[str, Any]] = []
    for row in dataset_rows if isinstance(dataset_rows, list) else []:
        if not isinstance(row, dict):
            continue
        identifier = str(row.get("identifier") or row.get("@id") or len(records))
        records.append(
            _record(
                context,
                record_type="public_dataset_catalog_record",
                source_family="macro_industry_indicator",
                record_key=identifier,
                identifier_type="CMS_DATASET_ID",
                identifier=identifier,
                entity_name=str(row.get("title") or ""),
                status=str(row.get("modified") or row.get("issued") or ""),
                attributes={
                    "title": row.get("title"),
                    "description": row.get("description"),
                    "keyword": row.get("keyword"),
                    "theme": row.get("theme"),
                    "publisher": row.get("publisher"),
                    "distribution_count": len(row.get("distribution") or []) if isinstance(row.get("distribution"), list) else 0,
                },
            )
        )
    return records


def parse_census_trade_payload(payload: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], list):
        return []
    headers = [str(item) for item in payload[0]]
    records: list[dict[str, Any]] = []
    for index, values in enumerate(payload[1:], start=1):
        row = {headers[i]: values[i] for i in range(min(len(headers), len(values)))}
        commodity = str(row.get("I_COMMODITY") or row.get("E_COMMODITY") or context["profile"].get("commodity") or "")
        country = str(row.get("CTY_CODE") or row.get("COUNTRY") or index)
        time_value = str(row.get("time") or row.get("YEAR") or "")
        value = _parse_float(row.get("GEN_VAL_MO") or row.get("ALL_VAL_MO") or row.get("CON_VAL_MO"))
        records.append(
            _record(
                context,
                record_type="trade_context_observation",
                source_family="macro_industry_indicator",
                record_key=f"{commodity}:{country}:{time_value}",
                series_id=f"CENSUS_TRADE_IMPORTS_HS::{commodity}",
                period=time_value,
                observation_date=_normalize_period_to_date(time_value),
                metric_name="monthly import value",
                value=value,
                unit="USD",
                entity_name=str(row.get("CTY_NAME") or ""),
                attributes=row,
            )
        )
    return records


def parse_yahoo_chart_payload(payload: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
    chart = payload.get("chart") if isinstance(payload, dict) else {}
    results = chart.get("result") if isinstance(chart, dict) else []
    result = results[0] if isinstance(results, list) and results and isinstance(results[0], dict) else {}
    meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
    timestamps = result.get("timestamp") if isinstance(result.get("timestamp"), list) else []
    indicators = result.get("indicators") if isinstance(result.get("indicators"), dict) else {}
    quote_rows = indicators.get("quote") if isinstance(indicators.get("quote"), list) else []
    quote = quote_rows[0] if quote_rows and isinstance(quote_rows[0], dict) else {}
    close_values = quote.get("close") if isinstance(quote.get("close"), list) else []
    volume_values = quote.get("volume") if isinstance(quote.get("volume"), list) else []
    symbol = str(meta.get("symbol") or context["profile"].get("symbol") or "")
    records: list[dict[str, Any]] = []
    for index, timestamp in enumerate(timestamps):
        close = _parse_float(_list_get(close_values, index))
        if close is None:
            continue
        volume = _parse_float(_list_get(volume_values, index))
        observation_date = datetime.fromtimestamp(int(timestamp), tz=timezone.utc).date().isoformat()
        records.append(
            _record(
                context,
                record_type="market_price_observation",
                source_family="market_price_snapshot",
                record_key=f"{symbol}:{observation_date}",
                series_id=f"YAHOO_CHART::{symbol}",
                observation_date=observation_date,
                metric_name="daily close",
                value=close,
                unit=str(meta.get("currency") or ""),
                identifier_type="ticker",
                identifier=symbol,
                entity_name=str(meta.get("longName") or meta.get("shortName") or symbol),
                attributes={
                    "symbol": symbol,
                    "range": context["profile"].get("params", {}).get("range"),
                    "interval": context["profile"].get("params", {}).get("interval"),
                    "volume": volume,
                    "exchange_name": meta.get("exchangeName"),
                    "instrument_type": meta.get("instrumentType"),
                },
            )
        )
    return records


def parse_openalex_payload(payload: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("results") if isinstance(payload, dict) else []
    records: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        work_id = str(row.get("id") or row.get("doi") or len(records))
        host_venue = row.get("host_venue") if isinstance(row.get("host_venue"), dict) else {}
        concepts = row.get("concepts") if isinstance(row.get("concepts"), list) else []
        records.append(
            _record(
                context,
                record_type="research_work_lead_record",
                source_family="external_event_lead",
                record_key=work_id,
                identifier_type="OpenAlexWork",
                identifier=work_id,
                entity_name=str(host_venue.get("display_name") or ""),
                product_name=str(row.get("display_name") or ""),
                period=str(row.get("publication_year") or ""),
                observation_date=row.get("publication_date"),
                value=_parse_float(row.get("cited_by_count")),
                metric_name="cited_by_count",
                attributes={
                    "doi": row.get("doi"),
                    "title": row.get("display_name"),
                    "publication_year": row.get("publication_year"),
                    "type": row.get("type"),
                    "open_access": row.get("open_access"),
                    "top_concepts": [
                        {"id": item.get("id"), "display_name": item.get("display_name"), "score": item.get("score")}
                        for item in concepts[:5]
                        if isinstance(item, dict)
                    ],
                },
            )
        )
    return records


def parse_wikidata_search_payload(payload: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("search") if isinstance(payload, dict) else []
    records: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        entity_id = str(row.get("id") or len(records))
        records.append(
            _record(
                context,
                record_type="alias_identifier_candidate_record",
                source_family="external_event_lead",
                record_key=entity_id,
                identifier_type="WIKIDATA_QID",
                identifier=entity_id,
                entity_name=str(row.get("label") or ""),
                status=str(row.get("concepturi") or ""),
                attributes={
                    "description": row.get("description"),
                    "aliases": row.get("aliases"),
                    "match": row.get("match"),
                    "repository": row.get("repository"),
                    "url": row.get("url"),
                },
            )
        )
    return records


def parse_gdelt_lastupdate_payload(payload: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(payload, str):
        return []
    records: list[dict[str, Any]] = []
    for index, line in enumerate(payload.splitlines(), start=1):
        parts = line.strip().split()
        if len(parts) < 3:
            continue
        size, checksum, url = parts[0], parts[1], parts[2]
        records.append(
            _record(
                context,
                record_type="event_data_index_record",
                source_family="external_event_lead",
                record_key=url,
                identifier_type="GDELT_URL",
                identifier=url,
                value=_parse_float(size),
                unit="bytes",
                attributes={
                    "md5": checksum,
                    "file_name": url.rsplit("/", 1)[-1],
                    "index_row": index,
                    "route_type": "gdelt_lastupdate",
                },
            )
        )
    return records


def parse_common_crawl_collinfo_payload(payload: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in payload if isinstance(payload, list) else []:
        if not isinstance(row, dict):
            continue
        crawl_id = str(row.get("id") or len(records))
        records.append(
            _record(
                context,
                record_type="crawl_index_metadata_record",
                source_family="external_event_lead",
                record_key=crawl_id,
                identifier_type="COMMON_CRAWL_INDEX_ID",
                identifier=crawl_id,
                entity_name=str(row.get("name") or crawl_id),
                status=str(row.get("timegate") or ""),
                attributes={
                    "cdx_api": row.get("cdx-api"),
                    "from": row.get("from"),
                    "to": row.get("to"),
                    "description": row.get("description"),
                },
            )
        )
    return records


def parse_patentsview_migration_payload(payload: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(payload, str):
        return []
    title_match = re.search(r"<title>(.*?)</title>", payload, flags=re.IGNORECASE | re.DOTALL)
    title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else ""
    link_candidates = sorted(
        {
            match.group(1)
            for match in re.finditer(r'href=["\']([^"\']+)["\']', payload, flags=re.IGNORECASE)
            if any(token in match.group(1).lower() for token in ("patentsview", "open-data", "data-download", "developer.uspto"))
        }
    )
    return [
        _record(
            context,
            record_type="patent_data_access_metadata_record",
            source_family="external_event_lead",
            record_key="patentsview_uspto_odp_migration",
            identifier_type="USPTO_PATENTSVIEW_MIGRATION_PAGE",
            identifier=str(context["profile"].get("url") or ""),
            entity_name="USPTO PatentsView / Open Data Portal",
            status="migration_metadata_materialized",
            attributes={
                "title": title,
                "matched_link_count": len(link_candidates),
                "matched_links": link_candidates[:20],
                "content_length": len(payload),
            },
        )
    ]


def parse_openfda_payload(payload: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("results") if isinstance(payload, dict) else []
    records: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        products = row.get("products") if isinstance(row.get("products"), list) else []
        first_product = products[0] if products and isinstance(products[0], dict) else {}
        application_number = str(row.get("application_number") or "")
        brand_name = str(first_product.get("brand_name") or first_product.get("brand_name_base") or "")
        records.append(
            _record(
                context,
                record_type="fda_product_status_record",
                source_family="official_product_status",
                record_key=application_number or str(len(records)),
                identifier_type="FDA_APPLICATION_NUMBER",
                identifier=application_number,
                product_name=brand_name,
                entity_name=str(row.get("sponsor_name") or ""),
                status=str(row.get("submission_status") or row.get("marketing_status") or ""),
                attributes={
                    "application_number": application_number,
                    "sponsor_name": row.get("sponsor_name"),
                    "product_number": first_product.get("product_number"),
                    "active_ingredients": first_product.get("active_ingredients"),
                },
            )
        )
    return records


def parse_nhtsa_payload(payload: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("Results") if isinstance(payload, dict) else []
    records: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        model_name = str(row.get("Model_Name") or "")
        make_name = str(row.get("Make_Name") or "")
        records.append(
            _record(
                context,
                record_type="vehicle_model_identity_record",
                source_family="official_product_status",
                record_key=f"{make_name}:{model_name}",
                product_name=model_name,
                entity_name=make_name,
                identifier_type="NHTSA_MAKE_MODEL",
                identifier=f"{make_name}:{model_name}",
                attributes={key.lower(): row.get(key) for key in sorted(row.keys())},
            )
        )
    return records


def parse_gleif_payload(payload: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("data") if isinstance(payload, dict) else []
    records: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        attributes = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
        entity = attributes.get("entity") if isinstance(attributes.get("entity"), dict) else {}
        legal_name = entity.get("legalName") if isinstance(entity.get("legalName"), dict) else {}
        lei = str(attributes.get("lei") or row.get("id") or "")
        records.append(
            _record(
                context,
                record_type="legal_entity_identifier_record",
                source_family="relationship_edge",
                record_key=lei or str(len(records)),
                identifier_type="LEI",
                identifier=lei,
                entity_name=str(legal_name.get("name") or ""),
                status=str(entity.get("status") or ""),
                attributes={
                    "jurisdiction": entity.get("jurisdiction"),
                    "legal_form": entity.get("legalForm"),
                    "registration_status": attributes.get("registration", {}).get("status") if isinstance(attributes.get("registration"), dict) else None,
                },
            )
        )
    return records


def parse_openfigi_payload(payload: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for batch in payload if isinstance(payload, list) else []:
        rows = batch.get("data") if isinstance(batch, dict) else []
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            figi = str(row.get("figi") or "")
            records.append(
                _record(
                    context,
                    record_type="security_identifier_mapping_record",
                    source_family="relationship_edge",
                    record_key=figi or str(len(records)),
                    identifier_type="FIGI",
                    identifier=figi,
                    entity_name=str(row.get("name") or ""),
                    status=str(row.get("securityType") or ""),
                    attributes={key: row.get(key) for key in sorted(row.keys()) if key not in {"figi", "name"}},
                )
            )
    return records


def parse_dart_company_payload(payload: Any, context: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    status = str(payload.get("status") or "")
    if status != "000":
        raise RuntimeError(f"DART provider status {status}: {payload.get('message')}")
    corp_code = str(payload.get("corp_code") or "")
    return [
        _record(
            context,
            record_type="primary_disclosure_company_reference_record",
            source_family="global_public_annual_report",
            record_key=corp_code,
            identifier_type="DART_CORP_CODE",
            identifier=corp_code,
            entity_name=str(payload.get("corp_name") or ""),
            status=str(payload.get("corp_cls") or ""),
            attributes={
                "corp_name_eng": payload.get("corp_name_eng"),
                "stock_code": payload.get("stock_code"),
                "modify_date": payload.get("modify_date"),
            },
        )
    ]


def _record(context: dict[str, Any], *, record_type: str, source_family: str, record_key: str, **fields: Any) -> dict[str, Any]:
    plan_row = context["plan_row"]
    source_id = str(context["source_id"])
    record_id = f"PUBLICSOURCE::{source_id}::{record_type}::{record_key}"
    return {
        "schema_version": RECORD_SCHEMA_VERSION,
        "record_id": record_id,
        "snapshot_id": context["snapshot_id"],
        "source_id": source_id,
        "provider": plan_row.get("provider") or context["profile"].get("provider"),
        "collector_line": context["profile"].get("collector_line"),
        "record_type": record_type,
        "source_family": source_family,
        "source_families": plan_row.get("source_families") or [],
        "claim_scope": plan_row.get("claim_scope"),
        "claim_boundary": plan_row.get("boundary_notes"),
        "as_of_date": context["as_of_date"],
        "fetched_at": context["fetched_at"],
        "api_route": context["api_route"],
        "source_policy": context["profile"].get("source_policy"),
        **{key: value for key, value in fields.items() if value is not None and key != "attributes"},
        "attributes_json": json.dumps(fields.get("attributes") or {}, ensure_ascii=False, sort_keys=True),
    }


def _selected_profiles(*, source_filter: set[str], collector_line_filter: set[str]) -> list[tuple[str, dict[str, Any]]]:
    selected: list[tuple[str, dict[str, Any]]] = []
    for source_id in COLLECTOR_ORDER:
        profile = COLLECTOR_PROFILES[source_id]
        if source_filter and source_id not in source_filter:
            continue
        if collector_line_filter and str(profile.get("collector_line") or "") not in collector_line_filter:
            continue
        selected.append((source_id, {**profile, "source_id": source_id}))
    return selected


def _failure_row(source_id: str, profile: dict[str, Any], status: str, error: str) -> dict[str, Any]:
    return {
        "schema_version": "fin_agent_public_source_normalized_failure_v0.1",
        "source_id": source_id,
        "provider": profile.get("provider"),
        "collector_line": profile.get("collector_line"),
        "status": status,
        "error": _redact_text(error),
    }


def _profile_data_fields(profile: dict[str, Any]) -> list[str]:
    fields = profile.get("data_fields")
    if isinstance(fields, list) and fields:
        return [str(item) for item in fields]
    params = profile.get("params") or {}
    found: list[tuple[int, str]] = []
    for key, value in params.items():
        match = re.fullmatch(r"data\[(\d+)\]", str(key))
        if match:
            found.append((int(match.group(1)), str(value)))
    return [field for _, field in sorted(found)] or ["value"]


def _full_url(url: str, params: dict[str, Any]) -> str:
    if not params:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{urlencode(params, doseq=True)}"


def _redacted_params(params: dict[str, Any]) -> dict[str, Any]:
    return {key: ("REDACTED" if key.lower() in SECRET_QUERY_PARAMS else value) for key, value in params.items()}


def _redact_url(url: str) -> str:
    text = str(url)
    for param in SECRET_QUERY_PARAMS:
        text = re.sub(rf"([?&]{re.escape(param)}=)[^&]+", r"\1REDACTED", text, flags=re.IGNORECASE)
    return text


def _redact_text(text: str) -> str:
    return _redact_url(text)


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text or text.lower() in {"na", "n/a", "none", "null", "not available", ".", "--"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _normalize_bls_period(year: str, period: str) -> str:
    match = re.fullmatch(r"M(\d{2})", period or "")
    if match:
        return f"{year}-{match.group(1)}-01"
    return f"{year}-01-01"


def _normalize_period_to_date(period: str) -> str | None:
    text = str(period or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}", text):
        return f"{text}-01"
    quarter = re.fullmatch(r"(\d{4})Q([1-4])", text)
    if quarter:
        month = {"1": "01", "2": "04", "3": "07", "4": "10"}[quarter.group(2)]
        return f"{quarter.group(1)}-{month}-01"
    if re.fullmatch(r"\d{4}", text):
        return f"{text}-01-01"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    return None


def _latest_value(values: list[Any]) -> Any:
    cleaned = sorted(str(value) for value in values if value not in {None, ""})
    return cleaned[-1] if cleaned else None


def _list_get(values: Any, index: int) -> Any:
    return values[index] if isinstance(values, list) and 0 <= index < len(values) else None


def _copy_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _copy_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy_json_value(item) for item in value]
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _split_csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _resolve(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else REPO_ROOT / path


def _repo_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


COMMON_CONTEXT_POLICY = "normalized_smoke_context_only; requires source_boundary_gate_before_agent_promotion"

COLLECTOR_PROFILES: dict[str, dict[str, Any]] = {
    "fred_graph_csv": {
        "provider": "FRED",
        "collector_line": "macro_industry",
        "source_family": "macro_industry_indicator",
        "source_policy": COMMON_CONTEXT_POLICY,
        "method": "GET",
        "url": "https://fred.stlouisfed.org/graph/fredgraph.csv",
        "params": {"id": "FEDFUNDS"},
        "series_id": "FEDFUNDS",
        "unit": "percent",
        "response_format": "csv",
        "parser": parse_fred_graph_csv,
    },
    "fred_api": {
        "provider": "FRED",
        "collector_line": "macro_industry",
        "source_family": "macro_industry_indicator",
        "source_policy": COMMON_CONTEXT_POLICY,
        "method": "GET",
        "url": "https://api.stlouisfed.org/fred/series/observations",
        "params": {"series_id": "FEDFUNDS", "file_type": "json", "limit": "12", "sort_order": "desc"},
        "series_id": "FEDFUNDS",
        "unit": "percent",
        "env_var": "FRED_API_KEY",
        "env_param": "api_key",
        "env_location": "query",
        "parser": parse_fred_observations,
    },
    "bls_public_api": {
        "provider": "BLS",
        "collector_line": "macro_industry",
        "source_family": "macro_industry_indicator",
        "source_policy": COMMON_CONTEXT_POLICY,
        "method": "POST",
        "url": "https://api.bls.gov/publicAPI/v2/timeseries/data/",
        "json_body": {"seriesid": ["CUUR0000SA0"], "startyear": "2025", "endyear": "2026"},
        "unit": "index",
        "env_var": "BLS_API_KEY",
        "env_param": "registrationkey",
        "env_location": "json",
        "env_required": False,
        "parser": parse_bls_payload,
    },
    "bea_data_api": {
        "provider": "BEA",
        "collector_line": "macro_industry",
        "source_family": "macro_industry_indicator",
        "source_policy": COMMON_CONTEXT_POLICY,
        "method": "GET",
        "url": "https://apps.bea.gov/api/data",
        "params": {"method": "GetData", "datasetname": "NIPA", "TableName": "T10101", "Frequency": "Q", "Year": "2025", "ResultFormat": "JSON"},
        "unit": "BEA provider unit",
        "env_var": "BEA_API_KEY",
        "env_param": "UserID",
        "env_location": "query",
        "parser": parse_bea_payload,
    },
    "census_data_api": {
        "provider": "Census",
        "collector_line": "macro_industry",
        "source_family": "macro_industry_indicator",
        "source_policy": COMMON_CONTEXT_POLICY,
        "method": "GET",
        "url": "https://api.census.gov/data/2023/acs/acs5",
        "params": {"get": "NAME,B01001_001E", "for": "us:*"},
        "env_var": "CENSUS_API_KEY",
        "env_param": "key",
        "env_location": "query",
        "parser": parse_census_payload,
    },
    "eia_open_data": {
        "provider": "EIA",
        "collector_line": "macro_industry",
        "source_family": "macro_industry_indicator",
        "source_policy": COMMON_CONTEXT_POLICY,
        "method": "GET",
        "url": "https://api.eia.gov/v2/total-energy/data/",
        "params": {"frequency": "monthly", "data[0]": "value", "sort[0][column]": "period", "sort[0][direction]": "desc", "offset": "0", "length": "12"},
        "data_fields": ["value"],
        "dataset_id": "eia/total-energy/monthly",
        "unit": "mixed",
        "env_var": "EIA_API_KEY",
        "env_param": "api_key",
        "env_location": "query",
        "parser": parse_eia_payload,
    },
    "fdic_bankfind_api": {
        "provider": "FDIC",
        "collector_line": "macro_industry",
        "source_family": "macro_industry_indicator",
        "source_policy": COMMON_CONTEXT_POLICY,
        "method": "GET",
        "url": "https://banks.data.fdic.gov/api/institutions",
        "params": {"filters": "ACTIVE:1", "fields": "NAME,CERT,ACTIVE,CITY,STNAME", "limit": "5", "format": "json"},
        "parser": parse_fdic_payload,
    },
    "cms_public_data": {
        "provider": "CMS",
        "collector_line": "macro_industry",
        "source_family": "macro_industry_indicator",
        "source_policy": COMMON_CONTEXT_POLICY,
        "method": "GET",
        "url": "https://data.cms.gov/data.json",
        "params": {},
        "parser": parse_cms_catalog_payload,
    },
    "usitc_dataweb_and_trade": {
        "provider": "Census International Trade",
        "collector_line": "macro_industry",
        "source_family": "macro_industry_indicator",
        "source_policy": COMMON_CONTEXT_POLICY,
        "method": "GET",
        "url": "https://api.census.gov/data/timeseries/intltrade/imports/hs",
        "params": {
            "get": "I_COMMODITY,I_COMMODITY_LDESC,GEN_VAL_MO,CON_VAL_MO,CTY_CODE,CTY_NAME",
            "time": "2026-03",
            "COMM_LVL": "HS4",
            "I_COMMODITY": "8542",
        },
        "commodity": "8542",
        "env_var": "CENSUS_API_KEY",
        "env_param": "key",
        "env_location": "query",
        "parser": parse_census_trade_payload,
    },
    "yahoo_chart": {
        "provider": "Yahoo",
        "collector_line": "market_context",
        "source_family": "market_price_snapshot",
        "source_policy": "unofficial_provisional_market_context_only; replace_with_approved_provider_when_available",
        "method": "GET",
        "url": "https://query1.finance.yahoo.com/v8/finance/chart/AAPL",
        "params": {"range": "1mo", "interval": "1d"},
        "symbol": "AAPL",
        "parser": parse_yahoo_chart_payload,
    },
    "openalex_api": {
        "provider": "OpenAlex",
        "collector_line": "lead_discovery",
        "source_family": "external_event_lead",
        "source_policy": "research_trend_lead_only; requires topic_entity_resolver_before_research_use",
        "method": "GET",
        "url": "https://api.openalex.org/works",
        "params": {"search": "semiconductor", "per-page": "5"},
        "parser": parse_openalex_payload,
    },
    "wikidata": {
        "provider": "Wikidata",
        "collector_line": "lead_discovery",
        "source_family": "external_event_lead",
        "source_policy": "low_weight_alias_candidate_only; never_financial_fact_evidence",
        "method": "GET",
        "url": "https://www.wikidata.org/w/api.php",
        "params": {"action": "wbsearchentities", "search": "Apple Inc", "language": "en", "format": "json", "limit": "5"},
        "parser": parse_wikidata_search_payload,
    },
    "gdelt": {
        "provider": "GDELT",
        "collector_line": "lead_discovery",
        "source_family": "external_event_lead",
        "source_policy": "event_data_index_only; article_claims_require_official_verification",
        "method": "GET",
        "url": "http://data.gdeltproject.org/gdeltv2/lastupdate.txt",
        "params": {},
        "response_format": "text",
        "parser": parse_gdelt_lastupdate_payload,
    },
    "common_crawl_index": {
        "provider": "Common Crawl",
        "collector_line": "lead_discovery",
        "source_family": "external_event_lead",
        "source_policy": "crawl_index_discovery_only; fetched_pages_require_official_origin_filter",
        "method": "GET",
        "url": "https://index.commoncrawl.org/collinfo.json",
        "params": {},
        "parser": parse_common_crawl_collinfo_payload,
    },
    "patentsview_api": {
        "provider": "USPTO PatentsView / Open Data Portal",
        "collector_line": "lead_discovery",
        "source_family": "external_event_lead",
        "source_policy": "migration_metadata_only; patent_api_endpoint_validation_still_required",
        "method": "GET",
        "url": "https://www.uspto.gov/subscription-center/2026/patentsview-migrating-uspto-open-data-portal-march-20",
        "params": {},
        "response_format": "text",
        "parser": parse_patentsview_migration_payload,
    },
    "sec_edgar_apis": {
        "provider": "SEC",
        "collector_line": "identity_product_disclosure",
        "source_family": "sec_submissions_metadata",
        "source_policy": "primary_sec_metadata_smoke; existing_sec_pipeline_remains_authority_path",
        "method": "GET",
        "url": "https://data.sec.gov/submissions/CIK0000320193.json",
        "parser": parse_sec_submissions_payload,
    },
    "kr_dart_openapi": {
        "provider": "DART",
        "collector_line": "identity_product_disclosure",
        "source_family": "global_public_annual_report",
        "source_policy": "primary_disclosure_reference_smoke; filings_download_parser_not_promoted",
        "method": "GET",
        "url": "https://opendart.fss.or.kr/api/company.json",
        "params": {"corp_code": "00126380"},
        "env_var": "DART_API_KEY",
        "env_param": "crtfc_key",
        "env_location": "query",
        "parser": parse_dart_company_payload,
    },
    "gleif_api": {
        "provider": "GLEIF",
        "collector_line": "identity_product_disclosure",
        "source_family": "relationship_edge",
        "source_policy": "entity_resolution_only; legal_identifier_not_commercial_relationship",
        "method": "GET",
        "url": "https://api.gleif.org/api/v1/lei-records",
        "params": {"page[size]": "5"},
        "parser": parse_gleif_payload,
    },
    "openfigi_api": {
        "provider": "OpenFIGI",
        "collector_line": "identity_product_disclosure",
        "source_family": "relationship_edge",
        "source_policy": "security_identifier_mapping_only; not_financial_evidence",
        "method": "POST",
        "url": "https://api.openfigi.com/v3/mapping",
        "json_body": [{"idType": "TICKER", "idValue": "AAPL", "exchCode": "US"}],
        "env_var": "OPENFIGI_API_KEY",
        "env_param": "X-OPENFIGI-APIKEY",
        "env_location": "header",
        "env_required": False,
        "parser": parse_openfigi_payload,
    },
    "clinicaltrials_api": {
        "provider": "ClinicalTrials.gov",
        "collector_line": "identity_product_disclosure",
        "source_family": "official_product_status",
        "source_policy": "trial_registration_context_only; not_sales_or_approval_claim",
        "method": "GET",
        "url": "https://clinicaltrials.gov/api/v2/studies",
        "params": {"query.term": "cancer", "pageSize": "5"},
        "parser": parse_clinicaltrials_payload,
    },
    "openfda_api": {
        "provider": "openFDA",
        "collector_line": "identity_product_disclosure",
        "source_family": "official_product_status",
        "source_policy": "regulatory_product_status_context_only; not_commercial_uptake",
        "method": "GET",
        "url": "https://api.fda.gov/drug/drugsfda.json",
        "params": {"limit": "5"},
        "env_var": "OPENFDA_API_KEY",
        "env_param": "api_key",
        "env_location": "query",
        "env_required": False,
        "parser": parse_openfda_payload,
    },
    "nhtsa_vpic_api": {
        "provider": "NHTSA",
        "collector_line": "identity_product_disclosure",
        "source_family": "official_product_status",
        "source_policy": "vehicle_model_identity_context_only; not_sales_or_profitability",
        "method": "GET",
        "url": "https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMake/Tesla",
        "params": {"format": "json"},
        "parser": parse_nhtsa_payload,
    },
}

COLLECTOR_ORDER = [
    "fred_graph_csv",
    "fred_api",
    "bls_public_api",
    "bea_data_api",
    "census_data_api",
    "eia_open_data",
    "fdic_bankfind_api",
    "cms_public_data",
    "usitc_dataweb_and_trade",
    "yahoo_chart",
    "openalex_api",
    "wikidata",
    "gdelt",
    "common_crawl_index",
    "patentsview_api",
    "sec_edgar_apis",
    "kr_dart_openapi",
    "gleif_api",
    "openfigi_api",
    "clinicaltrials_api",
    "openfda_api",
    "nhtsa_vpic_api",
]


if __name__ == "__main__":
    raise SystemExit(main())
