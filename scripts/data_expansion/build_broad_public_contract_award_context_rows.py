from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


SCHEMA_VERSION = "finsight_broad_public_contract_award_context_row_v0_1"
ATTEMPT_SCHEMA_VERSION = "finsight_broad_public_contract_award_attempt_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_broad_public_contract_award_context_summary_v0_1"

USA_SPENDING_URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
DEFAULT_COMPANY_SOURCE_MATRIX = REPO_ROOT / "data" / "manifests" / "company_public_source_coverage_matrix_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "broad_public_contract_award_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_ATTEMPTS = REPO_ROOT / "data" / "manifests" / "broad_public_contract_award_attempts_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "broad_public_contract_award_context_summary_v0_1.json"
DEFAULT_RAW_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/broad_public_contract_awards")

RECIPIENT_ALIAS_OVERRIDES = {
    "AMAT": ("Applied Materials Inc", "Applied Materials Technologies"),
    "BWXT": ("BWXT Nuclear Operations Group",),
    "CARR": ("Carrier Corporation",),
    "CSCO": ("Cisco Systems", "Cisco Systems Inc"),
    "COR": ("Cencora", "AmerisourceBergen", "AmerisourceBergen Drug", "ASD Specialty Healthcare"),
    "CRM": ("Salesforce.com", "Salesforce Inc", "Salesforce.org"),
    "EME": ("EMCOR Government Services",),
    "EMR": ("Emerson Process Management",),
    "FIX": ("Comfort Systems USA Southwest",),
    "FORM": ("FormFactor", "FormFactor Beaverton"),
    "FTV": ("Fortive", "Landauer"),
    "GE": ("General Electric Company", "GE Aviation Systems LLC", "GE Vernova Operations LLC", "GE Vernova International LLC"),
    "GEHC": ("GE Medical Systems", "GE Healthcare IITS USA"),
    "GOOGL": ("Google LLC",),
    "HAL": ("Halliburton Energy Services",),
    "HUBS": ("HubSpot Inc", "HubSpot"),
    "HWM": ("Howmet Aerospace Inc",),
    "IDXX": ("IDEXX", "IDEXX Distribution"),
    "IEX": ("IDEX Health & Science",),
    "INTU": ("Intuit Inc",),
    "J": ("Jacobs Technology Inc", "Jacobs Government Services Company"),
    "LEU": ("Centrus Energy Corp", "American Centrifuge Operating LLC"),
    "MRVL": ("Marvell Government Solutions", "Marvell Semiconductor"),
    "ONTO": ("Onto Innovation", "Nanometrics"),
    "OTIS": ("Otis Elevator Company",),
    "ASML": ("ASML", "ASML US LLC"),
    "CAMT": ("Camtek", "Camtek Inc"),
    "HMC": ("Honda Motor", "American Honda Motor", "American Honda Motor Co"),
    "HUBS": ("HubSpot", "HubSpot Inc"),
    "PATH": ("UiPath", "UiPath Inc"),
    "PWR": ("PAR Electrical Contractors", "PAR Electrical Contractors LLC"),
    "SMCI": ("Super Micro Computer",),
    "TM": ("Toyota Motor Corporation",),
    "WST": ("West Pharmaceutical Services",),
}

