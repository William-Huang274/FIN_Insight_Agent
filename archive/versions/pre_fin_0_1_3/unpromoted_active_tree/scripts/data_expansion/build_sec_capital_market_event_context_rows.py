from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


SCHEMA_VERSION = "finsight_sec_capital_market_event_context_row_v0_1"
DEFAULT_SUBMISSIONS_DIR = REPO_ROOT / "data" / "raw_private" / "sec" / "_reference" / "submissions"
DEFAULT_COMPANY_TICKERS = REPO_ROOT / "data" / "raw_private" / "sec" / "_reference" / "company_tickers.json"
DEFAULT_COMPANY_UNIVERSE = REPO_ROOT / "data" / "manifests" / "vertical_source_lane_company_assignments_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "sec_capital_market_event_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "sec_capital_market_event_context_summary_v0_1.json"
DEFAULT_OUTPUT_FETCH_LEDGER = REPO_ROOT / "data" / "manifests" / "sec_capital_market_event_submission_fetch_ledger_v0_1.json"


OFFERING_FORMS = {
    "S-1",
    "S-1/A",
    "S-3",
    "S-3/A",
    "S-3ASR",
    "F-1",
    "F-1/A",
    "F-3",
    "F-3/A",
    "424B2",
    "424B3",
    "424B4",
    "424B5",
    "FWP",
}
INSIDER_FORMS = {"3", "3/A", "4", "4/A", "5", "5/A", "144", "144/A"}
BENEFICIAL_OWNERSHIP_FORMS = {
    "SC 13D",
    "SC 13D/A",
    "SC 13G",
    "SC 13G/A",
    "SCHEDULE 13D",
    "SCHEDULE 13D/A",
    "SCHEDULE 13G",
    "SCHEDULE 13G/A",
}
PROXY_GOVERNANCE_FORMS = {"DEF 14A", "DEFA14A", "PRE 14A", "DFAN14A", "PX14A6G"}


