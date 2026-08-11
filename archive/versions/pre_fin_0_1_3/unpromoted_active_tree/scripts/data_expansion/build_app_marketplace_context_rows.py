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


SCHEMA_VERSION = "fin_agent_app_marketplace_context_row_v0_1"
SUMMARY_SCHEMA_VERSION = "fin_agent_app_marketplace_context_summary_v0_1"

SOURCE_ID = "app_store_rankings"
DEFAULT_SOURCE_LAYER_ROWS = REPO_ROOT / "data" / "manifests" / "source_layer_capability_audit_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "app_marketplace_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "app_marketplace_context_summary_v0_1.json"
DEFAULT_OUTPUT_COVERAGE = REPO_ROOT / "data" / "manifests" / "app_marketplace_runtime_coverage_gate_v0_1.json"
DEFAULT_RAW_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/app_marketplace")

FetchFunc = Callable[[str, float], tuple[int, str, str]]


DEFAULT_APP_MARKETPLACE_PROBES: tuple[dict[str, Any], ...] = (
    {
        "ticker": "AAPL",
        "company_name": "Apple",
        "company_names": ["Apple"],
        "product_terms": ["Apple Store", "Apple Music"],
        "urls": ["https://apps.apple.com/us/app/apple-store/id375380948", "https://apps.apple.com/us/app/apple-music/id1108187390"],
    },
    {
        "ticker": "GOOGL",
        "company_name": "Google",
        "company_names": ["Google", "Alphabet"],
        "product_terms": ["Google", "YouTube", "Google Maps"],
        "urls": ["https://apps.apple.com/us/app/google/id284815942", "https://apps.apple.com/us/app/youtube/id544007664", "https://apps.apple.com/us/app/google-maps/id585027354"],
    },
    {
        "ticker": "META",
        "company_name": "Meta Platforms",
        "company_names": ["Meta", "Facebook", "Instagram", "WhatsApp"],
        "product_terms": ["Facebook", "Instagram", "WhatsApp"],
        "urls": ["https://apps.apple.com/us/app/facebook/id284882215", "https://apps.apple.com/us/app/instagram/id389801252", "https://apps.apple.com/us/app/whatsapp-messenger/id310633997"],
    },
    {
        "ticker": "MSFT",
        "company_name": "Microsoft",
        "company_names": ["Microsoft"],
        "product_terms": ["Microsoft Outlook", "Microsoft Teams"],
        "urls": ["https://apps.apple.com/us/app/microsoft-outlook/id951937596", "https://apps.apple.com/us/app/microsoft-teams/id1113153706"],
    },
    {
        "ticker": "NFLX",
        "company_name": "Netflix",
        "company_names": ["Netflix"],
        "product_terms": ["Netflix"],
        "urls": ["https://apps.apple.com/us/app/netflix/id363590051"],
    },
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build bounded L3 app marketplace context rows from public lookup APIs.")
    parser.add_argument("--tickers", nargs="*", default=[], help="Optional ticker allowlist.")
    parser.add_argument("--source-layer-rows", type=Path, default=DEFAULT_SOURCE_LAYER_ROWS)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-coverage-gate", type=Path, default=DEFAULT_OUTPUT_COVERAGE)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--timeout-s", type=float, default=10.0)
    parser.add_argument("--fetch-retries", type=int, default=2)
    parser.add_argument("--max-rows-per-probe", type=int, default=1)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if no parser-backed rows are produced.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    result = build_app_marketplace_context_rows(
        probes=DEFAULT_APP_MARKETPLACE_PROBES,
        generated_at=generated_at,
        tickers=args.tickers,
        raw_dir=args.raw_dir,
        timeout_s=args.timeout_s,
        fetch_retries=args.fetch_retries,
        max_rows_per_probe=args.max_rows_per_probe,
    )
    source_layer_rows = _load_jsonl(args.source_layer_rows)
    coverage_gate = build_app_marketplace_coverage_gate(
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


def build_app_marketplace_context_rows(
    *,
    probes: Iterable[Mapping[str, Any]],
    generated_at: str,
    raw_dir: Path,
    tickers: Iterable[str] = (),
    timeout_s: float = 10.0,
    fetch_retries: int = 2,
    max_rows_per_probe: int = 1,
    fetch: FetchFunc | None = None,
) -> dict[str, Any]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    ticker_filter = {str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()}
    fetcher = fetch or _fetch_url
    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    for probe in probes:
        ticker = str(probe.get("ticker") or "").strip().upper()
        if ticker_filter and ticker not in ticker_filter:
            continue
        company_name = str(probe.get("company_name") or ticker).strip()
        company_names = _unique_strings([company_name, *(probe.get("company_names") or [])])
        product_terms = _unique_strings(probe.get("product_terms") or [])
        for source_url in _unique_strings(probe.get("urls") or []):
            api_url, provider = app_marketplace_api_url(source_url)
            if not api_url:
                attempts.append(_attempt(ticker, source_url, "", "unsupported_url", reason="app_marketplace_url_not_supported"))
                continue
            try:
                status_code, content_type, body = _fetch_with_retries(fetcher, api_url, timeout_s, fetch_retries)
            except Exception as exc:  # noqa: BLE001
                attempts.append(_attempt(ticker, source_url, api_url, "fetch_failed", reason=f"{type(exc).__name__}: {str(exc)[:220]}"))
                continue
            if status_code >= 400 or not body.strip():
                attempts.append(_attempt(ticker, source_url, api_url, "unusable_response", reason=f"http_{status_code}" if status_code else "empty_body"))
                continue
            payload = _parse_json_object(body)
            if not payload:
                attempts.append(_attempt(ticker, source_url, api_url, "unusable_response", reason="non_json_or_empty_payload"))
                continue
            title = app_marketplace_title(payload=payload, fallback=source_url)
            raw_path = raw_dir / f"{ticker.lower()}_{_slug(provider)}_{_slug(title)}.json"
            raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            repair = {
                "repair_id": f"app_marketplace_backfill:{ticker.lower()}:{_slug(title)}",
                "repair_type": "market_proxy",
                "ticker": ticker,
                "company_name": company_name,
                "company_names": company_names,
                "product_terms": _unique_strings([*product_terms, *_product_terms_from_payload(payload)]),
                "product_names": _unique_strings([*product_terms, *_product_terms_from_payload(payload)]),
                "metric_leads": ["rating", "rating count", "version", "release date", "app marketplace proxy"],
            }
            parent_ref = _stable_ref("app_marketplace", [ticker, provider, api_url])
            parsed_rows = parse_public_web_context_rows(
                ticker=ticker,
                parent_evidence_ref=parent_ref,
                url=api_url,
                source_class="official_app_store_or_marketplace",
                repair_type="market_proxy",
                analysis_dimension="product_and_production",
                title=f"{company_name} app marketplace: {title}",
                body=json.dumps(payload, ensure_ascii=False),
                content_type="application/json",
                as_of_datetime=generated_at,
                citation={"url": api_url, "source_url": source_url, "title": title},
                source_layer_meta={
                    "source_id": SOURCE_ID,
                    "underlying_source_id": SOURCE_ID,
                    "source_layer_id": "L3",
                    "source_layer": "L3",
                    "layer_id": "L3",
                    "parser_status": "app_store_lookup_parser_pass",
                    "structured_fact_status": "bounded_context_fact_materialized",
                    "evidence_graph_status": "runtime_ready_context",
                    "runtime_ready_context": True,
                    "can_support_company_exact_fact": False,
                },
                claim_boundary=(
                    "Public app marketplace lookup context only; supports app listing, rating/review-count, "
                    "version, and recency proxy, not app revenue, company market share, downloads, sales, or customer adoption proof."
                ),
                authority_boundary="L3 app marketplace proxy; never exact company metric authority.",
                repair=repair,
                max_rows=max_rows_per_probe,
            )
            for row in parsed_rows:
                row["schema_version"] = SCHEMA_VERSION
                row["runtime_source_family"] = "public_source_context"
                row["source_family"] = "live_public_web_context"
                row["source_id"] = SOURCE_ID
                row["underlying_source_id"] = SOURCE_ID
                row["provider"] = provider
                row["source_url"] = source_url
                row["api_url"] = api_url
                row["raw_path"] = str(raw_path)
                row["context_only"] = True
                row["exact_value_authority"] = False
                row["can_support_company_exact_fact"] = False
                row["allowed_claims"] = ["app_store_marketplace_context", "market_proxy_context", "verification_lead"]
                row["forbidden_claims"] = ["app_revenue", "market_share", "download_count", "sales_volume", "customer_adoption_proof"]
                rows.append(row)
            attempts.append(
                _attempt(
                    ticker,
                    source_url,
                    api_url,
                    "materialized" if parsed_rows else "parser_no_rows",
                    provider=provider,
                    parsed_row_count=len(parsed_rows),
                    raw_path=str(raw_path),
                    title=title,
                )
            )
    return {"rows": _dedupe_rows(rows), "attempts": attempts}


def build_app_marketplace_coverage_gate(
    *,
    context_rows: list[dict[str, Any]],
    source_layer_rows: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    visible = {
        "product_technology_analyst": context_rows,
        "market_valuation_analyst": context_rows,
    }
    return build_source_coverage_gate(
        industry_schema="software_saas",
        phase="runtime_case",
        case_id="app_marketplace_context_backfill_smoke",
        source_layer_capability={"rows": source_layer_rows},
        observed_rows=context_rows,
        specialist_visible_rows=visible,
        required_dimensions=["app_rank_store_proxy"],
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
        "app_rank_store_proxy_requirement": _requirement_summary(coverage_gate, "app_rank_store_proxy"),
        "outputs": {"rows": str(output_rows), "coverage_gate": str(output_coverage)},
        "boundary": "L3 app marketplace rows are directional listing/rating/version proxy only and cannot prove downloads, revenue, sales, share, customer adoption, or moat.",
        "google_play_gap": "Google Play has no first-party public lookup API wired in this tranche; keep it as an app marketplace coverage gap instead of pretending App Store coverage is full marketplace coverage.",
        "attempts": attempts,
    }


def app_marketplace_api_url(url: str) -> tuple[str, str]:
    text = str(url or "").strip()
    if not text:
        return "", ""
    lower = text.lower()
    match = re.search(r"/id(\d+)(?:[/?#]|$)", lower)
    if match and ("apps.apple.com" in lower or "itunes.apple.com" in lower):
        return f"https://itunes.apple.com/lookup?id={match.group(1)}", "apple_app_store"
    if lower.startswith("https://itunes.apple.com/lookup?id="):
        return text, "apple_app_store"
    return "", ""


def app_marketplace_title(*, payload: Mapping[str, Any], fallback: str) -> str:
    results = payload.get("results") if isinstance(payload.get("results"), list) else []
    for item in results:
        if isinstance(item, Mapping):
            title = str(item.get("trackName") or item.get("trackCensoredName") or "").strip()
            if title:
                return title
    return fallback.rstrip("/").rsplit("/", 1)[-1] or "app_marketplace"


def _product_terms_from_payload(payload: Mapping[str, Any]) -> list[str]:
    terms: list[str] = []
    results = payload.get("results") if isinstance(payload.get("results"), list) else []
    for item in results[:3]:
        if not isinstance(item, Mapping):
            continue
        terms.extend([item.get("trackName"), item.get("trackCensoredName"), item.get("sellerName")])
    return _unique_strings(terms)


def _fetch_url(url: str, timeout_s: float) -> tuple[int, str, str]:
    request = Request(
        url,
        headers={
            "User-Agent": "FIN-Insight-Agent/0.1 app-marketplace-source-backfill",
            "Accept": "application/json,text/plain;q=0.8,*/*;q=0.5",
        },
    )
    try:
        with urlopen(request, timeout=float(timeout_s or 10.0)) as response:  # noqa: S310
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


def _parse_json_object(body: str) -> dict[str, Any]:
    try:
        value = json.loads(body)
    except json.JSONDecodeError:
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


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
        text = str(value or "").strip()
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


def _attempt(ticker: str, source_url: str, api_url: str, status: str, **extra: Any) -> dict[str, Any]:
    row = {"ticker": ticker, "source_url": source_url, "api_url": api_url, "status": status}
    row.update(extra)
    return row


if __name__ == "__main__":
    raise SystemExit(main())
