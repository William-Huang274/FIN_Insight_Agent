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


SCHEMA_VERSION = "fin_agent_v1_trusted_external_context_row_v0_1"
SUMMARY_SCHEMA_VERSION = "fin_agent_v1_trusted_external_context_summary_v0_1"

SOURCE_ID = "industry_association_reports"
DEFAULT_SOURCE_LAYER_ROWS = REPO_ROOT / "data" / "manifests" / "source_layer_capability_audit_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "v1_trusted_external_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "v1_trusted_external_context_summary_v0_1.json"
DEFAULT_OUTPUT_COVERAGE = REPO_ROOT / "data" / "manifests" / "v1_trusted_external_runtime_coverage_gate_v0_1.json"
DEFAULT_RAW_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/v1_trusted_external")

FetchFunc = Callable[[str, float], tuple[int, str, str]]


DEFAULT_TRUSTED_EXTERNAL_PROBES: tuple[dict[str, Any], ...] = (
    {
        "provider": "SIA",
        "url": "https://www.semiconductors.org/global-semiconductor-sales-increase-11-month-to-month-in-april/",
        "title": "SIA global semiconductor sales April 2026",
        "routing_tickers": ["NVDA", "AMD", "QCOM", "TSM", "ASML"],
        "topic_terms": ["semiconductor sales", "industry sales", "cycle", "WSTS"],
    },
    {
        "provider": "SIA",
        "url": "https://www.semiconductors.org/new-report-finds-semiconductors-account-for-95-of-an-ai-data-server-racks-value-encompassing-the-full-stack-of-chip-technologies/",
        "title": "SIA AI data center semiconductor ecosystem report",
        "routing_tickers": ["NVDA", "AMD", "HPE", "DELL", "TSM"],
        "topic_terms": ["AI data center", "server rack", "semiconductor value", "AI infrastructure"],
    },
    {
        "provider": "SEMI",
        "url": "https://www.semi.org/en/semi-press-release/semi-reports-global-semiconductor-equipment-billings-increased-14-percent-year-over-year-in-q1-2026",
        "title": "SEMI Q1 2026 semiconductor equipment billings",
        "routing_tickers": ["ASML", "AMAT", "LRCX", "KLAC", "TSM"],
        "topic_terms": ["equipment billings", "WFE", "capacity", "advanced packaging"],
    },
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build V1 trusted external industry-association context rows.")
    parser.add_argument("--tickers", nargs="*", default=[], help="Optional routing ticker allowlist.")
    parser.add_argument("--source-layer-rows", type=Path, default=DEFAULT_SOURCE_LAYER_ROWS)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-coverage-gate", type=Path, default=DEFAULT_OUTPUT_COVERAGE)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--timeout-s", type=float, default=20.0)
    parser.add_argument("--fetch-retries", type=int, default=2)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if no parser-backed trusted external rows are produced.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    result = build_v1_trusted_external_context_rows(
        probes=DEFAULT_TRUSTED_EXTERNAL_PROBES,
        generated_at=generated_at,
        raw_dir=args.raw_dir,
        tickers=args.tickers,
        timeout_s=args.timeout_s,
        fetch_retries=args.fetch_retries,
    )
    source_layer_rows = _load_jsonl(args.source_layer_rows)
    coverage_gate = build_v1_trusted_external_coverage_gate(
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


def build_v1_trusted_external_context_rows(
    *,
    probes: Iterable[Mapping[str, Any]],
    generated_at: str,
    raw_dir: Path,
    tickers: Iterable[str] = (),
    timeout_s: float = 20.0,
    fetch_retries: int = 2,
    fetch: FetchFunc | None = None,
) -> dict[str, Any]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    ticker_filter = {str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()}
    fetcher = fetch or _fetch_url
    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    for probe in probes:
        url = str(probe.get("url") or "").strip()
        provider = str(probe.get("provider") or "trusted_source").strip()
        if not url:
            attempts.append(_attempt(provider, "", "skipped_no_url"))
            continue
        try:
            status_code, content_type, body = _fetch_with_retries(fetcher, url, timeout_s, fetch_retries)
        except Exception as exc:  # noqa: BLE001
            attempts.append(_attempt(provider, url, "fetch_failed", reason=f"{type(exc).__name__}: {str(exc)[:220]}"))
            continue
        raw_path = raw_dir / f"{_slug(provider)}_{_stable_digest(url)}.html"
        raw_path.write_text(body, encoding="utf-8")
        if status_code >= 400 or not body.strip():
            attempts.append(_attempt(provider, url, "unusable_response", reason=f"http_{status_code}" if status_code else "empty_body", raw_path=str(raw_path)))
            continue
        parsed_count = 0
        for ticker in _unique_strings(probe.get("routing_tickers") or []):
            routing_ticker = str(ticker).upper()
            if ticker_filter and routing_ticker not in ticker_filter:
                continue
            repair = {
                "repair_id": f"v1_trusted_external:{_slug(provider)}:{routing_ticker}:{_stable_digest(url)}",
                "repair_type": "market_proxy",
                "ticker": routing_ticker,
                "company_name": "V1 Semiconductors / AI Infrastructure lane context",
                "company_names": ["Semiconductor Industry Association", "SEMI", provider],
                "product_terms": _unique_strings(probe.get("topic_terms") or []),
                "product_names": _unique_strings(probe.get("topic_terms") or []),
                "metric_leads": ["industry sales", "AI infrastructure context", "equipment billings", "cycle context"],
            }
            parent_ref = _stable_ref("v1_trusted_external", [provider, routing_ticker, url, generated_at[:10]])
            parsed_rows = parse_public_web_context_rows(
                ticker=routing_ticker,
                parent_evidence_ref=parent_ref,
                url=url,
                source_class="industry_association_dataset",
                repair_type="market_proxy",
                analysis_dimension="competition_and_market_position",
                title=str(probe.get("title") or url),
                body=body,
                content_type=content_type or "text/html",
                as_of_datetime=generated_at,
                citation={"url": url, "title": str(probe.get("title") or url), "provider": provider},
                source_layer_meta={
                    "source_id": SOURCE_ID,
                    "underlying_source_id": SOURCE_ID,
                    "source_layer_id": "L2",
                    "source_layer": "L2",
                    "layer_id": "L2",
                    "parser_status": "industry_association_article_parser_pass",
                    "structured_fact_status": "bounded_context_fact_materialized",
                    "evidence_graph_status": "runtime_ready_context",
                    "runtime_ready_context": True,
                    "can_support_company_exact_fact": False,
                },
                claim_boundary=(
                    "V1 trusted industry-association context only; routes industry cycle, AI infrastructure, and equipment context "
                    "to representative tickers, but cannot prove issuer revenue, sales, shipment, backlog, market share, or product KPI."
                ),
                authority_boundary="L2 trusted industry context; never issuer exact metric authority.",
                repair=repair,
                max_rows=2,
            )
            for row in parsed_rows:
                row["schema_version"] = SCHEMA_VERSION
                row["runtime_source_family"] = "public_source_context"
                row["source_family"] = "live_public_web_context"
                row["source_id"] = SOURCE_ID
                row["underlying_source_id"] = SOURCE_ID
                row["provider"] = provider
                row["raw_path"] = str(raw_path)
                row["context_scope"] = "v1_lane_context_routed_to_representative_ticker"
                row["routing_ticker_binding_status"] = "lane_context_routing_not_issuer_claim"
                row["issuer_binding_status"] = "lane_context_not_issuer_bound"
                row["entity_binding"]["issuer_binding_status"] = "lane_context_not_issuer_bound"
                row["entity_binding"]["binding_claim_boundary"] = (
                    "Ticker is used for V1 lane routing only; this industry association row is not issuer-specific evidence."
                )
                row["exact_value_authority"] = False
                row["can_support_company_exact_fact"] = False
                row["allowed_claims"] = ["trusted_industry_association_context", "industry_cycle_context", "market_proxy_context", "verification_lead"]
                row["forbidden_claims"] = ["issuer_revenue", "product_sales", "shipments", "market_share", "backlog", "product_kpi"]
            rows.extend(parsed_rows)
            parsed_count += len(parsed_rows)
        attempts.append(_attempt(provider, url, "materialized" if parsed_count else "parser_no_rows", raw_path=str(raw_path), parsed_row_count=parsed_count))
    return {"rows": _dedupe_rows(rows), "attempts": attempts}


def build_v1_trusted_external_coverage_gate(
    *,
    context_rows: list[dict[str, Any]],
    source_layer_rows: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    visible = {
        "market_valuation_analyst": context_rows,
        "risk_counterevidence_analyst": context_rows,
        "industry_supply_chain_analyst": context_rows,
    }
    return build_source_coverage_gate(
        industry_schema="semiconductors_hardware",
        phase="runtime_case",
        case_id="v1_trusted_external_industry_association_backfill",
        source_layer_capability={"rows": source_layer_rows},
        observed_rows=context_rows,
        specialist_visible_rows=visible,
        required_dimensions=["trusted_external_context"],
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
        "parser_backed_row_count": len([row for row in rows if row.get("source_specific_parser")]),
        "ticker_count": len({str(row.get("ticker") or "") for row in rows if str(row.get("ticker") or "")}),
        "tickers": sorted({str(row.get("ticker") or "") for row in rows if str(row.get("ticker") or "")}),
        "provider_counts": dict(sorted(Counter(str(row.get("provider") or "") for row in rows).items())),
        "structured_context_type_counts": dict(sorted(Counter(str(row.get("structured_context_type") or "") for row in rows).items())),
        "coverage_gate_status": str(coverage_gate.get("status") or ""),
        "trusted_external_context_requirement": _requirement_summary(coverage_gate, "trusted_external_context"),
        "outputs": {"rows": str(output_rows), "coverage_gate": str(output_coverage)},
        "boundary": "Trusted external rows are V1 lane context only and cannot support issuer revenue, sales, shipment, backlog, market-share, or product KPI claims.",
        "attempts": attempts,
    }


def _fetch_url(url: str, timeout_s: float) -> tuple[int, str, str]:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FIN-Insight-Agent/0.1 trusted-external-source-backfill",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urlopen(request, timeout=float(timeout_s or 20.0)) as response:  # noqa: S310
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
            text = line.strip()
            if not text:
                continue
            value = json.loads(text)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
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


def _dedupe_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.get("evidence_ref") or row.get("evidence_id") or "")
        if not key:
            key = hashlib.sha1(json.dumps(dict(row), ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    return out


def _stable_ref(prefix: str, parts: Iterable[Any]) -> str:
    digest = hashlib.sha1("|".join(str(part or "") for part in parts).encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _stable_digest(text: str) -> str:
    return hashlib.sha1(str(text or "").encode("utf-8", errors="ignore")).hexdigest()[:16]


def _slug(text: Any) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", str(text or "").strip()).strip("_").lower()
    return value[:90] or "trusted"


def _attempt(provider: str, url: str, status: str, **extra: Any) -> dict[str, Any]:
    row = {"provider": provider, "url": url, "status": status}
    row.update(extra)
    return row


if __name__ == "__main__":
    raise SystemExit(main())