def build_sec_capital_market_event_context_rows(
    *,
    submissions: Iterable[Mapping[str, Any]],
    generated_at: str | None = None,
    max_rows_per_ticker_role: int = 8,
    target_tickers: Iterable[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    generated_at = generated_at or _utc_now()
    target_ticker_set = {str(ticker or "").upper().strip() for ticker in target_tickers or [] if str(ticker or "").strip()}
    candidates: list[dict[str, Any]] = []
    for payload in submissions:
        candidates.extend(_rows_from_submission(payload, generated_at=generated_at, target_tickers=target_ticker_set))

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in candidates:
        grouped.setdefault((str(row.get("ticker") or ""), str(row.get("source_role") or "")), []).append(row)

    rows: list[dict[str, Any]] = []
    for key_rows in grouped.values():
        rows.extend(
            sorted(
                key_rows,
                key=lambda item: (str(item.get("filing_date") or ""), str(item.get("acceptance_datetime") or ""), str(item.get("accession_number") or "")),
                reverse=True,
            )[:max(1, max_rows_per_ticker_role)]
        )
    rows.sort(key=lambda item: (str(item.get("ticker") or ""), str(item.get("source_role") or ""), str(item.get("filing_date") or ""), str(item.get("accession_number") or "")))

    summary = {
        "schema_version": "finsight_sec_capital_market_event_context_summary_v0_1",
        "generated_at": generated_at,
        "status": "pass" if rows else "gap",
        "row_count": len(rows),
        "ticker_count": len({str(row.get("ticker") or "") for row in rows if row.get("ticker")}),
        "by_source_role": dict(Counter(str(row.get("source_role") or "") for row in rows)),
        "by_source_id": dict(Counter(str(row.get("source_id") or "") for row in rows)),
        "by_form_type": dict(Counter(str(row.get("form_type") or "") for row in rows).most_common(40)),
        "policy": (
            "SEC submissions metadata rows prove filing-event existence and timing only. They do not prove offering amount, "
            "insider shares, beneficial ownership percentage, buyback amount, or current fund flow without source-specific XML/text parsing."
        ),
    }
    return rows, summary


def _rows_from_submission(payload: Mapping[str, Any], *, generated_at: str, target_tickers: set[str] | None = None) -> list[dict[str, Any]]:
    tickers = _submission_tickers(payload)
    if target_tickers:
        tickers = [ticker for ticker in tickers if ticker in target_tickers]
    else:
        tickers = tickers[:1]
    if not tickers:
        return []
    cik = str(payload.get("cik") or "").zfill(10)
    company_name = str(payload.get("name") or "")
    recent = payload.get("filings", {}).get("recent", {}) if isinstance(payload.get("filings"), Mapping) else {}
    forms = _list(recent.get("form"))
    rows: list[dict[str, Any]] = []
    for ticker in tickers:
        for index, form in enumerate(forms):
            normalized_form = str(form or "").upper().strip()
            role = _source_role_for_form(normalized_form)
            if not role:
                continue
            rows.append(
                _event_row(
                    payload=payload,
                    recent=recent,
                    index=index,
                    ticker=ticker,
                    cik=cik,
                    company_name=company_name,
                    form_type=normalized_form,
                    source_role=role,
                    generated_at=generated_at,
                )
            )
    return rows


def _event_row(
    *,
    payload: Mapping[str, Any],
    recent: Mapping[str, Any],
    index: int,
    ticker: str,
    cik: str,
    company_name: str,
    form_type: str,
    source_role: str,
    generated_at: str,
) -> dict[str, Any]:
    accession = _nth(recent.get("accessionNumber"), index)
    filing_date = _nth(recent.get("filingDate"), index)
    report_date = _nth(recent.get("reportDate"), index)
    primary_document = _nth(recent.get("primaryDocument"), index)
    source_url = _filing_url(cik, accession, primary_document)
    source_id = _source_id_for_role(source_role)
    evidence_ref = f"sec_capital_market_event:{_stable_id(ticker, source_role, accession, form_type)}"
    role_label = source_role.replace("_", " ")
    citation_span = f"SEC submissions metadata reports {ticker} {form_type} filing {accession} filed {filing_date}."
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "evidence_ref": evidence_ref,
        "fact_id": evidence_ref,
        "ticker": ticker,
        "company_name": company_name,
        "cik": cik,
        "source_family": "primary_sec_filing",
        "runtime_source_family": "primary_sec_filing",
        "source_layer_id": "L1",
        "source_id": source_id,
        "source_role": source_role,
        "runtime_contract": _runtime_contract_for_role(source_role),
        "structured_context_type": source_role,
        "parser_status": "parser_pass",
        "structured_fact_status": "bounded_context_fact_materialized",
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "product_binding_status": "not_applicable",
        "counterparty_binding_status": "not_bound",
        "source_url": source_url,
        "filing_date": str(filing_date or ""),
        "report_date": str(report_date or ""),
        "acceptance_datetime": str(_nth(recent.get("acceptanceDateTime"), index) or ""),
        "accession_number": str(accession or ""),
        "form_type": form_type,
        "primary_document": str(primary_document or ""),
        "primary_doc_description": str(_nth(recent.get("primaryDocDescription"), index) or ""),
        "items": str(_nth(recent.get("items"), index) or ""),
        "event_type": source_role,
        "event_label": f"{ticker} {form_type} {role_label}",
        "exact_value_authority": False,
        "can_support_company_exact_fact": False,
        "claim_types": [source_role, "capital_market_event_context"],
        "allowed_claims": _allowed_claims_for_role(source_role),
        "forbidden_claims": _forbidden_claims_for_role(source_role),
        "citation_span": citation_span,
        "claim_boundary": _claim_boundary_for_role(source_role),
        "text": citation_span,
        "preview": citation_span,
        "all_tickers": _list(payload.get("tickers")),
        "exchanges": _list(payload.get("exchanges")),
    }


def _source_role_for_form(form_type: str) -> str:
    if form_type in OFFERING_FORMS:
        return "securities_offering_filing_event"
    if form_type in INSIDER_FORMS:
        return "insider_transaction_filing_event"
    if form_type in BENEFICIAL_OWNERSHIP_FORMS:
        return "beneficial_ownership_filing_event"
    if form_type in PROXY_GOVERNANCE_FORMS:
        return "proxy_governance_filing_event"
    return ""


def _source_id_for_role(source_role: str) -> str:
    return {
        "securities_offering_filing_event": "sec_offering_filing_metadata",
        "insider_transaction_filing_event": "sec_form_3_4_5_metadata",
        "beneficial_ownership_filing_event": "sec_schedule_13d_13g_metadata",
        "proxy_governance_filing_event": "sec_proxy_governance_metadata",
    }.get(source_role, "sec_submissions_metadata")


def _runtime_contract_for_role(source_role: str) -> str:
    return {
        "securities_offering_filing_event": "SecuritiesOfferingFilingEventRow",
        "insider_transaction_filing_event": "InsiderTransactionFilingEventRow",
        "beneficial_ownership_filing_event": "BeneficialOwnershipFilingEventRow",
        "proxy_governance_filing_event": "ProxyGovernanceFilingEventRow",
    }.get(source_role, "SecCapitalMarketFilingEventRow")


def _allowed_claims_for_role(source_role: str) -> list[str]:
    base = ["capital_market_event_context", "filing_event_existence"]
    if source_role == "securities_offering_filing_event":
        return [*base, "securities_offering_context", "financing_activity_signal"]
    if source_role == "insider_transaction_filing_event":
        return [*base, "insider_transaction_context"]
    if source_role == "beneficial_ownership_filing_event":
        return [*base, "beneficial_ownership_context", "activist_or_holder_attention_context"]
    if source_role == "proxy_governance_filing_event":
        return [*base, "governance_proxy_context", "capital_allocation_context"]
    return base


def _forbidden_claims_for_role(source_role: str) -> list[str]:
    common = [
        "offering_amount_without_filing_text_or_xml",
        "security_terms_without_filing_text_or_xml",
        "insider_share_count_without_xml",
        "beneficial_ownership_percentage_without_schedule_parser",
        "buyback_amount_without_company_disclosure",
        "realtime_flow",
        "current_buying_pressure",
        "complete_ownership",
        "intraday_positioning",
    ]
    if source_role == "proxy_governance_filing_event":
        return [*common, "actual_repurchase_without_company_disclosure"]
    return common


def _claim_boundary_for_role(source_role: str) -> str:
    if source_role == "securities_offering_filing_event":
        return (
            "SEC submissions metadata can support offering/registration filing-event existence, form type, accession, "
            "and filing date only. It cannot prove offering amount, security terms, dilution, coupon, maturity, or proceeds "
            "without source-specific filing text/XML parsing."
        )
    if source_role == "insider_transaction_filing_event":
        return (
            "SEC submissions metadata can support Form 3/4/5/144 filing-event existence and timing only. It cannot prove "
            "insider shares, transaction price, ownership change, or management intent without ownership XML parsing."
        )
    if source_role == "beneficial_ownership_filing_event":
        return (
            "SEC submissions metadata can support Schedule 13D/13G filing-event existence and timing only. It cannot prove "
            "beneficial ownership percentage, activist thesis, current buying pressure, or complete ownership without schedule parsing."
        )
    if source_role == "proxy_governance_filing_event":
        return (
            "SEC submissions metadata can support proxy/governance filing-event existence and timing only. It cannot prove actual "
            "buyback amount, compensation outcome, voting result, or governance judgment without filing text/table parsing."
        )
    return "SEC submissions metadata filing-event context only."


def _primary_ticker(payload: Mapping[str, Any]) -> str:
    tickers = _submission_tickers(payload)
    return str(tickers[0] or "").upper().strip() if tickers else ""


def _submission_tickers(payload: Mapping[str, Any]) -> list[str]:
    return _unique_strings(payload.get("tickers") or [])


def _filing_url(cik: str, accession: Any, primary_document: Any) -> str:
    accession_text = str(accession or "")
    doc = str(primary_document or "")
    if not cik or not accession_text or not doc:
        return ""
    cik_int = str(int(cik)) if cik.isdigit() else cik.lstrip("0")
    accession_compact = accession_text.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_compact}/{doc}"


