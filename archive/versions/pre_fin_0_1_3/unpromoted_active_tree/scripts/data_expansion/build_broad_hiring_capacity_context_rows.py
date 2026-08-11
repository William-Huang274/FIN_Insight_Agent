from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


SCHEMA_VERSION = "finsight_broad_hiring_capacity_context_row_v0_1"
ATTEMPT_SCHEMA_VERSION = "finsight_broad_hiring_capacity_attempt_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_broad_hiring_capacity_context_summary_v0_1"

DEFAULT_COMPANY_SOURCE_MATRIX = REPO_ROOT / "data" / "manifests" / "company_public_source_coverage_matrix_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "broad_hiring_capacity_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_ATTEMPTS = REPO_ROOT / "data" / "manifests" / "broad_hiring_capacity_attempts_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "broad_hiring_capacity_context_summary_v0_1.json"
DEFAULT_RAW_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/broad_hiring_capacity")

USER_AGENT = "FIN-Insight-Agent public ATS source audit"

KNOWN_BOARD_TOKENS = {
    "ABNB": ("greenhouse", "airbnb"),
    "COIN": ("greenhouse", "coinbase"),
    "DASH": ("greenhouse", "doordashusa"),
    "DDOG": ("greenhouse", "datadog"),
    "HUBS": ("greenhouse", "hubspotjobs"),
    "NET": ("greenhouse", "cloudflare"),
    "PLTR": ("lever", "palantir"),
    "RBLX": ("greenhouse", "roblox"),
    "UBER": ("greenhouse", "uber"),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build broad public ATS hiring capacity rows from Greenhouse/Lever APIs.")
    parser.add_argument("--company-source-matrix", type=Path, default=DEFAULT_COMPANY_SOURCE_MATRIX)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-attempts", type=Path, default=DEFAULT_OUTPUT_ATTEMPTS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--tickers", nargs="*", default=[])
    parser.add_argument("--timeout-s", type=float, default=6.0)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--max-jobs-per-company", type=int, default=2)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    matrix_rows = _load_jsonl(args.company_source_matrix)
    result = build_broad_hiring_capacity_context_rows(
        matrix_rows=matrix_rows,
        generated_at=generated_at,
        tickers=args.tickers,
        raw_dir=args.raw_dir,
        timeout_s=args.timeout_s,
        workers=args.workers,
        max_jobs_per_company=args.max_jobs_per_company,
    )
    summary = build_summary(
        rows=result["rows"],
        attempts=result["attempts"],
        matrix_rows=matrix_rows,
        generated_at=generated_at,
        output_rows=args.output_rows,
        output_attempts=args.output_attempts,
    )
    _write_jsonl(args.output_rows, result["rows"])
    _write_jsonl(args.output_attempts, result["attempts"])
    _write_json(args.output_summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and not result["rows"]:
        return 1
    return 0


def build_broad_hiring_capacity_context_rows(
    *,
    matrix_rows: Iterable[Mapping[str, Any]],
    generated_at: str,
    raw_dir: Path,
    tickers: Iterable[str] = (),
    timeout_s: float = 6.0,
    workers: int = 24,
    max_jobs_per_company: int = 2,
) -> dict[str, list[dict[str, Any]]]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    ticker_filter = {str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()}
    companies: list[dict[str, Any]] = []
    for company in matrix_rows:
        ticker = str(company.get("ticker") or "").strip().upper()
        if not ticker or (ticker_filter and ticker not in ticker_filter):
            continue
        requirements = {str(req.get("requirement_id") or "") for req in company.get("source_role_matrix") or [] if isinstance(req, Mapping)}
        if "hiring_capacity_proxy" in requirements:
            companies.append(dict(company))
    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, int(workers or 1))) as executor:
        futures = {
            executor.submit(
                _process_company,
                company,
                generated_at=generated_at,
                raw_dir=raw_dir,
                timeout_s=timeout_s,
                max_jobs=max_jobs_per_company,
            ): str(company.get("ticker") or "").upper()
            for company in companies
        }
        for future in as_completed(futures):
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001
                ticker = futures[future]
                attempts.append(_attempt(ticker, "worker", "", "worker_failed", reason=f"{type(exc).__name__}:{str(exc)[:200]}", raw_path=""))
                continue
            rows.extend(result["rows"])
            attempts.extend(result["attempts"])
    return {"rows": _dedupe_rows(rows), "attempts": attempts}


