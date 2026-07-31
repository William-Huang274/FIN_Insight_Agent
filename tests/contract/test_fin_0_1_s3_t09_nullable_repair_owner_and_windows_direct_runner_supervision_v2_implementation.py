from __future__ import annotations

import inspect
import json
from pathlib import Path
import sys
import time
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (  # noqa: E402
    DeepSeekS3ThreeCellNodeExecutor,
    S3_FOUR_LAYER_VERIFIER_LAYERS,
    S3_OWNER_GRADE_VERIFIER_STATE_MACHINE_REF,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentExecutor,
    S3VerifierStateMachineError,
)
from scripts.releases import (  # noqa: E402
    run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution as runner,
)
from scripts.releases import (  # noqa: E402
    supervise_fin_ia_0_1_s3_t09_exact_live_execution as supervisor,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


IMPLEMENTATION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s3_t09_nullable_repair_owner_and_windows_direct_runner_"
    "supervision_v2_zero_call_implementation_v1_0.json"
)
BACKLOG = (
    ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)


def _finding(
    layer: str,
    *,
    status: str = "pass",
    owner: str | None = None,
) -> dict[str, Any]:
    return {
        "layer": layer,
        "status": status,
        "issue_codes": [] if status == "pass" else ["typed_issue"],
        "artifact_or_claim_refs": (
            [] if status == "pass" else ["artifact:fixture"]
        ),
        "repair_owner": owner,
    }


def _validate(findings: list[dict[str, Any]], decision: str) -> None:
    lead_digest = canonical_digest({"lead": "fixture"})
    writer_digest = canonical_digest({"writer": "fixture"})
    S3ThreeCellBoundedAgentExecutor._validate_verifier_output(
        {
            "findings": findings,
            "bound_lead_digest": lead_digest,
            "bound_writer_digest": writer_digest,
            "decision": decision,
        },
        lead_digest,
        writer_digest,
        output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
    )


def test_request_and_validator_share_nullable_owner_v2_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        S3ThreeCellBoundedAgentExecutor,
        "_validate_owner_grade_verifier_input",
        staticmethod(lambda payload: None),
    )
    admission = S3ThreeCellBoundedAgentAdmission(
        admission_id="fin01-s3-t09-nullable-v2-zero-call-probe",
        execution_mode="zero_call_nullable_v2_probe",
        output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
    )
    _, request, _ = DeepSeekS3ThreeCellNodeExecutor._node_request(
        "verifier", {}, admission
    )
    state_machine = request["output_state_machine"]

    assert S3_OWNER_GRADE_VERIFIER_STATE_MACHINE_REF.endswith(":v2")
    assert state_machine["contract_ref"] == (
        S3_OWNER_GRADE_VERIFIER_STATE_MACHINE_REF
    )
    assert state_machine["finding_rules"]["pass"]["repair_owner"] == (
        "must_be_JSON_null"
    )
    assert state_machine["literal_JSON_examples"]["pass_repair_owner"] is None
    assert (
        state_machine["literal_JSON_examples"]["literal_string_none_allowed"]
        is False
    )
    assert "JSON null" in request["required_output_schema"]["findings"][0][
        "repair_owner"
    ]


@pytest.mark.parametrize(
    ("statuses", "decision"),
    (
        (("pass", "pass", "pass", "pass"), "accept_for_internal_review"),
        (("review_required", "pass", "pass", "pass"), "repair"),
        (("fail", "pass", "pass", "pass"), "reject"),
    ),
)
def test_nullable_owner_positive_matrix(
    statuses: tuple[str, ...],
    decision: str,
) -> None:
    _validate(
        [
            _finding(
                layer,
                status=status,
                owner=None if status == "pass" else "research_lead",
            )
            for layer, status in zip(S3_FOUR_LAYER_VERIFIER_LAYERS, statuses)
        ],
        decision,
    )


@pytest.mark.parametrize("owner", ("none", "research_lead"))
def test_pass_owner_string_is_rejected_without_normalization(owner: str) -> None:
    findings = [_finding(layer) for layer in S3_FOUR_LAYER_VERIFIER_LAYERS]
    findings[0]["repair_owner"] = owner
    with pytest.raises(S3VerifierStateMachineError) as caught:
        _validate(findings, "accept_for_internal_review")
    assert caught.value.telemetry["failure_subtype"] == "pass_with_repair_owner"
    assert caught.value.telemetry["repair_owner_persisted"] is False


@pytest.mark.parametrize("owner", (None, "none"))
def test_nonpass_null_or_literal_none_owner_is_rejected(owner: str | None) -> None:
    findings = [_finding(layer) for layer in S3_FOUR_LAYER_VERIFIER_LAYERS]
    findings[0] = _finding(
        S3_FOUR_LAYER_VERIFIER_LAYERS[0],
        status="review_required",
        owner=owner,
    )
    with pytest.raises(S3VerifierStateMachineError) as caught:
        _validate(findings, "repair")
    assert caught.value.telemetry["failure_subtype"] == (
        "nonpass_without_repair_owner"
    )


