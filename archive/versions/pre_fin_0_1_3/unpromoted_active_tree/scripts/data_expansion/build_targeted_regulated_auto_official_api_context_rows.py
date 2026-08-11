from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


SCHEMA_VERSION = "finsight_targeted_regulated_auto_official_api_context_row_v0_1"
ATTEMPT_SCHEMA_VERSION = "finsight_targeted_regulated_auto_official_api_attempt_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_targeted_regulated_auto_official_api_context_summary_v0_1"

DEFAULT_COMPANY_SOURCE_MATRIX = REPO_ROOT / "data" / "manifests" / "company_public_source_coverage_matrix_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "targeted_regulated_auto_official_api_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_ATTEMPTS = REPO_ROOT / "data" / "manifests" / "targeted_regulated_auto_official_api_attempts_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "targeted_regulated_auto_official_api_context_summary_v0_1.json"
DEFAULT_RAW_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/targeted_regulated_auto_official_api")

USER_AGENT = "FIN-Insight-Agent research data audit; public official API materialization"

AUTO_MAKE_ALIASES = {
    "1211.HK": ("BYD",),
    "F": ("Ford", "Lincoln"),
    "GM": ("Chevrolet", "Cadillac", "GMC", "Buick"),
    "HMC": ("Honda", "Acura"),
    "LCID": ("Lucid",),
    "LI": ("Li",),
    "NIO": ("NIO",),
    "RIVN": ("Rivian",),
    "TM": ("Toyota", "Lexus"),
    "TSLA": ("Tesla",),
    "XPEV": ("XPeng", "Xpeng"),
}

AUTO_MANUFACTURER_ALIASES = {
    "PCAR": ("PACCAR", "Paccar"),
}

HEALTHCARE_ALIAS_OVERRIDES = {
    "A": ("Agilent Technologies", "Agilent Technologies, Inc."),
    "ARGX": ("argenx", "argenx SE"),
    "BMY": ("Bristol Myers Squibb", "Bristol-Myers Squibb"),
    "BNTX": ("BioNTech",),
    "GEHC": ("GE HealthCare", "GE Healthcare"),
    "GSK": ("GlaxoSmithKline", "GSK"),
    "LLY": ("Eli Lilly",),
    "MRK": ("Merck Sharp Dohme", "Merck"),
    "NVO": ("Novo Nordisk",),
    "REGN": ("Regeneron",),
    "SNY": ("Sanofi",),
    "ZBH": ("Zimmer Biomet",),
}

DEVICE_510K_ALIAS_OVERRIDES = {
    "DHR": ("Beckman Coulter", "Cepheid", "Leica Biosystems", "SCIEX"),
    "MTD": ("Mettler", "Mettler Toledo"),
    "RVTY": ("PerkinElmer", "Wallac"),
    "WST": ("West Pharmaceutical", "West Pharma"),
}

FDA_ANIMAL_DRUG_SPONSOR_ALIASES = {
    "IDXX": ("IDEXX Pharmaceuticals, Inc.",),
    "ZTS": ("Zoetis Inc.",),
}

FDA_ANIMAL_DRUG_PRODUCT_SEEDS = {
    "ZTS": ("apoquel®", "Simparica TRIO®", "Cerenia® Tablets"),
}

