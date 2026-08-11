from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


AGENT_DATA_BRIEF_SCHEMA_VERSION = "finsight_agent_runtime_data_brief_v0_1"
ROLE_EVIDENCE_PACK_SCHEMA_VERSION = "finsight_role_evidence_pack_registry_v0_1"
AGENT_RUNTIME_CONSUMPTION_SUMMARY_SCHEMA_VERSION = "finsight_agent_runtime_consumption_contract_summary_v0_1"


ROLE_DOMAIN_POLICIES: dict[str, tuple[str, ...]] = {
    "fundamental_analyst": (
        "financial_statement_fact",
        "industry_operating_metric_fact",
    ),
    "product_technology_analyst": (
        "product_profile_or_spec_fact",
        "product_kpi_fact",
        "customer_deployment_or_order_signal",
        "regulated_or_official_api_signal",
    ),
    "industry_supply_chain_analyst": (
        "customer_deployment_or_order_signal",
        "macro_industry_driver_signal",
        "regulated_or_official_api_signal",
        "product_profile_or_spec_fact",
    ),
    "market_valuation_analyst": (
        "market_liquidity_signal",
        "capital_funding_ownership_fact",
        "financial_statement_fact",
    ),
    "capital_ownership_macro_analyst": (
        "capital_funding_ownership_fact",
        "macro_industry_driver_signal",
        "market_liquidity_signal",
        "financial_statement_fact",
    ),
    "risk_counterevidence_analyst": (
        "regulated_or_official_api_signal",
        "source_authority",
        "macro_industry_driver_signal",
        "capital_funding_ownership_fact",
        "financial_statement_fact",
    ),
}

DEFAULT_MAX_REFS_PER_PACK = 24