def load_submissions(submissions_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(submissions_dir.glob("CIK*.json")):
        if "-submissions-" in path.name:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, Mapping) and payload.get("filings"):
            rows.append(dict(payload))
    return rows


def fetch_missing_submissions_for_universe(
    *,
    submissions_dir: Path,
    company_universe_rows: Iterable[Mapping[str, Any]],
    company_ticker_map: Mapping[str, str],
    tickers: Iterable[str] = (),
    user_agent: str = "FINInsightAgent/0.1 public-data-research",
    fetch_limit: int = 0,
    request_sleep_seconds: float = 0.12,
    fetch_workers: int = 1,
) -> dict[str, Any]:
    submissions_dir.mkdir(parents=True, exist_ok=True)
    target_tickers = [str(ticker or "").upper().strip() for ticker in tickers if str(ticker or "").strip()]
    if not target_tickers:
        target_tickers = _unique_strings(row.get("ticker") for row in company_universe_rows)
    cached_tickers = _cached_submission_tickers(submissions_dir)
    fetched: list[dict[str, Any]] = []
    skipped_cached: list[str] = []
    non_sec_mappable: list[str] = []
    failures: list[dict[str, Any]] = []
    attempted = 0
    jobs: list[tuple[str, str]] = []
    for ticker in target_tickers:
        if not ticker:
            continue
        if ticker in cached_tickers:
            skipped_cached.append(ticker)
            continue
        cik = str(company_ticker_map.get(ticker) or "").zfill(10)
        if not cik.strip("0"):
            non_sec_mappable.append(ticker)
            continue
        if fetch_limit and attempted >= fetch_limit:
            break
        attempted += 1
        jobs.append((ticker, cik))

    if fetch_workers > 1 and jobs:
        with ThreadPoolExecutor(max_workers=max(1, fetch_workers)) as executor:
            futures = {
                executor.submit(
                    _fetch_one_submission,
                    ticker=ticker,
                    cik=cik,
                    submissions_dir=submissions_dir,
                    user_agent=user_agent,
                ): (ticker, cik)
                for ticker, cik in jobs
            }
            for future in as_completed(futures):
                result = future.result()
                if result.get("status") == "fetched":
                    fetched.append({key: result[key] for key in ("ticker", "cik", "url", "output_path")})
                else:
                    failures.append({key: result.get(key) for key in ("ticker", "cik", "url", "reason", "message")})
    else:
        for ticker, cik in jobs:
            result = _fetch_one_submission(
                ticker=ticker,
                cik=cik,
                submissions_dir=submissions_dir,
                user_agent=user_agent,
            )
            if result.get("status") == "fetched":
                fetched.append({key: result[key] for key in ("ticker", "cik", "url", "output_path")})
            else:
                failures.append({key: result.get(key) for key in ("ticker", "cik", "url", "reason", "message")})
            if request_sleep_seconds > 0:
                time.sleep(request_sleep_seconds)
    return {
        "schema_version": "finsight_sec_submission_fetch_ledger_v0_1",
        "status": "pass" if fetched or skipped_cached else "gap",
        "target_ticker_count": len(target_tickers),
        "cached_skip_count": len(skipped_cached),
        "fetched_count": len(fetched),
        "non_sec_mappable_count": len(non_sec_mappable),
        "failure_count": len(failures),
        "fetch_limit": fetch_limit,
        "fetch_workers": fetch_workers,
        "fetched": sorted(fetched, key=lambda row: str(row.get("ticker") or "")),
        "non_sec_mappable_tickers": non_sec_mappable,
        "failures": failures,
        "policy": (
            "Only SEC company_tickers-mappable issuers are fetched from data.sec.gov submissions. "
            "Non-US/local listings without SEC mapping remain local-exchange/IR parser gaps."
        ),
    }


