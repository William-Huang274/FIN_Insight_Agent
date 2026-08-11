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
from typing import Any, Callable, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.public_web_context_parser import parse_public_web_context_rows  # noqa: E402
from sec_agent.source_coverage_gate import build_source_coverage_gate  # noqa: E402


SCHEMA_VERSION = "fin_agent_hiring_capacity_context_row_v0_1"
SUMMARY_SCHEMA_VERSION = "fin_agent_hiring_capacity_context_summary_v0_1"

SOURCE_ID = "job_postings_hiring_signals"
DEFAULT_SOURCE_LAYER_ROWS = REPO_ROOT / "data" / "manifests" / "source_layer_capability_audit_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "hiring_capacity_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "hiring_capacity_context_summary_v0_1.json"
DEFAULT_OUTPUT_COVERAGE = REPO_ROOT / "data" / "manifests" / "hiring_capacity_runtime_coverage_gate_v0_1.json"
DEFAULT_RAW_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/hiring_capacity")

FetchFunc = Callable[[str, float], tuple[int, str, str]]


DEFAULT_HIRING_PROBES: tuple[dict[str, Any], ...] = (
    {
        "ticker": "DDOG",
        "company_name": "Datadog",
        "provider": "greenhouse",
        "board_token": "datadog",
        "company_names": ["Datadog"],
        "role_focus_terms": ["AI", "Cloud", "Platform", "Security", "Infrastructure", "Data"],
    },
    {
        "ticker": "NET",
        "company_name": "Cloudflare",
        "provider": "greenhouse",
        "board_token": "cloudflare",
        "company_names": ["Cloudflare"],
        "role_focus_terms": ["AI", "Workers", "Security", "Network", "Infrastructure", "Platform"],
    },
    {
        "ticker": "PLTR",
        "company_name": "Palantir",
        "provider": "lever",
        "board_token": "palantir",
        "company_names": ["Palantir"],
        "role_focus_terms": ["AI", "AIP", "Foundry", "Gotham", "Platform", "Deployment"],
    },
    {
        "ticker": "COIN",
        "company_name": "Coinbase",
        "provider": "greenhouse",
        "board_token": "coinbase",
        "company_names": ["Coinbase"],
        "role_focus_terms": ["Wallet", "Payments", "Security", "Blockchain", "Platform", "Data"],
    },
    {
        "ticker": "RBLX",
        "company_name": "Roblox",
        "provider": "greenhouse",
        "board_token": "roblox",
        "company_names": ["Roblox"],
        "role_focus_terms": ["AI", "Creator", "Avatar", "Engine", "Infrastructure", "Platform"],
    },
    {
        "ticker": "DASH",
        "company_name": "DoorDash",
        "provider": "greenhouse",
        "board_token": "doordashusa",
        "company_names": ["DoorDash"],
        "role_focus_terms": ["Ads", "Marketplace", "Logistics", "Platform", "Data", "Delivery"],
    },
    {
        "ticker": "ABNB",
        "company_name": "Airbnb",
        "provider": "greenhouse",
        "board_token": "airbnb",
        "company_names": ["Airbnb"],
        "role_focus_terms": ["Marketplace", "Payments", "Trust", "AI", "Platform", "Search"],
    },
    {
        "ticker": "LYFT",
        "company_name": "Lyft",
        "provider": "greenhouse",
        "board_token": "lyft",
        "company_names": ["Lyft"],
        "role_focus_terms": ["Marketplace", "Pricing", "Platform", "Data", "Rider", "Driver"],
    },
    {
        "ticker": "ASAN",
        "company_name": "Asana",
        "provider": "greenhouse",
        "board_token": "asana",
        "company_names": ["Asana"],
        "role_focus_terms": ["AI", "Work Graph", "Enterprise", "Platform", "Product", "Data"],
    },
    {
        "ticker": "NVDA",
        "company_name": "NVIDIA",
        "provider": "workday",
        "api_url": "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs",
        "job_base_url": "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite",
        "company_names": ["NVIDIA"],
        "role_focus_terms": ["AI", "GPU", "CUDA", "Data Center", "Networking", "Systems", "Platform"],
        "search_text": "AI",
    },
    {
        "ticker": "HPE",
        "company_name": "Hewlett Packard Enterprise",
        "provider": "workday",
        "api_url": "https://hpe.wd5.myworkdayjobs.com/wday/cxs/hpe/Jobsathpe/jobs",
        "job_base_url": "https://hpe.wd5.myworkdayjobs.com/Jobsathpe",
        "company_names": ["Hewlett Packard Enterprise", "HPE"],
        "role_focus_terms": ["AI", "Networking", "Server", "High Performance Computing", "Cray", "GreenLake", "Cloud"],
        "search_text": "AI",
    },
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build bounded L3 hiring/capacity context rows from public ATS APIs.")
    parser.add_argument("--tickers", nargs="*", default=[], help="Optional ticker allowlist.")
    parser.add_argument("--source-layer-rows", type=Path, default=DEFAULT_SOURCE_LAYER_ROWS)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-coverage-gate", type=Path, default=DEFAULT_OUTPUT_COVERAGE)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--timeout-s", type=float, default=12.0)
    parser.add_argument("--fetch-retries", type=int, default=2)
    parser.add_argument("--max-jobs-per-company", type=int, default=5)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if no parser-backed rows are produced.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    result = build_hiring_capacity_context_rows(
        probes=DEFAULT_HIRING_PROBES,
        generated_at=generated_at,
        raw_dir=args.raw_dir,
        tickers=args.tickers,
        timeout_s=args.timeout_s,
        fetch_retries=args.fetch_retries,
        max_jobs_per_company=args.max_jobs_per_company,
    )
    source_layer_rows = _load_jsonl(args.source_layer_rows)
    coverage_gate = build_hiring_capacity_coverage_gate(
        context_rows=result["rows"],
        source_layer_rows=source_layer_rows,
        generated_at=generated_at,
    )
    summary = build_summary(
        rows=result["rows"],
        attempts=result["attempts"],
        coverage_gate=coverage_gate,
        generated_at=generated_at,
        output_rows=args.output_rows,
        output_coverage=args.output_coverage_gate,
    )
    _write_jsonl(args.output_rows, result["rows"])
    _write_json(args.output_summary, summary)
    _write_json(args.output_coverage_gate, coverage_gate)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and summary["parser_backed_row_count"] <= 0:
        return 1
    return 0


