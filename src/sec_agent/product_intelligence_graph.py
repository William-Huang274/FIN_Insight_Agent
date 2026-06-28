from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


PRODUCT_INTELLIGENCE_NODE_SCHEMA_VERSION = "finsight_product_intelligence_node_v0_1"
PRODUCT_INTELLIGENCE_EDGE_SCHEMA_VERSION = "finsight_product_intelligence_edge_v0_1"
PRODUCT_INTELLIGENCE_COMPANY_PACK_SCHEMA_VERSION = "finsight_product_intelligence_company_pack_v0_1"
PRODUCT_INTELLIGENCE_GAP_SCHEMA_VERSION = "finsight_product_intelligence_gap_v0_1"
PRODUCT_INTELLIGENCE_SUMMARY_SCHEMA_VERSION = "finsight_product_intelligence_summary_v0_1"


DEFAULT_PRODUCT_SLOTS = "data/manifests/company_product_slots_v0_1.jsonl"
DEFAULT_PRODUCT_GRAPH_NODES = "data/manifests/product_relationship_graph_nodes_v0_1.jsonl"
DEFAULT_PRODUCT_GRAPH_EDGES = "data/manifests/product_relationship_graph_edges_v0_1.jsonl"
DEFAULT_GOLD_MART_ROWS = "data/manifests/gold_fact_signal_mart_rows_v0_1.jsonl"

PRODUCT_RELEVANT_FACT_DOMAINS: set[str] = {
    "product_profile_or_spec_fact",
    "product_kpi_fact",
    "industry_operating_metric_fact",
    "customer_deployment_or_order_signal",
    "regulated_or_official_api_signal",
}

PRODUCT_EXACT_DOMAINS: set[str] = {
    "product_kpi_fact",
    "industry_operating_metric_fact",
}

PRODUCT_SPEC_FORBIDDEN_CLAIMS: tuple[str, ...] = (
    "product_revenue",
    "sku_revenue",
    "unit_sales",
    "shipments",
    "ASP",
    "market_share",
    "sell_through",
    "inventory",
    "backlog",
    "customer_order_value",
)

RELATIONSHIP_AUTHORITY_BY_TYPE: dict[str, str] = {
    "OFFICIAL_CUSTOMER_DEPLOYMENT_EVENT": "deployment_signal_authority",
    "PUBLIC_ORDER_OR_TENDER_CONTEXT": "deployment_signal_authority",
    "CHANNEL_OR_DISTRIBUTION_CONTEXT": "channel_presence_signal",
    "OFFICIAL_SUPPLY_CHAIN_RELATIONSHIP": "supply_chain_signal",
    "COMPONENT_INPUT_TO": "supply_chain_signal",
    "ENABLES_PRODUCTION_FOR": "supply_chain_signal",
    "MANUFACTURING_DEPENDENCY_FOR": "template_context_edge",
    "INFRASTRUCTURE_COMPLEMENT_TO": "template_context_edge",
    "INFRASTRUCTURE_SUPPLIER_TO": "template_context_edge",
    "INPUT_OR_COMPLEMENT_TO": "template_context_edge",
    "COMPLEMENTS_WITH": "template_context_edge",
    "COMPETES_WITH": "competitive_context_candidate",
    "HAS_PRODUCT_SLOT": "product_taxonomy_context",
    "FAMILY_HAS_PRODUCT_SLOT": "product_taxonomy_context",
    "BELONGS_TO_FAMILY": "product_taxonomy_context",
    "HAS_PRODUCT_FAMILY": "product_taxonomy_context",
    "IN_PRODUCT_FAMILY": "product_taxonomy_context",
}


def build_product_intelligence_graph(
    repo_root: str | Path,
    *,
    generated_at: str | None = None,
    product_slots_path: str = DEFAULT_PRODUCT_SLOTS,
    product_graph_nodes_path: str = DEFAULT_PRODUCT_GRAPH_NODES,
    product_graph_edges_path: str = DEFAULT_PRODUCT_GRAPH_EDGES,
    gold_mart_rows_path: str = DEFAULT_GOLD_MART_ROWS,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    generated_at = generated_at or _utc_now()
    slots = _read_jsonl(root / product_slots_path)
    product_graph_nodes = _read_jsonl(root / product_graph_nodes_path)
    product_graph_edges = _read_jsonl(root / product_graph_edges_path)
    gold_rows = [
        row
        for row in _read_jsonl(root / gold_mart_rows_path)
        if str(row.get("fact_domain") or "") in PRODUCT_RELEVANT_FACT_DOMAINS and _ticker(row)
    ]

    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}

    for row in product_graph_nodes:
        node = _node_from_product_graph(row, generated_at=generated_at)
        nodes.setdefault(node["node_id"], node)

    for slot in slots:
        for node in _nodes_from_product_slot(slot, generated_at=generated_at):
            nodes.setdefault(node["node_id"], node)

    for row in gold_rows:
        for node in _nodes_from_gold_product_row(row, generated_at=generated_at):
            nodes.setdefault(node["node_id"], node)

    for row in product_graph_edges:
        edge = _edge_from_product_graph(row, generated_at=generated_at)
        edges.setdefault(edge["edge_id"], edge)

    for row in gold_rows:
        for edge in _edges_from_gold_product_row(row, generated_at=generated_at):
            edges.setdefault(edge["edge_id"], edge)

    packs, gaps = _build_company_packs_and_gaps(
        slots=slots,
        gold_rows=gold_rows,
        edges=list(edges.values()),
        generated_at=generated_at,
    )
    summary = build_product_intelligence_summary(
        nodes=list(nodes.values()),
        edges=list(edges.values()),
        packs=packs,
        gaps=gaps,
        generated_at=generated_at,
    )
    return {
        "nodes": sorted(nodes.values(), key=lambda row: row["node_id"]),
        "edges": sorted(edges.values(), key=lambda row: row["edge_id"]),
        "company_packs": sorted(packs, key=lambda row: row["ticker"]),
        "gap_rows": sorted(gaps, key=lambda row: row["gap_id"]),
        "summary": summary,
    }


