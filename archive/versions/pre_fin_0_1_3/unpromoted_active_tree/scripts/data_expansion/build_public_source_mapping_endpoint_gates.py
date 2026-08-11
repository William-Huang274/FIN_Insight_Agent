from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import time
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlencode
from xml.etree import ElementTree

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

from env_loader import load_env_file


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "fin_agent_public_source_mapping_endpoint_gate_v0.1"
SUMMARY_SCHEMA_VERSION = "fin_agent_public_source_mapping_endpoint_gate_summary_v0.1"
DEFAULT_USER_AGENT = "FinSight-Agent/0.1 public-source-mapping-gate contact@example.com"
SECRET_QUERY_PARAMS = {"api_key", "key", "userid", "crtfc_key", "registrationkey"}

SOURCE_ORDER = [
    "sec_universe_identity",
    "openfigi_api",
    "gleif_api",
    "fdic_bankfind_api",
    "clinicaltrials_api",
    "openfda_api",
    "nhtsa_vpic_api",
    "census_data_api",
    "eia_open_data",
    "kr_dart_openapi",
]

LEGAL_SUFFIXES = {
    "ag",
    "corp",
    "corporation",
    "co",
    "company",
    "inc",
    "incorporated",
    "limited",
    "ltd",
    "llc",
    "lp",
    "plc",
    "sa",
    "se",
    "nv",
    "holdings",
    "holding",
    "group",
    "and",
}

OPENFIGI_EXCH_CODES = {
    "NYSE": "US",
    "NASDAQ": "US",
    "NYSEARCA": "US",
    "CBOE": "US",
    "OTC": "US",
    "HKEX": "HK",
    "KRX": "KS",
    "TWSE": "TT",
    "TSE": "JP",
    "SZSE": "CH",
    "SSE": "CH",
    "XETRA": "GY",
}

AUTO_MAKE_ALIASES = {
    "TSLA": ["Tesla"],
    "F": ["Ford"],
    "GM": ["Chevrolet", "Cadillac", "Buick", "GMC"],
    "TM": ["Toyota"],
    "HMC": ["Honda"],
    "RIVN": ["Rivian"],
    "LCID": ["Lucid"],
    "LI": ["Li Auto"],
    "NIO": ["NIO"],
    "XPEV": ["XPENG"],
    "1211.HK": ["BYD"],
}

