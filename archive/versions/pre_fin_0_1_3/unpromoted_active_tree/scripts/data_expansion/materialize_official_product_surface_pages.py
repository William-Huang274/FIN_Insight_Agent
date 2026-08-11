from __future__ import annotations

import argparse
import html
import json
import os
import re
import ssl
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.official_issuer_repair import known_official_issuer_profiles  # noqa: E402


SUMMARY_SCHEMA_VERSION = "fin_agent_official_product_surface_materialization_summary_v0_1"
DEFAULT_OUTPUT = Path(
    "Z:/FIN_Insight_Agent_data/processed_private/public_source_extended_materialization/company_product_pages/company_product_pages.materialized.jsonl"
)
DEFAULT_RAW_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/company_product_pages")
DEFAULT_CLEAN_DIR = Path("Z:/FIN_Insight_Agent_data/processed_private/public_source_extended_materialization/company_product_pages")
DEFAULT_SUMMARY = REPO_ROOT / "data" / "manifests" / "official_product_surface_materialization_summary_v0_1.json"

FetchFunc = Callable[[str, float], tuple[int, str, str]]


SYSTEM_BROWSER_EXECUTABLE_CANDIDATES = (
    Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
    Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
    Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
    Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize official company product pages from curated issuer profiles.")
    parser.add_argument("--tickers", nargs="*", default=[], help="Optional ticker allowlist. Defaults to all known profiles.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--clean-dir", type=Path, default=DEFAULT_CLEAN_DIR)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--max-urls-per-issuer", type=int, default=2)
    parser.add_argument("--timeout-s", type=float, default=10.0)
    parser.add_argument("--min-clean-text-chars", type=int, default=300)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--prune-unusable-existing", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if no new page is materialized.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    existing_rows = _load_jsonl(args.output)
    result = materialize_official_product_surface_pages(
        profiles=known_official_issuer_profiles(),
        existing_rows=existing_rows,
        tickers=args.tickers,
        raw_dir=args.raw_dir,
        clean_dir=args.clean_dir,
        generated_at=generated_at,
        max_urls_per_issuer=args.max_urls_per_issuer,
        timeout_s=args.timeout_s,
        min_clean_text_chars=args.min_clean_text_chars,
        skip_existing=bool(args.skip_existing),
        prune_unusable_existing=bool(args.prune_unusable_existing),
    )
    _write_jsonl(args.output, result["rows"])
    _write_json(args.summary, result["summary"])
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and (result["summary"]["new_materialized_count"] + result["summary"]["updated_materialized_count"]) <= 0:
        return 1
    return 0


def materialize_official_product_surface_pages(
    *,
    profiles: Mapping[str, Mapping[str, Any]],
    existing_rows: Iterable[Mapping[str, Any]],
    raw_dir: Path,
    clean_dir: Path,
    generated_at: str,
    tickers: Iterable[str] = (),
    max_urls_per_issuer: int = 2,
    timeout_s: float = 10.0,
    min_clean_text_chars: int = 300,
    skip_existing: bool = False,
    prune_unusable_existing: bool = False,
    fetch: FetchFunc | None = None,
) -> dict[str, Any]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    clean_dir.mkdir(parents=True, exist_ok=True)
    existing_list = [dict(row) for row in existing_rows if isinstance(row, Mapping)]
    ticker_filter = {str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()}
    fetcher = fetch or _fetch_url
    rows_by_key: dict[str, dict[str, Any]] = {}
    pruned_unusable_existing = 0
    for row in existing_list:
        key = _row_key(row)
        if not key:
            continue
        if prune_unusable_existing and not row_usable(row, min_clean_text_chars=min_clean_text_chars):
            pruned_unusable_existing += 1
            continue
        rows_by_key[key] = dict(row)

    attempts: list[dict[str, Any]] = []
    new_materialized = 0
    updated_materialized = 0
    skipped_existing = 0
    blocked = 0
    failed = 0

    for ticker, profile_value in sorted(profiles.items()):
        profile = dict(profile_value)
        ticker = str(profile.get("ticker") or ticker).strip().upper()
        if ticker_filter and ticker not in ticker_filter:
            continue
        company = str(profile.get("company_name") or profile.get("issuer_name") or "").strip()
        domains = {str(item).lower().strip() for item in profile.get("company_domains") or [] if str(item).strip()}
        urls = _unique_strings(profile.get("official_product_urls") or [])[: max(1, int(max_urls_per_issuer or 1))]
        surfaces = [str(item).strip() for item in profile.get("official_product_surfaces") or [] if str(item).strip()]
        for index, url in enumerate(urls, start=1):
            key = _key(ticker, url)
            if skip_existing and key in rows_by_key:
                skipped_existing += 1
                attempts.append(_attempt(ticker, url, "skipped_existing"))
                continue
            if not _url_allowed(url, domains):
                blocked += 1
                attempts.append(_attempt(ticker, url, "blocked_domain", reason="url_not_in_company_domain_allowlist"))
                continue
            try:
                status_code, content_type, body = fetcher(url, timeout_s)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                attempts.append(_attempt(ticker, url, "fetch_failed", reason=f"{type(exc).__name__}: {str(exc)[:200]}"))
                continue
            if status_code >= 400 or not body.strip():
                failed += 1
                attempts.append(_attempt(ticker, url, "unusable_response", reason=f"http_{status_code}" if status_code else "empty_body"))
                continue

            title = extract_title(body) or f"{ticker} official product surface"
            clean_text = html_to_text(body)
            usability_error = response_usability_error(title=title, clean_text=clean_text, min_clean_text_chars=min_clean_text_chars)
            if usability_error:
                failed += 1
                rows_by_key.pop(key, None)
                attempts.append(_attempt(ticker, url, "unusable_response", reason=usability_error, title=title, clean_text_char_count=len(clean_text)))
                continue
            product = infer_product_surface(profile=profile, url=url, title=title, surfaces=surfaces, index=index)
            stem = f"{ticker.lower()}_{_slug(product or _domain(url) or 'product')}"
            raw_path = raw_dir / f"{stem}.html"
            clean_path = clean_dir / f"{stem}.txt"
            raw_path.write_text(body, encoding="utf-8", errors="replace")
            clean_path.write_text(clean_text, encoding="utf-8", errors="replace")

            row = {
                "ticker": ticker,
                "company": company,
                "product": product,
                "source_url": url,
                "title": title,
                "status_code": status_code,
                "content_type": content_type,
                "raw_path": str(raw_path),
                "clean_text_path": str(clean_path),
                "clean_text_char_count": len(clean_text),
                "fetched_at": generated_at,
                "materialization_status": "live_fetch_materialized",
                "source_policy": "official_company_product_surface_context_only",
            }
            if key in rows_by_key:
                updated_materialized += 1
            else:
                new_materialized += 1
            rows_by_key[key] = row
            attempts.append(_attempt(ticker, url, "materialized", clean_text_char_count=len(clean_text), title=title))

    rows = sorted(rows_by_key.values(), key=lambda item: (str(item.get("ticker") or ""), str(item.get("source_url") or item.get("url") or "")))
    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if new_materialized or updated_materialized or rows else "gap",
        "existing_input_count": len(existing_list),
        "output_row_count": len(rows),
        "ticker_count": len({str(row.get("ticker") or "") for row in rows if str(row.get("ticker") or "")}),
        "tickers": sorted({str(row.get("ticker") or "") for row in rows if str(row.get("ticker") or "")}),
        "attempted_count": len(attempts),
        "new_materialized_count": new_materialized,
        "updated_materialized_count": updated_materialized,
        "skipped_existing_count": skipped_existing,
        "pruned_unusable_existing_count": pruned_unusable_existing,
        "blocked_count": blocked,
        "failed_count": failed,
        "attempts": attempts,
        "boundary": "Materialized official product pages are bounded product taxonomy/spec context only; no sales/share/ASP/inventory/sell-through authority.",
    }
    return {"rows": rows, "summary": summary}


