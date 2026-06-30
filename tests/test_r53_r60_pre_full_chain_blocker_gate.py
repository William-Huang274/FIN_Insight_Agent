from __future__ import annotations

import json
from pathlib import Path

from sec_agent.r53_r60_pre_full_chain_blocker_gate import build_p21_pre_full_chain_blocker_gate


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def seed_p21_fixture(root: Path) -> None:
    manifest_dir = root / "data" / "manifests"
    _write_jsonl(
        manifest_dir / "r53_r60_demand_map_v0_1.jsonl",
        [
            {"demand_id": "U0-D01", "status": "ready_for_implementation"},
            {"demand_id": "U1-D01", "status": "planned"},
        ],
    )
    _write_jsonl(
        manifest_dir / "r53_r60_implementation_tasks_v0_1.jsonl",
        [
            {"task_id": "T0", "status": "ready_for_implementation"},
            {"task_id": "T1", "status": "planned"},
            {"task_id": "T2", "status": "planned"},
        ],
    )
    _write_jsonl(
        manifest_dir / "r53_r60_release_board_v0_1.jsonl",
        [
            {"slice_id": "S0", "status": "ready_to_start"},
            {"slice_id": "S1", "status": "blocked_by_dependencies"},
        ],
    )
    for slice_id, filename in {
        "S0": "r53_r60_unified_backlog_summary_v0_1.json",
        "S1": "r53_r60_s1_runtime_task_spine_summary_v0_1.json",
        "P14": "r53_r60_p14_data_ingestion_retrieval_control_plane_summary_v0_1.json",
        "P18": "r53_r60_p18_internal_reviewer_dogfood_window_summary_v0_1.json",
    }.items():
        _write_json(
            manifest_dir / filename,
            {
                "status": "pass",
                "closeout_level": "L4_scope_pass",
                "release_decision": f"{slice_id}_L4_scope_pass",
                "pilot_execution_status": "not_started_requires_real_internal_pilot" if slice_id == "P18" else None,
            },
        )


def test_p21_materializes_blockers_and_blocks_broad_full_chain(tmp_path: Path) -> None:
    seed_p21_fixture(tmp_path)

    summary = build_p21_pre_full_chain_blocker_gate(tmp_path)

    assert summary["status"] == "pass"
    assert summary["closeout_level"] == "L4_scope_pass_for_blocker_registration_only"
    assert summary["full_chain_broad_eval_allowed"] is False
    assert summary["blocker_count_total"] == 5
    assert summary["blocker_count_open"] == 3
    assert "20_50_case_full_chain_quality_claim" in summary["not_allowed_while_blocked"]
    assert (tmp_path / summary["outputs"]["schema"]).exists()
    assert (tmp_path / summary["outputs"]["blockers"]).exists()
    assert (tmp_path / summary["outputs"]["gate_rows"]).exists()
    assert (tmp_path / summary["outputs"]["summary"]).exists()
    assert (tmp_path / summary["outputs"]["current_status_overlay"]).exists()
    assert (tmp_path / summary["outputs"]["current_release_board"]).exists()
    assert (tmp_path / summary["outputs"]["report"]).exists()


def test_p21_records_machine_readable_board_drift_as_blocker_evidence(tmp_path: Path) -> None:
    seed_p21_fixture(tmp_path)
    summary = build_p21_pre_full_chain_blocker_gate(tmp_path)
    blockers = [
        json.loads(line)
        for line in (tmp_path / summary["outputs"]["blockers"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    first = blockers[0]
    assert first["blocker_id"] == "B01-machine-readable-backlog-status-parity"
    assert first["status"] == "closed_by_p21_current_status_overlay"
    assert first["observed_evidence"]["board_status_counts"]["demand_map"]["status_counts"] == {
        "planned": 1,
        "ready_for_implementation": 1,
    }
    assert first["observed_evidence"]["board_status_counts"]["release_board"]["status_counts"] == {
        "blocked_by_dependencies": 1,
        "ready_to_start": 1,
    }


def test_p21_gate_rows_are_diagnostic_not_product_release_pass(tmp_path: Path) -> None:
    seed_p21_fixture(tmp_path)
    summary = build_p21_pre_full_chain_blocker_gate(tmp_path)
    gates = [
        json.loads(line)
        for line in (tmp_path / summary["outputs"]["gate_rows"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert all(row["status"] == "pass" for row in gates)
    assert summary["release_decision"] == "P21_pre_full_chain_blockers_registered_broad_full_chain_blocked"
    assert "targeted_full_chain_smoke_for_integration_only" in summary["allowed_while_blocked"]


def test_p21_current_status_overlay_covers_s_and_p_slices(tmp_path: Path) -> None:
    seed_p21_fixture(tmp_path)
    summary = build_p21_pre_full_chain_blocker_gate(tmp_path)
    overlay_rows = [
        json.loads(line)
        for line in (tmp_path / summary["outputs"]["current_status_overlay"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    slice_ids = {row["slice_id"] for row in overlay_rows}

    assert {"S0", "S1", "P14", "P18", "P20", "P20b", "P21"}.issubset(slice_ids)
    p20b = next(row for row in overlay_rows if row["slice_id"] == "P20b")
    assert p20b["current_status"] == "partial_open"
    assert "P20b-D02-numeric-display-lineage" in p20b["open_boundaries"]
