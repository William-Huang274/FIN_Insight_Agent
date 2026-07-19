from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/engineering/run_point01_m5_calibration_drills.py"
POLICY = ROOT / "configs/engineering_handoff/point01_m5_calibration_policy_v1_0.json"
SPEC = importlib.util.spec_from_file_location("point01_m5_calibration", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_local_synthetic_restart_worker_loss_and_transaction_atomicity_drills_pass() -> None:
    result = MODULE.build_result(json.loads(POLICY.read_text(encoding="utf-8")), policy_path=POLICY)
    assert result["status"] == "pass"
    assert result["evidence"]["worker_a_process_started"] is True
    assert result["evidence"]["worker_a_exit_code"] == 71
    assert result["evidence"]["worker_loss_observed"] is True
    assert result["evidence"]["worker_b_process_started"] is True
    assert result["evidence"]["worker_b_reclaimed"] is True
    assert result["evidence"]["recovered_fencing_token"] == 2
    assert result["evidence"]["stale_worker_fenced"] is True
    assert result["evidence"]["transaction_crash_process_started"] is True
    assert result["evidence"]["transaction_crash_exit_code"] == 73
    assert result["evidence"]["partial_row_absent_after_process_crash"] is True
    assert result["evidence"]["budget_crash_process_started"] is True
    assert result["evidence"]["budget_crash_exit_code"] == 74
    assert result["evidence"]["budget_artifact_committed_before_reconcile"] is True
    assert result["evidence"]["budget_reservation_reconciled_consumed"] is True
    assert result["worker_started"] is False
    assert result["external_call_count"] == 0
