from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
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


SCHEMA_VERSION = "finsight_local_public_tender_context_row_v0_1"
ATTEMPT_SCHEMA_VERSION = "finsight_local_public_tender_attempt_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_local_public_tender_summary_v0_1"

DEFAULT_DOCKET_PATH = REPO_ROOT / "data" / "manifests" / "company_gap_docket_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "local_public_tender_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_ATTEMPTS = REPO_ROOT / "data" / "manifests" / "local_public_tender_attempts_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "local_public_tender_summary_v0_1.json"
DEFAULT_RAW_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/local_public_tenders")

FetchFunc = Callable[[str, float], tuple[int, str, str]]

LOCAL_TENDER_PLANS = {
    "1211.HK": {
        "jurisdiction": "hk",
        "provider": "hk_open_data_contract_awards",
        "source_url": "https://www.digitalpolicy.gov.hk/open_data/business_window/soa-qps-awarded-service-contracts.csv",
        "aliases": ["BYD Company Limited", "BYD", "比亚迪"],
        "parser": "hk_soa_qps_awarded_service_contracts_csv",
    },
    "2308.TW": {
        "jurisdiction": "tw",
        "provider": "tw_pcc_eprocurement",
        "source_url": "https://web.pcc.gov.tw/",
        "aliases": ["Delta Electronics", "台達電子", "台达电子"],
        "parser": "tw_pcc_portal_no_stable_supplier_award_csv_parser",
    },
    "2317.TW": {
        "jurisdiction": "tw",
        "provider": "tw_pcc_eprocurement",
        "source_url": "https://web.pcc.gov.tw/",
        "aliases": ["Hon Hai", "Foxconn", "鴻海", "鸿海"],
        "parser": "tw_pcc_portal_no_stable_supplier_award_csv_parser",
    },
    "2382.TW": {
        "jurisdiction": "tw",
        "provider": "tw_pcc_eprocurement",
        "source_url": "https://web.pcc.gov.tw/",
        "aliases": ["Quanta Computer", "Quanta", "廣達", "广达"],
        "parser": "tw_pcc_portal_no_stable_supplier_award_csv_parser",
    },
    "3231.TW": {
        "jurisdiction": "tw",
        "provider": "tw_pcc_eprocurement",
        "source_url": "https://web.pcc.gov.tw/",
        "aliases": ["Wistron", "緯創", "纬创"],
        "parser": "tw_pcc_portal_no_stable_supplier_award_csv_parser",
    },
    "6752.T": {
        "jurisdiction": "jp",
        "provider": "jp_jetro_procurement",
        "source_url": "https://www.jetro.go.jp/en/database/procurement/",
        "aliases": ["Panasonic Holdings", "Panasonic", "パナソニック"],
        "parser": "jp_jetro_procurement_notice_portal_no_award_csv_parser",
    },
    "8035.T": {
        "jurisdiction": "jp",
        "provider": "jp_jetro_procurement",
        "source_url": "https://www.jetro.go.jp/en/database/procurement/",
        "aliases": ["Tokyo Electron", "TEL", "東京エレクトロン"],
        "parser": "jp_jetro_procurement_notice_portal_no_award_csv_parser",
    },
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build local public tender/order proxy rows or attempt-backed source boundaries.")
    parser.add_argument("--docket-path", type=Path, default=DEFAULT_DOCKET_PATH)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-attempts", type=Path, default=DEFAULT_OUTPUT_ATTEMPTS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--tickers", nargs="*", default=[])
    parser.add_argument("--timeout-s", type=float, default=20.0)
    parser.add_argument("--replace-output", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    targets = build_targets(_load_jsonl(args.docket_path), tickers=args.tickers)
    result = build_local_public_tender_context_rows(
        targets=targets,
        generated_at=generated_at,
        raw_dir=args.raw_dir,
        timeout_s=args.timeout_s,
    )
    output_rows = result["rows"] if args.replace_output else _dedupe_rows([*_load_jsonl(args.output_rows), *result["rows"]])
    output_attempts = (
        result["attempts"]
        if args.replace_output
        else _dedupe_attempts([*_load_jsonl(args.output_attempts), *result["attempts"]])
    )
    summary = build_summary(targets=targets, rows=output_rows, attempts=output_attempts, generated_at=generated_at)
    _write_jsonl(args.output_rows, output_rows)
    _write_jsonl(args.output_attempts, output_attempts)
    _write_json(args.output_summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict and summary["attempt_count"] <= 0:
        return 1
    return 0


def build_targets(rows: Iterable[Mapping[str, Any]], *, tickers: Iterable[str] = ()) -> list[dict[str, Any]]:
    ticker_filter = {str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()}
    targets: list[dict[str, Any]] = []
    gap_tickers = {
        str(row.get("ticker") or "").strip().upper(): row
        for row in rows
        if str(row.get("requirement_id") or "") == "public_order_proxy" and str(row.get("ticker") or "").strip().upper()
    }
    for ticker, plan in LOCAL_TENDER_PLANS.items():
        if ticker_filter and ticker not in ticker_filter:
            continue
        if ticker not in gap_tickers and not ticker_filter:
            continue
        target = dict(plan)
        target["ticker"] = ticker
        target["company_name"] = gap_tickers.get(ticker, {}).get("company_name") or ticker
        targets.append(target)
    return targets


def build_local_public_tender_context_rows(
    *,
    targets: Iterable[Mapping[str, Any]],
    generated_at: str,
    raw_dir: Path,
    timeout_s: float = 20.0,
    fetch: FetchFunc | None = None,
) -> dict[str, list[dict[str, Any]]]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    fetcher = fetch or _fetch_url
    for target in targets:
        ticker = str(target.get("ticker") or "").strip().upper()
        source_url = str(target.get("source_url") or "").strip()
        status_code, content_type, body = fetcher(source_url, timeout_s)
        raw_path = raw_dir / f"{_slug(ticker)}_{_stable_digest(source_url)}.raw"
        raw_path.write_text(body or "", encoding="utf-8", errors="replace")
        if status_code < 200 or status_code >= 300 or not str(body or "").strip():
            attempts.append(_attempt(target, "fetch_failed", f"http_{status_code}", raw_path=raw_path))
            continue
        try:
            parsed_rows = _rows_from_target_payload(target, body, generated_at=generated_at, raw_path=raw_path)
        except Exception as exc:  # noqa: BLE001
            attempts.append(
                _attempt(
                    target,
                    "parser_failed",
                    f"{type(exc).__name__}: {str(exc)[:220]}",
                    raw_path=raw_path,
                    content_type=content_type,
                )
            )
            continue
        rows.extend(parsed_rows)
        attempts.append(
            _attempt(
                target,
                "materialized" if parsed_rows else "no_supplier_bound_award_or_no_structured_award_endpoint",
                "" if parsed_rows else "Local public tender route fetched, but no supplier-bound award row with amount/date/agency was available.",
                raw_path=raw_path,
                parsed_row_count=len(parsed_rows),
                content_type=content_type,
            )
        )
    return {"rows": _dedupe_rows(rows), "attempts": _dedupe_attempts(attempts)}


def _rows_from_target_payload(target: Mapping[str, Any], body: str, *, generated_at: str, raw_path: Path) -> list[dict[str, Any]]:
    parser = str(target.get("parser") or "")
    if parser == "hk_soa_qps_awarded_service_contracts_csv":
        return _hk_soa_qps_rows(target, body, generated_at=generated_at, raw_path=raw_path)
    return []


def _hk_soa_qps_rows(target: Mapping[str, Any], body: str, *, generated_at: str, raw_path: Path) -> list[dict[str, Any]]:
    aliases = [str(alias) for alias in target.get("aliases") or []]
    reader = csv.DictReader(io.StringIO(body.lstrip("\ufeff"), newline=""))
    rows: list[dict[str, Any]] = []
    for record in reader:
        contractor = _first_present(record, "Contractor Awarded", "Contractor", "Supplier", "Awarded Supplier")
        if not _matches_alias(contractor, aliases):
            continue
        award_id = "|".join(
            [
                _first_present(record, "QPS Contract", "Contract"),
                _first_present(record, "Service Category/Group", "Service Category", "Group"),
                _first_present(record, "Bureau/ Department", "Bureau/Department", "Department"),
                _first_present(record, "Work Assignment Title", "Title"),
                _first_present(record, "Date of Award", "Award Date"),
                contractor,
            ]
        )
        rows.append(
            _tender_row(
                target,
                award_id=award_id,
                award_amount=_first_present(record, "Awarded Contract Value SOA-QPS3", "Awarded Contract Value", "Contract Value"),
                award_start_date=_first_present(record, "Date of Award", "Award Date"),
                awarding_agency=_first_present(record, "Bureau/ Department", "Bureau/Department", "Department"),
                award_description=_first_present(record, "Work Assignment Title", "Title"),
                recipient_name=contractor,
                generated_at=generated_at,
                raw_path=raw_path,
            )
        )
    return rows


def _tender_row(
    target: Mapping[str, Any],
    *,
    award_id: str,
    award_amount: Any,
    award_start_date: str,
    awarding_agency: str,
    award_description: str,
    recipient_name: str,
    generated_at: str,
    raw_path: Path,
) -> dict[str, Any]:
    ticker = str(target.get("ticker") or "").strip().upper()
    source_url = str(target.get("source_url") or "").strip()
    evidence_ref = f"local_public_tender:{_stable_digest('|'.join([ticker, award_id, recipient_name]))}"
    text = (
        f"{ticker} local public tender award: recipient={recipient_name}; agency={awarding_agency}; "
        f"award_id={award_id}; amount={award_amount}; date={award_start_date}; description={award_description[:180]}."
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
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
        "source_specific_parser": "local_public_tender_award_parser_v0_1",
        "source_specific_resolver": "local_supplier_to_issuer_alias_resolver_v0_1",
        "parser_status": "source_specific_context_parser_pass",
        "structured_fact_status": "bounded_context_fact_materialized",
        "runtime_ready_context": True,
        "bounded_structured_context": True,
        "structured_context_type": "public_tender_contract_context",
        "requirement_id": "public_order_proxy",
        "ticker": ticker,
        "company": target.get("company_name") or ticker,
        "company_name": target.get("company_name") or ticker,
        "source_url": source_url,
        "api_url": source_url,
        "raw_path": str(raw_path),
        "citation": {"url": source_url, "title": "Local public tender award", "record_id": award_id},
        "award_id": award_id,
        "award_amount": award_amount,
        "award_start_date": award_start_date,
        "awarding_agency": awarding_agency,
        "counterparty": awarding_agency,
        "recipient_name": recipient_name,
        "award_description": award_description,
        "fact_label": f"{recipient_name} local public tender award from {awarding_agency}",
        "product_or_segment": award_description or "local public tender award",
        "product_family": award_description or "local public tender award",
        "period": award_start_date,
        "as_of_datetime": generated_at,
        "issuer_binding_status": "issuer_mentioned_in_snapshot",
        "counterparty_binding_status": "counterparty_mentioned_in_snapshot",
        "entity_binding": {
            "issuer_ticker": ticker,
            "issuer_binding_status": "issuer_mentioned_in_snapshot",
            "issuer_matched_terms": [recipient_name],
            "counterparty_binding_status": "counterparty_mentioned_in_snapshot",
            "counterparty_matched_terms": [awarding_agency],
            "resolver_status": "local_public_tender_supplier_bound_to_issuer",
            "binding_claim_boundary": "Individual local public tender award only; no total order, backlog, revenue, or market-share inference.",
        },
        "resolver_status": "local_public_tender_supplier_bound_to_issuer",
        "context_only": True,
        "exact_value_authority": False,
        "can_support_company_exact_fact": False,
        "allowed_claims": ["public_tender_contract_context", "market_proxy_context", "verification_lead"],
        "forbidden_claims": ["total_orders", "backlog", "issuer_revenue", "market_share", "sales_volume"],
        "claim_boundary": "Individual local public tender award snapshot only; no total order/backlog/revenue promotion.",
        "text": text,
        "preview": text,
    }


def build_summary(
    *,
    targets: list[Mapping[str, Any]],
    rows: list[Mapping[str, Any]],
    attempts: list[Mapping[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if attempts else "gap",
        "target_ticker_count": len({str(target.get("ticker") or "") for target in targets}),
        "attempt_count": len(attempts),
        "row_count": len(rows),
        "row_ticker_count": len({str(row.get("ticker") or "") for row in rows if row.get("ticker")}),
        "row_tickers": sorted({str(row.get("ticker") or "") for row in rows if row.get("ticker")}),
        "attempt_status_counts": dict(sorted(Counter(str(row.get("status") or "") for row in attempts).items())),
        "attempt_provider_counts": dict(sorted(Counter(str(row.get("provider") or "") for row in attempts).items())),
        "boundary": "Local tender rows require supplier-bound award id, amount, date, agency, and official source URL; portal existence alone stays attempt-only.",
    }


def _fetch_url(url: str, timeout_s: float) -> tuple[int, str, str]:
    request = Request(url, headers={"User-Agent": "FIN-Insight-Agent local-public-tender-adapter", "Accept": "*/*"})
    try:
        with urlopen(request, timeout=float(timeout_s or 20.0)) as response:  # noqa: S310
            raw = response.read()
            encoding = response.headers.get_content_charset() or "utf-8"
            return int(getattr(response, "status", 200) or 200), str(response.headers.get("Content-Type") or ""), raw.decode(encoding, errors="replace")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return int(exc.code or 0), str(exc.headers.get("Content-Type") if exc.headers else ""), body
    except (URLError, TimeoutError) as exc:
        return 0, "", f"{type(exc).__name__}: {str(exc)[:220]}"
    except Exception as exc:  # noqa: BLE001
        return 0, "", f"{type(exc).__name__}: {str(exc)[:220]}"


def _attempt(target: Mapping[str, Any], status: str, reason: str, *, raw_path: Path, **extra: Any) -> dict[str, Any]:
    ticker = str(target.get("ticker") or "").strip().upper()
    row = {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "attempt_id": f"local_public_tender_attempt:{_stable_digest('|'.join([ticker, str(target.get('source_url') or ''), status, reason]))}",
        "ticker": ticker,
        "source_id": "public_tenders_contracts_orders",
        "provider": target.get("provider") or "local_public_tender",
        "jurisdiction": target.get("jurisdiction") or "",
        "source_url": target.get("source_url") or "",
        "status": status,
        "reason": reason,
        "raw_path": str(raw_path),
    }
    row.update(extra)
    return row


def _matches_alias(value: str, aliases: Iterable[str]) -> bool:
    norm = _normalize(value)
    return bool(norm) and any(_normalize(alias) and _normalize(alias) in norm for alias in aliases)


def _first_present(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _normalize(value: str) -> str:
    text = re.sub(r"[^a-z0-9\u4e00-\u9fffぁ-んァ-ン一-龥]+", " ", str(value or "").lower())
    text = re.sub(r"\b(inc|incorporated|corp|corporation|co|company|ltd|limited|plc|se|sa|nv|ag|llc|the)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


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
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    return out


def _slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").lower()).strip("_")
    return text[:80] or "unknown"


def _stable_digest(text: str) -> str:
    return hashlib.sha1(str(text or "").encode("utf-8", errors="ignore")).hexdigest()[:16]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
