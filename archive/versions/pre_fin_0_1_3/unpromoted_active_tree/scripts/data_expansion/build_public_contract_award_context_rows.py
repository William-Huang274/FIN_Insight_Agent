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


SCHEMA_VERSION = "fin_agent_public_contract_award_context_row_v0_1"
SUMMARY_SCHEMA_VERSION = "fin_agent_public_contract_award_context_summary_v0_1"

SOURCE_ID = "public_tenders_contracts_orders"
USA_SPENDING_URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
DEFAULT_SOURCE_LAYER_ROWS = REPO_ROOT / "data" / "manifests" / "source_layer_capability_audit_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "public_contract_award_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "public_contract_award_context_summary_v0_1.json"
DEFAULT_OUTPUT_COVERAGE = REPO_ROOT / "data" / "manifests" / "public_contract_award_runtime_coverage_gate_v0_1.json"
DEFAULT_RAW_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/public_contract_awards")

FetchFunc = Callable[[str, Mapping[str, Any], float], tuple[int, str, str]]


DEFAULT_CONTRACT_PROBES: tuple[dict[str, Any], ...] = (
    {
        "ticker": "PLTR",
        "company_name": "Palantir Technologies",
        "company_names": ["Palantir Technologies", "PALANTIR TECHNOLOGIES INC"],
        "recipient_search_text": ["Palantir Technologies"],
        "product_terms": ["AIP", "Foundry", "Gotham", "data platform", "software"],
    },
    {
        "ticker": "MSFT",
        "company_name": "Microsoft",
        "company_names": ["Microsoft", "MICROSOFT CORPORATION"],
        "recipient_search_text": ["Microsoft Corporation"],
        "product_terms": ["Azure", "cloud", "software", "security"],
    },
    {
        "ticker": "AMZN",
        "company_name": "Amazon",
        "company_names": ["Amazon", "Amazon Web Services", "AWS"],
        "recipient_search_text": ["Amazon Web Services"],
        "product_terms": ["AWS", "cloud", "compute", "infrastructure"],
    },
    {
        "ticker": "ORCL",
        "company_name": "Oracle",
        "company_names": ["Oracle", "ORACLE AMERICA INC"],
        "recipient_search_text": ["Oracle America"],
        "product_terms": ["Oracle Cloud", "database", "software", "enterprise"],
    },
    {
        "ticker": "IBM",
        "company_name": "IBM",
        "company_names": ["IBM", "INTERNATIONAL BUSINESS MACHINES"],
        "recipient_search_text": ["International Business Machines"],
        "product_terms": ["hybrid cloud", "consulting", "software", "infrastructure"],
    },
    {
        "ticker": "LDOS",
        "company_name": "Leidos",
        "company_names": ["Leidos", "LEIDOS INC"],
        "recipient_search_text": ["Leidos"],
        "product_terms": ["defense", "IT services", "systems integration", "mission software"],
    },
    {
        "ticker": "DELL",
        "company_name": "Dell Technologies",
        "company_names": [
            "Dell Technologies",
            "Dell",
            "DELL FEDERAL SYSTEMS L.P.",
            "DELL MARKETING L.P.",
        ],
        "recipient_search_text": ["Dell Federal Systems", "Dell Marketing"],
        "product_terms": ["PowerEdge", "server", "storage", "infrastructure", "AI server"],
    },
    {
        "ticker": "HPE",
        "company_name": "Hewlett Packard Enterprise",
        "company_names": [
            "Hewlett Packard Enterprise",
            "HPE",
            "HEWLETT PACKARD ENTERPRISE COMPANY",
            "HEWLETT PACKARD ENTERPRISE SERVICES LLC",
        ],
        "recipient_search_text": ["Hewlett Packard Enterprise", "Hewlett Packard Enterprise Services"],
        "product_terms": ["ProLiant", "Cray", "server", "supercomputing", "networking"],
    },
    {
        "ticker": "NVDA",
        "company_name": "NVIDIA",
        "company_names": ["NVIDIA", "NVIDIA CORPORATION"],
        "recipient_search_text": ["NVIDIA Corporation"],
        "product_terms": ["GPU", "accelerator", "CUDA", "AI infrastructure", "semiconductor"],
    },
    {
        "ticker": "INTC",
        "company_name": "Intel",
        "company_names": ["Intel", "INTEL CORPORATION"],
        "recipient_search_text": ["Intel Corporation"],
        "product_terms": ["CPU", "processor", "semiconductor", "foundry", "FPGA"],
    },
    {
        "ticker": "AMD",
        "company_name": "Advanced Micro Devices",
        "company_names": ["Advanced Micro Devices", "ADVANCED MICRO DEVICES INC", "AMD"],
        "recipient_search_text": ["Advanced Micro Devices"],
        "product_terms": ["EPYC", "Instinct", "CPU", "GPU", "accelerator"],
    },
    {
        "ticker": "QCOM",
        "company_name": "Qualcomm",
        "company_names": ["Qualcomm", "QUALCOMM INCORPORATED"],
        "recipient_search_text": ["Qualcomm Incorporated"],
        "product_terms": ["Snapdragon", "modem", "RF", "chipset", "semiconductor"],
    },
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build bounded L3 public contract award context rows from USAspending.")
    parser.add_argument("--tickers", nargs="*", default=[], help="Optional ticker allowlist.")
    parser.add_argument("--source-layer-rows", type=Path, default=DEFAULT_SOURCE_LAYER_ROWS)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-coverage-gate", type=Path, default=DEFAULT_OUTPUT_COVERAGE)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--timeout-s", type=float, default=20.0)
    parser.add_argument("--fetch-retries", type=int, default=2)
    parser.add_argument("--max-awards-per-company", type=int, default=3)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if no parser-backed rows are produced.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    result = build_public_contract_award_context_rows(
        probes=DEFAULT_CONTRACT_PROBES,
        generated_at=generated_at,
        raw_dir=args.raw_dir,
        tickers=args.tickers,
        timeout_s=args.timeout_s,
        fetch_retries=args.fetch_retries,
        max_awards_per_company=args.max_awards_per_company,
    )
    source_layer_rows = _load_jsonl(args.source_layer_rows)
    coverage_gate = build_public_contract_award_coverage_gate(
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


def build_public_contract_award_context_rows(
    *,
    probes: Iterable[Mapping[str, Any]],
    generated_at: str,
    raw_dir: Path,
    tickers: Iterable[str] = (),
    timeout_s: float = 20.0,
    fetch_retries: int = 2,
    max_awards_per_company: int = 3,
    fetch: FetchFunc | None = None,
) -> dict[str, Any]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    ticker_filter = {str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()}
    fetcher = fetch or _post_json
    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []

    for probe in probes:
        ticker = str(probe.get("ticker") or "").strip().upper()
        if ticker_filter and ticker not in ticker_filter:
            continue
        company_name = str(probe.get("company_name") or ticker).strip()
        payload = usaspending_payload(probe, limit=max_awards_per_company)
        try:
            status_code, content_type, body = _fetch_with_retries(fetcher, USA_SPENDING_URL, payload, timeout_s, fetch_retries)
        except Exception as exc:  # noqa: BLE001
            attempts.append(_attempt(ticker, USA_SPENDING_URL, "fetch_failed", reason=f"{type(exc).__name__}: {str(exc)[:220]}"))
            continue
        if status_code >= 400 or not body.strip():
            attempts.append(_attempt(ticker, USA_SPENDING_URL, "unusable_response", reason=f"http_{status_code}" if status_code else "empty_body"))
            continue
        response_payload = _parse_json_object(body)
        if not response_payload:
            attempts.append(_attempt(ticker, USA_SPENDING_URL, "unusable_response", reason="non_json_or_empty_payload"))
            continue
        awards = normalize_usaspending_awards(response_payload)[: max(0, int(max_awards_per_company or 0))]
        raw_path = raw_dir / f"{ticker.lower()}_usaspending_contract_awards.json"
        raw_path.write_text(json.dumps(response_payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        json_ld_items = [award_to_json_ld(award, company_name=company_name) for award in awards]
        html_body = (
            "<html><head><script type=\"application/ld+json\">"
            + json.dumps(json_ld_items, ensure_ascii=False)
            + "</script></head><body></body></html>"
        )
        agencies = _unique_strings(award.get("awarding_agency") for award in awards)
        recipient_names = _unique_strings([company_name, *(probe.get("company_names") or []), *(award.get("recipient_name") for award in awards)])
        product_terms = _unique_strings([*(probe.get("product_terms") or []), "contract", "award", "procurement"])
        repair = {
            "repair_id": f"public_contract_award_backfill:{ticker.lower()}",
            "repair_type": "market_proxy",
            "ticker": ticker,
            "company_name": company_name,
            "company_names": recipient_names,
            "issuer_names": recipient_names,
            "counterparties": agencies,
            "product_terms": product_terms,
            "product_names": product_terms,
            "metric_leads": ["award id", "awarding agency", "start date", "award amount", "public contract proxy"],
        }
        parent_ref = _stable_ref("public_contract_award", [ticker, USA_SPENDING_URL, generated_at[:10]])
        parsed_rows = parse_public_web_context_rows(
            ticker=ticker,
            parent_evidence_ref=parent_ref,
            url=USA_SPENDING_URL,
            source_class="public_tender_or_contract_portal",
            repair_type="market_proxy",
            analysis_dimension="industry_supply_chain",
            title=f"{company_name} USAspending public contract awards",
            body=html_body,
            content_type="text/html",
            as_of_datetime=generated_at,
            citation={"url": USA_SPENDING_URL, "title": f"{company_name} USAspending public contract awards"},
            source_layer_meta={
                "source_id": SOURCE_ID,
                "underlying_source_id": SOURCE_ID,
                "source_layer_id": "L3",
                "source_layer": "L3",
                "layer_id": "L3",
                "parser_status": "usaspending_award_jsonld_parser_pass",
                "structured_fact_status": "bounded_context_fact_materialized",
                "evidence_graph_status": "runtime_ready_context",
                "runtime_ready_context": True,
                "can_support_company_exact_fact": False,
            },
            claim_boundary=(
                "Public USAspending contract award context only; supports individual public award/agency existence "
                "and procurement relationship proxy, not total company orders, backlog, revenue, demand, or market share."
            ),
            authority_boundary="L3 public contract/order proxy; never company-wide exact metric authority.",
            repair=repair,
            max_rows=max_awards_per_company,
        )
        award_by_label = {str(award.get("jsonld_name") or ""): award for award in awards}
        for row in parsed_rows:
            row["schema_version"] = SCHEMA_VERSION
            row["runtime_source_family"] = "public_source_context"
            row["source_family"] = "live_public_web_context"
            row["source_id"] = SOURCE_ID
            row["underlying_source_id"] = SOURCE_ID
            row["provider"] = "usaspending"
            row["api_url"] = USA_SPENDING_URL
            row["raw_path"] = str(raw_path)
            row["context_only"] = True
            row["exact_value_authority"] = False
            row["can_support_company_exact_fact"] = False
            row["allowed_claims"] = ["public_tender_contract_context", "market_proxy_context", "verification_lead"]
            row["forbidden_claims"] = ["total_orders", "backlog", "revenue", "sales", "demand_proof", "market_share"]
            matched_award = award_by_label.get(str(row.get("fact_label") or ""))
            if matched_award:
                row["award_id"] = str(matched_award.get("award_id") or "")
                row["award_amount"] = matched_award.get("award_amount")
                row["awarding_agency"] = str(matched_award.get("awarding_agency") or "")
                row["award_start_date"] = str(matched_award.get("start_date") or "")
            rows.append(row)
        attempts.append(
            _attempt(
                ticker,
                USA_SPENDING_URL,
                "materialized" if parsed_rows else "parser_no_rows",
                raw_path=str(raw_path),
                award_count=len(awards),
                parsed_row_count=len(parsed_rows),
                agencies=agencies,
            )
        )
    return {"rows": _dedupe_rows(rows), "attempts": attempts}


def build_public_contract_award_coverage_gate(
    *,
    context_rows: list[dict[str, Any]],
    source_layer_rows: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    visible = {
        "industry_supply_chain_analyst": context_rows,
        "product_technology_analyst": context_rows,
        "capital_ownership_macro_analyst": context_rows,
    }
    return build_source_coverage_gate(
        industry_schema="software_saas",
        phase="runtime_case",
        case_id="public_contract_award_context_backfill_smoke",
        source_layer_capability={"rows": source_layer_rows},
        observed_rows=context_rows,
        specialist_visible_rows=visible,
        required_dimensions=["public_order_proxy"],
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
        "counterparty_binding_status_counts": dict(sorted(Counter(str(row.get("counterparty_binding_status") or "") for row in rows).items())),
        "coverage_gate_status": str(coverage_gate.get("status") or ""),
        "public_order_proxy_requirement": _requirement_summary(coverage_gate, "public_order_proxy"),
        "outputs": {"rows": str(output_rows), "coverage_gate": str(output_coverage)},
        "boundary": "L3 public contract award rows are individual public-award relationship proxy only and cannot prove total orders, backlog, revenue, sales, demand, or share.",
        "attempts": attempts,
    }


def usaspending_payload(probe: Mapping[str, Any], *, limit: int) -> dict[str, Any]:
    return {
        "filters": {
            "recipient_search_text": _unique_strings(probe.get("recipient_search_text") or [probe.get("company_name")]),
            "award_type_codes": ["A", "B", "C", "D"],
        },
        "fields": [
            "Award ID",
            "Recipient Name",
            "Award Amount",
            "Start Date",
            "End Date",
            "Awarding Agency",
            "Award Description",
        ],
        "page": 1,
        "limit": max(1, int(limit or 3)),
        "sort": "Start Date",
        "order": "desc",
    }


def normalize_usaspending_awards(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    results = payload.get("results") if isinstance(payload.get("results"), list) else []
    out: list[dict[str, Any]] = []
    for result in results:
        if not isinstance(result, Mapping):
            continue
        award_id = str(result.get("Award ID") or "").strip()
        recipient = str(result.get("Recipient Name") or "").strip()
        agency = str(result.get("Awarding Agency") or "").strip()
        description = str(result.get("Award Description") or "").strip()
        amount = result.get("Award Amount")
        start = str(result.get("Start Date") or "").strip()
        name = _compact_text(
            f"{recipient} public contract award from {agency}"
            f"{' for ' + description if description else ''}"
            f"{' award ' + award_id if award_id else ''}",
            220,
        )
        out.append(
            {
                "award_id": award_id,
                "recipient_name": recipient,
                "awarding_agency": agency,
                "award_description": description,
                "award_amount": amount,
                "start_date": start,
                "end_date": str(result.get("End Date") or "").strip(),
                "jsonld_name": name,
            }
        )
    return out


def award_to_json_ld(award: Mapping[str, Any], *, company_name: str) -> dict[str, Any]:
    amount = award.get("award_amount")
    agency = str(award.get("awarding_agency") or "").strip()
    description = str(award.get("award_description") or "").strip()
    amount_text = f" Amount={amount}." if amount not in {None, ""} else ""
    return {
        "@context": "https://schema.org",
        "@type": "GovernmentService",
        "name": str(award.get("jsonld_name") or "").strip(),
        "description": _compact_text(
            f"USAspending public contract award for {company_name}; agency={agency}; "
            f"award_id={award.get('award_id') or ''}; description={description}.{amount_text}",
            420,
        ),
        "identifier": str(award.get("award_id") or "").strip(),
        "datePublished": str(award.get("start_date") or "").strip(),
        "provider": {"@type": "GovernmentOrganization", "name": agency},
    }


def _post_json(url: str, payload: Mapping[str, Any], timeout_s: float) -> tuple[int, str, str]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=data,
        headers={
            "User-Agent": "FIN-Insight-Agent/0.1 public-contract-award-source-backfill",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
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


def _fetch_with_retries(fetcher: FetchFunc, url: str, payload: Mapping[str, Any], timeout_s: float, retries: int) -> tuple[int, str, str]:
    max_attempts = max(1, int(retries or 0) + 1)
    last_exc: Exception | None = None
    for attempt_index in range(max_attempts):
        try:
            return fetcher(url, payload, timeout_s)
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


def _compact_text(text: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    return value if len(value) <= limit else value[: max(0, limit - 3)].rstrip() + "..."


def _attempt(ticker: str, api_url: str, status: str, **extra: Any) -> dict[str, Any]:
    row = {"ticker": ticker, "api_url": api_url, "status": status}
    row.update(extra)
    return row


if __name__ == "__main__":
    raise SystemExit(main())
