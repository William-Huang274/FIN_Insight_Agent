"""P33 no-paid fixture for the capital-market feedback contract.

S8 already materializes issuer-level secondary-market / capital-feedback packs.
P33-1.3 proves the stricter P32 contract boundary: these rows can feed
Research Lead / Judgment material as market-positioning, credit/funding,
ownership, liquidity, valuation and derivatives thesis drivers without being
promoted to company fundamentals, product KPIs, real-time fund flow, or
investment advice.
"""

from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from sec_agent.r53_r60_research_to_quant_lab import rows_to_dicts
from sec_agent.r53_r60_runtime_task_spine import json_loads, rel_path, utc_now_iso, write_json
from sec_agent.r53_r60_secondary_market_capital_feedback import PACK_ROLES, build_s8_gate, default_s8_paths


SCHEMA_VERSION = "fin_insight_p33_capital_market_feedback_fixture_v0_1"
CONTRACT_ID = "l3_capital_market_feedback_contract_v0_1"
RELEASE_DECISION_PASS = "P33_1_3_L4_scope_pass_capital_market_feedback_fixture"
RELEASE_DECISION_BLOCKED = "P33_1_3_blocked_capital_market_feedback_fixture"

PROHIBITED_FUNDAMENTAL_PROMOTION = {
    "company_operating_performance",
    "product_revenue",
    "market_share",
    "fundamental_improvement",
    "current_fund_flow_without_flow_source",
    "investment_recommendation",
}


@dataclass(frozen=True)
class P33CapitalMarketFeedbackFixturePaths:
    manifest_path: Path
    report_path: Path


def default_p33_capital_market_feedback_fixture_paths(root: Path) -> P33CapitalMarketFeedbackFixturePaths:
    return P33CapitalMarketFeedbackFixturePaths(
        manifest_path=root / "data" / "manifests" / "p33_capital_market_feedback_fixture_v0_1.json",
        report_path=root
        / "docs"
        / "internal"
        / "vnext_20260610"
        / "p33_capital_market_feedback_fixture_report.zh-CN.md",
    )


def build_p33_capital_market_feedback_fixture(
    root: Path,
    *,
    rebuild_dependencies: bool = True,
    write_outputs: bool = True,
) -> dict[str, Any]:
    root = root.resolve()
    paths = default_p33_capital_market_feedback_fixture_paths(root)
    if rebuild_dependencies:
        s8_summary = build_s8_gate(root)
    else:
        s8_summary = _read_json_if_exists(default_s8_paths(root).summary_path)
    manifest = collect_capital_market_feedback_fixture_manifest(root, s8_summary=s8_summary)
    if write_outputs:
        write_json(paths.manifest_path, manifest)
        paths.report_path.parent.mkdir(parents=True, exist_ok=True)
        paths.report_path.write_text(render_capital_market_feedback_fixture_report(manifest), encoding="utf-8")
    return manifest