def test_direct_runner_topology_and_windows_native_probe_are_closed() -> None:
    launch_source = inspect.getsource(supervisor._launch_detached)
    windows_probe_source = inspect.getsource(
        supervisor._windows_process_snapshot
    )
    runner_entrypoint_source = inspect.getsource(runner._entrypoint)

    assert '"_child"' not in launch_source
    assert "subprocess.Popen(" in launch_source
    assert '"runner_pid": process.pid' in launch_source
    assert "OpenProcess" in windows_probe_source
    assert "GetExitCodeProcess" in windows_probe_source
    assert "os.kill" not in windows_probe_source
    assert "finally:" in runner_entrypoint_source
    assert "finalize_supervised_process" in runner_entrypoint_source


def test_nonzero_synthetic_runner_self_finalizes_typed_receipt(
    tmp_path: Path,
) -> None:
    supervision_root = tmp_path / "typed-failure"
    launch = supervisor.launch_host_lifetime_smoke(
        supervision_root,
        delay_seconds=0.05,
        fail=True,
    )
    assert launch["runner_pid"] == launch["runner_process_identity"]["pid"]

    deadline = time.monotonic() + 8
    status = supervisor.read_process_status(supervision_root)
    while status["exit_receipt"] is None and time.monotonic() < deadline:
        time.sleep(0.05)
        status = supervisor.read_process_status(supervision_root)
    receipt = status["exit_receipt"]
    assert receipt["status"] == "actual_runner_self_finalized"
    assert receipt["exit_code"] == 7
    assert receipt["typed_unhandled_failure_code"] == "process_exit_nonzero"
    assert receipt["runner_pid"] == launch["runner_pid"]
    assert receipt["automatic_retry_count"] == 0
    assert receipt["relaunch_count"] == 0


def test_pid_reuse_guard_fails_closed_without_exit_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supervision_root = tmp_path / "pid-reuse"
    supervision_root.mkdir()
    (supervision_root / "launch_receipt.json").write_text(
        json.dumps(
            {
                "contract_ref": supervisor.SUPERVISION_CONTRACT_REF,
                "runner_pid": 321,
                "runner_process_identity": {
                    "pid": 321,
                    "identity_kind": "windows_pid_and_creation_filetime",
                    "creation_filetime_100ns": 100,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        supervisor,
        "process_snapshot",
        lambda pid: {
            "pid": pid,
            "query_succeeded": True,
            "running": True,
            "identity_kind": "windows_pid_and_creation_filetime",
            "creation_filetime_100ns": 200,
        },
    )
    status = supervisor.read_process_status(supervision_root)
    assert status["status"] == "pid_reused_identity_mismatch"
    assert status["process_alive"] is False
    assert status["signals_sent"] == 0
    assert status["monitor_mutations"] == 0


def test_missing_host_capability_blocks_before_issuance_read(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        RuntimeError,
        match="s3_t09_host_lifetime_capability_receipt_missing",
    ):
        supervisor.launch_exact_run(
            tmp_path / "never-launched",
            runtime_root=tmp_path / "runtime",
            issuance_path=tmp_path / "missing-issuance.json",
            admission_path=tmp_path / "missing-admission.json",
            host_capability_receipt_path=tmp_path / "missing-capability.json",
        )
    assert not (tmp_path / "never-launched").exists()


def test_implementation_result_routes_to_fresh_agent_proof_only() -> None:
    implementation = json.loads(IMPLEMENTATION.read_text(encoding="utf-8"))
    backlog = json.loads(BACKLOG.read_text(encoding="utf-8"))

    assert implementation["status"] == (
        "pass_zero_call_nullable_repair_owner_and_windows_direct_runner_"
        "self_finalizing_supervision_v2_implemented_and_host_smoke_proven"
    )
    assert set(implementation["observed_counts"].values()) == {0}
    assert implementation["stage_decision"]["S3_T09"] == (
        "blocked_zero_artifacts_no_comparison_or_owner_acceptance"
    )
    assert implementation["next_action"] == (
        "S3-T09-NULLABLE-REPAIR-OWNER-AND-WINDOWS-DIRECT-RUNNER-"
        "SUPERVISION-V2-FRESH-AGENT-PROOF-DECISION"
    )
    assert backlog["next_action"][
        "verifier_nullable_repair_owner_and_windows_supervision_v2_implementation_ref"
    ] == (
        "configs/releases/fin_ia_0_1_s3_t09_nullable_repair_owner_and_"
        "windows_direct_runner_supervision_v2_zero_call_implementation_v1_0.json"
    )
    assert backlog["next_action"]["repair_implementation_complete"] is True
    assert backlog["next_action"]["agent_execution_authorized"] is False
    assert backlog["next_action"]["fresh_exact_admission_issuance_authorized"] is (
        True
    )
    assert backlog["next_action"]["fresh_exact_admission_consumed"] is True
    assert backlog["next_action"]["second_live_execution_authorized"] is False
