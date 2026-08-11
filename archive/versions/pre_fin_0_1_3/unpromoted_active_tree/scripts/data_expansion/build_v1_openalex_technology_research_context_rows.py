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
from urllib.parse import urlencode
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.source_coverage_gate import build_source_coverage_gate  # noqa: E402


SCHEMA_VERSION = "fin_agent_v1_openalex_technology_research_context_row_v0_1"
SUMMARY_SCHEMA_VERSION = "fin_agent_v1_openalex_technology_research_context_summary_v0_1"

SOURCE_ID = "openalex_api"
OPENALEX_WORKS_URL = "https://api.openalex.org/works"
DEFAULT_SOURCE_LAYER_ROWS = REPO_ROOT / "data" / "manifests" / "source_layer_capability_audit_v0_1.jsonl"
DEFAULT_FAMILY_SOURCE_ROUTE_PLAN = REPO_ROOT / "data" / "manifests" / "family_source_route_plan_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "v1_openalex_technology_research_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_ATTEMPTS = REPO_ROOT / "data" / "manifests" / "v1_openalex_technology_research_attempts_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "v1_openalex_technology_research_context_summary_v0_1.json"
DEFAULT_OUTPUT_COVERAGE = REPO_ROOT / "data" / "manifests" / "v1_openalex_technology_research_runtime_coverage_gate_v0_1.json"
DEFAULT_RAW_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/openalex_v1_technology")

FetchFunc = Callable[[str, float], tuple[int, str, str]]


DEFAULT_OPENALEX_PROBES: tuple[dict[str, Any], ...] = (
    {
        "ticker": "NVDA",
        "company_name": "NVIDIA",
        "company_names": ["NVIDIA", "Nvidia Corporation", "Nvidia"],
        "product_terms": ["CUDA", "GPU", "parallel computing", "accelerated computing"],
        "search_query": "NVIDIA CUDA GPU parallel computing",
    },
    {
        "ticker": "AMD",
        "company_name": "Advanced Micro Devices",
        "company_names": ["Advanced Micro Devices", "AMD"],
        "product_terms": ["ROCm", "AMD GPUs", "HIP", "GPU"],
        "search_query": "AMD ROCm GPU HIP",
    },
    {
        "ticker": "QCOM",
        "company_name": "Qualcomm",
        "company_names": ["Qualcomm", "Qualcomm Incorporated", "Snapdragon"],
        "product_terms": ["Snapdragon", "Qualcomm", "mobile processor", "SoC"],
        "search_query": "Qualcomm Snapdragon processor",
    },
    {
        "ticker": "ASML",
        "company_name": "ASML",
        "company_names": ["ASML", "ASML Holding"],
        "product_terms": ["EUV", "High-NA", "lithography"],
        "search_query": "ASML EUV lithography High-NA",
    },
    {
        "ticker": "TSM",
        "company_name": "TSMC",
        "company_names": ["TSMC", "Taiwan Semiconductor Manufacturing"],
        "product_terms": ["3nm", "semiconductor", "foundry"],
        "search_query": "TSMC 3nm semiconductor foundry",
    },
)

OPENALEX_COMPANY_ALIAS_OVERRIDES: dict[str, tuple[str, ...]] = {
    "ADI": ("Analog Devices", "Analog Devices Inc", "ADI"),
    "ALB": ("Albemarle", "Albemarle Corporation"),
    "CRM": ("Salesforce", "Salesforce.com", "Salesforce Research"),
    "CSCO": ("Cisco", "Cisco Systems", "Cisco Systems Inc"),
    "FLNC": ("Fluence", "Fluence Energy"),
    "GOOGL": ("Google", "Google LLC", "Google Research", "Alphabet"),
    "MPWR": ("Monolithic Power Systems", "MPS"),
    "PLTR": ("Palantir", "Palantir Technologies"),
    "SQM": ("SQM", "Sociedad Quimica y Minera", "Chemical & Mining Co of Chile"),
    "TDY": ("Teledyne", "Teledyne Technologies"),
    "TER": ("Teradyne",),
    "TSLA": ("Tesla", "Tesla Inc"),
    "TXN": ("Texas Instruments", "TI"),
    "WDAY": ("Workday",),
    "1211.HK": ("BYD", "BYD Company", "BYD Company Limited"),
    "300750.SZ": ("CATL", "Contemporary Amperex", "Contemporary Amperex Technology"),
    "373220.KS": ("LG Energy Solution", "LGES", "LG Energy Solution Ltd"),
}