def collect_capital_market_feedback_fixture_manifest(root: Path, *, s8_summary: Mapping[str, Any]) -> dict[str, Any]:
    s8_paths = default_s8_paths(root)
    if not s8_paths.db_path.exists():
        raise FileNotFoundError(f"Runtime DB is missing: {s8_paths.db_path}")

    source_audit = _collect_source_role_audit(s8_paths.db_path)
    signal_audit = _collect_signal_authority_audit(s8_paths.db_path)
    gap_audit = _collect_typed_gap_audit(s8_paths.db_path)
    graph_audit = _collect_graph_edge_audit(s8_paths.db_path)
    judgment_material = _build_judgment_material(s8_paths.db_path)
    acceptance_gates = evaluate_capital_market_feedback_fixture_gates(
        s8_summary=s8_summary,
        source_audit=source_audit,
        signal_audit=signal_audit,
        gap_audit=gap_audit,
        graph_audit=graph_audit,
        judgment_material=judgment_material,
    )
    fail_count = len([row for row in acceptance_gates if row["status"] != "pass"])
    status = "pass" if fail_count == 0 else "fail"
    paths = default_p33_capital_market_feedback_fixture_paths(root)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "contract_id": CONTRACT_ID,
        "status": status,
        "release_decision": RELEASE_DECISION_PASS if status == "pass" else RELEASE_DECISION_BLOCKED,
        "closeout_level": "L4_scope_pass" if status == "pass" else "blocked",
        "promotion_recommendation": "active_registry_ready_runtime_alignment_only" if status == "pass" else "deferred_pending_repair",
        "promotion_scope": "capital_market_initial",
        "absorbed_contract_ids": [CONTRACT_ID],
        "artifacts": [
            {
                "artifact_type": "p33_capital_market_feedback_fixture",
                "contract_aligned_plan": {
                    "absorbed_contract_ids": [CONTRACT_ID],
                    "used_case_contract_ids": [CONTRACT_ID],
                },
            }
        ],
        "source_fixture_refs": {
            "s8_summary": rel_path(default_s8_paths(root).summary_path, root),
            "s8_gate_rows": rel_path(default_s8_paths(root).gate_rows_path, root),
            "runtime_db": rel_path(default_s8_paths(root).db_path, root),
            "p33_manifest": rel_path(paths.manifest_path, root),
            "p33_report": rel_path(paths.report_path, root),
        },
        "input_contract_required_fields": [
            "ticker",
            "pack_role",
            "source_id",
            "authority_class",
            "frequency",
            "lag_policy",
            "allowed_claims",
            "forbidden_claims",
            "claim_boundary",
            "evidence_or_gap_ref",
        ],
        "output_contract_required_fields": [
            "ticker",
            "judgment_role",
            "thesis_driver_scope",
            "authority_class",
            "evidence_refs",
            "gap_refs",
            "allowed_claims",
            "forbidden_claims",
            "cannot_promote_to",
            "writer_instruction",
        ],
        "source_audit": source_audit,
        "signal_audit": signal_audit,
        "gap_audit": gap_audit,
        "graph_audit": graph_audit,
        "judgment_material": judgment_material,
        "acceptance_gates": acceptance_gates,
        "gate_fail_count": fail_count,
        "runtime_entry_policy": (
            "Runtime alignment only: may align CapitalMarketFeedbackPack, "
            "CapitalFeedbackSignal, CapitalFeedbackGapItem, and capital-feedback "
            "graph edges as bounded thesis drivers. It cannot promote market "
            "signals to company fundamentals, product KPIs, real-time fund flow, "
            "or investment recommendations."
        ),
        "do_not_promote": [
            "market_proxy_as_fundamental_fact",
            "real_time_flow_claim_from_delayed_public_data",
            "derivatives_proxy_as_single_stock_gamma_exposure",
            "13f_lagged_position_as_current_buying_pressure",
            "market_positioning_as_investment_recommendation",
        ],
        "rollback_gate": [
            "market_proxy_misused_in_core_thesis",
            "lagged_holder_row_rendered_as_realtime_flow",
            "missing_borrow_or_option_data_hidden_as_observed_signal",
            "capital_feedback_judgment_material_lacks_boundary",
        ],
    }


def _collect_source_role_audit(db_path: Path) -> dict[str, Any]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = rows_to_dicts(
            conn.execute(
                """
                select source_id, pack_role, authority_class, frequency, lag_policy,
                       issuer_bound, instrument_bound, lifecycle_status, commercial_boundary,
                       forbidden_claims_json
                from secondary_market_source_registry_s8
                order by pack_role, source_id
                """
            ).fetchall()
        )
    role_counts = Counter(str(row.get("pack_role")) for row in rows)
    missing_roles = [role for role in PACK_ROLES if role_counts.get(role, 0) <= 0]
    boundary_ready = [
        row
        for row in rows
        if row.get("authority_class")
        and row.get("frequency")
        and row.get("lag_policy")
        and row.get("commercial_boundary")
        and json_loads(str(row.get("forbidden_claims_json") or "[]"), [])
    ]
    return {
        "status": "pass" if not missing_roles and len(boundary_ready) == len(rows) else "fail",
        "source_count": len(rows),
        "role_counts": dict(role_counts),
        "missing_roles": missing_roles,
        "boundary_ready_count": len(boundary_ready),
    }


