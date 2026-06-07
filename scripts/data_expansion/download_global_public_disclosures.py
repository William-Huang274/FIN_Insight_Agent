from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_PLAN = REPO_ROOT / "data" / "manifests" / "tier2_global_public_disclosure_source_plan_v0_1.jsonl"
DEFAULT_PROFILES = REPO_ROOT / "configs" / "data_sources" / "global_public_disclosure_profiles_v0_1.yaml"
DEFAULT_QUEUE_OUTPUT = REPO_ROOT / "data" / "manifests" / "tier2_global_public_disclosure_download_tasks_v0_1.jsonl"
DEFAULT_SUMMARY_OUTPUT = REPO_ROOT / "data" / "manifests" / "tier2_global_public_disclosure_download_tasks_summary_v0_1.json"
SCHEMA_VERSION = "fin_agent_global_public_disclosure_download_task_v0.1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build or materialize profile-aware download tasks for global public disclosures.")
    parser.add_argument("--source-plan", type=Path, default=DEFAULT_SOURCE_PLAN)
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    parser.add_argument("--queue-output", type=Path, default=DEFAULT_QUEUE_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--profile", default="", help="Optional disclosure_profile filter.")
    parser.add_argument("--ticker", default="", help="Optional ticker filter.")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--execute", action="store_true", help="Execute implemented profile strategies and download matched report documents.")
    parser.add_argument(
        "--allow-company-ir-fallback",
        action="store_true",
        help="When a profile-specific strategy is not implemented, try official company IR locators as staging-only fallback.",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--user-agent", default="FinSight-Agent/0.1 research downloader contact@example.com")
    parser.add_argument(
        "--materialize-locators",
        action="store_true",
        help="Create cache directories and locator metadata only. Does not download report documents.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    plan_rows = _load_jsonl(_resolve(args.source_plan))
    profiles_config = _load_yaml(_resolve(args.profiles))
    tasks, issues = build_global_public_disclosure_download_tasks(
        plan_rows=plan_rows,
        profiles_config=profiles_config,
        profile_filter=args.profile,
        ticker_filter=args.ticker,
        limit=args.limit,
    )
    if args.materialize_locators:
        tasks = materialize_locator_metadata(tasks)
    if args.execute:
        tasks, execution_issues = execute_download_tasks(
            tasks,
            timeout=args.timeout,
            user_agent=args.user_agent,
            allow_company_ir_fallback=args.allow_company_ir_fallback,
        )
        issues.extend(execution_issues)
    queue_output = _resolve(args.queue_output)
    summary_output = _resolve(args.summary_output)
    queue_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl(queue_output, tasks)
    summary = summarize_download_tasks(tasks=tasks, issues=issues, queue_output=queue_output, summary_output=summary_output)
    summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "pass" else 1


def build_global_public_disclosure_download_tasks(
    *,
    plan_rows: Iterable[Mapping[str, Any]],
    profiles_config: Mapping[str, Any],
    profile_filter: str = "",
    ticker_filter: str = "",
    limit: int = 0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    profiles = profiles_config.get("profiles") or {}
    profile_filter = profile_filter.strip()
    ticker_filter = ticker_filter.upper().strip()
    tasks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for row in plan_rows:
        profile_name = str(row.get("disclosure_profile") or "").strip()
        ticker = str(row.get("ticker") or "").upper().strip()
        if profile_filter and profile_name != profile_filter:
            continue
        if ticker_filter and ticker != ticker_filter:
            continue
        profile = profiles.get(profile_name)
        if not profile:
            issues.append({"type": "missing_profile", "plan_id": row.get("plan_id"), "ticker": ticker, "disclosure_profile": profile_name})
            continue
        source_locator_urls = [str(url).strip() for url in row.get("source_locator_urls") or [] if str(url).strip()]
        if not source_locator_urls:
            issues.append({"type": "missing_source_locator_urls", "plan_id": row.get("plan_id"), "ticker": ticker, "disclosure_profile": profile_name})
            continue
        task = {
            "schema_version": SCHEMA_VERSION,
            "task_id": "DOWNLOAD::" + str(row.get("plan_id") or ""),
            "plan_id": row.get("plan_id"),
            "ticker": ticker,
            "issuer_id": row.get("issuer_id"),
            "exchange_symbol": row.get("exchange_symbol"),
            "company_name": row.get("company_name"),
            "disclosure_profile": profile_name,
            "locator_strategy": row.get("locator_strategy"),
            "parser_profile": row.get("parser_profile"),
            "fiscal_year": row.get("fiscal_year"),
            "report_type": row.get("report_type"),
            "source_tier": row.get("source_tier"),
            "source_family": row.get("source_family"),
            "source_locator_urls": source_locator_urls,
            "preferred_source_kinds": row.get("preferred_source_kinds") or [],
            "cache_dir": row.get("cache_dir"),
            "metadata_path": str(Path(str(row.get("cache_dir") or "")) / "locator_metadata.json").replace("\\", "/"),
            "download_strategy": _download_strategy(profile),
            "download_implementation_status": str(profile.get("download_implementation_status") or "profile_strategy_not_implemented").strip(),
            "download_blocker": str(profile.get("download_blocker") or "").strip(),
            "api_key_env": str(profile.get("api_key_env") or "").strip(),
            "parser_implementation_status": str(profile.get("parser_implementation_status") or "parser_not_started").strip(),
            "parser_blocker": str(profile.get("parser_blocker") or "").strip(),
            "download_status": "dry_run_ready",
            "document_downloaded": False,
            "profile_dispatch_status": "ready_for_profile_strategy",
            "implementation_status": "locator_only_scaffold",
            "source_boundary": row.get("source_boundary"),
        }
        tasks.append(task)
        if limit and len(tasks) >= limit:
            break
    return tasks, issues


def materialize_locator_metadata(tasks: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    materialized: list[dict[str, Any]] = []
    for task in tasks:
        row = dict(task)
        metadata_path = _resolve(Path(str(row.get("metadata_path") or "")))
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata = {
            "schema_version": "fin_agent_global_public_disclosure_locator_metadata_v0.1",
            "task_id": row.get("task_id"),
            "plan_id": row.get("plan_id"),
            "ticker": row.get("ticker"),
            "company_name": row.get("company_name"),
            "disclosure_profile": row.get("disclosure_profile"),
            "fiscal_year": row.get("fiscal_year"),
            "report_type": row.get("report_type"),
            "source_locator_urls": row.get("source_locator_urls"),
            "download_status": "locator_metadata_only",
            "document_downloaded": False,
        }
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        row["download_status"] = "locator_metadata_written"
        row["document_downloaded"] = False
        materialized.append(row)
    return materialized


def execute_download_tasks(
    tasks: Iterable[Mapping[str, Any]],
    *,
    timeout: float = 30.0,
    user_agent: str = "FinSight-Agent/0.1 research downloader contact@example.com",
    allow_company_ir_fallback: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    executed: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    candidate_cache: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for task in tasks:
        row = dict(task)
        strategy = str(row.get("download_strategy") or "")
        if strategy != "company_ir_official_report_download":
            if not allow_company_ir_fallback or not _task_allows_company_ir_fallback(row):
                status = _profile_strategy_blocked_status(row)
                row["download_status"] = status
                row["document_downloaded"] = False
                _write_profile_strategy_metadata(row, download_status=status)
                issues.append(
                    {
                        "type": status,
                        "task_id": row.get("task_id"),
                        "download_strategy": strategy,
                        "download_implementation_status": row.get("download_implementation_status"),
                        "download_blocker": row.get("download_blocker"),
                        "api_key_env": row.get("api_key_env"),
                    }
                )
                executed.append(row)
                continue
            row["primary_download_strategy"] = strategy
            row["download_strategy"] = "company_ir_official_report_fallback"
            row["source_policy"] = "profile_strategy_pending_company_ir_fallback"
        locator_key = tuple(str(url).strip() for url in row.get("source_locator_urls") or [] if str(url).strip())
        candidates = candidate_cache.get(locator_key)
        if candidates is None:
            candidates = discover_company_ir_report_candidates(row, timeout=timeout, user_agent=user_agent)
            candidate_cache[locator_key] = candidates
        result, issue = download_company_ir_official_report(row, timeout=timeout, user_agent=user_agent, candidates=candidates)
        executed.append(result)
        if issue:
            if row.get("source_policy") == "profile_strategy_pending_company_ir_fallback":
                issue = {
                    **issue,
                    "type": f"company_ir_fallback_{issue.get('type') or 'issue'}",
                    "primary_download_strategy": row.get("primary_download_strategy"),
                }
            issues.append(issue)
    return executed, issues


def _profile_strategy_blocked_status(task: Mapping[str, Any]) -> str:
    status = str(task.get("download_implementation_status") or "").strip()
    if status:
        return status
    return "profile_strategy_not_implemented"


def _write_profile_strategy_metadata(task: Mapping[str, Any], *, download_status: str) -> None:
    _write_download_metadata(
        task,
        {
            "download_status": download_status,
            "document_downloaded": False,
            "download_implementation_status": task.get("download_implementation_status"),
            "download_blocker": task.get("download_blocker"),
            "api_key_env": task.get("api_key_env"),
            "parser_implementation_status": task.get("parser_implementation_status"),
            "parser_blocker": task.get("parser_blocker"),
        },
    )


def _task_allows_company_ir_fallback(task: Mapping[str, Any]) -> bool:
    preferred_source_kinds = {str(value).lower() for value in task.get("preferred_source_kinds") or []}
    if "company_ir" in preferred_source_kinds:
        return True
    urls = [str(url).lower() for url in task.get("source_locator_urls") or []]
    return any("investor" in url or "/ir" in url or "reports" in url for url in urls)


def download_company_ir_official_report(
    task: Mapping[str, Any],
    *,
    timeout: float = 30.0,
    user_agent: str = "FinSight-Agent/0.1 research downloader contact@example.com",
    candidates: Iterable[Mapping[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    row = dict(task)
    try:
        candidate_rows = list(candidates) if candidates is not None else discover_company_ir_report_candidates(row, timeout=timeout, user_agent=user_agent)
        selected = select_best_report_candidate(candidate_rows, fiscal_year=int(row.get("fiscal_year")), report_type=str(row.get("report_type") or ""))
        if not selected:
            row["download_status"] = "no_matching_document_candidate"
            row["document_downloaded"] = False
            row["candidate_count"] = len(candidate_rows)
            _write_download_metadata(
                row,
                {
                    "download_status": "no_matching_document_candidate",
                    "document_downloaded": False,
                    "candidate_count": len(candidate_rows),
                    "candidate_sample": list(candidate_rows[:10]),
                },
            )
            return row, {"type": "no_matching_document_candidate", "task_id": row.get("task_id"), "ticker": row.get("ticker"), "candidate_count": len(candidate_rows)}
        document_url = str(selected["url"])
        row["selected_candidate_url"] = document_url
        row["selected_candidate_score"] = selected.get("score")
        payload, headers = _fetch_bytes(document_url, timeout=timeout, user_agent=user_agent)
        sha256 = hashlib.sha256(payload).hexdigest()
        cache_dir = _resolve(Path(str(row.get("cache_dir") or "")))
        cache_dir.mkdir(parents=True, exist_ok=True)
        file_name = _safe_file_name(Path(urlparse(document_url).path).name or "official_report.pdf")
        document_path = cache_dir / file_name
        document_path.write_bytes(payload)
        documented_path = _path_for_metadata(document_path)
        metadata = {
            "source_url": document_url,
            "document_path": documented_path,
            "content_type": headers.get("content-type", ""),
            "byte_count": len(payload),
            "sha256": sha256,
            "selected_candidate": selected,
            "candidate_count": len(candidate_rows),
            "document_downloaded": True,
            "download_status": "document_downloaded",
        }
        _write_download_metadata(row, metadata)
        row.update(
            {
                "download_status": "document_downloaded",
                "document_downloaded": True,
                "document_path": documented_path,
                "document_url": document_url,
                "downloaded_bytes": len(payload),
                "sha256": sha256,
                "candidate_count": len(candidate_rows),
                "selected_candidate_score": selected.get("score"),
            }
        )
        return row, None
    except Exception as exc:  # noqa: BLE001 - downloader records structured issue instead of hiding runtime detail.
        row["download_status"] = "download_error"
        row["document_downloaded"] = False
        return row, {
            "type": "download_error",
            "task_id": row.get("task_id"),
            "ticker": row.get("ticker"),
            "selected_candidate_url": row.get("selected_candidate_url"),
            "error": str(exc),
        }


def _write_download_metadata(task: Mapping[str, Any], metadata: Mapping[str, Any]) -> None:
    cache_dir = _resolve(Path(str(task.get("cache_dir") or "")))
    metadata_path = _resolve(Path(str(task.get("metadata_path") or cache_dir / "locator_metadata.json")))
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "fin_agent_global_public_disclosure_download_metadata_v0.1",
        "task_id": task.get("task_id"),
        "plan_id": task.get("plan_id"),
        "ticker": task.get("ticker"),
        "company_name": task.get("company_name"),
        "disclosure_profile": task.get("disclosure_profile"),
        "fiscal_year": task.get("fiscal_year"),
        "report_type": task.get("report_type"),
        "source_tier": task.get("source_tier"),
        "source_family": task.get("source_family"),
        "source_locator_urls": task.get("source_locator_urls") or [],
        "source_policy": task.get("source_policy"),
        "primary_download_strategy": task.get("primary_download_strategy"),
        "download_strategy": task.get("download_strategy"),
        **dict(metadata),
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    metadata_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def discover_company_ir_report_candidates(
    task: Mapping[str, Any],
    *,
    timeout: float = 30.0,
    user_agent: str = "FinSight-Agent/0.1 research downloader contact@example.com",
) -> list[dict[str, Any]]:
    roots = [str(url).strip() for url in task.get("source_locator_urls") or [] if str(url).strip()]
    seen_pages: set[str] = set()
    pages_to_fetch = list(roots)
    candidates: list[dict[str, Any]] = []
    root_hosts = {urlparse(root).netloc.lower() for root in roots if urlparse(root).netloc}
    while pages_to_fetch and len(seen_pages) < 8:
        page_url = pages_to_fetch.pop(0)
        if page_url in seen_pages:
            continue
        if root_hosts and urlparse(page_url).netloc.lower() not in root_hosts:
            continue
        seen_pages.add(page_url)
        try:
            html_text = _fetch_text(page_url, timeout=timeout, user_agent=user_agent)
        except (HTTPError, URLError, TimeoutError):
            continue
        candidates.extend(_candidate_links_from_text(page_url, html_text, source_stage="locator_page"))
        for api_url in _extract_api_urls(page_url, html_text):
            try:
                api_text = _fetch_text(api_url, timeout=timeout, user_agent=user_agent, accept="application/json")
            except (HTTPError, URLError, TimeoutError):
                continue
            candidates.extend(_candidate_links_from_json_text(api_url, api_text))
        for related_url in _related_report_pages(page_url, html_text):
            if related_url not in seen_pages and _same_host(page_url, related_url):
                pages_to_fetch.append(related_url)
        pages_to_fetch = list(dict.fromkeys(pages_to_fetch))[:12]
    return _dedupe_candidates(candidates)


def select_best_report_candidate(candidates: Iterable[Mapping[str, Any]], *, fiscal_year: int, report_type: str) -> dict[str, Any] | None:
    scored: list[dict[str, Any]] = []
    for candidate in candidates:
        row = dict(candidate)
        haystack = " ".join(str(row.get(key) or "") for key in ("url", "text", "display_name", "file_name", "released_date")).lower()
        score = 0
        if str(fiscal_year) in haystack:
            score += 20
        if ".pdf" in str(row.get("url") or "").lower():
            score += 8
        if report_type == "annual_report" and ("annual report" in haystack or "annual-report" in haystack):
            score += 10
        if report_type == "business_report" and "business" in haystack and "report" in haystack:
            score += 10
        if report_type == "integrated_report" and "integrated" in haystack and "report" in haystack:
            score += 10
        if report_type == "annual_securities_report" and ("securities report" in haystack or "annual securities" in haystack):
            score += 10
        if report_type in {"annual_report", "business_report", "integrated_report", "annual_securities_report"} and not _has_annual_like_report_term(haystack):
            continue
        display_name = str(row.get("display_name") or "").strip().lower()
        file_name = str(row.get("file_name") or "").strip().lower()
        if report_type == "annual_report" and (display_name.startswith("annual report") or "annual-report" in file_name):
            score += 8
        if "annual general meeting" in haystack or "agm" in haystack:
            score -= 12
        if any(term in haystack for term in ("sustainability", "remuneration", "financial data", "presentation", "half-year", "half_interim", "half interim", "interim report", "semiannual", "quarter", "press", "news release")):
            score -= 18
        if score < 20:
            continue
        row["score"] = score
        scored.append(row)
    if not scored:
        return None
    return sorted(scored, key=lambda item: (int(item.get("score") or 0), str(item.get("url") or "")), reverse=True)[0]


def _has_annual_like_report_term(haystack: str) -> bool:
    return any(
        term in haystack
        for term in (
            "annual report",
            "annual-report",
            "business report",
            "business-report",
            "annual securities report",
            "annual-securities-report",
            "integrated report",
            "integrated-report",
        )
    )


def summarize_download_tasks(
    *,
    tasks: list[Mapping[str, Any]],
    issues: list[Mapping[str, Any]],
    queue_output: Path,
    summary_output: Path,
) -> dict[str, Any]:
    return {
        "schema_version": "fin_agent_global_public_disclosure_download_tasks_summary_v0.1",
        "status": "fail" if issues else "pass",
        "task_count": len(tasks),
        "company_count": len({str(task.get("ticker") or "") for task in tasks}),
        "profile_counts": dict(sorted(Counter(str(task.get("disclosure_profile") or "unknown") for task in tasks).items())),
        "report_type_counts": dict(sorted(Counter(str(task.get("report_type") or "unknown") for task in tasks).items())),
        "download_strategy_counts": dict(sorted(Counter(str(task.get("download_strategy") or "unknown") for task in tasks).items())),
        "download_status_counts": dict(sorted(Counter(str(task.get("download_status") or "unknown") for task in tasks).items())),
        "document_downloaded_count": sum(1 for task in tasks if task.get("document_downloaded")),
        "downloaded_byte_count": sum(int(task.get("downloaded_bytes") or 0) for task in tasks),
        "issue_counts": dict(sorted(Counter(str(issue.get("type") or "unknown") for issue in issues).items())),
        "issues": list(issues),
        "outputs": {"download_tasks": _path_for_metadata(queue_output), "summary": _path_for_metadata(summary_output)},
    }


def _download_strategy(profile: Mapping[str, Any]) -> str:
    strategy = str(profile.get("locator_strategy") or "").strip()
    if strategy:
        return strategy
    return "profile_specific_locator"


class _URLCollector(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[dict[str, str]] = []
        self._active_url = ""
        self._active_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key.lower(): value or "" for key, value in attrs}
        for key in ("href", "src", "data-href", "data-api", "data-nocacheapi"):
            if attr_map.get(key):
                url = html.unescape(attr_map[key])
                self.links.append({"url": urljoin(self.base_url, url), "text": "", "attr": key})
        if tag.lower() == "a" and attr_map.get("href"):
            self._active_url = urljoin(self.base_url, html.unescape(attr_map["href"]))
            self._active_text = []

    def handle_data(self, data: str) -> None:
        if self._active_url:
            self._active_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._active_url:
            text = " ".join(part.strip() for part in self._active_text if part.strip())
            self.links.append({"url": self._active_url, "text": text, "attr": "href_text"})
            self._active_url = ""
            self._active_text = []


def _candidate_links_from_text(base_url: str, text: str, *, source_stage: str) -> list[dict[str, Any]]:
    parser = _URLCollector(base_url)
    parser.feed(text)
    candidates: list[dict[str, Any]] = []
    for link in parser.links:
        url = link["url"]
        if ".pdf" in url.lower():
            candidates.append({"url": url, "text": link.get("text", ""), "source_stage": source_stage, "candidate_source": "html_link"})
    for match in re.finditer(r"https?://[^\"'<> ]+?\.pdf|/[^\"'<> ]+?\.pdf", text, flags=re.IGNORECASE):
        candidates.append({"url": urljoin(base_url, html.unescape(match.group(0))), "text": "", "source_stage": source_stage, "candidate_source": "html_regex"})
    return candidates


def _extract_api_urls(base_url: str, text: str) -> list[str]:
    parser = _URLCollector(base_url)
    parser.feed(text)
    api_urls = [
        link["url"]
        for link in parser.links
        if "product-document" in link["url"].lower() and ("json" in link["url"].lower() or "dataapi" in link["url"].lower())
    ]
    return list(dict.fromkeys(api_urls))


def _related_report_pages(base_url: str, text: str) -> list[str]:
    parser = _URLCollector(base_url)
    parser.feed(text)
    scored: list[tuple[int, str]] = []
    for link in parser.links:
        haystack = (link.get("url", "") + " " + link.get("text", "")).lower()
        score = 0
        url = link.get("url", "")
        if ".pdf" in haystack:
            continue
        if "annual-reports" in haystack or ("annual" in haystack and "report" in haystack):
            score += 30
        elif "reports-presentations" in haystack:
            score += 10
        if url.rstrip("/") == base_url.rstrip("/"):
            score = 0
        if score:
            scored.append((score, link["url"]))
    return list(dict.fromkeys(url for _, url in sorted(scored, key=lambda item: item[0], reverse=True)))


def _candidate_links_from_json_text(api_url: str, text: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return _candidate_links_from_text(api_url, text, source_stage="api_text")
    for item in _walk_json_objects(payload):
        url = _document_url_from_json_item(api_url, item)
        if not url:
            continue
        candidates.append(
            {
                "url": url,
                "text": str(item.get("divShortDescr") or item.get("description") or ""),
                "display_name": str(item.get("documentDisplayName") or item.get("title") or ""),
                "file_name": str(item.get("filename") or ""),
                "released_date": str(item.get("releasedDate") or item.get("date") or ""),
                "source_stage": "api_json",
                "candidate_source": "document_json",
            }
        )
    return candidates


def _walk_json_objects(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk_json_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json_objects(child)


def _document_url_from_json_item(api_url: str, item: Mapping[str, Any]) -> str:
    for key in ("downloadUrl", "url", "href", "assetUrl"):
        value = str(item.get(key) or "").strip()
        if value and ".pdf" in value.lower():
            return urljoin(api_url, value)
    path = str(item.get("assetDamPath") or "").strip()
    filename = str(item.get("filename") or "").strip()
    if path and filename and filename.lower().endswith(".pdf"):
        normalized_path = path.rstrip("/")
        if normalized_path.lower().endswith(".pdf"):
            return urljoin(api_url, normalized_path)
        if normalized_path.startswith("/assets/"):
            return urljoin(api_url, f"{normalized_path}/{filename}")
        return urljoin(api_url, f"/assets/row/public{normalized_path}/{filename}")
    return ""


def _dedupe_candidates(candidates: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        url = str(candidate.get("url") or "").strip()
        if not url:
            continue
        result.setdefault(url, dict(candidate))
    return list(result.values())


def _fetch_text(url: str, *, timeout: float, user_agent: str, accept: str = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8") -> str:
    payload, _ = _fetch_bytes(url, timeout=timeout, user_agent=user_agent, accept=accept)
    return payload.decode("utf-8", "replace")


def _fetch_bytes(
    url: str,
    *,
    timeout: float,
    user_agent: str,
    accept: str = "application/pdf,text/html,application/xhtml+xml,application/json,*/*;q=0.8",
) -> tuple[bytes, Mapping[str, str]]:
    request = Request(url, headers={"User-Agent": user_agent, "Accept": accept})
    with urlopen(request, timeout=timeout) as response:
        return response.read(), {key.lower(): value for key, value in response.headers.items()}


def _same_host(left: str, right: str) -> bool:
    return urlparse(left).netloc.lower() == urlparse(right).netloc.lower()


def _safe_file_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return safe or "official_report.pdf"


def _path_for_metadata(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
