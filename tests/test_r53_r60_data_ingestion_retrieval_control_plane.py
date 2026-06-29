from __future__ import annotations

import sqlite3
from pathlib import Path

from sec_agent.r53_r60_context_graph_skill_registry import build_s4_gate
from sec_agent.r53_r60_data_ingestion_retrieval_control_plane import (
    NEGATIVE_AUTHORITY_ID,
    NEGATIVE_RAW_DOC_ID,
    P14_DRILL_TASK_ID,
    P14_TASK_ID,
    build_p14_gate,
    data_ingestion_retrieval_control_plane_schema_contract,
    default_p14_paths,
)
from sec_agent.r53_r60_durable_runtime_hil_resource_router import build_p12_gate
from sec_agent.r53_r60_graph_skill_memory_lifecycle import build_p13_gate
from sec_agent.r53_r60_retrieval_evidence_spine import build_s3_gate
from sec_agent.r53_r60_runtime_task_spine import json_loads
from test_r53_r60_context_graph_skill_registry import seed_s3_fixture
from test_r53_r60_durable_runtime_hil_resource_router import seed_p12_fixture


def seed_p14_fixture(root: Path) -> None:
    seed_s3_fixture(root)
    assert build_s3_gate(root)["release_decision"] == "S3_L4_scope_pass"
    assert build_s4_gate(root)["release_decision"] == "S4_L4_scope_pass"
    seed_p12_fixture(root)
    assert build_p12_gate(root)["release_decision"] == "P12_L4_scope_pass_runtime_drill_ready"
    assert build_p13_gate(root)["release_decision"] == "P13_L4_scope_pass_graph_skill_memory_lifecycle_ready"


def test_build_p14_gate_outputs_l4_scope_pass(tmp_path: Path) -> None:
    seed_p14_fixture(tmp_path)

    summary = build_p14_gate(tmp_path)

    assert summary["release_decision"] == "P14_L4_scope_pass_data_ingestion_retrieval_control_plane_ready"
    assert summary["closeout_level"] == "L4_scope_pass"
    assert summary["status"] == "pass"
    assert summary["source_snapshot_status"] == "source_snapshots_ready"
    assert summary["parser_contract_status"] == "parser_contracts_ready"
    assert summary["lineage_status"] == "raw_to_runtime_lineage_ready"
    assert summary["retrieval_control_status"] == "strategy_budget_context_bridge_ready"
    assert summary["context_bridge_status"] == "context_bridge_ready"
    assert summary["performance_status"] == "local_profile_recorded"
    assert summary["counts"]["gate_count"] == 12
    assert summary["counts"]["gate_fail_count"] == 0
    assert summary["counts"]["source_snapshot_count"] >= 6
    assert summary["counts"]["parser_run_count"] >= 6
    assert summary["counts"]["blocked_authority_count"] == 1
    assert summary["counts"]["strategy_pack_count"] >= 5
    assert summary["counts"]["context_bridge_count"] >= 4
    assert (tmp_path / summary["outputs"]["schema"]).exists()
    assert (tmp_path / summary["outputs"]["gate_rows"]).exists()
    assert (tmp_path / summary["outputs"]["summary"]).exists()
    assert (tmp_path / summary["outputs"]["closeout_report"]).exists()


def test_p14_schema_and_source_modalities_are_present(tmp_path: Path) -> None:
    seed_p14_fixture(tmp_path)
    build_p14_gate(tmp_path)
    db_path = default_p14_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}
        modalities = {row[0] for row in conn.execute("select distinct source_modality from source_snapshot_registry_p14").fetchall()}
        statuses = {row[0] for row in conn.execute("select distinct status from ingestion_jobs_p14").fetchall()}

    contract = data_ingestion_retrieval_control_plane_schema_contract()
    assert set(contract["tables"]).issubset(tables)
    assert set(contract["required_source_modalities"]).issubset(modalities)
    assert "succeeded" in statuses
    assert "index_snapshot_reconciled" in statuses


