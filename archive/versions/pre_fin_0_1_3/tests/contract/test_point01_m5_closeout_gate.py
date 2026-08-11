from __future__ import annotations

import json
import importlib.util
from pathlib import Path
from subprocess import run
import sys

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/engineering/run_point01_m5_closeout_gate.py"
SPEC = importlib.util.spec_from_file_location("point01_m5_closeout_gate", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_m5_closeout_gate_reflects_the_current_digest_bound_human_receipt(tmp_path) -> None:
    output = tmp_path / "m5_closeout.json"
    completed = run([sys.executable, str(SCRIPT), "--skip-fixture-rerun", "--verify-existing-package", "--output", str(output)], cwd=ROOT, capture_output=True, text=True, check=False)
    result = json.loads(output.read_text(encoding="utf-8"))
    assert set(result["completed_machine_calibrations"]) == {"persistent_budget_security_hitl_authority", "process_restart_worker_loss_crash_matrix", "concurrent_budget_reservation_and_security_drill", "hitl_interruption_drill", "semantic_impact_context_rebase_drill", "observability_incident_drill"}
    expected_manifest = [path.relative_to(ROOT).as_posix() for path in sorted((ROOT / "tests/contract").glob("test_point01_m5*.py"))]
    assert result["machine_checks"]["m5_test_manifest"]["paths"] == expected_manifest
    assert result["closeout_package"]["path_count"] > 18
    assert result["authority_boundary"]["legacy_task_run"] == "authoritative"
    full_review = json.loads((ROOT / "configs/engineering_handoff/point01_m5_human_full_calibrated_closeout_v1_0.json").read_text(encoding="utf-8"))
    receipt_is_current = (
        full_review["status"] == "accepted_m5_full_calibrated_closeout_only"
        and full_review["decision"] == "approve_m5_full_calibrated_temporary_store_closeout_only"
        and full_review["closeout_package_digest"] == MODULE._package_manifest()[1]
    )
    assert result["human_review"]["full_calibrated"]["status"] == full_review["status"]
    if receipt_is_current:
        assert completed.returncode == 0
        assert result["gate_status"] == "pass"
        assert result["milestone_status"] == "M5_complete_temporary_store_full_calibrated_reviewed"
    else:
        assert completed.returncode == 1
        assert result["gate_status"] == "fail_closed"
        assert "fixture_tranche_receipt_package_digest_mismatch" in result["unmet_closeout_conditions"]
        assert result["milestone_status"] == "M5_fixture_tranche_accepted_full_and_calibrated_closeout_pending"


def test_full_calibrated_review_can_close_only_when_bound_to_current_package_digest() -> None:
    manifest = json.loads((ROOT / "configs/engineering_handoff/point01_m5_9_closeout_gate_manifest_v1_0.json").read_text(encoding="utf-8"))
    policy = json.loads((ROOT / "configs/engineering_handoff/point01_m5_9_closeout_policy_v1_0.json").read_text(encoding="utf-8"))
    stale_tranche = json.loads((ROOT / "configs/engineering_handoff/point01_m5_human_ops_security_closeout_v1_0.json").read_text(encoding="utf-8"))
    full_review = {"review_version": "finsight_point01_m5_human_full_calibrated_closeout_v1_0", "scope": "Point01_M5_full_calibrated_temporary_store_closeout_only", "status": "accepted_m5_full_calibrated_closeout_only", "required_decision": "approve_m5_full_calibrated_temporary_store_closeout_only", "reviewer_identity": "test-independent-reviewer", "reviewed_at": "2026-07-13T10:30:00+00:00", "decision": "approve_m5_full_calibrated_temporary_store_closeout_only", "closeout_package_digest": MODULE._package_manifest()[1], "notes": "contract-only synthetic receipt"}
    result = MODULE.build_result(manifest, policy, stale_tranche, full_review, invoke_fixtures=False, invoke_checks=False, m1_result={"gate_status": "pass"})
    assert result["gate_status"] == "pass"
    assert result["milestone_status"] == "M5_complete_temporary_store_full_calibrated_reviewed"


def test_machine_calibration_semantic_validator_rejects_truthy_but_wrong_process_evidence() -> None:
    policy = json.loads((ROOT / "configs/engineering_handoff/point01_m5_9_closeout_policy_v1_0.json").read_text(encoding="utf-8"))
    fixture_results = {
        "M5.calibration": {
            "status": "pass",
            "evidence": {
                "worker_a_process_started": True,
                "worker_a_exit_code": 1,
                "worker_loss_observed": True,
                "worker_b_process_started": True,
                "worker_b_reclaimed": True,
                "recovered_fencing_token": 2,
                "stale_worker_fenced": True,
                "transaction_crash_process_started": True,
                "transaction_crash_exit_code": 73,
                "partial_row_absent_after_process_crash": True,
                "budget_crash_process_started": True,
                "budget_crash_exit_code": 74,
                "budget_artifact_committed_before_reconcile": True,
                "budget_reservation_reconciled_consumed": True,
            },
        }
    }
    details = MODULE._machine_calibration_validation_details(policy, fixture_results)
    assert details["process_restart_worker_loss_crash_matrix"]["status"] == "fail_closed"


def test_package_hash_ignores_only_m5_fixture_execution_time(tmp_path) -> None:
    fixture = tmp_path / "point01_m5_fixture_result.json"
    payload = {"result_version": "fixture-v1", "generated_at": "2026-07-13T00:00:00+00:00", "status": "pass", "evidence": {"exact": True}}
    fixture.write_text(json.dumps(payload), encoding="utf-8")
    initial = MODULE._package_file_sha256(fixture)
    fixture.write_text(json.dumps({**payload, "generated_at": "2026-07-13T00:01:00+00:00"}), encoding="utf-8")
    assert MODULE._package_file_sha256(fixture) == initial
    fixture.write_text(json.dumps({**payload, "evidence": {"exact": False}}), encoding="utf-8")
    assert MODULE._package_file_sha256(fixture) != initial