STRICT_RECIPIENT_ALIAS_ONLY_TICKERS = {"TM"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build broad USAspending public contract award exact proxy rows.")
    parser.add_argument("--company-source-matrix", type=Path, default=DEFAULT_COMPANY_SOURCE_MATRIX)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-attempts", type=Path, default=DEFAULT_OUTPUT_ATTEMPTS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--tickers", nargs="*", default=[])
    parser.add_argument("--timeout-s", type=float, default=20.0)
    parser.add_argument("--sleep-s", type=float, default=0.03)
    parser.add_argument("--limit", type=int, default=2)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--replace-output", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    matrix_rows = _load_jsonl(args.company_source_matrix)
    result = build_broad_public_contract_award_context_rows(
        matrix_rows=matrix_rows,
        generated_at=generated_at,
        tickers=args.tickers,
        raw_dir=args.raw_dir,
        timeout_s=args.timeout_s,
        sleep_s=args.sleep_s,
        limit=args.limit,
        workers=args.workers,
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


def build_broad_public_contract_award_context_rows(
    *,
    matrix_rows: Iterable[Mapping[str, Any]],
    generated_at: str,
    raw_dir: Path,
    tickers: Iterable[str] = (),
    timeout_s: float = 20.0,
    sleep_s: float = 0.03,
    limit: int = 2,
    workers: int = 12,
) -> dict[str, list[dict[str, Any]]]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    ticker_filter = {str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()}
    companies: list[dict[str, Any]] = []
    for company in matrix_rows:
        ticker = str(company.get("ticker") or "").strip().upper()
        if not ticker or (ticker_filter and ticker not in ticker_filter):
            continue
        requirements = {str(req.get("requirement_id") or "") for req in company.get("source_role_matrix") or [] if isinstance(req, Mapping)}
        if not (requirements & {"public_order_proxy", "supply_chain_official_relationship"}):
            continue
        companies.append(dict(company))

    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    max_workers = max(1, int(workers or 1))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _process_company,
                company,
                generated_at=generated_at,
                raw_dir=raw_dir,
                timeout_s=timeout_s,
                limit=limit,
            ): str(company.get("ticker") or "").strip().upper()
            for company in companies
        }
        for future in as_completed(futures):
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001
                ticker = futures[future]
                attempts.append(
                    _attempt(
                        ticker,
                        status="worker_failed",
                        raw_path=raw_dir / f"{_slug(ticker)}_worker_failed.json",
                        reason=f"{type(exc).__name__}:{str(exc)[:220]}",
                    )
                )
                continue
            rows.extend(result["rows"])
            attempts.extend(result["attempts"])
            if sleep_s:
                time.sleep(float(sleep_s))
    return {"rows": _dedupe_rows(rows), "attempts": attempts}


def _process_company(
    company: Mapping[str, Any],
    *,
    generated_at: str,
    raw_dir: Path,
    timeout_s: float,
    limit: int,
) -> dict[str, list[dict[str, Any]]]:
    ticker = str(company.get("ticker") or "").strip().upper()
    requirements = {str(req.get("requirement_id") or "") for req in company.get("source_role_matrix") or [] if isinstance(req, Mapping)}
    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    aliases = _recipient_aliases(company.get("company_name") or ticker, ticker)
    materialized = 0
    for alias in aliases:
        payload = usaspending_payload([alias], limit=limit)
        status_code, body, reason = _post_json(USA_SPENDING_URL, payload, timeout_s=timeout_s)
        raw_path = raw_dir / f"{_slug(ticker)}_{_slug(alias)}_{_stable_digest(json.dumps(payload, sort_keys=True))}.json"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(body or "", encoding="utf-8")
        if status_code < 200 or status_code >= 300:
            attempts.append(_attempt(ticker, status=f"http_{status_code}", raw_path=raw_path, reason=reason))
            continue
        parsed = _parse_json(body)
        awards = normalize_usaspending_awards(parsed)
        alias_materialized = 0
        for award in awards:
            if not _award_recipient_matches(award.get("recipient_name") or "", aliases):
                continue
            if "public_order_proxy" in requirements:
                rows.append(_award_row(company, award, requirement_id="public_order_proxy", generated_at=generated_at, matched_alias=alias))
            if "supply_chain_official_relationship" in requirements:
                rows.append(
                    _award_row(company, award, requirement_id="supply_chain_official_relationship", generated_at=generated_at, matched_alias=alias)
                )
            alias_materialized += 1
            materialized += 1
        attempts.append(
            _attempt(
                ticker,
                status="materialized" if alias_materialized else "no_bound_records",
                raw_path=raw_path,
                reason="" if alias_materialized else f"USAspending returned no recipient-bound awards for alias={alias}",
                queried_alias=alias,
            )
        )
        if materialized >= max(1, int(limit or 1)):
            break
    return {"rows": rows, "attempts": attempts}


