from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from sec_agent.r53_r60_unified_backlog import (
    ACTIVE_SOURCE_DOCS,
    build_s0_unified_backlog,
    read_jsonl,
)


def create_minimal_repo(root: Path, *, active_docs: bool = True, legacy_count: int = 12) -> None:
    if active_docs:
        for doc in ACTIVE_SOURCE_DOCS:
            path = root / doc
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {Path(doc).stem}\n", encoding="utf-8")

    legacy_dir = root / "docs" / "worklog" / "integrated_execution_p_series"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    for idx in range(legacy_count):
        (legacy_dir / f"{idx:03d}_r{idx}_baseline_gate.md").write_text(
            f"# R{idx} baseline\n",
            encoding="utf-8",
        )


def test_s0_backlog_builds_l4_scope_contract(tmp_path: Path) -> None:
    create_minimal_repo(tmp_path)

    result = build_s0_unified_backlog(tmp_path)

    assert result.summary["status"] == "pass"
    assert result.summary["release_decision"] == "S0_L4_scope_pass"
    assert result.summary["closeout_level"] == "L4_scope_pass"
    assert result.summary["counts"]["demand_count"] == 61
    assert result.summary["counts"]["implementation_task_count"] == 183
    assert result.summary["counts"]["release_slice_count"] == 11

    demands = read_jsonl(result.outputs["r_document_demand_map"])
    release_board = read_jsonl(result.outputs["release_board"])
    pass_matrix = read_jsonl(result.outputs["pass_level_gate_matrix"])

    assert {row["slice_id"] for row in release_board} == {f"S{i}" for i in range(11)}
    assert all(row["closeout_level"] == "L4_scope_pass" for row in demands)
    assert all("target_pass_level" not in json.dumps(row) for row in demands)
    assert all(row["product_acceptance"] for row in demands)
    assert all(row["engineering_acceptance"] for row in demands)
    assert all(row["quality_acceptance"] for row in demands)
    assert all(row["ops_acceptance"] for row in demands)

    by_level = {row["pass_level"]: row for row in pass_matrix}
    assert by_level["L4_scope_pass"]["is_slice_closeout_allowed"] is True
    assert by_level["L4_production_pass"]["is_full_product_release_gate"] is True
    for level in ["L0_smoke_pass", "L1_contract_pass", "L2_internal_dogfood_pass", "L3_release_candidate_pass"]:
        assert by_level[level]["is_slice_closeout_allowed"] is False


def test_s0_gate_blocks_missing_required_sources(tmp_path: Path) -> None:
    create_minimal_repo(tmp_path, active_docs=False, legacy_count=0)

    result = build_s0_unified_backlog(tmp_path)

    assert result.summary["status"] == "fail"
    failed_gate_ids = {row["gate_id"] for row in result.gate_rows if row["status"] == "fail"}
    assert "required_active_source_docs_exist" in failed_gate_ids
    assert "legacy_r0_r49_baseline_inventory_present" in failed_gate_ids


def test_s0_sqlite_counts_match_outputs(tmp_path: Path) -> None:
    create_minimal_repo(tmp_path)

    result = build_s0_unified_backlog(tmp_path)
    sqlite_path = result.outputs["sqlite_mirror"]

    with sqlite3.connect(sqlite_path) as conn:
        counts = dict(conn.execute("SELECT table_name, row_count FROM table_counts").fetchall())

    assert counts["demand_map"] == len(read_jsonl(result.outputs["r_document_demand_map"]))
    assert counts["implementation_tasks"] == len(read_jsonl(result.outputs["implementation_tasks"]))
    assert counts["release_board"] == len(read_jsonl(result.outputs["release_board"]))
    assert counts["gate_rows"] == len(read_jsonl(result.outputs["gate_rows"]))


def test_s0_schema_avoids_legacy_target_pass_level_field(tmp_path: Path) -> None:
    create_minimal_repo(tmp_path)

    result = build_s0_unified_backlog(tmp_path)
    schema_text = result.outputs["schema"].read_text(encoding="utf-8")
    demands_text = result.outputs["r_document_demand_map"].read_text(encoding="utf-8")

    assert "target_pass_level" not in schema_text
    assert "target_pass_level" not in demands_text
