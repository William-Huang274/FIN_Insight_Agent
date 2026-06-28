from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


RESEARCH_GRAPH_NODE_SCHEMA_VERSION = "finsight_research_graph_node_v0_1"
RESEARCH_GRAPH_EDGE_SCHEMA_VERSION = "finsight_research_graph_edge_v0_1"
RESEARCH_GRAPH_EVIDENCE_SUPPORT_SCHEMA_VERSION = "finsight_research_graph_evidence_support_v0_1"
RESEARCH_GRAPH_SUMMARY_SCHEMA_VERSION = "finsight_research_graph_summary_v0_1"
RESEARCH_GRAPH_SQLITE_SCHEMA_VERSION = "finsight_research_graph_sqlite_v0_1"


DEFAULT_PRODUCT_GRAPH_NODES = "data/manifests/product_relationship_graph_nodes_v0_1.jsonl"
DEFAULT_PRODUCT_GRAPH_EDGES = "data/manifests/product_relationship_graph_edges_v0_1.jsonl"
DEFAULT_GOLD_MART_ROWS = "data/manifests/gold_fact_signal_mart_rows_v0_1.jsonl"

STRUCTURAL_PRODUCT_GRAPH_EDGE_TYPES: set[str] = {
    "HAS_PRODUCT_SLOT",
    "FAMILY_HAS_PRODUCT_SLOT",
}


