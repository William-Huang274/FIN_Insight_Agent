from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.fast_contract
ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("point01_m4_synthetic_closeout_gate", ROOT / "scripts/engineering/run_point01_m4_synthetic_closeout_gate.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_m4_synthetic_closeout_requires_human_acceptance_and_rechecks_store_backed_pilot(tmp_path: Path) -> None:
    work_root = tmp_path / "synthetic-pilot"
    approval = tmp_path / "approval.json"
    evidence = tmp_path / "evidence.json"
    pilot_result = tmp_path / "pilot-result.json"
    subprocess.run(
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
            str(pilot_result),
            "--execute-approved-pilot",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    acceptance = tmp_path / "acceptance.json"
    payload = {
        "status": "accepted",
        "decision": "accept_m4_nonproduction_synthetic_persistent_pilot",
        "reviewer_identity": "fixture-human-reviewer",
        "reviewed_at": "2026-07-12T00:00:00+00:00",
        "reviewed_artifacts": {
            "approval": {"path": str(approval), "sha256": _sha256(approval)},
            "execution_evidence": {"path": str(evidence), "sha256": _sha256(evidence)},
            "pilot_result": {"path": str(pilot_result), "sha256": _sha256(pilot_result)},
        },
    }
    acceptance.write_text(json.dumps(payload), encoding="utf-8")
    result = MODULE.build_result(
        acceptance_path=acceptance,
        approval_path=approval,
        evidence_path=evidence,
        pilot_result_path=pilot_result,
        persistent_store_path=work_root / "canonical.sqlite",
        backup_snapshot_path=work_root / "backups" / "pre_mutation_baseline.sqlite",
        work_root=tmp_path / "closeout",
    )
    assert result["status"] == "pass"
    assert result["milestone"] == "M4_complete_nonproduction_synthetic_pilot"
    assert result["store_backed_pilot_verification"]["status"] == "pass"
    assert result["business_case_mutation"] is False
    assert MODULE._acceptance_errors({**payload, "status": "pending_human_acceptance"}) == ["synthetic_human_acceptance_pending"]
