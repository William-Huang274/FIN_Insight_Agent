"""Production-path contract checks for the v2.4 B0.1 package.

These are all synthetic, temporary and preflight-only: no receipt registrar,
runtime namespace, compiler/shadow scenario, network, provider or fixed store
is opened or written.
"""

from __future__ import annotations

import copy
import importlib.util
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.m2_a1_execution_receipt import (
    M2A1ExecutionPreflightError,
    M2A1ExecutionReceipt,
    M2A1ExternalPackageAdmission,
    M2A1ReceiptLedger,
    V2_3_ADMISSION_SCHEMA,
    V2_4_ADMISSION_SCHEMA,
    _package_payload,
    _verify_index_and_working_inputs,
    canonical_digest,
    preflight_exact_execution,
)


ROOT = Path(__file__).resolve().parents[2]
FREEZE = ROOT / "scripts/engineering/run_point01_m2_a1_operational_qualification_v2_4_refreeze.py"


@lru_cache(maxsize=1)
def _module():
    spec = importlib.util.spec_from_file_location("point01_m2_a1_b01_refreeze", FREEZE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def _artifacts():
    return _module().build_artifacts()


def _package(module, tmp_path: Path) -> dict[str, object]:
    package = copy.deepcopy(_artifacts()["package"])
    package["execution_preflight"]["execution_staging_namespace_path"] = str((tmp_path / "v2_4_namespace").resolve())
    package["package_digest"] = canonical_digest(_package_payload(package))
    return package


def _admission(package: dict[str, object], *, schema_version: str = V2_4_ADMISSION_SCHEMA) -> M2A1ExternalPackageAdmission:
    now = datetime.now(timezone.utc)
    preflight = package["execution_preflight"]
    assert isinstance(preflight, dict)
    return M2A1ExternalPackageAdmission.create(
        admission_ref="synthetic-v2-4-preflight-only",
        admission_id="synthetic-v2-4-preflight-only-id",
        admission_version=1,
        package_ref=str(package["package_ref"]),
        executable_package_digest=str(package["package_digest"]),
        scope=str(package["scope"]),
        authority_boundary=str(package["authority_boundary"]),
        reviewer_identity="william/003/total_reviewer",
        expires_at=now + timedelta(minutes=5),
        execution_staging_namespace_id=str(preflight["execution_staging_namespace_id"]),
        schema_version=schema_version,
    )


def test_v2_4_missing_admission_reaches_production_validator_not_schema_stop(tmp_path: Path) -> None:
    module = _module()
    package = _package(module, tmp_path)
    with pytest.raises(M2A1ExecutionPreflightError, match="package_admission_required"):
        preflight_exact_execution(package, None, repository_root=ROOT, receipt_id="synthetic-no-admission", scenario_id=module.BASELINE)
    assert not (tmp_path / "v2_4_namespace").exists()


def test_v2_4_unknown_or_mixed_v2_3_fields_fail_before_authority_access(tmp_path: Path) -> None:
    module = _module()
    package = _package(module, tmp_path)
    package["external_package_admission_ref"] = "v2-3-field-forbidden"
    with pytest.raises(M2A1ExecutionPreflightError, match="execution_package_schema_invalid"):
        preflight_exact_execution(package, None, repository_root=ROOT, receipt_id="synthetic-mixed-schema", scenario_id=module.BASELINE)
    assert not (tmp_path / "v2_4_namespace").exists()


def test_v2_4_synthetic_exact_admission_is_read_only_and_v2_3_is_rejected(tmp_path: Path) -> None:
    module = _module()
    package = _package(module, tmp_path)
    admitted = _admission(package)
    preflight = preflight_exact_execution(package, admitted, repository_root=ROOT, receipt_id="synthetic-read-only", scenario_id=module.BASELINE)
    assert preflight.package_contract.schema_version == "finsight_point01_m2_a1_execution_ready_audit_package_manifest_v2_4"
    assert preflight.execution_staging_namespace == (tmp_path / "v2_4_namespace").resolve()
    assert not preflight.execution_staging_namespace.exists()
    stale_authority = _admission(package, schema_version=V2_3_ADMISSION_SCHEMA)
    with pytest.raises(M2A1ExecutionPreflightError, match="admission_schema_version_mismatch"):
        preflight_exact_execution(package, stale_authority, repository_root=ROOT, receipt_id="synthetic-v2-3-authority", scenario_id=module.BASELINE)
    assert not preflight.execution_staging_namespace.exists()


@pytest.mark.parametrize("field", ["package_digest", "plan_gate_digest", "repair_gate_digest"])
def test_v2_4_cross_gate_tamper_or_wrong_repair_binding_fails_closed(tmp_path: Path, field: str) -> None:
    module = _module()
    artifacts = _artifacts()
    if field == "package_digest":
        plan = copy.deepcopy(artifacts["plan"])
        plan["exact_package"]["package_gate_digest"] = "0" * 64
        plan["plan_digest"] = module.canonical_digest({key: value for key, value in plan.items() if key != "plan_digest"})
        assert module.verify_plan(plan, artifacts["package"], artifacts["package_gate"])["status"] == "fail_closed"
    elif field == "plan_gate_digest":
        blueprint = copy.deepcopy(artifacts["blueprint"])
        blueprint["exact_binding"]["plan_gate_digest"] = "0" * 64
        blueprint["blueprint_digest"] = module.canonical_digest({key: value for key, value in blueprint.items() if key != "blueprint_digest"})
        assert module.verify_blueprint(blueprint, artifacts["package"], artifacts["package_gate"], artifacts["plan"], artifacts["plan_gate"])["status"] == "fail_closed"
    else:
        package = _package(module, tmp_path)
        package["phase_a_digests"]["repair_gate"] = "0" * 64
        package["phase_a_artifacts"]["repair_gate"]["digest"] = "0" * 64
        package["package_digest"] = canonical_digest(_package_payload(package))
        with pytest.raises(M2A1ExecutionPreflightError, match="execution_phase_a_artifact_digest_mismatch:repair_gate"):
            preflight_exact_execution(package, None, repository_root=ROOT, receipt_id="synthetic-repair-gate", scenario_id=module.BASELINE)


def test_v2_4_entries_own_their_identity_without_v2_3_loader_or_constants() -> None:
    child = (ROOT / "scripts/engineering/run_point01_m2_a1_actual_audit_clean_child_v2_4.py").read_text(encoding="utf-8")
    registrar = (ROOT / "scripts/engineering/run_point01_m2_a1_receipt_registrar_v2_4.py").read_text(encoding="utf-8")
    for source in (child, registrar):
        assert "V23_" not in source
        assert "spec_from_file_location" not in source
        assert "PACKAGE_PATH = ROOT / \"data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_4.json\"" in source


def test_v2_4_staged_drift_stops_before_consumption_or_namespace_materialization(tmp_path: Path) -> None:
    module = _module()
    package = _package(module, tmp_path)
    one_path = next(iter(package["input_file_sha256"]))

    def drifted_reader(path: Path) -> bytes:
        value = path.read_bytes()
        return value + b"\n# synthetic-drift" if path.as_posix().endswith(str(one_path).replace("\\", "/")) else value

    with pytest.raises(M2A1ExecutionPreflightError, match="execution_working_index_drift"):
        preflight_exact_execution(
            package,
            None,
            repository_root=ROOT,
            receipt_id="synthetic-pre-consume-drift",
            scenario_id=module.BASELINE,
            working_reader=drifted_reader,
        )
    assert not (tmp_path / "v2_4_namespace").exists()


def test_v2_4_post_consume_drift_is_spent_outcome_unknown_without_runtime(tmp_path: Path) -> None:
    module = _module()
    package = _package(module, tmp_path)
    admission = _admission(package)
    preflight = preflight_exact_execution(package, admission, repository_root=ROOT, receipt_id="synthetic-post-consume-drift", scenario_id=module.BASELINE)
    receipt = M2A1ExecutionReceipt.create(
        receipt_id=preflight.receipt_id,
        receipt_version=1,
        approval_id="synthetic-test-only-no-authority",
        package_ref=str(package["package_ref"]),
        executable_package_digest=str(package["package_digest"]),
        scope=str(package["scope"]),
        admission_digest=admission.admission_digest,
        nonce_sha256="b" * 64,
        expires_at=admission.expires_at,
        reviewer_identity=admission.reviewer_identity,
        execution_staging_namespace_id=admission.execution_staging_namespace_id,
        scenario_id=preflight.scenario_id,
        schema_version="finsight_point01_m2_a1_single_use_execution_receipt_v2_4",
    )
    preflight.materialize_authority_for_registration()
    ledger = M2A1ReceiptLedger.create_for_registration(preflight.ledger_path, approved_authority_root=preflight.authority_root)
    ledger.register(
        receipt,
        admission=admission,
        package_ref=str(package["package_ref"]),
        executable_package_digest=str(package["package_digest"]),
        scope=str(package["scope"]),
        authority_boundary=str(package["authority_boundary"]),
        execution_staging_namespace_id=admission.execution_staging_namespace_id,
        scenario_id=preflight.scenario_id,
        expected_admission_schema_version=V2_4_ADMISSION_SCHEMA,
        expected_receipt_schema_version="finsight_point01_m2_a1_single_use_execution_receipt_v2_4",
    )
    grant = ledger.consume_before_run(
        receipt.receipt_id,
        admission=admission,
        package_ref=str(package["package_ref"]),
        executable_package_digest=str(package["package_digest"]),
        scope=str(package["scope"]),
        authority_boundary=str(package["authority_boundary"]),
        preflight_digest=preflight.preflight_digest,
        run_root=preflight.run_root,
        execution_staging_namespace_id=admission.execution_staging_namespace_id,
        scenario_id=preflight.scenario_id,
        expected_admission_schema_version=V2_4_ADMISSION_SCHEMA,
        expected_receipt_schema_version="finsight_point01_m2_a1_single_use_execution_receipt_v2_4",
    )
    one_path = next(iter(package["input_file_sha256"]))
    with pytest.raises(M2A1ExecutionPreflightError, match="execution_working_index_drift"):
        _verify_index_and_working_inputs(
            ROOT,
            package["input_file_sha256"],
            working_reader=lambda path: path.read_bytes() + b"synthetic-drift" if path.as_posix().endswith(str(one_path).replace("\\", "/")) else path.read_bytes(),
        )
    terminal_digest = ledger.recover_consumed_without_terminal(grant.receipt_id)
    assert len(terminal_digest) == 64
    assert [event["event_type"] for event in ledger.events(grant.receipt_id)] == ["REGISTERED", "CONSUMED_BEFORE_RUN", "TERMINAL"]
    assert not preflight.runtime_root.exists()
    assert not preflight.output_path.parent.exists()