OPENFDA_SPONSOR_ALIASES = {
    "ABBV": ["ABBVIE"],
    "ABT": ["ABBOTT"],
    "AMGN": ["AMGEN"],
    "BMY": ["BRISTOL"],
    "GILD": ["GILEAD"],
    "JNJ": ["JANSSEN", "JOHNSON"],
    "LLY": ["LILLY"],
    "MRK": ["MERCK"],
    "MRNA": ["MODERNA"],
    "PFE": ["PFIZER"],
    "REGN": ["REGENERON"],
    "VRTX": ["VERTEX"],
    "ZTS": ["ZOETIS"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build target-universe public source mapping and endpoint gates.")
    parser.add_argument("--universe-csv", default="data/manifests/tier1_tier2_market_universe_v0_1.csv")
    parser.add_argument("--universe-manifest", default="data/manifests/tier1_plus_tier2_supply_chain_manifest.jsonl")
    parser.add_argument("--run-id", default="public_source_mapping_endpoint_gate_v0_1")
    parser.add_argument("--output-root", default="data/processed_private/public_sources")
    parser.add_argument("--manifest-output", default="data/manifests/public_source_mapping_endpoint_gate_summary_v0_1.json")
    parser.add_argument("--gate-output", default="data/manifests/public_source_mapping_endpoint_gate_v0_1.jsonl")
    parser.add_argument("--source-id-filter", default="", help="Comma-separated source_id filter.")
    parser.add_argument("--max-records-per-company", type=int, default=50)
    parser.add_argument("--max-gleif-results-per-company", type=int, default=3)
    parser.add_argument("--fdic-page-size", type=int, default=1000)
    parser.add_argument("--timeout-s", type=float, default=30.0)
    parser.add_argument("--sleep-s", type=float, default=0.05)
    parser.add_argument("--allow-source-failures", action="store_true")
    parser.add_argument("--skip-live", action="store_true")
    parser.add_argument("--env-file", default=".env")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    loaded_env_keys = load_env_file(_resolve(args.env_file))
    started_at = datetime.now(timezone.utc).isoformat()
    output_dir = _resolve(args.output_root) / args.run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    records_path = output_dir / "endpoint_records.jsonl"
    mappings_path = output_dir / "mapping_candidates.jsonl"
    gaps_path = output_dir / "source_gaps.jsonl"
    entities_path = output_dir / "universe_entities.jsonl"
    metadata_path = output_dir / "metadata.json"
    manifest_output = _resolve(args.manifest_output)
    gate_output = _resolve(args.gate_output)

    universe = load_universe(_resolve(args.universe_csv), _resolve(args.universe_manifest))
    source_filter = set(_split_csv(args.source_id_filter))
    selected_sources = [source for source in SOURCE_ORDER if not source_filter or source in source_filter]
    session = requests.Session()
    session.headers.update({"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json,text/csv,*/*"})
    sink = ArtifactSink(records=[], mappings=[], gaps=[])
    gate_rows: list[dict[str, Any]] = []

    _write_jsonl(entities_path, [entity_row(row) for row in universe])

    for source_id in selected_sources:
        before = sink.counts()
        gate_started = datetime.now(timezone.utc).isoformat()
        try:
            if source_id == "sec_universe_identity":
                result = build_sec_identity_gate(universe, sink=sink)
            elif source_id == "openfigi_api":
                result = build_openfigi_gate(universe, session=session, sink=sink, args=args)
            elif source_id == "gleif_api":
                result = build_gleif_gate(universe, session=session, sink=sink, args=args)
            elif source_id == "fdic_bankfind_api":
                result = build_fdic_gate(universe, session=session, sink=sink, args=args)
            elif source_id == "clinicaltrials_api":
                result = build_clinicaltrials_gate(universe, session=session, sink=sink, args=args)
            elif source_id == "openfda_api":
                result = build_openfda_gate(universe, session=session, sink=sink, args=args)
            elif source_id == "nhtsa_vpic_api":
                result = build_nhtsa_gate(universe, session=session, sink=sink, args=args)
            elif source_id == "census_data_api":
                result = build_census_gate(session=session, sink=sink, args=args)
            elif source_id == "eia_open_data":
                result = build_eia_gate(session=session, sink=sink, args=args)
            elif source_id == "kr_dart_openapi":
                result = build_dart_gate(universe, session=session, sink=sink, args=args)
            else:
                result = {"status": "skipped_unknown_source", "decision": "not_ready_unknown_source"}
        except Exception as exc:  # noqa: BLE001
            result = {
                "status": "error",
                "decision": "blocked_source_exception",
                "error": redact_text(str(exc)),
            }
        after = sink.counts()
        gate_rows.append(
            build_gate_row(
                source_id,
                result=result,
                before=before,
                after=after,
                started_at=gate_started,
                output_dir=output_dir,
                skip_live=args.skip_live,
            )
        )
        if args.sleep_s > 0:
            time.sleep(args.sleep_s)

    _write_jsonl(records_path, sink.records)
    _write_jsonl(mappings_path, sink.mappings)
    _write_jsonl(gaps_path, sink.gaps)
    _write_jsonl(gate_output, gate_rows)
    summary = build_summary(
        universe=universe,
        gate_rows=gate_rows,
        started_at=started_at,
        loaded_env_keys=loaded_env_keys,
        output_dir=output_dir,
        records_path=records_path,
        mappings_path=mappings_path,
        gaps_path=gaps_path,
        entities_path=entities_path,
        metadata_path=metadata_path,
        manifest_output=manifest_output,
        gate_output=gate_output,
    )
    metadata_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    failed = [row for row in gate_rows if row["status"] == "error"]
    return 2 if failed and not args.allow_source_failures else 0


class ArtifactSink:
    def __init__(self, *, records: list[dict[str, Any]], mappings: list[dict[str, Any]], gaps: list[dict[str, Any]]) -> None:
        self.records = records
        self.mappings = mappings
        self.gaps = gaps

    def counts(self) -> dict[str, int]:
        return {"records": len(self.records), "mappings": len(self.mappings), "gaps": len(self.gaps)}

    def add_record(self, row: dict[str, Any]) -> None:
        self.records.append({"schema_version": SCHEMA_VERSION, **row})

    def add_mapping(self, row: dict[str, Any]) -> None:
        self.mappings.append({"schema_version": SCHEMA_VERSION, **row})

    def add_gap(self, row: dict[str, Any]) -> None:
        self.gaps.append({"schema_version": SCHEMA_VERSION, **row})


def build_sec_identity_gate(universe: list[dict[str, Any]], *, sink: ArtifactSink) -> dict[str, Any]:
    mapped = 0
    missing = 0
    for company in universe:
        if company.get("sec_download_eligible") != "true":
            continue
        if company.get("cik"):
            mapped += 1
            sink.add_mapping(
                mapping_row(
                    "sec_universe_identity",
                    company,
                    external_id=f"CIK{company['cik']}",
                    external_name=company["company_name"],
                    identifier_type="sec_cik",
                    confidence="high",
                    status="mapped",
                    evidence={"cik": company["cik"], "source": "tier1_plus_tier2_supply_chain_manifest"},
                )
            )
        else:
            missing += 1
            sink.add_gap(gap_row("sec_universe_identity", company, "missing_cik", "SEC eligible company has no CIK."))
    return {
        "status": "pass" if missing == 0 else "partial",
        "decision": "ready_for_primary_disclosure_inventory" if missing == 0 else "partial_missing_cik",
        "mapped_company_count": mapped,
        "gap_count": missing,
    }


def build_openfigi_gate(universe: list[dict[str, Any]], *, session: requests.Session, sink: ArtifactSink, args: argparse.Namespace) -> dict[str, Any]:
    if args.skip_live:
        return {"status": "skipped_live", "decision": "not_confirmed_skip_live"}
    jobs = build_openfigi_jobs(universe)
    if not jobs:
        return {"status": "partial", "decision": "blocked_no_openfigi_jobs"}
    headers = {}
    api_key = os.environ.get("OPENFIGI_API_KEY", "").strip()
    if api_key:
        headers["X-OPENFIGI-APIKEY"] = api_key
    mapped = 0
    failed = 0
    endpoint = "https://api.openfigi.com/v3/mapping"
    for chunk in _chunks(jobs, 50):
        response = session.post(endpoint, headers=headers, json=[job["request"] for job in chunk], timeout=args.timeout_s)
        if response.status_code >= 400:
            failed += len(chunk)
            for job in chunk:
                sink.add_gap(gap_row("openfigi_api", job["company"], "http_error", f"OpenFIGI mapping failed: {response.status_code}"))
            continue
        payload = response.json()
        for job, result in zip(chunk, payload):
            data_rows = result.get("data") if isinstance(result, dict) else None
            if not data_rows:
                failed += 1
                sink.add_gap(gap_row("openfigi_api", job["company"], "no_figi_match", "OpenFIGI returned no mapping rows."))
                continue
            for item in data_rows[:3]:
                sink.add_record(
                    {
                        "source_id": "openfigi_api",
                        "record_type": "security_identifier_mapping_record",
                        "source_url": endpoint,
                        "source_url_logged": endpoint,
                        "ticker": job["company"]["ticker"],
                        "external_id": item.get("figi") or item.get("compositeFIGI") or item.get("shareClassFIGI"),
                        "external_name": item.get("name"),
                        "attributes": {
                            "ticker": item.get("ticker"),
                            "exchCode": item.get("exchCode"),
                            "marketSector": item.get("marketSector"),
                            "securityType": item.get("securityType"),
                            "securityType2": item.get("securityType2"),
                        },
                    }
                )
            best = data_rows[0]
            mapped += 1
            sink.add_mapping(
                mapping_row(
                    "openfigi_api",
                    job["company"],
                    external_id=best.get("figi") or best.get("compositeFIGI") or "",
                    external_name=best.get("name") or "",
                    identifier_type="figi",
                    confidence="high" if str(best.get("ticker") or "").upper() == job["request"]["idValue"].upper() else "medium",
                    status="mapped",
                    evidence={"exchCode": best.get("exchCode"), "marketSector": best.get("marketSector")},
                )
            )
        if args.sleep_s > 0:
            time.sleep(args.sleep_s)
    return {
        "status": "pass" if mapped and failed == 0 else "partial" if mapped else "fail",
        "decision": "ready_for_identifier_mapping_after_rate_gate" if mapped else "blocked_no_figi_matches",
        "mapped_company_count": mapped,
        "gap_count": failed,
        "request_job_count": len(jobs),
        "api_key_present": bool(api_key),
    }


def build_gleif_gate(universe: list[dict[str, Any]], *, session: requests.Session, sink: ArtifactSink, args: argparse.Namespace) -> dict[str, Any]:
    if args.skip_live:
        return {"status": "skipped_live", "decision": "not_confirmed_skip_live"}
    mapped = 0
    gaps = 0
    for company in universe:
        params = {
            "filter[entity.legalName]": company["company_name"],
            "page[size]": str(max(args.max_gleif_results_per_company, 1)),
        }
        url = "https://api.gleif.org/api/v1/lei-records"
        response = session.get(url, params=params, timeout=args.timeout_s)
        logged_url = redact_url(response.url)
        if response.status_code >= 400:
            gaps += 1
            sink.add_gap(gap_row("gleif_api", company, "http_error", f"GLEIF query failed: {response.status_code}", source_url=logged_url))
            continue
        payload = response.json()
        rows = payload.get("data") if isinstance(payload, dict) else []
        if not isinstance(rows, list) or not rows:
            gaps += 1
            sink.add_gap(gap_row("gleif_api", company, "no_lei_candidate", "GLEIF returned no LEI candidates.", source_url=logged_url))
            continue
        best_candidate: dict[str, Any] | None = None
        best_confidence = "low"
        for item in rows:
            attrs = item.get("attributes") if isinstance(item, dict) else {}
            entity = attrs.get("entity") if isinstance(attrs, dict) else {}
            legal_name = ((entity.get("legalName") or {}).get("name") if isinstance(entity.get("legalName"), dict) else "") if isinstance(entity, dict) else ""
            lei = attrs.get("lei") if isinstance(attrs, dict) else item.get("id")
            confidence = name_match_confidence(company["company_name"], legal_name)
            sink.add_record(
                {
                    "source_id": "gleif_api",
                    "record_type": "legal_entity_identifier_record",
                    "source_url": logged_url,
                    "ticker": company["ticker"],
                    "external_id": lei,
                    "external_name": legal_name,
                    "attributes": {
                        "registration_status": ((attrs.get("registration") or {}).get("status") if isinstance(attrs, dict) else None),
                        "entity_status": ((entity.get("status") if isinstance(entity, dict) else None)),
                    },
                }
            )
            if best_candidate is None or confidence_rank(confidence) > confidence_rank(best_confidence):
                best_candidate = {"lei": lei, "legal_name": legal_name}
                best_confidence = confidence
        if best_candidate and best_confidence in {"high", "medium"}:
            mapped += 1
            sink.add_mapping(
                mapping_row(
                    "gleif_api",
                    company,
                    external_id=best_candidate["lei"],
                    external_name=best_candidate["legal_name"],
                    identifier_type="lei",
                    confidence=best_confidence,
                    status="candidate_mapped",
                    evidence={"match_policy": "normalized_legal_name"},
                )
            )
        else:
            gaps += 1
            sink.add_gap(gap_row("gleif_api", company, "low_confidence_lei_candidate", "GLEIF candidates did not pass conservative name matching.", source_url=logged_url))
        if args.sleep_s > 0:
            time.sleep(args.sleep_s)
    return {
        "status": "pass" if mapped and gaps == 0 else "partial" if mapped else "fail",
        "decision": "partial_requires_entity_mapping",
        "mapped_company_count": mapped,
        "gap_count": gaps,
    }


def build_fdic_gate(universe: list[dict[str, Any]], *, session: requests.Session, sink: ArtifactSink, args: argparse.Namespace) -> dict[str, Any]:
    if args.skip_live:
        return {"status": "skipped_live", "decision": "not_confirmed_skip_live"}
    url = "https://banks.data.fdic.gov/api/institutions"
    all_rows: list[dict[str, Any]] = []
    offset = 0
    page_size = max(args.fdic_page_size, 1)
    while True:
        params = {
            "filters": "ACTIVE:1",
            "fields": "NAME,CERT,ACTIVE,CITY,STNAME,ASSET,CHARTER,WEBADDR",
            "limit": str(page_size),
            "offset": str(offset),
            "format": "json",
        }
        response = session.get(url, params=params, timeout=args.timeout_s)
        logged_url = redact_url(response.url)
        if response.status_code >= 400:
            sink.add_gap({"source_id": "fdic_bankfind_api", "gap_type": "http_error", "detail": f"FDIC institutions failed: {response.status_code}", "source_url": logged_url})
            break
        payload = response.json()
        rows = payload.get("data") if isinstance(payload, dict) else []
        if not isinstance(rows, list) or not rows:
            break
        for item in rows:
            data = item.get("data") if isinstance(item, dict) else {}
            if not isinstance(data, dict):
                continue
            all_rows.append(data)
            sink.add_record(
                {
                    "source_id": "fdic_bankfind_api",
                    "record_type": "institution_reference_record",
                    "source_url": logged_url,
                    "external_id": data.get("CERT"),
                    "external_name": data.get("NAME"),
                    "attributes": {
                        "city": data.get("CITY"),
                        "state": data.get("STNAME"),
                        "active": data.get("ACTIVE"),
                        "asset": data.get("ASSET"),
                    },
                }
            )
        total = int((payload.get("meta") or {}).get("total") or len(all_rows))
        offset += len(rows)
        if offset >= total:
            break
    financials = [row for row in universe if row.get("sector") == "Financials"]
    mapped = 0
    gaps = 0
    for company in financials:
        candidates = match_by_normalized_name(company["company_name"], all_rows, "NAME")
        if candidates:
            best = candidates[0]
            mapped += 1
            sink.add_mapping(
                mapping_row(
                    "fdic_bankfind_api",
                    company,
                    external_id=str(best.get("CERT") or ""),
                    external_name=str(best.get("NAME") or ""),
                    identifier_type="fdic_cert",
                    confidence="medium",
                    status="subsidiary_or_institution_candidate",
                    evidence={"city": best.get("CITY"), "state": best.get("STNAME")},
                )
            )
        else:
            gaps += 1
            sink.add_gap(gap_row("fdic_bankfind_api", company, "no_fdic_institution_candidate", "No active FDIC institution matched issuer name."))
    return {
        "status": "pass" if all_rows else "fail",
        "decision": "partial_requires_entity_mapping",
        "downloaded_record_count": len(all_rows),
        "target_financial_company_count": len(financials),
        "mapped_company_count": mapped,
        "gap_count": gaps,
    }


def build_clinicaltrials_gate(universe: list[dict[str, Any]], *, session: requests.Session, sink: ArtifactSink, args: argparse.Namespace) -> dict[str, Any]:
    if args.skip_live:
        return {"status": "skipped_live", "decision": "not_confirmed_skip_live"}
    targets = [row for row in universe if row.get("sector") == "Health Care"]
    mapped = 0
    gaps = 0
    for company in targets:
        downloaded = 0
        page_token = ""
        company_had_rows = False
        while downloaded < args.max_records_per_company:
            params = {"query.spons": sponsor_query_name(company), "pageSize": str(min(25, args.max_records_per_company - downloaded))}
            if page_token:
                params["pageToken"] = page_token
            response = session.get("https://clinicaltrials.gov/api/v2/studies", params=params, timeout=args.timeout_s)
            logged_url = redact_url(response.url)
            if response.status_code >= 400:
                sink.add_gap(gap_row("clinicaltrials_api", company, "http_error", f"ClinicalTrials query failed: {response.status_code}", source_url=logged_url))
                break
            payload = response.json()
            rows = payload.get("studies") if isinstance(payload, dict) else []
            if not isinstance(rows, list) or not rows:
                break
            company_had_rows = True
            for study in rows:
                protocol = study.get("protocolSection") if isinstance(study, dict) else {}
                identification = protocol.get("identificationModule") if isinstance(protocol, dict) else {}
                status = protocol.get("statusModule") if isinstance(protocol, dict) else {}
                sponsor = protocol.get("sponsorCollaboratorsModule") if isinstance(protocol, dict) else {}
                nct_id = identification.get("nctId") if isinstance(identification, dict) else ""
                brief_title = identification.get("briefTitle") if isinstance(identification, dict) else ""
                lead_sponsor = ((sponsor.get("leadSponsor") or {}).get("name") if isinstance(sponsor, dict) else "")
                sink.add_record(
                    {
                        "source_id": "clinicaltrials_api",
                        "record_type": "clinical_trial_status_record",
                        "source_url": logged_url,
                        "ticker": company["ticker"],
                        "external_id": nct_id,
                        "external_name": brief_title,
                        "attributes": {
                            "lead_sponsor": lead_sponsor,
                            "overall_status": status.get("overallStatus") if isinstance(status, dict) else "",
                            "start_date": ((status.get("startDateStruct") or {}).get("date") if isinstance(status, dict) else ""),
                        },
                    }
                )
                downloaded += 1
            page_token = str(payload.get("nextPageToken") or "")
            if not page_token:
                break
            if args.sleep_s > 0:
                time.sleep(args.sleep_s)
        if company_had_rows:
            mapped += 1
            sink.add_mapping(
                mapping_row(
                    "clinicaltrials_api",
                    company,
                    external_id=company["ticker"],
                    external_name=company["company_name"],
                    identifier_type="clinicaltrials_sponsor_query",
                    confidence="medium",
                    status="sponsor_query_candidate",
                    evidence={"downloaded_study_count": downloaded, "truncated": downloaded >= args.max_records_per_company},
                )
            )
        else:
            gaps += 1
            sink.add_gap(gap_row("clinicaltrials_api", company, "no_sponsor_studies", "No ClinicalTrials.gov studies matched sponsor query."))
        if args.sleep_s > 0:
            time.sleep(args.sleep_s)
    return {
        "status": "pass" if mapped and gaps == 0 else "partial" if mapped else "fail",
        "decision": "partial_requires_healthcare_entity_mapping",
        "target_company_count": len(targets),
        "mapped_company_count": mapped,
        "gap_count": gaps,
    }


def build_openfda_gate(universe: list[dict[str, Any]], *, session: requests.Session, sink: ArtifactSink, args: argparse.Namespace) -> dict[str, Any]:
    if args.skip_live:
        return {"status": "skipped_live", "decision": "not_confirmed_skip_live"}
    targets = [row for row in universe if row.get("sector") == "Health Care"]
    mapped = 0
    gaps = 0
    for company in targets:
        terms = openfda_terms(company)
        company_records = 0
        matched_term = ""
        for term in terms:
            skip = 0
            while company_records < args.max_records_per_company:
                params = {"search": f"sponsor_name:{term}", "limit": str(min(25, args.max_records_per_company - company_records)), "skip": str(skip)}
                response = session.get("https://api.fda.gov/drug/drugsfda.json", params=params, timeout=args.timeout_s)
                logged_url = redact_url(response.url)
                if response.status_code == 404:
                    break
                if response.status_code >= 400:
                    sink.add_gap(gap_row("openfda_api", company, "http_error", f"openFDA query failed: {response.status_code}", source_url=logged_url))
                    break
                payload = response.json()
                rows = payload.get("results") if isinstance(payload, dict) else []
                if not isinstance(rows, list) or not rows:
                    break
                matched_term = term
                for item in rows:
                    app_number = item.get("application_number")
                    sponsor = item.get("sponsor_name")
                    products = item.get("products") if isinstance(item.get("products"), list) else []
                    product_names = [str(product.get("brand_name") or "") for product in products if isinstance(product, dict)]
                    sink.add_record(
                        {
                            "source_id": "openfda_api",
                            "record_type": "fda_product_status_record",
                            "source_url": logged_url,
                            "ticker": company["ticker"],
                            "external_id": app_number,
                            "external_name": sponsor,
                            "attributes": {
                                "sponsor_name": sponsor,
                                "product_names": product_names[:5],
                                "product_count": len(product_names),
                            },
                        }
                    )
                    company_records += 1
                total = int(((payload.get("meta") or {}).get("results") or {}).get("total") or company_records)
                skip += len(rows)
                if skip >= total or company_records >= args.max_records_per_company:
                    break
            if company_records:
                break
        if company_records:
            mapped += 1
            sink.add_mapping(
                mapping_row(
                    "openfda_api",
                    company,
                    external_id=matched_term,
                    external_name=company["company_name"],
                    identifier_type="openfda_sponsor_name_query",
                    confidence="medium",
                    status="sponsor_query_candidate",
                    evidence={"downloaded_record_count": company_records, "matched_term": matched_term, "truncated": company_records >= args.max_records_per_company},
                )
            )
        else:
            gaps += 1
            sink.add_gap(gap_row("openfda_api", company, "no_sponsor_product_records", "No openFDA drug/drugsfda sponsor records matched sponsor aliases."))
        if args.sleep_s > 0:
            time.sleep(args.sleep_s)
    return {
        "status": "pass" if mapped and gaps == 0 else "partial" if mapped else "fail",
        "decision": "partial_requires_endpoint_and_product_mapping",
        "target_company_count": len(targets),
        "mapped_company_count": mapped,
        "gap_count": gaps,
    }


def build_nhtsa_gate(universe: list[dict[str, Any]], *, session: requests.Session, sink: ArtifactSink, args: argparse.Namespace) -> dict[str, Any]:
    if args.skip_live:
        return {"status": "skipped_live", "decision": "not_confirmed_skip_live"}
    targets = auto_targets(universe)
    mapped = 0
    gaps = 0
    for company in targets:
        makes = AUTO_MAKE_ALIASES.get(company["ticker"], [first_distinctive_token(company["company_name"])])
        company_rows = 0
        for make in makes:
            response = session.get(f"https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMake/{make}", params={"format": "json"}, timeout=args.timeout_s)
            logged_url = redact_url(response.url)
            if response.status_code >= 400:
                continue
            payload = response.json()
            rows = payload.get("Results") if isinstance(payload, dict) else []
            if not isinstance(rows, list) or not rows:
                continue
            matching_rows = [item for item in rows if isinstance(item, dict) and make_name_matches(make, item.get("Make_Name"))]
            if not matching_rows:
                continue
            for item in matching_rows[: args.max_records_per_company]:
                sink.add_record(
                    {
                        "source_id": "nhtsa_vpic_api",
                        "record_type": "vehicle_model_identity_record",
                        "source_url": logged_url,
                        "ticker": company["ticker"],
                        "external_id": item.get("Model_ID"),
                        "external_name": item.get("Model_Name"),
                        "attributes": {"make_id": item.get("Make_ID"), "make_name": item.get("Make_Name")},
                    }
                )
                company_rows += 1
            sink.add_mapping(
                mapping_row(
                    "nhtsa_vpic_api",
                    company,
                    external_id=make,
                    external_name=str(rows[0].get("Make_Name") or make),
                    identifier_type="nhtsa_make",
                    confidence="medium",
                    status="make_query_candidate",
                    evidence={"downloaded_model_count": len(matching_rows), "query_make": make},
                )
            )
            break
        if company_rows:
            mapped += 1
        else:
            gaps += 1
            sink.add_gap(gap_row("nhtsa_vpic_api", company, "no_make_model_records", "No NHTSA vPIC make/model records matched make aliases."))
    return {
        "status": "pass" if mapped and gaps == 0 else "partial" if mapped else "fail",
        "decision": "partial_requires_auto_entity_mapping",
        "target_company_count": len(targets),
        "mapped_company_count": mapped,
        "gap_count": gaps,
    }


def build_census_gate(*, session: requests.Session, sink: ArtifactSink, args: argparse.Namespace) -> dict[str, Any]:
    if args.skip_live:
        return {"status": "skipped_live", "decision": "not_confirmed_skip_live"}
    years = ["2021", "2022", "2023"]
    rows_out = 0
    gaps = 0
    for year in years:
        url = f"https://api.census.gov/data/{year}/acs/acs5"
        params = {"get": "NAME,B01001_001E", "for": "us:*"}
        api_key = os.environ.get("CENSUS_API_KEY", "").strip()
        if api_key:
            params["key"] = api_key
        response = session.get(url, params=params, timeout=args.timeout_s)
        logged_url = redact_url(response.url)
        if response.status_code >= 400:
            gaps += 1
            sink.add_gap({"source_id": "census_data_api", "gap_type": "http_error", "detail": f"Census ACS {year} failed: {response.status_code}", "source_url": logged_url})
            continue
        payload = response.json()
        if not isinstance(payload, list) or len(payload) < 2:
            gaps += 1
            sink.add_gap({"source_id": "census_data_api", "gap_type": "empty_dataset", "detail": f"Census ACS {year} returned no rows.", "source_url": logged_url})
            continue
        header = payload[0]
        for data in payload[1:]:
            row = dict(zip(header, data))
            sink.add_record(
                {
                    "source_id": "census_data_api",
                    "record_type": "macro_cross_section_observation",
                    "source_url": logged_url,
                    "external_id": f"ACS5:{year}:B01001_001E:US",
                    "external_name": row.get("NAME"),
                    "attributes": {"year": year, "metric_name": "B01001_001E", "value": row.get("B01001_001E"), "geography": row.get("us")},
                }
            )
            rows_out += 1
    return {
        "status": "pass" if rows_out and gaps == 0 else "partial" if rows_out else "fail",
        "decision": "ready_for_context_inventory_after_boundary_gate" if rows_out and gaps == 0 else "partial_requires_dataset_table_contract",
        "downloaded_record_count": rows_out,
        "gap_count": gaps,
        "dataset_years": years,
    }


def build_eia_gate(*, session: requests.Session, sink: ArtifactSink, args: argparse.Namespace) -> dict[str, Any]:
    if args.skip_live:
        return {"status": "skipped_live", "decision": "not_confirmed_skip_live"}
    api_key = os.environ.get("EIA_API_KEY", "").strip()
    routes = [
        {
            "name": "total_energy_monthly_latest",
            "url": "https://api.eia.gov/v2/total-energy/data/",
            "params": {"frequency": "monthly", "data[0]": "value", "sort[0][column]": "period", "sort[0][direction]": "desc", "offset": "0", "length": "500"},
        },
        {
            "name": "electricity_retail_sales_monthly_latest",
            "url": "https://api.eia.gov/v2/electricity/retail-sales/data/",
            "params": {"frequency": "monthly", "data[0]": "sales", "sort[0][column]": "period", "sort[0][direction]": "desc", "offset": "0", "length": "500"},
        },
    ]
    rows_out = 0
    gaps = 0
    for route in routes:
        params = dict(route["params"])
        if api_key:
            params["api_key"] = api_key
        response = session.get(route["url"], params=params, timeout=args.timeout_s)
        logged_url = redact_url(response.url)
        if response.status_code >= 400:
            gaps += 1
            sink.add_gap({"source_id": "eia_open_data", "gap_type": "http_error", "detail": f"EIA route {route['name']} failed: {response.status_code}", "source_url": logged_url})
            continue
        payload = response.json()
        data_rows = ((payload.get("response") or {}).get("data") or []) if isinstance(payload, dict) else []
        for item in data_rows:
            if not isinstance(item, dict):
                continue
            value = item.get("value", item.get("sales"))
            sink.add_record(
                {
                    "source_id": "eia_open_data",
                    "record_type": "macro_time_series_observation",
                    "source_url": logged_url,
                    "external_id": f"{route['name']}:{item.get('period')}:{item.get('series-description') or item.get('sectorid') or item.get('stateid') or ''}",
                    "external_name": item.get("series-description") or item.get("sectorName") or item.get("stateDescription"),
                    "attributes": {"route": route["name"], "period": item.get("period"), "value": value, "unit": item.get("unit")},
                }
            )
            rows_out += 1
    return {
        "status": "pass" if rows_out and gaps == 0 else "partial" if rows_out else "fail",
        "decision": "partial_requires_route_and_entity_mapping",
        "downloaded_record_count": rows_out,
        "gap_count": gaps,
        "api_key_present": bool(api_key),
    }


def build_dart_gate(universe: list[dict[str, Any]], *, session: requests.Session, sink: ArtifactSink, args: argparse.Namespace) -> dict[str, Any]:
    if args.skip_live:
        return {"status": "skipped_live", "decision": "not_confirmed_skip_live"}
    api_key = os.environ.get("DART_API_KEY", "").strip()
    if not api_key:
        for company in [row for row in universe if row.get("country") == "South Korea"]:
            sink.add_gap(gap_row("kr_dart_openapi", company, "missing_dart_api_key", "DART_API_KEY is not configured."))
        return {"status": "blocked", "decision": "blocked_missing_credential", "api_key_present": False}
    corp_rows = download_dart_corp_codes(session=session, api_key=api_key, timeout_s=args.timeout_s)
    for row in corp_rows:
        sink.add_record(
            {
                "source_id": "kr_dart_openapi",
                "record_type": "dart_corp_code_reference",
                "source_url": "https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key=REDACTED",
                "external_id": row.get("corp_code"),
                "external_name": row.get("corp_name"),
                "attributes": {"stock_code": row.get("stock_code"), "modify_date": row.get("modify_date")},
            }
        )
    kr_targets = [row for row in universe if row.get("country") == "South Korea"]
    mapped = 0
    gaps = 0
    filings = 0
    for company in kr_targets:
        match = match_dart_company(company, corp_rows)
        if not match:
            gaps += 1
            sink.add_gap(gap_row("kr_dart_openapi", company, "no_dart_corp_code_match", "No DART corp_code matched Korean issuer."))
            continue
        mapped += 1
        sink.add_mapping(
            mapping_row(
                "kr_dart_openapi",
                company,
                external_id=match.get("corp_code") or "",
                external_name=match.get("corp_name") or "",
                identifier_type="dart_corp_code",
                confidence="high" if normalize_stock_code(company.get("exchange_symbol")) == normalize_stock_code(match.get("stock_code")) else "medium",
                status="mapped",
                evidence={"stock_code": match.get("stock_code"), "modify_date": match.get("modify_date")},
            )
        )
        list_rows = download_dart_filings(session=session, api_key=api_key, corp_code=str(match.get("corp_code") or ""), timeout_s=args.timeout_s)
        if not list_rows:
            sink.add_gap(gap_row("kr_dart_openapi", company, "no_recent_dart_filings", "DART list endpoint returned no filings for current audit window."))
        for filing in list_rows[: args.max_records_per_company]:
            filings += 1
            sink.add_record(
                {
                    "source_id": "kr_dart_openapi",
                    "record_type": "dart_filing_metadata_record",
                    "source_url": "https://opendart.fss.or.kr/api/list.json?crtfc_key=REDACTED",
                    "ticker": company["ticker"],
                    "external_id": filing.get("rcept_no"),
                    "external_name": filing.get("report_nm"),
                    "attributes": {
                        "corp_code": filing.get("corp_code"),
                        "corp_name": filing.get("corp_name"),
                        "rcept_dt": filing.get("rcept_dt"),
                        "corp_cls": filing.get("corp_cls"),
                    },
                }
            )
        if args.sleep_s > 0:
            time.sleep(args.sleep_s)
    return {
        "status": "pass" if mapped and filings and gaps == 0 else "partial" if mapped else "fail",
        "decision": "partial_requires_dart_document_parser" if mapped else "blocked_no_dart_mapping",
        "target_company_count": len(kr_targets),
        "mapped_company_count": mapped,
        "downloaded_corp_code_count": len(corp_rows),
        "downloaded_filing_count": filings,
        "gap_count": gaps,
        "api_key_present": True,
    }


def load_universe(universe_csv: Path, universe_manifest: Path) -> list[dict[str, Any]]:
    cik_by_ticker: dict[str, str] = {}
    alternate_by_ticker: dict[str, list[str]] = {}
    if universe_manifest.exists():
        for row in _read_jsonl(universe_manifest):
            ticker = str(row.get("ticker") or "").upper()
            if ticker:
                cik_by_ticker[ticker] = str(row.get("cik") or "")
                alternate_by_ticker[ticker] = [str(item) for item in row.get("alternate_tickers") or []]
    rows: list[dict[str, Any]] = []
    with universe_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            ticker = str(row.get("ticker") or "").upper()
            row = {str(k): str(v or "") for k, v in row.items()}
            row["ticker"] = ticker
            row["cik"] = cik_by_ticker.get(ticker, "")
            row["alternate_tickers"] = alternate_by_ticker.get(ticker, [])
            rows.append(row)
    return rows


def build_openfigi_jobs(universe: list[dict[str, Any]]) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for company in universe:
        exchange = str(company.get("listing_exchange") or "").upper()
        exch_code = OPENFIGI_EXCH_CODES.get(exchange)
        if not exch_code:
            continue
        ticker = str(company.get("exchange_symbol") or company.get("ticker") or "").upper()
        ticker = ticker.split(".")[0] if "." in ticker else ticker
        if not ticker:
            continue
        jobs.append(
            {
                "company": company,
                "request": {"idType": "TICKER", "idValue": ticker, "exchCode": exch_code},
            }
        )
    return jobs


def auto_targets(universe: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in universe if row.get("ticker") in AUTO_MAKE_ALIASES]


def openfda_terms(company: dict[str, Any]) -> list[str]:
    ticker = str(company.get("ticker") or "").upper()
    if ticker in OPENFDA_SPONSOR_ALIASES:
        return OPENFDA_SPONSOR_ALIASES[ticker]
    normalized = normalize_name(company.get("company_name"))
    tokens = [token.upper() for token in normalized.split() if len(token) >= 4]
    return tokens[:2]


def sponsor_query_name(company: dict[str, Any]) -> str:
    name = str(company.get("company_name") or "")
    normalized = normalize_name(name)
    if normalized:
        tokens = normalized.split()
        return " ".join(tokens[:3])
    return name


def first_distinctive_token(name: str) -> str:
    tokens = [token for token in normalize_name(name).split() if len(token) >= 2]
    return tokens[0].upper() if tokens else str(name or "").split()[0]


def make_name_matches(query_make: str, provider_make: Any) -> bool:
    query = normalize_name(query_make)
    provider = normalize_name(provider_make)
    if not query or not provider:
        return False
    if query == provider:
        return True
    query_tokens = set(query.split())
    provider_tokens = set(provider.split())
    if len(query_tokens) == 1:
        return query in provider_tokens
    return query_tokens.issubset(provider_tokens)


def match_by_normalized_name(company_name: str, rows: list[dict[str, Any]], name_key: str) -> list[dict[str, Any]]:
    company_norm = normalize_name(company_name)
    if not company_norm:
        return []
    matches = []
    for row in rows:
        row_norm = normalize_name(row.get(name_key))
        if not row_norm:
            continue
        shorter_token_count = min(len(company_norm.split()), len(row_norm.split()))
        if company_norm == row_norm or (
            len(company_norm) >= 8
            and len(row_norm) >= 8
            and shorter_token_count >= 2
            and (company_norm in row_norm or row_norm in company_norm)
        ):
            matches.append(row)
    return matches


def name_match_confidence(a: str, b: str) -> str:
    na = normalize_name(a)
    nb = normalize_name(b)
    if not na or not nb:
        return "low"
    if na == nb:
        return "high"
    shorter_token_count = min(len(na.split()), len(nb.split()))
    if len(na) >= 8 and len(nb) >= 8 and shorter_token_count >= 2 and (na in nb or nb in na):
        return "medium"
    return "low"


def confidence_rank(value: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(value, 0)


def download_dart_corp_codes(*, session: requests.Session, api_key: str, timeout_s: float) -> list[dict[str, Any]]:
    response = session.get("https://opendart.fss.or.kr/api/corpCode.xml", params={"crtfc_key": api_key}, timeout=timeout_s)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        xml_name = archive.namelist()[0]
        xml_bytes = archive.read(xml_name)
    root = ElementTree.fromstring(xml_bytes)
    rows = []
    for item in root.findall("list"):
        rows.append(
            {
                "corp_code": text_of(item, "corp_code"),
                "corp_name": text_of(item, "corp_name"),
                "stock_code": text_of(item, "stock_code"),
                "modify_date": text_of(item, "modify_date"),
            }
        )
    return rows


def download_dart_filings(*, session: requests.Session, api_key: str, corp_code: str, timeout_s: float) -> list[dict[str, Any]]:
    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bgn_de": "20240101",
        "end_de": datetime.now(timezone.utc).date().strftime("%Y%m%d"),
        "page_count": "100",
    }
    response = session.get("https://opendart.fss.or.kr/api/list.json", params=params, timeout=timeout_s)
    if response.status_code >= 400:
        return []
    payload = response.json()
    rows = payload.get("list") if isinstance(payload, dict) else []
    return rows if isinstance(rows, list) else []


def match_dart_company(company: dict[str, Any], corp_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    stock_code = normalize_stock_code(company.get("exchange_symbol"))
    if stock_code:
        for row in corp_rows:
            if normalize_stock_code(row.get("stock_code")) == stock_code:
                return row
    matches = match_by_normalized_name(company.get("company_name", ""), corp_rows, "corp_name")
    return matches[0] if matches else None


def text_of(item: ElementTree.Element, tag: str) -> str:
    child = item.find(tag)
    return child.text.strip() if child is not None and child.text else ""


def normalize_stock_code(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def normalize_name(value: Any) -> str:
    text = str(value or "").strip().lower().replace("&", " and ")
    text = re.sub(r"\b(the|class [a-z])\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    tokens = [token for token in text.split() if token and token not in LEGAL_SUFFIXES]
    return " ".join(tokens)


def entity_row(company: dict[str, Any]) -> dict[str, Any]:
    aliases = _unique([company.get("ticker"), company.get("provider_symbol"), company.get("exchange_symbol"), company.get("company_name"), *company.get("alternate_tickers", [])])
    return {
        "schema_version": SCHEMA_VERSION,
        "entity_id": f"ticker:{company['ticker']}",
        "ticker": company["ticker"],
        "cik": company.get("cik", ""),
        "company_name": company.get("company_name", ""),
        "sector": company.get("sector", ""),
        "category": company.get("category", ""),
        "country": company.get("country", ""),
        "listing_exchange": company.get("listing_exchange", ""),
        "aliases": aliases,
        "normalized_aliases": _unique([normalize_name(alias) for alias in aliases]),
    }


def mapping_row(
    source_id: str,
    company: dict[str, Any],
    *,
    external_id: str,
    external_name: str,
    identifier_type: str,
    confidence: str,
    status: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "mapping_type": identifier_type,
        "status": status,
        "confidence": confidence,
        "ticker": company.get("ticker", ""),
        "company_name": company.get("company_name", ""),
        "sector": company.get("sector", ""),
        "category": company.get("category", ""),
        "country": company.get("country", ""),
        "external_id": str(external_id or ""),
        "external_name": str(external_name or ""),
        "evidence": evidence,
    }


def gap_row(source_id: str, company: dict[str, Any], gap_type: str, detail: str, *, source_url: str = "") -> dict[str, Any]:
    return {
        "source_id": source_id,
        "gap_type": gap_type,
        "ticker": company.get("ticker", ""),
        "company_name": company.get("company_name", ""),
        "sector": company.get("sector", ""),
        "category": company.get("category", ""),
        "country": company.get("country", ""),
        "detail": detail,
        "source_url": source_url,
    }


def build_gate_row(
    source_id: str,
    *,
    result: dict[str, Any],
    before: dict[str, int],
    after: dict[str, int],
    started_at: str,
    output_dir: Path,
    skip_live: bool,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "source_id": source_id,
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "status": result.get("status", "unknown"),
        "decision": result.get("decision", "unknown"),
        "skip_live": skip_live,
        "new_endpoint_record_count": after["records"] - before["records"],
        "new_mapping_candidate_count": after["mappings"] - before["mappings"],
        "new_source_gap_count": after["gaps"] - before["gaps"],
        "result": result,
        "processed_private_output_dir": _repo_path(output_dir),
    }


def build_summary(
    *,
    universe: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    started_at: str,
    loaded_env_keys: set[str],
    output_dir: Path,
    records_path: Path,
    mappings_path: Path,
    gaps_path: Path,
    entities_path: Path,
    metadata_path: Path,
    manifest_output: Path,
    gate_output: Path,
) -> dict[str, Any]:
    status_counts = Counter(str(row.get("status") or "") for row in gate_rows)
    decision_counts = Counter(str(row.get("decision") or "") for row in gate_rows)
    ready_sources = [
        row["source_id"]
        for row in gate_rows
        if str(row.get("decision") or "").startswith("ready_")
    ]
    blocked_or_partial = [
        {"source_id": row["source_id"], "decision": row.get("decision"), "status": row.get("status")}
        for row in gate_rows
        if row["source_id"] not in ready_sources
    ]
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "pass_with_gaps" if not status_counts.get("error") else "partial_with_errors",
        "started_at": started_at,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "loaded_env_key_names": sorted(loaded_env_keys),
        "universe_company_count": len(universe),
        "source_count": len(gate_rows),
        "status_counts": dict(sorted(status_counts.items())),
        "decision_counts": dict(sorted(decision_counts.items())),
        "ready_sources": ready_sources,
        "blocked_or_partial_sources": blocked_or_partial,
        "outputs": {
            "processed_private_output_dir": _repo_path(output_dir),
            "endpoint_records": _repo_path(records_path),
            "mapping_candidates": _repo_path(mappings_path),
            "source_gaps": _repo_path(gaps_path),
            "universe_entities": _repo_path(entities_path),
            "metadata": _repo_path(metadata_path),
            "gate_rows": _repo_path(gate_output),
            "summary": _repo_path(manifest_output),
        },
        "agent_promotion_allowed": False,
        "agent_promotion_blocker": "Mapping/endpoint gates generated target-universe data, but runtime promotion still requires source-specific boundary adapters and resolver confidence thresholds.",
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _chunks(values: list[Any], size: int) -> Iterable[list[Any]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


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


def _unique(values: list[Any]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def redact_url(url: str) -> str:
    text = str(url)
    for key in SECRET_QUERY_PARAMS:
        text = re.sub(rf"([?&]{re.escape(key)}=)[^&]+", rf"\1REDACTED", text, flags=re.IGNORECASE)
    return text


def redact_text(text: str) -> str:
    return redact_url(text)


if __name__ == "__main__":
    raise SystemExit(main())
