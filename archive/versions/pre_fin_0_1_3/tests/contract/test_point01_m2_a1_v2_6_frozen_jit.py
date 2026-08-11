"""B0.3 frozen-JIT contract tests; no active human authority is created."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.m2_a1_execution_receipt import (
    HumanJITWindowApproval,
    M2A1ExecutionPreflightError,
    M2A1ExternalPackageAdmission,
    V2_5_ADMISSION_SCHEMA,
    preflight_exact_execution,
    validate_human_jit_window_approval,
)


ROOT = Path(__file__).resolve().parents[2]
FREEZE_PATH = ROOT / "scripts/engineering/run_point01_m2_a1_operational_qualification_v2_6_refreeze.py"
JIT_PATH = ROOT / "scripts/engineering/run_point01_m2_a1_v2_6_frozen_jit_window.py"
NAMESPACE = Path("D:/temp/FIN_Insight_Agent/point01_m2_a1_exact_admitted_runs_v2_6")
SPEC = importlib.util.spec_from_file_location("m2_a1_v2_6_freeze", FREEZE_PATH)
assert SPEC and SPEC.loader
freeze = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(freeze)


def _approval(artifacts: dict[str, dict[str, object]]) -> HumanJITWindowApproval:
    package, package_gate, plan, plan_gate, blueprint, blueprint_gate = (artifacts[name] for name in ("package", "package_gate", "plan", "plan_gate", "blueprint", "blueprint_gate"))
    now = datetime.now(timezone.utc)
    exact = blueprint["exact_binding"]  # type: ignore[index]
    return HumanJITWindowApproval.create(
        approval_ref="synthetic-v2-6-dry-run-only",
        approval_id="synthetic-v2-6-dry-run-only",
        approval_version=1,
        reviewer_identity="william/003/total_reviewer",
        decision="approved_single_jit_window",
        issued_at=now - timedelta(minutes=1),
        expires_at=now + timedelta(minutes=20),
        package_ref=package["package_ref"],  # type: ignore[index]
        package_digest=package["package_digest"],  # type: ignore[index]
        package_gate_digest=package_gate["gate_digest"],  # type: ignore[index]
        plan_digest=plan["plan_digest"],  # type: ignore[index]
        plan_gate_digest=plan_gate["gate_digest"],  # type: ignore[index]
        blueprint_digest=blueprint["blueprint_digest"],  # type: ignore[index]
        blueprint_gate_digest=blueprint_gate["gate_digest"],  # type: ignore[index]
        phase_a_digests=package["phase_a_digests"],  # type: ignore[index]
        incident_digest=package["incident_evidence"]["incident_digest"],  # type: ignore[index]
        expired_terminal_digest=package["incident_evidence"]["expired_terminal_digest"],  # type: ignore[index]
        scenario_id=exact["scenario_id"],  # type: ignore[index]
        input_ref=exact["input_ref"],  # type: ignore[index]
        mutation=exact["mutation"],  # type: ignore[index]
        authority_boundary=package["authority_boundary"],  # type: ignore[index]
        execution_staging_namespace_id=exact["execution_staging_namespace_id"],  # type: ignore[index]
        admission_ttl_minutes=30,
        receipt_ttl_minutes=15,
        single_use=True,
        no_retry_replay_or_renewal=True,
    )


def test_human_approval_exact_binding_and_tamper_are_deterministic() -> None:
    artifacts = freeze.build_artifacts()
    approval = _approval(artifacts)
    validator_inputs = {"package": artifacts["package"], "package_gate": artifacts["package_gate"], "plan": artifacts["plan"], "plan_gate": artifacts["plan_gate"], "blueprint": artifacts["blueprint"], "blueprint_gate": artifacts["blueprint_gate"]}
    assert validate_human_jit_window_approval(approval, **validator_inputs)["status"] == "pass"
    tampered_values = (
        {"scenario_id": "p01-wrong"},
        {"reviewer_identity": "deepseek/001/employee"},
        {"package_digest": "0" * 64},
        {"package_gate_digest": "1" * 64},
        {"plan_gate_digest": "2" * 64},
        {"blueprint_gate_digest": "3" * 64},
        {"admission_ttl_minutes": 29},
        {"receipt_ttl_minutes": 31},
        {"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)},
    )
    for update in tampered_values:
        verdict = validate_human_jit_window_approval(approval.model_copy(update=update), **validator_inputs)
        assert verdict["status"] == "human_jit_window_approval_binding_mismatch"


def test_frozen_jit_default_missing_and_synthetic_dry_run_have_zero_writes(tmp_path: Path) -> None:
    assert not NAMESPACE.exists()
    default = subprocess.run([sys.executable, str(JIT_PATH)], cwd=ROOT, text=True, capture_output=True, check=False)
    missing = subprocess.run([sys.executable, str(JIT_PATH), "--dry-run-approved-window", "--approval", str(tmp_path / "absent.json")], cwd=ROOT, text=True, capture_output=True, check=False)
    assert default.returncode == 2
    assert missing.returncode == 2
    assert json.loads(missing.stdout)["status"] == "m2_a1_frozen_jit_json_input_unreadable"
    artifacts = freeze.build_artifacts()
    approval = _approval(artifacts)
    approval_path = tmp_path / "synthetic_approval.json"
    approval_path.write_text(json.dumps(approval.model_dump(mode="json"), sort_keys=True), encoding="utf-8")
    dry = subprocess.run([sys.executable, str(JIT_PATH), "--dry-run-approved-window", "--approval", str(approval_path)], cwd=ROOT, text=True, capture_output=True, check=False)
    assert dry.returncode == 0
    payload = json.loads(dry.stdout)
    assert payload["status"] == "human_jit_window_approval_preflight_pass_no_side_effects"
    assert all(payload[key] == 0 for key in ("new_admission", "new_receipt", "namespace", "runtime", "actual"))
    for update in ({"reviewer_identity": "deepseek/001/employee"}, {"plan_gate_digest": "a" * 64}, {"receipt_ttl_minutes": 31}):
        invalid_path = tmp_path / f"invalid_{len(update)}_{next(iter(update))}.json"
        invalid_path.write_text(json.dumps(approval.model_copy(update=update).model_dump(mode="json"), sort_keys=True), encoding="utf-8")
        rejected = subprocess.run([sys.executable, str(JIT_PATH), "--dry-run-approved-window", "--approval", str(invalid_path)], cwd=ROOT, text=True, capture_output=True, check=False)
        assert rejected.returncode == 2
        rejected_payload = json.loads(rejected.stdout)
        assert rejected_payload["status"] == "human_jit_window_approval_binding_mismatch"
        assert all(rejected_payload[key] == 0 for key in ("new_admission", "new_receipt", "namespace", "runtime", "actual"))
    assert not NAMESPACE.exists()


def test_v2_5_admission_cannot_activate_v2_6_package_before_any_path_write() -> None:
    artifacts = freeze.build_artifacts()
    legacy_admission = M2A1ExternalPackageAdmission.create(
        admission_ref="historical-v2-5-non-replayable",
        admission_id="historical-v2-5-non-replayable",
        admission_version=1,
        reviewer_identity="william/003/total_reviewer",
        package_ref="point01-m2-a1-v2-5-historical",
        executable_package_digest="0" * 64,
        scope="historical_only",
        authority_boundary="historical_only",
        execution_staging_namespace_id="point01_m2_a1_exact_admitted_runs_v2_5",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        schema_version=V2_5_ADMISSION_SCHEMA,
    )
    with pytest.raises(M2A1ExecutionPreflightError, match="admission_schema_version_mismatch"):
        preflight_exact_execution(
            artifacts["package"],
            legacy_admission,
            repository_root=ROOT,
            receipt_id="historical-receipt-not-replayable",
            scenario_id="p01-baseline-separated-input",
        )
    assert not NAMESPACE.exists()