def infer_product_surface(*, profile: Mapping[str, Any], url: str, title: str, surfaces: list[str], index: int) -> str:
    haystack = f"{url} {title}".lower()
    for surface in surfaces:
        tokens = [token for token in re.split(r"[^a-z0-9]+", surface.lower()) if len(token) >= 3]
        if tokens and any(token in haystack for token in tokens):
            return surface
    if surfaces:
        return surfaces[min(index - 1, len(surfaces) - 1)]
    return str(profile.get("company_name") or profile.get("ticker") or "official product surface")


def html_to_text(body: str) -> str:
    parser = _TextExtractor()
    parser.feed(body)
    parser.close()
    text = " ".join(parser.parts)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def extract_title(body: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
    if not match:
        return ""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", match.group(1)))).strip()


def response_usability_error(*, title: str, clean_text: str, min_clean_text_chars: int) -> str:
    title_l = title.lower()
    text_l = clean_text[:2000].lower()
    blocked_markers = (
        "request has been blocked",
        "access denied",
        "temporarily unavailable",
        "enable javascript",
        "bot detection",
        "bot manager",
        "captcha",
        "client challenge",
        "just a moment",
        "radware",
        "404 error",
        "404 |",
        "page not found",
        "not found |",
        "system down",
        "custom error",
        "error-pagenotfound",
        "認証中",
    )
    non_content_markers = (
        "domain for sale",
        "premium domain for sale",
        "this domain is for sale",
        "buy this domain",
        "aftermarket.com",
        "parked domain",
    )
    non_content_title_markers = (
        "linkedin",
        "bloomberg | linkedin",
    )
    if any(marker in title_l or marker in text_l for marker in blocked_markers):
        return "blocked_or_non_content_page"
    if any(marker in title_l or marker in text_l for marker in non_content_markers):
        return "non_official_or_parked_domain_page"
    if any(marker in title_l for marker in non_content_title_markers):
        return "non_official_or_parked_domain_page"
    if len(clean_text.strip()) < int(min_clean_text_chars or 0):
        return f"clean_text_too_short:{len(clean_text.strip())}"
    return ""


def row_usable(row: Mapping[str, Any], *, min_clean_text_chars: int) -> bool:
    title = str(row.get("title") or "")
    count = int(row.get("clean_text_char_count") or 0)
    clean_text = ""
    path_text = str(row.get("clean_text_path") or "").strip()
    path = Path(path_text) if path_text else None
    if path is not None and path.exists() and path.is_file():
        clean_text = path.read_text(encoding="utf-8", errors="replace")
    elif count:
        clean_text = "x" * count
    return not response_usability_error(title=title, clean_text=clean_text, min_clean_text_chars=min_clean_text_chars)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data.strip():
            self.parts.append(data.strip())


def _fetch_url(url: str, timeout_s: float) -> tuple[int, str, str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 FIN-Insight-Agent/0.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }
    request = Request(
        url,
        headers=headers,
    )
    timeout = float(timeout_s or 10.0)
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            body = response.read().decode("utf-8", errors="replace")
            return int(getattr(response, "status", 200) or 200), str(response.headers.get("Content-Type") or ""), body
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return int(exc.code or 0), str(exc.headers.get("Content-Type") if exc.headers else ""), body
    except URLError as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            raise
        ssl_context = ssl._create_unverified_context()  # noqa: SLF001
        with urlopen(request, timeout=timeout, context=ssl_context) as response:  # noqa: S310
            body = response.read().decode("utf-8", errors="replace")
            return int(getattr(response, "status", 200) or 200), str(response.headers.get("Content-Type") or ""), body


class PlaywrightBrowserFetcher:
    """Browser-backed fetcher for public official pages that require JS rendering."""

    def __init__(
        self,
        *,
        executable_path: str | Path | None = None,
        headless: bool = True,
        wait_until: str = "domcontentloaded",
        settle_ms: int = 700,
    ) -> None:
        self.executable_path = str(executable_path or detect_browser_executable_path() or "")
        self.headless = bool(headless)
        self.wait_until = wait_until
        self.settle_ms = max(0, int(settle_ms or 0))
        self._playwright = None
        self._browser = None
        self._context = None

    def __enter__(self) -> "PlaywrightBrowserFetcher":
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("playwright package is required for browser-backed public fetch") from exc
        self._playwright = sync_playwright().start()
        launch_kwargs: dict[str, Any] = {
            "headless": self.headless,
            "args": [
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
            ],
        }
        if self.executable_path:
            launch_kwargs["executable_path"] = self.executable_path
        self._browser = self._playwright.chromium.launch(**launch_kwargs)
        self._context = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            locale="en-US",
            viewport={"width": 1440, "height": 1200},
        )
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._context is not None:
            self._context.close()
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()

    def __call__(self, url: str, timeout_s: float) -> tuple[int, str, str]:
        if self._context is None:
            raise RuntimeError("PlaywrightBrowserFetcher must be used as a context manager")
        timeout_ms = max(1000, int(float(timeout_s or 10.0) * 1000))
        page = self._context.new_page()
        try:
            response = page.goto(url, wait_until=self.wait_until, timeout=timeout_ms)
            if self.settle_ms:
                page.wait_for_timeout(self.settle_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 2500))
            except Exception:
                pass
            body = page.content()
            status = int(response.status) if response is not None else 0
            content_type = ""
            if response is not None:
                content_type = str(response.headers.get("content-type") or "")
            return status, content_type or "text/html; fetch_mode=browser", body
        finally:
            page.close()