def build_agent_runtime_consumption_contract(
    repo_root: str | Path,
    *,
    generated_at: str | None = None,
    max_refs_per_pack: int = DEFAULT_MAX_REFS_PER_PACK,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    generated_at = generated_at or _utc_now()
    gold_rows = _read_jsonl(root / "data/manifests/gold_fact_signal_mart_rows_v0_1.jsonl")
    graph_edges = _read_jsonl(root / "data/manifests/research_graph_edges_v0_1.jsonl")
    retrieval_summary = _read_json(root / "data/manifests/retrieval_index_registry_summary_v0_1.json")
    parser_summary = _read_json(root / "data/manifests/parser_quality_summary_v0_1.json")
    raw_summary = _read_json(root / "data/manifests/raw_source_provenance_summary_v0_1.json")
    graph_summary = _read_json(root / "data/manifests/research_graph_summary_v0_1.json")

    rows_by_ticker = _group_gold_rows_by_ticker(gold_rows)
    graph_by_ticker = _group_graph_edges_by_ticker(graph_edges)
    briefs: list[dict[str, Any]] = []
    packs: list[dict[str, Any]] = []
    for ticker in sorted(rows_by_ticker):
        company_rows = rows_by_ticker[ticker]
        company_name = _first_nonempty(row.get("company_name") for row in company_rows)
        company_packs = []
        for role, domains in ROLE_DOMAIN_POLICIES.items():
            pack = _build_role_pack(
                ticker=ticker,
                company_name=company_name,
                role=role,
                domains=domains,
                rows=company_rows,
                generated_at=generated_at,
                max_refs=max_refs_per_pack,
            )
            packs.append(pack)
            company_packs.append(pack)
        briefs.append(
            _build_company_data_brief(
                ticker=ticker,
                company_name=company_name,
                rows=company_rows,
                graph_edges=graph_by_ticker.get(ticker, []),
                role_packs=company_packs,
                retrieval_summary=retrieval_summary,
                parser_summary=parser_summary,
                raw_summary=raw_summary,
                graph_summary=graph_summary,
                generated_at=generated_at,
            )
        )

    summary = build_agent_runtime_consumption_summary(briefs=briefs, packs=packs, generated_at=generated_at)
    return {"briefs": briefs, "packs": packs, "summary": summary}


def build_agent_runtime_consumption_summary(
    *,
    briefs: Sequence[Mapping[str, Any]],
    packs: Sequence[Mapping[str, Any]],
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or _utc_now()
    invalid_selected_gap_rows = []
    for pack in packs:
        for ref in pack.get("selected_evidence_refs") or []:
            if isinstance(ref, Mapping) and str(ref.get("authority_mode") or "") == "planning_or_gap_only":
                invalid_selected_gap_rows.append({"ticker": pack.get("ticker"), "role": pack.get("role"), "ref": ref})
    expected_pack_count = len(briefs) * len(ROLE_DOMAIN_POLICIES)
    companies_without_any_pack = [
        str(brief.get("ticker") or "")
        for brief in briefs
        if not any((pack.get("ticker") == brief.get("ticker")) and pack.get("selected_count") for pack in packs)
    ]
    role_gap_counts = Counter(str(pack.get("role") or "") for pack in packs if pack.get("status") == "gap")
    status = "pass" if not invalid_selected_gap_rows and len(packs) == expected_pack_count and not companies_without_any_pack else "action_required"
    return {
        "schema_version": AGENT_RUNTIME_CONSUMPTION_SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": status,
        "company_brief_count": len(briefs),
        "role_evidence_pack_count": len(packs),
        "expected_role_evidence_pack_count": expected_pack_count,
        "role_count": len(ROLE_DOMAIN_POLICIES),
        "company_without_any_evidence_pack_count": len(companies_without_any_pack),
        "companies_without_any_evidence_pack_sample": companies_without_any_pack[:30],
        "pack_status_counts": dict(Counter(str(pack.get("status") or "") for pack in packs)),
        "pack_role_gap_counts": dict(role_gap_counts),
        "selected_ref_count": sum(int(pack.get("selected_count") or 0) for pack in packs),
        "gap_ref_count": sum(int(pack.get("gap_count") or 0) for pack in packs),
        "invalid_selected_gap_row_count": len(invalid_selected_gap_rows),
        "invalid_selected_gap_row_samples": invalid_selected_gap_rows[:20],
        "memo_writer_input_contract": {
            "allowed_inputs": [
                "JudgmentState",
                "MemoLogicPlan",
                "verified ClaimCards",
                "bounded gaps",
                "role_evidence_pack_refs",
            ],
            "forbidden_inputs": [
                "raw retrieval rows",
                "tool observations",
                "unverified web snippets",
                "planning_or_gap_only rows as evidence",
            ],
        },
        "policy": "Research Lead consumes compact data briefs; specialists consume role-specific evidence packs; Memo Writer consumes verified judgment inputs only.",
    }


def render_agent_runtime_consumption_report(summary: Mapping[str, Any], *, output_paths: Mapping[str, str]) -> str:
    lines = [
        "# RD6 Agent Runtime Consumption Contract",
        "",
        f"- Generated at: `{summary.get('generated_at', '')}`",
        f"- Status: `{summary.get('status', '')}`",
        f"- Company briefs: `{summary.get('company_brief_count', 0)}`",
        f"- Role evidence packs: `{summary.get('role_evidence_pack_count', 0)}`",
        f"- Selected evidence refs: `{summary.get('selected_ref_count', 0)}`",
        f"- Gap refs: `{summary.get('gap_ref_count', 0)}`",
        f"- Invalid selected gap rows: `{summary.get('invalid_selected_gap_row_count', 0)}`",
        "",
        "## Outputs",
        "",
    ]
    for key, path in output_paths.items():
        lines.append(f"- `{key}`: `{path}`")
    lines.extend(
        [
            "",
            "## Pack Status Counts",
            "",
            _markdown_counter_table(summary.get("pack_status_counts") or {}, "Status", "Packs"),
            "",
            "## Role Gap Counts",
            "",
            _markdown_counter_table(summary.get("pack_role_gap_counts") or {}, "Role", "Gap packs"),
            "",
            "## Boundary",
            "",
            "- Research Lead 先读 compact data brief，再生成 retrieval / repair plan。",
            "- Specialist 只消费 role-specific EvidencePack 引用，不直接扫散装 JSONL。",
            "- Memo Writer 不接触 raw retrieval / tool observations，只消费 JudgmentState、MemoLogicPlan、verified ClaimCards 和 bounded gaps。",
            "- `planning_or_gap_only` rows 不得进入 selected evidence refs；只能进入 gap summary。",
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


def write_agent_runtime_consumption_sqlite(
    path: str | Path,
    *,
    briefs: Sequence[Mapping[str, Any]],
    packs: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(target)) as conn:
        conn.execute("drop table if exists agent_data_briefs")
        conn.execute("drop table if exists role_evidence_packs")
        conn.execute(
            """
            create table agent_data_briefs (
                data_brief_id text primary key,
                schema_version text not null,
                generated_at text not null,
                ticker text not null,
                company_name text not null,
                exact_fact_count integer not null,
                bounded_signal_count integer not null,
                planning_gap_count integer not null,
                fact_domain_counts_json text not null,
                authority_mode_counts_json text not null,
                source_layer_counts_json text not null,
                graph_edge_counts_json text not null,
                role_pack_status_counts_json text not null,
                retrieval_registry_digest text not null,
                parser_quality_digest text not null,
                raw_provenance_digest text not null,
                graph_store_digest text not null
            )
            """
        )
        conn.execute(
            """
            create table role_evidence_packs (
                role_pack_id text primary key,
                schema_version text not null,
                generated_at text not null,
                ticker text not null,
                company_name text not null,
                role text not null,
                status text not null,
                selected_count integer not null,
                gap_count integer not null,
                selected_evidence_refs_json text not null,
                gap_refs_json text not null,
                domain_policy_json text not null
            )
            """
        )
        conn.executemany(
            """
            insert into agent_data_briefs values (
                :data_brief_id, :schema_version, :generated_at, :ticker, :company_name,
                :exact_fact_count, :bounded_signal_count, :planning_gap_count,
                :fact_domain_counts_json, :authority_mode_counts_json, :source_layer_counts_json,
                :graph_edge_counts_json, :role_pack_status_counts_json, :retrieval_registry_digest,
                :parser_quality_digest, :raw_provenance_digest, :graph_store_digest
            )
            """,
            [dict(row) for row in briefs],
        )
        conn.executemany(
            """
            insert into role_evidence_packs values (
                :role_pack_id, :schema_version, :generated_at, :ticker, :company_name, :role,
                :status, :selected_count, :gap_count, :selected_evidence_refs_json, :gap_refs_json,
                :domain_policy_json
            )
            """,
            [dict(row) for row in packs],
        )
        conn.execute("create index idx_agent_data_briefs_ticker on agent_data_briefs(ticker)")
        conn.execute("create index idx_role_evidence_packs_ticker_role on role_evidence_packs(ticker, role)")
        conn.execute("create index idx_role_evidence_packs_status on role_evidence_packs(status)")
        brief_count = conn.execute("select count(*) from agent_data_briefs").fetchone()[0]
        pack_count = conn.execute("select count(*) from role_evidence_packs").fetchone()[0]
    return {"brief_count": int(brief_count), "pack_count": int(pack_count)}


def _build_company_data_brief(
    *,
    ticker: str,
    company_name: str,
    rows: Sequence[Mapping[str, Any]],
    graph_edges: Sequence[Mapping[str, Any]],
    role_packs: Sequence[Mapping[str, Any]],
    retrieval_summary: Mapping[str, Any],
    parser_summary: Mapping[str, Any],
    raw_summary: Mapping[str, Any],
    graph_summary: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    authority_counts = Counter(str(row.get("authority_mode") or "") for row in rows)
    fact_domain_counts = Counter(str(row.get("fact_domain") or "") for row in rows)
    source_layer_counts = Counter(str(row.get("source_layer") or "") for row in rows)
    graph_edge_counts = Counter(str(edge.get("edge_type") or "") for edge in graph_edges)
    role_pack_status_counts = Counter(str(pack.get("status") or "") for pack in role_packs)
    exact_fact_count = int(authority_counts.get("exact_company_fact_authority", 0))
    bounded_signal_count = int(authority_counts.get("bounded_thesis_driver_authority", 0))
    planning_gap_count = int(authority_counts.get("planning_or_gap_only", 0))
    return {
        "schema_version": AGENT_DATA_BRIEF_SCHEMA_VERSION,
        "generated_at": generated_at,
        "data_brief_id": f"data_brief:{ticker}:{_digest({'domains': fact_domain_counts, 'authority': authority_counts})[:16]}",
        "ticker": ticker,
        "company_name": company_name,
        "exact_fact_count": exact_fact_count,
        "bounded_signal_count": bounded_signal_count,
        "planning_gap_count": planning_gap_count,
        "fact_domain_counts_json": json.dumps(dict(fact_domain_counts), ensure_ascii=False, sort_keys=True),
        "authority_mode_counts_json": json.dumps(dict(authority_counts), ensure_ascii=False, sort_keys=True),
        "source_layer_counts_json": json.dumps(dict(source_layer_counts), ensure_ascii=False, sort_keys=True),
        "graph_edge_counts_json": json.dumps(dict(graph_edge_counts), ensure_ascii=False, sort_keys=True),
        "role_pack_status_counts_json": json.dumps(dict(role_pack_status_counts), ensure_ascii=False, sort_keys=True),
        "retrieval_registry_digest": _digest(retrieval_summary),
        "parser_quality_digest": _digest(parser_summary),
        "raw_provenance_digest": _digest(raw_summary),
        "graph_store_digest": _digest(graph_summary),
    }


def _build_role_pack(
    *,
    ticker: str,
    company_name: str,
    role: str,
    domains: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
    generated_at: str,
    max_refs: int,
) -> dict[str, Any]:
    domain_set = {str(item) for item in domains}
    candidates = [dict(row) for row in rows if str(row.get("fact_domain") or "") in domain_set]
    selected_candidates = [
        row
        for row in candidates
        if bool(row.get("can_enter_evidence_bundle")) and str(row.get("authority_mode") or "") != "planning_or_gap_only"
    ]
    selected_candidates.sort(key=_role_pack_sort_key)
    selected_refs = [_compact_evidence_ref(row) for row in selected_candidates[:max_refs]]
    gap_refs = [_compact_gap_ref(row) for row in candidates if str(row.get("authority_mode") or "") == "planning_or_gap_only"]
    return {
        "schema_version": ROLE_EVIDENCE_PACK_SCHEMA_VERSION,
        "generated_at": generated_at,
        "role_pack_id": f"role_pack:{ticker}:{role}:{_digest({'domains': domains, 'selected': selected_refs})[:16]}",
        "ticker": ticker,
        "company_name": company_name,
        "role": role,
        "status": "pass" if selected_refs else "gap",
        "selected_count": len(selected_refs),
        "gap_count": len(gap_refs),
        "selected_evidence_refs_json": json.dumps(selected_refs, ensure_ascii=False, sort_keys=True),
        "gap_refs_json": json.dumps(gap_refs, ensure_ascii=False, sort_keys=True),
        "domain_policy_json": json.dumps(list(domains), ensure_ascii=False, sort_keys=True),
    }


def _compact_evidence_ref(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "gold_row_id": str(row.get("gold_row_id") or ""),
        "source_row_id": str(row.get("source_row_id") or ""),
        "fact_domain": str(row.get("fact_domain") or ""),
        "fact_type": str(row.get("fact_type") or ""),
        "authority_mode": str(row.get("authority_mode") or ""),
        "support_surface": str(row.get("support_surface") or ""),
        "source_layer": str(row.get("source_layer") or ""),
        "source_role": str(row.get("source_role") or ""),
        "product_family": str(row.get("product_family") or ""),
        "product_or_segment": str(row.get("product_or_segment") or ""),
        "citation_url": str(row.get("citation_url") or ""),
        "claim_boundary": str(row.get("claim_boundary") or ""),
    }


def _compact_gap_ref(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "gold_row_id": str(row.get("gold_row_id") or ""),
        "source_row_id": str(row.get("source_row_id") or ""),
        "fact_domain": str(row.get("fact_domain") or ""),
        "source_role": str(row.get("source_role") or ""),
        "claim_boundary": str(row.get("claim_boundary") or ""),
    }


def _role_pack_sort_key(row: Mapping[str, Any]) -> tuple[int, str, str]:
    authority_rank = {
        "exact_company_fact_authority": 0,
        "bounded_thesis_driver_authority": 1,
    }.get(str(row.get("authority_mode") or ""), 5)
    return (
        authority_rank,
        str(row.get("fact_domain") or ""),
        str(row.get("gold_row_id") or row.get("source_row_id") or ""),
    )


def _group_gold_rows_by_ticker(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        grouped[ticker].append(dict(row))
    return grouped


def _group_graph_edges_by_ticker(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        from_node = str(row.get("from_node_id") or "")
        if from_node.startswith("company:"):
            grouped[from_node.split(":", 1)[1].upper()].append(dict(row))
    return grouped


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, Mapping):
                rows.append(dict(payload))
    return rows


def _first_nonempty(values: Iterable[Any]) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _digest(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:24]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _markdown_counter_table(counter: Mapping[str, Any], key_label: str, value_label: str) -> str:
    lines = [f"| {key_label} | {value_label} |", "| --- | ---: |"]
    for key, value in sorted(counter.items(), key=lambda item: str(item[0])):
        lines.append(f"| `{key}` | `{value}` |")
    return "\n".join(lines)
