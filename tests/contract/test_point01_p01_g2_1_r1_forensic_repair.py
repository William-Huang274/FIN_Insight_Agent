"""P01-G2.1-R1 deterministic child-failure forensic regressions.

These fixtures use a fresh pytest root and a local Python child only.  They do
not open the historical authority root, fixed approval DB, formal namespace,
network client, model, provider, or business store.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.m2_a1_execution_receipt import M2A1ReceiptAuthorityError, M2A1ReceiptLedger
from sec_agent.canonical_runtime.m2_a1_v2_10_execution_proof import (
    ChildExecutionIncidentPersistenceError,
    ChildExecutionSourceRefsError,
    _argv_shape,
    _redacted_excerpt,
    capture_child_execution_outcome,
    execute_synthetic_nonhuman_v2_10_fixture,
)
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.p01_g2_1_forensic_repair import (
    validate_incident_input,
    validate_reconciliation,
    validate_repair_package,
    validate_sanitization_reconciliation,
    validate_sanitization_repair_package,
)


ROOT = Path(__file__).resolve().parents[2]
PARENT = ROOT / "scripts/engineering/run_point01_m2_a1_actual_audit_v2_10.py"
PACKAGE_DIGEST = "a" * 64
POLICY_PATH = ROOT / "configs/engineering_handoff/point01_p01_g2_1_r1_forensic_repair_policy_v1_0.json"
INCIDENT_INPUT_PATH = ROOT / "data/manifests/point01_p01_g2_1_r1_incident_input_manifest_v1_0.json"
RECONCILIATION_PATH = ROOT / "data/manifests/point01_p01_g2_1_r1_historical_incident_reconciliation_v1_0.json"
REPAIR_PACKAGE_PATH = ROOT / "data/manifests/point01_p01_g2_1_r1_forensic_repair_package_v1_0.json"
REPAIR_GATE_PATH = ROOT / "data/manifests/point01_p01_g2_1_r1_forensic_repair_gate_v1_0.json"
R1_1_POLICY_PATH = ROOT / "configs/engineering_handoff/point01_p01_g2_1_r1_1_sanitization_repair_policy_v1_0.json"
R1_1_RECONCILIATION_PATH = ROOT / "data/manifests/point01_p01_g2_1_r1_1_sanitization_reconciliation_v1_0.json"
R1_1_PACKAGE_PATH = ROOT / "data/manifests/point01_p01_g2_1_r1_1_sanitization_repair_package_v1_0.json"
R1_1_GATE_PATH = ROOT / "data/manifests/point01_p01_g2_1_r1_1_sanitization_repair_gate_v1_0.json"


def _mapping(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _source_refs() -> dict[str, str]:
    return {
        "attempt_ref": "r1-fixture-attempt",
        "receipt_id": "r1-fixture-receipt",
        "receipt_digest": "b" * 64,
        "admission_digest": "c" * 64,
        "human_approval_digest": "d" * 64,
    }


def test_r1_nonzero_child_persists_bounded_redacted_incident_before_parent_returns(tmp_path: Path) -> None:
    incident = tmp_path / "output" / "child_execution_incident.json"
    outcome = capture_child_execution_outcome(
        argv=[sys.executable, "-c", "import sys; print('token=abc'); print('fixture@example.test', file=sys.stderr); sys.exit(17)"],
        incident_path=incident,
        stage="r1_deterministic_failed_child",
        source_refs=_source_refs(),
    )
    assert outcome.returncode == 17 and incident.is_file()
    payload = json.loads(incident.read_text(encoding="utf-8"))
    assert payload["incident_envelope_digest"] == canonical_digest({key: value for key, value in payload.items() if key != "incident_envelope_digest"})
    assert payload["stdout_digest"] == hashlib.sha256(b"token=abc\n").hexdigest()
    assert payload["stderr_digest"] == hashlib.sha256(b"fixture@example.test\n").hexdigest()
    exported = json.dumps(payload, sort_keys=True)
    assert "token=abc" not in exported and "fixture@example.test" not in exported
    assert "<redacted>" in exported and "<redacted-email>" in exported
    assert len(payload["stdout_capture"]["excerpt"]) <= 512 + len("<truncated>")
    assert payload["argv_shape_digest"] == canonical_digest({"argument_count": 3, "roles": ["interpreter", "short_flag", "value"]})


def test_r1_incident_write_failure_is_fail_closed_and_preserves_child_returncode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sec_agent.canonical_runtime.m2_a1_v2_10_execution_proof as proof

    def fail_write(*_args: object, **_kwargs: object) -> str:
        raise OSError("injected_incident_disk_failure")

    monkeypatch.setattr(proof, "_write_verified", fail_write)
    with pytest.raises(ChildExecutionIncidentPersistenceError, match="returncode=23:OSError") as error:
        capture_child_execution_outcome(
            argv=[sys.executable, "-c", "import sys; sys.exit(23)"],
            incident_path=tmp_path / "incident.json",
            stage="r1_instrumentation_failure",
            source_refs={"attempt_ref": "a", "receipt_id": "r", "receipt_digest": "a" * 64, "admission_digest": "b" * 64, "human_approval_digest": "c" * 64},
        )
    assert error.value.returncode == 23


def test_r1_nonzero_child_links_envelope_to_outcome_unknown_terminal_and_denies_replay(tmp_path: Path) -> None:
    result = execute_synthetic_nonhuman_v2_10_fixture(
        temporary_root=tmp_path,
        parent=PARENT,
        package_digest=PACKAGE_DIGEST,
        branch="captured_child_nonzero",
    )
    assert result.state == "outcome_unknown" and result.actual is None
    assert result.artifact_digests["child_execution_incident"]
    assert "child_execution_incident_envelope_persisted" in result.route_trace
    ledger = M2A1ReceiptLedger.open_existing(result.ledger_path, approved_authority_root=result.ledger_path.parent)
    terminal = ledger.verify_terminal_event(
        result.receipt_id,
        expected_human_approval_digest=result.receipt.human_approval_digest,
        expected_incident_envelope_digest=result.artifact_digests["child_execution_incident"],
        expected_incident_envelope_ref="child_execution_incident.json",
    )
    assert terminal["terminal_status"] == "outcome_unknown"
    assert [item["event_type"] for item in ledger.events(result.receipt_id)] == ["REGISTERED", "CONSUMED_BEFORE_RUN", "TERMINAL"]
    with pytest.raises(M2A1ReceiptAuthorityError):
        ledger.consume_before_run(
            result.receipt_id,
            admission=result.admission,
            package_ref=result.admission.package_ref,
            executable_package_digest=PACKAGE_DIGEST,
            scope=result.admission.scope,
            authority_boundary=result.admission.authority_boundary,
            preflight_digest=result.grant.preflight_digest,
            run_root=result.ledger_path.parent.parent,
            execution_staging_namespace_id=result.admission.execution_staging_namespace_id,
            scenario_id=result.receipt.scenario_id,
            expected_admission_schema_version=result.admission.schema_version,
            expected_receipt_schema_version=result.receipt.schema_version,
            expected_human_approval_digest=result.receipt.human_approval_digest,
        )


def test_r1_empty_streams_are_explicit_and_no_actual_artifact_is_synthesized(tmp_path: Path) -> None:
    incident = tmp_path / "empty-incident.json"
    outcome = capture_child_execution_outcome(
        argv=[sys.executable, "-c", "import sys; sys.exit(19)"],
        incident_path=incident,
        stage="r1_empty_streams",
        source_refs={"attempt_ref": "a", "receipt_id": "r", "receipt_digest": "a" * 64, "admission_digest": "b" * 64, "human_approval_digest": "c" * 64},
    )
    payload = json.loads(incident.read_text(encoding="utf-8"))
    assert outcome.returncode == 19
    assert payload["stdout_capture"] == {"capture_status": "empty", "raw_length": 0, "excerpt": ""}
    assert payload["stderr_capture"] == {"capture_status": "empty", "raw_length": 0, "excerpt": ""}
    assert not (tmp_path / "actual.json").exists()


def test_r1_historical_reconciliation_is_independent_and_preserves_exact_counts() -> None:
    policy, incident, reconciliation = _mapping(POLICY_PATH), _mapping(INCIDENT_INPUT_PATH), _mapping(RECONCILIATION_PATH)
    assert validate_incident_input(incident, policy=policy) == ()
    assert validate_reconciliation(reconciliation, incident_input=incident, policy=policy) == ()
    assert reconciliation["incident_link_method"] == "independent_immutable_reconciliation_artifact"
    assert reconciliation["historical_terminal_digest"] == "13785b7d5d0bdee2459842d1eaa7137eccdbd747aa969f36aa309970194daf8c"
    assert reconciliation["historical_counts"] == {
        "baseline_attempt_count": 1,
        "baseline_success_count": 0,
        "actual_artifact_count": 0,
        "receipt_registration_count": 1,
        "receipt_consume_count": 1,
        "runtime_materialization_count": 1,
        "terminal_outcome_unknown_count": 1,
        "negative_case_execution_count": 0,
    }
    assert reconciliation["historical_child_execution_observation"]["capture_status"] == "not_persisted_pre_r1"


def test_r1_repair_package_is_forensic_only_and_gate_is_digest_bound() -> None:
    policy, package, gate = _mapping(POLICY_PATH), _mapping(REPAIR_PACKAGE_PATH), _mapping(REPAIR_GATE_PATH)
    assert validate_repair_package(package, policy=policy) == ()
    assert gate["status"] == "pass"
    assert gate["gate_digest"] == canonical_digest({key: value for key, value in gate.items() if key != "gate_digest"})
    assert package["execution_counts"] == {
        "operational_authority": 0,
        "receipt": 0,
        "baseline": 0,
        "negative_case": 0,
        "network": 0,
        "tool": 0,
        "model": 0,
        "provider": 0,
        "fixed_store_write": 0,
    }


def test_r1_1_argv_shape_digest_excludes_all_values_but_retains_flag_names() -> None:
    baseline = canonical_digest(_argv_shape(["python-a", "--token=SENSITIVE_VALUE_A", "--receipt-id", "receipt-one", "--output", "D:/private/a.json", "--", "payload-one"]))
    for changed_values in (
        ["python-b", "--token=SENSITIVE_VALUE_B", "--receipt-id", "receipt-two", "--output", "D:/private/b.json", "--", "payload-two"],
        ["python-c", "--token=DIFFERENT", "--receipt-id", "another-receipt", "--output", "C:/other/value.json", "--", "different"],
    ):
        assert canonical_digest(_argv_shape(changed_values)) == baseline
    assert canonical_digest(_argv_shape(["python-a", "--secret=SENSITIVE_VALUE_A", "--receipt-id", "receipt-one", "--output", "D:/private/a.json", "--", "payload-one"])) != baseline
    assert canonical_digest(_argv_shape(["python-a", "--token=SENSITIVE_VALUE_A", "--receipt-id", "receipt-one", "--output", "D:/private/a.json", "--", "payload-one", "extra"])) != baseline


@pytest.mark.parametrize(
    "stream,sensitive",
    [
        ('{"api_key":"SENSITIVE_JSON"}', "SENSITIVE_JSON"),
        ("token=SENSITIVE_ASSIGNMENT", "SENSITIVE_ASSIGNMENT"),
        ("User-Agent: SENSITIVE_AGENT", "SENSITIVE_AGENT"),
        ("Authorization: " + "Bearer " + "SENSITIVE" + "_BEARER", "SENSITIVE" + "_BEARER"),
        ("Cookie: session=SENSITIVE_COOKIE", "SENSITIVE_COOKIE"),
        ("Proxy-Authorization: SENSITIVE_PROXY", "SENSITIVE_PROXY"),
        ("https://example.test/x?access_token=SENSITIVE_QUERY&safe=1", "SENSITIVE_QUERY"),
    ],
)
def test_r1_1_excerpt_sanitizer_removes_supported_secret_shapes(stream: str, sensitive: str) -> None:
    payload = _redacted_excerpt(stream)
    exported = json.dumps(payload, sort_keys=True)
    assert sensitive not in exported
    assert any(marker in exported for marker in ("<redacted>", "<redacted-sensitive-line>", "<redacted-path>"))
    assert len(str(payload["excerpt"])) <= 512 + len("<truncated>")


@pytest.mark.parametrize(
    "mutation",
    [
        {"unexpected": "x"},
        {"attempt_ref": "line\nbreak"},
        {"receipt_id": "D:/private/path"},
        {"receipt_id": "https://example.test/value"},
        {"attempt_ref": "token=SENSITIVE"},
        {"attempt_ref": "x" * 129},
        {"receipt_digest": "A" * 64},
    ],
)
def test_r1_1_source_refs_reject_before_child_start_or_incident_write(tmp_path: Path, mutation: dict[str, str]) -> None:
    refs = _source_refs()
    refs.update(mutation)
    called = False

    def forbidden_runner(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal called
        called = True
        raise AssertionError("child_must_not_start")

    with pytest.raises(ChildExecutionSourceRefsError):
        capture_child_execution_outcome(
            argv=[sys.executable, "-c", "raise SystemExit(7)"],
            incident_path=tmp_path / "must-not-exist.json",
            stage="r1_1_invalid_source_refs",
            source_refs=refs,
            runner=forbidden_runner,
        )
    assert called is False and not (tmp_path / "must-not-exist.json").exists()


def test_r1_1_superseding_package_binds_rejected_r1_evidence_without_execution() -> None:
    policy = _mapping(R1_1_POLICY_PATH)
    incident = _mapping(INCIDENT_INPUT_PATH)
    reconciliation = _mapping(R1_1_RECONCILIATION_PATH)
    package = _mapping(R1_1_PACKAGE_PATH)
    gate = _mapping(R1_1_GATE_PATH)
    assert validate_sanitization_reconciliation(reconciliation, incident_input=incident, policy=policy) == ()
    assert validate_sanitization_repair_package(package, policy=policy) == ()
    assert package["supersedes"] == policy["supersedes"]
    assert package["historical_bindings"]["r1_reconciliation_digest"] == "7913ee3d38ef3ffd2d28eaf8f5fb2cf4b19545f72deb9dca8d003a032597939a"
    assert gate["status"] == "pass"
    assert gate["gate_digest"] == canonical_digest({key: value for key, value in gate.items() if key != "gate_digest"})
    assert all(value == 0 for value in package["execution_counts"].values())