def build_product_intelligence_summary(
    *,
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    packs: Sequence[Mapping[str, Any]],
    gaps: Sequence[Mapping[str, Any]],
    generated_at: str | None = None,
    sqlite_path: str = "",
    sqlite_node_count: int = 0,
    sqlite_edge_count: int = 0,
    sqlite_pack_count: int = 0,
    sqlite_gap_count: int = 0,
) -> dict[str, Any]:
    generated_at = generated_at or _utc_now()
    node_ids = {str(row.get("node_id") or "") for row in nodes}
    dangling_edges = [
        row
        for row in edges
        if str(row.get("from_node_id") or "") not in node_ids or str(row.get("to_node_id") or "") not in node_ids
    ]
    invalid_evidence_edges = [
        row
        for row in edges
        if row.get("can_enter_evidence_bundle") and str(row.get("authority_type") or "") == "template_context_edge"
    ]
    status = "pass"
    if dangling_edges or invalid_evidence_edges:
        status = "action_required"
    if sqlite_node_count and sqlite_node_count != len(nodes):
        status = "action_required"
    if sqlite_edge_count and sqlite_edge_count != len(edges):
        status = "action_required"
    if sqlite_pack_count and sqlite_pack_count != len(packs):
        status = "action_required"
    if sqlite_gap_count and sqlite_gap_count != len(gaps):
        status = "action_required"
    return {
        "schema_version": PRODUCT_INTELLIGENCE_SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": status,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "company_pack_count": len(packs),
        "gap_count": len(gaps),
        "company_count": len({str(row.get("ticker") or "") for row in packs}),
        "node_type_counts": dict(Counter(str(row.get("node_type") or "") for row in nodes)),
        "edge_type_counts": dict(Counter(str(row.get("edge_type") or "") for row in edges).most_common(50)),
        "authority_type_counts": dict(Counter(str(row.get("authority_type") or "") for row in edges)),
        "evidence_bundle_edge_count": sum(1 for row in edges if row.get("can_enter_evidence_bundle")),
        "company_pack_status_counts": dict(Counter(str(row.get("status") or "") for row in packs)),
        "gap_reason_counts": dict(Counter(str(row.get("gap_reason") or "") for row in gaps)),
        "dangling_edge_count": len(dangling_edges),
        "invalid_evidence_edge_count": len(invalid_evidence_edges),
        "dangling_edge_samples": [_compact_edge(row) for row in dangling_edges[:20]],
        "invalid_evidence_edge_samples": [_compact_edge(row) for row in invalid_evidence_edges[:20]],
        "sqlite_path": sqlite_path,
        "sqlite_node_count": sqlite_node_count,
        "sqlite_edge_count": sqlite_edge_count,
        "sqlite_pack_count": sqlite_pack_count,
        "sqlite_gap_count": sqlite_gap_count,
        "policy": (
            "ProductIntelligenceGraph v0.1 normalizes product slots, product facts, deployment/channel/supply-chain signals, "
            "and competitive context into a Research Lead consumable graph. It keeps Product-KPI exact authority strict while "
            "allowing product specs, architecture/profile, customer deployment, channel, and supply-chain signals to support "
            "bounded thesis-driver analysis with explicit forbidden claims."
        ),
    }


