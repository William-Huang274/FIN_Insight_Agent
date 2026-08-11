"""B0.6 regressions for the default-deny v2.9 executable authority package."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.m2_a1_execution_receipt import (
    HumanJITWindowApproval,
    M2A1ExecutionPreflightError,
    M2A1ExecutionReceipt,
    M2A1ExternalPackageAdmission,
    V2_4_ADMISSION_SCHEMA,
    V2_9_ADMISSION_SCHEMA,
    V2_9_RECEIPT_SCHEMA,
    preflight_exact_execution,
)
from sec_agent.canonical_runtime.models import canonical_digest


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_PATH = ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_9.json"
ENTRY = ROOT / "scripts/engineering/run_point01_m2_a1_v2_9_frozen_jit_window.py"
NAMESPACE = Path("D:/temp/FIN_Insight_Agent/point01_m2_a1_exact_admitted_runs_v2_9")


def _package() -> dict[str, object]:
    return json.loads(PACKAGE_PATH.read_text(encoding="utf-8"))


def _mapping(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _test_only_approval(*, expired: bool) -> HumanJITWindowApproval:
    package = _package()
    package_gate = _mapping(ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_freeze_gate_result_v2_9.json")
    plan = _mapping(ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_6_executable_authority.json")
    plan_gate = _mapping(ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_6_executable_authority_gate.json")
    blueprint = _mapping(ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_6_executable_authority.json")
    blueprint_gate = _mapping(ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_6_executable_authority_gate.json")
    exact = blueprint["exact_binding"]
    assert isinstance(exact, dict)
    now = datetime.now(timezone.utc)
    expires_at = now - timedelta(minutes=1) if expired else now + timedelta(minutes=5)
    return HumanJITWindowApproval.create(
        approval_ref="test_only_external_authority_fixture",
        approval_id="test-only-v2-9-human-window",
        approval_version=1,
        reviewer_identity="william/003/total_reviewer",
        decision="approved_single_jit_window",
        issued_at=now - timedelta(minutes=2),
        expires_at=expires_at,
        package_ref=str(package["package_ref"]),
        package_digest=str(package["package_digest"]),
        package_gate_digest=str(package_gate["gate_digest"]),
        plan_digest=str(plan["plan_digest"]),
        plan_gate_digest=str(plan_gate["gate_digest"]),
        blueprint_digest=str(blueprint["blueprint_digest"]),
        blueprint_gate_digest=str(blueprint_gate["gate_digest"]),
        phase_a_digests=package["phase_a_digests"],
        incident_digest=package["incident_evidence"]["incident_digest"],
        expired_terminal_digest=package["incident_evidence"]["expired_terminal_digest"],
        scenario_id=str(exact["scenario_id"]),
        input_ref=str(exact["input_ref"]),
        mutation=str(exact["mutation"]),
        authority_boundary=str(exact["authority_boundary"]),
        execution_staging_namespace_id=str(exact["execution_staging_namespace_id"]),
        admission_ttl_minutes=30,
        receipt_ttl_minutes=15,
        single_use=True,
        no_retry_replay_or_renewal=True,
    )


def _fixture_admission(package: dict[str, object], *, schema_version: str = V2_9_ADMISSION_SCHEMA) -> M2A1ExternalPackageAdmission:
    contract = package["execution_preflight"]
    assert isinstance(contract, dict)
    human_digest = canonical_digest({"fixture_kind": "synthetic_nonhuman_fixture", "purpose": "v2_9_preflight_only"})
    return M2A1ExternalPackageAdmission.create(
        admission_ref="test_only_external_authority_fixture",
        admission_id="test-only-v2-9-admission",
        admission_version=1,
        reviewer_identity="synthetic/nonhuman-fixture",
        package_ref=str(package["package_ref"]),
        executable_package_digest=str(package["package_digest"]),
        scope=str(package["scope"]),
        authority_boundary=str(package["authority_boundary"]),
        execution_staging_namespace_id=str(contract["execution_staging_namespace_id"]),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        schema_version=schema_version,
        human_approval_digest=human_digest,
    )


def test_v2_9_missing_or_unreadable_approval_is_zero_side_effect_default_deny() -> None:
    before = NAMESPACE.exists()
    result = subprocess.run([sys.executable, str(ENTRY), "--dry-run-approved-window", "--approval", str(ROOT / "does-not-exist.json")], cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert "m2_a1_v2_9_approval_preflight_fail_closed" in result.stdout
    assert NAMESPACE.exists() is before


@pytest.mark.parametrize("expired", [False, True])
def test_v2_9_test_only_exact_or_expired_approval_dry_run_never_materializes_authority(tmp_path: Path, expired: bool) -> None:
    approval = _test_only_approval(expired=expired)
    path = tmp_path / "test-only-approval.json"
    path.write_text(json.dumps(approval.model_dump(mode="json")), encoding="utf-8")
    before = NAMESPACE.exists()
    result = subprocess.run([sys.executable, str(ENTRY), "--dry-run-approved-window", "--approval", str(path)], cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == (2 if expired else 0)
    expected = "m2_a1_v2_9_approval_preflight_fail_closed" if expired else "m2_a1_v2_9_approval_preflight_pass_no_side_effects"
    assert expected in result.stdout
    assert NAMESPACE.exists() is before


def test_v2_9_exact_test_only_external_authority_reaches_read_only_production_preflight() -> None:
    package = _package()
    admission = _fixture_admission(package)
    preflight = preflight_exact_execution(
        package,
        admission,
        repository_root=ROOT,
        receipt_id="test-only-v2-9-receipt",
        scenario_id="p01-baseline-separated-input",
        human_approval_digest=admission.human_approval_digest,
    )
    assert preflight.package_contract.admission_schema_version == V2_9_ADMISSION_SCHEMA
    assert preflight.runtime_root.exists() is False and preflight.output_path.exists() is False
    assert preflight.execution_staging_namespace == NAMESPACE


def test_v2_9_old_admission_schema_cannot_activate_new_package() -> None:
    package = _package()
    old = _fixture_admission(package, schema_version=V2_4_ADMISSION_SCHEMA)
    with pytest.raises(M2A1ExecutionPreflightError, match="admission_schema_version_mismatch"):
        preflight_exact_execution(package, old, repository_root=ROOT, receipt_id="test-only-old-authority", scenario_id="p01-baseline-separated-input", human_approval_digest=old.human_approval_digest)


def test_v2_9_receipt_schema_and_production_entries_are_frozen() -> None:
    package = _package()
    contract = package["executable_authority_contract"]
    assert isinstance(contract, dict)
    assert contract["admission_schema_version"] == V2_9_ADMISSION_SCHEMA
    assert contract["receipt_schema_version"] == V2_9_RECEIPT_SCHEMA
    assert contract["default_deny"] is True and contract["exact_approval_required"] is True
    entries = contract["entries"]
    assert isinstance(entries, dict) and set(entries) == {"orchestrator", "registrar", "parent", "clean_child"}
    assert "active_human_authority_not_issued" not in ENTRY.read_text(encoding="utf-8")
    assert "def execute(approval_path" in ENTRY.read_text(encoding="utf-8")
