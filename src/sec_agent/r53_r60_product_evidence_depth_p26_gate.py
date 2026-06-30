"""P26 product-evidence all-universe depth gate.

P25 originally consumed the five-dimension depth parity summary directly for
the product-evidence pack.  That was too coarse: Product-KPI exact gaps should
block exact KPI claims, but they should not erase the product/profile/spec/
relationship graph that is already available for all companies.  P26 splits the
all-universe product pack into auditable sublayers and reports the real
remaining product-pack blocker separately.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from sec_agent.r53_r60_runtime_task_spine import default_s1_paths, rel_path, utc_now_iso, write_json, write_jsonl


SCHEMA_VERSION = "r53_r60_p26_product_evidence_all_universe_depth_gate_v0_1"
P26_REPORT_ID = "p26_product_evidence_all_universe_depth_report_v0_1"


@dataclass(frozen=True)
class P26Paths:
    db_path: Path
    schema_path: Path
    layer_rows_path: Path
    gap_rows_path: Path
    gate_rows_path: Path
    summary_path: Path
    report_path: Path


def default_p26_paths(root: Path) -> P26Paths:
    s1_paths = default_s1_paths(root)
    return P26Paths(
        db_path=s1_paths.db_path,
        schema_path=root / "configs" / "r53_r60" / "p26_product_evidence_all_universe_depth_schema_v0_1.json",
        layer_rows_path=root
        / "data"
        / "manifests"
        / "r53_r60_p26_product_evidence_all_universe_depth_layer_rows_v0_1.jsonl",
        gap_rows_path=root
        / "data"
        / "manifests"
        / "r53_r60_p26_product_evidence_all_universe_depth_gap_rows_v0_1.jsonl",
        gate_rows_path=root
        / "data"
        / "manifests"
        / "r53_r60_p26_product_evidence_all_universe_depth_gate_rows_v0_1.jsonl",
        summary_path=root / "data" / "manifests" / "r53_r60_p26_product_evidence_all_universe_depth_summary_v0_1.json",
        report_path=root
        / "docs"
        / "internal"
        / "vnext_20260610"
        / "r53_r60_p26_product_evidence_all_universe_depth_gate.zh-CN.md",
    )


def p26_schema_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass_for_product_evidence_pack_depth_classification",
        "tables": [
            "product_evidence_depth_layers_p26",
            "product_evidence_depth_gaps_p26",
            "product_evidence_depth_gate_results_p26",
            "product_evidence_depth_reports_p26",
        ],
        "policy": {
            "product_kpi_exact_gap_blocks_exact_kpi_claims_only": True,
            "product_kpi_exact_gap_does_not_hide_product_profile_spec_graph": True,
            "customer_deployment_signal_gap_blocks_product_pack_broad_quality": True,
            "capital_market_detail_gap_is_cross_pack_not_product_pack_gate": True,
            "all_gaps_must_be_typed_before_p25_can_consume_p26": True,
        },
        "required_layers": [
            "product_profile_spec_graph",
            "product_relationship_graph",
            "product_kpi_exact_boundary",
            "customer_deployment_signal",
        ],
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _nested(payload: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return default
        current = current.get(key)
    return default if current is None else current


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def create_p26_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists product_evidence_depth_layers_p26 (
            layer_id text primary key,
            layer_name text not null,
            readiness_status text not null,
            product_pack_blocking integer not null,
            claim_boundary text not null,
            observed_value_json text not null default '{}',
            source_refs_json text not null default '[]',
            next_action text not null default '',
            created_at text not null
        );
        create table if not exists product_evidence_depth_gaps_p26 (
            gap_id text primary key,
            layer_id text not null,
            severity text not null,
            blocker_scope text not null,
            gap_class text not null,
            gap_count integer not null,
            observed_value_json text not null default '{}',
            next_action text not null default '',
            created_at text not null
        );
        create table if not exists product_evidence_depth_gate_results_p26 (
            gate_id text primary key,
            gate_name text not null,
            gate_group text not null,
            status text not null,
            detail_json text not null default '{}',
            created_at text not null
        );
        create table if not exists product_evidence_depth_reports_p26 (
            report_id text primary key,
            product_pack_readiness_status text not null,
            broad_full_chain_product_pack_ready integer not null,
            blocking_gap_count integer not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        """
    )


def clear_p26_rows(conn: sqlite3.Connection) -> None:
    for table in p26_schema_contract()["tables"]:
        conn.execute(f"delete from {table}")