def build_hiring_capacity_context_rows(
    *,
    probes: Iterable[Mapping[str, Any]],
    generated_at: str,
    raw_dir: Path,
    tickers: Iterable[str] = (),
    timeout_s: float = 12.0,
    fetch_retries: int = 2,
    max_jobs_per_company: int = 5,
    fetch: FetchFunc | None = None,
) -> dict[str, Any]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    ticker_filter = {str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()}
    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []

    for probe in probes:
        ticker = str(probe.get("ticker") or "").strip().upper()
        if ticker_filter and ticker not in ticker_filter:
            continue
        company_name = str(probe.get("company_name") or ticker).strip()
        provider = str(probe.get("provider") or "").strip().lower()
        board_token = str(probe.get("board_token") or "").strip()
        api_url = str(probe.get("api_url") or "").strip() or ats_api_url(provider=provider, board_token=board_token)
        if not api_url:
            attempts.append(_attempt(ticker, "", "", provider, "unsupported_provider", reason="ats_provider_not_supported"))
            continue
        if fetch is not None:
            fetcher = fetch
        elif provider == "workday":
            search_text = str(probe.get("search_text") or "").strip()
            fetcher = lambda url, timeout_s, search_text=search_text: _post_workday_jobs(
                url,
                timeout_s,
                search_text=search_text,
                limit=max(20, int(max_jobs_per_company or 5) * 4),
            )
        else:
            fetcher = _fetch_url
        try:
            status_code, content_type, body = _fetch_with_retries(fetcher, api_url, timeout_s, fetch_retries)
        except Exception as exc:  # noqa: BLE001
            attempts.append(_attempt(ticker, "", api_url, provider, "fetch_failed", reason=f"{type(exc).__name__}: {str(exc)[:220]}"))
            continue
        if status_code >= 400 or not body.strip():
            attempts.append(_attempt(ticker, "", api_url, provider, "unusable_response", reason=f"http_{status_code}" if status_code else "empty_body"))
            continue
        payload = _parse_json(body)
        if payload is None:
            attempts.append(_attempt(ticker, "", api_url, provider, "unusable_response", reason="non_json_or_empty_payload"))
            continue

        raw_path = raw_dir / f"{ticker.lower()}_{_slug(provider)}_{_slug(board_token)}.json"
        raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        all_jobs = normalize_ats_jobs(payload, provider=provider, base_url=str(probe.get("job_base_url") or ""))
        selected_jobs = select_jobs_for_focus(all_jobs, focus_terms=probe.get("role_focus_terms") or [], max_jobs=max_jobs_per_company)
        json_ld_items = [job_to_json_ld(job, company_name=company_name) for job in selected_jobs]
        html_body = (
            "<html><head><script type=\"application/ld+json\">"
            + json.dumps(json_ld_items, ensure_ascii=False)
            + "</script></head><body></body></html>"
        )
        role_terms = _unique_strings(
            [
                *(probe.get("role_focus_terms") or []),
                *(job.get("matched_focus_terms") or [] for job in selected_jobs),
                *(job.get("title") for job in selected_jobs),
            ]
        )
        repair = {
            "repair_id": f"hiring_capacity_backfill:{ticker.lower()}:{_slug(board_token)}",
            "repair_type": "market_proxy",
            "ticker": ticker,
            "company_name": company_name,
            "company_names": _unique_strings([company_name, *(probe.get("company_names") or [])]),
            "product_terms": role_terms,
            "product_names": role_terms,
            "metric_leads": ["job title", "department", "team", "location", "date posted", "hiring proxy"],
        }
        parent_ref = _stable_ref("hiring_capacity", [ticker, provider, api_url, generated_at[:10]])
        parsed_rows = parse_public_web_context_rows(
            ticker=ticker,
            parent_evidence_ref=parent_ref,
            url=api_url,
            source_class="job_posting_snapshot",
            repair_type="market_proxy",
            analysis_dimension="product_and_production",
            title=f"{company_name} public ATS job postings",
            body=html_body,
            content_type="text/html",
            as_of_datetime=generated_at,
            citation={"url": api_url, "title": f"{company_name} public ATS job postings"},
            source_layer_meta={
                "source_id": SOURCE_ID,
                "underlying_source_id": SOURCE_ID,
                "source_layer_id": "L3",
                "source_layer": "L3",
                "layer_id": "L3",
                "parser_status": "ats_jobposting_jsonld_parser_pass",
                "structured_fact_status": "bounded_context_fact_materialized",
                "evidence_graph_status": "runtime_ready_context",
                "runtime_ready_context": True,
                "can_support_company_exact_fact": False,
            },
            claim_boundary=(
                "Public ATS job posting context only; supports directional hiring, role focus, geography, "
                "and capacity signal proxy, not headcount, revenue, demand, order, production, or margin proof."
            ),
            authority_boundary="L3 hiring/capacity proxy; never exact company metric authority.",
            repair=repair,
            max_rows=max_jobs_per_company,
        )
        selected_by_label = {str(job.get("jsonld_title") or job.get("title") or ""): job for job in selected_jobs}
        for row in parsed_rows:
            row["schema_version"] = SCHEMA_VERSION
            row["runtime_source_family"] = "public_source_context"
            row["source_family"] = "live_public_web_context"
            row["source_id"] = SOURCE_ID
            row["underlying_source_id"] = SOURCE_ID
            row["provider"] = provider
            row["board_token"] = board_token
            row["api_url"] = api_url
            row["raw_path"] = str(raw_path)
            row["context_only"] = True
            row["exact_value_authority"] = False
            row["can_support_company_exact_fact"] = False
            row["allowed_claims"] = ["hiring_signal_context", "market_proxy_context", "verification_lead"]
            row["forbidden_claims"] = ["headcount", "revenue", "order_volume", "production_capacity_fact", "demand_proof", "margin_fact"]
            matched_job = selected_by_label.get(str(row.get("fact_label") or ""))
            if matched_job:
                row["job_url"] = str(matched_job.get("url") or "")
                row["job_department"] = str(matched_job.get("department") or "")
                row["job_location"] = str(matched_job.get("location") or "")
                row["matched_focus_terms"] = list(matched_job.get("matched_focus_terms") or [])
            rows.append(row)
        attempts.append(
            _attempt(
                ticker,
                "",
                api_url,
                provider,
                "materialized" if parsed_rows else "parser_no_rows",
                raw_path=str(raw_path),
                total_job_count=len(all_jobs),
                selected_job_count=len(selected_jobs),
                parsed_row_count=len(parsed_rows),
            )
        )

    return {"rows": _dedupe_rows(rows), "attempts": attempts}