def _process_company(
    company: Mapping[str, Any],
    *,
    generated_at: str,
    raw_dir: Path,
    timeout_s: float,
    max_jobs: int,
) -> dict[str, list[dict[str, Any]]]:
    ticker = str(company.get("ticker") or "").strip().upper()
    company_name = str(company.get("company_name") or ticker).strip()
    board_candidates = board_token_candidates(ticker, company_name)
    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    for provider, token, url in board_candidates:
        status, body, reason = _fetch_text(url, timeout_s=timeout_s)
        raw_path = raw_dir / provider / f"{_slug(ticker)}_{_slug(token)}.json"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(body or "", encoding="utf-8")
        if status != "ok":
            attempts.append(_attempt(ticker, provider, url, status, reason=reason, raw_path=str(raw_path)))
            continue
        payload = _parse_json(body)
        parsed_rows = parse_jobs(company, provider=provider, token=token, url=url, payload=payload, generated_at=generated_at, max_jobs=max_jobs)
        rows.extend(parsed_rows)
        attempts.append(_attempt(ticker, provider, url, "materialized" if parsed_rows else "no_job_rows", reason="" if parsed_rows else "ATS endpoint returned no parseable job rows", raw_path=str(raw_path)))
        if rows:
            break
    return {"rows": rows[:max_jobs], "attempts": attempts}


def board_token_candidates(ticker: str, company_name: str) -> list[tuple[str, str, str]]:
    known = KNOWN_BOARD_TOKENS.get(ticker)
    candidates: list[tuple[str, str]] = []
    if known:
        candidates.append(known)
    slug = _slug(_simplify_company_name(company_name))
    compact = slug.replace("_", "")
    ticker_slug = _slug(ticker)
    smart_token = "".join(part.capitalize() for part in slug.split("_") if part)
    for token in _unique([compact, slug, ticker_slug]):
        candidates.extend([("greenhouse", token), ("lever", token), ("ashby", token)])
    for token in _unique([smart_token, compact, ticker_slug.upper()]):
        candidates.append(("smartrecruiters", token))
    out: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for provider, token in candidates:
        key = (provider, token)
        if not token or key in seen:
            continue
        seen.add(key)
        if provider == "greenhouse":
            url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
        elif provider == "lever":
            url = f"https://api.lever.co/v0/postings/{token}?mode=json"
        elif provider == "ashby":
            url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
        else:
            url = f"https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=25"
        out.append((provider, token, url))
    return out[:10]


def parse_jobs(
    company: Mapping[str, Any],
    *,
    provider: str,
    token: str,
    url: str,
    payload: Any,
    generated_at: str,
    max_jobs: int,
) -> list[dict[str, Any]]:
    jobs: list[Mapping[str, Any]] = []
    if provider == "greenhouse":
        value = payload.get("jobs") if isinstance(payload, Mapping) else None
        jobs = [job for job in value if isinstance(job, Mapping)] if isinstance(value, list) else []
    elif provider == "lever":
        jobs = [job for job in payload if isinstance(job, Mapping)] if isinstance(payload, list) else []
    elif provider == "ashby":
        value = payload.get("jobs") if isinstance(payload, Mapping) else None
        jobs = [job for job in value if isinstance(job, Mapping)] if isinstance(value, list) else []
    elif provider == "smartrecruiters":
        value = payload.get("content") if isinstance(payload, Mapping) else None
        jobs = [job for job in value if isinstance(job, Mapping)] if isinstance(value, list) else []
    out: list[dict[str, Any]] = []
    for job in jobs[: max(1, max_jobs * 3)]:
        if provider == "greenhouse":
            title = str(job.get("title") or "").strip()
            location = str((job.get("location") or {}).get("name") if isinstance(job.get("location"), Mapping) else "").strip()
            date_value = str(job.get("updated_at") or "").strip()
            job_url = str(job.get("absolute_url") or url).strip()
            department = str((job.get("departments") or [{}])[0].get("name") if isinstance(job.get("departments"), list) and job.get("departments") else "").strip()
        elif provider == "lever":
            title = str(job.get("text") or "").strip()
            categories = job.get("categories") if isinstance(job.get("categories"), Mapping) else {}
            location = str(categories.get("location") or "").strip()
            department = str(categories.get("team") or categories.get("department") or "").strip()
            created = job.get("createdAt")
            date_value = str(created or "").strip()
            job_url = str(job.get("hostedUrl") or job.get("applyUrl") or url).strip()
        elif provider == "ashby":
            title = str(job.get("title") or "").strip()
            location = str(job.get("location") or job.get("locationName") or "").strip()
            department = str(job.get("department") or job.get("team") or "").strip()
            date_value = str(job.get("publishedAt") or "").strip()
            job_url = str(job.get("jobUrl") or job.get("jobUrl") or url).strip()
        else:
            title = str(job.get("name") or "").strip()
            location_payload = job.get("location") if isinstance(job.get("location"), Mapping) else {}
            location = str(location_payload.get("fullLocation") or ", ".join(str(location_payload.get(key) or "").strip() for key in ("city", "region", "country") if str(location_payload.get(key) or "").strip())).strip()
            department_payload = job.get("department") if isinstance(job.get("department"), Mapping) else {}
            department = str(department_payload.get("label") or department_payload.get("name") or "").strip()
            date_value = str(job.get("releasedDate") or "").strip()
            job_url = str(job.get("applyUrl") or job.get("ref") or url).strip()
        if not title or not location:
            continue
        issuer_binding_status = _issuer_binding_status(company, provider=provider, token=token, job=job)
        out.append(
            _job_row(
                company,
                provider=provider,
                token=token,
                source_url=url,
                job_url=job_url,
                title=title,
                location=location,
                department=department,
                date_value=date_value,
                issuer_binding_status=issuer_binding_status,
                generated_at=generated_at,
            )
        )
        if len(out) >= max_jobs:
            break
    return out