def build_research_graph_store(
    repo_root: str | Path,
    *,
    generated_at: str | None = None,
    product_graph_nodes_path: str = DEFAULT_PRODUCT_GRAPH_NODES,
    product_graph_edges_path: str = DEFAULT_PRODUCT_GRAPH_EDGES,
    gold_mart_rows_path: str = DEFAULT_GOLD_MART_ROWS,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    generated_at = generated_at or _utc_now()
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    support_rows: list[dict[str, Any]] = []
    gold_support_map: dict[str, dict[str, Any]] = {}

    product_nodes = root / product_graph_nodes_path
    if product_nodes.exists():
        for row in _read_jsonl(product_nodes):
            node = _node_from_product_graph(row, generated_at=generated_at)
            nodes.setdefault(node["graph_node_id"], node)

    gold_path = root / gold_mart_rows_path
    if gold_path.exists():
        for row in _read_jsonl(gold_path):
            gold_support_map[row.get("gold_row_id", "")] = row
            evidence_ref = str(row.get("evidence_ref") or "")
            if evidence_ref:
                gold_support_map[evidence_ref] = row
            source_row_id = str(row.get("source_row_id") or "")
            if source_row_id:
                gold_support_map[source_row_id] = row
            for node in _nodes_from_gold_row(row, generated_at=generated_at):
                nodes.setdefault(node["graph_node_id"], node)
            edge = _edge_from_gold_row(row, generated_at=generated_at)
            edges.setdefault(edge["graph_edge_id"], edge)
            support_rows.append(_support_from_gold_row(edge["graph_edge_id"], row, generated_at=generated_at))

    product_edges = root / product_graph_edges_path
    if product_edges.exists():
        for row in _read_jsonl(product_edges):
            edge = _edge_from_product_graph(row, generated_at=generated_at)
            edges.setdefault(edge["graph_edge_id"], edge)
            for support in _supports_from_product_graph_edge(edge, row, gold_support_map, generated_at=generated_at):
                support_rows.append(support)

    summary = build_research_graph_summary(
        nodes=list(nodes.values()),
        edges=list(edges.values()),
        support_rows=support_rows,
        generated_at=generated_at,
    )
    return {
        "nodes": sorted(nodes.values(), key=lambda row: row["graph_node_id"]),
        "edges": sorted(edges.values(), key=lambda row: row["graph_edge_id"]),
        "support_rows": sorted(support_rows, key=lambda row: row["support_id"]),
        "summary": summary,
    }


def build_research_graph_summary(
    *,
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    support_rows: Sequence[Mapping[str, Any]],
    generated_at: str | None = None,
    sqlite_path: str = "",
    sqlite_node_count: int = 0,
    sqlite_edge_count: int = 0,
    sqlite_support_count: int = 0,
) -> dict[str, Any]:
    generated_at = generated_at or _utc_now()
    node_ids = {str(row.get("graph_node_id") or "") for row in nodes}
    dangling_edges = [
        row for row in edges if str(row.get("from_node_id") or "") not in node_ids or str(row.get("to_node_id") or "") not in node_ids
    ]
    support_counts_by_edge = Counter(str(row.get("graph_edge_id") or "") for row in support_rows)
    unsupported_edges = [row for row in edges if not support_counts_by_edge.get(str(row.get("graph_edge_id") or ""))]
    status = "pass"
    if dangling_edges or unsupported_edges:
        status = "action_required"
    if sqlite_node_count and sqlite_node_count != len(nodes):
        status = "action_required"
    if sqlite_edge_count and sqlite_edge_count != len(edges):
        status = "action_required"
    if sqlite_support_count and sqlite_support_count != len(support_rows):
        status = "action_required"
    return {
        "schema_version": RESEARCH_GRAPH_SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": status,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "evidence_support_row_count": len(support_rows),
        "dangling_edge_count": len(dangling_edges),
        "unsupported_edge_count": len(unsupported_edges),
        "sqlite_path": sqlite_path,
        "sqlite_node_count": sqlite_node_count,
        "sqlite_edge_count": sqlite_edge_count,
        "sqlite_support_count": sqlite_support_count,
        "node_type_counts": dict(Counter(str(row.get("node_type") or "") for row in nodes)),
        "edge_type_counts": dict(Counter(str(row.get("edge_type") or "") for row in edges).most_common(40)),
        "edge_authority_mode_counts": dict(Counter(str(row.get("authority_mode") or "") for row in edges)),
        "support_status_counts": dict(Counter(str(row.get("support_status") or "") for row in support_rows)),
        "unsupported_edge_samples": [_compact_edge(row) for row in unsupported_edges[:20]],
        "dangling_edge_samples": [_compact_edge(row) for row in dangling_edges[:20]],
        "policy": (
            "RD4 Research Graph Store merges product relationship graph edges with RD3 Gold Mart fact/signal edges. "
            "Every edge must have an evidence-support row. Source-evidence-only support rows remain bounded and do not "
            "create new authority."
        ),
    }


def write_research_graph_sqlite(
    sqlite_path: str | Path,
    *,
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    support_rows: Sequence[Mapping[str, Any]],
    replace: bool = True,
) -> dict[str, int]:
    target = Path(sqlite_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(target)) as conn:
        conn.execute(
            """
            create table if not exists research_graph_nodes (
                graph_node_id text primary key,
                schema_version text not null,
                generated_at text not null,
                node_type text not null,
                label text,
                ticker text,
                payload_json text,
                source text
            )
            """
        )
        conn.execute(
            """
            create table if not exists research_graph_edges (
                graph_edge_id text primary key,
                schema_version text not null,
                generated_at text not null,
                from_node_id text not null,
                to_node_id text not null,
                edge_type text not null,
                authority_mode text,
                can_enter_evidence_bundle integer,
                confidence real,
                source_layer text,
                source_role text,
                claim_boundary text,
                forbidden_claims_json text,
                evidence_refs_json text,
                gold_row_ids_json text,
                source_edge_id text
            )
            """
        )
        conn.execute(
            """
            create table if not exists research_graph_evidence_support (
                support_id text primary key,
                schema_version text not null,
                generated_at text not null,
                graph_edge_id text not null,
                gold_row_id text,
                source_row_id text,
                source_rowset_path text,
                evidence_ref text,
                citation_url text,
                citation_span text,
                authority_mode text,
                can_enter_evidence_bundle integer,
                support_status text
            )
            """
        )
        conn.execute("create table if not exists research_graph_metadata(key text primary key, value text not null)")
        if replace:
            conn.execute("delete from research_graph_nodes")
            conn.execute("delete from research_graph_edges")
            conn.execute("delete from research_graph_evidence_support")
        conn.executemany(
            """
            insert or replace into research_graph_nodes (
                graph_node_id, schema_version, generated_at, node_type, label, ticker, payload_json, source
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["graph_node_id"],
                    row["schema_version"],
                    row["generated_at"],
                    row["node_type"],
                    row.get("label", ""),
                    row.get("ticker", ""),
                    row.get("payload_json", "{}"),
                    row.get("source", ""),
                )
                for row in nodes
            ],
        )
        conn.executemany(
            """
            insert or replace into research_graph_edges (
                graph_edge_id, schema_version, generated_at, from_node_id, to_node_id, edge_type, authority_mode,
                can_enter_evidence_bundle, confidence, source_layer, source_role, claim_boundary,
                forbidden_claims_json, evidence_refs_json, gold_row_ids_json, source_edge_id
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["graph_edge_id"],
                    row["schema_version"],
                    row["generated_at"],
                    row["from_node_id"],
                    row["to_node_id"],
                    row["edge_type"],
                    row.get("authority_mode", ""),
                    1 if row.get("can_enter_evidence_bundle") else 0,
                    float(row.get("confidence") or 0.0),
                    row.get("source_layer", ""),
                    row.get("source_role", ""),
                    row.get("claim_boundary", ""),
                    row.get("forbidden_claims_json", "[]"),
                    row.get("evidence_refs_json", "[]"),
                    row.get("gold_row_ids_json", "[]"),
                    row.get("source_edge_id", ""),
                )
                for row in edges
            ],
        )
        conn.executemany(
            """
            insert or replace into research_graph_evidence_support (
                support_id, schema_version, generated_at, graph_edge_id, gold_row_id, source_row_id,
                source_rowset_path, evidence_ref, citation_url, citation_span, authority_mode,
                can_enter_evidence_bundle, support_status
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["support_id"],
                    row["schema_version"],
                    row["generated_at"],
                    row["graph_edge_id"],
                    row.get("gold_row_id", ""),
                    row.get("source_row_id", ""),
                    row.get("source_rowset_path", ""),
                    row.get("evidence_ref", ""),
                    row.get("citation_url", ""),
                    row.get("citation_span", ""),
                    row.get("authority_mode", ""),
                    1 if row.get("can_enter_evidence_bundle") else 0,
                    row.get("support_status", ""),
                )
                for row in support_rows
            ],
        )
        for table, column in (
            ("research_graph_nodes", "node_type"),
            ("research_graph_nodes", "ticker"),
            ("research_graph_edges", "edge_type"),
            ("research_graph_edges", "source_role"),
            ("research_graph_edges", "authority_mode"),
            ("research_graph_evidence_support", "graph_edge_id"),
            ("research_graph_evidence_support", "gold_row_id"),
        ):
            conn.execute(f"create index if not exists idx_{table}_{column} on {table}({column})")
        conn.execute(
            "insert or replace into research_graph_metadata(key, value) values (?, ?)",
            ("schema_version", RESEARCH_GRAPH_SQLITE_SCHEMA_VERSION),
        )
        conn.commit()
        return {
            "node_count": int(conn.execute("select count(*) from research_graph_nodes").fetchone()[0]),
            "edge_count": int(conn.execute("select count(*) from research_graph_edges").fetchone()[0]),
            "support_count": int(conn.execute("select count(*) from research_graph_evidence_support").fetchone()[0]),
        }


def render_research_graph_report(summary: Mapping[str, Any], *, output_paths: Mapping[str, str]) -> str:
    lines = [
        "# RD4 Research Graph Store v0.1",
        "",
        f"- Generated at: `{summary.get('generated_at', '')}`",
        f"- Status: `{summary.get('status', '')}`",
        f"- Nodes: `{summary.get('node_count', 0)}`",
        f"- Edges: `{summary.get('edge_count', 0)}`",
        f"- Evidence support rows: `{summary.get('evidence_support_row_count', 0)}`",
        f"- Dangling edges: `{summary.get('dangling_edge_count', 0)}`",
        f"- Unsupported edges: `{summary.get('unsupported_edge_count', 0)}`",
        "",
        "## Outputs",
        "",
    ]
    for key, path in output_paths.items():
        lines.append(f"- `{key}`: `{path}`")
    lines.extend(
        [
            "",
            "## Node Types",
            "",
            _markdown_counter_table(summary.get("node_type_counts") or {}, "Node type", "Count"),
            "",
            "## Edge Authority",
            "",
            _markdown_counter_table(summary.get("edge_authority_mode_counts") or {}, "Authority", "Edges"),
            "",
            "## Support Status",
            "",
            _markdown_counter_table(summary.get("support_status_counts") or {}, "Support", "Rows"),
            "",
            "## Boundary",
            "",
            "- RD4 不新增事实提权；图边 authority 继承 RD3 Gold Mart 或原 ProductRelationshipGraph 边界。",
            "- `source_evidence_ref_only` 表示原图边已有 evidence_ref 但未映射到 Gold Mart row，仍保持原 claim boundary。",
            "- Memo/ClaimCard 不能只因为图边存在就推断销量、ASP、份额、订单值、backlog 或实时资金流。",
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


def _node_from_product_graph(row: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": RESEARCH_GRAPH_NODE_SCHEMA_VERSION,
        "generated_at": generated_at,
        "graph_node_id": str(row.get("node_id") or ""),
        "node_type": str(row.get("node_type") or "unknown"),
        "label": str(row.get("label") or ""),
        "ticker": _ticker_from_node_id(str(row.get("node_id") or "")),
        "payload_json": json.dumps(row.get("payload") or {}, ensure_ascii=False, sort_keys=True),
        "source": "product_relationship_graph",
    }


def _nodes_from_gold_row(row: Mapping[str, Any], *, generated_at: str) -> list[dict[str, Any]]:
    ticker = str(row.get("ticker") or "").strip()
    nodes: list[dict[str, Any]] = []
    if ticker:
        nodes.append(_node(f"company:{ticker}", "company", str(row.get("company_name") or ticker), ticker=ticker, generated_at=generated_at, source="gold_fact_signal_mart"))
    else:
        nodes.append(
            _node(
                _unknown_issuer_node_id(row),
                "unknown_issuer",
                "Unknown issuer",
                generated_at=generated_at,
                source="gold_fact_signal_mart",
                payload={"gold_row_id": row.get("gold_row_id", ""), "fact_domain": row.get("fact_domain", "")},
            )
        )
    product_label = str(row.get("product_or_segment") or "").strip()
    product_family = str(row.get("product_family") or "").strip()
    if product_label:
        nodes.append(
            _node(
                _stable_node_id("product_context", ticker, product_family, product_label),
                "product_context",
                product_label,
                ticker=ticker,
                generated_at=generated_at,
                source="gold_fact_signal_mart",
                payload={"product_family": product_family},
            )
        )
    counterparty = str(row.get("counterparty") or "").strip()
    if counterparty:
        nodes.append(_node(_stable_node_id("counterparty", counterparty), "counterparty", counterparty, generated_at=generated_at, source="gold_fact_signal_mart"))
    fact_node_id = _fact_node_id(row)
    nodes.append(
        _node(
            fact_node_id,
            "fact_or_signal_type",
            str(row.get("fact_type") or row.get("fact_domain") or ""),
            ticker=ticker,
            generated_at=generated_at,
            source="gold_fact_signal_mart",
            payload={"fact_domain": row.get("fact_domain", ""), "support_surface": row.get("support_surface", "")},
        )
    )
    return nodes


def _edge_from_gold_row(row: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").strip()
    from_node_id = f"company:{ticker}" if ticker else _unknown_issuer_node_id(row)
    to_node_id = _gold_target_node_id(row)
    edge_type = _edge_type_for_gold_row(row)
    evidence_ref = str(row.get("evidence_ref") or row.get("source_row_id") or row.get("gold_row_id") or "")
    return {
        "schema_version": RESEARCH_GRAPH_EDGE_SCHEMA_VERSION,
        "generated_at": generated_at,
        "graph_edge_id": _stable_id("rd4_gold_edge", row.get("gold_row_id"), from_node_id, to_node_id, edge_type),
        "from_node_id": from_node_id,
        "to_node_id": to_node_id,
        "edge_type": edge_type,
        "authority_mode": str(row.get("authority_mode") or ""),
        "can_enter_evidence_bundle": bool(row.get("can_enter_evidence_bundle")),
        "confidence": 1.0 if row.get("can_enter_evidence_bundle") else 0.0,
        "source_layer": str(row.get("source_layer") or ""),
        "source_role": str(row.get("source_role") or ""),
        "claim_boundary": str(row.get("claim_boundary") or ""),
        "forbidden_claims_json": str(row.get("forbidden_claims_json") or "[]"),
        "evidence_refs_json": json.dumps([evidence_ref] if evidence_ref else [], ensure_ascii=False),
        "gold_row_ids_json": json.dumps([row.get("gold_row_id")] if row.get("gold_row_id") else [], ensure_ascii=False),
        "source_edge_id": "",
    }


def _edge_from_product_graph(row: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    evidence_refs = [str(item) for item in row.get("evidence_refs") or [] if str(item).strip()]
    relationship_type = str(row.get("relationship_type") or "RELATIONSHIP_CONTEXT")
    lacks_direct_evidence = not evidence_refs and relationship_type not in STRUCTURAL_PRODUCT_GRAPH_EDGE_TYPES
    return {
        "schema_version": RESEARCH_GRAPH_EDGE_SCHEMA_VERSION,
        "generated_at": generated_at,
        "graph_edge_id": str(row.get("edge_id") or _stable_id("rd4_product_edge", row)),
        "from_node_id": str(row.get("from_node_id") or ""),
        "to_node_id": str(row.get("to_node_id") or ""),
        "edge_type": relationship_type,
        "authority_mode": "planning_or_gap_only" if lacks_direct_evidence else "bounded_thesis_driver_authority",
        "can_enter_evidence_bundle": False if lacks_direct_evidence else True,
        "confidence": 0.0 if lacks_direct_evidence else float(row.get("confidence") or 0.0),
        "source_layer": str(row.get("source_layer") or ""),
        "source_role": "product_relationship_graph",
        "claim_boundary": str(row.get("claim_boundary") or ""),
        "forbidden_claims_json": json.dumps(row.get("forbidden_claims") or [], ensure_ascii=False),
        "evidence_refs_json": json.dumps(evidence_refs, ensure_ascii=False),
        "gold_row_ids_json": "[]",
        "source_edge_id": str(row.get("edge_id") or ""),
    }


def _support_from_gold_row(graph_edge_id: str, row: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": RESEARCH_GRAPH_EVIDENCE_SUPPORT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "support_id": _stable_id("rd4_support", graph_edge_id, row.get("gold_row_id")),
        "graph_edge_id": graph_edge_id,
        "gold_row_id": str(row.get("gold_row_id") or ""),
        "source_row_id": str(row.get("source_row_id") or ""),
        "source_rowset_path": str(row.get("source_rowset_path") or ""),
        "evidence_ref": str(row.get("evidence_ref") or ""),
        "citation_url": str(row.get("citation_url") or ""),
        "citation_span": str(row.get("citation_span") or ""),
        "authority_mode": str(row.get("authority_mode") or ""),
        "can_enter_evidence_bundle": bool(row.get("can_enter_evidence_bundle")),
        "support_status": "gold_mart_row",
    }


def _supports_from_product_graph_edge(
    edge: Mapping[str, Any],
    row: Mapping[str, Any],
    gold_support_map: Mapping[str, Mapping[str, Any]],
    *,
    generated_at: str,
) -> list[dict[str, Any]]:
    evidence_refs = [str(item) for item in row.get("evidence_refs") or [] if str(item).strip()]
    if not evidence_refs:
        edge_type = str(edge.get("edge_type") or "")
        support_status = (
            "structural_graph_topology_no_external_ref"
            if edge_type in STRUCTURAL_PRODUCT_GRAPH_EDGE_TYPES
            else "modelled_relationship_without_direct_evidence_ref"
        )
        return [
            {
                "schema_version": RESEARCH_GRAPH_EVIDENCE_SUPPORT_SCHEMA_VERSION,
                "generated_at": generated_at,
                "support_id": _stable_id("rd4_support", edge.get("graph_edge_id"), "missing_evidence_ref"),
                "graph_edge_id": str(edge.get("graph_edge_id") or ""),
                "gold_row_id": "",
                "source_row_id": "",
                "source_rowset_path": "",
                "evidence_ref": "",
                "citation_url": "",
                "citation_span": "",
                "authority_mode": str(edge.get("authority_mode") or ""),
                "can_enter_evidence_bundle": bool(edge.get("can_enter_evidence_bundle")),
                "support_status": support_status,
            }
        ]
    supports: list[dict[str, Any]] = []
    for evidence_ref in evidence_refs:
        gold = gold_support_map.get(evidence_ref)
        if gold:
            supports.append(_support_from_gold_row(str(edge.get("graph_edge_id") or ""), gold, generated_at=generated_at))
        else:
            supports.append(
                {
                    "schema_version": RESEARCH_GRAPH_EVIDENCE_SUPPORT_SCHEMA_VERSION,
                    "generated_at": generated_at,
                    "support_id": _stable_id("rd4_support", edge.get("graph_edge_id"), evidence_ref),
                    "graph_edge_id": str(edge.get("graph_edge_id") or ""),
                    "gold_row_id": "",
                    "source_row_id": evidence_ref,
                    "source_rowset_path": "",
                    "evidence_ref": evidence_ref,
                    "citation_url": "",
                    "citation_span": "",
                    "authority_mode": str(edge.get("authority_mode") or ""),
                    "can_enter_evidence_bundle": bool(edge.get("can_enter_evidence_bundle")),
                    "support_status": "source_evidence_ref_only",
                }
            )
    return supports


def _node(
    node_id: str,
    node_type: str,
    label: str,
    *,
    generated_at: str,
    ticker: str = "",
    source: str,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": RESEARCH_GRAPH_NODE_SCHEMA_VERSION,
        "generated_at": generated_at,
        "graph_node_id": node_id,
        "node_type": node_type,
        "label": label,
        "ticker": ticker,
        "payload_json": json.dumps(dict(payload or {}), ensure_ascii=False, sort_keys=True),
        "source": source,
    }


def _gold_target_node_id(row: Mapping[str, Any]) -> str:
    counterparty = str(row.get("counterparty") or "").strip()
    if counterparty:
        return _stable_node_id("counterparty", counterparty)
    product_label = str(row.get("product_or_segment") or "").strip()
    if product_label:
        return _stable_node_id("product_context", row.get("ticker", ""), row.get("product_family", ""), product_label)
    return _fact_node_id(row)


def _fact_node_id(row: Mapping[str, Any]) -> str:
    return _stable_node_id("fact_type", row.get("fact_domain", ""), row.get("fact_type", ""), row.get("metric_family", ""), row.get("metric_name", ""))


def _unknown_issuer_node_id(row: Mapping[str, Any]) -> str:
    return _stable_node_id("unknown_issuer", row.get("gold_row_id", ""))


def _edge_type_for_gold_row(row: Mapping[str, Any]) -> str:
    domain = str(row.get("fact_domain") or "")
    return {
        "financial_statement_fact": "HAS_FINANCIAL_STATEMENT_FACT",
        "product_kpi_fact": "HAS_PRODUCT_KPI_FACT",
        "product_profile_or_spec_fact": "HAS_PRODUCT_PROFILE_OR_SPEC",
        "industry_operating_metric_fact": "HAS_INDUSTRY_OPERATING_METRIC",
        "customer_deployment_or_order_signal": "HAS_CUSTOMER_DEPLOYMENT_OR_ORDER_SIGNAL",
        "capital_funding_ownership_fact": "HAS_CAPITAL_FUNDING_OWNERSHIP_FACT",
        "market_liquidity_signal": "HAS_MARKET_LIQUIDITY_SIGNAL",
        "macro_industry_driver_signal": "HAS_MACRO_INDUSTRY_DRIVER_SIGNAL",
        "regulated_or_official_api_signal": "HAS_REGULATED_OR_OFFICIAL_API_SIGNAL",
        "source_authority": "HAS_SOURCE_AUTHORITY_ROW",
    }.get(domain, "HAS_BOUNDED_CONTEXT_SIGNAL")


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


def _ticker_from_node_id(node_id: str) -> str:
    if node_id.startswith("company:"):
        return node_id.split(":", 1)[1]
    return ""


def _stable_node_id(prefix: str, *parts: Any) -> str:
    cleaned = [str(part or "").strip().lower() for part in parts if str(part or "").strip()]
    label = ":".join(cleaned)
    return f"{prefix}:{_stable_id(prefix, label)}"


def _stable_id(*parts: Any) -> str:
    raw = "\x1f".join(str(part or "") for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _compact_edge(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "graph_edge_id": row.get("graph_edge_id", ""),
        "from_node_id": row.get("from_node_id", ""),
        "to_node_id": row.get("to_node_id", ""),
        "edge_type": row.get("edge_type", ""),
    }


def _markdown_counter_table(counter: Mapping[str, Any], key_label: str, value_label: str) -> str:
    lines = [f"| {key_label} | {value_label} |", "| --- | ---: |"]
    for key, value in sorted(counter.items(), key=lambda item: str(item[0])):
        lines.append(f"| `{key}` | `{value}` |")
    return "\n".join(lines)