def build_hiring_capacity_coverage_gate(
    *,
    context_rows: list[dict[str, Any]],
    source_layer_rows: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    visible = {
        "product_technology_analyst": context_rows,
        "industry_supply_chain_analyst": context_rows,
        "risk_counterevidence_analyst": context_rows,
    }
    return build_source_coverage_gate(
        industry_schema="software_saas",
        phase="runtime_case",
        case_id="hiring_capacity_context_backfill_smoke",
        source_layer_capability={"rows": source_layer_rows},
        observed_rows=context_rows,
        specialist_visible_rows=visible,
        required_dimensions=["hiring_capacity_proxy"],
        generated_at=generated_at,
    )


def build_summary(
    *,
    rows: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    coverage_gate: Mapping[str, Any],
    generated_at: str,
    output_rows: Path,
    output_coverage: Path,
) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if rows else "gap",
        "attempted_count": len(attempts),
        "materialized_count": len([row for row in attempts if row.get("status") == "materialized"]),
        "failed_count": len([row for row in attempts if row.get("status") not in {"materialized"}]),
        "context_row_count": len(rows),
        "parser_backed_row_count": len([row for row in rows if row.get("bounded_structured_context") or row.get("structured_context_type")]),
        "ticker_count": len({str(row.get("ticker") or "") for row in rows if str(row.get("ticker") or "")}),
        "tickers": sorted({str(row.get("ticker") or "") for row in rows if str(row.get("ticker") or "")}),
        "provider_counts": dict(sorted(Counter(str(row.get("provider") or "") for row in rows).items())),
        "structured_context_type_counts": dict(sorted(Counter(str(row.get("structured_context_type") or "") for row in rows).items())),
        "issuer_binding_status_counts": dict(sorted(Counter(str(row.get("issuer_binding_status") or "") for row in rows).items())),
        "product_binding_status_counts": dict(sorted(Counter(str(row.get("product_binding_status") or "") for row in rows).items())),
        "coverage_gate_status": str(coverage_gate.get("status") or ""),
        "hiring_capacity_proxy_requirement": _requirement_summary(coverage_gate, "hiring_capacity_proxy"),
        "outputs": {"rows": str(output_rows), "coverage_gate": str(output_coverage)},
        "boundary": "L3 hiring rows are directional public ATS proxy only and cannot prove headcount, demand, revenue, order volume, production capacity, or margins.",
        "attempts": attempts,
    }