def _job_row(
    company: Mapping[str, Any],
    *,
    provider: str,
    token: str,
    source_url: str,
    job_url: str,
    title: str,
    location: str,
    department: str,
    date_value: str,
    issuer_binding_status: str,
    generated_at: str,
) -> dict[str, Any]:
    ticker = str(company.get("ticker") or "").strip().upper()
    evidence_ref = _stable_ref("broad_hiring_capacity", [ticker, provider, token, title, location, date_value])
    text = f"{ticker} public ATS job posting: {title}; location={location}; department={department}; date={date_value}; provider={provider}."
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "source_id": "job_postings_hiring_signals",
        "underlying_source_id": "job_postings_hiring_signals",
        "source_class": "job_postings_hiring_signals",
        "source_family": "public_source_context",
        "runtime_source_family": "public_source_context",
        "source_layer_id": "L3",
        "source_layer": "L3",
        "layer_id": "L3",
        "source_specific_parser": f"broad_{provider}_ats_job_parser_v0_1",
        "source_specific_resolver": "ats_board_token_to_issuer_resolver_v0_1",
        "provider": provider,
        "board_token": token,
        "parser_status": "source_specific_context_parser_pass",
        "structured_fact_status": "bounded_context_fact_materialized",
        "runtime_ready_context": True,
        "bounded_structured_context": True,
        "structured_context_type": "hiring_capacity_proxy",
        "requirement_id": "hiring_capacity_proxy",
        "ticker": ticker,
        "company": company.get("company_name") or "",
        "company_name": company.get("company_name") or "",
        "source_url": source_url,
        "job_url": job_url,
        "citation": {"url": source_url, "source_url": job_url, "title": title},
        "fact_label": title,
        "job_location": location,
        "job_department": department,
        "date": date_value,
        "posted_at": date_value,
        "product_or_segment": title,
        "product_family": title,
        "as_of_datetime": generated_at,
        "issuer_binding_status": issuer_binding_status,
        "product_binding_status": "product_mentioned_in_snapshot",
        "counterparty_binding_status": "not_bound",
        "entity_binding": {
            "issuer_ticker": ticker,
            "issuer_binding_status": issuer_binding_status,
            "product_binding_status": "product_mentioned_in_snapshot",
            "counterparty_binding_status": "not_bound",
            "resolver_status": "ats_board_token_bound_to_issuer" if issuer_binding_status == "issuer_mentioned_in_snapshot" else "ats_board_token_candidate_not_verified",
            "binding_claim_boundary": "Public ATS job posting role/geography/focus signal only; no headcount, revenue, demand, or capacity proof.",
        },
        "resolver_status": "ats_board_token_bound_to_issuer" if issuer_binding_status == "issuer_mentioned_in_snapshot" else "ats_board_token_candidate_not_verified",
        "context_only": True,
        "exact_value_authority": False,
        "can_support_company_exact_fact": False,
        "allowed_claims": ["hiring_signal_context", "market_proxy_context", "verification_lead"],
        "forbidden_claims": ["headcount", "revenue", "order_volume", "production_capacity_fact", "demand_proof"],
        "claim_boundary": "Public job posting supports role/geography/focus signal only.",
        "text": text,
        "preview": text,
    }