def write_product_intelligence_sqlite(
    sqlite_path: str | Path,
    *,
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    packs: Sequence[Mapping[str, Any]],
    gaps: Sequence[Mapping[str, Any]],
    replace: bool = True,
) -> dict[str, int]:
    target = Path(sqlite_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if replace and target.exists():
        target.unlink()
    with sqlite3.connect(str(target)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS product_intelligence_nodes (
                node_id TEXT PRIMARY KEY,
                schema_version TEXT,
                generated_at TEXT,
                node_type TEXT,
                ticker TEXT,
                product_family_id TEXT,
                product_or_segment TEXT,
                label TEXT,
                source_ref TEXT,
                payload_json TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS product_intelligence_edges (
                edge_id TEXT PRIMARY KEY,
                schema_version TEXT,
                generated_at TEXT,
                from_node_id TEXT,
                to_node_id TEXT,
                edge_type TEXT,
                ticker TEXT,
                product_family_id TEXT,
                authority_type TEXT,
                authority_mode TEXT,
                can_enter_evidence_bundle INTEGER,
                confidence REAL,
                source_layer TEXT,
                source_role TEXT,
                claim_boundary TEXT,
                forbidden_claims_json TEXT,
                evidence_refs_json TEXT,
                payload_json TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS product_intelligence_company_packs (
                ticker TEXT PRIMARY KEY,
                schema_version TEXT,
                generated_at TEXT,
                company_name TEXT,
                status TEXT,
                product_family_count INTEGER,
                product_slot_count INTEGER,
                product_profile_count INTEGER,
                technical_spec_count INTEGER,
                product_kpi_exact_count INTEGER,
                industry_operating_metric_count INTEGER,
                customer_deployment_signal_count INTEGER,
                channel_signal_count INTEGER,
                supply_chain_signal_count INTEGER,
                competitive_edge_count INTEGER,
                gap_count INTEGER,
                pack_json TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS product_intelligence_gaps (
                gap_id TEXT PRIMARY KEY,
                schema_version TEXT,
                generated_at TEXT,
                ticker TEXT,
                company_name TEXT,
                gap_reason TEXT,
                severity TEXT,
                next_action TEXT,
                public_source_boundary TEXT,
                evidence_refs_json TEXT
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO product_intelligence_nodes (
                node_id, schema_version, generated_at, node_type, ticker, product_family_id,
                product_or_segment, label, source_ref, payload_json
            ) VALUES (
                :node_id, :schema_version, :generated_at, :node_type, :ticker, :product_family_id,
                :product_or_segment, :label, :source_ref, :payload_json
            )
            """,
            [dict(row) for row in nodes],
        )
        conn.executemany(
            """
            INSERT INTO product_intelligence_edges (
                edge_id, schema_version, generated_at, from_node_id, to_node_id, edge_type, ticker,
                product_family_id, authority_type, authority_mode, can_enter_evidence_bundle, confidence,
                source_layer, source_role, claim_boundary, forbidden_claims_json, evidence_refs_json, payload_json
            ) VALUES (
                :edge_id, :schema_version, :generated_at, :from_node_id, :to_node_id, :edge_type, :ticker,
                :product_family_id, :authority_type, :authority_mode, :can_enter_evidence_bundle, :confidence,
                :source_layer, :source_role, :claim_boundary, :forbidden_claims_json, :evidence_refs_json, :payload_json
            )
            """,
            [{**dict(row), "can_enter_evidence_bundle": int(bool(row.get("can_enter_evidence_bundle")))} for row in edges],
        )
        conn.executemany(
            """
            INSERT INTO product_intelligence_company_packs (
                ticker, schema_version, generated_at, company_name, status, product_family_count,
                product_slot_count, product_profile_count, technical_spec_count, product_kpi_exact_count,
                industry_operating_metric_count, customer_deployment_signal_count, channel_signal_count,
                supply_chain_signal_count, competitive_edge_count, gap_count, pack_json
            ) VALUES (
                :ticker, :schema_version, :generated_at, :company_name, :status, :product_family_count,
                :product_slot_count, :product_profile_count, :technical_spec_count, :product_kpi_exact_count,
                :industry_operating_metric_count, :customer_deployment_signal_count, :channel_signal_count,
                :supply_chain_signal_count, :competitive_edge_count, :gap_count, :pack_json
            )
            """,
            [dict(row) for row in packs],
        )
        conn.executemany(
            """
            INSERT INTO product_intelligence_gaps (
                gap_id, schema_version, generated_at, ticker, company_name, gap_reason, severity,
                next_action, public_source_boundary, evidence_refs_json
            ) VALUES (
                :gap_id, :schema_version, :generated_at, :ticker, :company_name, :gap_reason, :severity,
                :next_action, :public_source_boundary, :evidence_refs_json
            )
            """,
            [dict(row) for row in gaps],
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pig_edges_ticker ON product_intelligence_edges(ticker)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pig_edges_authority ON product_intelligence_edges(authority_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pig_gaps_reason ON product_intelligence_gaps(gap_reason)")
        conn.commit()
        return {
            "node_count": int(conn.execute("SELECT COUNT(*) FROM product_intelligence_nodes").fetchone()[0]),
            "edge_count": int(conn.execute("SELECT COUNT(*) FROM product_intelligence_edges").fetchone()[0]),
            "pack_count": int(conn.execute("SELECT COUNT(*) FROM product_intelligence_company_packs").fetchone()[0]),
            "gap_count": int(conn.execute("SELECT COUNT(*) FROM product_intelligence_gaps").fetchone()[0]),
        }


def render_product_intelligence_report(summary: Mapping[str, Any], *, output_paths: Mapping[str, str]) -> str:
    lines = [
        "# ProductIntelligenceGraph v0.1",
        "",
        f"- Generated at: `{summary.get('generated_at', '')}`",
        f"- Status: `{summary.get('status', '')}`",
        f"- Companies: `{summary.get('company_count', 0)}`",
        f"- Nodes / edges: `{summary.get('node_count', 0)}` / `{summary.get('edge_count', 0)}`",
        f"- Company packs: `{summary.get('company_pack_count', 0)}`",
        f"- Gap rows: `{summary.get('gap_count', 0)}`",
        f"- Evidence-bundle eligible edges: `{summary.get('evidence_bundle_edge_count', 0)}`",
        "",
        "## Outputs",
        "",
    ]
    for key, path in output_paths.items():
        lines.append(f"- `{key}`: `{path}`")
    lines.extend(
        [
            "",
            "## Authority Types",
            "",
            _markdown_counter_table(summary.get("authority_type_counts") or {}, "Authority type", "Edges"),
            "",
            "## Company Pack Status",
            "",
            _markdown_counter_table(summary.get("company_pack_status_counts") or {}, "Status", "Companies"),
            "",
            "## Gaps",
            "",
            _markdown_counter_table(summary.get("gap_reason_counts") or {}, "Gap reason", "Rows"),
            "",
            "## Boundary",
            "",
            "- Product-KPI exact remains strict and separate from product profile/spec/deployment signals.",
            "- Technical specs can support capability, generation, architecture and comparison claims, not sales, ASP, share, backlog or shipment claims.",
            "- Customer deployment, public order, channel and supply-chain edges support bounded thesis drivers only unless exact commercial fields are separately disclosed.",
            "- Same-family competitive edges are comparable candidates; they do not prove share shift, win/loss, pricing pressure or substitution without stronger evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _node_from_product_graph(row: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    payload = row.get("payload") if isinstance(row.get("payload"), Mapping) else {}
    node_id = str(row.get("node_id") or "")
    ticker = str(payload.get("ticker") or "")
    product_family_id = str(payload.get("family_id") or "")
    return {
        "schema_version": PRODUCT_INTELLIGENCE_NODE_SCHEMA_VERSION,
        "generated_at": generated_at,
        "node_id": node_id,
        "node_type": _product_node_type(str(row.get("node_type") or "")),
        "ticker": ticker or _ticker_from_node_id(node_id),
        "product_family_id": product_family_id or _family_from_node_id(node_id),
        "product_or_segment": str(payload.get("product_slot_name") or ""),
        "label": str(row.get("label") or ""),
        "source_ref": node_id,
        "payload_json": json.dumps({"source": "product_relationship_graph_node", "payload": payload}, ensure_ascii=False, sort_keys=True),
    }


def _nodes_from_product_slot(slot: Mapping[str, Any], *, generated_at: str) -> list[dict[str, Any]]:
    ticker = _ticker(slot)
    family_id = str(slot.get("family_id") or "")
    company_name = str(slot.get("company_name") or "")
    product_slot_id = str(slot.get("product_slot_id") or "")
    product_slot_name = str(slot.get("product_slot_name") or "")
    return [
        {
            "schema_version": PRODUCT_INTELLIGENCE_NODE_SCHEMA_VERSION,
            "generated_at": generated_at,
            "node_id": f"company:{ticker}",
            "node_type": "company",
            "ticker": ticker,
            "product_family_id": "",
            "product_or_segment": "",
            "label": company_name or ticker,
            "source_ref": str(slot.get("assignment_id") or ""),
            "payload_json": json.dumps({"source": "company_product_slot"}, ensure_ascii=False, sort_keys=True),
        },
        {
            "schema_version": PRODUCT_INTELLIGENCE_NODE_SCHEMA_VERSION,
            "generated_at": generated_at,
            "node_id": f"product_family:{family_id}",
            "node_type": "product_family",
            "ticker": "",
            "product_family_id": family_id,
            "product_or_segment": "",
            "label": str(slot.get("family_name") or family_id),
            "source_ref": family_id,
            "payload_json": json.dumps({"source": "company_product_slot"}, ensure_ascii=False, sort_keys=True),
        },
        {
            "schema_version": PRODUCT_INTELLIGENCE_NODE_SCHEMA_VERSION,
            "generated_at": generated_at,
            "node_id": f"product_slot:{product_slot_id}",
            "node_type": "product_slot",
            "ticker": ticker,
            "product_family_id": family_id,
            "product_or_segment": product_slot_name,
            "label": product_slot_name,
            "source_ref": product_slot_id,
            "payload_json": json.dumps(
                {
                    "source": "company_product_slot",
                    "slot_status": slot.get("slot_status"),
                    "sample_urls": slot.get("sample_urls") or [],
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        },
    ]


def _nodes_from_gold_product_row(row: Mapping[str, Any], *, generated_at: str) -> list[dict[str, Any]]:
    ticker = _ticker(row)
    family_id = _family_id(row)
    company_name = str(row.get("company_name") or ticker)
    nodes = [
        {
            "schema_version": PRODUCT_INTELLIGENCE_NODE_SCHEMA_VERSION,
            "generated_at": generated_at,
            "node_id": f"company:{ticker}",
            "node_type": "company",
            "ticker": ticker,
            "product_family_id": "",
            "product_or_segment": "",
            "label": company_name,
            "source_ref": str(row.get("source_row_id") or row.get("gold_row_id") or ""),
            "payload_json": json.dumps({"source": "gold_fact_signal_mart"}, ensure_ascii=False, sort_keys=True),
        }
    ]
    if family_id:
        nodes.append(
            {
                "schema_version": PRODUCT_INTELLIGENCE_NODE_SCHEMA_VERSION,
                "generated_at": generated_at,
                "node_id": f"company_product_family:{ticker}:{family_id}",
                "node_type": "company_product_family",
                "ticker": ticker,
                "product_family_id": family_id,
                "product_or_segment": str(row.get("product_family") or ""),
                "label": f"{ticker} {row.get('product_family') or family_id}",
                "source_ref": str(row.get("source_row_id") or row.get("gold_row_id") or ""),
                "payload_json": json.dumps({"source": "gold_fact_signal_mart"}, ensure_ascii=False, sort_keys=True),
            }
        )
    nodes.append(_node_from_gold_product_row(row, generated_at=generated_at))
    return nodes


def _node_from_gold_product_row(row: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    gold_row_id = str(row.get("gold_row_id") or _stable_id("gold", row))
    return {
        "schema_version": PRODUCT_INTELLIGENCE_NODE_SCHEMA_VERSION,
        "generated_at": generated_at,
        "node_id": f"product_evidence:{gold_row_id}",
        "node_type": _gold_node_type(row),
        "ticker": _ticker(row),
        "product_family_id": _family_id(row),
        "product_or_segment": str(row.get("product_or_segment") or row.get("metric_name") or row.get("fact_type") or ""),
        "label": _gold_label(row),
        "source_ref": gold_row_id,
        "payload_json": json.dumps(_compact_gold_payload(row), ensure_ascii=False, sort_keys=True),
    }


def _edge_from_product_graph(row: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    relationship_type = str(row.get("relationship_type") or "")
    authority_type = RELATIONSHIP_AUTHORITY_BY_TYPE.get(relationship_type, "product_relationship_context")
    evidence_refs = _list_field(row.get("evidence_refs"))
    can_enter = bool(evidence_refs) and authority_type != "template_context_edge"
    return {
        "schema_version": PRODUCT_INTELLIGENCE_EDGE_SCHEMA_VERSION,
        "generated_at": generated_at,
        "edge_id": f"pig_edge:{row.get('edge_id') or _stable_id('product_graph_edge', row)}",
        "from_node_id": str(row.get("from_node_id") or ""),
        "to_node_id": str(row.get("to_node_id") or ""),
        "edge_type": relationship_type,
        "ticker": _ticker_from_node_id(str(row.get("from_node_id") or "")),
        "product_family_id": _family_from_node_id(str(row.get("from_node_id") or "")) or _family_from_node_id(str(row.get("to_node_id") or "")),
        "authority_type": authority_type,
        "authority_mode": _authority_mode_for_relationship(authority_type),
        "can_enter_evidence_bundle": can_enter,
        "confidence": float(row.get("confidence") or 0.0),
        "source_layer": str(row.get("source_layer") or ""),
        "source_role": _source_role_for_relationship(authority_type),
        "claim_boundary": str(row.get("claim_boundary") or ""),
        "forbidden_claims_json": json.dumps(_list_field(row.get("forbidden_claims")), ensure_ascii=False, sort_keys=True),
        "evidence_refs_json": json.dumps(evidence_refs, ensure_ascii=False, sort_keys=True),
        "payload_json": json.dumps(
            {
                "source": "product_relationship_graph_edge",
                "promotion_status": row.get("promotion_status"),
                "source_edge_id": row.get("edge_id"),
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
    }


def _edges_from_gold_product_row(row: Mapping[str, Any], *, generated_at: str) -> list[dict[str, Any]]:
    ticker = _ticker(row)
    gold_row_id = str(row.get("gold_row_id") or _stable_id("gold", row))
    evidence_node_id = f"product_evidence:{gold_row_id}"
    family_id = _family_id(row)
    authority_type = _authority_type_for_gold_row(row)
    edge_type = _edge_type_for_gold_row(row)
    source_role = str(row.get("source_role") or "")
    edge = {
        "schema_version": PRODUCT_INTELLIGENCE_EDGE_SCHEMA_VERSION,
        "generated_at": generated_at,
        "edge_id": _stable_id("pig_gold_edge", ticker, gold_row_id, edge_type),
        "from_node_id": f"company:{ticker}",
        "to_node_id": evidence_node_id,
        "edge_type": edge_type,
        "ticker": ticker,
        "product_family_id": family_id,
        "authority_type": authority_type,
        "authority_mode": str(row.get("authority_mode") or ""),
        "can_enter_evidence_bundle": bool(row.get("can_enter_evidence_bundle")),
        "confidence": 1.0 if str(row.get("authority_mode") or "") == "exact_company_fact_authority" else 0.78,
        "source_layer": str(row.get("source_layer") or ""),
        "source_role": source_role,
        "claim_boundary": str(row.get("claim_boundary") or ""),
        "forbidden_claims_json": json.dumps(_gold_forbidden_claims(row), ensure_ascii=False, sort_keys=True),
        "evidence_refs_json": json.dumps(_gold_evidence_refs(row), ensure_ascii=False, sort_keys=True),
        "payload_json": json.dumps(_compact_gold_payload(row), ensure_ascii=False, sort_keys=True),
    }
    edges = [edge]
    if family_id:
        edges.append(
            {
                **edge,
                "edge_id": _stable_id("pig_family_gold_edge", ticker, family_id, gold_row_id, edge_type),
                "from_node_id": f"company_product_family:{ticker}:{family_id}",
                "to_node_id": evidence_node_id,
                "edge_type": f"FAMILY_{edge_type}",
            }
        )
    return edges


def _build_company_packs_and_gaps(
    *,
    slots: Sequence[Mapping[str, Any]],
    gold_rows: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    generated_at: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    slots_by_ticker: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    gold_by_ticker: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    edges_by_ticker: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    company_names: dict[str, str] = {}
    for slot in slots:
        ticker = _ticker(slot)
        if ticker:
            slots_by_ticker[ticker].append(slot)
            company_names.setdefault(ticker, str(slot.get("company_name") or ""))
    for row in gold_rows:
        ticker = _ticker(row)
        if ticker:
            gold_by_ticker[ticker].append(row)
            company_names.setdefault(ticker, str(row.get("company_name") or ""))
    for edge in edges:
        ticker = str(edge.get("ticker") or "")
        if not ticker:
            ticker = _ticker_from_node_id(str(edge.get("from_node_id") or ""))
        if ticker:
            edges_by_ticker[ticker].append(edge)

    tickers = sorted(set(slots_by_ticker) | set(gold_by_ticker) | set(edges_by_ticker))
    packs: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for ticker in tickers:
        company_slots = slots_by_ticker.get(ticker, [])
        company_gold = gold_by_ticker.get(ticker, [])
        company_edges = edges_by_ticker.get(ticker, [])
        company_name = company_names.get(ticker, "")
        family_ids = sorted({str(row.get("family_id") or "") for row in company_slots if str(row.get("family_id") or "")})
        exact_kpi_rows = [row for row in company_gold if str(row.get("fact_domain") or "") == "product_kpi_fact"]
        operating_rows = [row for row in company_gold if str(row.get("fact_domain") or "") == "industry_operating_metric_fact"]
        profile_rows = [row for row in company_gold if str(row.get("fact_domain") or "") == "product_profile_or_spec_fact"]
        technical_rows = [row for row in profile_rows if _authority_type_for_gold_row(row) == "technical_fact_authority"]
        deployment_rows = [row for row in company_gold if str(row.get("fact_domain") or "") == "customer_deployment_or_order_signal"]
        channel_edges = [edge for edge in company_edges if str(edge.get("authority_type") or "") == "channel_presence_signal"]
        supply_edges = [edge for edge in company_edges if str(edge.get("authority_type") or "") == "supply_chain_signal"]
        competitive_edges = [edge for edge in company_edges if str(edge.get("authority_type") or "") == "competitive_context_candidate"]
        company_gaps = _gap_rows_for_company(
            ticker=ticker,
            company_name=company_name,
            slots=company_slots,
            exact_kpi_rows=exact_kpi_rows,
            operating_rows=operating_rows,
            profile_rows=profile_rows,
            technical_rows=technical_rows,
            deployment_rows=deployment_rows,
            channel_edges=channel_edges,
            supply_edges=supply_edges,
            generated_at=generated_at,
        )
        gaps.extend(company_gaps)
        pack_payload = {
            "family_ids": family_ids[:20],
            "representative_product_slots": [_compact_slot(row) for row in company_slots[:12]],
            "representative_exact_kpis": [_compact_gold_payload(row) for row in exact_kpi_rows[:12]],
            "representative_operating_metrics": [_compact_gold_payload(row) for row in operating_rows[:12]],
            "representative_product_profile_or_specs": [_compact_gold_payload(row) for row in profile_rows[:12]],
            "representative_deployment_rows": [_compact_gold_payload(row) for row in deployment_rows[:12]],
            "representative_relationship_edges": [_compact_edge(row) for row in company_edges[:20]],
            "gap_ids": [row["gap_id"] for row in company_gaps],
            "memo_writer_boundary": "Memo Writer must consume this pack through Research Lead / MemoLogicPlan; raw slots and relationship edges are not standalone thesis conclusions.",
        }
        packs.append(
            {
                "schema_version": PRODUCT_INTELLIGENCE_COMPANY_PACK_SCHEMA_VERSION,
                "generated_at": generated_at,
                "ticker": ticker,
                "company_name": company_name,
                "status": "pass_with_gaps" if company_gaps else "pass",
                "product_family_count": len(family_ids),
                "product_slot_count": len(company_slots),
                "product_profile_count": len(profile_rows),
                "technical_spec_count": len(technical_rows),
                "product_kpi_exact_count": len(exact_kpi_rows),
                "industry_operating_metric_count": len(operating_rows),
                "customer_deployment_signal_count": len(deployment_rows),
                "channel_signal_count": len(channel_edges),
                "supply_chain_signal_count": len(supply_edges),
                "competitive_edge_count": len(competitive_edges),
                "gap_count": len(company_gaps),
                "pack_json": json.dumps(pack_payload, ensure_ascii=False, sort_keys=True),
            }
        )
    return packs, gaps


def _gap_rows_for_company(
    *,
    ticker: str,
    company_name: str,
    slots: Sequence[Mapping[str, Any]],
    exact_kpi_rows: Sequence[Mapping[str, Any]],
    operating_rows: Sequence[Mapping[str, Any]],
    profile_rows: Sequence[Mapping[str, Any]],
    technical_rows: Sequence[Mapping[str, Any]],
    deployment_rows: Sequence[Mapping[str, Any]],
    channel_edges: Sequence[Mapping[str, Any]],
    supply_edges: Sequence[Mapping[str, Any]],
    generated_at: str,
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    if not slots:
        gaps.append(_gap_row(ticker, company_name, "product_slot_absent", "hard", "run product family/source route locator", generated_at, []))
    if profile_rows and not technical_rows:
        gaps.append(
            _gap_row(
                ticker,
                company_name,
                "technical_spec_exact_slot_absent",
                "soft",
                "deepen official product spec / technical document parser where relevant",
                generated_at,
                [str(row.get("gold_row_id") or "") for row in profile_rows[:5]],
            )
        )
    if not exact_kpi_rows and not operating_rows:
        gaps.append(
            _gap_row(
                ticker,
                company_name,
                "product_kpi_or_operating_metric_absent",
                "soft",
                "keep as public/commercial boundary unless company disclosure or industry slot parser finds exact value/unit/period/product row",
                generated_at,
                [str(row.get("product_slot_id") or "") for row in slots[:5]],
            )
        )
    if not deployment_rows and not channel_edges and not supply_edges:
        gaps.append(
            _gap_row(
                ticker,
                company_name,
                "deployment_channel_supply_chain_signal_absent",
                "soft",
                "target issuer official customer/deployment, distributor/channel, public order, or official supply-chain route before declaring boundary",
                generated_at,
                [str(row.get("product_slot_id") or "") for row in slots[:5]],
            )
        )
    return gaps


def _gap_row(
    ticker: str,
    company_name: str,
    reason: str,
    severity: str,
    next_action: str,
    generated_at: str,
    refs: Sequence[str],
) -> dict[str, Any]:
    return {
        "schema_version": PRODUCT_INTELLIGENCE_GAP_SCHEMA_VERSION,
        "generated_at": generated_at,
        "gap_id": _stable_id("pig_gap", ticker, reason),
        "ticker": ticker,
        "company_name": company_name,
        "gap_reason": reason,
        "severity": severity,
        "next_action": next_action,
        "public_source_boundary": "not_declared_final_boundary_until targeted source/parser repair has been attempted",
        "evidence_refs_json": json.dumps([ref for ref in refs if ref], ensure_ascii=False, sort_keys=True),
    }


def _authority_type_for_gold_row(row: Mapping[str, Any]) -> str:
    fact_domain = str(row.get("fact_domain") or "")
    fact_type = str(row.get("fact_type") or "").lower()
    source_role = str(row.get("source_role") or "").lower()
    source_row_id = str(row.get("source_row_id") or "").lower()
    if fact_domain == "product_kpi_fact":
        return "exact_product_kpi_authority"
    if fact_domain == "industry_operating_metric_fact":
        return "industry_operating_metric_authority"
    if fact_domain == "customer_deployment_or_order_signal":
        return "deployment_signal_authority"
    if fact_domain == "regulated_or_official_api_signal":
        return "regulated_product_context_signal"
    if "technical" in fact_type or "technical" in source_role or "official_product_spec" in source_row_id:
        return "technical_fact_authority"
    return "product_profile_authority"


def _edge_type_for_gold_row(row: Mapping[str, Any]) -> str:
    return {
        "exact_product_kpi_authority": "HAS_PRODUCT_KPI_EXACT_FACT",
        "industry_operating_metric_authority": "HAS_INDUSTRY_OPERATING_METRIC",
        "technical_fact_authority": "HAS_TECHNICAL_PRODUCT_SPEC",
        "deployment_signal_authority": "HAS_CUSTOMER_DEPLOYMENT_SIGNAL",
        "regulated_product_context_signal": "HAS_REGULATED_PRODUCT_CONTEXT",
        "product_profile_authority": "HAS_PRODUCT_PROFILE",
    }.get(_authority_type_for_gold_row(row), "HAS_PRODUCT_CONTEXT")


def _gold_node_type(row: Mapping[str, Any]) -> str:
    return {
        "exact_product_kpi_authority": "product_kpi_exact_fact",
        "industry_operating_metric_authority": "industry_operating_metric_fact",
        "technical_fact_authority": "technical_product_spec",
        "deployment_signal_authority": "customer_deployment_signal",
        "regulated_product_context_signal": "regulated_product_context_signal",
        "product_profile_authority": "product_profile_context",
    }.get(_authority_type_for_gold_row(row), "product_context")


def _gold_forbidden_claims(row: Mapping[str, Any]) -> list[str]:
    payload_claims = _list_field(row.get("forbidden_claims"))
    if payload_claims:
        return payload_claims
    authority_type = _authority_type_for_gold_row(row)
    if authority_type in {"technical_fact_authority", "product_profile_authority", "deployment_signal_authority", "channel_presence_signal"}:
        return list(PRODUCT_SPEC_FORBIDDEN_CLAIMS)
    if authority_type == "exact_product_kpi_authority":
        return ["market_share", "sell_through", "channel_inventory", "undisclosed_product_revenue", "ASP_without_company_or_tracker_data"]
    return list(PRODUCT_SPEC_FORBIDDEN_CLAIMS)


def _gold_evidence_refs(row: Mapping[str, Any]) -> list[str]:
    refs = [
        str(row.get("gold_row_id") or ""),
        str(row.get("source_row_id") or ""),
        str(row.get("evidence_ref") or ""),
        str(row.get("citation_url") or row.get("source_url") or ""),
    ]
    return _unique(refs)


def _compact_gold_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "gold_row_id": row.get("gold_row_id"),
        "source_row_id": row.get("source_row_id"),
        "ticker": row.get("ticker"),
        "company_name": row.get("company_name"),
        "fact_domain": row.get("fact_domain"),
        "fact_type": row.get("fact_type"),
        "authority_mode": row.get("authority_mode"),
        "support_surface": row.get("support_surface"),
        "source_layer": row.get("source_layer"),
        "source_role": row.get("source_role"),
        "product_family": row.get("product_family"),
        "product_or_segment": row.get("product_or_segment"),
        "metric_name": row.get("metric_name"),
        "value": row.get("value"),
        "unit": row.get("unit"),
        "period": row.get("period"),
        "citation_url": row.get("citation_url") or row.get("source_url"),
        "claim_boundary": row.get("claim_boundary"),
    }


def _compact_slot(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "product_slot_id": row.get("product_slot_id"),
        "family_id": row.get("family_id"),
        "family_name": row.get("family_name"),
        "product_slot_name": row.get("product_slot_name"),
        "slot_status": row.get("slot_status"),
        "claim_boundary": row.get("claim_boundary"),
        "sample_urls": (row.get("sample_urls") or [])[:3] if isinstance(row.get("sample_urls"), list) else [],
    }


def _compact_edge(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "edge_id": row.get("edge_id"),
        "edge_type": row.get("edge_type"),
        "from_node_id": row.get("from_node_id"),
        "to_node_id": row.get("to_node_id"),
        "authority_type": row.get("authority_type"),
        "can_enter_evidence_bundle": row.get("can_enter_evidence_bundle"),
        "claim_boundary": row.get("claim_boundary"),
    }


def _gold_label(row: Mapping[str, Any]) -> str:
    parts = [
        str(row.get("product_or_segment") or row.get("product_family") or ""),
        str(row.get("metric_name") or row.get("fact_type") or ""),
        str(row.get("period") or ""),
    ]
    return " | ".join(part for part in parts if part) or str(row.get("gold_row_id") or "")


def _product_node_type(node_type: str) -> str:
    return {
        "company": "company",
        "product_family": "product_family",
        "company_product_family": "company_product_family",
        "product_slot": "product_slot",
        "external_counterparty": "counterparty",
    }.get(node_type, node_type or "unknown")


def _authority_mode_for_relationship(authority_type: str) -> str:
    if authority_type == "product_taxonomy_context":
        return "bounded_thesis_driver_authority"
    if authority_type == "template_context_edge":
        return "planning_or_gap_only"
    return "bounded_thesis_driver_authority"


def _source_role_for_relationship(authority_type: str) -> str:
    return {
        "deployment_signal_authority": "customer_deployment_or_order_signal",
        "channel_presence_signal": "channel_offer_or_distributor_context",
        "supply_chain_signal": "supply_chain_relationship",
        "competitive_context_candidate": "competitive_comparable_context",
        "template_context_edge": "derived_lane_template_context",
        "product_taxonomy_context": "product_taxonomy_context",
    }.get(authority_type, "product_relationship_context")


def _family_id(row: Mapping[str, Any]) -> str:
    return _slug(str(row.get("product_family") or ""))


def _ticker(row: Mapping[str, Any]) -> str:
    return str(row.get("ticker") or row.get("issuer_ticker") or "").strip().upper()


def _ticker_from_node_id(node_id: str) -> str:
    if node_id.startswith("company:"):
        return node_id.split(":", 1)[1].upper()
    if node_id.startswith("company_product_family:"):
        parts = node_id.split(":")
        return parts[1].upper() if len(parts) > 1 else ""
    if node_id.startswith("product_slot:"):
        return ""
    return ""


def _family_from_node_id(node_id: str) -> str:
    if node_id.startswith("product_family:"):
        return node_id.split(":", 1)[1]
    if node_id.startswith("company_product_family:"):
        parts = node_id.split(":")
        return parts[2] if len(parts) > 2 else ""
    return ""


def _list_field(value: Any) -> list[str]:
    if isinstance(value, list):
        return _unique([str(item) for item in value])
    if isinstance(value, str) and value.strip():
        stripped = value.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return _unique([str(item) for item in parsed])
            except json.JSONDecodeError:
                pass
        return [stripped]
    return []


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    target = Path(path)
    if not target.exists():
        return []
    rows: list[dict[str, Any]] = []
    with target.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, Mapping):
                rows.append(dict(row))
    return rows


def _markdown_counter_table(counter: Mapping[str, Any], key_label: str, value_label: str) -> str:
    if not counter:
        return "_None._"
    lines = [f"| {key_label} | {value_label} |", "| --- | ---: |"]
    for key, value in sorted(counter.items(), key=lambda item: (-int(item[1] or 0), str(item[0]))):
        lines.append(f"| `{key}` | {value} |")
    return "\n".join(lines)


def _unique(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        cleaned = str(value or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        output.append(cleaned)
    return output


def _slug(value: str) -> str:
    text = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value or ""))
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


def _stable_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha1(
        "||".join(json.dumps(part, ensure_ascii=False, sort_keys=True, default=str) for part in parts).encode("utf-8")
    ).hexdigest()[:20]
    return f"{prefix}:{digest}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
