"""Deterministic v2.3 receipt-lifecycle tests; never invoke an M2 scenario."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path

import pytest

from sec_agent.canonical_runtime import m2_a1_execution_receipt as receipt_module
from sec_agent.canonical_runtime.m2_a1_execution_receipt import (
    M2A1ExecutionPreflight,
    M2A1ExecutionPreflightError,
    M2A1ConsumptionGrant,
    M2A1ExecutionReceipt,
    M2A1ExternalPackageAdmission,
    M2A1ReceiptAuthorityError,
    M2A1ReceiptLedger,
    preflight_exact_execution,
)
from sec_agent.canonical_runtime.models import canonical_digest


ROOT = Path(__file__).resolve().parents[2]
FREEZE_PATH = ROOT / "scripts/engineering/run_point01_m2_a1_execution_ready_package_freeze.py"
EXECUTOR_PATH = ROOT / "scripts/engineering/run_point01_m2_a1_actual_audit.py"
CLEAN_CHILD_PATH = ROOT / "scripts/engineering/run_point01_m2_a1_actual_audit_clean_child.py"
SPEC = importlib.util.spec_from_file_location("m2_a1_receipt_lifecycle_freeze", FREEZE_PATH)
assert SPEC is not None and SPEC.loader is not None
freeze = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(freeze)


def _index_reader(_root: Path, relative_path: str) -> bytes:
    return freeze._staged_bytes(relative_path)


def _working_reader(path: Path) -> bytes:
    return freeze._staged_bytes(path.relative_to(ROOT).as_posix())


def _package(tmp_path: Path) -> dict[str, object]:
    package = deepcopy(freeze.build_package())
    contract = deepcopy(package["execution_preflight"])
    contract["execution_staging_namespace_path"] = str((tmp_path / "approved-staging").absolute())
    package["execution_preflight"] = contract
    payload = receipt_module._package_payload(package)
    package["package_digest"] = canonical_digest(payload)
    return package


def _admission(package: dict[str, object]) -> M2A1ExternalPackageAdmission:
    contract = package["execution_preflight"]
    assert isinstance(contract, dict)
    return M2A1ExternalPackageAdmission.create(
        admission_ref=str(package["external_package_admission_ref"]),
        admission_id="m2-a1-lifecycle-synthetic-admission",
        admission_version=1,
        reviewer_identity="william/003/total_reviewer",
        package_ref=str(package["package_ref"]),
        executable_package_digest=str(package["package_digest"]),
        scope=str(package["scope"]),
        authority_boundary=str(package["authority_boundary"]),
        execution_staging_namespace_id=str(contract["execution_staging_namespace_id"]),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )


def _preflight(tmp_path: Path, package: dict[str, object], admission: M2A1ExternalPackageAdmission, *, receipt_id: str = "m2-a1-lifecycle-receipt") -> M2A1ExecutionPreflight:
    return preflight_exact_execution(
        package,
        admission,
        repository_root=ROOT,
        receipt_id=receipt_id,
        scenario_id="p01-baseline-separated-input",
        index_reader=_index_reader,
        working_reader=_working_reader,
        fixed_fingerprint_reader=lambda _path: freeze.FIXED_APPROVAL_SHA256,
    )


def _receipt(preflight: M2A1ExecutionPreflight, *, expires_at: datetime | None = None) -> M2A1ExecutionReceipt:
    return M2A1ExecutionReceipt.create(
        receipt_id=preflight.receipt_id,
        receipt_version=1,
        approval_id="m2-a1-lifecycle-synthetic-approval",
        package_ref=str(preflight.package["package_ref"]),
        executable_package_digest=str(preflight.package["package_digest"]),
        scope=str(preflight.package["scope"]),
        admission_digest=preflight.admission.admission_digest,
        nonce_sha256="e" * 64,
        expires_at=expires_at or preflight.admission.expires_at,
        reviewer_identity=preflight.admission.reviewer_identity,
        execution_staging_namespace_id=preflight.admission.execution_staging_namespace_id,
        scenario_id=preflight.scenario_id,
    )


def _register(preflight: M2A1ExecutionPreflight, receipt: M2A1ExecutionReceipt) -> M2A1ReceiptLedger:
    preflight.materialize_authority_for_registration()
    ledger = M2A1ReceiptLedger.create_for_registration(preflight.ledger_path, approved_authority_root=preflight.authority_root)
    registered = ledger.register(
        receipt,
        admission=preflight.admission,
        package_ref=str(preflight.package["package_ref"]),
        executable_package_digest=str(preflight.package["package_digest"]),
        scope=str(preflight.package["scope"]),
        authority_boundary=str(preflight.package["authority_boundary"]),
        execution_staging_namespace_id=preflight.admission.execution_staging_namespace_id,
        scenario_id=preflight.scenario_id,
    )
    assert registered["registration_status"] == "registered"
    return ledger


def _consume(ledger: M2A1ReceiptLedger, preflight: M2A1ExecutionPreflight) -> M2A1ConsumptionGrant:
    return ledger.consume_before_run(
        preflight.receipt_id,
        admission=preflight.admission,
        package_ref=str(preflight.package["package_ref"]),
        executable_package_digest=str(preflight.package["package_digest"]),
        scope=str(preflight.package["scope"]),
        authority_boundary=str(preflight.package["authority_boundary"]),
        preflight_digest=preflight.preflight_digest,
        run_root=preflight.run_root,
        execution_staging_namespace_id=preflight.admission.execution_staging_namespace_id,
        scenario_id=preflight.scenario_id,
    )


def test_registration_is_authority_only_and_recovery_is_idempotent(tmp_path: Path) -> None:
    package = _package(tmp_path)
    preflight = _preflight(tmp_path, package, _admission(package))
    receipt = _receipt(preflight)
    ledger = _register(preflight, receipt)
    assert ledger.state(receipt.receipt_id)["state"] == "active_unconsumed"  # type: ignore[index]
    assert [item["event_type"] for item in ledger.events(receipt.receipt_id)] == ["REGISTERED"]
    assert not preflight.runtime_root.exists()
    assert not preflight.output_path.parent.exists()
    assert preflight.materialize_authority_for_registration() is False
    reopened = M2A1ReceiptLedger.create_for_registration(preflight.ledger_path, approved_authority_root=preflight.authority_root)
    assert reopened.register(receipt, admission=preflight.admission, package_ref=str(package["package_ref"]), executable_package_digest=str(package["package_digest"]), scope=str(package["scope"]), authority_boundary=str(package["authority_boundary"]), execution_staging_namespace_id=preflight.admission.execution_staging_namespace_id, scenario_id=preflight.scenario_id)["registration_status"] == "already_registered_exact"


def test_existing_ledger_consumes_before_any_runtime_or_output_materialization(tmp_path: Path) -> None:
    package = _package(tmp_path)
    preflight = _preflight(tmp_path, package, _admission(package))
    _register(preflight, _receipt(preflight))
    executor_ledger = M2A1ReceiptLedger.open_existing(preflight.ledger_path, approved_authority_root=preflight.authority_root)
    grant = _consume(executor_ledger, preflight)
    assert grant.state == "consumed_before_run"
    assert not preflight.runtime_root.exists()
    assert not preflight.output_path.parent.exists()
    consumed = preflight.materialize_runtime_after_consumption(grant, ledger=executor_ledger)
    assert consumed.state == "consumed_before_run"
    assert preflight.runtime_root.is_dir()
    assert preflight.output_path.parent.is_dir()
    assert [item["event_type"] for item in executor_ledger.events(consumed.receipt_id)] == ["REGISTERED", "CONSUMED_BEFORE_RUN"]


def test_registered_only_or_forged_grant_cannot_materialize_runtime_or_output(tmp_path: Path) -> None:
    package = _package(tmp_path)
    preflight = _preflight(tmp_path, package, _admission(package))
    receipt = _receipt(preflight)
    ledger = _register(preflight, receipt)
    registered_only_grant = M2A1ConsumptionGrant.create(
        receipt_id=receipt.receipt_id,
        consumed_receipt_digest=receipt.receipt_digest,
        admission_digest=preflight.admission.admission_digest,
        executable_package_digest=str(package["package_digest"]),
        scenario_id=preflight.scenario_id,
        run_root=str(preflight.run_root),
        preflight_digest=preflight.preflight_digest,
    )
    with pytest.raises(M2A1ExecutionPreflightError, match="receipt_consumption_grant_receipt_not_consumed"):
        preflight.materialize_runtime_after_consumption(registered_only_grant, ledger=ledger)
    assert not preflight.runtime_root.exists()
    assert not preflight.output_path.parent.exists()

    grant = _consume(ledger, preflight)
    forged = grant.model_copy(update={"grant_digest": "0" * 64})
    with pytest.raises(M2A1ExecutionPreflightError, match="receipt_consumption_grant_digest_invalid"):
        preflight.materialize_runtime_after_consumption(forged, ledger=ledger)
    assert not preflight.runtime_root.exists()
    assert not preflight.output_path.parent.exists()


def test_register_rejects_wrong_scenario_and_wrong_package_at_authority_layer(tmp_path: Path) -> None:
    package = _package(tmp_path)
    preflight = _preflight(tmp_path, package, _admission(package))
    preflight.materialize_authority_for_registration()
    ledger = M2A1ReceiptLedger.create_for_registration(preflight.ledger_path, approved_authority_root=preflight.authority_root)
    wrong_scenario = _receipt(preflight).model_copy(update={"scenario_id": "wrong-scenario"})
    with pytest.raises(M2A1ReceiptAuthorityError, match="receipt_binding_mismatch"):
        ledger.register(
            wrong_scenario,
            admission=preflight.admission,
            package_ref=str(package["package_ref"]),
            executable_package_digest=str(package["package_digest"]),
            scope=str(package["scope"]),
            authority_boundary=str(package["authority_boundary"]),
            execution_staging_namespace_id=preflight.admission.execution_staging_namespace_id,
            scenario_id=preflight.scenario_id,
        )
    wrong_package = _receipt(preflight).model_copy(update={"executable_package_digest": "f" * 64})
    with pytest.raises(M2A1ReceiptAuthorityError, match="receipt_executable_package_digest_mismatch"):
        ledger.register(
            wrong_package,
            admission=preflight.admission,
            package_ref=str(package["package_ref"]),
            executable_package_digest=str(package["package_digest"]),
            scope=str(package["scope"]),
            authority_boundary=str(package["authority_boundary"]),
            execution_staging_namespace_id=preflight.admission.execution_staging_namespace_id,
            scenario_id=preflight.scenario_id,
        )
    assert not preflight.runtime_root.exists()
    assert not preflight.output_path.parent.exists()


def test_post_consume_drift_stop_records_outcome_unknown_without_runtime_materialization(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package = _package(tmp_path)
    preflight = _preflight(tmp_path, package, _admission(package))
    _register(preflight, _receipt(preflight))
    ledger = M2A1ReceiptLedger.open_existing(preflight.ledger_path, approved_authority_root=preflight.authority_root)
    _consume(ledger, preflight)
    monkeypatch.setattr(M2A1ExecutionPreflight, "reverify_current_execution_tree", lambda _self: (_ for _ in ()).throw(M2A1ExecutionPreflightError("execution_working_index_drift:synthetic")))
    with pytest.raises(M2A1ExecutionPreflightError, match="execution_working_index_drift:synthetic"):
        preflight.reverify_current_execution_tree()
    terminal_digest = ledger.recover_consumed_without_terminal(preflight.receipt_id)
    assert len(terminal_digest) == 64
    assert [item["event_type"] for item in ledger.events(preflight.receipt_id)] == ["REGISTERED", "CONSUMED_BEFORE_RUN", "TERMINAL"]
    assert not preflight.runtime_root.exists()
    assert not preflight.output_path.parent.exists()


def test_executor_reverify_failure_spends_receipt_and_does_not_materialize_or_import_m2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Exercise the CLI's post-consume failure branch without an M2 import."""

    spec = importlib.util.spec_from_file_location("m2_a1_isolated_executor", CLEAN_CHILD_PATH)
    assert spec is not None and spec.loader is not None
    executor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(executor)

    package = {
        "package_ref": "synthetic-package-ref",
        "package_digest": "a" * 64,
        "scope": "synthetic-scope",
        "authority_boundary": "synthetic-boundary",
    }
    admission = M2A1ExternalPackageAdmission.create(
        admission_ref="synthetic-admission-ref",
        admission_id="synthetic-admission-id",
        admission_version=1,
        reviewer_identity="william/003/total_reviewer",
        package_ref=str(package["package_ref"]),
        executable_package_digest=str(package["package_digest"]),
        scope=str(package["scope"]),
        authority_boundary=str(package["authority_boundary"]),
        execution_staging_namespace_id="synthetic-namespace",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )

    class FakePreflight:
        receipt_id = "synthetic-receipt"
        authority_root = tmp_path / "authority"
        ledger_path = authority_root / "ledger.sqlite"
        preflight_digest = "b" * 64
        run_root = tmp_path / "run"
        scenario_id = "p01-baseline-separated-input"
        materialized = False

        def reverify_current_execution_tree(self) -> None:
            raise M2A1ExecutionPreflightError("execution_working_index_drift:synthetic")

        def verify_consumption_grant_before_runtime(self, *_args: object, **_kwargs: object) -> object:
            pytest.fail("grant verification must follow successful reverify")

        def materialize_runtime_after_consumption(self, *_args: object, **_kwargs: object) -> object:
            self.materialized = True
            pytest.fail("runtime/output must not materialize after reverify drift")

    preflight = FakePreflight()

    class FakeLedger:
        consumed = False
        recovered = False

        def consume_before_run(self, *_args: object, **_kwargs: object) -> object:
            self.consumed = True
            return object()

        def recover_consumed_without_terminal(self, receipt_id: str) -> str:
            assert receipt_id == preflight.receipt_id
            self.recovered = True
            return "c" * 64

    ledger = FakeLedger()

    class FakeLedgerType:
        @staticmethod
        def open_existing(*_args: object, **_kwargs: object) -> FakeLedger:
            return ledger

    monkeypatch.setattr(
        executor,
        "_json",
        lambda path: package if Path(path) == executor.PACKAGE_PATH else admission.model_dump(mode="json"),
    )
    monkeypatch.setattr(receipt_module, "preflight_exact_execution", lambda *_args, **_kwargs: preflight)
    monkeypatch.setattr(receipt_module, "M2A1ReceiptLedger", FakeLedgerType)

    assert executor.main(
        [
            "--execute-admitted",
            "--admission",
            str(tmp_path / "admission.json"),
            "--receipt-id",
            preflight.receipt_id,
            "--scenario-id",
            preflight.scenario_id,
        ]
    ) == 1
    result = capsys.readouterr().out
    assert "m2_a1_post_consume_outcome_unknown" in result
    assert ledger.consumed is True
    assert ledger.recovered is True
    assert preflight.materialized is False
    assert not (preflight.run_root / "runtime").exists()


