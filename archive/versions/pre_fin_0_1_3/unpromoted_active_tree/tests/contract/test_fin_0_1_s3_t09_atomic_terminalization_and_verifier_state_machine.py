from __future__ import annotations

import inspect
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    DeepSeekS3ThreeCellNodeExecutor,
    S3_FOUR_LAYER_VERIFIER_LAYERS,
    S3_OWNER_GRADE_VERIFIER_STATE_MACHINE_REF,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentExecutor,
    S3VerifierStateMachineError,
)
from apps.workbench.backend.application.research_runtime import Fin01ResearchRuntime
from scripts.releases.supervise_fin_ia_0_1_s3_t09_exact_live_execution import (
    SUPERVISION_CONTRACT_REF,
    current_process_identity,
    inspect_exact_status,
    launch_host_lifetime_smoke,
    read_process_status,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    _assert_supervised_cli_execution,
)
from sec_agent.canonical_runtime.models import canonical_digest


LEAD = {"lead": "fixture"}
WRITER = {"writer": "fixture"}
LEAD_DIGEST = canonical_digest(LEAD)
WRITER_DIGEST = canonical_digest(WRITER)


def _finding(
    layer: str,
    *,
    status: str = "pass",
    issue_codes: list[str] | None = None,
    refs: list[str] | None = None,
    owner: str | None = None,
) -> dict[str, Any]:
    return {
        "layer": layer,
        "status": status,
        "issue_codes": list(issue_codes or []),
        "artifact_or_claim_refs": list(refs or []),
        "repair_owner": owner,
    }


def _output(
    findings: list[Mapping[str, Any]],
    decision: str,
) -> dict[str, Any]:
    return {
        "findings": [dict(row) for row in findings],
        "bound_lead_digest": LEAD_DIGEST,
        "bound_writer_digest": WRITER_DIGEST,
        "decision": decision,
    }


def _validate(
    findings: list[Mapping[str, Any]],
    decision: str,
    *,
    local_semantic_issues: list[str] | None = None,
) -> None:
    S3ThreeCellBoundedAgentExecutor._validate_verifier_output(
        _output(findings, decision),
        LEAD_DIGEST,
        WRITER_DIGEST,
        output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
        local_semantic_issues=local_semantic_issues or [],
    )


def _pass_findings() -> list[dict[str, Any]]:
    return [_finding(layer) for layer in S3_FOUR_LAYER_VERIFIER_LAYERS]


def test_runtime_failure_path_has_one_atomic_fail_command_with_captures() -> None:
    source = inspect.getsource(Fin01ResearchRuntime.dispatch_once)
    assert "record_research_run_provider_output_captures" not in source
    assert '"provider_output_captures": provider_output_captures' in source
    assert "command_type=\"FAIL_RESEARCH_RUN\"" in source


def test_provider_request_exposes_closed_typed_verifier_state_machine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        S3ThreeCellBoundedAgentExecutor,
        "_validate_owner_grade_verifier_input",
        staticmethod(lambda payload: None),
    )
    admission = S3ThreeCellBoundedAgentAdmission(
        admission_id="fin01-s3-t09-state-machine-zero-call-probe-v1",
        execution_mode="zero_call_state_machine_probe",
        output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
    )
    _, request, _ = DeepSeekS3ThreeCellNodeExecutor._node_request(
        "verifier",
        {},
        admission,
    )
    state_machine = request["output_state_machine"]
    assert state_machine["contract_ref"] == S3_OWNER_GRADE_VERIFIER_STATE_MACHINE_REF
    assert state_machine["finding_rules"]["pass"] == {
        "issue_codes": "must_be_empty",
        "artifact_or_claim_refs": "must_be_empty",
        "repair_owner": "must_be_JSON_null",
    }
    assert state_machine["literal_JSON_examples"]["pass_repair_owner"] is None
    assert (
        state_machine["literal_JSON_examples"]["literal_string_none_allowed"]
        is False
    )
    assert state_machine["decision_rules"]["reject"] == "iff any layer is fail"
    assert state_machine["normalization_or_silent_rewrite_allowed"] is False

    # The fake Provider derives its answer from the request state machine rather
    # than using a pre-baked output that could hide request/validator drift.
    fake_findings = []
    for layer in S3_FOUR_LAYER_VERIFIER_LAYERS:
        pass_rule = state_machine["finding_rules"]["pass"]
        assert set(pass_rule.values()) == {
            "must_be_empty",
            "must_be_JSON_null",
        }
        fake_findings.append(_finding(layer))
    _validate(fake_findings, "accept_for_internal_review")