def _collect_signal_authority_audit(db_path: Path) -> dict[str, Any]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = rows_to_dicts(
            conn.execute(
                """
                select signal_id, ticker, pack_role, signal_type, source_id, source_role,
                       authority_class, evidence_ref, allowed_claims_json,
                       forbidden_claims_json, claim_boundary
                from capital_feedback_signals_s8
                order by ticker, pack_role, signal_id
                """
            ).fetchall()
        )
    role_counts = Counter(str(row.get("pack_role")) for row in rows)
    authority_counts = Counter(str(row.get("authority_class")) for row in rows)
    market_proxy_rows = [
        row for row in rows if row.get("authority_class") in {"market_expectation_proxy", "lagged_positioning_context"}
    ]
    market_proxy_boundary_ok = [
        row
        for row in market_proxy_rows
        if PROHIBITED_FUNDAMENTAL_PROMOTION.intersection(
            set(json_loads(str(row.get("forbidden_claims_json") or "[]"), []))
        )
    ]
    lagged_rows = [row for row in rows if row.get("authority_class") == "lagged_positioning_context"]
    lagged_rows_ok = [
        row
        for row in lagged_rows
        if {"realtime_flow", "current_buying_pressure"}.intersection(
            set(json_loads(str(row.get("forbidden_claims_json") or "[]"), []))
        )
    ]
    exact_rows = [
        row
        for row in rows
        if row.get("authority_class") in {"exact_filing_fact", "exact_financial_statement_fact"}
    ]
    exact_rows_ok = [
        row
        for row in exact_rows
        if "investment_recommendation" in json_loads(str(row.get("forbidden_claims_json") or "[]"), [])
        and row.get("evidence_ref")
        and row.get("claim_boundary")
    ]
    return {
        "status": "pass",
        "signal_count": len(rows),
        "role_counts": dict(role_counts),
        "authority_counts": dict(authority_counts),
        "market_proxy_row_count": len(market_proxy_rows),
        "market_proxy_boundary_ok_count": len(market_proxy_boundary_ok),
        "lagged_positioning_count": len(lagged_rows),
        "lagged_positioning_boundary_ok_count": len(lagged_rows_ok),
        "exact_fact_row_count": len(exact_rows),
        "exact_fact_boundary_ok_count": len(exact_rows_ok),
    }


def _collect_typed_gap_audit(db_path: Path) -> dict[str, Any]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = rows_to_dicts(
            conn.execute(
                """
                select gap_id, ticker, pack_role, gap_type, source_id, lifecycle_status,
                       public_boundary, commercial_boundary, next_action, forbidden_claims_json
                from capital_feedback_gap_items_s8
                order by ticker, pack_role, gap_id
                """
            ).fetchall()
        )
    role_counts = Counter(str(row.get("pack_role")) for row in rows)
    complete_rows = [
        row
        for row in rows
        if row.get("lifecycle_status") == "typed_gap"
        and row.get("public_boundary")
        and row.get("commercial_boundary")
        and row.get("next_action")
        and "claiming_missing_data_as_observed_fact"
        in json_loads(str(row.get("forbidden_claims_json") or "[]"), [])
    ]
    return {
        "status": "pass" if len(complete_rows) == len(rows) else "fail",
        "gap_count": len(rows),
        "complete_gap_count": len(complete_rows),
        "role_counts": dict(role_counts),
    }


def _collect_graph_edge_audit(db_path: Path) -> dict[str, Any]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = rows_to_dicts(
            conn.execute(
                """
                select graph_edge_id, ticker, pack_role, authority_class,
                       evidence_refs_json, gap_refs_json, forbidden_claims_json, confidence, status
                from capital_feedback_graph_edges_s8
                order by ticker, pack_role, graph_edge_id
                """
            ).fetchall()
        )
    edge_counts = Counter(str(row.get("pack_role")) for row in rows)
    backed = [
        row
        for row in rows
        if json_loads(str(row.get("evidence_refs_json") or "[]"), [])
        or json_loads(str(row.get("gap_refs_json") or "[]"), [])
    ]
    boundary_ready = [
        row for row in rows if json_loads(str(row.get("forbidden_claims_json") or "[]"), []) and row.get("confidence")
    ]
    return {
        "status": "pass" if len(backed) == len(rows) and len(boundary_ready) == len(rows) else "fail",
        "edge_count": len(rows),
        "backed_edge_count": len(backed),
        "boundary_ready_edge_count": len(boundary_ready),
        "role_counts": dict(edge_counts),
    }


def _build_judgment_material(db_path: Path, *, max_tickers: int = 6) -> list[dict[str, Any]]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        preferred = ["NVDA", "AMD", "DELL", "ASML", "000660.KS", "005930.KS"]
        available = {
            row["ticker"]
            for row in conn.execute("select distinct ticker from capital_feedback_packs_s8 order by ticker").fetchall()
        }
        tickers = [ticker for ticker in preferred if ticker in available]
        if len(tickers) < max_tickers:
            for row in conn.execute("select distinct ticker from capital_feedback_packs_s8 order by ticker limit 20").fetchall():
                ticker = row["ticker"]
                if ticker not in tickers:
                    tickers.append(ticker)
                if len(tickers) >= max_tickers:
                    break

        rows: list[dict[str, Any]] = []
        for ticker in tickers[:max_tickers]:
            signals = rows_to_dicts(
                conn.execute(
                    """
                    select signal_id, pack_role, signal_type, source_id, authority_class,
                           evidence_ref, allowed_claims_json, forbidden_claims_json, claim_boundary
                    from capital_feedback_signals_s8
                    where ticker = ?
                    order by pack_role, signal_id
                    """,
                    (ticker,),
                ).fetchall()
            )
            gaps = rows_to_dicts(
                conn.execute(
                    """
                    select gap_id, pack_role, gap_type, public_boundary, commercial_boundary,
                           forbidden_claims_json
                    from capital_feedback_gap_items_s8
                    where ticker = ?
                    order by pack_role, gap_id
                    """,
                    (ticker,),
                ).fetchall()
            )
            rows.extend(_project_ticker_judgment_material(ticker, signals=signals, gaps=gaps))
    return rows


