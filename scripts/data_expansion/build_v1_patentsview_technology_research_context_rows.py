from __future__ import annotations

import argparse
import hashlib
import json
import os
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


SCHEMA_VERSION = "finsight_v1_patentsview_technology_research_context_row_v0_1"
ATTEMPT_SCHEMA_VERSION = "finsight_v1_patentsview_technology_research_attempt_v0_1"
SUMMARY_SCHEMA_VERSION = "finsight_v1_patentsview_technology_research_summary_v0_1"

SOURCE_ID = "patentsview_api"
PATENTSEARCH_API_URL = "https://search.patentsview.org/api/v1/patent/"

DEFAULT_DOCKET_PATH = REPO_ROOT / "data" / "manifests" / "company_gap_docket_v0_1.jsonl"
DEFAULT_OUTPUT_ROWS = REPO_ROOT / "data" / "manifests" / "v1_patentsview_technology_research_context_rows_v0_1.jsonl"
DEFAULT_OUTPUT_ATTEMPTS = REPO_ROOT / "data" / "manifests" / "v1_patentsview_technology_research_attempts_v0_1.jsonl"
DEFAULT_OUTPUT_SUMMARY = REPO_ROOT / "data" / "manifests" / "v1_patentsview_technology_research_context_summary_v0_1.json"
DEFAULT_RAW_DIR = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/patentsview_v1_technology")

FetchFunc = Callable[[str, bytes, Mapping[str, str], float], tuple[int, str, str]]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build bounded PatentsView assignee/topic technology proxy rows.")
    parser.add_argument("--docket-path", type=Path, default=DEFAULT_DOCKET_PATH)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--output-attempts", type=Path, default=DEFAULT_OUTPUT_ATTEMPTS)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--tickers", nargs="*", default=[])
    parser.add_argument("--api-key-env", default="PATENTSVIEW_API_KEY")
    parser.add_argument("--timeout-s", type=float, default=20.0)
    parser.add_argument("--fetch-retries", type=int, default=1)
    parser.add_argument("--max-rows-per-company", type=int, default=2)
    parser.add_argument("--replace-output", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = _utc_now()
    targets = build_targets(_load_jsonl(args.docket_path), tickers=args.tickers)
    api_key = _load_api_key(args.api_key_env)
    result = build_v1_patentsview_technology_research_context_rows(
        targets=targets,
        generated_at=generated_at,
        raw_dir=args.raw_dir,
        api_key=api_key,
        timeout_s=args.timeout_s,
        fetch_retries=args.fetch_retries,
        max_rows_per_company=args.max_rows_per_company,
    )
    output_rows = result["rows"] if args.replace_output else _dedupe_rows([*_load_jsonl(args.output_rows), *result["rows"]])
    output_attempts = (
        result["attempts"]
        if args.replace_output
        else _dedupe_attempts([*_load_jsonl(args.output_attempts), *result["attempts"]])
    )
    summary = build_summary(
        targets=targets,
        rows=output_rows,
        attempts=output_attempts,
        generated_at=generated_at,
        output_rows=args.output_rows,
        output_attempts=args.output_attempts,
    )
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
    for row in rows:
        if str(row.get("requirement_id") or "") != "technology_research_proxy":
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker or (ticker_filter and ticker not in ticker_filter):
            continue
        family_names = _unique_strings(row.get("family_names") or [])
        family_ids = _unique_strings(row.get("family_ids") or [])
        targets.append(
            {
                "ticker": ticker,
                "company_name": row.get("company_name") or ticker,
                "primary_lane_id": row.get("primary_lane_id") or "",
                "family_ids": family_ids,
                "family_names": family_names,
                "company_aliases": _company_aliases(row.get("company_name") or ticker, ticker),
                "product_terms": _product_terms(family_names=family_names, family_ids=family_ids),
            }
        )
    return targets


def build_v1_patentsview_technology_research_context_rows(
    *,
    targets: Iterable[Mapping[str, Any]],
    generated_at: str,
    raw_dir: Path,
    api_key: str,
    timeout_s: float = 20.0,
    fetch_retries: int = 1,
    max_rows_per_company: int = 2,
    fetch: FetchFunc | None = None,
) -> dict[str, Any]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    fetcher = fetch or _fetch_url
    for target in targets:
        ticker = str(target.get("ticker") or "").strip().upper()
        if not api_key:
            attempts.append(_attempt(ticker, "missing_patentsview_api_key", "PatentSearch API requires X-Api-Key."))
            continue
        query = patentsview_query(target)
        body = json.dumps(query, ensure_ascii=False).encode("utf-8")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "FIN-Insight-Agent/0.1 PatentsView technology proxy",
            "X-Api-Key": api_key,
        }
        try:
            status_code, content_type, response_body = _fetch_with_retries(fetcher, PATENTSEARCH_API_URL, body, headers, timeout_s, fetch_retries)
        except Exception as exc:  # noqa: BLE001
            attempts.append(_attempt(ticker, "fetch_failed", f"{type(exc).__name__}: {str(exc)[:220]}", api_url=PATENTSEARCH_API_URL))
            continue
        raw_path = raw_dir / f"{ticker.lower()}_patentsview_{_stable_digest(json.dumps(query, sort_keys=True))}.json"
        raw_path.write_text(response_body or "", encoding="utf-8")
        if status_code >= 400 or not str(response_body or "").strip():
            attempts.append(_attempt(ticker, "unusable_response", f"http_{status_code}", api_url=PATENTSEARCH_API_URL, raw_path=str(raw_path)))
            continue
        payload = _parse_json_object(response_body)
        if not payload:
            attempts.append(_attempt(ticker, "unusable_response", "non_json_or_empty_payload", api_url=PATENTSEARCH_API_URL, raw_path=str(raw_path)))
            continue
        patent_rows = technology_rows_from_patentsview_payload(
            payload,
            target=target,
            api_url=PATENTSEARCH_API_URL,
            raw_path=raw_path,
            generated_at=generated_at,
            max_rows=max_rows_per_company,
        )
        rows.extend(patent_rows)
        attempts.append(
            _attempt(
                ticker,
                "materialized" if patent_rows else "no_assignee_topic_bound_patents",
                "",
                api_url=PATENTSEARCH_API_URL,
                raw_path=str(raw_path),
                result_count=len(_payload_patents(payload)),
                parsed_row_count=len(patent_rows),
            )
        )
    return {"rows": _dedupe_rows(rows), "attempts": _dedupe_attempts(attempts)}