@pytest.mark.parametrize(
    ("statuses", "decision"),
    (
        (("pass", "pass", "pass", "pass"), "accept_for_internal_review"),
        (("review_required", "pass", "pass", "pass"), "repair"),
        (("fail", "pass", "pass", "pass"), "reject"),
    ),
)
def test_three_positive_verifier_states(
    statuses: tuple[str, ...],
    decision: str,
) -> None:
    findings = [
        _finding(
            layer,
            status=status,
            issue_codes=[] if status == "pass" else ["typed_issue"],
            refs=[] if status == "pass" else ["artifact:fixture"],
            owner=None if status == "pass" else "research_lead",
        )
        for layer, status in zip(S3_FOUR_LAYER_VERIFIER_LAYERS, statuses)
    ]
    _validate(findings, decision)


@pytest.mark.parametrize(
    ("mutate", "decision", "expected_subtype"),
    (
        (
            lambda rows: rows[0].update(issue_codes=["typed_issue"]),
            "accept_for_internal_review",
            "pass_with_nonempty_issue_codes",
        ),
        (
            lambda rows: rows[0].update(
                artifact_or_claim_refs=["artifact:fixture"]
            ),
            "accept_for_internal_review",
            "pass_with_nonempty_refs",
        ),
        (
            lambda rows: rows[0].update(repair_owner="none"),
            "accept_for_internal_review",
            "pass_with_repair_owner",
        ),
        (
            lambda rows: rows[0].update(repair_owner="research_lead"),
            "accept_for_internal_review",
            "pass_with_repair_owner",
        ),
        (
            lambda rows: rows[0].update(
                status="review_required",
                artifact_or_claim_refs=["artifact:fixture"],
                repair_owner="research_lead",
            ),
            "repair",
            "nonpass_without_issue_codes",
        ),
        (
            lambda rows: rows[0].update(
                status="review_required",
                issue_codes=["typed_issue"],
                repair_owner="research_lead",
            ),
            "repair",
            "nonpass_without_refs",
        ),
        (
            lambda rows: rows[0].update(
                status="review_required",
                issue_codes=["typed_issue"],
                artifact_or_claim_refs=["artifact:fixture"],
            ),
            "repair",
            "nonpass_without_repair_owner",
        ),
        (
            lambda rows: rows[0].update(
                status="review_required",
                issue_codes=["typed_issue"],
                artifact_or_claim_refs=["artifact:fixture"],
                repair_owner="none",
            ),
            "repair",
            "nonpass_without_repair_owner",
        ),
        (
            lambda rows: None,
            "repair",
            "decision_findings_state_conflict",
        ),
    ),
)
def test_closed_negative_verifier_state_fixtures(
    mutate,
    decision: str,
    expected_subtype: str,
) -> None:
    findings = _pass_findings()
    mutate(findings)
    with pytest.raises(S3VerifierStateMachineError) as caught:
        _validate(findings, decision)
    assert caught.value.failure_code == "s3_bounded_verifier_state_machine_invalid"
    telemetry = caught.value.telemetry
    assert telemetry["failure_subtype"] == expected_subtype
    assert telemetry["failing_layer_count"] >= 1
    rendered = json.dumps(telemetry)
    assert "typed_issue" not in rendered
    assert "artifact:fixture" not in rendered
    assert "research_lead" not in rendered
    assert all(
        telemetry[key] is False
        for key in (
            "raw_issue_codes_persisted",
            "raw_refs_persisted",
            "repair_owner_persisted",
            "raw_output_persisted",
            "private_reasoning_persisted",
        )
    )


@pytest.mark.parametrize("owner", ("", "   ", 7, [], {}))
def test_nullable_owner_structural_gate_rejects_blank_or_invalid_types(
    owner: Any,
) -> None:
    findings = _pass_findings()
    findings[0]["repair_owner"] = owner
    with pytest.raises(
        ValueError, match="s3_bounded_verifier_finding_schema_invalid"
    ):
        _validate(findings, "accept_for_internal_review")


def test_local_semantic_issue_cannot_be_accepted_behind_all_pass_findings() -> None:
    with pytest.raises(S3VerifierStateMachineError) as caught:
        _validate(
            _pass_findings(),
            "accept_for_internal_review",
            local_semantic_issues=["content_not_persisted"],
        )
    assert (
        caught.value.telemetry["failure_subtype"]
        == "decision_findings_state_conflict"
    )


