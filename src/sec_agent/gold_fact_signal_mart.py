from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


GOLD_FACT_SIGNAL_MART_SCHEMA_VERSION = "finsight_gold_fact_signal_mart_row_v0_1"
GOLD_FACT_SIGNAL_MART_SUMMARY_SCHEMA_VERSION = "finsight_gold_fact_signal_mart_summary_v0_1"
GOLD_FACT_SIGNAL_MART_SQLITE_SCHEMA_VERSION = "finsight_gold_fact_signal_mart_sqlite_v0_1"


DEFAULT_SOURCE_ROWSETS: tuple[str, ...] = (
    "data/manifests/sec_financial_statement_metric_runtime_rows_v0_1.jsonl",
    "data/manifests/non_us_l1_financial_statement_metric_runtime_rows_v0_1.jsonl",
    "data/manifests/company_reported_product_operating_metric_runtime_rows_v0_1.jsonl",
    "data/manifests/company_disclosed_product_business_mix_runtime_rows_v0_1.jsonl",
    "data/manifests/non_us_product_kpi_local_disclosure_runtime_rows_v0_1.jsonl",
    "data/manifests/industry_operating_metric_slot_rows_v0_1.jsonl",
    "data/manifests/company_disclosed_product_profile_context_rows_v0_1.jsonl",
    "data/manifests/official_product_catalog_context_rows_v0_1.jsonl",
    "data/manifests/official_product_spec_context_rows_v0_1.jsonl",
    "data/manifests/official_customer_deployment_surface_context_rows_v0_1.jsonl",
    "data/manifests/public_contract_award_context_rows_v0_1.jsonl",
    "data/manifests/capital_funding_ownership_context_rows_v0_1.jsonl",
    "data/manifests/sec_capital_market_event_context_rows_v0_1.jsonl",
    "data/manifests/market_liquidity_driver_context_rows_v0_1.jsonl",
    "data/manifests/v1_macro_official_exposure_context_rows_v0_1.jsonl",
    "data/manifests/public_official_api_context_rows_v0_1.jsonl",
    "data/manifests/r18_source_authority_data_mart_rows_v0_1.jsonl",
)

SQLITE_COLUMNS: tuple[str, ...] = (
    "gold_row_id",
    "schema_version",
    "generated_at",
    "source_rowset_path",
    "source_row_id",
    "ticker",
    "company_name",
    "fact_domain",
    "fact_type",
    "support_surface",
    "authority_mode",
    "can_enter_evidence_bundle",
    "exact_value_authority",
    "can_support_company_exact_fact",
    "source_layer",
    "source_role",
    "source_id",
    "metric_family",
    "metric_name",
    "canonical_metric_id",
    "value",
    "unit",
    "period",
    "fiscal_year",
    "as_of_date",
    "product_family",
    "product_or_segment",
    "counterparty",
    "event_type",
    "object_type",
    "claim_types_json",
    "allowed_claims_json",
    "forbidden_claims_json",
    "claim_boundary",
    "citation_url",
    "citation_span",
    "evidence_ref",
    "source_url",
    "raw_path",
    "parser_status",
    "structured_fact_status",
    "runtime_contract",
    "source_specific_parser",
    "payload_json",
)


