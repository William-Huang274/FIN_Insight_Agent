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
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.public_web_context_parser import parse_public_web_context_rows  # noqa: E402
from sec_agent.source_coverage_gate import build_source_coverage_gate  # noqa: E402


SCHEMA_VERSION = "fin_agent_developer_ecosystem_context_row_v0_1"
SUMMARY_SCHEMA_VERSION = "fin_agent_developer_ecosystem_context_summary_v0_1"

SOURCE_ID = "developer_ecosystem_github_npm_pypi_huggingface"
DEFAULT_SOURCE_LAYER_ROWS = REPO_ROOT / "data" / "manifests" / "source_layer_capability_audit_v0_1.jsonl"
DEFAULT_SEED_PATH = REPO_ROOT / "data" / "manifests" / "developer_ecosystem_official_seed_registry_v0_1.jsonl"
DEFAULT_LOCATED_SEED_PATH = REPO_ROOT / "data" / "manifests" / "developer_ecosystem_official_seed_locator_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "developer_ecosystem_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_ATTEMPTS = REPO_ROOT / "data" / "manifests" / "developer_ecosystem_attempts_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "developer_ecosystem_context_summary_v0_1.json"
DEFAULT_OUTPUT_COVERAGE = REPO_ROOT / "data" / "manifests" / "developer_ecosystem_runtime_coverage_gate_v0_1.json"
DEFAULT_RAW_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/developer_ecosystem")

FetchFunc = Callable[[str, float], tuple[int, str, str]]