class HttpThenBrowserFetcher:
    """Try normal public HTTP first, then use browser rendering for blocked/non-content pages."""

    def __init__(self, browser_fetcher: PlaywrightBrowserFetcher, *, min_clean_text_chars: int = 300) -> None:
        self.browser_fetcher = browser_fetcher
        self.min_clean_text_chars = int(min_clean_text_chars or 0)

    def __enter__(self) -> "HttpThenBrowserFetcher":
        self.browser_fetcher.__enter__()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.browser_fetcher.__exit__(exc_type, exc, tb)

    def __call__(self, url: str, timeout_s: float) -> tuple[int, str, str]:
        try:
            status_code, content_type, body = _fetch_url(url, timeout_s)
        except Exception:
            return self.browser_fetcher(url, timeout_s)
        if status_code >= 400 or not body.strip():
            return self.browser_fetcher(url, timeout_s)
        title = extract_title(body)
        clean_text = html_to_text(body)
        usability_error = response_usability_error(
            title=title,
            clean_text=clean_text,
            min_clean_text_chars=self.min_clean_text_chars,
        )
        if usability_error == "blocked_or_non_content_page":
            return self.browser_fetcher(url, timeout_s)
        return status_code, content_type, body


def detect_browser_executable_path() -> str:
    env_path = os.environ.get("FINSIGHT_BROWSER_EXECUTABLE_PATH", "").strip()
    if env_path and Path(env_path).exists():
        return env_path
    for path in SYSTEM_BROWSER_EXECUTABLE_CANDIDATES:
        if path.exists():
            return str(path)
    return ""


def _url_allowed(url: str, domains: set[str]) -> bool:
    domain = _domain(url)
    if not domain:
        return False
    if not domains:
        return True
    return any(domain == item or domain.endswith("." + item) for item in domains)


def _row_key(row: Mapping[str, Any]) -> str:
    return _key(str(row.get("ticker") or ""), str(row.get("source_url") or row.get("url") or ""))


def _key(ticker: str, url: str) -> str:
    ticker = str(ticker or "").strip().upper()
    url = str(url or "").strip()
    return f"{ticker}|{url}" if ticker and url else ""


def _attempt(ticker: str, url: str, status: str, **extra: Any) -> dict[str, Any]:
    return {"ticker": ticker, "url": url, "status": status, **extra}


def _domain(url: str) -> str:
    return urlparse(str(url or "")).netloc.lower().removeprefix("www.")


def _slug(value: str) -> str:
    text = "".join(ch.lower() if ch.isalnum() else "_" for ch in value or "")
    return "_".join(part for part in text.split("_") if part)[:72] or "product"


def _unique_strings(values: Iterable[Any]) -> list[str]:
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
            if isinstance(value, dict):
                rows.append(value)
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
