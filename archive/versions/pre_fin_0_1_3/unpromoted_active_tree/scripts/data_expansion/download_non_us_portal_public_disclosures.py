from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urljoin

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

import download_global_public_disclosures as base


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_PLAN = REPO_ROOT / "data" / "manifests" / "tier2_global_public_disclosure_source_plan_v0_1.jsonl"
DEFAULT_QUEUE_OUTPUT = REPO_ROOT / "data" / "manifests" / "tier2_global_public_disclosure_portal_download_clean_v0_1.jsonl"
DEFAULT_SUMMARY_OUTPUT = REPO_ROOT / "data" / "manifests" / "tier2_global_public_disclosure_portal_download_clean_summary_v0_1.json"
SCHEMA_VERSION = "fin_agent_global_public_disclosure_download_task_v0.1"
HKEX_SEARCH_URL = "https://www1.hkexnews.hk/search/titleSearchServlet.do"
HKEX_PARTIAL_URL = "https://www1.hkexnews.hk/search/partial.do"
CNINFO_SEARCH_URL = "http://www.cninfo.com.cn/new/information/topSearch/query"
CNINFO_ANNOUNCEMENT_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_STATIC_ROOT = "http://static.cninfo.com.cn/"
MOPS_DOCUMENT_URL = "https://doc.twse.com.tw/server-java/t57sb01"
MOPS_STATIC_ROOT = "https://doc.twse.com.tw/"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download profile-specific public portal disclosures for non-US supply-chain issuers.")
    parser.add_argument("--source-plan", type=Path, default=DEFAULT_SOURCE_PLAN)
    parser.add_argument("--queue-output", type=Path, default=DEFAULT_QUEUE_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--profile", default="", help="Comma-separated profile filter. Defaults to HKEX and CNINFO implemented profiles.")
    parser.add_argument("--ticker", default="", help="Optional ticker filter.")
    parser.add_argument("--cache-root", type=Path, default=None)
    parser.add_argument("--processed-root", type=Path, default=None)
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--user-agent", default="FinSight-Agent/0.1 non-us-portal-downloader contact@example.com")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    base.configure_disclosure_storage(cache_root=args.cache_root, processed_root=args.processed_root)
    plan_rows = _load_jsonl(_resolve(args.source_plan))
    profile_filter = set(_split_csv(args.profile)) or {"tw_mops_annual_report", "hkex_annual_report", "szse_cninfo_annual_report"}
    ticker_filter = args.ticker.upper().strip()
    selected_plan_rows = [
        row
        for row in plan_rows
        if str(row.get("disclosure_profile") or "") in profile_filter
        and (not ticker_filter or str(row.get("ticker") or "").upper() == ticker_filter)
    ]
    session = requests.Session()
    session.headers.update({"User-Agent": args.user_agent, "Accept": "application/json,text/html,application/pdf,*/*"})
    downloaded, issues = execute_portal_downloads(selected_plan_rows, session=session, timeout=args.timeout)
    queue_output = _resolve(args.queue_output)
    summary_output = _resolve(args.summary_output)
    queue_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl(queue_output, downloaded)
    summary = summarize_downloads(downloaded=downloaded, issues=issues, queue_output=queue_output, summary_output=summary_output)
    summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


def execute_portal_downloads(
    plan_rows: Iterable[Mapping[str, Any]],
    *,
    session: requests.Session,
    timeout: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    hkex_stock_id_cache: dict[str, str] = {}
    cninfo_org_id_cache: dict[str, str] = {}
    for plan in plan_rows:
        profile = str(plan.get("disclosure_profile") or "")
        if profile == "tw_mops_annual_report":
            row, issue = download_tw_mops_annual_report(plan, session=session, timeout=timeout)
        elif profile == "hkex_annual_report":
            row, issue = download_hkex_annual_report(plan, session=session, timeout=timeout, stock_id_cache=hkex_stock_id_cache)
        elif profile == "szse_cninfo_annual_report":
            row, issue = download_cninfo_annual_report(plan, session=session, timeout=timeout, org_id_cache=cninfo_org_id_cache)
        else:
            row = base_task_row(plan)
            row["download_status"] = "profile_not_implemented_in_portal_downloader"
            row["document_downloaded"] = False
            issue = {"type": "profile_not_implemented_in_portal_downloader", "task_id": row["task_id"], "ticker": row.get("ticker"), "profile": profile}
        rows.append(row)
        if issue:
            issues.append(issue)
    return rows, issues


def download_tw_mops_annual_report(
    plan: Mapping[str, Any],
    *,
    session: requests.Session,
    timeout: float,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    row = base_task_row(plan)
    row["download_strategy"] = "mops_annual_report_f04_download"
    code = str(plan.get("exchange_symbol") or "").strip()
    fiscal_year = int(plan.get("fiscal_year") or 0)
    if not code or not fiscal_year:
        return mark_gap(row, "mops_missing_code_or_fiscal_year", "MOPS annual report lookup requires exchange_symbol and fiscal_year.")
    filenames = query_mops_annual_report_filenames(session=session, stock_code=code, fiscal_year=fiscal_year, timeout=timeout)
    selected_filename = select_mops_annual_report_filename(filenames, stock_code=code, fiscal_year=fiscal_year)
    if not selected_filename:
        return mark_gap(row, "mops_annual_report_not_found", f"No MOPS F04 annual report matched fiscal_year={fiscal_year}.")
    pdf_url = resolve_mops_pdf_url(session=session, stock_code=code, filename=selected_filename, timeout=timeout)
    if not pdf_url:
        return mark_gap(row, "mops_pdf_url_not_found", f"MOPS step=9 returned no PDF href for {selected_filename}.")
    selected = {
        "mops_year": fiscal_year - 1910,
        "filename": selected_filename,
        "candidate_count": len(filenames),
        "query_kind": "F",
        "query_dtype": "F04",
    }
    return download_selected_pdf(row, session=session, timeout=timeout, document_url=pdf_url, selected=selected, source_policy="official_market_disclosure_system")


def query_mops_annual_report_filenames(*, session: requests.Session, stock_code: str, fiscal_year: int, timeout: float) -> list[str]:
    # MOPS annual reports are filed in the shareholder-meeting year: fiscal 2024 -> Minguo year 114.
    mops_year = fiscal_year - 1910
    response = session.post(
        MOPS_DOCUMENT_URL,
        data={
            "id": "",
            "key": "",
            "step": "1",
            "co_id": stock_code,
            "year": str(mops_year),
            "seamon": "",
            "mtype": "F",
            "dtype": "F04",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return extract_pdf_filenames(response.text)


def select_mops_annual_report_filename(filenames: Iterable[str], *, stock_code: str, fiscal_year: int) -> str:
    expected_prefix = f"{fiscal_year}_{stock_code}_"
    scored: list[tuple[int, str]] = []
    for filename in dict.fromkeys(str(item or "").strip() for item in filenames if str(item or "").strip()):
        lowered = filename.lower()
        if not lowered.endswith(".pdf"):
            continue
        if "f04" not in lowered:
            continue
        score = 10
        if filename.startswith(expected_prefix):
            score += 100
        if f"_{stock_code}_" in filename:
            score += 20
        if str(fiscal_year) in filename:
            score += 20
        scored.append((score, filename))
    return sorted(scored, reverse=True)[0][1] if scored else ""


def resolve_mops_pdf_url(*, session: requests.Session, stock_code: str, filename: str, timeout: float) -> str:
    response = session.post(
        MOPS_DOCUMENT_URL,
        data={"step": "9", "kind": "F", "co_id": stock_code, "filename": filename},
        timeout=timeout,
    )
    response.raise_for_status()
    href = extract_pdf_href(response.text)
    return urljoin(MOPS_STATIC_ROOT, href) if href else ""


def extract_pdf_filenames(text: str) -> list[str]:
    return [html.unescape(match.group(0)) for match in re_find_pdf_names(text)]


def extract_pdf_href(text: str) -> str:
    for match in re_find_pdf_hrefs(text):
        return html.unescape(match)
    return ""


def download_hkex_annual_report(
    plan: Mapping[str, Any],
    *,
    session: requests.Session,
    timeout: float,
    stock_id_cache: dict[str, str],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    row = base_task_row(plan)
    row["download_strategy"] = "hkexnews_issuer_report_search"
    code = str(plan.get("exchange_symbol") or "").zfill(5)
    fiscal_year = int(plan.get("fiscal_year") or 0)
    stock_id = stock_id_cache.get(code)
    if not stock_id:
        stock_id = lookup_hkex_stock_id(session=session, stock_code=code, timeout=timeout)
        if stock_id:
            stock_id_cache[code] = stock_id
    if not stock_id:
        return mark_gap(row, "hkex_stock_id_not_found", "HKEX stockId lookup returned no issuer match.")
    candidates = query_hkex_annual_reports(session=session, stock_id=stock_id, fiscal_year=fiscal_year, timeout=timeout)
    selected = select_hkex_annual_report(candidates, fiscal_year=fiscal_year)
    if not selected:
        return mark_gap(row, "hkex_annual_report_not_found", f"No HKEX annual report matched fiscal_year={fiscal_year}.")
    document_url = urljoin("https://www1.hkexnews.hk/", str(selected.get("FILE_LINK") or ""))
    return download_selected_pdf(row, session=session, timeout=timeout, document_url=document_url, selected=selected, source_policy="official_exchange_portal")


def lookup_hkex_stock_id(*, session: requests.Session, stock_code: str, timeout: float) -> str:
    response = session.get(
        HKEX_PARTIAL_URL,
        params={"lang": "EN", "type": "A", "name": stock_code, "market": "SEHK", "callback": "callback"},
        headers={"Referer": "https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=en"},
        timeout=timeout,
    )
    payload = parse_jsonp(response.text)
    for item in payload.get("stockInfo") or []:
        if str(item.get("code") or "").zfill(5) == stock_code:
            return str(item.get("stockId") or "")
    return ""


def query_hkex_annual_reports(*, session: requests.Session, stock_id: str, fiscal_year: int, timeout: float) -> list[dict[str, Any]]:
    response = session.get(
        HKEX_SEARCH_URL,
        params={
            "sortDir": "0",
            "sortByOptions": "DateTime",
            "category": "0",
            "market": "SEHK",
            "stockId": stock_id,
            "documentType": "",
            "fromDate": f"{fiscal_year + 1}0101",
            "toDate": f"{fiscal_year + 1}1231",
            "title": "Annual Report",
            "searchType": "0",
            "t1code": "",
            "t2Gcode": "",
            "t2code": "",
            "rowRange": "100",
            "lang": "en",
        },
        headers={"Referer": "https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=en"},
        timeout=timeout,
    )
    payload = response.json()
    result = payload.get("result") or "[]"
    return [dict(item) for item in json.loads(result)]


def select_hkex_annual_report(candidates: Iterable[Mapping[str, Any]], *, fiscal_year: int) -> dict[str, Any] | None:
    expected_terms = {f"{fiscal_year} annual report", f"annual report {fiscal_year}"}
    scored: list[dict[str, Any]] = []
    for candidate in candidates:
        title = html.unescape(str(candidate.get("TITLE") or "")).lower()
        short_text = html.unescape(str(candidate.get("SHORT_TEXT") or "")).lower()
        if not any(term in title for term in expected_terms):
            continue
        if "interim" in title or "summary" in title:
            continue
        score = 100
        if "printed version" in title:
            score -= 20
        if "annual report" in short_text:
            score += 10
        row = dict(candidate)
        row["selection_score"] = score
        scored.append(row)
    return sorted(scored, key=lambda item: (int(item.get("selection_score") or 0), str(item.get("DATE_TIME") or "")), reverse=True)[0] if scored else None


def download_cninfo_annual_report(
    plan: Mapping[str, Any],
    *,
    session: requests.Session,
    timeout: float,
    org_id_cache: dict[str, str],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    row = base_task_row(plan)
    row["download_strategy"] = "cninfo_security_report_search"
    code = str(plan.get("exchange_symbol") or "").strip()
    fiscal_year = int(plan.get("fiscal_year") or 0)
    org_id = org_id_cache.get(code)
    if not org_id:
        org_id = lookup_cninfo_org_id(session=session, stock_code=code, timeout=timeout)
        if org_id:
            org_id_cache[code] = org_id
    if not org_id:
        return mark_gap(row, "cninfo_org_id_not_found", "CNINFO topSearch returned no orgId.")
    candidates = query_cninfo_annual_reports(session=session, stock_code=code, org_id=org_id, timeout=timeout)
    selected = select_cninfo_annual_report(candidates, fiscal_year=fiscal_year)
    if not selected:
        return mark_gap(row, "cninfo_annual_report_not_found", f"No CNINFO annual report matched fiscal_year={fiscal_year}.")
    document_url = urljoin(CNINFO_STATIC_ROOT, str(selected.get("adjunctUrl") or ""))
    return download_selected_pdf(row, session=session, timeout=timeout, document_url=document_url, selected=selected, source_policy="official_disclosure_platform")


def lookup_cninfo_org_id(*, session: requests.Session, stock_code: str, timeout: float) -> str:
    response = session.post(CNINFO_SEARCH_URL, data={"keyWord": stock_code, "maxNum": "10"}, timeout=timeout)
    for item in response.json():
        if str(item.get("code") or "") == stock_code and item.get("orgId"):
            return str(item["orgId"])
    return ""


def query_cninfo_annual_reports(*, session: requests.Session, stock_code: str, org_id: str, timeout: float) -> list[dict[str, Any]]:
    response = session.post(
        CNINFO_ANNOUNCEMENT_URL,
        data={
            "pageNum": "1",
            "pageSize": "30",
            "column": "szse",
            "tabName": "fulltext",
            "plate": "sz",
            "stock": f"{stock_code},{org_id}",
            "searchkey": "",
            "secid": "",
            "category": "category_ndbg_szsh",
            "trade": "",
            "seDate": "2023-01-01~2026-12-31",
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        },
        headers={"Referer": "http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search"},
        timeout=timeout,
    )
    payload = response.json()
    return [dict(item) for item in payload.get("announcements") or []]


def select_cninfo_annual_report(candidates: Iterable[Mapping[str, Any]], *, fiscal_year: int) -> dict[str, Any] | None:
    expected = f"{fiscal_year}年年度报告"
    scored: list[dict[str, Any]] = []
    for candidate in candidates:
        title = str(candidate.get("announcementTitle") or "").replace("<em>", "").replace("</em>", "")
        if expected not in title:
            continue
        if "摘要" in title or "更正" in title:
            continue
        row = dict(candidate)
        row["selection_score"] = 100
        scored.append(row)
    return sorted(scored, key=lambda item: (int(item.get("selection_score") or 0), int(item.get("announcementTime") or 0)), reverse=True)[0] if scored else None


def download_selected_pdf(
    row: dict[str, Any],
    *,
    session: requests.Session,
    timeout: float,
    document_url: str,
    selected: Mapping[str, Any],
    source_policy: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    try:
        response = session.get(document_url, timeout=timeout)
        response.raise_for_status()
        payload = response.content
        cache_dir = _resolve_path(row["cache_dir"])
        cache_dir.mkdir(parents=True, exist_ok=True)
        file_name = base._safe_file_name(Path(document_url.split("?", 1)[0]).name or "official_report.pdf")
        document_path = cache_dir / file_name
        document_path.write_bytes(payload)
        headers = {key.lower(): value for key, value in response.headers.items()}
        clean_result = base.clean_downloaded_report_document(document_path=document_path, payload=payload, headers=headers, cache_dir=cache_dir)
        sha256 = hashlib.sha256(payload).hexdigest()
        metadata = {
            "source_url": document_url,
            "document_path": base._path_for_metadata(document_path),
            "content_type": headers.get("content-type", ""),
            "byte_count": len(payload),
            "sha256": sha256,
            "selected_candidate": dict(selected),
            "document_downloaded": True,
            "download_status": "document_downloaded",
            "source_policy": source_policy,
            **clean_result,
        }
        base._write_download_metadata(row, metadata)
        row.update(
            {
                "download_status": "document_downloaded" if clean_result.get("cleaned_text_status") != "cleaned_text_written" else "document_downloaded_cleaned",
                "document_downloaded": True,
                "document_path": base._path_for_metadata(document_path),
                "document_url": document_url,
                "downloaded_bytes": len(payload),
                "sha256": sha256,
                "source_policy": source_policy,
                "cleaned_text_path": clean_result.get("cleaned_text_path", ""),
                "cleaned_text_char_count": clean_result.get("cleaned_text_char_count", 0),
                "cleaned_text_status": clean_result.get("cleaned_text_status", ""),
                "parser_status": clean_result.get("parser_status", ""),
            }
        )
        return row, None
    except Exception as exc:  # noqa: BLE001
        return mark_gap(row, "portal_download_error", base.redact_text(str(exc)))


def base_task_row(plan: Mapping[str, Any]) -> dict[str, Any]:
    cache_dir = base._cache_dir_for_task(plan.get("cache_dir"))
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": "DOWNLOAD::" + str(plan.get("plan_id") or ""),
        "plan_id": plan.get("plan_id"),
        "ticker": str(plan.get("ticker") or "").upper(),
        "issuer_id": plan.get("issuer_id"),
        "exchange_symbol": plan.get("exchange_symbol"),
        "company_name": plan.get("company_name"),
        "disclosure_profile": plan.get("disclosure_profile"),
        "fiscal_year": plan.get("fiscal_year"),
        "report_type": plan.get("report_type"),
        "source_tier": plan.get("source_tier"),
        "source_family": plan.get("source_family"),
        "source_locator_urls": plan.get("source_locator_urls") or [],
        "cache_dir": base._path_for_metadata(cache_dir),
        "metadata_path": base._path_for_metadata(cache_dir / "locator_metadata.json"),
        "source_boundary": plan.get("source_boundary"),
        "document_downloaded": False,
        "download_status": "dry_run_ready",
        "profile_dispatch_status": "ready_for_portal_strategy",
    }


def mark_gap(row: dict[str, Any], gap_type: str, detail: str) -> tuple[dict[str, Any], dict[str, Any]]:
    row["download_status"] = gap_type
    row["document_downloaded"] = False
    base._write_download_metadata(
        row,
        {
            "download_status": gap_type,
            "document_downloaded": False,
            "gap_detail": detail,
        },
    )
    return row, {"type": gap_type, "task_id": row.get("task_id"), "ticker": row.get("ticker"), "detail": detail}


def summarize_downloads(*, downloaded: list[Mapping[str, Any]], issues: list[Mapping[str, Any]], queue_output: Path, summary_output: Path) -> dict[str, Any]:
    return {
        "schema_version": "fin_agent_global_public_disclosure_portal_download_summary_v0.1",
        "status": "fail" if issues else "pass",
        "task_count": len(downloaded),
        "company_count": len({str(row.get("ticker") or "") for row in downloaded}),
        "profile_counts": dict(sorted(Counter(str(row.get("disclosure_profile") or "unknown") for row in downloaded).items())),
        "download_status_counts": dict(sorted(Counter(str(row.get("download_status") or "unknown") for row in downloaded).items())),
        "document_downloaded_count": sum(1 for row in downloaded if row.get("document_downloaded")),
        "downloaded_byte_count": sum(int(row.get("downloaded_bytes") or 0) for row in downloaded),
        "cleaned_text_char_count": sum(int(row.get("cleaned_text_char_count") or 0) for row in downloaded),
        "issue_counts": dict(sorted(Counter(str(issue.get("type") or "unknown") for issue in issues).items())),
        "issues": list(issues),
        "outputs": {"download_tasks": base._path_for_metadata(queue_output), "summary": base._path_for_metadata(summary_output)},
    }


def parse_jsonp(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("callback(") and stripped.endswith(");"):
        stripped = stripped[len("callback(") : -2]
    return json.loads(stripped)


def re_find_pdf_names(text: str) -> list[Any]:
    import re

    return list(re.finditer(r"[\w\-\u4e00-\u9fff%()（）]+\.pdf", text, flags=re.IGNORECASE))


def re_find_pdf_hrefs(text: str) -> list[str]:
    import re

    return [match.group(1) for match in re.finditer(r"""href=["']([^"']+?\.pdf)["']""", text, flags=re.IGNORECASE)]


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


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _resolve_path(value: str) -> Path:
    return _resolve(Path(str(value or "")))


if __name__ == "__main__":
    raise SystemExit(main())