OPENALEX_TECHNOLOGY_TOPIC_OVERRIDES: dict[str, tuple[str, ...]] = {
    "ADI": ("analog", "signal processing", "data converter", "microcontroller"),
    "CSCO": ("networking", "router", "security", "wireless", "switching"),
    "MPWR": ("power management", "DC-DC", "converter", "voltage regulator"),
    "PLTR": ("Foundry", "ontology", "AIP", "data platform"),
    "TDY": ("imaging", "sensor", "instrumentation", "camera"),
    "TER": ("semiconductor test", "automatic test equipment", "ATE", "test system"),
    "TSLA": ("battery", "autopilot", "supercharger", "electric vehicle"),
    "1211.HK": ("Blade Battery", "battery", "electric vehicle", "DM-i"),
    "300750.SZ": ("battery", "lithium ion", "energy storage", "cell"),
    "373220.KS": ("battery", "lithium ion", "energy storage", "cell"),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build V1 bounded OpenAlex technology/research proxy rows.")
    parser.add_argument("--tickers", nargs="*", default=[], help="Optional ticker allowlist.")
    parser.add_argument("--source-layer-rows", type=Path, default=DEFAULT_SOURCE_LAYER_ROWS)
    parser.add_argument("--family-source-route-plan", type=Path, default=DEFAULT_FAMILY_SOURCE_ROUTE_PLAN)
    parser.add_argument("--from-family-route-plan", action="store_true")
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-attempts", type=Path, default=DEFAULT_OUTPUT_ATTEMPTS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-coverage-gate", type=Path, default=DEFAULT_OUTPUT_COVERAGE)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--timeout-s", type=float, default=18.0)
    parser.add_argument("--fetch-retries", type=int, default=2)
    parser.add_argument("--per-page", type=int, default=5)
    parser.add_argument("--max-rows-per-company", type=int, default=3)
    parser.add_argument("--replace-output", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if no issuer/topic-bound rows are produced.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    probes = (
        openalex_probes_from_family_route_plan(_load_jsonl(args.family_source_route_plan), tickers=args.tickers)
        if args.from_family_route_plan
        else list(DEFAULT_OPENALEX_PROBES)
    )
    result = build_v1_openalex_technology_research_context_rows(
        probes=probes,
        generated_at=generated_at,
        raw_dir=args.raw_dir,
        tickers=args.tickers,
        timeout_s=args.timeout_s,
        fetch_retries=args.fetch_retries,
        per_page=args.per_page,
        max_rows_per_company=args.max_rows_per_company,
    )
    source_layer_rows = _load_jsonl(args.source_layer_rows)
    output_rows = result["rows"] if args.replace_output else _dedupe_rows([*_load_jsonl(args.output_rows), *result["rows"]])
    output_attempts = (
        result["attempts"]
        if args.replace_output
        else _dedupe_attempts([*_load_jsonl(args.output_attempts), *result["attempts"]])
    )
    coverage_gate = build_v1_openalex_coverage_gate(
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


def openalex_probes_from_family_route_plan(
    rows: Iterable[Mapping[str, Any]],
    *,
    tickers: Iterable[str] = (),
) -> list[dict[str, Any]]:
    ticker_filter = {str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()}
    probes_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if str(row.get("route_id") or "") != "technology_research_proxy":
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker or (ticker_filter and ticker not in ticker_filter):
            continue
        company_name = str(row.get("company_name") or ticker).strip()
        query_terms = _unique_strings(row.get("query_terms") or [])
        family_name = str(row.get("family_name") or row.get("family_id") or "").strip()
        product_terms = _unique_strings(OPENALEX_TECHNOLOGY_TOPIC_OVERRIDES.get(ticker, ()) or [family_name, *query_terms])
        if not product_terms:
            continue
        key = (ticker, " ".join(product_terms[:4]).lower())
        company_aliases = _unique_strings([company_name, ticker, *OPENALEX_COMPANY_ALIAS_OVERRIDES.get(ticker, ())])
        search_name = company_aliases[2] if len(company_aliases) > 2 else company_aliases[0]
        search_query = " ".join([search_name, *product_terms[:4]])
        probes_by_key[key] = {
            "ticker": ticker,
            "company_name": company_name,
            "company_names": company_aliases,
            "product_terms": product_terms,
            "search_query": search_query,
        }
    return list(probes_by_key.values())


def build_v1_openalex_technology_research_context_rows(
    *,
    probes: Iterable[Mapping[str, Any]],
    generated_at: str,
    raw_dir: Path,
    tickers: Iterable[str] = (),
    timeout_s: float = 18.0,
    fetch_retries: int = 2,
    per_page: int = 5,
    max_rows_per_company: int = 3,
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
        query = str(probe.get("search_query") or "").strip()
        if not query:
            attempts.append(_attempt(ticker, "", "skipped_no_query"))
            continue
        api_url = openalex_works_search_url(query, per_page=per_page)
        try:
            status_code, content_type, body = _fetch_with_retries(fetcher, api_url, timeout_s, fetch_retries)
        except Exception as exc:  # noqa: BLE001
            attempts.append(_attempt(ticker, api_url, "fetch_failed", reason=f"{type(exc).__name__}: {str(exc)[:220]}"))
            continue
        raw_path = raw_dir / f"{ticker.lower()}_openalex_works_{_slug(query)}.json"
        raw_path.write_text(body, encoding="utf-8")
        if status_code >= 400 or not body.strip():
            attempts.append(_attempt(ticker, api_url, "unusable_response", reason=f"http_{status_code}" if status_code else "empty_body", raw_path=str(raw_path)))
            continue
        payload = _parse_json_object(body)
        if not payload:
            attempts.append(_attempt(ticker, api_url, "unusable_response", reason="non_json_or_empty_payload", raw_path=str(raw_path)))
            continue
        work_rows = technology_rows_from_openalex_payload(
            payload,
            probe=probe,
            api_url=api_url,
            raw_path=raw_path,
            generated_at=generated_at,
            max_rows=max_rows_per_company,
        )
        rows.extend(work_rows)
        attempts.append(
            _attempt(
                ticker,
                api_url,
                "materialized" if work_rows else "no_issuer_topic_bound_works",
                raw_path=str(raw_path),
                result_count=len(payload.get("results") or []) if isinstance(payload.get("results"), list) else 0,
                parsed_row_count=len(work_rows),
            )
        )
    return {"rows": _dedupe_rows(rows), "attempts": attempts}


def openalex_works_search_url(query: str, *, per_page: int = 5) -> str:
    params = {"search": str(query or "").strip(), "per-page": max(1, int(per_page or 5))}
    return f"{OPENALEX_WORKS_URL}?{urlencode(params)}"


def technology_rows_from_openalex_payload(
    payload: Mapping[str, Any],
    *,
    probe: Mapping[str, Any],
    api_url: str,
    raw_path: Path,
    generated_at: str,
    max_rows: int,
) -> list[dict[str, Any]]:
    ticker = str(probe.get("ticker") or "").strip().upper()
    company_name = str(probe.get("company_name") or ticker).strip()
    company_terms = _unique_strings([company_name, *(probe.get("company_names") or [])])
    product_terms = _unique_strings(probe.get("product_terms") or [])
    rows: list[dict[str, Any]] = []
    for work in payload.get("results") or []:
        if not isinstance(work, Mapping):
            continue
        snapshot_text = openalex_work_snapshot_text(work)
        matched_issuer_terms = _matched_terms(snapshot_text, company_terms)
        matched_product_terms = _matched_terms(snapshot_text, product_terms)
        if not matched_issuer_terms or not matched_product_terms:
            continue
        title = str(work.get("title") or "OpenAlex work").strip()
        work_id = str(work.get("id") or "").strip()
        evidence_ref = _stable_ref("v1_openalex_technology", [ticker, work_id or title])
        publication_year = work.get("publication_year")
        cited_by_count = work.get("cited_by_count")
        topic = matched_product_terms[0]
        summary = _compact_text(
            f"OpenAlex technology/research proxy for {company_name}: {title}; "
            f"matched issuer terms={', '.join(matched_issuer_terms[:3])}; "
            f"matched technology topics={', '.join(matched_product_terms[:4])}; "
            f"publication_year={publication_year}; cited_by_count={cited_by_count}. "
            "This is research/IP attention context only, not product launch, sales, revenue, or durable moat proof.",
            620,
        )
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "evidence_ref": evidence_ref,
                "evidence_id": evidence_ref,
                "parent_evidence_ref": _stable_ref("v1_openalex_search", [ticker, api_url]),
                "snapshot_id": evidence_ref,
                "source_family": "public_source_context",
                "runtime_source_family": "public_source_context",
                "source_id": SOURCE_ID,
                "underlying_source_id": SOURCE_ID,
                "source_class": SOURCE_ID,
                "source_layer_id": "L3",
                "source_layer": "L3",
                "layer_id": "L3",
                "source_specific_parser": "openalex_works_search_issuer_topic_parser_v0_1",
                "source_specific_resolver": "openalex_works_search_issuer_topic_resolver_v0_1",
                "parser_status": "openalex_works_search_parser_pass",
                "structured_fact_status": "bounded_context_fact_materialized",
                "evidence_graph_status": "runtime_ready_context",
                "runtime_ready_context": True,
                "bounded_structured_context": True,
                "structured_context_type": "technology_research_proxy_context",
                "claim_types": ["technology_research_proxy", "ip_or_research_activity_context", "verification_lead"],
                "allowed_claims": ["technology_research_proxy", "ip_or_research_activity_context", "verification_lead"],
                "forbidden_claims": ["product_launch", "revenue", "sales", "market_share", "durable_moat_proof"],
                "ticker": ticker,
                "company": company_name,
                "source_entity_name": company_name,
                "topic": topic,
                "product_or_segment": topic,
                "product_family": topic,
                "metric_name": "openalex_work_search_result",
                "value": cited_by_count,
                "unit": "cited_by_count",
                "period": str(publication_year or ""),
                "publication_year": publication_year,
                "cited_by_count": cited_by_count,
                "openalex_work_id": work_id,
                "openalex_doi": str(work.get("doi") or "").strip(),
                "api_route": api_url,
                "raw_path": str(raw_path),
                "as_of_datetime": generated_at,
                "citation": {"url": work_id or api_url, "api_route": api_url, "title": title},
                "issuer_binding_status": "issuer_mentioned_in_snapshot",
                "product_binding_status": "technology_topic_bound",
                "counterparty_binding_status": "not_bound",
                "entity_binding": {
                    "schema_version": "finsight_public_web_entity_binding_v0_1",
                    "issuer_ticker": ticker,
                    "issuer_binding_status": "issuer_mentioned_in_snapshot",
                    "issuer_matched_terms": matched_issuer_terms[:6],
                    "product_binding_status": "technology_topic_bound",
                    "product_matched_terms": matched_product_terms[:6],
                    "counterparty_binding_status": "not_bound",
                    "source_entity_role": "technology_topic_or_ip_proxy",
                    "resolver_status": "issuer_product_bound",
                    "binding_claim_boundary": "OpenAlex binding routes research context to product analyst only; it is not product KPI, sales, launch, share, revenue, or moat authority.",
                },
                "resolver_status": "issuer_product_bound",
                "resolver_reason": "openalex_work_snapshot_mentions_issuer_and_technology_topic",
                "context_only": True,
                "exact_value_authority": False,
                "can_support_company_exact_fact": False,
                "claim_boundary": "OpenAlex research/IP signal only; not product launch, sales, revenue, share, or durable moat proof.",
                "authority_boundary": "L3 technology/research proxy; never issuer exact metric authority.",
                "preview": summary,
                "text": summary,
            }
        )
        if len(rows) >= max(0, int(max_rows or 0)):
            break
    return rows


def openalex_work_snapshot_text(work: Mapping[str, Any]) -> str:
    parts: list[str] = [str(work.get("title") or "")]
    for concept in work.get("concepts") or []:
        if isinstance(concept, Mapping):
            parts.append(str(concept.get("display_name") or ""))
    for authorship in work.get("authorships") or []:
        if not isinstance(authorship, Mapping):
            continue
        for institution in authorship.get("institutions") or []:
            if isinstance(institution, Mapping):
                parts.append(str(institution.get("display_name") or ""))
    inverted = work.get("abstract_inverted_index")
    if isinstance(inverted, Mapping):
        words_by_pos: dict[int, str] = {}
        for word, positions in inverted.items():
            if not isinstance(positions, list):
                continue
            for pos in positions[:3]:
                if isinstance(pos, int):
                    words_by_pos[pos] = str(word)
        if words_by_pos:
            parts.append(" ".join(word for _, word in sorted(words_by_pos.items())[:120]))
    return " ".join(parts)


def build_v1_openalex_coverage_gate(
    *,
    context_rows: list[dict[str, Any]],
    source_layer_rows: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    visible = {"product_technology_analyst": context_rows}
    return build_source_coverage_gate(
        industry_schema="semiconductors_hardware",
        phase="runtime_case",
        case_id="v1_openalex_technology_research_context_backfill",
        source_layer_capability={"rows": source_layer_rows},
        observed_rows=context_rows,
        specialist_visible_rows=visible,
        required_dimensions=["technology_research_proxy"],
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
        "parser_backed_row_count": len([row for row in rows if row.get("source_specific_parser")]),
        "ticker_count": len({str(row.get("ticker") or "") for row in rows if str(row.get("ticker") or "")}),
        "tickers": sorted({str(row.get("ticker") or "") for row in rows if str(row.get("ticker") or "")}),
        "source_id_counts": dict(sorted(Counter(str(row.get("source_id") or "") for row in rows).items())),
        "issuer_binding_status_counts": dict(sorted(Counter(str(row.get("issuer_binding_status") or "") for row in rows).items())),
        "product_binding_status_counts": dict(sorted(Counter(str(row.get("product_binding_status") or "") for row in rows).items())),
        "coverage_gate_status": str(coverage_gate.get("status") or ""),
        "technology_research_proxy_requirement": _requirement_summary(coverage_gate, "technology_research_proxy"),
        "outputs": {"rows": str(output_rows), "attempts": str(output_attempts), "coverage_gate": str(output_coverage)},
        "boundary": "OpenAlex rows are L3 research/IP proxy only and cannot support product launch, sales, revenue, share, or durable moat claims.",
        "attempts": attempts,
    }


def _fetch_url(url: str, timeout_s: float) -> tuple[int, str, str]:
    request = Request(
        url,
        headers={
            "User-Agent": "FIN-Insight-Agent/0.1 OpenAlex technology context (mailto:research@example.com)",
            "Accept": "application/json,text/plain;q=0.8,*/*;q=0.5",
        },
    )
    try:
        with urlopen(request, timeout=float(timeout_s or 18.0)) as response:  # noqa: S310
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


def _matched_terms(text: str, terms: Iterable[Any]) -> list[str]:
    lower = text.lower()
    return [term for term in _unique_strings(terms) if term.lower() in lower]


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


def _dedupe_attempts(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = "|".join(
            [
                str(row.get("ticker") or "").upper(),
                str(row.get("api_url") or row.get("source_url") or ""),
                str(row.get("search_query") or ""),
                str(row.get("status") or ""),
                str(row.get("reason") or ""),
            ]
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    return out


def _stable_ref(prefix: str, parts: Iterable[Any]) -> str:
    digest = hashlib.sha1("|".join(str(part or "") for part in parts).encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _compact_text(text: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    return value if len(value) <= limit else value[: max(0, limit - 3)].rstrip() + "..."


def _slug(value: Any) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", str(value or "").strip()).strip("_").lower()
    return text[:90] or "openalex"


def _attempt(ticker: str, api_url: str, status: str, **extra: Any) -> dict[str, Any]:
    row = {
        "ticker": ticker,
        "api_url": api_url,
        "source_url": api_url,
        "source_id": SOURCE_ID,
        "underlying_source_id": SOURCE_ID,
        "provider": "openalex",
        "status": status,
    }
    row.update(extra)
    return row


if __name__ == "__main__":
    raise SystemExit(main())