def ats_api_url(*, provider: str, board_token: str) -> str:
    if not board_token:
        return ""
    if provider == "greenhouse":
        return f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
    if provider == "lever":
        return f"https://api.lever.co/v0/postings/{board_token}?mode=json"
    if provider == "workday" and board_token.startswith("https://"):
        return board_token
    return ""


def normalize_ats_jobs(payload: Any, *, provider: str, base_url: str = "") -> list[dict[str, Any]]:
    if provider == "greenhouse" and isinstance(payload, Mapping):
        jobs = payload.get("jobs") if isinstance(payload.get("jobs"), list) else []
        return [_normalize_greenhouse_job(job) for job in jobs if isinstance(job, Mapping)]
    if provider == "lever" and isinstance(payload, list):
        return [_normalize_lever_job(job) for job in payload if isinstance(job, Mapping)]
    if provider == "workday" and isinstance(payload, Mapping):
        jobs = payload.get("jobPostings") if isinstance(payload.get("jobPostings"), list) else []
        return [_normalize_workday_job(job, base_url=base_url) for job in jobs if isinstance(job, Mapping)]
    return []


def _normalize_greenhouse_job(job: Mapping[str, Any]) -> dict[str, Any]:
    departments = [str(row.get("name") or "") for row in job.get("departments") or [] if isinstance(row, Mapping)]
    offices = [str(row.get("name") or "") for row in job.get("offices") or [] if isinstance(row, Mapping)]
    location = ""
    location_obj = job.get("location")
    if isinstance(location_obj, Mapping):
        location = str(location_obj.get("name") or "").strip()
    return {
        "title": str(job.get("title") or "").strip(),
        "department": "; ".join(_unique_strings(departments)),
        "team": "; ".join(_unique_strings(departments)),
        "location": location or "; ".join(_unique_strings(offices)),
        "date": str(job.get("updated_at") or "").strip(),
        "url": str(job.get("absolute_url") or "").strip(),
        "raw_id": str(job.get("id") or "").strip(),
    }