def test_detached_supervisor_does_not_kill_slow_fixture_child(
    tmp_path: Path,
) -> None:
    supervision_root = tmp_path / "supervision"
    marker = tmp_path / "child-finished.txt"
    launch = launch_host_lifetime_smoke(
        supervision_root,
        delay_seconds=0.25,
        marker_path=marker,
    )
    assert launch["contract_ref"] == SUPERVISION_CONTRACT_REF
    assert launch["runner_pid"] == launch["runner_process_identity"]["pid"]
    assert launch["process_topology"] == (
        "direct_actual_runner_no_intermediate_wrapper"
    )
    assert launch["parent_enforced_timeout_seconds"] is None
    assert launch["parent_may_terminate_child"] is False
    assert launch["automatic_retry_count"] == 0

    deadline = time.monotonic() + 8
    status = read_process_status(supervision_root)
    while status["exit_receipt"] is None and time.monotonic() < deadline:
        time.sleep(0.05)
        status = read_process_status(supervision_root)
    assert marker.read_text(encoding="utf-8") == "finished"
    assert status["exit_receipt"]["exit_code"] == 0
    assert status["signals_sent"] == 0
    assert status["automatic_retry_count"] == 0
    assert Path(status["exit_receipt"]["stdout_ref"]).exists()
    assert Path(status["exit_receipt"]["stderr_ref"]).exists()


def test_exact_monitor_requires_child_exit_and_consistent_terminal_truth() -> None:
    source = inspect.getsource(inspect_exact_status)
    assert "exit_receipt.get(\"exit_code\") == 0" in source
    assert "terminal_consistent" in source
    assert '"signals_sent": 0' in source
    assert '"automatic_retry_count": 0' in source


def test_direct_exact_execute_cli_requires_supervision_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FIN_IA_S3_T09_SUPERVISION_ROOT", raising=False)
    monkeypatch.delenv(
        "FIN_IA_S3_T09_SUPERVISION_CONTRACT_REF", raising=False
    )
    with pytest.raises(
        RuntimeError, match="s3_t09_exact_execute_requires_supervised_lifecycle"
    ):
        _assert_supervised_cli_execution()

    supervision_root = tmp_path / "supervision-contract"
    supervision_root.mkdir()
    host_receipt = supervision_root / "host-capability.json"
    host_receipt.write_text("{}", encoding="utf-8")
    (supervision_root / "launch_receipt.json").write_text(
        json.dumps(
            {
                "contract_ref": SUPERVISION_CONTRACT_REF,
                "process_topology": (
                    "direct_actual_runner_no_intermediate_wrapper"
                ),
                "runner_pid": os.getpid(),
                "runner_process_identity": current_process_identity(),
                "parent_enforced_timeout_seconds": None,
                "parent_may_terminate_child": False,
                "monitoring_contract": (
                    "read_only_no_signal_no_retry_no_relaunch"
                ),
                "automatic_retry_count": 0,
                "fallback_count": 0,
                "replay_count": 0,
                "relaunch_count": 0,
                "host_capability_binding": {
                    "receipt_ref": str(host_receipt),
                    "receipt_sha256": hashlib.sha256(
                        host_receipt.read_bytes()
                    ).hexdigest(),
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "FIN_IA_S3_T09_SUPERVISION_ROOT", str(supervision_root)
    )
    monkeypatch.setenv(
        "FIN_IA_S3_T09_SUPERVISION_CONTRACT_REF",
        SUPERVISION_CONTRACT_REF,
    )
    _assert_supervised_cli_execution()


def test_implementation_result_remains_traced_after_issuance_gate() -> None:
    result = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_s3_t09_atomic_terminalization_and_typed_verifier_state_machine_zero_call_implementation_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    backlog = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
        ).read_text(encoding="utf-8")
    )

    assert result["status"] == (
        "pass_zero_call_atomic_failure_terminalization_"
        "typed_verifier_state_machine_safe_telemetry_"
        "and_supervised_runner_fixture_proven"
    )
    assert set(result["observed_counts"].values()) == {0}
    assert result["stage_decision"]["S3_T09"] == (
        "blocked_zero_artifacts_no_comparison_or_owner_acceptance"
    )
    assert result["next_action"] == (
        "S3-T09-ATOMIC-CAPTURE-FAILURE-TERMINALIZATION-AND-"
        "TYPED-VERIFIER-STATE-MACHINE-FRESH-AGENT-PROOF-DECISION"
    )
    assert backlog["next_action"]["zero_call_implementation_ref"] == (
        "configs/releases/fin_ia_0_1_s3_t09_atomic_terminalization_and_"
        "typed_verifier_state_machine_zero_call_implementation_v1_0.json"
    )
    assert backlog["next_action"]["fresh_exact_live_execution_result_ref"] == (
        "configs/releases/fin_ia_0_1_s3_t09_atomic_terminalization_and_"
        "typed_verifier_state_machine_fresh_exact_live_execution_result_v1_0.json"
    )
