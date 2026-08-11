from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from sec_agent.r53_r60_pack_depth_b05_gate import build_p25_pack_depth_gate, default_p25_paths, p25_schema_contract
from sec_agent.r53_r60_pre_full_chain_blocker_gate import build_p21_pre_full_chain_blocker_gate
from test_r53_r60_pre_full_chain_blocker_gate import seed_p21_fixture


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def seed_p25_inputs(root: Path) -> None:
    manifest_dir = root / "data" / "manifests"
    _write_json(
        manifest_dir / "second_third_layer_depth_parity_summary_v0_1.json",
        {
            "status": "pass",
            "parity_status": "fail",
            "company_count": 3,
            "checks": {"all_missing_depth_is_classified": True},
            "metrics": {
                "full_depth_target_met_company_count": 2,
                "full_depth_target_gap_company_count": 1,
                "dimension_gap_counts": {
                    "product_kpi_depth": 1,
                    "customer_deployment_depth": 1,
                    "capital_market_detail_depth": 0,
                    "product_spec_depth": 0,
                    "market_liquidity_depth": 0,
                },
            },
        },
    )
    _write_json(
        manifest_dir / "ai_semis_product_depth_gate_v0_2.json",
        {
            "status": "pass",
            "company_count": 2,
            "gap_queue_count": 0,
            "strict_depth_status_counts": {"pass": 2},
            "layer_status_counts": {"product_profile": {"detailed_profile_ready": 2}},
            "gap_reason_counts": {},
        },
    )
    _write_json(
        manifest_dir / "r53_r60_s7_deliverable_studio_dashboard_summary_v0_1.json",
        {
            "status": "pass",
            "release_decision": "S7_L4_scope_pass",
            "closeout_level": "L4_scope_pass",
            "boundary": "deterministic render only",
            "customer_ready_editorial_quality_pass": True,
            "editorial_acceptance_status": "deterministic_customer_ready_pass",
            "counts": {"render_jobs_s7": 4, "deliverable_quality_gates_s7": 4, "gate_fail_count": 0},
            "render_jobs": [{"output_format": "markdown"}, {"output_format": "docx"}],
        },
    )
    _write_json(
        manifest_dir / "r53_r60_s8_secondary_market_capital_feedback_summary_v0_1.json",
        {
            "status": "pass",
            "release_decision": "S8_L4_scope_pass",
            "closeout_level": "L4_scope_pass",
            "boundary": "missing real-time derivatives and credit feed",
            "counts": {"pack_count": 3, "signal_count": 10},
            "role_signal_counts": {"secondary_market_capital_flow": 3},
            "role_gap_counts": {"credit_funding": 3, "derivatives_market_signal": 3, "valuation_price_in": 3},
        },
    )
    _write_json(
        manifest_dir / "r53_r60_s9_research_to_quant_lab_summary_v0_1.json",
        {
            "status": "pass",
            "release_decision": "S9_L4_scope_pass",
            "closeout_level": "L4_scope_pass",
            "counts": {
                "approved_factor_count": 2,
                "backtest_result_count": 2,
                "factor_card_count": 3,
                "blocked_factor_count": 1,
                "no_live_trading": True,
            },
            "experience_outcomes": {"diagnostic_supported_for_research_validation": 2},
        },
    )
    _write_json(
        manifest_dir / "r53_r60_p14_data_ingestion_retrieval_control_plane_summary_v0_1.json",
        {
            "status": "pass",
            "release_decision": "P14_L4_scope_pass",
            "closeout_level": "L4_scope_pass",
            "source_snapshot_status": "source_snapshots_ready",
            "parser_contract_status": "parser_contracts_ready",
            "retrieval_control_status": "strategy_budget_context_bridge_ready",
            "lineage_status": "raw_to_runtime_lineage_ready",
            "context_bridge_status": "context_bridge_ready",
            "current_universe_refresh_status": "current_accepted_public_source_universe_ready",
            "current_universe_refresh_evidence": [{"evidence_name": "fixture_current_universe", "status": "pass"}],
            "policy": {
                "current_accepted_universe_refresh_is_runtime_ready": True,
                "not_full_internet_crawler_or_realtime_refresh": True,
            },
            "readiness_report": {"known_gaps_json": "[]"},
        },
    )