def _normalize_lever_job(job: Mapping[str, Any]) -> dict[str, Any]:
    categories = job.get("categories") if isinstance(job.get("categories"), Mapping) else {}
    created = job.get("createdAt")
    date = ""
    if isinstance(created, int):
        date = datetime.fromtimestamp(created / 1000, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "title": str(job.get("text") or "").strip(),
        "department": str(categories.get("department") or categories.get("team") or "").strip(),
        "team": str(categories.get("team") or "").strip(),
        "location": str(categories.get("location") or "").strip(),
        "date": date,
        "url": str(job.get("hostedUrl") or job.get("applyUrl") or "").strip(),
        "raw_id": str(job.get("id") or "").strip(),
    }


def _normalize_workday_job(job: Mapping[str, Any], *, base_url: str) -> dict[str, Any]:
    external_path = str(job.get("externalPath") or "").strip()
    url = ""
    if base_url and external_path:
        url = f"{base_url.rstrip('/')}/{external_path.lstrip('/')}"
    title = str(job.get("title") or "").strip()
    bullet_fields = [str(item or "").strip() for item in job.get("bulletFields") or [] if str(item or "").strip()]
    return {
        "title": title,
        "department": str(job.get("category") or job.get("jobFamily") or "").strip(),
        "team": "; ".join(_unique_strings([job.get("category"), job.get("jobFamily"), *bullet_fields[:1]])),
        "location": str(job.get("locationsText") or "").strip(),
        "date": str(job.get("postedOn") or job.get("startDate") or "").strip(),
        "url": url,
        "raw_id": bullet_fields[0] if bullet_fields else external_path,
    }


def select_jobs_for_focus(jobs: Iterable[Mapping[str, Any]], *, focus_terms: Iterable[Any], max_jobs: int) -> list[dict[str, Any]]:
    terms = _unique_strings(focus_terms)
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for index, job in enumerate(jobs):
        haystack = " ".join(str(job.get(key) or "") for key in ("title", "department", "team", "location")).lower()
        matched = [term for term in terms if term.lower() in haystack]
        score = len(matched)
        item = dict(job)
        item["matched_focus_terms"] = matched
        scored.append((score, -index, item))
    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    selected = [item for score, _, item in scored if score > 0][: max(0, int(max_jobs or 0))]
    if len(selected) < max_jobs:
        for _, _, item in scored:
            if item in selected:
                continue
            selected.append(item)
            if len(selected) >= max_jobs:
                break
    for job in selected:
        taxonomy = _unique_strings([*(job.get("matched_focus_terms") or []), job.get("department"), job.get("team")])[:4]
        title_parts = [str(job.get("title") or "").strip(), " / ".join(taxonomy)]
        job["jsonld_title"] = " | ".join(part for part in title_parts if part)
    return selected