def test_replay_and_missing_ledger_stop_before_runtime_output_or_import(tmp_path: Path) -> None:
    package = _package(tmp_path)
    preflight = _preflight(tmp_path, package, _admission(package))
    with pytest.raises(M2A1ReceiptAuthorityError, match="receipt_ledger_not_registered_no_create"):
        M2A1ReceiptLedger.open_existing(preflight.ledger_path, approved_authority_root=preflight.authority_root)
    assert not preflight.run_root.exists()
    _register(preflight, _receipt(preflight))
    ledger = M2A1ReceiptLedger.open_existing(preflight.ledger_path, approved_authority_root=preflight.authority_root)
    _consume(ledger, preflight)
    with pytest.raises(M2A1ReceiptAuthorityError, match="receipt_already_consumed|receipt_binding_mismatch"):
        _consume(ledger, preflight)
    assert not preflight.runtime_root.exists()
    assert not preflight.output_path.parent.exists()


@pytest.mark.parametrize("kind", ["expired", "wrong_package", "tampered"])
def test_invalid_receipt_never_materializes_runtime_or_output(tmp_path: Path, kind: str) -> None:
    package = _package(tmp_path)
    preflight = _preflight(tmp_path, package, _admission(package))
    receipt = _receipt(preflight, expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)) if kind == "expired" else _receipt(preflight)
    if kind == "wrong_package":
        receipt = receipt.model_copy(update={"executable_package_digest": "f" * 64})
    if kind == "tampered":
        receipt = receipt.model_copy(update={"receipt_digest": "0" * 64})
    preflight.materialize_authority_for_registration()
    ledger = M2A1ReceiptLedger.create_for_registration(preflight.ledger_path, approved_authority_root=preflight.authority_root)
    with pytest.raises(M2A1ReceiptAuthorityError):
        ledger.register(receipt, admission=preflight.admission, package_ref=str(package["package_ref"]), executable_package_digest=str(package["package_digest"]), scope=str(package["scope"]), authority_boundary=str(package["authority_boundary"]), execution_staging_namespace_id=preflight.admission.execution_staging_namespace_id, scenario_id=preflight.scenario_id)
    assert not preflight.runtime_root.exists()
    assert not preflight.output_path.parent.exists()