def test_p14_blocks_raw_snapshot_without_parser_authority(tmp_path: Path) -> None:
    seed_p14_fixture(tmp_path)
    build_p14_gate(tmp_path)
    db_path = default_p14_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        raw_doc = conn.execute("select * from raw_source_documents_p14 where raw_document_id = ?", (NEGATIVE_RAW_DOC_ID,)).fetchone()
        parser_gap = conn.execute("select * from parser_runs_p14 where raw_document_id = ?", (NEGATIVE_RAW_DOC_ID,)).fetchone()
        blocked_auth = conn.execute("select * from authority_mapping_records_p14 where authority_mapping_id = ?", (NEGATIVE_AUTHORITY_ID,)).fetchone()
        bad_context = conn.execute(
            "select count(*) from retrieval_context_bridge_records_p14 where selected_authority_mapping_ids_json like ?",
            (f"%{NEGATIVE_AUTHORITY_ID}%",),
        ).fetchone()[0]

    assert raw_doc["status"] == "blocked_no_parser"
    assert parser_gap["status"] == "parser_gap_blocked"
    assert int(parser_gap["typed_gap_count"]) == 1
    assert blocked_auth["status"] == "blocked"
    assert int(blocked_auth["can_enter_claim_card"]) == 0
    assert int(blocked_auth["can_enter_context"]) == 0
    assert bad_context == 0


def test_p14_authority_index_and_lineage_contract(tmp_path: Path) -> None:
    seed_p14_fixture(tmp_path)
    build_p14_gate(tmp_path)
    db_path = default_p14_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        modes = {row[0] for row in conn.execute("select distinct authority_mode from authority_mapping_records_p14 where status = 'accepted'").fetchall()}
        index_rows = conn.execute("select * from index_refresh_records_p14").fetchall()
        incomplete_lineage = conn.execute("select count(*) from ingestion_lineage_edges_p14 where lineage_status not in ('complete', 'blocked')").fetchone()[0]
        milvus = conn.execute("select * from index_refresh_records_p14 where index_type = 'milvus_semantic'").fetchone()

    assert {"exact_company_fact_authority", "technical_fact_authority", "deployment_signal_authority", "macro_context_only"}.issubset(modes)
    assert index_rows
    assert all(int(row["lineage_complete"]) == 1 for row in index_rows)
    assert incomplete_lineage == 0
    assert json_loads(milvus["payload_json"], {})["milvus_not_exact_authority"] is True


def test_p14_retrieval_budget_context_bridge_and_quality_probes(tmp_path: Path) -> None:
    seed_p14_fixture(tmp_path)
    build_p14_gate(tmp_path)
    db_path = default_p14_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        intents = {row[0] for row in conn.execute("select intent_id from retrieval_strategy_packs_p14").fetchall()}
        budgets = conn.execute("select * from retrieval_budget_records_p14").fetchall()
        bridges = conn.execute("select * from retrieval_context_bridge_records_p14").fetchall()
        failed_probes = conn.execute("select count(*) from retrieval_quality_probe_records_p14 where status != 'pass'").fetchone()[0]

    contract = data_ingestion_retrieval_control_plane_schema_contract()
    assert set(contract["required_intents"]).issubset(intents)
    assert budgets
    assert all(int(row["candidate_budget"]) > 0 and int(row["context_budget_tokens"]) > 0 for row in budgets)
    assert bridges
    for row in bridges:
        assert row["exact_ref_policy"] == "preserve_exact_refs_not_summaries"
        assert row["context_policy_ref"] != "p13_context_policy_missing"
        assert json_loads(row["selected_authority_mapping_ids_json"], [])
        assert json_loads(row["selected_index_refresh_ids_json"], [])
    assert failed_probes == 0


def test_p14_rerun_stable_and_appends_workpaper_event(tmp_path: Path) -> None:
    seed_p14_fixture(tmp_path)
    first = build_p14_gate(tmp_path)
    second = build_p14_gate(tmp_path)
    db_path = default_p14_paths(tmp_path).db_path

    with sqlite3.connect(db_path) as conn:
        snapshot_count = conn.execute("select count(*) from source_snapshot_registry_p14").fetchone()[0]
        gate_count = conn.execute("select count(*) from data_plane_gate_results_p14").fetchone()[0]
        event_count = conn.execute(
            "select count(*) from workpaper_events where task_id = ? and event_type = 'data_ingestion_retrieval_control_plane_ready'",
            (P14_TASK_ID,),
        ).fetchone()[0]
        drill_resume_count = conn.execute(
            "select resume_count from research_tasks where task_id = ?",
            (P14_DRILL_TASK_ID,),
        ).fetchone()[0]

    assert first["release_decision"] == "P14_L4_scope_pass_data_ingestion_retrieval_control_plane_ready"
    assert second["release_decision"] == "P14_L4_scope_pass_data_ingestion_retrieval_control_plane_ready"
    assert snapshot_count >= 6
    assert gate_count == 12
    assert event_count == 2
    assert int(drill_resume_count) >= 1
