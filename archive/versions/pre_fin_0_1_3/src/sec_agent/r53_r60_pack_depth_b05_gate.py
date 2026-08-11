"""P25 / B05 pack-depth gate before broad full-chain regression.

B05 is not a data backfill shortcut.  It verifies whether the upstream packs
that broad full-chain cases would consume are deep enough to support research
quality claims, and records the exact blocker when they are not.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from sec_agent.r53_r60_runtime_task_spine import default_s1_paths, rel_path, utc_now_iso, write_json, write_jsonl


SCHEMA_VERSION = "r53_r60_p25_b05_pack_depth_gate_v0_1"
P25_REPORT_ID = "p25_b05_pack_depth_gate_report_v0_1"


@dataclass(frozen=True)
class P25Paths:
    db_path: Path
    schema_path: Path
    pack_rows_path: Path
    requirement_rows_path: Path
    gate_rows_path: Path
    summary_path: Path
    report_path: Path


def default_p25_paths(root: Path) -> P25Paths:
    s1_paths = default_s1_paths(root)
    return P25Paths(
        db_path=s1_paths.db_path,
        schema_path=root / "configs" / "r53_r60" / "p25_b05_pack_depth_gate_schema_v0_1.json",
        pack_rows_path=root / "data" / "manifests" / "r53_r60_p25_b05_pack_depth_assessment_rows_v0_1.jsonl",
        requirement_rows_path=root / "data" / "manifests" / "r53_r60_p25_b05_pack_depth_requirement_rows_v0_1.jsonl",
        gate_rows_path=root / "data" / "manifests" / "r53_r60_p25_b05_pack_depth_gate_rows_v0_1.jsonl",
        summary_path=root / "data" / "manifests" / "r53_r60_p25_b05_pack_depth_summary_v0_1.json",
        report_path=root / "docs" / "internal" / "vnext_20260610" / "r53_r60_p25_b05_pack_depth_gate_blocked.zh-CN.md",
    )


def p25_schema_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass_for_pack_depth_blocker_registration_only",
        "release_scope": "b05_pack_level_depth_readiness_gate",
        "tables": [
            "pack_depth_assessments_p25",
            "pack_depth_requirements_p25",
            "pack_depth_gate_results_p25",
            "pack_depth_reports_p25",
        ],
        "policy": {
            "broad_full_chain_requires_all_required_packs_ready": True,
            "scope_pass_slices_do_not_equal_depth_pass": True,
            "typed_gap_required_for_public_or_commercial_boundary": True,
            "route_or_seed_only_never_counts_as_depth": True,
            "blocked_packs_must_report_next_repair": True,
        },
        "required_packs": [
            "product_evidence_pack_all_universe",
            "ai_semis_product_evidence_pack",
            "secondary_market_capital_feedback_pack",
            "research_to_quant_lab_pack",
            "deliverable_studio_pack",
            "retrieval_data_refresh_pack",
        ],
    }


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


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


def create_p25_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists pack_depth_assessments_p25 (
            pack_id text primary key,
            pack_name text not null,
            pack_group text not null,
            readiness_status text not null,
            broad_full_chain_ready integer not null,
            evidence_summary_json text not null default '{}',
            blocker_summary_json text not null default '{}',
            source_refs_json text not null default '[]',
            next_actions_json text not null default '[]',
            created_at text not null
        );
        create table if not exists pack_depth_requirements_p25 (
            requirement_id text primary key,
            pack_id text not null,
            requirement text not null,
            status text not null,
            observed_value_json text not null default '{}',
            pass_condition text not null,
            blocker_type text not null default '',
            next_action text not null default '',
            created_at text not null
        );
        create table if not exists pack_depth_gate_results_p25 (
            gate_id text primary key,
            gate_name text not null,
            gate_group text not null,
            status text not null,
            detail_json text not null default '{}',
            created_at text not null
        );
        create table if not exists pack_depth_reports_p25 (
            report_id text primary key,
            release_decision text not null,
            closeout_level text not null,
            b05_status_after_p25 text not null,
            broad_full_chain_quality_eval_allowed integer not null,
            blocked_pack_count integer not null,
            payload_json text not null default '{}',
            created_at text not null
        );
        """
    )


