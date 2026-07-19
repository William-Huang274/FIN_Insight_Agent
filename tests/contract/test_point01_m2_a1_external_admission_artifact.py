"""Static-only tests for the M2-A1 v2.3 external admission artifact."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts/engineering/run_point01_m2_a1_external_admission_artifact.py"
SPEC = importlib.util.spec_from_file_location("m2_a1_external_admission_artifact", RUNNER)
assert SPEC is not None and SPEC.loader is not None
admission_runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(admission_runner)


def _artifacts() -> tuple[dict, dict, dict, dict, datetime]:
    issued_at = datetime(2026, 7, 13, 23, 12, tzinfo=timezone.utc)
    package = admission_runner._staged_json(admission_runner.PACKAGE_PATH)
    gate = admission_runner._staged_json(admission_runner.PACKAGE_GATE_PATH)
    admission = admission_runner.build_runtime_admission(package, issued_at=issued_at, expires_at=issued_at + timedelta(minutes=30))
    authority = admission_runner.build_authority_artifact(package, gate, admission, issued_at=issued_at, nonce_bytes=b"n" * 32)
    return package, gate, admission, authority, issued_at


def test_historical_v2_3_admission_is_invalidated_by_phase_a_input_change() -> None:
    package, gate, admission, authority, issued_at = _artifacts()
    result = admission_runner.verify_admission_artifacts(package, gate, admission, authority, now=issued_at, namespace_exists=lambda _path: False)
    assert result["status"] == "fail_closed"
    assert result["checks"]["package_staged_bytes_exact"] is False
    assert result["package_digest"] == admission_runner.EXPECTED_PACKAGE_DIGEST
    assert result["execution_counts"]["execution_receipts_created"] == 0
    assert result["execution_counts"]["runtime_namespaces_created"] == 0
    assert authority["raw_nonce_persisted"] is False
    assert set(authority).isdisjoint({"nonce", "raw_nonce", "user_agent"})
    assert len(authority["nonce_sha256"]) == 64


def test_tampered_authority_or_runtime_namespace_fails_closed() -> None:
    package, gate, admission, authority, issued_at = _artifacts()
    tampered = {**authority, "scope": "wrong"}
    failed = admission_runner.verify_admission_artifacts(package, gate, admission, tampered, now=issued_at, namespace_exists=lambda _path: False)
    assert failed["status"] == "fail_closed"
    assert failed["checks"]["authority_artifact_digest_exact"] is False
    assert failed["checks"]["authority_binding_exact"] is False

    namespace_failed = admission_runner.verify_admission_artifacts(package, gate, admission, authority, now=issued_at, namespace_exists=lambda _path: True)
    assert namespace_failed["status"] == "fail_closed"
    assert namespace_failed["checks"]["runtime_namespace_absent"] is False
