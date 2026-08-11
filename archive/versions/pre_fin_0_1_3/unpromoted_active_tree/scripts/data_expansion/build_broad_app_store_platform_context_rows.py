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


SCHEMA_VERSION = "finsight_broad_app_store_platform_context_row_v0_1"
ATTEMPT_SCHEMA_VERSION = "finsight_broad_app_store_platform_attempt_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_broad_app_store_platform_context_summary_v0_1"

DEFAULT_COMPANY_SOURCE_MATRIX = REPO_ROOT / "data" / "manifests" / "company_public_source_coverage_matrix_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "broad_app_store_platform_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_ATTEMPTS = REPO_ROOT / "data" / "manifests" / "broad_app_store_platform_attempts_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "broad_app_store_platform_context_summary_v0_1.json"
DEFAULT_RAW_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/broad_app_store_platform")

USER_AGENT = "FIN-Insight-Agent public app marketplace audit"
APP_ALIAS_OVERRIDES = {
    "BKNG": ("Booking.com", "Booking.com B.V.", "KAYAK", "OpenTable"),
    "CASY": ("Casey's", "Caseys General Stores", "Caseys General Stores Inc"),
    "DG": ("Dollar General", "Dolgencorp", "Dolgencorp LLC"),
    "FIVN": ("Five9",),
    "GTLB": ("GitLab",),
    "HST": ("Host Hotels", "Host Hotels & Resorts", "Host Hotels & Resorts, Inc."),
    "LVS": ("Sands Resorts", "Venetian Las Vegas", "Venetian Macau Limited"),
    "LYV": ("Live Nation", "Ticketmaster"),
    "MELI": ("Mercado Libre", "MercadoLibre"),
    "MNST": ("Monster Energy", "Monster Energy Company"),
    "PSKY": ("Paramount+", "Paramount", "CBS Mobile"),
    "RCL": ("Royal Caribbean", "Celebrity Cruises"),
    "SATS": ("DISH Anywhere", "DISH Network", "DISH Network LLC"),
    "TKO": ("UFC", "WWE", "Zuffa", "Zuffa LLC", "World Wrestling Entertainment", "World Wrestling Entertainment LLC"),
    "TTD": ("The Trade Desk",),
    "TTWO": ("Rockstar Games", "2K"),
    "WBD": ("Max", "HBO Max", "Warner Bros.", "WarnerMedia"),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build broad App Store / platform review rows from iTunes Search API.")
    parser.add_argument("--company-source-matrix", type=Path, default=DEFAULT_COMPANY_SOURCE_MATRIX)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-attempts", type=Path, default=DEFAULT_OUTPUT_ATTEMPTS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--tickers", nargs="*", default=[])
    parser.add_argument("--timeout-s", type=float, default=12.0)
    parser.add_argument("--sleep-s", type=float, default=0.05)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--max-apps-per-company", type=int, default=2)
    parser.add_argument("--replace-output", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    matrix_rows = _load_jsonl(args.company_source_matrix)
    result = build_broad_app_store_platform_context_rows(
        matrix_rows=matrix_rows,
        generated_at=generated_at,
        tickers=args.tickers,
        raw_dir=args.raw_dir,
        timeout_s=args.timeout_s,
        sleep_s=args.sleep_s,
        limit=args.limit,
        max_apps_per_company=args.max_apps_per_company,
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


def build_broad_app_store_platform_context_rows(
    *,
    matrix_rows: Iterable[Mapping[str, Any]],
    generated_at: str,
    raw_dir: Path,
    tickers: Iterable[str] = (),
    timeout_s: float = 12.0,
    sleep_s: float = 0.05,
    limit: int = 5,
    max_apps_per_company: int = 2,
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
        route_requirements = requirements & {"app_rank_store_proxy", "platform_review_proxy"}
        if not route_requirements:
            continue
        aliases = _aliases(company.get("company_name") or ticker, ticker)
        materialized = 0
        for query in _query_aliases(company.get("company_name") or ticker, ticker):
            url = f"https://itunes.apple.com/search?term={quote(query)}&entity=software&country=us&limit={max(1, int(limit))}"
            status, body, reason = _fetch_text(url, timeout_s=timeout_s)
            raw_path = raw_dir / f"{_slug(ticker)}_{_stable_digest(url)}.json"
            raw_path.write_text(body or "", encoding="utf-8")
            if status != "ok":
                attempts.append(_attempt(ticker, url, status, raw_path=raw_path, reason=reason))
                continue
            payload = _parse_json(body)
            results = payload.get("results") if isinstance(payload, Mapping) else []
            for app in results if isinstance(results, list) else []:
                if not isinstance(app, Mapping):
                    continue
                seller = _first_text(app.get("sellerName"), app.get("artistName"))
                if not _alias_matches(seller, aliases):
                    continue
                track_id = str(app.get("trackId") or "")
                track_name = str(app.get("trackName") or "").strip()
                if not track_id or not track_name:
                    continue
                if "app_rank_store_proxy" in route_requirements:
                    rows.append(_app_row(company, app, source_id="app_store_rankings", requirement_id="app_rank_store_proxy", generated_at=generated_at))
                if "platform_review_proxy" in route_requirements:
                    rows.append(_app_row(company, app, source_id="platform_reviews_rankings_downloads", requirement_id="platform_review_proxy", generated_at=generated_at))
                materialized += 1
                if materialized >= max_apps_per_company:
                    break
            attempts.append(_attempt(ticker, url, "materialized" if materialized else "no_bound_records", raw_path=raw_path, reason="" if materialized else "iTunes search returned no seller-bound app rows"))
            if materialized >= max_apps_per_company:
                break
            if sleep_s:
                time.sleep(sleep_s)
    return {"rows": _dedupe_rows(rows), "attempts": attempts}


def _app_row(
    company: Mapping[str, Any],
    app: Mapping[str, Any],
    *,
    source_id: str,
    requirement_id: str,
    generated_at: str,
) -> dict[str, Any]:
    ticker = str(company.get("ticker") or "").strip().upper()
    track_id = str(app.get("trackId") or "")
    track_name = str(app.get("trackName") or "").strip()
    source_url = str(app.get("trackViewUrl") or f"https://itunes.apple.com/lookup?id={track_id}")
    lookup_url = f"https://itunes.apple.com/lookup?id={track_id}"
    rating = app.get("averageUserRating")
    rating_count = app.get("userRatingCount")
    version = str(app.get("version") or "")
    release_date = str(app.get("currentVersionReleaseDate") or app.get("releaseDate") or "")
    evidence_ref = _stable_ref("broad_app_store_platform", [ticker, source_id, track_id, track_name])
    text = (
        f"{ticker} public app marketplace snapshot: {track_name}; seller={_first_text(app.get('sellerName'), app.get('artistName'))}; "
        f"rating={rating}; rating_count={rating_count}; version={version}; release_date={release_date}."
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "source_id": source_id,
        "underlying_source_id": source_id,
        "source_class": source_id,
        "source_family": "public_source_context",
        "runtime_source_family": "public_source_context",
        "source_layer_id": "L3",
        "source_layer": "L3",
        "layer_id": "L3",
        "source_specific_parser": "broad_itunes_search_lookup_parser_v0_1",
        "source_specific_resolver": "itunes_seller_to_issuer_resolver_v0_1",
        "parser_status": "source_specific_context_parser_pass",
        "structured_fact_status": "bounded_context_fact_materialized",
        "runtime_ready_context": True,
        "bounded_structured_context": True,
        "structured_context_type": "app_marketplace_context" if source_id == "app_store_rankings" else "platform_review_context",
        "requirement_id": requirement_id,
        "ticker": ticker,
        "company": company.get("company_name") or "",
        "company_name": company.get("company_name") or "",
        "source_url": source_url,
        "api_url": lookup_url,
        "citation": {"url": lookup_url, "source_url": source_url, "title": track_name},
        "fact_label": track_name,
        "product_or_segment": track_name,
        "product_family": track_name,
        "rating": rating,
        "rating_count": rating_count,
        "review_count": rating_count,
        "version": version,
        "release_date": release_date,
        "period": release_date,
        "as_of_datetime": generated_at,
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "product_binding_status": "product_mentioned_in_snapshot",
        "counterparty_binding_status": "not_bound",
        "entity_binding": {
            "issuer_ticker": ticker,
            "issuer_binding_status": "issuer_mentioned_in_snapshot",
            "product_binding_status": "product_mentioned_in_snapshot",
            "counterparty_binding_status": "not_bound",
            "resolver_status": "itunes_seller_bound_to_issuer",
            "binding_claim_boundary": "App listing/rating snapshot only; no revenue, downloads, market share, or durable adoption proof.",
        },
        "resolver_status": "itunes_seller_bound_to_issuer",
        "context_only": True,
        "exact_value_authority": False,
        "can_support_company_exact_fact": False,
        "allowed_claims": ["app_store_marketplace_context", "platform_review_context", "market_proxy_context", "verification_lead"],
        "forbidden_claims": ["app_revenue", "download_count", "market_share", "sales_volume", "durable_moat_proof"],
        "claim_boundary": "Public app marketplace listing/rating/version snapshot only; no revenue/download/share promotion.",
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
        if isinstance(req, Mapping) and str(req.get("requirement_id") or "") in {"app_rank_store_proxy", "platform_review_proxy"}
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
        "row_source_counts": dict(sorted(Counter(str(row.get("source_id") or "") for row in rows).items())),
        "attempt_status_counts": dict(sorted(Counter(str(row.get("status") or "") for row in attempts).items())),
        "unmaterialized_tickers": sorted(required - success),
        "outputs": {"rows": str(output_rows), "attempts": str(output_attempts)},
        "boundary": "Only seller-bound iTunes app rows are promoted; app marketplace rows cannot prove revenue, downloads, share, sales, or moat.",
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
        return "fetch_failed", "", f"{type(exc).__name__}:{str(exc)[:200]}"
    except Exception as exc:  # noqa: BLE001
        return "fetch_failed", "", f"{type(exc).__name__}:{str(exc)[:200]}"


def _parse_json(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _attempt(ticker: str, url: str, status: str, *, raw_path: Path, reason: str) -> dict[str, Any]:
    return {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "attempt_id": _stable_ref("broad_app_store_platform_attempt", [ticker, url, status, reason]),
        "ticker": ticker,
        "source_id": "itunes_search_api",
        "source_url": url,
        "status": status,
        "raw_path": str(raw_path),
        "reason": reason,
    }


def _aliases(company_name: str, ticker: str) -> tuple[str, ...]:
    values = [*APP_ALIAS_OVERRIDES.get(str(ticker or "").upper(), ()), company_name, _simplify_company_name(company_name), ticker]
    return tuple(_unique(value for value in values if value))


def _query_aliases(company_name: str, ticker: str) -> tuple[str, ...]:
    values = [*APP_ALIAS_OVERRIDES.get(str(ticker or "").upper(), ()), company_name, _simplify_company_name(company_name)]
    return tuple(_unique(value for value in values if value))


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
    return re.sub(
        r"\b(inc|incorporated|corp|corporation|co|company|ltd|limited|plc|se|sa|nv|ag|llc|the|class a|class b)\b\.?",
        "",
        re.split(r"[,(/-]", str(value or ""), maxsplit=1)[0],
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


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