def _project_ticker_judgment_material(
    ticker: str, *, signals: Iterable[Mapping[str, Any]], gaps: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    signal_by_role: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in signals:
        signal_by_role[str(row.get("pack_role"))].append(row)
    gap_by_role: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in gaps:
        gap_by_role[str(row.get("pack_role"))].append(row)

    projected: list[dict[str, Any]] = []
    for role in PACK_ROLES:
        role_signals = signal_by_role.get(role, [])[:3]
        role_gaps = gap_by_role.get(role, [])[:2]
        if not role_signals and not role_gaps:
            continue
        forbidden_claims = sorted(
            {
                item
                for row in [*role_signals, *role_gaps]
                for item in json_loads(str(row.get("forbidden_claims_json") or "[]"), [])
            }
        )
        allowed_claims = sorted(
            {
                item
                for row in role_signals
                for item in json_loads(str(row.get("allowed_claims_json") or "[]"), [])
            }
        )
        evidence_refs = [str(row.get("evidence_ref") or row.get("signal_id") or "") for row in role_signals if row.get("evidence_ref") or row.get("signal_id")]
        gap_refs = [str(row.get("gap_id") or "") for row in role_gaps if row.get("gap_id")]
        projected.append(
            {
                "ticker": ticker,
                "judgment_role": role,
                "thesis_driver_scope": _role_scope(role),
                "authority_class": ",".join(sorted({str(row.get("authority_class")) for row in role_signals if row.get("authority_class")})) or "gap",
                "evidence_refs": evidence_refs,
                "gap_refs": gap_refs,
                "allowed_claims": allowed_claims,
                "forbidden_claims": forbidden_claims,
                "cannot_promote_to": sorted(PROHIBITED_FUNDAMENTAL_PROMOTION.intersection(forbidden_claims)),
                "writer_instruction": _writer_instruction(role, has_signal=bool(role_signals), has_gap=bool(role_gaps)),
                "promoted_to_fundamental_fact": False,
            }
        )
    return projected


def _role_scope(role: str) -> str:
    return {
        "secondary_market_capital_flow": "market_price_volume_reaction_context",
        "ownership_and_holder": "holder_structure_or_lagged_positioning_context",
        "credit_funding": "capital_cost_or_refinancing_context",
        "corporate_action": "issuance_buyback_insider_proxy_event_context",
        "liquidity_and_positioning": "liquidity_short_borrow_or_positioning_context",
        "valuation_price_in": "valuation_or_price_in_context",
        "derivatives_market_signal": "macro_or_derivatives_expectation_proxy",
    }.get(role, "capital_market_feedback_context")


def _writer_instruction(role: str, *, has_signal: bool, has_gap: bool) -> str:
    if has_signal and has_gap:
        return f"Use {role} as bounded market/capital context and explicitly mention missing exact/public fields."
    if has_signal:
        return f"Use {role} as bounded thesis-driver context only; do not state fundamentals or investment advice from it."
    return f"Expose {role} as a typed gap; do not infer the missing signal from other rows."


def evaluate_capital_market_feedback_fixture_gates(
    *,
    s8_summary: Mapping[str, Any],
    source_audit: Mapping[str, Any],
    signal_audit: Mapping[str, Any],
    gap_audit: Mapping[str, Any],
    graph_audit: Mapping[str, Any],
    judgment_material: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    def gate(gate_id: str, passed: bool, detail: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now_iso(),
            "gate_id": gate_id,
            "status": "pass" if passed else "fail",
            "pass_level": "L4_scope_pass" if passed else "blocked",
            "detail": dict(detail),
        }

    material_roles = {str(row.get("judgment_role")) for row in judgment_material}
    all_material_rows_bounded = all(
        row.get("writer_instruction")
        and row.get("promoted_to_fundamental_fact") is False
        and (row.get("evidence_refs") or row.get("gap_refs"))
        and row.get("forbidden_claims")
        for row in judgment_material
    )
    return [
        gate(
            "p33_1_3_s8_capital_feedback_l4_pass",
            s8_summary.get("release_decision") == "S8_L4_scope_pass"
            and int((s8_summary.get("counts") or {}).get("gate_fail_count") or 0) == 0,
            {"release_decision": s8_summary.get("release_decision"), "counts": s8_summary.get("counts")},
        ),
        gate(
            "p33_1_3_source_roles_authority_boundaries_present",
            source_audit.get("status") == "pass" and not source_audit.get("missing_roles"),
            source_audit,
        ),
        gate(
            "p33_1_3_market_proxy_not_fundamental_fact",
            int(signal_audit.get("market_proxy_row_count") or 0) > 0
            and signal_audit.get("market_proxy_row_count") == signal_audit.get("market_proxy_boundary_ok_count"),
            {
                "market_proxy_row_count": signal_audit.get("market_proxy_row_count"),
                "market_proxy_boundary_ok_count": signal_audit.get("market_proxy_boundary_ok_count"),
            },
        ),
        gate(
            "p33_1_3_lagged_holder_not_realtime_flow",
            signal_audit.get("lagged_positioning_count") == signal_audit.get("lagged_positioning_boundary_ok_count"),
            {
                "lagged_positioning_count": signal_audit.get("lagged_positioning_count"),
                "lagged_positioning_boundary_ok_count": signal_audit.get("lagged_positioning_boundary_ok_count"),
            },
        ),
        gate(
            "p33_1_3_exact_credit_and_statement_facts_separated",
            int(signal_audit.get("exact_fact_row_count") or 0) > 0
            and signal_audit.get("exact_fact_row_count") == signal_audit.get("exact_fact_boundary_ok_count"),
            {
                "exact_fact_row_count": signal_audit.get("exact_fact_row_count"),
                "exact_fact_boundary_ok_count": signal_audit.get("exact_fact_boundary_ok_count"),
            },
        ),
        gate(
            "p33_1_3_missing_market_depth_is_typed_gap",
            gap_audit.get("status") == "pass" and int(gap_audit.get("gap_count") or 0) > 0,
            gap_audit,
        ),
        gate(
            "p33_1_3_graph_edges_evidence_or_gap_backed",
            graph_audit.get("status") == "pass",
            graph_audit,
        ),
        gate(
            "p33_1_3_judgment_material_writer_ready_and_bounded",
            bool(judgment_material)
            and PACK_ROLES[0] in material_roles
            and all_material_rows_bounded,
            {"judgment_material_count": len(judgment_material), "roles": sorted(material_roles)},
        ),
    ]


def render_capital_market_feedback_fixture_report(manifest: Mapping[str, Any]) -> str:
    lines = [
        "# P33-1.3 Capital Market Feedback Fixture Report",
        "",
        f"- Contract: `{manifest.get('contract_id')}`",
        f"- Status: `{manifest.get('status')}`",
        f"- Release decision: `{manifest.get('release_decision')}`",
        f"- Closeout level: `{manifest.get('closeout_level')}`",
        f"- Promotion recommendation: `{manifest.get('promotion_recommendation')}`",
        "",
        "## What This Proves",
        "",
        "- Secondary-market / capital-feedback rows can become bounded thesis-driver material.",
        "- Market, holder, derivatives, liquidity and valuation signals are not promoted to fundamentals.",
        "- Delayed 13F / holder rows are not rendered as real-time buying pressure.",
        "- Missing short-borrow, option/gamma, credit spread or local holder rows remain typed gaps.",
        "- Writer-facing material carries evidence/gap refs plus allowed/forbidden claim boundaries.",
        "",
        "## Counts",
        "",
        f"- Source roles: `{manifest.get('source_audit', {}).get('source_count')}`",
        f"- Signals: `{manifest.get('signal_audit', {}).get('signal_count')}`",
        f"- Gaps: `{manifest.get('gap_audit', {}).get('gap_count')}`",
        f"- Graph edges: `{manifest.get('graph_audit', {}).get('edge_count')}`",
        f"- Judgment material rows: `{len(manifest.get('judgment_material') or [])}`",
        "",
        "## Acceptance Gates",
        "",
    ]
    for row in manifest.get("acceptance_gates", []):
        lines.append(f"- `{row.get('status')}` `{row.get('gate_id')}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            str(manifest.get("runtime_entry_policy")),
            "",
            "## Source Fixture Refs",
            "",
        ]
    )
    for key, value in (manifest.get("source_fixture_refs") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines) + "\n"


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json_loads(path.read_text(encoding="utf-8"), {})