def patentsview_query(target: Mapping[str, Any]) -> dict[str, Any]:
    aliases = list(target.get("company_aliases") or [])[:3]
    terms = list(target.get("product_terms") or [])[:5]
    assignee_query: dict[str, Any] = {"_or": [{"_text_any": {"assignees.assignee_organization": alias}} for alias in aliases]}
    topic_query: dict[str, Any] = {
        "_or": [
            *({"_text_any": {"patents.patent_title": term}} for term in terms),
            *({"_text_any": {"patents.patent_abstract": term}} for term in terms),
        ]
    }
    return {
        "q": {"_and": [assignee_query, topic_query]},
        "f": [
            "patents.patent_id",
            "patents.patent_title",
            "patents.patent_date",
            "patents.patent_abstract",
            "assignees",
            "cpc_current",
        ],
        "o": {"size": 10},
    }


def technology_rows_from_patentsview_payload(
    payload: Mapping[str, Any],
    *,
    target: Mapping[str, Any],
    api_url: str,
    raw_path: Path,
    generated_at: str,
    max_rows: int,
) -> list[dict[str, Any]]:
    ticker = str(target.get("ticker") or "").strip().upper()
    company_name = str(target.get("company_name") or ticker).strip()
    aliases = _unique_strings(target.get("company_aliases") or [])
    product_terms = _unique_strings(target.get("product_terms") or [])
    rows: list[dict[str, Any]] = []
    for patent in _payload_patents(payload):
        assignee_text = _assignee_text(patent)
        patent_text = _patent_snapshot_text(patent)
        matched_issuer_terms = _matched_terms(assignee_text, aliases)
        matched_product_terms = _matched_terms(patent_text, product_terms)
        if not matched_issuer_terms or not matched_product_terms:
            continue
        patent_id = _first_string(patent, "patent_id", "patents.patent_id", "patent_number")
        title = _first_string(patent, "patent_title", "patents.patent_title", "title") or "PatentsView patent"
        patent_date = _first_string(patent, "patent_date", "patents.patent_date", "date")
        patent_public_url = f"https://patents.google.com/patent/{patent_id}" if patent_id else ""
        evidence_ref = f"patentsview_technology:{_stable_digest('|'.join([ticker, patent_id or title]))}"
        topic = matched_product_terms[0]
        summary = _compact_text(
            f"PatentsView assignee/topic patent proxy for {company_name}: {title}; patent_id={patent_id}; "
            f"matched assignee={', '.join(matched_issuer_terms[:3])}; matched topics={', '.join(matched_product_terms[:4])}. "
            "This is IP/technology activity context only, not product sales, revenue, market share, or moat proof.",
            620,
        )
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": generated_at,
                "evidence_ref": evidence_ref,
                "evidence_id": evidence_ref,
                "snapshot_id": evidence_ref,
                "source_family": "public_source_context",
                "runtime_source_family": "public_source_context",
                "source_id": SOURCE_ID,
                "underlying_source_id": SOURCE_ID,
                "source_class": SOURCE_ID,
                "source_layer_id": "L3",
                "source_layer": "L3",
                "layer_id": "L3",
                "source_specific_parser": "patentsview_patentsearch_assignee_topic_parser_v0_1",
                "source_specific_resolver": "patentsview_patentsearch_assignee_topic_resolver_v0_1",
                "parser_status": "patentsview_patentsearch_parser_pass",
                "structured_fact_status": "bounded_context_fact_materialized",
                "evidence_graph_status": "runtime_ready_context",
                "runtime_ready_context": True,
                "bounded_structured_context": True,
                "structured_context_type": "technology_research_proxy_context",
                "ticker": ticker,
                "company": company_name,
                "source_entity_name": company_name,
                "topic": topic,
                "product_or_segment": topic,
                "product_family": topic,
                "metric_name": "patentsview_assignee_topic_patent",
                "value": 1,
                "unit": "patent_record",
                "period": patent_date[:4] if patent_date else "",
                "patent_id": patent_id,
                "patent_title": title,
                "patent_date": patent_date,
                "api_route": api_url,
                "source_url": api_url,
                "patent_public_url": patent_public_url,
                "raw_path": str(raw_path),
                "as_of_datetime": generated_at,
                "citation": {"url": api_url, "patent_public_url": patent_public_url, "title": title},
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
                    "source_entity_role": "patent_assignee_technology_proxy",
                    "resolver_status": "assignee_product_bound",
                    "binding_claim_boundary": "PatentsView binding supports IP/technology proxy only; no sales, revenue, share, launch, or moat authority.",
                },
                "claim_types": ["technology_research_proxy", "ip_or_research_activity_context", "verification_lead"],
                "allowed_claims": ["technology_research_proxy", "ip_or_research_activity_context", "verification_lead"],
                "forbidden_claims": ["product_launch", "product_sales", "revenue", "market_share", "durable_moat_proof"],
                "context_only": True,
                "exact_value_authority": False,
                "can_support_company_exact_fact": False,
                "claim_boundary": "PatentsView patent signal only; not product launch, sales, revenue, share, or durable moat proof.",
                "authority_boundary": "L3 technology/research proxy; never issuer exact metric authority.",
                "preview": summary,
                "text": summary,
            }
        )
        if len(rows) >= max(0, int(max_rows or 0)):
            break
    return rows