def usaspending_payload(recipient_search_text: Iterable[str], *, limit: int) -> dict[str, Any]:
    return {
        "filters": {
            "recipient_search_text": list(recipient_search_text),
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
        "limit": max(1, int(limit or 2)),
        "sort": "Start Date",
        "order": "desc",
    }


def normalize_usaspending_awards(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    results = payload.get("results") if isinstance(payload.get("results"), list) else []
    out: list[dict[str, Any]] = []
    for result in results:
        if not isinstance(result, Mapping):
            continue
        out.append(
            {
                "award_id": str(result.get("Award ID") or "").strip(),
                "recipient_name": str(result.get("Recipient Name") or "").strip(),
                "awarding_agency": str(result.get("Awarding Agency") or "").strip(),
                "award_description": str(result.get("Award Description") or "").strip(),
                "award_amount": result.get("Award Amount"),
                "award_start_date": str(result.get("Start Date") or "").strip(),
                "award_end_date": str(result.get("End Date") or "").strip(),
            }
        )
    return out


def _award_row(
    company: Mapping[str, Any],
    award: Mapping[str, Any],
    *,
    requirement_id: str,
    generated_at: str,
    matched_alias: str = "",
) -> dict[str, Any]:
    ticker = str(company.get("ticker") or "").strip().upper()
    award_id = str(award.get("award_id") or "").strip()
    agency = str(award.get("awarding_agency") or "").strip()
    recipient = str(award.get("recipient_name") or "").strip()
    description = str(award.get("award_description") or "").strip()
    evidence_ref = _stable_ref("broad_public_contract_award", [ticker, requirement_id, award_id, agency, recipient])
    fact_label = f"{recipient} public contract award from {agency} award {award_id}".strip()
    text = (
        f"{ticker} USAspending public award: recipient={recipient}; agency={agency}; award_id={award_id}; "
        f"amount={award.get('award_amount')}; start={award.get('award_start_date')}; description={description[:180]}."
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "source_id": "public_tenders_contracts_orders",
        "underlying_source_id": "public_tenders_contracts_orders",
        "source_class": "public_tenders_contracts_orders",
        "source_family": "public_source_context",
        "runtime_source_family": "public_source_context",
        "source_layer_id": "L3",
        "source_layer": "L3",
        "layer_id": "L3",
        "source_specific_parser": "broad_usaspending_award_parser_v0_1",
        "source_specific_resolver": "usaspending_recipient_to_issuer_resolver_v0_1",
        "parser_status": "source_specific_context_parser_pass",
        "structured_fact_status": "bounded_context_fact_materialized",
        "runtime_ready_context": True,
        "bounded_structured_context": True,
        "structured_context_type": "public_tender_contract_context",
        "requirement_id": requirement_id,
        "ticker": ticker,
        "company": company.get("company_name") or "",
        "company_name": company.get("company_name") or "",
        "source_url": USA_SPENDING_URL,
        "api_url": USA_SPENDING_URL,
        "citation": {"url": USA_SPENDING_URL, "title": "USAspending public award", "record_id": award_id},
        "award_id": award_id,
        "award_amount": award.get("award_amount"),
        "award_start_date": award.get("award_start_date"),
        "awarding_agency": agency,
        "counterparty": agency,
        "recipient_name": recipient,
        "matched_recipient_alias": matched_alias,
        "award_description": description,
        "fact_label": fact_label,
        "product_or_segment": description or "public contract award",
        "product_family": description or "public contract award",
        "period": award.get("award_start_date"),
        "as_of_datetime": generated_at,
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "product_binding_status": "product_mentioned_in_snapshot",
        "counterparty_binding_status": "counterparty_mentioned_in_snapshot",
        "entity_binding": {
            "issuer_ticker": ticker,
            "issuer_binding_status": "issuer_mentioned_in_snapshot",
            "issuer_matched_terms": [matched_alias] if matched_alias else [],
            "product_binding_status": "product_mentioned_in_snapshot",
            "counterparty_binding_status": "counterparty_mentioned_in_snapshot",
            "counterparty_matched_terms": [agency],
            "resolver_status": "usaspending_recipient_bound_to_issuer",
            "binding_claim_boundary": "Individual public award existence only; no total orders, backlog, revenue, sales, or market share inference.",
        },
        "resolver_status": "usaspending_recipient_bound_to_issuer",
        "context_only": True,
        "exact_value_authority": False,
        "can_support_company_exact_fact": False,
        "allowed_claims": ["public_tender_contract_context", "official_supply_chain_relationship_context", "market_proxy_context", "verification_lead"],
        "forbidden_claims": ["total_orders", "backlog", "issuer_revenue", "market_share", "sales_volume"],
        "claim_boundary": "Individual public tender/award snapshot only; no total order/backlog/revenue promotion.",
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
        if isinstance(req, Mapping) and str(req.get("requirement_id") or "") in {"public_order_proxy", "supply_chain_official_relationship"}
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
        "row_requirement_counts": dict(sorted(Counter(str(row.get("requirement_id") or "") for row in rows).items())),
        "attempt_status_counts": dict(sorted(Counter(str(row.get("status") or "") for row in attempts).items())),
        "unmaterialized_tickers": sorted(required - success),
        "outputs": {"rows": str(output_rows), "attempts": str(output_attempts)},
        "boundary": "USAspending rows are individual public-award snapshots only and cannot prove total orders, backlog, revenue, demand, or share.",
    }


def _post_json(url: str, payload: Mapping[str, Any], *, timeout_s: float) -> tuple[int, str, str]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=data,
        headers={
            "User-Agent": "FIN-Insight-Agent public-contract-award-source-backfill",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_s) as response:
            return int(response.status), response.read().decode("utf-8", errors="replace"), ""
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return int(exc.code or 0), body, f"HTTPError:{exc.code}"
    except (URLError, TimeoutError) as exc:
        return 0, "", f"{type(exc).__name__}:{str(exc)[:200]}"
    except Exception as exc:  # noqa: BLE001
        return 0, "", f"{type(exc).__name__}:{str(exc)[:200]}"


def _parse_json(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _recipient_aliases(company_name: str, ticker: str) -> tuple[str, ...]:
    base = _simplify_company_name(company_name)
    ticker_upper = str(ticker or "").upper()
    aliases = [*RECIPIENT_ALIAS_OVERRIDES.get(ticker_upper, ())]
    if ticker_upper not in STRICT_RECIPIENT_ALIAS_ONLY_TICKERS:
        aliases.extend([company_name, base])
    if ticker_upper not in STRICT_RECIPIENT_ALIAS_ONLY_TICKERS and "amazon" in _normalize(company_name):
        aliases.extend(["Amazon Web Services", "AWS"])
    if ticker_upper not in STRICT_RECIPIENT_ALIAS_ONLY_TICKERS and "microsoft" in _normalize(company_name):
        aliases.append("Microsoft Corporation")
    if ticker_upper not in STRICT_RECIPIENT_ALIAS_ONLY_TICKERS and "oracle" in _normalize(company_name):
        aliases.append("Oracle America")
    if ticker_upper not in STRICT_RECIPIENT_ALIAS_ONLY_TICKERS and "dell" in _normalize(company_name):
        aliases.extend(["Dell Federal Systems", "Dell Marketing"])
    return tuple(_unique(alias for alias in aliases if alias))


def _award_recipient_matches(value: str, aliases: Iterable[str]) -> bool:
    norm = _normalize(value)
    if not norm:
        return False
    norm_tokens = norm.split()
    for alias in aliases:
        alias_norm = _normalize(alias)
        if not alias_norm:
            continue
        alias_tokens = alias_norm.split()
        if norm == alias_norm:
            return True
        if _contains_token_sequence(norm_tokens, alias_tokens):
            return True
        if len(norm_tokens) >= 2 and _contains_token_sequence(alias_tokens, norm_tokens):
            return True
    return False


def _contains_token_sequence(tokens: list[str], needle: list[str]) -> bool:
    if not tokens or not needle or len(needle) > len(tokens):
        return False
    return any(tokens[index : index + len(needle)] == needle for index in range(len(tokens) - len(needle) + 1))


def _attempt(ticker: str, *, status: str, raw_path: Path, reason: str, queried_alias: str = "") -> dict[str, Any]:
    return {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "attempt_id": _stable_ref("broad_public_contract_award_attempt", [ticker, status, raw_path, reason]),
        "ticker": ticker,
        "source_id": "public_tenders_contracts_orders",
        "source_url": USA_SPENDING_URL,
        "status": status,
        "queried_alias": queried_alias,
        "raw_path": str(raw_path),
        "reason": reason,
    }


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


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        key = re.sub(r"\s+", " ", text.lower()).strip()
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