def test_crash_after_consume_is_terminal_outcome_unknown_and_never_reactivates(tmp_path: Path) -> None:
    package = _package(tmp_path)
    preflight = _preflight(tmp_path, package, _admission(package))
    _register(preflight, _receipt(preflight))
    ledger = M2A1ReceiptLedger.open_existing(preflight.ledger_path, approved_authority_root=preflight.authority_root)
    _consume(ledger, preflight)
    terminal_digest = ledger.recover_consumed_without_terminal(preflight.receipt_id)
    assert len(terminal_digest) == 64
    assert [item["event_type"] for item in ledger.events(preflight.receipt_id)] == ["REGISTERED", "CONSUMED_BEFORE_RUN", "TERMINAL"]
    with pytest.raises(M2A1ReceiptAuthorityError, match="receipt_terminal_already_recorded"):
        ledger.recover_consumed_without_terminal(preflight.receipt_id)
    assert not preflight.runtime_root.exists()
    assert not preflight.output_path.parent.exists()


def test_package_lifecycle_contract_tamper_fails_before_fixed_fingerprint_or_write(tmp_path: Path) -> None:
    package = _package(tmp_path)
    package["receipt_lifecycle"] = {"registrar": "bypass"}
    with pytest.raises(M2A1ExecutionPreflightError, match="execution_package_digest_mismatch"):
        _preflight(tmp_path, package, _admission(package))
