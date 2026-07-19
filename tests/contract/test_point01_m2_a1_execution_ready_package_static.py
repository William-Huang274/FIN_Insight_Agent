"""Static checks for the M2-A1 v2.3 receipt-invariants package freeze."""

from __future__ import annotations

import ast
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.m2_a1_execution_receipt import (
    M2A1ExecutionPreflightError,
    M2A1ExternalPackageAdmission,
    preflight_exact_execution,
)

ROOT = Path(__file__).resolve().parents[2]
FREEZE_PATH = ROOT / "scripts/engineering/run_point01_m2_a1_execution_ready_package_freeze.py"
SPEC = importlib.util.spec_from_file_location("m2_a1_execution_ready_freeze", FREEZE_PATH)
assert SPEC is not None and SPEC.loader is not None
freeze = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(freeze)


def test_freeze_uses_git_index_and_external_admission_gated_execution_mode() -> None:
    source = FREEZE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {node.names[0].name for node in tree.body if isinstance(node, ast.Import)}
    assert {"hashlib", "json", "re", "subprocess"}.issubset(imported)
    assert "import sec_agent" not in source
    assert "from sec_agent" not in source
    package = freeze.build_package()
    assert package["input_bytes_source"] == "git_index"
    assert package["execution_mode"] == "external_admission_gated"
    assert package["actual_execution_authorized_by_package"] is False
    assert package["execution_preflight"]["caller_path_override"] == "forbidden"
    assert package["receipt_lifecycle"]["executor"] == "open_existing_consume_reverify_verify_grant_before_runtime"
    assert freeze.verify_package(package)["status"] == "pass"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda package: package.__setitem__("input_bytes_source", "working_tree"),
        lambda package: package["input_file_sha256"].__setitem__(next(iter(package["input_file_sha256"])), "0" * 64),
        lambda package: package.__setitem__("authority_boundary", "self_signed_bypass"),
        lambda package: package.__setitem__("execution_mode", "unrestricted"),
    ],
)
def test_package_validator_rejects_all_authority_payload_tampering(mutation) -> None:
    package = freeze.build_package()
    tampered = deepcopy(package)
    mutation(tampered)
    assert freeze.verify_package(tampered)["status"] == "package_digest_mismatch"


def test_self_signed_package_without_external_admission_is_fail_closed() -> None:
    package = freeze.build_package()
    assert freeze.verify_external_admission(package, None)["status"] == "package_admission_required"
    gate = freeze.build_gate(package)
    assert gate["status"] == "receipt_invariants_repaired_package_frozen_pending_exact_admission"
    assert gate["actual_admission_status"] == "package_admission_required"


def _admission_for(package: dict[str, object]) -> M2A1ExternalPackageAdmission:
    return M2A1ExternalPackageAdmission.create(
        admission_ref=str(package["external_package_admission_ref"]),
        admission_id="synthetic-static-preflight-admission",
        admission_version=1,
        reviewer_identity="william/003/total_reviewer",
        package_ref=str(package["package_ref"]),
        executable_package_digest=str(package["package_digest"]),
        scope=str(package["scope"]),
        authority_boundary=str(package["authority_boundary"]),
        execution_staging_namespace_id=str(package["execution_preflight"]["execution_staging_namespace_id"]),  # type: ignore[index]
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )


def _index_reader(_root: Path, relative_path: str) -> bytes:
    return freeze._staged_bytes(relative_path)


def _staged_working_reader(path: Path) -> bytes:
    return freeze._staged_bytes(path.relative_to(ROOT).as_posix())