def load_p26_inputs(root: Path) -> dict[str, dict[str, Any]]:
    manifest = root / "data" / "manifests"
    return {
        "depth_parity": _read_json(manifest / "second_third_layer_depth_parity_summary_v0_1.json"),
        "product_intelligence": _read_json(manifest / "product_intelligence_graph_summary_v0_1.json"),
    }


def build_p26_layer_rows(inputs: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    now = utc_now_iso()
    depth = inputs.get("depth_parity", {})
    pig = inputs.get("product_intelligence", {})
    metrics = depth.get("metrics") if isinstance(depth.get("metrics"), Mapping) else {}
    dimension_target_counts = metrics.get("dimension_target_met_counts") if isinstance(metrics.get("dimension_target_met_counts"), Mapping) else {}
    dimension_gap_counts = metrics.get("dimension_gap_counts") if isinstance(metrics.get("dimension_gap_counts"), Mapping) else {}
    dimension_gap_class_counts = (
        metrics.get("dimension_gap_class_counts") if isinstance(metrics.get("dimension_gap_class_counts"), Mapping) else {}
    )
    product_gap_classes = (
        dimension_gap_class_counts.get("product_kpi_depth")
        if isinstance(dimension_gap_class_counts.get("product_kpi_depth"), Mapping)
        else {}
    )

    company_count = _as_int(depth.get("company_count"))
    product_spec_ready_count = _as_int(dimension_target_counts.get("product_spec_depth"))
    product_kpi_ready_count = _as_int(dimension_target_counts.get("product_kpi_depth"))
    product_kpi_gap_count = _as_int(dimension_gap_counts.get("product_kpi_depth"))
    customer_ready_count = _as_int(dimension_target_counts.get("customer_deployment_depth"))
    customer_gap_count = _as_int(dimension_gap_counts.get("customer_deployment_depth"))
    capital_gap_count = _as_int(dimension_gap_counts.get("capital_market_detail_depth"))
    pig_company_pack_count = _as_int(pig.get("company_pack_count"))
    pig_company_count = _as_int(pig.get("company_count"))
    dangling_edges = _as_int(pig.get("dangling_edge_count"))
    invalid_edges = _as_int(pig.get("invalid_evidence_edge_count"))
    edge_count = _as_int(pig.get("edge_count"))
    node_count = _as_int(pig.get("node_count"))
    pig_gap_count = _as_int(pig.get("gap_count"))

    product_profile_graph_ready = (
        depth.get("status") == "pass"
        and company_count > 0
        and product_spec_ready_count == company_count
        and pig.get("status") == "pass"
        and pig_company_count == company_count
        and pig_company_pack_count == company_count
        and dangling_edges == 0
        and invalid_edges == 0
        and edge_count > 0
        and node_count > 0
    )
    product_kpi_gap_typed = product_kpi_gap_count == sum(_as_int(value) for key, value in product_gap_classes.items() if key != "none")
    product_kpi_boundary_ready = product_kpi_ready_count > 0 and product_kpi_gap_typed
    customer_ready = customer_gap_count == 0 and customer_ready_count == company_count
    relationship_graph_ready = pig.get("status") == "pass" and edge_count > 0 and dangling_edges == 0 and invalid_edges == 0

    def layer(
        layer_id: str,
        name: str,
        status: str,
        blocking: bool,
        boundary: str,
        observed: dict[str, Any],
        refs: list[str],
        next_action: str,
    ) -> dict[str, Any]:
        return {
            "layer_id": layer_id,
            "layer_name": name,
            "readiness_status": status,
            "product_pack_blocking": blocking,
            "claim_boundary": boundary,
            "observed_value": observed,
            "source_refs": refs,
            "next_action": next_action,
            "created_at": now,
        }

    return [
        layer(
            "product_profile_spec_graph",
            "Product profile / spec / ProductIntelligenceGraph surface",
            "ready" if product_profile_graph_ready else "blocked_product_profile_spec_graph_gap",
            not product_profile_graph_ready,
            "Supports product/service/asset profile, product family, specification, architecture, and relationship navigation; not exact revenue/share/ASP by itself.",
            {
                "company_count": company_count,
                "product_spec_ready_count": product_spec_ready_count,
                "pig_company_count": pig_company_count,
                "pig_company_pack_count": pig_company_pack_count,
                "pig_gap_count": pig_gap_count,
                "dangling_edge_count": dangling_edges,
                "invalid_evidence_edge_count": invalid_edges,
                "node_count": node_count,
                "edge_count": edge_count,
            },
            [
                "data/manifests/second_third_layer_depth_parity_summary_v0_1.json",
                "data/manifests/product_intelligence_graph_summary_v0_1.json",
            ],
            "Repair ProductIntelligenceGraph or product_spec_depth only if coverage/parity fails; do not use KPI gaps to hide product profile/spec readiness.",
        ),
        layer(
            "product_relationship_graph",
            "Product relationship / competitive / supply-chain graph",
            "ready" if relationship_graph_ready else "blocked_product_relationship_graph_gap",
            not relationship_graph_ready,
            "Supports bounded competition, substitution, upstream/downstream, deployment, and read-through reasoning; not standalone win/loss, market share, or revenue proof.",
            {
                "edge_count": edge_count,
                "node_count": node_count,
                "edge_type_counts": pig.get("edge_type_counts", {}),
                "authority_type_counts": pig.get("authority_type_counts", {}),
                "dangling_edge_count": dangling_edges,
                "invalid_evidence_edge_count": invalid_edges,
            },
            ["data/manifests/product_intelligence_graph_summary_v0_1.json"],
            "Repair dangling/invalid graph edges before using graph as product reasoning substrate.",
        ),
        layer(
            "product_kpi_exact_boundary",
            "Product-KPI exact / business metric boundary",
            "ready_with_typed_exact_kpi_gaps" if product_kpi_boundary_ready else "blocked_untyped_product_kpi_exact_gap",
            not product_kpi_boundary_ready,
            "Exact rows support disclosed product/business operating metrics. Missing exact KPI rows block exact KPI claims only; they do not erase product profile/spec/relationship evidence.",
            {
                "product_kpi_ready_count": product_kpi_ready_count,
                "product_kpi_gap_count": product_kpi_gap_count,
                "product_kpi_gap_class_counts": product_gap_classes,
                "product_kpi_gap_typed": product_kpi_gap_typed,
            },
            ["data/manifests/second_third_layer_depth_parity_summary_v0_1.json"],
            "Keep exact Product-KPI gaps as claim-scope restrictions; repair only untyped parser/join gaps or known-public exact rows.",
        ),
        layer(
            "customer_deployment_signal",
            "Customer deployment / adoption / distribution / operating-footprint signal",
            "ready" if customer_ready else "blocked_customer_deployment_signal_gap",
            not customer_ready,
            "Supports bounded customer deployment, adoption, channel, public order, regulated identity, or operating-footprint analysis; not revenue/backlog/order-value proof.",
            {
                "customer_deployment_ready_count": customer_ready_count,
                "customer_deployment_gap_count": customer_gap_count,
                "customer_deployment_gap_class_counts": (
                    dimension_gap_class_counts.get("customer_deployment_depth")
                    if isinstance(dimension_gap_class_counts.get("customer_deployment_depth"), Mapping)
                    else {}
                ),
            },
            ["data/manifests/second_third_layer_depth_parity_summary_v0_1.json"],
            "Continue targeted official customer/deployment, channel/distribution, regulated identity, public award/tender, and lane-specific operating-footprint adapters for the missing companies.",
        ),
        layer(
            "capital_market_detail_cross_pack_dependency",
            "Capital-market detail residual cross-pack dependency",
            "out_of_scope_for_product_pack" if capital_gap_count else "ready",
            False,
            "Capital-market detail belongs to capital/financing packs. It should not block the product evidence pack, but remains visible for B05/P25 cross-pack planning.",
            {
                "capital_market_detail_gap_count": capital_gap_count,
                "capital_market_detail_gap_class_counts": (
                    dimension_gap_class_counts.get("capital_market_detail_depth")
                    if isinstance(dimension_gap_class_counts.get("capital_market_detail_depth"), Mapping)
                    else {}
                ),
            },
            ["data/manifests/second_third_layer_depth_parity_summary_v0_1.json"],
            "Route residual capital detail gaps to capital/funding pack repair, not ProductEvidencePack readiness.",
        ),
    ]


def build_p26_gap_rows(layer_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    now = utc_now_iso()
    rows: list[dict[str, Any]] = []
    for layer in layer_rows:
        observed = layer["observed_value"]
        if layer["layer_id"] == "product_kpi_exact_boundary" and _as_int(observed.get("product_kpi_gap_count")):
            rows.append(
                {
                    "gap_id": "p26_product_kpi_exact_typed_gap",
                    "layer_id": layer["layer_id"],
                    "severity": "nonblocking_claim_scope_gap"
                    if layer["readiness_status"] == "ready_with_typed_exact_kpi_gaps"
                    else "blocking_untyped_gap",
                    "blocker_scope": "exact_product_kpi_claims_only"
                    if layer["readiness_status"] == "ready_with_typed_exact_kpi_gaps"
                    else "product_pack_until_typed",
                    "gap_class": "typed_product_kpi_exact_gap",
                    "gap_count": _as_int(observed.get("product_kpi_gap_count")),
                    "observed_value": observed,
                    "next_action": layer["next_action"],
                    "created_at": now,
                }
            )
        if layer["layer_id"] == "customer_deployment_signal" and _as_int(observed.get("customer_deployment_gap_count")):
            rows.append(
                {
                    "gap_id": "p26_customer_deployment_signal_gap",
                    "layer_id": layer["layer_id"],
                    "severity": "blocking_product_pack_gap",
                    "blocker_scope": "product_pack_broad_full_chain_quality",
                    "gap_class": "customer_deployment_public_source_or_adapter_gap",
                    "gap_count": _as_int(observed.get("customer_deployment_gap_count")),
                    "observed_value": observed,
                    "next_action": layer["next_action"],
                    "created_at": now,
                }
            )
        if layer["layer_id"] == "capital_market_detail_cross_pack_dependency" and _as_int(observed.get("capital_market_detail_gap_count")):
            rows.append(
                {
                    "gap_id": "p26_capital_market_detail_cross_pack_gap",
                    "layer_id": layer["layer_id"],
                    "severity": "cross_pack_nonblocking_for_product_pack",
                    "blocker_scope": "capital_or_funding_pack",
                    "gap_class": "capital_market_detail_residual_gap",
                    "gap_count": _as_int(observed.get("capital_market_detail_gap_count")),
                    "observed_value": observed,
                    "next_action": layer["next_action"],
                    "created_at": now,
                }
            )
    return rows


def build_p26_gate_rows(layer_rows: list[dict[str, Any]], gap_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    now = utc_now_iso()
    layer_by_id = {row["layer_id"]: row for row in layer_rows}
    required_layers = p26_schema_contract()["required_layers"]
    missing_layers = [layer for layer in required_layers if layer not in layer_by_id]
    blocking_layers = [row["layer_id"] for row in layer_rows if row["product_pack_blocking"]]
    exact_kpi_gap = next((row for row in gap_rows if row["gap_id"] == "p26_product_kpi_exact_typed_gap"), None)
    customer_gap = next((row for row in gap_rows if row["gap_id"] == "p26_customer_deployment_signal_gap"), None)

    def gate(gate_id: str, group: str, status: str, detail: dict[str, Any]) -> dict[str, Any]:
        return {
            "gate_id": gate_id,
            "gate_name": gate_id,
            "gate_group": group,
            "status": status,
            "detail": detail,
            "created_at": now,
        }

    return [
        gate(
            "p26_required_layers_present",
            "coverage",
            "pass" if not missing_layers else "fail",
            {"required_layers": required_layers, "missing_layers": missing_layers},
        ),
        gate(
            "p26_product_profile_spec_graph_ready",
            "product_intelligence",
            "pass" if layer_by_id.get("product_profile_spec_graph", {}).get("readiness_status") == "ready" else "fail",
            {"layer": layer_by_id.get("product_profile_spec_graph", {})},
        ),
        gate(
            "p26_product_kpi_exact_gap_is_claim_scope_only",
            "claim_boundary",
            "pass" if not exact_kpi_gap or exact_kpi_gap["blocker_scope"] == "exact_product_kpi_claims_only" else "fail",
            {"product_kpi_exact_gap": exact_kpi_gap},
        ),
        gate(
            "p26_customer_deployment_gap_blocks_product_pack",
            "release_boundary",
            "blocked" if customer_gap else "pass",
            {"customer_deployment_gap": customer_gap},
        ),
        gate(
            "p26_capital_gap_not_product_pack_gate",
            "cross_pack_boundary",
            "pass",
            {"capital_gap": next((row for row in gap_rows if row["gap_id"] == "p26_capital_market_detail_cross_pack_gap"), None)},
        ),
        gate(
            "p26_product_pack_ready_for_broad_full_chain",
            "release_boundary",
            "blocked" if blocking_layers else "pass",
            {"blocking_layers": blocking_layers},
        ),
    ]


def persist_p26_rows(
    paths: P26Paths,
    layer_rows: list[dict[str, Any]],
    gap_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    with _connect(paths.db_path) as conn:
        create_p26_schema(conn)
        clear_p26_rows(conn)
        for row in layer_rows:
            conn.execute(
                """
                insert into product_evidence_depth_layers_p26(
                    layer_id, layer_name, readiness_status, product_pack_blocking, claim_boundary,
                    observed_value_json, source_refs_json, next_action, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["layer_id"],
                    row["layer_name"],
                    row["readiness_status"],
                    int(bool(row["product_pack_blocking"])),
                    row["claim_boundary"],
                    _json_dumps(row["observed_value"]),
                    _json_dumps(row["source_refs"]),
                    row["next_action"],
                    row["created_at"],
                ),
            )
        for row in gap_rows:
            conn.execute(
                """
                insert into product_evidence_depth_gaps_p26(
                    gap_id, layer_id, severity, blocker_scope, gap_class, gap_count,
                    observed_value_json, next_action, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["gap_id"],
                    row["layer_id"],
                    row["severity"],
                    row["blocker_scope"],
                    row["gap_class"],
                    row["gap_count"],
                    _json_dumps(row["observed_value"]),
                    row["next_action"],
                    row["created_at"],
                ),
            )
        for row in gate_rows:
            conn.execute(
                """
                insert into product_evidence_depth_gate_results_p26(
                    gate_id, gate_name, gate_group, status, detail_json, created_at
                ) values (?, ?, ?, ?, ?, ?)
                """,
                (row["gate_id"], row["gate_name"], row["gate_group"], row["status"], _json_dumps(row["detail"]), row["created_at"]),
            )
        conn.execute(
            """
            insert into product_evidence_depth_reports_p26(
                report_id, product_pack_readiness_status, broad_full_chain_product_pack_ready,
                blocking_gap_count, payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?)
            """,
            (
                P26_REPORT_ID,
                summary["product_pack_readiness_status"],
                int(bool(summary["broad_full_chain_product_pack_ready"])),
                summary["counts"]["blocking_gap_count"],
                _json_dumps({"counts": summary["counts"], "outputs": summary["outputs"]}),
                summary["generated_at"],
            ),
        )


def build_p26_product_evidence_depth_gate(root: Path) -> dict[str, Any]:
    root = root.resolve()
    paths = default_p26_paths(root)
    paths.schema_path.parent.mkdir(parents=True, exist_ok=True)
    paths.layer_rows_path.parent.mkdir(parents=True, exist_ok=True)
    paths.report_path.parent.mkdir(parents=True, exist_ok=True)

    inputs = load_p26_inputs(root)
    layer_rows = build_p26_layer_rows(inputs)
    gap_rows = build_p26_gap_rows(layer_rows)
    gate_rows = build_p26_gate_rows(layer_rows, gap_rows)
    gate_fail_count = sum(1 for row in gate_rows if row["status"] == "fail")
    gate_blocked_count = sum(1 for row in gate_rows if row["status"] == "blocked")
    blocking_gap_rows = [row for row in gap_rows if row["severity"].startswith("blocking")]
    blocking_layers = [row for row in layer_rows if row["product_pack_blocking"]]
    broad_ready = gate_fail_count == 0 and not blocking_gap_rows and not blocking_layers
    generated_at = utc_now_iso()
    if broad_ready:
        readiness = "ready"
        decision = "P26_product_evidence_pack_ready_for_broad_full_chain"
    elif gate_fail_count:
        readiness = "failed_contract_or_untyped_gap"
        decision = "P26_product_evidence_pack_gate_failed"
    else:
        readiness = "blocked_customer_deployment_signal_gap"
        decision = "P26_product_evidence_pack_blocked_customer_deployment_gap"

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if broad_ready else ("fail" if gate_fail_count else "pass_with_product_pack_blocker_registered"),
        "release_decision": decision,
        "closeout_level": "L4_scope_pass_for_product_evidence_pack_depth_classification",
        "product_pack_readiness_status": readiness,
        "broad_full_chain_product_pack_ready": broad_ready,
        "counts": {
            "layer_count": len(layer_rows),
            "gap_count": len(gap_rows),
            "blocking_gap_count": len(blocking_gap_rows),
            "nonblocking_gap_count": len(gap_rows) - len(blocking_gap_rows),
            "blocking_layer_count": len(blocking_layers),
            "gate_count": len(gate_rows),
            "gate_fail_count": gate_fail_count,
            "gate_blocked_count": gate_blocked_count,
        },
        "layer_readiness": {row["layer_id"]: row["readiness_status"] for row in layer_rows},
        "blocking_gap_ids": [row["gap_id"] for row in blocking_gap_rows],
        "claim_boundary_policy": {
            "product_kpi_exact_gap_blocks_exact_kpi_claims_only": True,
            "capital_market_detail_gap_is_cross_pack_dependency": True,
            "customer_deployment_gap_blocks_product_pack_broad_quality": bool(blocking_gap_rows),
        },
        "known_gaps": [
            {
                "gap": row["gap_id"],
                "layer_id": row["layer_id"],
                "severity": row["severity"],
                "blocker_scope": row["blocker_scope"],
                "gap_count": row["gap_count"],
                "next_action": row["next_action"],
                "observed_value": row["observed_value"],
            }
            for row in gap_rows
        ],
        "outputs": {
            "schema": rel_path(paths.schema_path, root),
            "layer_rows": rel_path(paths.layer_rows_path, root),
            "gap_rows": rel_path(paths.gap_rows_path, root),
            "gate_rows": rel_path(paths.gate_rows_path, root),
            "summary": rel_path(paths.summary_path, root),
            "report": rel_path(paths.report_path, root),
            "runtime_db": rel_path(paths.db_path, root),
        },
    }
    persist_p26_rows(paths, layer_rows, gap_rows, gate_rows, summary)
    write_json(paths.schema_path, p26_schema_contract())
    write_jsonl(paths.layer_rows_path, layer_rows)
    write_jsonl(paths.gap_rows_path, gap_rows)
    write_jsonl(paths.gate_rows_path, gate_rows)
    write_json(paths.summary_path, summary)
    paths.report_path.write_text(render_p26_report(summary, layer_rows, gap_rows, gate_rows), encoding="utf-8")
    return summary


def render_p26_report(
    summary: dict[str, Any],
    layer_rows: list[dict[str, Any]],
    gap_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
) -> str:
    lines = [
        "# R53-R60 P26 Product Evidence All-Universe Depth Gate",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Release decision: `{summary['release_decision']}`",
        f"- Product pack readiness: `{summary['product_pack_readiness_status']}`",
        f"- Broad full-chain product pack ready: `{summary['broad_full_chain_product_pack_ready']}`",
        "",
        "## Counts",
        "",
    ]
    for key, value in summary["counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Layers", ""])
    for row in layer_rows:
        marker = "blocking" if row["product_pack_blocking"] else "nonblocking"
        lines.append(f"- `{row['layer_id']}`: `{row['readiness_status']}` / `{marker}`")
    lines.extend(["", "## Gaps", ""])
    for row in gap_rows:
        lines.append(f"- `{row['gap_id']}`: `{row['severity']}` / `{row['blocker_scope']}` / count `{row['gap_count']}`")
    lines.extend(["", "## Gates", ""])
    for row in gate_rows:
        lines.append(f"- `{row['gate_id']}`: `{row['status']}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "P26 deliberately separates Product-KPI exact coverage from the rest of product intelligence. Missing exact Product-KPI rows block exact KPI claims, not product profile/spec/relationship reasoning. Customer/deployment/adoption gaps still block broad product-pack quality until real source/adapter repair or an accepted public/commercial boundary is recorded.",
            "",
            "P26 把 Product-KPI exact 和产品画像/规格/关系图谱拆开：缺 SKU/产品线 exact KPI 不能写成精确收入、出货、ASP、份额，但不能抹掉已经存在的产品规格、架构、部署、竞争和供应链证据。CustomerDeployment 仍是产品包 broad quality 的真实 blocker。",
            "",
        ]
    )
    return "\n".join(lines)


__all__ = [
    "SCHEMA_VERSION",
    "P26Paths",
    "build_p26_product_evidence_depth_gate",
    "build_p26_layer_rows",
    "build_p26_gap_rows",
    "build_p26_gate_rows",
    "create_p26_schema",
    "default_p26_paths",
    "p26_schema_contract",
]