def clear_p25_rows(conn: sqlite3.Connection) -> None:
    for table in p25_schema_contract()["tables"]:
        conn.execute(f"delete from {table}")


def load_p25_inputs(root: Path) -> dict[str, dict[str, Any]]:
    manifest = root / "data" / "manifests"
    return {
        "depth_parity": _read_json(manifest / "second_third_layer_depth_parity_summary_v0_1.json"),
        "ai_semis_product": _read_json(manifest / "ai_semis_product_depth_gate_v0_2.json"),
        "s7_deliverable": _read_json(manifest / "r53_r60_s7_deliverable_studio_dashboard_summary_v0_1.json"),
        "s8_secondary": _read_json(manifest / "r53_r60_s8_secondary_market_capital_feedback_summary_v0_1.json"),
        "s9_quant": _read_json(manifest / "r53_r60_s9_research_to_quant_lab_summary_v0_1.json"),
        "p14_data": _read_json(manifest / "r53_r60_p14_data_ingestion_retrieval_control_plane_summary_v0_1.json"),
        "p26_product_evidence": _read_json(
            manifest / "r53_r60_p26_product_evidence_all_universe_depth_summary_v0_1.json"
        ),
    }


def build_pack_assessment_rows(root: Path, inputs: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    now = utc_now_iso()
    depth = inputs.get("depth_parity", {})
    depth_metrics = depth.get("metrics") if isinstance(depth.get("metrics"), Mapping) else {}
    ai_semis = inputs.get("ai_semis_product", {})
    s7 = inputs.get("s7_deliverable", {})
    s8 = inputs.get("s8_secondary", {})
    s9 = inputs.get("s9_quant", {})
    p14 = inputs.get("p14_data", {})
    p26_product_evidence = inputs.get("p26_product_evidence", {})

    full_depth_count = _as_int(depth_metrics.get("full_depth_target_met_company_count"))
    company_count = _as_int(depth.get("company_count"))
    full_gap_count = _as_int(depth_metrics.get("full_depth_target_gap_company_count"))
    dimension_gap_counts = dict(depth_metrics.get("dimension_gap_counts") or {})
    all_missing_classified = bool(_nested(depth, "checks", "all_missing_depth_is_classified", default=False))
    depth_ready = bool(company_count and full_depth_count == company_count and full_gap_count == 0)

    ai_company_count = _as_int(ai_semis.get("company_count"))
    ai_gap_queue = _as_int(ai_semis.get("gap_queue_count"))
    ai_strict_pass = _as_int(_nested(ai_semis, "strict_depth_status_counts", "pass", default=0))
    ai_ready = ai_semis.get("status") == "pass" and ai_company_count > 0 and ai_gap_queue == 0 and ai_strict_pass == ai_company_count

    s8_role_gap_counts = dict(s8.get("role_gap_counts") or {})
    s8_required_missing_roles = {
        key: value for key, value in s8_role_gap_counts.items() if key in {"credit_funding", "derivatives_market_signal", "valuation_price_in"} and _as_int(value) > 0
    }
    s8_ready = s8.get("status") == "pass" and not s8_required_missing_roles

    s9_counts = s9.get("counts") if isinstance(s9.get("counts"), Mapping) else {}
    s9_ready = (
        s9.get("status") == "pass"
        and _as_int(s9_counts.get("approved_factor_count")) >= 2
        and _as_int(s9_counts.get("backtest_result_count")) >= 2
        and bool(s9_counts.get("no_live_trading")) is True
    )

    s7_counts = s7.get("counts") if isinstance(s7.get("counts"), Mapping) else {}
    s7_customer_ready = bool(s7.get("customer_ready_editorial_quality_pass") or False)
    s7_ready = s7.get("status") == "pass" and s7_customer_ready

    p14_policy = p14.get("policy") if isinstance(p14.get("policy"), Mapping) else {}
    p14_ready = (
        p14.get("status") == "pass"
        and p14.get("source_snapshot_status") == "source_snapshots_ready"
        and p14.get("parser_contract_status") == "parser_contracts_ready"
        and p14.get("current_universe_refresh_status") == "current_accepted_public_source_universe_ready"
    )

    p26_available = bool(p26_product_evidence)
    p26_ready = bool(p26_product_evidence.get("broad_full_chain_product_pack_ready")) if p26_available else False
    p26_readiness_status = str(p26_product_evidence.get("product_pack_readiness_status") or "")
    if p26_available:
        product_pack_ready = p26_ready
        product_pack_status = "ready" if p26_ready else (p26_readiness_status or "blocked_product_evidence_depth_gap")
        product_evidence_summary = {
            "p26_status": p26_product_evidence.get("status"),
            "p26_release_decision": p26_product_evidence.get("release_decision"),
            "product_pack_readiness_status": p26_product_evidence.get("product_pack_readiness_status"),
            "broad_full_chain_product_pack_ready": p26_product_evidence.get("broad_full_chain_product_pack_ready"),
            "p26_counts": p26_product_evidence.get("counts", {}),
            "p26_layer_readiness": p26_product_evidence.get("layer_readiness", {}),
            "p26_claim_boundary_policy": p26_product_evidence.get("claim_boundary_policy", {}),
            "legacy_depth_snapshot": {
                "company_count": company_count,
                "full_depth_target_met_company_count": full_depth_count,
                "full_depth_target_gap_company_count": full_gap_count,
                "dimension_gap_counts": dimension_gap_counts,
                "all_missing_depth_is_classified": all_missing_classified,
            },
        }
        product_blocker_summary = {
            "p26_known_gaps": p26_product_evidence.get("known_gaps", []),
            "p26_blocking_gap_ids": p26_product_evidence.get("blocking_gap_ids", []),
            "p26_release_decision": p26_product_evidence.get("release_decision"),
            "legacy_parity_status": depth.get("parity_status"),
            "legacy_remaining_gap_count": full_gap_count,
        }
        product_source_refs = [
            "data/manifests/r53_r60_p26_product_evidence_all_universe_depth_summary_v0_1.json",
            "data/manifests/second_third_layer_depth_parity_summary_v0_1.json",
            "data/manifests/product_intelligence_graph_summary_v0_1.json",
        ]
        if product_pack_ready:
            product_next_actions = [
                "Use P26 as the ProductEvidencePack depth boundary: Product-KPI exact gaps block exact KPI claims only.",
                "CustomerDeployment/adoption depth is closed for the 603-company universe; keep residual exact KPI gaps as claim-scope limits, not product-pack blockers.",
            ]
        else:
            product_next_actions = [
                "Use P26 as the ProductEvidencePack depth boundary: Product-KPI exact gaps block exact KPI claims only; CustomerDeployment signal gaps still block broad product-pack quality.",
                "Continue targeted official customer/deployment, channel/distribution, regulated identity, public award/tender, and lane-specific operating-footprint adapters until P26 broad_full_chain_product_pack_ready=true.",
            ]
    else:
        product_pack_ready = depth_ready
        product_pack_status = "ready" if depth_ready else "blocked_full_universe_depth_gap"
        product_evidence_summary = {
            "company_count": company_count,
            "full_depth_target_met_company_count": full_depth_count,
            "full_depth_target_gap_company_count": full_gap_count,
            "dimension_gap_counts": dimension_gap_counts,
            "all_missing_depth_is_classified": all_missing_classified,
            "p26_product_evidence_summary_missing": True,
        }
        product_blocker_summary = {
            "remaining_gap_count": full_gap_count,
            "gap_by_dimension": dimension_gap_counts,
            "parity_status": depth.get("parity_status"),
        }
        product_source_refs = ["data/manifests/second_third_layer_depth_parity_summary_v0_1.json"]
        product_next_actions = [
            "Build P26 ProductEvidence all-universe depth split before using P25 for product pack closeout.",
            "Continue targeted adapter/parser repair for Product-KPI exact, CustomerDeployment and remaining capital detail gaps.",
            "Do not treat classified gap audit pass as full-depth pass.",
        ]

    def row(
        pack_id: str,
        pack_name: str,
        pack_group: str,
        readiness_status: str,
        ready: bool,
        evidence_summary: dict[str, Any],
        blocker_summary: dict[str, Any],
        source_refs: list[str],
        next_actions: list[str],
    ) -> dict[str, Any]:
        return {
            "pack_id": pack_id,
            "pack_name": pack_name,
            "pack_group": pack_group,
            "readiness_status": readiness_status,
            "broad_full_chain_ready": ready,
            "evidence_summary": evidence_summary,
            "blocker_summary": blocker_summary,
            "source_refs": source_refs,
            "next_actions": next_actions,
            "created_at": now,
        }

    return [
        row(
            "product_evidence_pack_all_universe",
            "603-company ProductEvidencePack all-universe depth matrix",
            "product_data_depth",
            product_pack_status,
            product_pack_ready,
            product_evidence_summary,
            product_blocker_summary,
            product_source_refs,
            product_next_actions,
        ),
        row(
            "ai_semis_product_evidence_pack",
            "AI / Semis product intelligence depth pack",
            "product_data_depth",
            "ready" if ai_ready else "blocked_ai_semis_depth_gap",
            ai_ready,
            {
                "company_count": ai_company_count,
                "gap_queue_count": ai_gap_queue,
                "strict_depth_status_counts": ai_semis.get("strict_depth_status_counts", {}),
                "layer_status_counts": ai_semis.get("layer_status_counts", {}),
            },
            {"gap_reason_counts": ai_semis.get("gap_reason_counts", {})},
            ["data/manifests/ai_semis_product_depth_gate_v0_2.json"],
            ["Keep AI/Semis pack as representative domain-depth pass; do not generalize it to all 603 companies."],
        ),
        row(
            "secondary_market_capital_feedback_pack",
            "Secondary Market / Capital Feedback Pack",
            "secondary_market_depth",
            "ready" if s8_ready else "blocked_missing_secondary_market_roles",
            s8_ready,
            {
                "pack_count": _nested(s8, "counts", "pack_count", default=0),
                "signal_count": _nested(s8, "counts", "signal_count", default=0),
                "role_signal_counts": s8.get("role_signal_counts", {}),
                "role_gap_counts": s8_role_gap_counts,
            },
            {
                "missing_required_roles": s8_required_missing_roles,
                "boundary": s8.get("boundary", ""),
            },
            ["data/manifests/r53_r60_s8_secondary_market_capital_feedback_summary_v0_1.json"],
            [
                "Backfill or explicitly commercial-bound credit funding, derivatives, valuation and positioning roles.",
                "Keep delayed/lagged market rows as market context, not company fundamental proof.",
            ],
        ),
        row(
            "research_to_quant_lab_pack",
            "Research-to-Quant Lab Pack",
            "quant_depth",
            "ready" if s9_ready else "blocked_quant_scope_or_approval_gap",
            s9_ready,
            {
                "approved_factor_count": s9_counts.get("approved_factor_count"),
                "backtest_result_count": s9_counts.get("backtest_result_count"),
                "factor_card_count": s9_counts.get("factor_card_count"),
                "no_live_trading": s9_counts.get("no_live_trading"),
                "experience_outcomes": s9.get("experience_outcomes", {}),
            },
            {
                "boundary": "S9 validates research-to-quant plumbing only; it is not production alpha, live trading, or complete security master.",
                "blocked_factor_count": s9_counts.get("blocked_factor_count"),
            },
            ["data/manifests/r53_r60_s9_research_to_quant_lab_summary_v0_1.json"],
            [
                "Treat S9 as internal quant-validation plumbing until security master, broader datasets and human approvals are expanded.",
            ],
        ),
        row(
            "deliverable_studio_pack",
            "Deliverable Studio / Dashboard Projection Pack",
            "deliverable_depth",
            "ready" if s7_ready else "blocked_human_editorial_acceptance_gap",
            s7_ready,
            {
                "render_jobs": _nested(s7, "counts", "render_jobs_s7", default=0),
                "deliverable_quality_gates": _nested(s7, "counts", "deliverable_quality_gates_s7", default=0),
                "gate_fail_count": _nested(s7, "counts", "gate_fail_count", default=0),
                "output_formats": [item.get("output_format") for item in s7.get("render_jobs", []) if isinstance(item, Mapping)],
            },
            {
                "boundary": s7.get("boundary", ""),
                "customer_ready_editorial_quality_pass": s7_customer_ready,
            },
            ["data/manifests/r53_r60_s7_deliverable_studio_dashboard_summary_v0_1.json"],
            [
                "Run real deliverable accept/reject and editorial/readability review before using broad full-chain outputs as product quality proof.",
            ],
        ),
        row(
            "retrieval_data_refresh_pack",
            "Data ingestion / retrieval refresh pack",
            "data_rag_depth",
            "ready" if p14_ready else "blocked_live_refresh_or_full_crawler_gap",
            p14_ready,
            {
                "source_snapshot_status": p14.get("source_snapshot_status"),
                "parser_contract_status": p14.get("parser_contract_status"),
                "retrieval_control_status": p14.get("retrieval_control_status"),
                "lineage_status": p14.get("lineage_status"),
                "context_bridge_status": p14.get("context_bridge_status"),
                "current_universe_refresh_status": p14.get("current_universe_refresh_status"),
                "current_universe_refresh_evidence_count": len(p14.get("current_universe_refresh_evidence") or []),
            },
            {
                "policy": p14_policy,
                "known_p14_gaps": _nested(p14, "readiness_report", "known_gaps_json", default="[]"),
            },
            ["data/manifests/r53_r60_p14_data_ingestion_retrieval_control_plane_summary_v0_1.json"],
            [
                "Keep accepted-universe manifests refreshed before broad full-chain quality claims; real-time/full internet crawler and production p95/p99 remain separate production gates.",
            ],
        ),
    ]


def build_requirement_rows(pack_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    now = utc_now_iso()
    rows: list[dict[str, Any]] = []
    for pack in pack_rows:
        pack_id = pack["pack_id"]
        ready = bool(pack["broad_full_chain_ready"])
        rows.append(
            {
                "requirement_id": f"p25_req_{pack_id}",
                "pack_id": pack_id,
                "requirement": f"{pack['pack_name']} must be broad-full-chain ready or remain a typed blocker.",
                "status": "pass" if ready else "blocked",
                "observed_value": {
                    "readiness_status": pack["readiness_status"],
                    "evidence_summary": pack["evidence_summary"],
                    "blocker_summary": pack["blocker_summary"],
                },
                "pass_condition": "broad_full_chain_ready == true",
                "blocker_type": "" if ready else pack["readiness_status"],
                "next_action": "; ".join(pack["next_actions"]),
                "created_at": now,
            }
        )
    return rows


def build_gate_rows(pack_rows: list[dict[str, Any]], requirement_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    now = utc_now_iso()
    blocked_packs = [row for row in pack_rows if not row["broad_full_chain_ready"]]
    missing_source_refs = [row["pack_id"] for row in pack_rows if not row["source_refs"]]
    typed_blockers = [row for row in requirement_rows if row["status"] == "blocked" and row["blocker_type"]]

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
            "p25_required_packs_assessed",
            "coverage",
            "pass" if len(pack_rows) == len(p25_schema_contract()["required_packs"]) else "fail",
            {"pack_count": len(pack_rows), "required_packs": p25_schema_contract()["required_packs"]},
        ),
        gate(
            "p25_pack_source_refs_present",
            "provenance",
            "pass" if not missing_source_refs else "fail",
            {"missing_source_refs": missing_source_refs},
        ),
        gate(
            "p25_blocked_packs_have_typed_requirements",
            "blocker_typing",
            "pass" if len(typed_blockers) == len(blocked_packs) else "fail",
            {"blocked_pack_count": len(blocked_packs), "typed_blocker_count": len(typed_blockers)},
        ),
        gate(
            "p25_broad_full_chain_depth_ready",
            "release_boundary",
            "blocked" if blocked_packs else "pass",
            {"blocked_packs": [row["pack_id"] for row in blocked_packs]},
        ),
        gate(
            "p25_b05_remains_open_until_all_packs_ready",
            "release_boundary",
            "pass",
            {"b05_status_after_p25": "open_pack_level_depth_required" if blocked_packs else "closed_by_p25_pack_depth_ready"},
        ),
    ]


def persist_p25_rows(
    paths: P25Paths,
    pack_rows: list[dict[str, Any]],
    requirement_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    with _connect(paths.db_path) as conn:
        create_p25_schema(conn)
        clear_p25_rows(conn)
        for row in pack_rows:
            conn.execute(
                """
                insert into pack_depth_assessments_p25(
                    pack_id, pack_name, pack_group, readiness_status, broad_full_chain_ready,
                    evidence_summary_json, blocker_summary_json, source_refs_json, next_actions_json, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["pack_id"],
                    row["pack_name"],
                    row["pack_group"],
                    row["readiness_status"],
                    int(bool(row["broad_full_chain_ready"])),
                    _json_dumps(row["evidence_summary"]),
                    _json_dumps(row["blocker_summary"]),
                    _json_dumps(row["source_refs"]),
                    _json_dumps(row["next_actions"]),
                    row["created_at"],
                ),
            )
        for row in requirement_rows:
            conn.execute(
                """
                insert into pack_depth_requirements_p25(
                    requirement_id, pack_id, requirement, status, observed_value_json,
                    pass_condition, blocker_type, next_action, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["requirement_id"],
                    row["pack_id"],
                    row["requirement"],
                    row["status"],
                    _json_dumps(row["observed_value"]),
                    row["pass_condition"],
                    row["blocker_type"],
                    row["next_action"],
                    row["created_at"],
                ),
            )
        for row in gate_rows:
            conn.execute(
                """
                insert into pack_depth_gate_results_p25(
                    gate_id, gate_name, gate_group, status, detail_json, created_at
                ) values (?, ?, ?, ?, ?, ?)
                """,
                (row["gate_id"], row["gate_name"], row["gate_group"], row["status"], _json_dumps(row["detail"]), row["created_at"]),
            )
        conn.execute(
            """
            insert into pack_depth_reports_p25(
                report_id, release_decision, closeout_level, b05_status_after_p25,
                broad_full_chain_quality_eval_allowed, blocked_pack_count, payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                P25_REPORT_ID,
                summary["release_decision"],
                summary["closeout_level"],
                summary["b05_status_after_p25"],
                int(bool(summary["broad_full_chain_quality_eval_allowed"])),
                summary["counts"]["blocked_pack_count"],
                _json_dumps({"counts": summary["counts"], "outputs": summary["outputs"]}),
                summary["generated_at"],
            ),
        )


def build_p25_pack_depth_gate(root: Path) -> dict[str, Any]:
    root = root.resolve()
    paths = default_p25_paths(root)
    paths.schema_path.parent.mkdir(parents=True, exist_ok=True)
    paths.pack_rows_path.parent.mkdir(parents=True, exist_ok=True)
    paths.report_path.parent.mkdir(parents=True, exist_ok=True)

    inputs = load_p25_inputs(root)
    pack_rows = build_pack_assessment_rows(root, inputs)
    requirement_rows = build_requirement_rows(pack_rows)
    gate_rows = build_gate_rows(pack_rows, requirement_rows)

    gate_fail_count = sum(1 for row in gate_rows if row["status"] == "fail")
    gate_blocked_count = sum(1 for row in gate_rows if row["status"] == "blocked")
    blocked_pack_count = sum(1 for row in pack_rows if not row["broad_full_chain_ready"])
    ready_pack_count = len(pack_rows) - blocked_pack_count
    blocked_pack_ids = [row["pack_id"] for row in pack_rows if not row["broad_full_chain_ready"]]
    broad_ready = gate_fail_count == 0 and blocked_pack_count == 0
    generated_at = utc_now_iso()

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if broad_ready else ("blocked" if gate_fail_count else "pass_with_pack_depth_blockers_registered"),
        "release_decision": "P25_b05_pack_depth_ready_broad_full_chain_allowed"
        if broad_ready
        else ("P25_b05_pack_depth_gate_failed" if gate_fail_count else "P25_b05_pack_depth_blockers_registered_broad_full_chain_blocked"),
        "closeout_level": "L4_scope_pass_for_pack_depth_blocker_registration_only"
        if not broad_ready
        else "L4_scope_pass_for_broad_full_chain_pack_depth",
        "b05_status_after_p25": "closed_by_p25_pack_depth_ready" if broad_ready else "open_pack_level_depth_required",
        "broad_full_chain_quality_eval_allowed": broad_ready,
        "counts": {
            "pack_count": len(pack_rows),
            "ready_pack_count": ready_pack_count,
            "blocked_pack_count": blocked_pack_count,
            "requirement_count": len(requirement_rows),
            "blocked_requirement_count": sum(1 for row in requirement_rows if row["status"] == "blocked"),
            "gate_count": len(gate_rows),
            "gate_fail_count": gate_fail_count,
            "gate_blocked_count": gate_blocked_count,
        },
        "blocked_pack_ids": blocked_pack_ids,
        "pack_readiness": {row["pack_id"]: row["readiness_status"] for row in pack_rows},
        "known_gaps": [
            {
                "gap": row["pack_id"],
                "reason": row["readiness_status"],
                "detail": row["blocker_summary"],
                "next_actions": row["next_actions"],
            }
            for row in pack_rows
            if not row["broad_full_chain_ready"]
        ],
        "outputs": {
            "schema": rel_path(paths.schema_path, root),
            "pack_rows": rel_path(paths.pack_rows_path, root),
            "requirement_rows": rel_path(paths.requirement_rows_path, root),
            "gate_rows": rel_path(paths.gate_rows_path, root),
            "summary": rel_path(paths.summary_path, root),
            "report": rel_path(paths.report_path, root),
            "runtime_db": rel_path(paths.db_path, root),
        },
    }

    persist_p25_rows(paths, pack_rows, requirement_rows, gate_rows, summary)
    write_json(paths.schema_path, p25_schema_contract())
    write_jsonl(paths.pack_rows_path, pack_rows)
    write_jsonl(paths.requirement_rows_path, requirement_rows)
    write_jsonl(paths.gate_rows_path, gate_rows)
    write_json(paths.summary_path, summary)
    paths.report_path.write_text(render_p25_report(summary, pack_rows, gate_rows), encoding="utf-8")
    return summary


def render_p25_report(summary: dict[str, Any], pack_rows: list[dict[str, Any]], gate_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# R53-R60 P25 / B05 Pack Depth Gate",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Release decision: `{summary['release_decision']}`",
        f"- Closeout level: `{summary['closeout_level']}`",
        f"- B05 status after P25: `{summary['b05_status_after_p25']}`",
        f"- Broad full-chain quality eval allowed: `{summary['broad_full_chain_quality_eval_allowed']}`",
        "",
        "## Counts",
        "",
    ]
    for key, value in summary["counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Pack Readiness", ""])
    for row in pack_rows:
        marker = "ready" if row["broad_full_chain_ready"] else "blocked"
        lines.append(f"- `{row['pack_id']}`: `{marker}` / `{row['readiness_status']}`")
    lines.extend(["", "## Gates", ""])
    for row in gate_rows:
        lines.append(f"- `{row['gate_id']}`: `{row['status']}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "P25 does not backfill missing data and does not claim broad full-chain research quality. It proves that pack-level depth blockers are typed, sourced, and machine-readable before expensive broad regression.",
            "",
            "P25 不补假数据，也不声明 broad full-chain 研究质量已达标。它只证明 pack 级深度阻塞项已机器化、可追溯、可继续按源和 parser 修复。",
            "",
        ]
    )
    return "\n".join(lines)


__all__ = [
    "SCHEMA_VERSION",
    "P25Paths",
    "build_p25_pack_depth_gate",
    "build_pack_assessment_rows",
    "build_requirement_rows",
    "create_p25_schema",
    "default_p25_paths",
    "p25_schema_contract",
]