def build_summary(
    *,
    targets: list[Mapping[str, Any]],
    rows: list[Mapping[str, Any]],
    attempts: list[Mapping[str, Any]],
    generated_at: str,
    output_rows: Path,
    output_attempts: Path,
) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if rows else "gap",
        "target_ticker_count": len({str(target.get("ticker") or "") for target in targets}),
        "attempt_count": len(attempts),
        "context_row_count": len(rows),
        "ticker_count": len({str(row.get("ticker") or "") for row in rows if row.get("ticker")}),
        "tickers": sorted({str(row.get("ticker") or "") for row in rows if row.get("ticker")}),
        "attempt_status_counts": dict(sorted(Counter(str(row.get("status") or "") for row in attempts).items())),
        "row_source_counts": dict(sorted(Counter(str(row.get("source_id") or "") for row in rows).items())),
        "outputs": {"rows": str(output_rows), "attempts": str(output_attempts)},
        "boundary": "PatentsView rows are L3 assignee/topic IP proxy only and cannot support product launch, sales, revenue, share, or durable moat claims.",
    }


def _fetch_url(url: str, body: bytes, headers: Mapping[str, str], timeout_s: float) -> tuple[int, str, str]:
    request = Request(url, data=body, headers=dict(headers), method="POST")
    try:
        with urlopen(request, timeout=float(timeout_s or 20.0)) as response:  # noqa: S310
            text = response.read().decode("utf-8", errors="replace")
            return int(getattr(response, "status", 200) or 200), str(response.headers.get("Content-Type") or ""), text
    except HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return int(exc.code or 0), str(exc.headers.get("Content-Type") if exc.headers else ""), text
    except URLError:
        raise


def _fetch_with_retries(
    fetcher: FetchFunc,
    url: str,
    body: bytes,
    headers: Mapping[str, str],
    timeout_s: float,
    retries: int,
) -> tuple[int, str, str]:
    max_attempts = max(1, int(retries or 0) + 1)
    last_exc: Exception | None = None
    for attempt_index in range(max_attempts):
        try:
            return fetcher(url, body, headers, timeout_s)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt_index + 1 >= max_attempts:
                break
            time.sleep(min(1.5, 0.25 * (2**attempt_index)))
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("fetch_failed_without_exception")