def build_summary(
    *,
    rows: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    matrix_rows: list[dict[str, Any]],
    generated_at: str,
    output_rows: Path,
    output_attempts: Path,
) -> dict[str, Any]:
    required = {
        str(row.get("ticker") or "").upper()
        for row in matrix_rows
        for req in row.get("source_role_matrix") or []
        if isinstance(req, Mapping) and str(req.get("requirement_id") or "") == "hiring_capacity_proxy"
    }
    success = {str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")}
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if rows else "gap",
        "required_ticker_count": len(required),
        "success_ticker_count": len(success),
        "unmaterialized_ticker_count": len(required - success),
        "row_count": len(rows),
        "attempt_count": len(attempts),
        "attempt_status_counts": dict(sorted(Counter(str(row.get("status") or "") for row in attempts).items())),
        "unmaterialized_tickers": sorted(required - success),
        "outputs": {"rows": str(output_rows), "attempts": str(output_attempts)},
        "boundary": "Only public ATS JSON job postings are promoted; hiring rows cannot prove headcount, production capacity, demand, revenue, or order volume.",
    }


def _fetch_text(url: str, *, timeout_s: float) -> tuple[str, str, str]:
    try:
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        with urlopen(request, timeout=timeout_s) as response:
            body = response.read().decode("utf-8", errors="ignore")
            return ("ok", body, "") if response.status < 400 else (f"http_{response.status}", body, f"http_{response.status}")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else ""
        return f"http_{exc.code}", body, f"http_{exc.code}"
    except (URLError, TimeoutError) as exc:
        return "fetch_failed", "", f"{type(exc).__name__}:{str(exc)[:160]}"
    except Exception as exc:  # noqa: BLE001
        return "fetch_failed", "", f"{type(exc).__name__}:{str(exc)[:160]}"


def _issuer_binding_status(company: Mapping[str, Any], *, provider: str, token: str, job: Mapping[str, Any]) -> str:
    ticker = str(company.get("ticker") or "").upper()
    company_name = str(company.get("company_name") or "").strip()
    known = KNOWN_BOARD_TOKENS.get(ticker)
    if known and known == (provider, token):
        return "issuer_mentioned_in_snapshot"
    company_slug = _slug(_simplify_company_name(company_name))
    compact_company = company_slug.replace("_", "")
    token_text = _slug(token).replace("_", "")
    if provider == "smartrecruiters":
        job_company = job.get("company") if isinstance(job.get("company"), Mapping) else {}
        job_company_name = _slug(_simplify_company_name(str(job_company.get("name") or ""))).replace("_", "")
        if job_company_name and job_company_name in {compact_company, token_text}:
            return "issuer_mentioned_in_snapshot"
        if token_text and token_text == compact_company:
            return "issuer_mentioned_in_snapshot"
    if token_text and token_text == compact_company and len(token_text) >= 6:
        return "issuer_mentioned_in_snapshot"
    return "issuer_locator_candidate_unverified"


def _parse_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def _attempt(ticker: str, provider: str, url: str, status: str, *, reason: str, raw_path: str) -> dict[str, Any]:
    return {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "attempt_id": _stable_ref("broad_hiring_capacity_attempt", [ticker, provider, url, status, reason]),
        "ticker": ticker,
        "source_id": "job_postings_hiring_signals",
        "provider": provider,
        "source_url": url,
        "status": status,
        "raw_path": raw_path,
        "reason": reason,
    }


def _simplify_company_name(value: str) -> str:
    return re.sub(
        r"\b(inc|incorporated|corp|corporation|co|company|ltd|limited|plc|se|sa|nv|ag|llc|the|class a|class b)\b\.?",
        "",
        re.split(r"[,(/-]", str(value or ""), maxsplit=1)[0],
        flags=re.IGNORECASE,
    ).strip()


def _slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", str(value or "").lower()).strip("_")
    return text[:80] or "unknown"


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
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


def _dedupe_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.get("evidence_ref") or "")
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    return out


def _stable_ref(prefix: str, parts: Iterable[Any]) -> str:
    digest = hashlib.sha1("|".join(str(part or "") for part in parts).encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
