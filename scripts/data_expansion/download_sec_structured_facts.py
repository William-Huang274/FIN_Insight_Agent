from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import requests
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_PLAN = REPO_ROOT / "data" / "manifests" / "structured_financial_fact_source_plan_v0_1.jsonl"
DEFAULT_CONFIG = REPO_ROOT / "configs" / "data_sources" / "structured_financial_fact_sources_v0_1.yaml"
DEFAULT_FACT_OUTPUT = REPO_ROOT / "data" / "staging" / "structured_financial_facts" / "sec_companyfacts_financial_fact_rows_v0_1.jsonl"
DEFAULT_SUBMISSIONS_OUTPUT = REPO_ROOT / "data" / "staging" / "structured_financial_facts" / "sec_submissions_filing_rows_v0_1.jsonl"
DEFAULT_SUMMARY_OUTPUT = REPO_ROOT / "data" / "manifests" / "sec_structured_facts_download_summary_v0_1.json"
FACT_ROW_SCHEMA_VERSION = "fin_agent_sec_companyfacts_financial_fact_row_v0.1"
SUBMISSION_ROW_SCHEMA_VERSION = "fin_agent_sec_submissions_filing_row_v0.1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download SEC CompanyFacts/Submissions and normalize staging fact rows.")
    parser.add_argument("--source-plan", type=Path, default=DEFAULT_SOURCE_PLAN)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--fact-output", type=Path, default=DEFAULT_FACT_OUTPUT)
    parser.add_argument("--submissions-output", type=Path, default=DEFAULT_SUBMISSIONS_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--tickers", default="", help="Optional comma-separated ticker filter.")
    parser.add_argument("--years", default="", help="Comma-separated fiscal years. Defaults to config.default_years.")
    parser.add_argument("--forms", default="10-K,10-Q,20-F,40-F", help="Comma-separated form filter for normalized rows.")
    parser.add_argument("--limit-companies", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--refresh", action="store_true", help="Re-download even if raw JSON already exists.")
    parser.add_argument("--user-agent", default=os.getenv("SEC_USER_AGENT") or "FinSight-Agent/0.1 structured-facts contact@example.com")
    parser.add_argument("--rate-limit", type=float, default=8.0)
    parser.add_argument("--timeout", type=int, default=30)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = _load_yaml(_resolve(args.config))
    years = _parse_int_csv(args.years) or [int(year) for year in config.get("default_years") or []]
    forms = {form.upper() for form in _parse_str_csv(args.forms)}
    ticker_filter = {ticker.upper() for ticker in _parse_str_csv(args.tickers)}
    plan_rows = _load_jsonl(_resolve(args.source_plan))
    grouped = group_sec_structured_fact_plan_rows(plan_rows, ticker_filter=ticker_filter)
    if args.limit_companies:
        grouped = dict(list(grouped.items())[: int(args.limit_companies)])

    if args.dry_run:
        summary = {
            "schema_version": "fin_agent_sec_structured_facts_download_summary_v0.1",
            "status": "dry_run",
            "company_count": len(grouped),
            "tickers": sorted(grouped),
            "years": years,
            "forms": sorted(forms),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    client = SecStructuredFactsClient(
        user_agent=args.user_agent,
        timeout=int(args.timeout),
        rate_limit=float(args.rate_limit),
    )
    fact_output = _resolve(args.fact_output)
    submissions_output = _resolve(args.submissions_output)
    summary_output = _resolve(args.summary_output)
    fact_output.parent.mkdir(parents=True, exist_ok=True)
    submissions_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)

    issues: list[dict[str, Any]] = []
    company_count = 0
    companyfacts_payloads = 0
    submissions_payloads = 0
    fact_rows = 0
    submission_rows = 0
    source_family_counts: Counter[str] = Counter()
    form_counts: Counter[str] = Counter()
    concept_counts: Counter[str] = Counter()
    ticker_fact_counts: Counter[str] = Counter()

    with fact_output.open("w", encoding="utf-8", newline="\n") as fact_handle, submissions_output.open("w", encoding="utf-8", newline="\n") as submission_handle:
        for ticker, rows in grouped.items():
            company_count += 1
            company_plan = select_company_plan_rows(rows)
            try:
                if company_plan.get("companyfacts"):
                    payload, metadata = client.fetch_json_to_cache(company_plan["companyfacts"], refresh=bool(args.refresh))
                    companyfacts_payloads += 1
                    normalized = normalize_companyfacts_payload(company_plan["companyfacts"], payload, metadata=metadata, years=set(years), forms=forms)
                    for row in normalized:
                        fact_handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                    fact_rows += len(normalized)
                    for row in normalized:
                        source_family_counts[str(row.get("source_family") or "")] += 1
                        form_counts[str(row.get("form_type") or "")] += 1
                        concept_counts[str(row.get("concept") or "")] += 1
                        ticker_fact_counts[str(row.get("ticker") or ticker)] += 1
                if company_plan.get("submissions"):
                    payload, metadata = client.fetch_json_to_cache(company_plan["submissions"], refresh=bool(args.refresh))
                    submissions_payloads += 1
                    normalized_submissions = normalize_submissions_payload(company_plan["submissions"], payload, metadata=metadata, years=set(years), forms=forms)
                    for row in normalized_submissions:
                        submission_handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                    submission_rows += len(normalized_submissions)
            except Exception as exc:  # noqa: BLE001
                issues.append({"type": "sec_structured_fact_download_or_normalize_error", "ticker": ticker, "error": str(exc)})

    summary = {
        "schema_version": "fin_agent_sec_structured_facts_download_summary_v0.1",
        "status": "fail" if issues else "pass",
        "company_count": company_count,
        "companyfacts_payloads": companyfacts_payloads,
        "submissions_payloads": submissions_payloads,
        "fact_rows": fact_rows,
        "submission_rows": submission_rows,
        "years": years,
        "forms": sorted(forms),
        "source_family_counts": dict(sorted(source_family_counts.items())),
        "form_counts": dict(sorted(form_counts.items())),
        "top_concepts": dict(concept_counts.most_common(25)),
        "ticker_fact_rows_min": min(ticker_fact_counts.values()) if ticker_fact_counts else 0,
        "ticker_fact_rows_max": max(ticker_fact_counts.values()) if ticker_fact_counts else 0,
        "issue_counts": dict(sorted(Counter(str(issue.get("type") or "unknown") for issue in issues).items())),
        "issues": issues[:100],
        "outputs": {
            "fact_rows": str(fact_output),
            "submission_rows": str(submissions_output),
            "summary": str(summary_output),
        },
    }
    summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


class SecStructuredFactsClient:
    def __init__(self, *, user_agent: str, timeout: int = 30, rate_limit: float = 8.0) -> None:
        self.timeout = int(timeout)
        self.min_interval = 1.0 / float(rate_limit) if rate_limit > 0 else 0.0
        self._last_request_ts = 0.0
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate",
            }
        )

    def fetch_json_to_cache(self, plan_row: Mapping[str, Any], *, refresh: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
        cache_dir = _resolve(Path(str(plan_row.get("cache_dir") or "")))
        fact_source = str(plan_row.get("fact_source") or "payload").strip()
        payload_path = cache_dir / f"{fact_source}.json"
        metadata_path = cache_dir / f"{fact_source}.metadata.json"
        if payload_path.exists() and metadata_path.exists() and not refresh:
            payload = _read_json(payload_path)
            metadata = _read_json(metadata_path)
            metadata["cache_status"] = "hit"
            return payload, metadata
        url = str(plan_row.get("source_url") or "").strip()
        if not url:
            raise ValueError(f"Missing source_url for {plan_row.get('plan_id')}")
        self._rate_limit()
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        metadata = {
            "schema_version": "fin_agent_sec_structured_fact_raw_metadata_v0.1",
            "plan_id": plan_row.get("plan_id"),
            "ticker": plan_row.get("ticker"),
            "cik": plan_row.get("cik"),
            "cik10": plan_row.get("cik10"),
            "fact_source": fact_source,
            "source_url": url,
            "content_type": response.headers.get("content-type", ""),
            "byte_count": len(encoded),
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
            "cache_status": "downloaded",
        }
        cache_dir.mkdir(parents=True, exist_ok=True)
        payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload, metadata

    def _rate_limit(self) -> None:
        if self.min_interval <= 0:
            return
        elapsed = time.time() - self._last_request_ts
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request_ts = time.time()


def group_sec_structured_fact_plan_rows(plan_rows: Iterable[Mapping[str, Any]], *, ticker_filter: set[str] | None = None) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    filters = {ticker.upper() for ticker in ticker_filter or set()}
    for row in plan_rows:
        if str(row.get("integration_mode") or "") != "new_sec_api_download":
            continue
        ticker = str(row.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        if filters and ticker not in filters:
            continue
        grouped.setdefault(ticker, []).append(dict(row))
    return dict(sorted(grouped.items()))


def select_company_plan_rows(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for row in rows:
        fact_source = str(row.get("fact_source") or "")
        if fact_source in {"sec_companyfacts", "sec_submissions"}:
            selected[fact_source.replace("sec_", "")] = dict(row)
    return selected


def normalize_companyfacts_payload(
    plan_row: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any] | None = None,
    years: set[int] | None = None,
    forms: set[str] | None = None,
) -> list[dict[str, Any]]:
    years = years or set()
    forms = {form.upper() for form in forms or set()}
    ticker = str(plan_row.get("ticker") or "").upper().strip()
    cik = str(plan_row.get("cik") or payload.get("cik") or "").strip()
    cik10 = str(plan_row.get("cik10") or _cik10(cik)).strip()
    entity_name = str(payload.get("entityName") or plan_row.get("company_name") or "").strip()
    rows: list[dict[str, Any]] = []
    facts = payload.get("facts") if isinstance(payload, Mapping) else {}
    if not isinstance(facts, Mapping):
        return rows
    for taxonomy, taxonomy_facts in facts.items():
        if not isinstance(taxonomy_facts, Mapping):
            continue
        for concept, concept_payload in taxonomy_facts.items():
            if not isinstance(concept_payload, Mapping):
                continue
            label = str(concept_payload.get("label") or concept).strip()
            description = str(concept_payload.get("description") or "").strip()
            units = concept_payload.get("units") or {}
            if not isinstance(units, Mapping):
                continue
            for unit, unit_facts in units.items():
                if not isinstance(unit_facts, list):
                    continue
                for index, fact in enumerate(unit_facts):
                    if not isinstance(fact, Mapping):
                        continue
                    fiscal_year = _int_or_none(fact.get("fy"))
                    form_type = str(fact.get("form") or "").upper().strip()
                    if years and (fiscal_year is None or fiscal_year not in years):
                        continue
                    if forms and form_type not in forms:
                        continue
                    value = fact.get("val")
                    accession_number = str(fact.get("accn") or "").strip()
                    end_date = str(fact.get("end") or "").strip()
                    fiscal_period = str(fact.get("fp") or "").upper().strip()
                    metric_family = classify_metric_family(concept=concept, label=label, description=description)
                    period_role, duration_months = infer_period_role_and_duration(
                        start=str(fact.get("start") or "").strip(),
                        end=end_date,
                        fiscal_period=fiscal_period,
                    )
                    rows.append(
                        {
                            "schema_version": FACT_ROW_SCHEMA_VERSION,
                            "fact_id": _fact_id(ticker, taxonomy, concept, unit, accession_number, end_date, fiscal_year, fiscal_period, index),
                            "ticker": ticker,
                            "issuer_id": plan_row.get("issuer_id"),
                            "cik": cik,
                            "cik10": cik10,
                            "company_name": plan_row.get("company_name") or entity_name,
                            "entity_name": entity_name,
                            "source_family": plan_row.get("source_family") or "sec_companyfacts_structured_fact",
                            "source_tier": plan_row.get("source_tier") or "company_reported_structured_fact",
                            "fact_source": "sec_companyfacts",
                            "taxonomy": str(taxonomy),
                            "concept": str(concept),
                            "label": label,
                            "description": description,
                            "metric_family": metric_family,
                            "metric_role": "point_in_time" if period_role == "instant" else "period_value",
                            "unit": str(unit),
                            "value": value,
                            "value_text": str(value),
                            "display_value_zh": format_display_value(value, str(unit)),
                            "start_date": str(fact.get("start") or "").strip(),
                            "end_date": end_date,
                            "period_end": end_date,
                            "period_role": period_role,
                            "duration_months": duration_months,
                            "fiscal_year": fiscal_year,
                            "fiscal_period": fiscal_period,
                            "form_type": form_type,
                            "filed_date": fact.get("filed"),
                            "accession_number": accession_number,
                            "frame": fact.get("frame"),
                            "source_url": plan_row.get("source_url"),
                            "raw_metadata_sha256": (metadata or {}).get("sha256"),
                            "mainline_vector_promotion_allowed": False,
                            "exact_value_ledger_candidate": True,
                        }
                    )
    return rows


def normalize_submissions_payload(
    plan_row: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any] | None = None,
    years: set[int] | None = None,
    forms: set[str] | None = None,
) -> list[dict[str, Any]]:
    years = years or set()
    forms = {form.upper() for form in forms or set()}
    ticker = str(plan_row.get("ticker") or "").upper().strip()
    cik = str(plan_row.get("cik") or payload.get("cik") or "").strip()
    cik10 = str(plan_row.get("cik10") or _cik10(cik)).strip()
    company_name = str(payload.get("name") or plan_row.get("company_name") or "").strip()
    rows: list[dict[str, Any]] = []
    recent = ((payload.get("filings") or {}).get("recent") or {}) if isinstance(payload, Mapping) else {}
    forms_list = recent.get("form") or []
    for index, form_type_raw in enumerate(forms_list):
        form_type = str(form_type_raw or "").upper().strip()
        if forms and form_type not in forms:
            continue
        report_date = _value_at(recent, "reportDate", index)
        fiscal_year = _year_from_date(report_date)
        if years and (fiscal_year is None or fiscal_year not in years):
            continue
        accession_number = _value_at(recent, "accessionNumber", index)
        rows.append(
            {
                "schema_version": SUBMISSION_ROW_SCHEMA_VERSION,
                "submission_row_id": _submission_row_id(ticker, accession_number, form_type, index),
                "ticker": ticker,
                "issuer_id": plan_row.get("issuer_id"),
                "cik": cik,
                "cik10": cik10,
                "company_name": company_name,
                "source_family": plan_row.get("source_family") or "sec_submissions_metadata",
                "source_tier": plan_row.get("source_tier") or "company_reported_structured_fact",
                "fact_source": "sec_submissions",
                "form_type": form_type,
                "filing_date": _value_at(recent, "filingDate", index),
                "report_date": report_date,
                "fiscal_year": fiscal_year,
                "accession_number": accession_number,
                "primary_document": _value_at(recent, "primaryDocument", index),
                "primary_doc_description": _value_at(recent, "primaryDocDescription", index),
                "items": _value_at(recent, "items", index),
                "acceptance_datetime": _value_at(recent, "acceptanceDateTime", index),
                "source_url": plan_row.get("source_url"),
                "raw_metadata_sha256": (metadata or {}).get("sha256"),
                "mainline_vector_promotion_allowed": False,
            }
        )
    return rows


def classify_metric_family(*, concept: str, label: str, description: str = "") -> str:
    text = f"{concept} {label} {description}".lower()
    if re.search(r"revenue|revenues|salesrevenue|sales revenue|net sales", text):
        return "revenue"
    if re.search(r"operatingincome|operating income|income from operations", text):
        return "operating_income"
    if re.search(r"netincomeloss|net income|net earnings", text):
        return "net_income"
    if re.search(r"capitalexpenditure|capital expenditure|paymentstoacquireproperty|payments to acquire property|additions to property", text):
        return "capital_expenditure_proxy"
    if re.search(r"netcashprovidedbyusedinoperatingactivities|operating cash", text):
        return "operating_cash_flow"
    if re.search(r"netcashprovidedbyusedininvestingactivities|investing cash", text):
        return "investing_cash_flow"
    if re.search(r"netcashprovidedbyusedinfinancingactivities|financing cash", text):
        return "financing_cash_flow"
    if re.search(r"researchanddevelopment|research and development|r&d", text):
        return "r_and_d"
    if re.search(r"grossprofit|gross profit", text):
        return "gross_profit"
    if re.search(r"assets", text):
        return "assets"
    if re.search(r"liabilities", text):
        return "liabilities"
    if re.search(r"stockholdersequity|stockholders.? equity|shareholders.? equity", text):
        return "equity"
    if re.search(r"sharesoutstanding|shares outstanding", text):
        return "shares_outstanding"
    return "other_companyfacts"


def infer_period_role_and_duration(*, start: str, end: str, fiscal_period: str) -> tuple[str, int | None]:
    if not start:
        return "instant", None
    months = _duration_months(start, end)
    if fiscal_period == "FY" or (months is not None and months >= 11):
        return "annual", months
    if months is not None and months <= 4:
        return "qtd", months
    if months is not None:
        return "ytd", months
    return "period", None


def format_display_value(value: Any, unit: str) -> str:
    if value is None:
        return ""
    unit_lower = unit.lower()
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return f"{value} {unit}".strip()
    if unit_lower in {"usd", "us dollars"}:
        abs_value = abs(numeric)
        if abs_value >= 1_000_000_000:
            return f"{numeric / 1_000_000_000:.3g} 十亿美元"
        if abs_value >= 1_000_000:
            return f"{numeric / 1_000_000:.3g} 百万美元"
        return f"{numeric:.3g} 美元"
    if unit_lower in {"shares"}:
        return f"{numeric:.3g} 股"
    return f"{numeric:.6g} {unit}".strip()


def _fact_id(ticker: str, taxonomy: str, concept: str, unit: str, accession_number: str, end_date: str, fiscal_year: int | None, fiscal_period: str, index: int) -> str:
    digest = hashlib.sha1("||".join(str(part) for part in (ticker, taxonomy, concept, unit, accession_number, end_date, fiscal_year, fiscal_period, index)).encode("utf-8")).hexdigest()[:12]
    return f"SECFACT::{_slug(ticker)}::{_slug(taxonomy)}::{_slug(concept)}::{_slug(unit)}::{digest}"


def _submission_row_id(ticker: str, accession_number: str, form_type: str, index: int) -> str:
    digest = hashlib.sha1("||".join(str(part) for part in (ticker, accession_number, form_type, index)).encode("utf-8")).hexdigest()[:12]
    return f"SECSUB::{_slug(ticker)}::{_slug(form_type)}::{digest}"


def _duration_months(start: str, end: str) -> int | None:
    try:
        from datetime import date

        s = date.fromisoformat(start)
        e = date.fromisoformat(end)
    except (TypeError, ValueError):
        return None
    days = max(0, (e - s).days)
    return max(1, round(days / 30.4375))


def _value_at(block: Mapping[str, Any], key: str, index: int) -> Any:
    values = block.get(key) or []
    if not isinstance(values, list) or index >= len(values):
        return None
    return values[index]


def _year_from_date(value: Any) -> int | None:
    text = str(value or "")
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _cik10(value: Any) -> str:
    digits = re.sub(r"\D+", "", str(value or ""))
    return digits.zfill(10) if digits else ""


def _slug(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").strip().upper()).strip("_")
    return text or "UNKNOWN"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _parse_int_csv(raw: str | None) -> list[int]:
    return [int(part.strip()) for part in (raw or "").split(",") if part.strip()]


def _parse_str_csv(raw: str | None) -> list[str]:
    return [part.strip() for part in (raw or "").split(",") if part.strip()]


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
