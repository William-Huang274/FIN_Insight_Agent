from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from sec_agent.data_quality_release_eval_gate import (
    build_data_quality_release_eval_gate,
    write_data_quality_release_eval_sqlite,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _seed_summaries(repo: Path, *, hard_fail: bool = False) -> None:
    _write_json(
        repo / "data/manifests/raw_source_provenance_summary_v0_1.json",
        {
            "status": "action_required" if hard_fail else "pass",
            "exact_authority_unresolved_count": 1 if hard_fail else 0,
            "unresolved_lineage_count": 1 if hard_fail else 0,
            "companyfacts_external_key_document_count": 0 if hard_fail else 588,
            "url_only_context_lineage_count": 12,
            "outputs": {},
        },
    )
    _write_json(
        repo / "data/manifests/parser_quality_summary_v0_1.json",
        {
            "status": "pass_with_recorded_rejections",
            "missing_declared_output_count": 0,
            "missing_artifact_count": 0,
            "parser_run_count": 1,
            "parser_status_counts": {"pass": 1, "unknown": 1},
            "outputs": {},
        },
    )
    _write_json(
        repo / "data/manifests/gold_fact_signal_mart_summary_v0_1.json",
        {
            "status": "pass",
            "row_count": 3,
            "sqlite_row_count": 3,
            "missing_source_rowset_count": 0,
            "planning_or_gap_only_count": 1,
            "by_authority_mode": {
                "exact_company_fact_authority": 1,
                "bounded_thesis_driver_authority": 1,
                "planning_or_gap_only": 1,
            },
            "outputs": {},
        },
    )
    _write_json(
        repo / "data/manifests/research_graph_summary_v0_1.json",
        {
            "status": "pass",
            "node_count": 2,
            "edge_count": 3,
            "evidence_support_row_count": 3,
            "sqlite_node_count": 2,
            "sqlite_edge_count": 3,
            "sqlite_support_count": 3,
            "dangling_edge_count": 0,
            "unsupported_edge_count": 0,
            "support_status_counts": {"gold_mart_row": 2, "modelled_relationship_without_direct_evidence_ref": 1},
            "outputs": {},
        },
    )
    _write_json(
        repo / "data/manifests/retrieval_index_registry_summary_v0_1.json",
        {
            "status": "pass",
            "index_snapshot_count": 2,
            "source_lineage_count": 3,
            "sqlite_snapshot_count": 2,
            "sqlite_lineage_count": 3,
            "missing_source_artifact_count": 0,
            "missing_record_file_snapshot_count": 0,
            "record_snapshot_trace_status_counts": {"record_snapshot_without_verified_raw_trace": 1},
            "parser_artifact_link_status_counts": {"no_parser_artifact_match": 2},
            "outputs": {},
        },
    )
    _write_json(
        repo / "data/manifests/agent_runtime_consumption_contract_summary_v0_1.json",
        {
            "status": "pass",
            "company_brief_count": 603,
            "role_evidence_pack_count": 3618,
            "expected_role_evidence_pack_count": 3618,
            "invalid_selected_gap_row_count": 1 if hard_fail else 0,
            "sqlite_brief_count": 603,
            "sqlite_pack_count": 3618,
            "gap_ref_count": 0 if hard_fail else 1,
            "outputs": {},
        },
    )


def test_rd7_passes_with_recorded_warnings_when_hard_gates_clear(tmp_path: Path) -> None:
    repo = tmp_path
    _seed_summaries(repo, hard_fail=False)

    result = build_data_quality_release_eval_gate(repo, generated_at="2026-06-27T00:00:00Z")

    assert result["summary"]["status"] == "pass_with_warnings"
    assert result["summary"]["fail_count"] == 0
    assert result["summary"]["warn_count"] >= 4
    assert any(row["gate_name"] == "url_only_context_lineage_count" and row["status"] == "warn" for row in result["gate_rows"])


def test_rd7_blocks_release_on_exact_lineage_or_authority_misuse(tmp_path: Path) -> None:
    repo = tmp_path
    _seed_summaries(repo, hard_fail=True)

    result = build_data_quality_release_eval_gate(repo, generated_at="2026-06-27T00:00:00Z")

    assert result["summary"]["status"] == "action_required"
    failing_gates = {row["gate_name"] for row in result["gate_rows"] if row["status"] == "fail"}
    assert "exact_authority_unresolved_count" in failing_gates
    assert "invalid_selected_gap_row_count" in failing_gates
    assert "planning_gap_ref_parity" in failing_gates


def test_rd7_sqlite_mirror_counts_gate_rows(tmp_path: Path) -> None:
    repo = tmp_path
    _seed_summaries(repo, hard_fail=False)
    result = build_data_quality_release_eval_gate(repo, generated_at="2026-06-27T00:00:00Z")
    sqlite_path = repo / "data/workbench_private/research_data/rd7.sqlite"

    counts = write_data_quality_release_eval_sqlite(sqlite_path, gate_rows=result["gate_rows"])

    assert counts["gate_row_count"] == len(result["gate_rows"])
    conn = sqlite3.connect(sqlite_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM data_quality_release_gate").fetchone()[0] == len(result["gate_rows"])
    finally:
        conn.close()