def _payload_patents(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    candidates = payload.get("patents") or payload.get("results") or _nested(payload, ("data", "patents")) or []
    return [row for row in candidates if isinstance(row, Mapping)] if isinstance(candidates, list) else []


def _assignee_text(patent: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for group_key in ("assignees", "assignee", "applicants"):
        group = patent.get(group_key)
        if isinstance(group, list):
            for item in group:
                if isinstance(item, Mapping):
                    parts.extend(str(item.get(key) or "") for key in ("assignee_organization", "organization", "name", "applicant_name"))
                else:
                    parts.append(str(item))
        elif isinstance(group, Mapping):
            parts.extend(str(group.get(key) or "") for key in ("assignee_organization", "organization", "name", "applicant_name"))
        elif group:
            parts.append(str(group))
    for key in ("assignee_organization", "assignees.assignee_organization"):
        parts.append(str(patent.get(key) or ""))
    return " ".join(parts)


def _patent_snapshot_text(patent: Mapping[str, Any]) -> str:
    parts = [
        _first_string(patent, "patent_title", "patents.patent_title", "title"),
        _first_string(patent, "patent_abstract", "patents.patent_abstract", "abstract"),
        _assignee_text(patent),
    ]
    for key in ("cpc_current", "cpc_at_issue"):
        value = patent.get(key)
        if isinstance(value, list):
            parts.extend(json.dumps(item, ensure_ascii=False) for item in value[:8])
        elif value:
            parts.append(str(value))
    return " ".join(parts)


def _company_aliases(company_name: str, ticker: str) -> list[str]:
    aliases = [company_name]
    normalized = re.sub(
        r"\b(incorporated|inc|corp|corporation|company|co|ltd|limited|plc|holdings?|class a|/del/|s\.a\.|sa)\b",
        " ",
        company_name,
        flags=re.I,
    )
    aliases.append(normalized)
    if ticker and len(ticker) > 2 and "." not in ticker:
        aliases.append(ticker)
    return [alias for alias in _unique_strings(re.sub(r"\s+", " ", value).strip(" ,.-") for value in aliases) if len(alias) >= 3]


def _product_terms(*, family_names: Iterable[Any], family_ids: Iterable[Any]) -> list[str]:
    terms: list[str] = []
    for value in [*list(family_names), *list(family_ids)]:
        text = str(value or "").replace("/", " ").replace("_", " ")
        for token in re.split(r"\s+", text):
            clean = re.sub(r"[^A-Za-z0-9+-]+", "", token).strip()
            if len(clean) >= 3 and clean.lower() not in {"and", "the", "for", "components", "platform"}:
                terms.append(clean)
        if text.strip():
            terms.append(text.strip())
    return _unique_strings(terms)


def _load_api_key(env_name: str) -> str:
    for key in _unique_strings([env_name, "PATENTSVIEW_API_KEY", "USPTO_PATENTSVIEW_API_KEY", "USPTO_API_KEY"]):
        value = os.environ.get(key)
        if value:
            return value.strip()
    for path in (REPO_ROOT / ".env", REPO_ROOT / ".ENV"):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" not in line or line.strip().startswith("#"):
                continue
            key, value = line.split("=", 1)
            if key.strip() in {env_name, "PATENTSVIEW_API_KEY", "USPTO_PATENTSVIEW_API_KEY", "USPTO_API_KEY"}:
                return value.strip().strip('"').strip("'")
    return ""


def _parse_json_object(body: str) -> dict[str, Any]:
    try:
        value = json.loads(body)
    except json.JSONDecodeError:
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


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


def _matched_terms(text: str, terms: Iterable[Any]) -> list[str]:
    lower = str(text or "").lower()
    return [term for term in _unique_strings(terms) if term.lower() in lower]


def _unique_strings(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


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
        key = "|".join(str(row.get(field) or "") for field in ("ticker", "api_url", "status", "reason"))
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    return out


def _first_string(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _nested(row: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    current: Any = row
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _compact_text(text: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    return value if len(value) <= limit else value[: max(0, limit - 3)].rstrip() + "..."


def _stable_digest(text: str) -> str:
    return hashlib.sha1(str(text or "").encode("utf-8", errors="ignore")).hexdigest()[:16]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _attempt(ticker: str, status: str, reason: str, **extra: Any) -> dict[str, Any]:
    row = {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "ticker": ticker,
        "source_id": SOURCE_ID,
        "underlying_source_id": SOURCE_ID,
        "provider": "patentsview",
        "api_url": PATENTSEARCH_API_URL,
        "source_url": PATENTSEARCH_API_URL,
        "status": status,
        "reason": reason,
    }
    row.update(extra)
    return row


if __name__ == "__main__":
    raise SystemExit(main())