def test_p25_registers_pack_depth_blockers_without_allowing_broad_full_chain(tmp_path: Path) -> None:
    seed_p25_inputs(tmp_path)

    summary = build_p25_pack_depth_gate(tmp_path)

    assert summary["status"] == "pass_with_pack_depth_blockers_registered"
    assert summary["b05_status_after_p25"] == "open_pack_level_depth_required"
    assert summary["broad_full_chain_quality_eval_allowed"] is False
    assert summary["counts"]["pack_count"] == 6
    assert summary["counts"]["gate_fail_count"] == 0
    assert summary["counts"]["blocked_pack_count"] >= 1
    assert "ai_semis_product_evidence_pack" not in summary["blocked_pack_ids"]
    assert "product_evidence_pack_all_universe" in summary["blocked_pack_ids"]
    assert (tmp_path / summary["outputs"]["summary"]).exists()
    assert (tmp_path / summary["outputs"]["report"]).exists()


def test_p25_sql_rows_capture_pack_requirements_and_gates(tmp_path: Path) -> None:
    seed_p25_inputs(tmp_path)
    build_p25_pack_depth_gate(tmp_path)
    paths = default_p25_paths(tmp_path)

    with sqlite3.connect(paths.db_path) as conn:
        conn.row_factory = sqlite3.Row
        tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        pack_count = conn.execute("select count(*) from pack_depth_assessments_p25").fetchone()[0]
        blocked_req_count = conn.execute("select count(*) from pack_depth_requirements_p25 where status = 'blocked'").fetchone()[0]
        gate_fail_count = conn.execute("select count(*) from pack_depth_gate_results_p25 where status = 'fail'").fetchone()[0]
        report = conn.execute("select * from pack_depth_reports_p25").fetchone()

    assert set(p25_schema_contract()["tables"]).issubset(tables)
    assert pack_count == 6
    assert blocked_req_count >= 1
    assert gate_fail_count == 0
    assert report["b05_status_after_p25"] == "open_pack_level_depth_required"
    assert report["broad_full_chain_quality_eval_allowed"] == 0


def test_p21_reads_p25_summary_and_keeps_b05_open_until_all_pack_depth_ready(tmp_path: Path) -> None:
    seed_p21_fixture(tmp_path)
    seed_p25_inputs(tmp_path)
    build_p25_pack_depth_gate(tmp_path)

    summary = build_p21_pre_full_chain_blocker_gate(tmp_path)
    blockers = [
        json.loads(line)
        for line in (tmp_path / summary["outputs"]["blockers"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    b05 = next(row for row in blockers if row["blocker_id"] == "B05-depth-packs-before-broad-full-chain")

    assert b05["status"] == "open_pack_level_depth_required"
    assert b05["observed_evidence"]["p25_pack_depth_summary"]["exists"] is True
    assert b05["observed_evidence"]["p25_pack_depth_summary"]["broad_full_chain_quality_eval_allowed"] is False


def test_p21_can_close_b05_only_when_p25_summary_records_all_pack_depth_ready(tmp_path: Path) -> None:
    seed_p21_fixture(tmp_path)
    p25_summary_path = tmp_path / "data" / "manifests" / "r53_r60_p25_b05_pack_depth_summary_v0_1.json"
    _write_json(
        p25_summary_path,
        {
            "status": "pass",
            "release_decision": "P25_b05_pack_depth_ready_broad_full_chain_allowed",
            "closeout_level": "L4_scope_pass_for_broad_full_chain_pack_depth",
            "b05_status_after_p25": "closed_by_p25_pack_depth_ready",
            "broad_full_chain_quality_eval_allowed": True,
            "counts": {"blocked_pack_count": 0, "blocked_requirement_count": 0, "gate_fail_count": 0},
        },
    )

    summary = build_p21_pre_full_chain_blocker_gate(tmp_path)
    blockers = [
        json.loads(line)
        for line in (tmp_path / summary["outputs"]["blockers"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    b05 = next(row for row in blockers if row["blocker_id"] == "B05-depth-packs-before-broad-full-chain")

    assert b05["status"] == "closed_by_p25_pack_depth_ready"
