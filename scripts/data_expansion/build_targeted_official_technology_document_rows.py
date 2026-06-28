from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


SCHEMA_VERSION = "finsight_targeted_official_technology_document_context_row_v0_1"
ATTEMPT_SCHEMA_VERSION = "finsight_targeted_official_technology_document_attempt_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_targeted_official_technology_document_summary_v0_1"

SOURCE_ID = "official_technical_document"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "targeted_official_technology_document_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_ATTEMPTS = REPO_ROOT / "data" / "manifests" / "targeted_official_technology_document_attempts_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "targeted_official_technology_document_summary_v0_1.json"
DEFAULT_RAW_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/official_technology_documents")

USER_AGENT = "Mozilla/5.0 FIN-Insight-Agent official technical document parser"

TARGETED_OFFICIAL_TECHNOLOGY_SEEDS: dict[str, tuple[dict[str, Any], ...]] = {
    "PLTR": (
        {
            "url": "https://www.palantir.com/platforms/foundry/",
            "issuer_aliases": ("Palantir", "Palantir Foundry"),
            "topic_terms": ("Foundry", "Ontology", "AIP", "data platform"),
            "doc_label": "Palantir Foundry official product/ontology surface",
        },
    ),
    "MPWR": (
        {
            "url": "https://www.monolithicpower.com/dc-dc-power-converters-lp",
            "issuer_aliases": ("Monolithic Power Systems", "MPS"),
            "topic_terms": ("DC-DC", "power converter", "buck", "boost", "power semiconductor"),
            "doc_label": "MPS official DC-DC power converter technology surface",
            "fetch_transport": "browser_rendered",
        },
    ),
    "300750.SZ": (
        {
            "url": "https://www.catl.com/en/research/technology/",
            "issuer_aliases": ("CATL", "Contemporary Amperex", "Contemporary Amperex Technology"),
            "topic_terms": ("battery", "lithium", "cell", "energy storage"),
            "doc_label": "CATL official technology/R&D surface",
        },
    ),
    "373220.KS": (
        {
            "url": "https://www.lgensol.com/mobile/en/company/rnd-battery1",
            "issuer_aliases": ("LG Energy Solution", "LGES"),
            "topic_terms": ("battery", "lithium", "cell", "energy"),
            "doc_label": "LG Energy Solution official battery R&D surface",
        },
    ),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build issuer/topic-bound official technology document proxy rows.")
    parser.add_argument("--tickers", nargs="*", default=[])
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-attempts", type=Path, default=DEFAULT_OUTPUT_ATTEMPTS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--timeout-s", type=float, default=25.0)
    parser.add_argument("--replace-output", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    rows, attempts = build_targeted_official_technology_document_rows(
        tickers=args.tickers,
        generated_at=generated_at,
        raw_dir=args.raw_dir,
        timeout_s=args.timeout_s,
    )
    output_rows = rows if args.replace_output else _dedupe_rows([*_load_jsonl(args.output_rows), *rows])
    output_attempts = attempts if args.replace_output else _dedupe_attempts([*_load_jsonl(args.output_attempts), *attempts])
    summary = build_summary(rows=output_rows, attempts=output_attempts, generated_at=generated_at, output_rows=args.output_rows, output_attempts=args.output_attempts)
    _write_jsonl(args.output_rows, output_rows)
    _write_jsonl(args.output_attempts, output_attempts)
    _write_json(args.output_summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and not rows:
        return 1
    return 0


def build_targeted_official_technology_document_rows(
    *,
    tickers: Iterable[str] = (),
    generated_at: str,
    raw_dir: Path,
    timeout_s: float = 25.0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ticker_filter = {str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()}
    target_tickers = [ticker for ticker in TARGETED_OFFICIAL_TECHNOLOGY_SEEDS if not ticker_filter or ticker in ticker_filter]
    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    for ticker in target_tickers:
        for seed in TARGETED_OFFICIAL_TECHNOLOGY_SEEDS[ticker]:
            result = _process_seed(ticker=ticker, seed=seed, generated_at=generated_at, raw_dir=raw_dir, timeout_s=timeout_s)
            rows.extend(result["rows"])
            attempts.extend(result["attempts"])
    return _dedupe_rows(rows), _dedupe_attempts(attempts)


def _process_seed(
    *,
    ticker: str,
    seed: Mapping[str, Any],
    generated_at: str,
    raw_dir: Path,
    timeout_s: float,
) -> dict[str, list[dict[str, Any]]]:
    url = str(seed.get("url") or "").strip()
    transport = str(seed.get("fetch_transport") or "direct")
    raw_path = raw_dir / _slug(ticker) / f"{_stable_digest(url)}.html"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    if transport == "browser_rendered":
        status, body, reason = _fetch_text_with_browser(url, timeout_s=timeout_s)
    else:
        status, body, reason = _fetch_text(url, timeout_s=timeout_s)
        if status == "ok" and (_looks_blocked(body) or not _matched_terms(_clean_html(body), seed.get("topic_terms") or [])):
            browser_status, browser_body, browser_reason = _fetch_text_with_browser(url, timeout_s=timeout_s)
            if browser_status == "ok" and browser_body and not _looks_blocked(browser_body):
                status, body, reason = browser_status, browser_body, browser_reason
                transport = "browser_rendered"
    raw_path.write_text(body or "", encoding="utf-8")
    if status != "ok" or not body or _looks_blocked(body):
        return {
            "rows": [],
            "attempts": [
                _attempt(
                    ticker,
                    url,
                    "unusable_response" if status == "ok" else status,
                    reason or "empty_or_blocked_body",
                    generated_at=generated_at,
                    raw_path=str(raw_path),
                    fetch_transport=transport,
                )
            ],
        }
    clean_body = _clean_html(body)
    issuer_terms = _matched_terms(f"{url} {clean_body}", seed.get("issuer_aliases") or [])
    topic_terms = _matched_terms(clean_body, seed.get("topic_terms") or [])
    if not issuer_terms or not topic_terms:
        return {
            "rows": [],
            "attempts": [
                _attempt(
                    ticker,
                    url,
                    "issuer_or_topic_binding_gap",
                    f"issuer_terms={issuer_terms}; topic_terms={topic_terms}",
                    generated_at=generated_at,
                    raw_path=str(raw_path),
                    fetch_transport=transport,
                )
            ],
        }
    row = _technology_document_row(
        ticker=ticker,
        seed=seed,
        source_url=url,
        issuer_terms=issuer_terms,
        topic_terms=topic_terms,
        clean_body=clean_body,
        generated_at=generated_at,
        raw_path=raw_path,
        fetch_transport=transport,
    )
    return {
        "rows": [row],
        "attempts": [
            _attempt(
                ticker,
                url,
                "materialized",
                "",
                generated_at=generated_at,
                raw_path=str(raw_path),
                fetch_transport=transport,
                parsed_row_count=1,
            )
        ],
    }


def _technology_document_row(
    *,
    ticker: str,
    seed: Mapping[str, Any],
    source_url: str,
    issuer_terms: list[str],
    topic_terms: list[str],
    clean_body: str,
    generated_at: str,
    raw_path: Path,
    fetch_transport: str,
) -> dict[str, Any]:
    label = str(seed.get("doc_label") or _html_title(clean_body) or source_url).strip()
    technical_doc_id = _stable_ref("official_technology_document", [ticker, source_url])
    preview = _compact_text(clean_body, 900)
    text = (
        f"{ticker} official technology document proxy: {label}; "
        f"matched issuer={', '.join(issuer_terms[:4])}; matched topics={', '.join(topic_terms[:6])}. "
        "This supports product/technology signal context only, not product sales, revenue, share, ASP, orders, or durable moat proof."
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "evidence_ref": technical_doc_id,
        "evidence_id": technical_doc_id,
        "snapshot_id": technical_doc_id,
        "source_family": "public_source_context",
        "runtime_source_family": "public_source_context",
        "source_id": SOURCE_ID,
        "underlying_source_id": SOURCE_ID,
        "source_class": SOURCE_ID,
        "source_layer_id": "L3",
        "source_layer": "L3",
        "layer_id": "L3",
        "source_specific_parser": "official_technology_document_issuer_topic_parser_v0_1",
        "source_specific_resolver": "official_domain_issuer_topic_resolver_v0_1",
        "parser_status": "source_specific_context_parser_pass",
        "structured_fact_status": "bounded_context_fact_materialized",
        "evidence_graph_status": "runtime_ready_context",
        "runtime_ready_context": True,
        "bounded_structured_context": True,
        "structured_context_type": "technology_research_proxy_context",
        "requirement_id": "technology_research_proxy",
        "ticker": ticker,
        "company_name": _company_name(ticker),
        "source_url": source_url,
        "raw_path": str(raw_path),
        "fetch_transport": fetch_transport,
        "citation": {"url": source_url, "source_url": source_url, "title": label},
        "fact_label": label,
        "technical_doc_id": technical_doc_id,
        "metric_name": "official_technology_document_issuer_topic_snapshot",
        "value": label,
        "unit": "document",
        "period": generated_at[:10],
        "date": generated_at[:10],
        "product_or_segment": topic_terms[0] if topic_terms else label,
        "product_family": topic_terms[0] if topic_terms else label,
        "matched_issuer_terms": issuer_terms,
        "matched_product_terms": topic_terms,
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "product_binding_status": "technology_topic_bound",
        "counterparty_binding_status": "not_bound",
        "entity_binding": {
            "issuer_ticker": ticker,
            "issuer_binding_status": "issuer_mentioned_in_snapshot",
            "product_binding_status": "technology_topic_bound",
            "counterparty_binding_status": "not_bound",
            "issuer_matched_terms": issuer_terms,
            "product_matched_terms": topic_terms,
            "resolver_status": "official_domain_issuer_topic_bound",
            "binding_claim_boundary": "Official technology document proxy only; no sales, revenue, share, ASP, order, or moat proof.",
        },
        "resolver_status": "official_domain_issuer_topic_bound",
        "context_only": True,
        "exact_value_authority": False,
        "can_support_company_exact_fact": False,
        "allowed_claims": ["technology_research_proxy", "product_technology_signal", "verification_lead"],
        "claim_types": ["technology_research_proxy", "product_technology_signal", "verification_lead"],
        "forbidden_claims": ["product_sales", "revenue", "market_share", "ASP", "order_volume", "durable_moat_proof"],
        "claim_boundary": "Official technology document supports bounded product/technology signal only; no economics or market-share promotion.",
        "text": text,
        "preview": preview,
    }


def build_summary(
    *,
    rows: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    generated_at: str,
    output_rows: Path,
    output_attempts: Path,
) -> dict[str, Any]:
    success = sorted({str(row.get("ticker") or "") for row in rows if row.get("ticker")})
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if success else "gap",
        "target_ticker_count": len(TARGETED_OFFICIAL_TECHNOLOGY_SEEDS),
        "success_ticker_count": len(success),
        "tickers": success,
        "row_count": len(rows),
        "attempt_count": len(attempts),
        "attempt_status_counts": dict(sorted(Counter(str(row.get("status") or "") for row in attempts).items())),
        "fetch_transport_counts": dict(sorted(Counter(str(row.get("fetch_transport") or "") for row in rows).items())),
        "outputs": {"rows": str(output_rows), "attempts": str(output_attempts)},
        "boundary": "Official technology documents are L3 bounded technology signals only; they cannot support product sales, revenue, ASP, share, order value, or durable moat claims.",
    }


def _fetch_text(url: str, *, timeout_s: float) -> tuple[str, str, str]:
    try:
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*"})
        with urlopen(request, timeout=timeout_s) as response:
            return "ok", response.read().decode("utf-8", errors="ignore"), ""
    except Exception as exc:  # noqa: BLE001
        code = getattr(exc, "code", None)
        return (f"http_{code}" if code else "fetch_failed"), "", str(exc)[:220]


def _fetch_text_with_browser(url: str, *, timeout_s: float) -> tuple[str, str, str]:
    try:
        from playwright.sync_api import sync_playwright

        executable_path = _browser_executable_path()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, executable_path=executable_path or None)
            try:
                page = browser.new_page(user_agent=USER_AGENT)
                page.goto(url, wait_until="domcontentloaded", timeout=max(10_000, int(timeout_s * 1000)))
                page.wait_for_timeout(4500)
                title = page.title()
                text = page.evaluate("document.body ? document.body.innerText : ''")
                html_body = f"<title>{html.escape(title or '')}</title><body>{html.escape(text or '')}</body>"
            finally:
                browser.close()
        return "ok", html_body, ""
    except Exception as exc:  # noqa: BLE001
        return "browser_fetch_failed", "", f"{type(exc).__name__}: {str(exc)[:220]}"


def _browser_executable_path() -> str:
    for candidate in (
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
        Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
    ):
        if candidate.exists():
            return str(candidate)
    return ""


def _looks_blocked(body: str) -> bool:
    lowered = str(body or "").lower()
    return any(token in lowered for token in ("client challenge", "javascript is disabled", "requiring captcha", "we're sorry"))


def _clean_html(body: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", str(body or ""), flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _html_title(body: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", str(body or ""), flags=re.I | re.S)
    return _clean_html(match.group(1)) if match else ""


def _matched_terms(text: str, terms: Iterable[Any]) -> list[str]:
    lowered = str(text or "").lower()
    out: list[str] = []
    for term in terms:
        value = str(term or "").strip()
        if value and value.lower() in lowered and value not in out:
            out.append(value)
    return out


def _company_name(ticker: str) -> str:
    return {
        "PLTR": "Palantir Technologies",
        "MPWR": "Monolithic Power Systems",
        "300750.SZ": "Contemporary Amperex Technology Co., Limited",
        "373220.KS": "LG Energy Solution, Ltd.",
    }.get(ticker, ticker)


def _compact_text(text: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    return value[: max(1, limit)].strip()


def _attempt(
    ticker: str,
    source_url: str,
    status: str,
    reason: str,
    *,
    generated_at: str,
    raw_path: str,
    fetch_transport: str,
    parsed_row_count: int = 0,
) -> dict[str, Any]:
    return {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "attempt_id": _stable_ref("targeted_official_technology_document_attempt", [ticker, source_url, status]),
        "ticker": ticker,
        "source_id": SOURCE_ID,
        "underlying_source_id": SOURCE_ID,
        "provider": SOURCE_ID,
        "source_url": source_url,
        "status": status,
        "reason": reason,
        "raw_path": raw_path,
        "fetch_transport": fetch_transport,
        "parsed_row_count": parsed_row_count,
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
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
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("evidence_ref") or "")
        if key:
            out[key] = dict(row)
    return list(out.values())


def _dedupe_attempts(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("attempt_id") or "")
        if key:
            out[key] = dict(row)
    return list(out.values())


def _stable_ref(prefix: str, parts: Iterable[Any]) -> str:
    return f"{prefix}:{_stable_digest('|'.join(str(part or '') for part in parts))}"


def _stable_digest(value: Any) -> str:
    return hashlib.sha1(str(value or "").encode("utf-8")).hexdigest()[:16]


def _slug(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "unknown"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