def _fetch_one_submission(*, ticker: str, cik: str, submissions_dir: Path, user_agent: str) -> dict[str, Any]:
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        try:
            payload = _download_json(url, user_agent=user_agent)
            if not isinstance(payload, Mapping) or "filings" not in payload:
                return {"status": "failed", "ticker": ticker, "cik": cik, "url": url, "reason": "invalid_submissions_payload"}
            output_path = submissions_dir / f"CIK{cik}.json"
            output_path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return {"status": "fetched", "ticker": ticker, "cik": cik, "url": url, "output_path": str(output_path)}
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            return {"status": "failed", "ticker": ticker, "cik": cik, "url": url, "reason": type(exc).__name__, "message": str(exc)[:240]}


def write_outputs(rows: list[dict[str, Any]], summary: Mapping[str, Any], *, output_rows: Path, output_summary: Path) -> dict[str, str]:
    output_rows.parent.mkdir(parents=True, exist_ok=True)
    output_summary.parent.mkdir(parents=True, exist_ok=True)
    output_rows.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    output_summary.write_text(json.dumps(dict(summary), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"rows": str(output_rows), "summary": str(output_summary)}


def load_company_ticker_map(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        return {}
    out: dict[str, str] = {}
    for item in payload.values():
        if not isinstance(item, Mapping):
            continue
        ticker = str(item.get("ticker") or "").upper().strip()
        cik = str(item.get("cik_str") or "").zfill(10)
        if ticker and cik.strip("0"):
            out[ticker] = cik
    return out


def load_company_universe(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            payload = json.loads(text)
            if isinstance(payload, Mapping):
                rows.append(dict(payload))
    return rows


def _cached_submission_tickers(submissions_dir: Path) -> set[str]:
    tickers: set[str] = set()
    for payload in load_submissions(submissions_dir):
        tickers.update(str(ticker or "").upper().strip() for ticker in _list(payload.get("tickers")) if str(ticker or "").strip())
    return tickers


def _download_json(url: str, *, user_agent: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept-Encoding": "identity",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - SEC public JSON endpoint.
        return json.loads(response.read().decode("utf-8"))


def _unique_strings(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").upper().strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _nth(value: Any, index: int) -> Any:
    values = _list(value)
    return values[index] if index < len(values) else ""


def _stable_id(*parts: Any) -> str:
    raw = "\x1f".join(str(part or "") for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Project local SEC submissions metadata into capital-market filing-event context rows.")
    parser.add_argument("--submissions-dir", type=Path, default=DEFAULT_SUBMISSIONS_DIR)
    parser.add_argument("--company-tickers", type=Path, default=DEFAULT_COMPANY_TICKERS)
    parser.add_argument("--company-universe", type=Path, default=DEFAULT_COMPANY_UNIVERSE)
    parser.add_argument("--fetch-missing-submissions", action="store_true")
    parser.add_argument("--fetch-limit", type=int, default=0)
    parser.add_argument("--request-sleep-seconds", type=float, default=0.12)
    parser.add_argument("--fetch-workers", type=int, default=1)
    parser.add_argument("--user-agent", default="FINInsightAgent/0.1 public-data-research")
    parser.add_argument("--tickers", nargs="*", default=[])
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-fetch-ledger", type=Path, default=DEFAULT_OUTPUT_FETCH_LEDGER)
    parser.add_argument("--max-rows-per-ticker-role", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    company_universe_rows = load_company_universe(args.company_universe)
    fetch_ledger: dict[str, Any] = {}
    if args.fetch_missing_submissions:
        fetch_ledger = fetch_missing_submissions_for_universe(
            submissions_dir=args.submissions_dir,
            company_universe_rows=company_universe_rows,
            company_ticker_map=load_company_ticker_map(args.company_tickers),
            tickers=args.tickers,
            user_agent=args.user_agent,
            fetch_limit=args.fetch_limit,
            request_sleep_seconds=args.request_sleep_seconds,
            fetch_workers=args.fetch_workers,
        )
        args.output_fetch_ledger.parent.mkdir(parents=True, exist_ok=True)
        args.output_fetch_ledger.write_text(json.dumps(fetch_ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rows, summary = build_sec_capital_market_event_context_rows(
        submissions=load_submissions(args.submissions_dir),
        max_rows_per_ticker_role=args.max_rows_per_ticker_role,
        target_tickers=args.tickers or _unique_strings(row.get("ticker") for row in company_universe_rows),
    )
    if fetch_ledger:
        summary["fetch_ledger"] = {
            "status": fetch_ledger.get("status"),
            "target_ticker_count": fetch_ledger.get("target_ticker_count"),
            "cached_skip_count": fetch_ledger.get("cached_skip_count"),
            "fetched_count": fetch_ledger.get("fetched_count"),
            "non_sec_mappable_count": fetch_ledger.get("non_sec_mappable_count"),
            "failure_count": fetch_ledger.get("failure_count"),
            "fetch_workers": fetch_ledger.get("fetch_workers"),
            "output_fetch_ledger": str(args.output_fetch_ledger),
        }
    written = write_outputs(rows, summary, output_rows=args.output_rows, output_summary=args.output_summary)
    print(json.dumps({"status": summary["status"], "row_count": summary["row_count"], "written": written}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