DEFAULT_DEVELOPER_PROBES: tuple[dict[str, Any], ...] = (
    {
        "ticker": "MSFT",
        "company_name": "Microsoft",
        "company_names": ["Microsoft", "Azure"],
        "product_terms": ["VS Code", "vscode", "Azure Identity", "@azure/identity"],
        "urls": ["https://github.com/microsoft/vscode", "https://www.npmjs.com/package/@azure/identity"],
    },
    {
        "ticker": "AMZN",
        "company_name": "Amazon",
        "company_names": ["Amazon", "AWS"],
        "product_terms": ["AWS SDK", "aws-sdk-js-v3", "@aws-sdk/client-s3"],
        "urls": ["https://github.com/aws/aws-sdk-js-v3", "https://www.npmjs.com/package/@aws-sdk/client-s3"],
    },
    {
        "ticker": "GOOGL",
        "company_name": "Google",
        "company_names": ["Google", "Google Cloud"],
        "product_terms": ["Google Cloud", "google-cloud-aiplatform", "Gemma", "google/gemma-2-2b"],
        "urls": ["https://pypi.org/project/google-cloud-aiplatform/", "https://huggingface.co/google/gemma-2-2b"],
    },
    {
        "ticker": "NVDA",
        "company_name": "NVIDIA",
        "company_names": ["NVIDIA"],
        "product_terms": ["NeMo", "NVIDIA NeMo", "cuda-samples", "NVIDIA/cuda-samples"],
        "urls": ["https://github.com/NVIDIA/NeMo", "https://github.com/NVIDIA/cuda-samples"],
    },
    {
        "ticker": "CRM",
        "company_name": "Salesforce",
        "company_names": ["Salesforce"],
        "product_terms": ["Salesforce CLI", "forcedotcom/cli", "@salesforce/cli"],
        "urls": ["https://github.com/forcedotcom/cli", "https://www.npmjs.com/package/@salesforce/cli"],
    },
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build bounded L3 developer ecosystem context rows from public APIs.")
    parser.add_argument("--tickers", nargs="*", default=[], help="Optional ticker allowlist.")
    parser.add_argument("--source-layer-rows", type=Path, default=DEFAULT_SOURCE_LAYER_ROWS)
    parser.add_argument("--seed-path", type=Path, default=DEFAULT_SEED_PATH)
    parser.add_argument("--located-seed-path", type=Path, default=DEFAULT_LOCATED_SEED_PATH)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-attempts", type=Path, default=DEFAULT_OUTPUT_ATTEMPTS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-coverage-gate", type=Path, default=DEFAULT_OUTPUT_COVERAGE)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--timeout-s", type=float, default=10.0)
    parser.add_argument("--fetch-retries", type=int, default=2)
    parser.add_argument("--max-rows-per-probe", type=int, default=4)
    parser.add_argument("--replace-output", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if no parser-backed rows are produced.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    probes = [*DEFAULT_DEVELOPER_PROBES, *_load_jsonl(args.seed_path), *_load_jsonl(args.located_seed_path)]
    result = build_developer_ecosystem_context_rows(
        probes=probes,
        generated_at=generated_at,
        tickers=args.tickers,
        raw_dir=args.raw_dir,
        timeout_s=args.timeout_s,
        fetch_retries=args.fetch_retries,
        max_rows_per_probe=args.max_rows_per_probe,
    )
    source_layer_rows = _load_jsonl(args.source_layer_rows)
    output_rows = result["rows"] if args.replace_output else _dedupe_rows([*_load_jsonl(args.output_rows), *result["rows"]])
    output_attempts = (
        result["attempts"]
        if args.replace_output
        else _dedupe_attempts([*_load_jsonl(args.output_attempts), *result["attempts"]])
    )
    coverage_gate = build_developer_ecosystem_coverage_gate(
        context_rows=output_rows,
        source_layer_rows=source_layer_rows,
        generated_at=generated_at,
    )
    summary = build_summary(
        rows=output_rows,
        attempts=output_attempts,
        coverage_gate=coverage_gate,
        generated_at=generated_at,
        output_rows=args.output_rows,
        output_attempts=args.output_attempts,
        output_coverage=args.output_coverage_gate,
    )
    _write_jsonl(args.output_rows, output_rows)
    _write_jsonl(args.output_attempts, output_attempts)
    _write_json(args.output_summary, summary)
    _write_json(args.output_coverage_gate, coverage_gate)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and summary["parser_backed_row_count"] <= 0:
        return 1
    return 0


def build_developer_ecosystem_context_rows(
    *,
    probes: Iterable[Mapping[str, Any]],
    generated_at: str,
    raw_dir: Path,
    tickers: Iterable[str] = (),
    timeout_s: float = 10.0,
    fetch_retries: int = 2,
    max_rows_per_probe: int = 4,
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
            api_url, provider = developer_api_url(source_url)
            if not api_url:
                attempts.append(_attempt(ticker, source_url, "", "unsupported_url", reason="developer_source_url_not_supported"))
                continue
            try:
                status_code, content_type, body = _fetch_with_retries(fetcher, api_url, timeout_s, fetch_retries)
            except Exception as exc:  # noqa: BLE001
                attempts.append(_attempt(ticker, source_url, api_url, "fetch_failed", reason=f"{type(exc).__name__}: {str(exc)[:220]}"))
                continue
            payload_source_url = api_url
            payload_content_type = "application/json"
            payload = _parse_json_object(body) if status_code < 400 and body.strip() else {}
            if provider == "github" and (status_code in {403, 429} or not payload):
                fallback_status, fallback_type, fallback_body = _fetch_github_html_fallback(
                    source_url=source_url,
                    fetcher=fetcher,
                    timeout_s=timeout_s,
                    fetch_retries=fetch_retries,
                )
                fallback_payload = _github_html_payload(source_url, fallback_body) if fallback_status < 400 else {}
                attempts.append(
                    _attempt(
                        ticker,
                        source_url,
                        api_url,
                        "github_api_fallback_html_materialized" if fallback_payload else "github_api_fallback_html_failed",
                        provider=provider,
                        reason=(
                            f"api_http_{status_code}; html_http_{fallback_status}"
                            if fallback_status
                            else f"api_http_{status_code}; html_empty_or_failed"
                        ),
                    )
                )
                if fallback_payload:
                    payload = fallback_payload
                    payload_source_url = source_url
                    payload_content_type = fallback_type or "text/html"
                    body = json.dumps(payload, ensure_ascii=False)
                    content_type = payload_content_type
            if status_code >= 400 and not payload:
                attempts.append(_attempt(ticker, source_url, api_url, "unusable_response", reason=f"http_{status_code}" if status_code else "empty_body"))
                continue
            if not payload:
                attempts.append(_attempt(ticker, source_url, api_url, "unusable_response", reason="non_json_or_empty_payload"))
                continue
            title = developer_source_title(provider=provider, payload=payload, fallback=source_url)
            raw_path = raw_dir / f"{ticker.lower()}_{_slug(provider)}_{_slug(title)}.json"
            raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            repair = {
                "repair_id": f"developer_ecosystem_backfill:{ticker.lower()}:{_slug(title)}",
                "repair_type": "market_proxy",
                "ticker": ticker,
                "company_name": company_name,
                "company_names": company_names,
                "product_terms": _unique_strings([*product_terms, *_product_terms_from_payload(provider, payload)]),
                "product_names": _unique_strings([*product_terms, *_product_terms_from_payload(provider, payload)]),
                "metric_leads": ["stars", "forks", "downloads", "likes", "latest version", "developer activity"],
            }
            parent_ref = _stable_ref("developer_ecosystem", [ticker, provider, api_url])
            parsed_rows = parse_public_web_context_rows(
                ticker=ticker,
                parent_evidence_ref=parent_ref,
                url=payload_source_url,
                source_class="developer_ecosystem_snapshot",
                repair_type="market_proxy",
                analysis_dimension="product_and_production",
                title=f"{company_name} developer ecosystem: {title}",
                body=json.dumps(payload, ensure_ascii=False),
                content_type=payload_content_type,
                as_of_datetime=generated_at,
                citation={"url": payload_source_url, "source_url": source_url, "title": title},
                source_layer_meta={
                    "source_id": SOURCE_ID,
                    "underlying_source_id": SOURCE_ID,
                    "source_layer_id": "L3",
                    "source_layer": "L3",
                    "layer_id": "L3",
                    "parser_status": "developer_ecosystem_api_parser_pass",
                    "structured_fact_status": "bounded_context_fact_materialized",
                    "evidence_graph_status": "runtime_ready_context",
                    "runtime_ready_context": True,
                    "can_support_company_exact_fact": False,
                },
                claim_boundary=(
                    "Developer ecosystem public API context only; supports directional developer activity, package, "
                    "repository, or model attention proxy, not revenue, market share, sales, moat, or customer adoption proof."
                ),
                authority_boundary="L3 developer ecosystem proxy; never exact company metric authority.",
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
                row["payload_source_url"] = payload_source_url
                row["raw_path"] = str(raw_path)
                row["context_only"] = True
                row["exact_value_authority"] = False
                row["can_support_company_exact_fact"] = False
                row["allowed_claims"] = ["developer_ecosystem_context", "market_proxy_context", "verification_lead"]
                row["forbidden_claims"] = ["issuer_revenue", "market_share", "sales_volume", "product_sales", "durable_moat_proof"]
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


def build_developer_ecosystem_coverage_gate(
    *,
    context_rows: list[dict[str, Any]],
    source_layer_rows: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    visible = {
        "product_technology_analyst": context_rows,
        "industry_supply_chain_analyst": context_rows,
    }
    return build_source_coverage_gate(
        industry_schema="semiconductors_hardware",
        phase="runtime_case",
        case_id="developer_ecosystem_context_backfill_smoke",
        source_layer_capability={"rows": source_layer_rows},
        observed_rows=context_rows,
        specialist_visible_rows=visible,
        required_dimensions=["developer_ecosystem_proxy"],
        generated_at=generated_at,
    )


def build_summary(
    *,
    rows: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    coverage_gate: Mapping[str, Any],
    generated_at: str,
    output_rows: Path,
    output_attempts: Path,
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
        "developer_ecosystem_proxy_requirement": _requirement_summary(coverage_gate, "developer_ecosystem_proxy"),
        "outputs": {"rows": str(output_rows), "attempts": str(output_attempts), "coverage_gate": str(output_coverage)},
        "attempts": attempts,
        "boundary": "L3 developer ecosystem rows are directional proxy/context only and cannot prove revenue, market share, sales, customer adoption, or durable moat.",
    }


def developer_api_url(url: str) -> tuple[str, str]:
    text = str(url or "").strip()
    lower = text.lower()
    github = re.match(r"https?://github\.com/([^/\s]+)/([^/\s#?]+)", lower)
    if github:
        owner = github.group(1)
        repo = github.group(2).removesuffix(".git")
        return f"https://api.github.com/repos/{owner}/{repo}", "github"
    npm = re.match(r"https?://www\.npmjs\.com/package/(@?[^/\s#?]+(?:/[^/\s#?]+)?)", lower)
    if npm:
        return f"https://registry.npmjs.org/{quote(npm.group(1), safe='@/')}", "npm"
    pypi = re.match(r"https?://pypi\.org/project/([^/\s#?]+)", lower)
    if pypi:
        return f"https://pypi.org/pypi/{quote(pypi.group(1), safe='')}/json", "pypi"
    huggingface = re.match(r"https?://huggingface\.co/([^/\s#?]+/[^/\s#?]+)", lower)
    if huggingface:
        return f"https://huggingface.co/api/models/{huggingface.group(1)}", "huggingface"
    if lower.startswith("https://api.github.com/repos/"):
        return text, "github"
    if lower.startswith("https://registry.npmjs.org/"):
        return text, "npm"
    if lower.startswith("https://pypi.org/pypi/") and lower.endswith("/json"):
        return text, "pypi"
    if lower.startswith("https://huggingface.co/api/models/"):
        return text, "huggingface"
    return "", ""


def developer_source_title(*, provider: str, payload: Mapping[str, Any], fallback: str) -> str:
    if provider == "github":
        return str(payload.get("full_name") or payload.get("name") or fallback).strip()
    if provider == "npm":
        return str(payload.get("name") or fallback).strip()
    if provider == "pypi":
        info = payload.get("info") if isinstance(payload.get("info"), Mapping) else {}
        return str(info.get("name") or fallback).strip()
    if provider == "huggingface":
        return str(payload.get("modelId") or payload.get("id") or fallback).strip()
    return fallback


def _product_terms_from_payload(provider: str, payload: Mapping[str, Any]) -> list[str]:
    if provider == "github":
        return _unique_strings([payload.get("full_name"), payload.get("name")])
    if provider == "npm":
        return _unique_strings([payload.get("name")])
    if provider == "pypi":
        info = payload.get("info") if isinstance(payload.get("info"), Mapping) else {}
        return _unique_strings([info.get("name"), info.get("summary")])
    if provider == "huggingface":
        return _unique_strings([payload.get("modelId"), payload.get("id"), payload.get("pipeline_tag")])
    return []


def _fetch_url(url: str, timeout_s: float) -> tuple[int, str, str]:
    request = Request(
        url,
        headers={
            "User-Agent": "FIN-Insight-Agent/0.1 developer-ecosystem-source-backfill",
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


def _fetch_github_html_fallback(
    *,
    source_url: str,
    fetcher: FetchFunc,
    timeout_s: float,
    fetch_retries: int,
) -> tuple[int, str, str]:
    parsed = urlparse(source_url)
    if parsed.netloc.lower() != "github.com":
        return 0, "", ""
    try:
        return _fetch_with_retries(fetcher, source_url, timeout_s, fetch_retries)
    except Exception:  # noqa: BLE001
        return 0, "", ""


def _github_html_payload(source_url: str, body: str) -> dict[str, Any]:
    if not body.strip():
        return {}
    parsed = urlparse(source_url)
    path_parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(path_parts) < 2:
        return {}
    owner, repo = path_parts[0], path_parts[1]
    full_name = f"{owner}/{repo}"
    title = _html_unescape(_first_match(r"(?is)<title>\s*GitHub\s+-\s*([^:<]+/[^:<]+).*?</title>", body)) or full_name
    stars = _parse_compact_number(
        _first_match(r'id=["\']repo-stars-counter-star["\'][^>]*title=["\']([^"\']+)["\']', body)
        or _first_match(r'href=["\'][^"\']*/stargazers["\'][^>]*>.*?<strong[^>]*>\s*([^<]+)\s*</strong>', body)
    )
    forks = _parse_compact_number(
        _first_match(r'href=["\'][^"\']*/forks["\'][^>]*>.*?<strong[^>]*>\s*([^<]+)\s*</strong>', body)
    )
    if stars is None and forks is None:
        return {}
    return {
        "full_name": full_name,
        "name": repo,
        "html_url": source_url,
        "description": _html_unescape(_first_match(r'property=["\']og:description["\']\s+content=["\']([^"\']+)["\']', body)),
        "stargazers_count": int(stars or 0),
        "forks_count": int(forks or 0),
        "pushed_at": "",
        "html_fallback_title": title,
        "source_parser": "github_public_html_fallback",
    }


def _first_match(pattern: str, text: str) -> str:
    match = re.search(pattern, text)
    return str(match.group(1)).strip() if match else ""


def _parse_compact_number(value: str) -> int | None:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    multiplier = 1
    if text.lower().endswith("k"):
        multiplier = 1_000
        text = text[:-1]
    elif text.lower().endswith("m"):
        multiplier = 1_000_000
        text = text[:-1]
    try:
        return int(float(text) * multiplier)
    except ValueError:
        return None


def _html_unescape(value: str) -> str:
    return (
        value.replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .strip()
    )


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


def _attempt(ticker: str, source_url: str, api_url: str, status: str, **extra: Any) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "source_url": source_url,
        "api_url": api_url,
        "source_id": SOURCE_ID,
        "underlying_source_id": SOURCE_ID,
        "status": status,
        **extra,
    }


def _stable_ref(prefix: str, parts: Iterable[str]) -> str:
    digest = hashlib.sha1("|".join(str(part or "") for part in parts).encode("utf-8", errors="ignore")).hexdigest()[:14]
    return f"{prefix}:{digest}"


def _dedupe_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        key = str(row.get("evidence_ref") or row.get("evidence_id") or "")
        if not key:
            key = hashlib.sha1(json.dumps(dict(row), sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    return out


def _dedupe_attempts(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        key = "|".join(
            [
                str(row.get("ticker") or "").upper(),
                str(row.get("source_url") or ""),
                str(row.get("api_url") or ""),
                str(row.get("status") or ""),
                str(row.get("reason") or ""),
            ]
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
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


def _slug(value: str) -> str:
    text = "".join(ch.lower() if ch.isalnum() else "_" for ch in value or "")
    return "_".join(part for part in text.split("_") if part)[:72] or "developer"


if __name__ == "__main__":
    raise SystemExit(main())