def build_gold_fact_signal_mart(
    repo_root: str | Path,
    *,
    generated_at: str | None = None,
    source_rowsets: Sequence[str] = DEFAULT_SOURCE_ROWSETS,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    generated_at = generated_at or _utc_now()
    rows: list[dict[str, Any]] = []
    source_rowset_status: list[dict[str, Any]] = []
    for relative_path in source_rowsets:
        path = (root / relative_path).resolve()
        if not path.exists():
            source_rowset_status.append(
                {
                    "source_rowset_path": relative_path,
                    "exists": False,
                    "row_count": 0,
                    "fact_domain_counts": {},
                }
            )
            continue
        count = 0
        domain_counts: Counter[str] = Counter()
        for ordinal, source_row in enumerate(_read_jsonl(path), start=1):
            mart_row = _mart_row(root, path, source_row, ordinal=ordinal, generated_at=generated_at)
            rows.append(mart_row)
            count += 1
            domain_counts[mart_row["fact_domain"]] += 1
        source_rowset_status.append(
            {
                "source_rowset_path": relative_path,
                "exists": True,
                "row_count": count,
                "fact_domain_counts": dict(domain_counts),
            }
        )
    summary = build_gold_fact_signal_mart_summary(
        rows=rows,
        source_rowset_status=source_rowset_status,
        generated_at=generated_at,
    )
    return {"rows": rows, "source_rowset_status": source_rowset_status, "summary": summary}


def build_gold_fact_signal_mart_summary(
    *,
    rows: Sequence[Mapping[str, Any]],
    source_rowset_status: Sequence[Mapping[str, Any]],
    generated_at: str | None = None,
    sqlite_path: str = "",
    sqlite_row_count: int = 0,
) -> dict[str, Any]:
    generated_at = generated_at or _utc_now()
    missing_rowsets = [row for row in source_rowset_status if not row.get("exists")]
    can_enter_rows = [row for row in rows if row.get("can_enter_evidence_bundle")]
    exact_rows = [row for row in rows if row.get("authority_mode") == "exact_company_fact_authority"]
    bounded_rows = [row for row in rows if row.get("authority_mode") == "bounded_thesis_driver_authority"]
    planning_rows = [row for row in rows if row.get("authority_mode") == "planning_or_gap_only"]
    status = "pass" if not missing_rowsets and sqlite_row_count in {0, len(rows)} else "action_required"
    return {
        "schema_version": GOLD_FACT_SIGNAL_MART_SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": status,
        "row_count": len(rows),
        "company_count": len({str(row.get("ticker") or "") for row in rows if row.get("ticker")}),
        "source_rowset_count": len(source_rowset_status),
        "missing_source_rowset_count": len(missing_rowsets),
        "sqlite_path": sqlite_path,
        "sqlite_row_count": sqlite_row_count,
        "evidence_bundle_allowed_count": len(can_enter_rows),
        "exact_company_fact_authority_count": len(exact_rows),
        "bounded_thesis_driver_authority_count": len(bounded_rows),
        "planning_or_gap_only_count": len(planning_rows),
        "by_fact_domain": dict(Counter(str(row.get("fact_domain") or "") for row in rows)),
        "by_authority_mode": dict(Counter(str(row.get("authority_mode") or "") for row in rows)),
        "by_support_surface": dict(Counter(str(row.get("support_surface") or "") for row in rows)),
        "by_source_layer": dict(Counter(str(row.get("source_layer") or "") for row in rows)),
        "top_source_roles": dict(Counter(str(row.get("source_role") or "") for row in rows).most_common(30)),
        "missing_source_rowset_samples": list(missing_rowsets[:20]),
        "policy": (
            "RD3 Gold Fact / Signal Mart is a unified research fact and bounded-signal row contract. Rows retain "
            "authority mode, allowed/forbidden claims, citation, parser status, and source rowset lineage. Planning "
            "or gap-only rows must not enter ClaimCards."
        ),
    }


def write_gold_fact_signal_mart_sqlite(
    sqlite_path: str | Path,
    rows: Sequence[Mapping[str, Any]],
    *,
    replace: bool = True,
) -> int:
    target = Path(sqlite_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(target)) as conn:
        conn.execute(
            """
            create table if not exists gold_fact_signal_mart (
                gold_row_id text primary key,
                schema_version text not null,
                generated_at text not null,
                source_rowset_path text not null,
                source_row_id text not null,
                ticker text,
                company_name text,
                fact_domain text not null,
                fact_type text,
                support_surface text,
                authority_mode text,
                can_enter_evidence_bundle integer,
                exact_value_authority integer,
                can_support_company_exact_fact integer,
                source_layer text,
                source_role text,
                source_id text,
                metric_family text,
                metric_name text,
                canonical_metric_id text,
                value text,
                unit text,
                period text,
                fiscal_year text,
                as_of_date text,
                product_family text,
                product_or_segment text,
                counterparty text,
                event_type text,
                object_type text,
                claim_types_json text,
                allowed_claims_json text,
                forbidden_claims_json text,
                claim_boundary text,
                citation_url text,
                citation_span text,
                evidence_ref text,
                source_url text,
                raw_path text,
                parser_status text,
                structured_fact_status text,
                runtime_contract text,
                source_specific_parser text,
                payload_json text
            )
            """
        )
        conn.execute(
            """
            create table if not exists gold_fact_signal_mart_metadata (
                key text primary key,
                value text not null
            )
            """
        )
        if replace:
            conn.execute("delete from gold_fact_signal_mart")
        payload = [[_sqlite_value(row.get(column)) for column in SQLITE_COLUMNS] for row in rows]
        placeholders = ", ".join("?" for _ in SQLITE_COLUMNS)
        conn.executemany(
            f"insert or replace into gold_fact_signal_mart ({', '.join(SQLITE_COLUMNS)}) values ({placeholders})",
            payload,
        )
        conn.execute(
            "insert or replace into gold_fact_signal_mart_metadata(key, value) values (?, ?)",
            ("schema_version", GOLD_FACT_SIGNAL_MART_SQLITE_SCHEMA_VERSION),
        )
        for column in ("ticker", "fact_domain", "authority_mode", "source_role", "support_surface"):
            conn.execute(f"create index if not exists idx_gold_fact_signal_mart_{column} on gold_fact_signal_mart({column})")
        conn.commit()
        return int(conn.execute("select count(*) from gold_fact_signal_mart").fetchone()[0])


def render_gold_fact_signal_mart_report(summary: Mapping[str, Any], *, output_paths: Mapping[str, str]) -> str:
    lines = [
        "# RD3 Gold Fact / Signal Mart",
        "",
        f"- Generated at: `{summary.get('generated_at', '')}`",
        f"- Status: `{summary.get('status', '')}`",
        f"- Rows: `{summary.get('row_count', 0)}`",
        f"- Companies: `{summary.get('company_count', 0)}`",
        f"- Source rowsets: `{summary.get('source_rowset_count', 0)}`",
        f"- Missing source rowsets: `{summary.get('missing_source_rowset_count', 0)}`",
        f"- SQLite rows: `{summary.get('sqlite_row_count', 0)}`",
        "",
        "## Outputs",
        "",
    ]
    for key, path in output_paths.items():
        lines.append(f"- `{key}`: `{path}`")
    lines.extend(
        [
            "",
            "## Authority",
            "",
            _markdown_counter_table(summary.get("by_authority_mode") or {}, "Authority mode", "Rows"),
            "",
            "## Fact Domains",
            "",
            _markdown_counter_table(summary.get("by_fact_domain") or {}, "Domain", "Rows"),
            "",
            "## Support Surfaces",
            "",
            _markdown_counter_table(summary.get("by_support_surface") or {}, "Surface", "Rows"),
            "",
            "## Boundary",
            "",
            "- RD3 只统一 accepted fact / bounded signal / source-authority row contract，不改变原始 authority。",
            "- `planning_or_gap_only` 行只允许进入 planning/gap ledger，不允许进入 ClaimCard evidence bundle。",
            "- Product spec、customer deployment、market liquidity、macro/context rows 可以支持 thesis driver，但不能冒充产品销量、ASP、份额、sell-through、backlog 或收入 exact。",
            "",
        ]
    )
    return "\n".join(lines)


def write_jsonl(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _mart_row(root: Path, source_path: Path, row: Mapping[str, Any], *, ordinal: int, generated_at: str) -> dict[str, Any]:
    rel = _rel(source_path, root)
    source_row_id = _source_row_id(row, rel, ordinal)
    citation = row.get("citation") if isinstance(row.get("citation"), Mapping) else {}
    fact_domain = _fact_domain(rel, row)
    authority_mode = _authority_mode(row)
    can_enter_evidence_bundle = _can_enter_evidence_bundle(row, authority_mode)
    payload = _compact_payload(row)
    return {
        "schema_version": GOLD_FACT_SIGNAL_MART_SCHEMA_VERSION,
        "generated_at": generated_at,
        "gold_row_id": _stable_id("rd3_gold_fact_signal", rel, source_row_id),
        "source_rowset_path": rel,
        "source_row_id": source_row_id,
        "ticker": _first_text(row, "ticker"),
        "company_name": _first_text(row, "company_name", "company"),
        "fact_domain": fact_domain,
        "fact_type": _fact_type(rel, row, fact_domain),
        "support_surface": _support_surface(row, fact_domain),
        "authority_mode": authority_mode,
        "can_enter_evidence_bundle": can_enter_evidence_bundle,
        "exact_value_authority": bool(row.get("exact_value_authority") or row.get("exact_company_fact_authority")),
        "can_support_company_exact_fact": bool(row.get("can_support_company_exact_fact") or row.get("exact_company_fact_authority")),
        "source_layer": _first_text(row, "source_layer", "source_layer_id", "layer_id"),
        "source_role": _first_text(row, "source_role"),
        "source_id": _first_text(row, "source_id", "underlying_source_id"),
        "metric_family": _first_text(row, "metric_family", "slot_metric_family", "source_metric_family"),
        "metric_name": _first_text(row, "metric_name", "spec_name", "fact_label"),
        "canonical_metric_id": _first_text(row, "canonical_metric_id", "slot_id"),
        "value": _string_value(row.get("value") if "value" in row else row.get("source_value") or row.get("spec_value")),
        "unit": _first_text(row, "unit", "source_unit", "spec_unit"),
        "period": _first_text(row, "period", "period_end", "as_of_date", "filing_date", "report_date"),
        "fiscal_year": _first_text(row, "fiscal_year"),
        "as_of_date": _first_text(row, "as_of_date", "as_of_datetime", "generated_at"),
        "product_family": _first_text(row, "product_family"),
        "product_or_segment": _first_text(row, "product_or_segment", "profile_value", "spec_label"),
        "counterparty": _first_text(row, "counterparty"),
        "event_type": _first_text(row, "event_type", "event_label"),
        "object_type": _first_text(row, "object_type", "runtime_contract"),
        "claim_types_json": _json_text(row.get("claim_types")),
        "allowed_claims_json": _json_text(row.get("allowed_claims")),
        "forbidden_claims_json": _json_text(row.get("forbidden_claims") or row.get("forbidden_claim_types")),
        "claim_boundary": _first_text(row, "claim_boundary", "authority_boundary", "source_boundary"),
        "citation_url": _first_text(citation, "url", "source_url") or _first_text(row, "source_url", "url", "snapshot_url"),
        "citation_span": _first_text(row, "citation_span") or _first_text(citation, "span", "title"),
        "evidence_ref": _first_text(row, "evidence_ref", "evidence_id", "fact_id", "ledger_id"),
        "source_url": _first_text(row, "source_url", "url", "snapshot_url"),
        "raw_path": _first_text(row, "raw_path", "source_document_id"),
        "parser_status": _first_text(row, "parser_status", "adapter_parser_status"),
        "structured_fact_status": _first_text(row, "structured_fact_status", "availability_status"),
        "runtime_contract": _first_text(row, "runtime_contract", "schema_version"),
        "source_specific_parser": _first_text(row, "source_specific_parser", "source_specific_resolver"),
        "payload_json": json.dumps(payload, ensure_ascii=False, sort_keys=True),
    }


def _fact_domain(source_path: str, row: Mapping[str, Any]) -> str:
    text = f"{source_path} {_first_text(row, 'source_role')} {_first_text(row, 'source_id')} {_first_text(row, 'support_surface')}".lower()
    if "source_authority_data_mart" in text:
        return "source_authority"
    if "financial_statement" in text or "working_capital" in text:
        return "financial_statement_fact"
    if "product_operating" in text or "product_business_mix" in text or "product_kpi" in text:
        return "product_kpi_fact"
    if "industry_operating" in text:
        return "industry_operating_metric_fact"
    if "product_spec" in text or "product_catalog" in text or "product_profile" in text or "product_pages" in text:
        return "product_profile_or_spec_fact"
    if "customer" in text or "deployment" in text or "contract_award" in text:
        return "customer_deployment_or_order_signal"
    if "capital" in text or "ownership" in text or "offering" in text or "insider" in text or "governance" in text:
        return "capital_funding_ownership_fact"
    if "market_liquidity" in text:
        return "market_liquidity_signal"
    if "macro" in text or "fred" in text or "eia" in text or "fdic" in text:
        return "macro_industry_driver_signal"
    if "official_api" in text or "regulated" in text or "openfda" in text or "clinicaltrials" in text or "nhtsa" in text:
        return "regulated_or_official_api_signal"
    return "bounded_context_signal"


def _fact_type(source_path: str, row: Mapping[str, Any], fact_domain: str) -> str:
    for key in (
        "canonical_metric_id",
        "metric_family",
        "slot_metric_family",
        "signal_authority_type",
        "event_type",
        "object_type",
        "runtime_contract",
        "source_role",
    ):
        value = _first_text(row, key)
        if value:
            return value
    return fact_domain


def _support_surface(row: Mapping[str, Any], fact_domain: str) -> str:
    explicit = _first_text(row, "support_surface", "dimension")
    if explicit:
        return explicit
    return {
        "financial_statement_fact": "fundamental_company_disclosure",
        "product_kpi_fact": "product_and_technology",
        "industry_operating_metric_fact": "product_and_technology",
        "product_profile_or_spec_fact": "product_spec_and_capability",
        "customer_deployment_or_order_signal": "official_customer_deployment_signal",
        "capital_funding_ownership_fact": "capital_funding_ownership_market_liquidity",
        "market_liquidity_signal": "capital_funding_ownership_market_liquidity",
        "macro_industry_driver_signal": "macro_industry_driver",
        "regulated_or_official_api_signal": "regulated_product_context",
        "source_authority": "source_authority",
    }.get(fact_domain, "bounded_context")


def _authority_mode(row: Mapping[str, Any]) -> str:
    admission_tier = _first_text(row, "admission_tier", "availability_status")
    if row.get("can_enter_evidence_bundle") is False and (
        _first_text(row, "gap_class") or admission_tier in {"attempt_backed_public_boundary", "route_or_parser_debt"}
    ):
        return "planning_or_gap_only"
    explicit = _first_text(row, "authority_mode", "admission_tier")
    if explicit:
        if explicit in {"attempt_backed_public_boundary", "route_or_parser_debt"}:
            return "planning_or_gap_only"
        return explicit
    if row.get("exact_value_authority") is True or row.get("can_support_company_exact_fact") is True:
        return "exact_company_fact_authority"
    if row.get("runtime_ready_context") is True or row.get("bounded_structured_context") is True:
        return "bounded_thesis_driver_authority"
    parser_status = _first_text(row, "parser_status", "structured_fact_status").lower()
    if row.get("allowed_claims") and any(token in parser_status for token in ("pass", "ready", "verified")):
        return "bounded_thesis_driver_authority"
    if row.get("claim_types") and _first_text(row, "claim_boundary"):
        return "bounded_thesis_driver_authority"
    return "planning_or_gap_only"


def _can_enter_evidence_bundle(row: Mapping[str, Any], authority_mode: str) -> bool:
    if "can_enter_evidence_bundle" in row:
        return bool(row.get("can_enter_evidence_bundle"))
    if authority_mode == "planning_or_gap_only":
        return False
    if authority_mode == "bounded_thesis_driver_authority":
        return True
    return bool(
        row.get("runtime_ready_context")
        or row.get("exact_value_authority")
        or row.get("can_support_company_exact_fact")
        or row.get("bounded_structured_context")
    )


def _source_row_id(row: Mapping[str, Any], rel_path: str, ordinal: int) -> str:
    for key in ("evidence_id", "evidence_ref", "fact_id", "ledger_id", "snapshot_id", "row_id", "id"):
        value = _first_text(row, key)
        if value:
            return value
    return _stable_id("rd3_source_row", rel_path, ordinal, json.dumps(_compact_payload(row, max_items=12), ensure_ascii=False, sort_keys=True))


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, Mapping):
                yield dict(payload)


def _sqlite_value(value: Any) -> Any:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if value is None:
        return ""
    return str(value)


def _first_text(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        if isinstance(value, (dict, list, tuple, set)):
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _json_text(value: Any) -> str:
    if value is None or value == "":
        return "[]"
    if isinstance(value, str):
        return json.dumps([value], ensure_ascii=False)
    if isinstance(value, (list, tuple, set)):
        return json.dumps(list(value), ensure_ascii=False)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _compact_payload(value: Any, *, max_items: int = 80, max_text: int = 1200) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _compact_payload(item, max_items=max_items, max_text=max_text) for key, item in list(value.items())[:max_items]}
    if isinstance(value, list):
        return [_compact_payload(item, max_items=max_items, max_text=max_text) for item in value[:max_items]]
    if isinstance(value, str) and len(value) > max_text:
        return value[:max_text] + "...[truncated]"
    return value


def _stable_id(*parts: Any) -> str:
    raw = "\x1f".join(str(part or "") for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rel(path: Path | None, root: Path) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _markdown_counter_table(counter: Mapping[str, Any], key_label: str, value_label: str) -> str:
    lines = [f"| {key_label} | {value_label} |", "| --- | ---: |"]
    for key, value in sorted(counter.items(), key=lambda item: str(item[0])):
        lines.append(f"| `{key}` | `{value}` |")
    return "\n".join(lines)