def job_to_json_ld(job: Mapping[str, Any], *, company_name: str) -> dict[str, Any]:
    location = str(job.get("location") or "").strip()
    return {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": str(job.get("jsonld_title") or job.get("title") or "job posting").strip(),
        "datePosted": str(job.get("date") or "").strip(),
        "hiringOrganization": {"@type": "Organization", "name": company_name},
        "jobLocation": {"@type": "Place", "address": {"@type": "PostalAddress", "addressLocality": location}},
        "url": str(job.get("url") or "").strip(),
    }


def _fetch_url(url: str, timeout_s: float) -> tuple[int, str, str]:
    request = Request(
        url,
        headers={
            "User-Agent": "FIN-Insight-Agent/0.1 hiring-capacity-source-backfill",
            "Accept": "application/json,text/plain;q=0.8,*/*;q=0.5",
        },
    )
    try:
        with urlopen(request, timeout=float(timeout_s or 12.0)) as response:  # noqa: S310
            body = response.read().decode("utf-8", errors="replace")
            return int(getattr(response, "status", 200) or 200), str(response.headers.get("Content-Type") or ""), body
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return int(exc.code or 0), str(exc.headers.get("Content-Type") if exc.headers else ""), body
    except URLError:
        raise


def _post_workday_jobs(url: str, timeout_s: float, *, search_text: str = "", limit: int = 20) -> tuple[int, str, str]:
    payload = {
        "appliedFacets": {},
        "limit": max(1, int(limit or 20)),
        "offset": 0,
        "searchText": str(search_text or ""),
    }
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "User-Agent": "FIN-Insight-Agent/0.1 hiring-capacity-source-backfill",
            "Accept": "application/json,text/plain;q=0.8,*/*;q=0.5",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=float(timeout_s or 12.0)) as response:  # noqa: S310
            body = response.read().decode("utf-8", errors="replace")
            return int(getattr(response, "status", 200) or 200), str(response.headers.get("Content-Type") or ""), body
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return int(exc.code or 0), str(exc.headers.get("Content-Type") if exc.headers else ""), body
    except URLError:
        raise


def _fetch_with_retries(fetcher: FetchFunc, url: str, timeout_s: float, retries: int) -> tuple[int, str, str]:
    max_attempts = max(1, int(retries or 0) + 1)
    last_exc: Exception | None = None
    for attempt_index in range(max_attempts):
        try:
            return fetcher(url, timeout_s)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt_index + 1 >= max_attempts:
                break
            time.sleep(min(1.5, 0.25 * (2**attempt_index)))
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("fetch_failed_without_exception")


def _parse_json(body: str) -> Any:
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def _requirement_summary(payload: Mapping[str, Any], requirement_id: str) -> dict[str, Any]:
    for row in payload.get("requirements") or []:
        if isinstance(row, Mapping) and str(row.get("requirement_id") or "") == requirement_id:
            return {
                "status": str(row.get("status") or ""),
                "observed_row_count": int(row.get("observed_row_count") or 0),
                "parser_row_count": int(row.get("parser_row_count") or 0),
                "entity_bound_row_count": int(row.get("entity_bound_row_count") or 0),
                "specialist_visible_row_count": int(row.get("specialist_visible_row_count") or 0),
                "gaps": list(row.get("gaps") or []),
            }
    return {}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            value = json.loads(line)
            if isinstance(value, Mapping):
                rows.append(dict(value))
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _unique_strings(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if isinstance(value, (list, tuple, set)):
            candidates = value
        else:
            candidates = [value]
        for candidate in candidates:
            text = str(candidate or "").strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(text)
    return out


def _dedupe_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.get("evidence_ref") or row.get("evidence_id") or "")
        if not key:
            key = hashlib.sha1(json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _stable_ref(prefix: str, parts: Iterable[Any]) -> str:
    digest = hashlib.sha1("|".join(str(part or "") for part in parts).encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _slug(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", str(text or "").strip()).strip("_").lower()
    return value[:90] or "unknown"


def _attempt(ticker: str, source_url: str, api_url: str, provider: str, status: str, **extra: Any) -> dict[str, Any]:
    row = {"ticker": ticker, "source_url": source_url, "api_url": api_url, "provider": provider, "status": status}
    row.update(extra)
    return row


if __name__ == "__main__":
    raise SystemExit(main())