FDA_ANIMAL_DRUG_ADVANCED_SEARCH_URL = "https://animaldrugsatfda.fda.gov/adafda/app/search/public/advancedSearch"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize targeted ClinicalTrials/openFDA/NHTSA official API rows for exact regulated/auto slots."
    )
    parser.add_argument("--company-source-matrix", type=Path, default=DEFAULT_COMPANY_SOURCE_MATRIX)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-attempts", type=Path, default=DEFAULT_OUTPUT_ATTEMPTS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--tickers", nargs="*", default=[], help="Optional ticker allowlist.")
    parser.add_argument("--timeout-s", type=float, default=20.0)
    parser.add_argument("--fetch-retries", type=int, default=1)
    parser.add_argument("--sleep-s", type=float, default=0.1)
    parser.add_argument("--max-rows-per-source", type=int, default=2)
    parser.add_argument("--replace-output", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if no rows are materialized.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    matrix_rows = _load_jsonl(args.company_source_matrix)
    result = build_targeted_regulated_auto_official_api_context_rows(
        matrix_rows=matrix_rows,
        generated_at=generated_at,
        tickers=args.tickers,
        raw_dir=args.raw_dir,
        timeout_s=args.timeout_s,
        fetch_retries=args.fetch_retries,
        sleep_s=args.sleep_s,
        max_rows_per_source=args.max_rows_per_source,
    )
    output_rows = result["rows"] if args.replace_output else _dedupe_rows([*_load_jsonl(args.output_rows), *result["rows"]])
    output_attempts = result["attempts"] if args.replace_output else _dedupe_attempts(
        [*_load_jsonl(args.output_attempts), *result["attempts"]]
    )
    summary = build_summary(
        rows=output_rows,
        attempts=output_attempts,
        matrix_rows=matrix_rows,
        generated_at=generated_at,
        output_rows=args.output_rows,
        output_attempts=args.output_attempts,
    )
    _write_jsonl(args.output_rows, output_rows)
    _write_jsonl(args.output_attempts, output_attempts)
    _write_json(args.output_summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and not result["rows"]:
        return 1
    return 0


def build_targeted_regulated_auto_official_api_context_rows(
    *,
    matrix_rows: Iterable[Mapping[str, Any]],
    generated_at: str,
    raw_dir: Path,
    tickers: Iterable[str] = (),
    timeout_s: float = 20.0,
    fetch_retries: int = 1,
    sleep_s: float = 0.1,
    max_rows_per_source: int = 2,
) -> dict[str, list[dict[str, Any]]]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    ticker_filter = {str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()}
    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    for company in matrix_rows:
        ticker = str(company.get("ticker") or "").strip().upper()
        if not ticker or (ticker_filter and ticker not in ticker_filter):
            continue
        requirements = {str(req.get("requirement_id") or "") for req in company.get("source_role_matrix") or [] if isinstance(req, Mapping)}
        if "regulated_product_context" in requirements:
            result = _fetch_regulated_rows(
                company,
                generated_at=generated_at,
                raw_dir=raw_dir,
                timeout_s=timeout_s,
                fetch_retries=fetch_retries,
                sleep_s=sleep_s,
                max_rows_per_source=max_rows_per_source,
            )
            rows.extend(result["rows"])
            attempts.extend(result["attempts"])
        if "auto_product_identity_context" in requirements:
            result = _fetch_auto_rows(
                company,
                generated_at=generated_at,
                raw_dir=raw_dir,
                timeout_s=timeout_s,
                fetch_retries=fetch_retries,
                sleep_s=sleep_s,
                max_rows_per_source=max_rows_per_source,
            )
            rows.extend(result["rows"])
            attempts.extend(result["attempts"])
    return {"rows": _dedupe_rows(rows), "attempts": attempts}


def _fetch_regulated_rows(
    company: Mapping[str, Any],
    *,
    generated_at: str,
    raw_dir: Path,
    timeout_s: float,
    fetch_retries: int,
    sleep_s: float,
    max_rows_per_source: int,
) -> dict[str, list[dict[str, Any]]]:
    ticker = str(company.get("ticker") or "").strip().upper()
    company_name = str(company.get("company_name") or ticker).strip()
    aliases = _healthcare_aliases(ticker, company_name)
    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []

    clinical_url = f"https://clinicaltrials.gov/api/v2/studies?query.spons={quote(aliases[0])}&pageSize={max_rows_per_source}"
    status, body, reason = _fetch_json_text(clinical_url, timeout_s=timeout_s, retries=fetch_retries)
    raw_path = raw_dir / "clinicaltrials" / f"{_slug(ticker)}_{_stable_digest(clinical_url)}.json"
    _write_text(raw_path, body)
    if status == "ok":
        parsed = _parse_json(body)
        studies = parsed.get("studies") if isinstance(parsed, Mapping) else []
        source_rows = _clinical_trials_rows(
            company,
            studies if isinstance(studies, list) else [],
            aliases=aliases,
            api_url=clinical_url,
            generated_at=generated_at,
            max_rows=max_rows_per_source,
        )
        rows.extend(source_rows)
        attempts.append(_attempt(ticker, "clinicaltrials_api", clinical_url, "materialized" if source_rows else "no_bound_records", raw_path=raw_path, reason="" if source_rows else "no sponsor-bound studies in returned page"))
    else:
        attempts.append(_attempt(ticker, "clinicaltrials_api", clinical_url, status, raw_path=raw_path, reason=reason))
    if sleep_s:
        time.sleep(sleep_s)

    fda_alias = aliases[0].upper()
    openfda_url = f"https://api.fda.gov/drug/drugsfda.json?search=sponsor_name:%22{quote(fda_alias)}%22&limit={max_rows_per_source}"
    status, body, reason = _fetch_json_text(openfda_url, timeout_s=timeout_s, retries=fetch_retries)
    raw_path = raw_dir / "openfda" / f"{_slug(ticker)}_{_stable_digest(openfda_url)}.json"
    _write_text(raw_path, body)
    if status == "ok":
        parsed = _parse_json(body)
        records = parsed.get("results") if isinstance(parsed, Mapping) else []
        source_rows = _openfda_rows(
            company,
            records if isinstance(records, list) else [],
            aliases=aliases,
            api_url=openfda_url,
            generated_at=generated_at,
            max_rows=max_rows_per_source,
        )
        rows.extend(source_rows)
        attempts.append(_attempt(ticker, "openfda_api", openfda_url, "materialized" if source_rows else "no_bound_records", raw_path=raw_path, reason="" if source_rows else "no sponsor-bound application records in returned page"))
    else:
        attempts.append(_attempt(ticker, "openfda_api", openfda_url, status, raw_path=raw_path, reason=reason))
    device_result = _fetch_openfda_device_510k_rows(
        company,
        generated_at=generated_at,
        raw_dir=raw_dir,
        timeout_s=timeout_s,
        fetch_retries=fetch_retries,
        sleep_s=sleep_s,
        max_rows_per_source=max_rows_per_source,
    )
    rows.extend(device_result["rows"])
    attempts.extend(device_result["attempts"])
    animal_result = _fetch_fda_animal_drug_rows(
        company,
        aliases=aliases,
        generated_at=generated_at,
        raw_dir=raw_dir,
        timeout_s=timeout_s,
        fetch_retries=fetch_retries,
        sleep_s=sleep_s,
        max_rows_per_source=max_rows_per_source,
    )
    rows.extend(animal_result["rows"])
    attempts.extend(animal_result["attempts"])
    return {"rows": rows, "attempts": attempts}


def _fetch_fda_animal_drug_rows(
    company: Mapping[str, Any],
    *,
    aliases: tuple[str, ...],
    generated_at: str,
    raw_dir: Path,
    timeout_s: float,
    fetch_retries: int,
    sleep_s: float,
    max_rows_per_source: int,
) -> dict[str, list[dict[str, Any]]]:
    ticker = str(company.get("ticker") or "").strip().upper()
    sponsor_aliases = _unique([*FDA_ANIMAL_DRUG_SPONSOR_ALIASES.get(ticker, ()), *aliases])
    if ticker not in FDA_ANIMAL_DRUG_SPONSOR_ALIASES:
        return {"rows": [], "attempts": []}
    queries: list[dict[str, Any]] = []
    for proprietary_name in FDA_ANIMAL_DRUG_PRODUCT_SEEDS.get(ticker, ()):
        queries.append({"proprietaryName": proprietary_name})
    if not queries:
        for sponsor_name in sponsor_aliases[:1]:
            queries.append({"sponsorName": sponsor_name})

    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    for query in queries:
        payload = _animal_drug_search_payload(query, page_size=max_rows_per_source)
        status, body, reason = _post_json_text(
            FDA_ANIMAL_DRUG_ADVANCED_SEARCH_URL,
            payload,
            timeout_s=timeout_s,
            retries=fetch_retries,
        )
        raw_path = raw_dir / "fda_animal_drugs" / f"{_slug(ticker)}_{_stable_digest(json.dumps(payload, sort_keys=True))}.json"
        _write_text(raw_path, body)
        if status != "ok":
            attempts.append(
                _attempt(
                    ticker,
                    "fda_animal_drugs_api",
                    FDA_ANIMAL_DRUG_ADVANCED_SEARCH_URL,
                    status,
                    raw_path=raw_path,
                    reason=reason,
                )
            )
            continue
        parsed = _parse_json(body)
        records = parsed.get("content") if isinstance(parsed, Mapping) else []
        source_rows = _fda_animal_drug_rows(
            company,
            records if isinstance(records, list) else [],
            sponsor_aliases=tuple(sponsor_aliases),
            api_url=FDA_ANIMAL_DRUG_ADVANCED_SEARCH_URL,
            query_payload=payload,
            generated_at=generated_at,
            max_rows=max_rows_per_source - len(rows),
        )
        rows.extend(source_rows)
        attempts.append(
            _attempt(
                ticker,
                "fda_animal_drugs_api",
                FDA_ANIMAL_DRUG_ADVANCED_SEARCH_URL,
                "materialized" if source_rows else "no_bound_records",
                raw_path=raw_path,
                reason="" if source_rows else "Animal Drugs @ FDA returned no sponsor-bound product applications for configured query.",
                result_count=int(parsed.get("totalElements") or 0) if isinstance(parsed, Mapping) else 0,
                parsed_row_count=len(source_rows),
            )
        )
        if len(rows) >= max_rows_per_source:
            break
        if sleep_s:
            time.sleep(sleep_s)
    return {"rows": rows, "attempts": attempts}


def _animal_drug_search_payload(query: Mapping[str, Any], *, page_size: int) -> dict[str, Any]:
    payload = {
        "basicSearchTerm": None,
        "applicationNumber": None,
        "sponsorName": None,
        "activeIngredientName": None,
        "applicationStatusCode": None,
        "applicationStatusValue": None,
        "indication": None,
        "proprietaryName": None,
        "doseFormName": None,
        "routeName": None,
        "speciesName": None,
        "isExact": False,
        "sortField": "applicationNumber",
        "sortDirection": "false",
        "pageSize": max(1, int(page_size or 1)),
        "pageNumber": 1,
    }
    for key, value in query.items():
        if key in payload:
            payload[key] = value
    return payload


def _fda_animal_drug_rows(
    company: Mapping[str, Any],
    records: list[Any],
    *,
    sponsor_aliases: tuple[str, ...],
    api_url: str,
    query_payload: Mapping[str, Any],
    generated_at: str,
    max_rows: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if max_rows <= 0:
        return out
    for record in records:
        if not isinstance(record, Mapping):
            continue
        sponsor = str(record.get("sponsorName") or "").strip()
        if not _alias_matches(sponsor, sponsor_aliases):
            continue
        application_number = str(record.get("applicationNumber") or "").strip()
        application_type = str(record.get("applicationType") or "").strip()
        application_id = str(record.get("applicationId") or "").strip()
        proprietary_name = str(record.get("proprietaryName") or "").strip()
        active_ingredient = str(record.get("activeIngredientName") or "").strip()
        status_code = str(record.get("applicationStatusCode") or "").strip()
        status = {
            "A": "Approved",
            "W": "Withdrawn",
            "V": "Voluntarily withdrawn",
        }.get(status_code, status_code)
        record_id = f"{application_type}{application_number}" if application_number else application_id
        period = _date_from_epoch_millis(record.get("publishDate"))
        row = _regulated_row(
            company,
            source_id="fda_animal_drugs_api",
            api_url=api_url,
            generated_at=generated_at,
            product_or_segment=proprietary_name or active_ingredient or record_id,
            fact_label=f"{record_id} {proprietary_name}".strip(),
            record_id=record_id,
            application_number=record_id,
            metric_name="FDA_ANIMAL_DRUG_APPLICATION",
            period=period,
            status=status,
            source_entity_name=sponsor,
            source_specific_parser="fda_animal_drugs_advanced_search_sponsor_product_parser_v0_1",
        )
        row["active_ingredient_name"] = active_ingredient
        row["application_status_code"] = status_code
        row["application_id"] = application_id
        row["query_payload"] = dict(query_payload)
        row["claim_boundary"] = (
            "Animal Drugs @ FDA / Green Book application context only; no sales, utilization, prescribing, safety incidence, "
            "market share, or approval-success inference."
        )
        row["authority_boundary"] = row["claim_boundary"]
        row["forbidden_claims"] = [
            "approval_success",
            "sales",
            "market_share",
            "utilization_share",
            "prescription_volume",
            "safety_incidence",
        ]
        row["text"] = (
            f"FDA Animal Drugs @ FDA regulated product context for {row['ticker']}: issuer={sponsor}; "
            f"application={record_id}; product={proprietary_name}; active_ingredient={active_ingredient}; "
            f"status={status}; publish_date={period}."
        )
        row["preview"] = row["text"]
        out.append(row)
        if len(out) >= max_rows:
            break
    return out


def _fetch_openfda_device_510k_rows(
    company: Mapping[str, Any],
    *,
    generated_at: str,
    raw_dir: Path,
    timeout_s: float,
    fetch_retries: int,
    sleep_s: float,
    max_rows_per_source: int,
) -> dict[str, list[dict[str, Any]]]:
    ticker = str(company.get("ticker") or "").strip().upper()
    aliases = tuple(DEVICE_510K_ALIAS_OVERRIDES.get(ticker, ()))
    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    if not aliases:
        return {"rows": rows, "attempts": attempts}
    for alias in aliases:
        url = f"https://api.fda.gov/device/510k.json?search=applicant:%22{quote(alias.upper())}%22&limit={max_rows_per_source}"
        status, body, reason = _fetch_json_text(url, timeout_s=timeout_s, retries=fetch_retries)
        raw_path = raw_dir / "openfda_device_510k" / f"{_slug(ticker)}_{_slug(alias)}_{_stable_digest(url)}.json"
        _write_text(raw_path, body)
        if status == "ok":
            parsed = _parse_json(body)
            records = parsed.get("results") if isinstance(parsed, Mapping) else []
            source_rows = _openfda_device_510k_rows(
                company,
                records if isinstance(records, list) else [],
                aliases=(alias,),
                api_url=url,
                generated_at=generated_at,
                max_rows=max_rows_per_source - len(rows),
            )
            rows.extend(source_rows)
            attempts.append(
                _attempt(
                    ticker,
                    "openfda_api",
                    url,
                    "materialized" if source_rows else "no_bound_records",
                    raw_path=raw_path,
                    reason="" if source_rows else f"no applicant-bound 510(k) records for alias={alias}",
                )
            )
        else:
            attempts.append(_attempt(ticker, "openfda_api", url, status, raw_path=raw_path, reason=reason))
        if sleep_s:
            time.sleep(sleep_s)
        if len(rows) >= max_rows_per_source:
            break
    return {"rows": rows[:max_rows_per_source], "attempts": attempts}


def _fetch_auto_rows(
    company: Mapping[str, Any],
    *,
    generated_at: str,
    raw_dir: Path,
    timeout_s: float,
    fetch_retries: int,
    sleep_s: float,
    max_rows_per_source: int,
) -> dict[str, list[dict[str, Any]]]:
    ticker = str(company.get("ticker") or "").strip().upper()
    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    aliases = AUTO_MAKE_ALIASES.get(ticker, ())
    manufacturer_aliases = AUTO_MANUFACTURER_ALIASES.get(ticker, ())
    if not aliases:
        if manufacturer_aliases:
            return _fetch_nhtsa_manufacturer_rows(
                company,
                manufacturer_aliases=manufacturer_aliases,
                generated_at=generated_at,
                raw_dir=raw_dir,
                timeout_s=timeout_s,
                fetch_retries=fetch_retries,
                sleep_s=sleep_s,
                max_rows_per_source=max_rows_per_source,
            )
        attempts.append(
            _attempt(
                ticker,
                "nhtsa_vpic_api",
                "",
                "not_applicable_or_make_alias_missing",
                reason="No configured vehicle make or manufacturer alias for this issuer; do not fabricate NHTSA identity slot.",
            )
        )
        return {"rows": rows, "attempts": attempts}
    for make in aliases:
        url = f"https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMake/{quote(make)}?format=json"
        status, body, reason = _fetch_json_text(url, timeout_s=timeout_s, retries=fetch_retries)
        raw_path = raw_dir / "nhtsa" / f"{_slug(ticker)}_{_slug(make)}.json"
        _write_text(raw_path, body)
        if status == "ok":
            parsed = _parse_json(body)
            records = parsed.get("Results") if isinstance(parsed, Mapping) else []
            source_rows = _nhtsa_rows(
                company,
                records if isinstance(records, list) else [],
                make=make,
                api_url=url,
                generated_at=generated_at,
                max_rows=max_rows_per_source,
            )
            rows.extend(source_rows)
            attempts.append(_attempt(ticker, "nhtsa_vpic_api", url, "materialized" if source_rows else "no_bound_records", raw_path=raw_path, reason="" if source_rows else "no model rows returned"))
        else:
            attempts.append(_attempt(ticker, "nhtsa_vpic_api", url, status, raw_path=raw_path, reason=reason))
        if sleep_s:
            time.sleep(sleep_s)
        if len(rows) >= max_rows_per_source:
            break
    return {"rows": rows[:max_rows_per_source], "attempts": attempts}


def _fetch_nhtsa_manufacturer_rows(
    company: Mapping[str, Any],
    *,
    manufacturer_aliases: tuple[str, ...],
    generated_at: str,
    raw_dir: Path,
    timeout_s: float,
    fetch_retries: int,
    sleep_s: float,
    max_rows_per_source: int,
) -> dict[str, list[dict[str, Any]]]:
    ticker = str(company.get("ticker") or "").strip().upper()
    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    for alias in manufacturer_aliases:
        url = f"https://vpic.nhtsa.dot.gov/api/vehicles/GetManufacturerDetails/{quote(alias)}?format=json"
        status, body, reason = _fetch_json_text(url, timeout_s=timeout_s, retries=fetch_retries)
        raw_path = raw_dir / "nhtsa_manufacturer" / f"{_slug(ticker)}_{_slug(alias)}.json"
        _write_text(raw_path, body)
        if status == "ok":
            parsed = _parse_json(body)
            records = parsed.get("Results") if isinstance(parsed, Mapping) else []
            source_rows = _nhtsa_manufacturer_rows(
                company,
                records if isinstance(records, list) else [],
                alias=alias,
                api_url=url,
                generated_at=generated_at,
                max_rows=max_rows_per_source - len(rows),
            )
            rows.extend(source_rows)
            attempts.append(
                _attempt(
                    ticker,
                    "nhtsa_vpic_api",
                    url,
                    "materialized" if source_rows else "no_bound_records",
                    raw_path=raw_path,
                    reason="" if source_rows else f"no manufacturer-bound NHTSA rows for alias={alias}",
                )
            )
        else:
            attempts.append(_attempt(ticker, "nhtsa_vpic_api", url, status, raw_path=raw_path, reason=reason))
        if sleep_s:
            time.sleep(sleep_s)
        if len(rows) >= max_rows_per_source:
            break
    return {"rows": rows[:max_rows_per_source], "attempts": attempts}


def _clinical_trials_rows(
    company: Mapping[str, Any],
    studies: list[Any],
    *,
    aliases: tuple[str, ...],
    api_url: str,
    generated_at: str,
    max_rows: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for study in studies:
        if not isinstance(study, Mapping):
            continue
        protocol = study.get("protocolSection") if isinstance(study.get("protocolSection"), Mapping) else {}
        ident = protocol.get("identificationModule") if isinstance(protocol.get("identificationModule"), Mapping) else {}
        status = protocol.get("statusModule") if isinstance(protocol.get("statusModule"), Mapping) else {}
        sponsor = protocol.get("sponsorCollaboratorsModule") if isinstance(protocol.get("sponsorCollaboratorsModule"), Mapping) else {}
        sponsor_name = _clinical_trial_bound_sponsor_name(sponsor, aliases)
        if not sponsor_name:
            organization_name = (
                (ident.get("organization") or {}).get("fullName") if isinstance(ident.get("organization"), Mapping) else ""
            )
            sponsor_name = organization_name if _alias_matches(str(organization_name or ""), aliases) else ""
        if not sponsor_name:
            continue
        nct_id = str(ident.get("nctId") or "").strip()
        title = str(ident.get("briefTitle") or ident.get("officialTitle") or nct_id).strip()
        period = _first_text(
            status.get("startDateStruct", {}).get("date") if isinstance(status.get("startDateStruct"), Mapping) else "",
            status.get("statusVerifiedDate"),
        )
        fact_label = f"{nct_id} {title}".strip()
        out.append(
            _regulated_row(
                company,
                source_id="clinicaltrials_api",
                api_url=api_url,
                generated_at=generated_at,
                product_or_segment=title,
                fact_label=fact_label,
                record_id=nct_id,
                trial_id=nct_id,
                metric_name="NCT_ID",
                period=period,
                status=str(status.get("overallStatus") or ""),
                source_entity_name=sponsor_name,
            )
        )
        if len(out) >= max_rows:
            break
    return out


def _clinical_trial_bound_sponsor_name(sponsor_module: Mapping[str, Any], aliases: Iterable[str]) -> str:
    lead = sponsor_module.get("leadSponsor") if isinstance(sponsor_module.get("leadSponsor"), Mapping) else {}
    lead_name = str(lead.get("name") or "").strip()
    if _alias_matches(lead_name, aliases):
        return lead_name
    collaborators = sponsor_module.get("collaborators")
    for collaborator in collaborators if isinstance(collaborators, list) else []:
        if not isinstance(collaborator, Mapping):
            continue
        name = str(collaborator.get("name") or "").strip()
        if _alias_matches(name, aliases):
            return name
    return ""


def _openfda_rows(
    company: Mapping[str, Any],
    records: list[Any],
    *,
    aliases: tuple[str, ...],
    api_url: str,
    generated_at: str,
    max_rows: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, Mapping):
            continue
        sponsor = str(record.get("sponsor_name") or "").strip()
        if not _alias_matches(sponsor, aliases):
            continue
        app_no = str(record.get("application_number") or "").strip()
        products = record.get("products") if isinstance(record.get("products"), list) else []
        product_name = ""
        for product in products:
            if isinstance(product, Mapping) and str(product.get("brand_name") or "").strip():
                product_name = str(product.get("brand_name") or "").strip()
                break
        product_name = product_name or app_no
        submissions = record.get("submissions") if isinstance(record.get("submissions"), list) else []
        submission_status = ""
        submission_date = ""
        if submissions and isinstance(submissions[0], Mapping):
            submission_status = str(submissions[0].get("submission_status") or "")
            submission_date = str(submissions[0].get("submission_status_date") or "")
        out.append(
            _regulated_row(
                company,
                source_id="openfda_api",
                api_url=api_url,
                generated_at=generated_at,
                product_or_segment=product_name,
                fact_label=f"{app_no} {product_name}".strip(),
                record_id=app_no,
                application_number=app_no,
                metric_name="FDA_APPLICATION_NUMBER",
                period=submission_date,
                status=submission_status,
                source_entity_name=sponsor,
            )
        )
        if len(out) >= max_rows:
            break
    return out


def _openfda_device_510k_rows(
    company: Mapping[str, Any],
    records: list[Any],
    *,
    aliases: tuple[str, ...],
    api_url: str,
    generated_at: str,
    max_rows: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if max_rows <= 0:
        return out
    for record in records:
        if not isinstance(record, Mapping):
            continue
        applicant = str(record.get("applicant") or "").strip()
        if not _alias_matches(applicant, aliases):
            continue
        k_number = str(record.get("k_number") or "").strip()
        product_code = str(record.get("product_code") or "").strip()
        openfda = record.get("openfda") if isinstance(record.get("openfda"), Mapping) else {}
        device_name = str(record.get("device_name") or openfda.get("device_name") or product_code or k_number).strip()
        decision_date = str(record.get("decision_date") or "").strip()
        decision = str(record.get("decision_description") or record.get("decision_code") or "").strip()
        out.append(
            _regulated_row(
                company,
                source_id="openfda_api",
                api_url=api_url,
                generated_at=generated_at,
                product_or_segment=device_name,
                fact_label=f"{k_number} {device_name}".strip(),
                record_id=k_number or product_code,
                application_number=k_number,
                device_id=product_code,
                metric_name="FDA_DEVICE_510K_NUMBER",
                period=decision_date,
                status=decision,
                source_entity_name=applicant,
                source_specific_parser="targeted_openfda_device_510k_applicant_product_parser_v0_1",
            )
        )
        if len(out) >= max_rows:
            break
    return out


def _nhtsa_rows(
    company: Mapping[str, Any],
    records: list[Any],
    *,
    make: str,
    api_url: str,
    generated_at: str,
    max_rows: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, Mapping):
            continue
        model = str(record.get("Model_Name") or "").strip()
        make_name = str(record.get("Make_Name") or make).strip()
        if not model:
            continue
        ticker = str(company.get("ticker") or "").strip().upper()
        evidence_ref = _stable_ref("targeted_nhtsa_vpic", [ticker, make_name, model, record.get("Model_ID")])
        out.append(
            {
                "schema_version": SCHEMA_VERSION,
                "evidence_ref": evidence_ref,
                "evidence_id": evidence_ref,
                "source_id": "nhtsa_vpic_api",
                "underlying_source_id": "nhtsa_vpic_api",
                "source_class": "nhtsa_vpic_api",
                "source_family": "public_source_context",
                "runtime_source_family": "public_source_context",
                "source_layer_id": "L2",
                "source_layer": "L2",
                "layer_id": "L2",
                "source_specific_parser": "targeted_nhtsa_vpic_make_model_parser_v0_1",
                "source_specific_resolver": "targeted_nhtsa_make_to_issuer_resolver_v0_1",
                "parser_status": "source_specific_context_parser_pass",
                "structured_fact_status": "bounded_context_fact_materialized",
                "runtime_ready_context": True,
                "bounded_structured_context": True,
                "structured_context_type": "vehicle_model_identity_context",
                "requirement_id": "auto_product_identity_context",
                "ticker": ticker,
                "company": company.get("company_name") or "",
                "company_name": company.get("company_name") or "",
                "source_url": api_url,
                "api_route": api_url,
                "citation": {"url": api_url, "record_id": evidence_ref, "title": f"NHTSA {make_name} {model}"},
                "make": make_name,
                "model": model,
                "manufacturer": make_name,
                "fact_label": f"{make_name} {model}",
                "product_or_segment": model,
                "metric_name": "NHTSA_MAKE_MODEL",
                "identifier": f"{make_name}:{model}",
                "identifier_type": "NHTSA_MAKE_MODEL",
                "as_of_datetime": generated_at,
                "issuer_binding_status": "issuer_mentioned_in_snapshot",
                "product_binding_status": "product_mentioned_in_snapshot",
                "counterparty_binding_status": "not_bound",
                "entity_binding": {
                    "issuer_ticker": ticker,
                    "issuer_binding_status": "issuer_mentioned_in_snapshot",
                    "product_binding_status": "product_mentioned_in_snapshot",
                    "counterparty_binding_status": "not_bound",
                    "resolver_status": "issuer_product_bound",
                    "binding_claim_boundary": "NHTSA make/model identity only; no sales, registration, or profitability inference.",
                },
                "resolver_status": "issuer_product_bound",
                "resolver_reason": "configured_make_alias_returned_nhtsa_models",
                "context_only": True,
                "exact_value_authority": False,
                "can_support_company_exact_fact": False,
                "allowed_claims": ["auto_product_identity_context", "official_product_identity_context"],
                "forbidden_claims": ["vehicle_sales", "market_share", "profitability", "registrations"],
                "claim_boundary": "NHTSA/vPIC make-model identity context only; no vehicle sales, registrations, share, or profitability claims.",
                "text": f"NHTSA model identity for {ticker}: make={make_name}; model={model}; source={api_url}",
                "preview": f"NHTSA model identity for {ticker}: make={make_name}; model={model}; source={api_url}",
            }
        )
        if len(out) >= max_rows:
            break
    return out


def _nhtsa_manufacturer_rows(
    company: Mapping[str, Any],
    records: list[Any],
    *,
    alias: str,
    api_url: str,
    generated_at: str,
    max_rows: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if max_rows <= 0:
        return out
    for record in records:
        if not isinstance(record, Mapping):
            continue
        manufacturer = str(record.get("Mfr_Name") or "").strip()
        if not manufacturer or not _alias_matches(manufacturer, (alias,)):
            continue
        vehicle_types = record.get("VehicleTypes") if isinstance(record.get("VehicleTypes"), list) else []
        vehicle_type = ""
        for item in vehicle_types:
            if isinstance(item, Mapping) and str(item.get("Name") or "").strip():
                vehicle_type = str(item.get("Name") or "").strip()
                break
        ticker = str(company.get("ticker") or "").strip().upper()
        evidence_ref = _stable_ref("targeted_nhtsa_vpic_manufacturer", [ticker, manufacturer, vehicle_type])
        fact_label = f"{manufacturer} {vehicle_type or 'vehicle manufacturer'}".strip()
        out.append(
            {
                "schema_version": SCHEMA_VERSION,
                "evidence_ref": evidence_ref,
                "evidence_id": evidence_ref,
                "source_id": "nhtsa_vpic_api",
                "underlying_source_id": "nhtsa_vpic_api",
                "source_class": "nhtsa_vpic_api",
                "source_family": "public_source_context",
                "runtime_source_family": "public_source_context",
                "source_layer_id": "L2",
                "source_layer": "L2",
                "layer_id": "L2",
                "source_specific_parser": "targeted_nhtsa_vpic_manufacturer_identity_parser_v0_1",
                "source_specific_resolver": "targeted_nhtsa_manufacturer_to_issuer_resolver_v0_1",
                "parser_status": "source_specific_context_parser_pass",
                "structured_fact_status": "bounded_context_fact_materialized",
                "runtime_ready_context": True,
                "bounded_structured_context": True,
                "structured_context_type": "vehicle_manufacturer_identity_context",
                "requirement_id": "auto_product_identity_context",
                "ticker": ticker,
                "company": company.get("company_name") or "",
                "company_name": company.get("company_name") or "",
                "source_url": api_url,
                "api_route": api_url,
                "citation": {"url": api_url, "record_id": evidence_ref, "title": fact_label},
                "make": alias.upper(),
                "manufacturer": manufacturer,
                "product_or_segment": vehicle_type or "Vehicle manufacturer",
                "fact_label": fact_label,
                "metric_name": "NHTSA_MANUFACTURER_DETAILS",
                "identifier": f"{manufacturer}:{vehicle_type}",
                "identifier_type": "NHTSA_MANUFACTURER_DETAILS",
                "as_of_datetime": generated_at,
                "issuer_binding_status": "issuer_mentioned_in_snapshot",
                "product_binding_status": "product_mentioned_in_snapshot",
                "counterparty_binding_status": "not_bound",
                "entity_binding": {
                    "issuer_ticker": ticker,
                    "issuer_binding_status": "issuer_mentioned_in_snapshot",
                    "product_binding_status": "product_mentioned_in_snapshot",
                    "counterparty_binding_status": "not_bound",
                    "resolver_status": "issuer_product_bound",
                    "binding_claim_boundary": "NHTSA manufacturer identity only; no sales, registration, or profitability inference.",
                },
                "resolver_status": "issuer_product_bound",
                "resolver_reason": "configured_manufacturer_alias_returned_nhtsa_manufacturer_details",
                "context_only": True,
                "exact_value_authority": False,
                "can_support_company_exact_fact": False,
                "allowed_claims": ["auto_product_identity_context", "official_product_identity_context"],
                "forbidden_claims": ["vehicle_sales", "market_share", "profitability", "registrations"],
                "claim_boundary": "NHTSA/vPIC manufacturer identity context only; no vehicle sales, registrations, share, or profitability claims.",
                "text": f"NHTSA manufacturer identity for {ticker}: manufacturer={manufacturer}; vehicle_type={vehicle_type}; source={api_url}",
                "preview": f"NHTSA manufacturer identity for {ticker}: manufacturer={manufacturer}; vehicle_type={vehicle_type}; source={api_url}",
            }
        )
        if len(out) >= max_rows:
            break
    return out


def _regulated_row(
    company: Mapping[str, Any],
    *,
    source_id: str,
    api_url: str,
    generated_at: str,
    product_or_segment: str,
    fact_label: str,
    record_id: str,
    metric_name: str,
    period: str,
    status: str,
    source_entity_name: str,
    trial_id: str = "",
    application_number: str = "",
    device_id: str = "",
    source_specific_parser: str = "",
) -> dict[str, Any]:
    ticker = str(company.get("ticker") or "").strip().upper()
    evidence_ref = _stable_ref(f"targeted_{source_id}", [ticker, record_id, product_or_segment])
    text = (
        f"{source_id} regulated product context for {ticker}: issuer={source_entity_name}; "
        f"product={product_or_segment}; record={record_id}; status={status}; period={period}."
    )
    row = {
        "schema_version": SCHEMA_VERSION,
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "record_id": record_id,
        "source_id": source_id,
        "underlying_source_id": source_id,
        "source_class": source_id,
        "source_family": "public_source_context",
        "runtime_source_family": "public_source_context",
        "source_layer_id": "L2",
        "source_layer": "L2",
        "layer_id": "L2",
        "source_specific_parser": source_specific_parser or f"targeted_{source_id}_issuer_product_parser_v0_1",
        "source_specific_resolver": f"targeted_{source_id}_issuer_product_resolver_v0_1",
        "parser_status": "source_specific_context_parser_pass",
        "structured_fact_status": "bounded_context_fact_materialized",
        "runtime_ready_context": True,
        "bounded_structured_context": True,
        "structured_context_type": "regulated_product_context",
        "requirement_id": "regulated_product_context",
        "ticker": ticker,
        "company": company.get("company_name") or "",
        "company_name": company.get("company_name") or "",
        "source_entity_name": source_entity_name,
        "source_url": api_url,
        "api_route": api_url,
        "citation": {"url": api_url, "record_id": record_id, "title": fact_label},
        "fact_label": fact_label,
        "product_or_segment": product_or_segment,
        "product_family": product_or_segment,
        "metric_name": metric_name,
        "period": period,
        "status": status,
        "as_of_datetime": generated_at,
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "product_binding_status": "product_mentioned_in_snapshot",
        "counterparty_binding_status": "not_bound",
        "entity_binding": {
            "issuer_ticker": ticker,
            "issuer_binding_status": "issuer_mentioned_in_snapshot",
            "product_binding_status": "product_mentioned_in_snapshot",
            "counterparty_binding_status": "not_bound",
            "resolver_status": "issuer_product_bound",
            "binding_claim_boundary": "Regulatory product/trial/application record only; no sales, approval success, utilization, or market share inference.",
        },
        "resolver_status": "issuer_product_bound",
        "resolver_reason": "official_api_record_bound_by_company_alias_and_product_record",
        "context_only": True,
        "exact_value_authority": False,
        "can_support_company_exact_fact": False,
        "allowed_claims": ["regulated_product_context", "trial_or_regulatory_status_context", "verification_lead"],
        "forbidden_claims": ["approval_success", "sales", "market_share", "utilization_share", "prescription_volume"],
        "claim_boundary": "Regulatory record supports product/trial/application existence and status context only.",
        "text": text,
        "preview": text,
    }
    if trial_id:
        row["trial_id"] = trial_id
    if application_number:
        row["application_number"] = application_number
    if device_id:
        row["device_id"] = device_id
    return row


def build_summary(
    *,
    rows: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    matrix_rows: list[dict[str, Any]],
    generated_at: str,
    output_rows: Path,
    output_attempts: Path,
) -> dict[str, Any]:
    required_tickers = {
        str(row.get("ticker") or "").upper()
        for row in matrix_rows
        for req in row.get("source_role_matrix") or []
        if isinstance(req, Mapping) and str(req.get("requirement_id") or "") in {"regulated_product_context", "auto_product_identity_context"}
    }
    success_tickers = {str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")}
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if rows else "gap",
        "required_ticker_count": len(required_tickers),
        "success_ticker_count": len(success_tickers),
        "unmaterialized_ticker_count": len(required_tickers - success_tickers),
        "row_count": len(rows),
        "attempt_count": len(attempts),
        "row_source_counts": dict(sorted(Counter(str(row.get("source_id") or "") for row in rows).items())),
        "attempt_status_counts": dict(sorted(Counter(str(row.get("status") or "") for row in attempts).items())),
        "unmaterialized_tickers": sorted(required_tickers - success_tickers),
        "outputs": {"rows": str(output_rows), "attempts": str(output_attempts)},
        "boundary": "Only sponsor/collaborator/applicant-bound ClinicalTrials/openFDA records and configured NHTSA make-model rows are promoted. No approval success, sales, utilization, registrations, share, or profitability claims.",
    }


def _healthcare_aliases(ticker: str, company_name: str) -> tuple[str, ...]:
    values = [*HEALTHCARE_ALIAS_OVERRIDES.get(ticker, ()), company_name, _simplify_company_name(company_name)]
    return tuple(_unique(value for value in values if value))


def _fetch_json_text(url: str, *, timeout_s: float, retries: int) -> tuple[str, str, str]:
    last_reason = ""
    for attempt in range(max(1, retries + 1)):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urlopen(request, timeout=timeout_s) as response:
                body = response.read().decode("utf-8", errors="ignore")
                if response.status >= 400:
                    return f"http_{response.status}", body, f"http_{response.status}"
                return "ok", body, ""
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else ""
            if exc.code == 404:
                return "no_results_or_http_404", body, "http_404"
            last_reason = f"HTTPError:{exc.code}"
        except (URLError, TimeoutError) as exc:
            last_reason = f"{type(exc).__name__}:{str(exc)[:200]}"
        except Exception as exc:  # noqa: BLE001
            last_reason = f"{type(exc).__name__}:{str(exc)[:200]}"
        if attempt < retries:
            time.sleep(0.5 * (attempt + 1))
    return "fetch_failed", "", last_reason


def _post_json_text(url: str, payload: Mapping[str, Any], *, timeout_s: float, retries: int) -> tuple[str, str, str]:
    last_reason = ""
    body_bytes = json.dumps(dict(payload), ensure_ascii=False).encode("utf-8")
    for attempt in range(max(1, retries + 1)):
        try:
            request = Request(
                url,
                data=body_bytes,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json", "Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=timeout_s) as response:
                body = response.read().decode("utf-8", errors="ignore")
                if response.status >= 400:
                    return f"http_{response.status}", body, f"http_{response.status}"
                return "ok", body, ""
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else ""
            if exc.code == 404:
                return "no_results_or_http_404", body, "http_404"
            last_reason = f"HTTPError:{exc.code}"
        except (URLError, TimeoutError) as exc:
            last_reason = f"{type(exc).__name__}:{str(exc)[:200]}"
        except Exception as exc:  # noqa: BLE001
            last_reason = f"{type(exc).__name__}:{str(exc)[:200]}"
        if attempt < retries:
            time.sleep(0.5 * (attempt + 1))
    return "fetch_failed", "", last_reason


def _parse_json(text: str) -> dict[str, Any]:
    if not text.strip():
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _attempt(
    ticker: str,
    source_id: str,
    url: str,
    status: str,
    *,
    raw_path: Path | str = "",
    reason: str = "",
    result_count: int | None = None,
    parsed_row_count: int | None = None,
) -> dict[str, Any]:
    row = {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "attempt_id": _stable_ref("targeted_official_api_attempt", [ticker, source_id, url, status, reason]),
        "ticker": ticker,
        "source_id": source_id,
        "source_url": url,
        "status": status,
        "raw_path": str(raw_path) if raw_path else "",
        "reason": reason,
    }
    if result_count is not None:
        row["result_count"] = result_count
    if parsed_row_count is not None:
        row["parsed_row_count"] = parsed_row_count
    return row


def _alias_matches(value: str, aliases: Iterable[str]) -> bool:
    norm = _normalize(value)
    if not norm:
        return False
    for alias in aliases:
        alias_norm = _normalize(alias)
        if alias_norm and (alias_norm in norm or norm in alias_norm):
            return True
    return False


def _simplify_company_name(value: str) -> str:
    text = re.split(r"[,(/-]", value, maxsplit=1)[0].strip()
    return re.sub(
        r"\b(inc|incorporated|corp|corporation|co|company|ltd|limited|plc|se|sa|nv|ag|llc|the)\b\.?",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()


def _normalize(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
    text = re.sub(r"\b(inc|incorporated|corp|corporation|co|company|ltd|limited|plc|se|sa|nv|ag|llc|the|class a|class b)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        key = _normalize(text)
        if not text or key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            value = json.loads(text)
            if isinstance(value, Mapping):
                rows.append(dict(value))
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text or "", encoding="utf-8")


def _dedupe_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.get("evidence_ref") or row.get("evidence_id") or "")
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    return out


def _dedupe_attempts(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.get("attempt_id") or "")
        if not key:
            key = "|".join(
                str(row.get(field) or "")
                for field in ("ticker", "source_id", "source_url", "status", "reason", "raw_path")
            )
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    return out


def _slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", str(value or "").lower()).strip("_")
    return text[:80] or "unknown"


def _stable_digest(value: str) -> str:
    return hashlib.sha1(str(value or "").encode("utf-8", errors="ignore")).hexdigest()[:16]


def _stable_ref(prefix: str, parts: Iterable[Any]) -> str:
    digest = hashlib.sha1("|".join(str(part or "") for part in parts).encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _date_from_epoch_millis(value: Any) -> str:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return ""
    if number <= 0:
        return ""
    return datetime.fromtimestamp(number / 1000, tz=timezone.utc).date().isoformat()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
