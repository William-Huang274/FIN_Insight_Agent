from __future__ import annotations

import json
from pathlib import Path

from sec_agent.r53_r60_pre_full_chain_blocker_gate import build_p21_pre_full_chain_blocker_gate
from sec_agent.r53_r60_source_doc_status_reconciliation import (
    CURRENT_STATUS_MARKER,
    EVIDENCE_REFS,
    SOURCE_DOCS,
    build_p22_source_doc_status_reconciliation,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def seed_p22_fixture(root: Path) -> None:
    for rel_path in SOURCE_DOCS.values():
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# seeded source doc\n\n{CURRENT_STATUS_MARKER}\n", encoding="utf-8")
    for key, rel_path in EVIDENCE_REFS.items():
        payload = {
            "status": "pass",
            "closeout_level": "L4_scope_pass",
            "release_decision": f"{key}_pass",
            "full_chain_broad_eval_allowed": False,
            "blocker_count_open": 3,
        }
        if key == "P21":
            payload["release_decision"] = "P21_pre_full_chain_blockers_registered_broad_full_chain_blocked"
        _write_json(root / rel_path, payload)


def test_p22_reconciles_source_docs_without_marking_broad_full_chain_ready(tmp_path: Path) -> None:
    seed_p22_fixture(tmp_path)

    summary = build_p22_source_doc_status_reconciliation(tmp_path)

    assert summary["status"] == "pass"
    assert summary["source_doc_status"] == "reconciled"
    assert summary["open_source_doc_status_rows"] == 0
    assert summary["full_chain_broad_eval_allowed"] is False
    assert summary["status_counts"]["partial"] > 0
    assert summary["status_counts"]["done"] > 0

    rows = [
        json.loads(line)
        for line in (tmp_path / summary["outputs"]["status_rows"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert {"R55", "R57", "R58", "R59", "R60"} == {row["doc_id"] for row in rows}
    assert all(row["current_status"] in {"done", "partial", "bounded_gap", "blocked", "open"} for row in rows)
    assert not any(row["current_status"] in {"planned", "draft", "unknown"} for row in rows)
    assert all(row["boundary"] and row["next_action"] for row in rows)


def test_p22_fails_when_source_doc_marker_is_missing(tmp_path: Path) -> None:
    seed_p22_fixture(tmp_path)
    (tmp_path / SOURCE_DOCS["R58"]).write_text("# seeded source doc without status section\n", encoding="utf-8")

    summary = build_p22_source_doc_status_reconciliation(tmp_path)

    assert summary["status"] == "fail"
    gates = [
        json.loads(line)
        for line in (tmp_path / summary["outputs"]["gate_rows"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    marker_gate = next(row for row in gates if row["gate_id"] == "p22_source_docs_have_current_status_sections")
    assert marker_gate["status"] == "fail"
    assert marker_gate["missing_markers"] == ["R58"]


def test_p21_closes_b03_after_p22_summary_passes(tmp_path: Path) -> None:
    seed_p22_fixture(tmp_path)
    _write_jsonl(tmp_path / "data/manifests/r53_r60_demand_map_v0_1.jsonl", [{"status": "planned"}])
    _write_jsonl(tmp_path / "data/manifests/r53_r60_implementation_tasks_v0_1.jsonl", [{"status": "planned"}])
    _write_jsonl(tmp_path / "data/manifests/r53_r60_release_board_v0_1.jsonl", [{"status": "blocked_by_dependencies"}])

    build_p22_source_doc_status_reconciliation(tmp_path)
    p21_summary = build_p21_pre_full_chain_blocker_gate(tmp_path)
    blockers = [
        json.loads(line)
        for line in (tmp_path / p21_summary["outputs"]["blockers"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    b03 = next(row for row in blockers if row["blocker_id"] == "B03-r-source-doc-status-reconciliation")
    assert b03["status"] == "closed_by_p22_source_doc_status_reconciliation"
    assert p21_summary["blocker_count_open"] == 2