def test_preflight_rejects_tampered_package_or_working_drift_before_fixed_store_or_write() -> None:
    package = freeze.build_package()
    tampered = deepcopy(package)
    tampered["authority_boundary"] = "changed_without_digest"
    with pytest.raises(M2A1ExecutionPreflightError, match="execution_package_digest_mismatch"):
        preflight_exact_execution(
            tampered,
            None,
            repository_root=ROOT,
            receipt_id="static-preflight-tamper",
            scenario_id="p01-baseline-separated-input",
            index_reader=_index_reader,
            working_reader=_staged_working_reader,
            fixed_fingerprint_reader=lambda _path: pytest.fail("fixed store must not be read"),
        )

    admission = _admission_for(package)
    changed = next(iter(package["input_file_sha256"]))
    with pytest.raises(M2A1ExecutionPreflightError, match="execution_working_index_drift"):
        preflight_exact_execution(
            package,
            admission,
            repository_root=ROOT,
            receipt_id="static-preflight-drift",
            scenario_id="p01-baseline-separated-input",
            index_reader=_index_reader,
            working_reader=lambda path: b"changed" if path.relative_to(ROOT).as_posix() == changed else _staged_working_reader(path),
            fixed_fingerprint_reader=lambda _path: pytest.fail("fixed store must not be read after working drift"),
        )


def test_preflight_missing_admission_has_no_fixed_read_and_cli_has_no_caller_paths() -> None:
    package = freeze.build_package()
    with pytest.raises(M2A1ExecutionPreflightError, match="package_admission_required"):
        preflight_exact_execution(
            package,
            None,
            repository_root=ROOT,
            receipt_id="static-preflight-missing-admission",
            scenario_id="p01-baseline-separated-input",
            index_reader=_index_reader,
            working_reader=_staged_working_reader,
            fixed_fingerprint_reader=lambda _path: pytest.fail("fixed store must not be read without admission"),
        )
    cli_source = (ROOT / "scripts/engineering/run_point01_m2_a1_actual_audit.py").read_text(encoding="utf-8")
    for forbidden_argument in ("--corpus", "--case-id", "--scenario-matrix", "--package", "--temporary-root", "--receipt-ledger", "--output"):
        assert forbidden_argument not in cli_source


def test_preflight_derives_package_bound_paths_without_materializing_them() -> None:
    package = freeze.build_package()
    admission = _admission_for(package)
    preflight = preflight_exact_execution(
        package,
        admission,
        repository_root=ROOT,
        receipt_id="static-preflight-bound-paths",
        scenario_id="p03-fixed-store-path",
        index_reader=_index_reader,
        working_reader=_staged_working_reader,
        fixed_fingerprint_reader=lambda _path: freeze.FIXED_APPROVAL_SHA256,
    )
    assert preflight.runtime_scenario == {
        "scenario_id": "p03-fixed-store-path",
        "input_ref": "m2-a1-healthcare-input",
        "mutation": "attempt_open_fixed_approval_store_path",
    }
    assert preflight.ledger_path == preflight.authority_root / "m2_a1_execution_receipts.sqlite"
    assert preflight.output_path.is_relative_to(preflight.run_root)
    assert preflight.input_count == len(freeze.PACKAGE_INPUTS)


def test_actual_runner_negative_paths_use_real_accessors_not_self_reported_canary_methods() -> None:
    harness_source = (ROOT / "src/sec_agent/canonical_runtime/m2_a1_audit_harness.py").read_text(encoding="utf-8")
    assert "self._canary.reject_" not in harness_source
    assert "sqlite3.connect(self._canary.fixed_paths[0])" in harness_source
    assert "os.getenv(self._canary.ambient_resolver_env_var)" in harness_source
    assert "socket.socket().connect" in harness_source


def test_executor_and_registrar_keep_the_receipt_lifecycle_explicit() -> None:
    executor_source = (ROOT / "scripts/engineering/run_point01_m2_a1_actual_audit.py").read_text(encoding="utf-8")
    child_source = (ROOT / "scripts/engineering/run_point01_m2_a1_actual_audit_clean_child.py").read_text(encoding="utf-8")
    registrar_source = (ROOT / "scripts/engineering/run_point01_m2_a1_receipt_registrar.py").read_text(encoding="utf-8")
    assert '"-I"' in executor_source
    assert "import sec_agent" not in executor_source
    assert child_source.index("open_existing") < child_source.index("consume_before_run") < child_source.index("reverify_current_execution_tree") < child_source.index("verify_consumption_grant_before_runtime") < child_source.index("materialize_runtime_after_consumption") < child_source.index("m2_a1_audit_canary") < child_source.index("m2_a1_audit_harness")
    assert "m2_a1_audit_harness" not in registrar_source
    assert "materialize_runtime_after_consumption" not in registrar_source
