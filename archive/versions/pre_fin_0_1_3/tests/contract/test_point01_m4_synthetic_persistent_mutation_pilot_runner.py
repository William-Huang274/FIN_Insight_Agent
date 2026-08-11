from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


pytestmark = pytest.mark.fast_contract
ROOT = Path(__file__).resolve().parents[2]


def test_m4_synthetic_persistent_mutation_pilot_is_explicitly_gated_and_restores_baseline(tmp_path: Path) -> None:
    work_root = tmp_path / "synthetic-pilot"
    approval = tmp_path / "approval.json"
    evidence = tmp_path / "evidence.json"
    result_path = tmp_path / "result.json"
    blocked = subprocess.run(
        [
            sys.executable,
            "scripts/engineering/run_point01_m4_synthetic_persistent_mutation_pilot.py",
            "--work-root",
            str(work_root),
            "--approval",
            str(approval),
            "--evidence",
            str(evidence),
            "--output",
            str(result_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert blocked.returncode != 0
    assert "execute_approved_pilot_flag_required" in blocked.stderr

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/engineering/run_point01_m4_synthetic_persistent_mutation_pilot.py",
            "--work-root",
            str(work_root),
            "--approval",
            str(approval),
            "--evidence",
            str(evidence),
            "--output",
            str(result_path),
            "--execute-approved-pilot",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(result_path.read_text(encoding="utf-8"))
    execution_evidence = json.loads(evidence.read_text(encoding="utf-8"))
    approval_record = json.loads(approval.read_text(encoding="utf-8"))
    assert result["status"] == "pass", completed.stderr
    assert result["business_case_mutation"] is False
    assert result["requested_status"] == "requested"
    assert result["executed_status"] == "executed"
    assert result["approved_read_contract_version_id"] == "contract-synthetic-pilot:v1"
    assert result["newer_contract_version_id"] == "contract-synthetic-pilot:v2"
    assert result["pinned_read_contract_version_id"] == "contract-synthetic-pilot:v1"
    assert result["rolled_back_status"] == "rolled_back"
    assert result["recovery"]["authority"] == "legacy"
    assert execution_evidence["status"] == "pass"
    assert execution_evidence["backup_restore_mode"] == "pre_mutation_baseline"
    assert execution_evidence["store_backed_errors"] == []
    assert execution_evidence["store_backed_verification"]["restored_matches_expected_baseline"] is True
    assert execution_evidence["store_backed_verification"]["restored_baseline_cutover_event_count"] == 0
    assert approval_record["authorization_decision"] == "user_explicit_approved_synthetic_persistent_pilot_only"
    assert approval_record["approver_type"] == "human"

    source = SQLiteCanonicalStore(work_root / "canonical.sqlite")
    restored = SQLiteCanonicalStore(work_root / "store_backed_restore" / "store_backed_restored.sqlite")
    source_case = source.get_latest("canonical_research_cases", "case-point01-synthetic-pilot")
    assert source_case is not None
    assert source.get_latest("canonical_case_control_versions", source_case["case_control_summary_ref"])["planning_authority"] == "legacy"
    assert len([event for event in source.list_events() if (event.get("payload") or {}).get("cutover_id")]) == 4
    assert len([event for event in restored.list_events() if (event.get("payload") or {}).get("cutover_id")]) == 0
    assert restored.content_fingerprint() == result["baseline_content_fingerprint"]
