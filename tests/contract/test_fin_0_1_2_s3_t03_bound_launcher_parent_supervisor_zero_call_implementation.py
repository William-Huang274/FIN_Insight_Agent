from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "releases"))

IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_bound_execution_launcher_"
    "parent_supervisor_zero_call_preflight_minimum_implementation_v1_0.json"
)
TEST_SUCCESSOR = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_launcher_supervisor_projection_"
    "assertion_test_controlled_successor_v5_0.json"
)
PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_27.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
EXECUTION_NEXT = (
    "FIN-0.1.2-S3-T03-NVDA-EXACT-LIVE-EXECUTION-AND-TERMINAL-"
    "MATERIALIZATION"
)
FAILURE_NEXT = (
    "FIN-0.1.2-S3-T03-NVDA-RESEARCH-LEAD-LOCAL-FACT-PRESENCE-AND-"
    "CLAIM-ALIAS-SEMANTIC-OWNERSHIP-REGRESSION-DISPOSITION-DECISION"
)
LEAD_V8_PROOF_NEXT = (
    "FIN-0.1.2-S3-T03-RESEARCH-LEAD-V8-LOCAL-SEMANTIC-"
    "MATERIALIZATION-INDEPENDENT-ZERO-CALL-PROOF-DECISION"
)
REPLACEMENT_AUTHORITY_NEXT = (
    "FIN-0.1.2-S3-T03-NVDA-REPLACEMENT-EXACT-LIVE-FRESH-"
    "ADMISSION-AUTHORITY-DECISION"
)
CONTROLLED_SUCCESSOR_NEXT = (
    "FIN-0.1.2-S3-T03-NVDA-REPLACEMENT-ADMISSION-ENVELOPE-ISSUER-"
    "SUPERVISOR-CONTROLLED-SUCCESSOR-MINIMUM-ZERO-CALL-IMPLEMENTATION"
)
TERMINAL_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_exact_live_execution_"
    "terminal_failure_result_v1_0.json"
)
CURRENT_PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_29.json"
)
LEAD_V8_PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_30.json"
)

from apps.workbench.backend.application.fin_0_1_2_s3_t03_exact_live_runner import (
    Fin012S3T03RunnerError,
    claim_supervised_execution_identity,
    load_bound_s3_t03_execution_envelope,
)
from sec_agent.canonical_runtime.models import canonical_digest
from run_fin_ia_0_1_2_s3_t03_nvda_supervised_exact_live import (
    ADMISSION,
    EXPECTED_ADMISSION_DIGEST,
    EXPECTED_ADMISSION_SHA256,
    EXPECTED_ISSUANCE_SHA256,
    ISSUANCE,
    Fin012S3T03SupervisedLiveError,
    _child_command,
    _run_child,
    load_admission,
    load_target,
    prepare_exact_input,
    run_zero_call_preflight,
    supervise_exact_execution,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_launcher_loads_only_the_frozen_issued_unconsumed_admission() -> None:
    target = load_target()
    admission = load_admission(target)

    assert _sha256(ADMISSION) == EXPECTED_ADMISSION_SHA256
    assert _sha256(ISSUANCE) == EXPECTED_ISSUANCE_SHA256
    assert target.admission_digest == EXPECTED_ADMISSION_DIGEST
    assert canonical_digest(admission.digest_payload()) == EXPECTED_ADMISSION_DIGEST
    assert target.execution_identity == "fin012-s3-t03-nvda-primary-r1"
    assert target.runtime_root_ref == ".codex_runtime/fin012-s3-t03-nvda-primary-r1"
    assert admission.max_provider_calls == 9
    assert admission.max_transport_attempts_per_call == 1
    assert admission.retry_budget == 0


def test_production_rehydration_matches_the_frozen_exact_input(
    tmp_path: Path,
) -> None:
    target = load_target()
    admission = load_admission(target)

    prepared = prepare_exact_input(tmp_path / "rehydrate", target, admission)

    assert prepared.execution_identity == target.execution_identity
    assert prepared.input_digest == target.complete_input_digest
    assert prepared.preparation_digest == target.preparation_digest
    assert prepared.work_unit_id == target.work_unit_id
    assert prepared.attempt_id == target.attempt_id
    assert prepared.research_run_id == target.research_run_id


def test_real_child_zero_call_preflight_never_claims_the_target_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = load_target()
    target_runtime = ROOT / target.runtime_root_ref
    if target_runtime.exists():
        terminal = _load(TERMINAL_RESULT)
        assert terminal["authority"]["admission_consumed"] is True
        assert terminal["typed_terminal"]["status"] == "failed"
        assert _sha256(target_runtime / "execution-result.json") == terminal[
            "typed_terminal"
        ]["execution_result_sha256"]
        return
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-secret-never-persist")

    output = tmp_path / "preflight.json"
    result = run_zero_call_preflight(output)

    assert result["status"] == "pass_real_child_parent_supervisor_zero_call_preflight"
    assert result["child_process_launch_count"] == 1
    assert result["observed_counts"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "execution_network_calls": 0,
        "source_network_calls": 0,
        "external_tool_calls": 0,
        "business_runs": 0,
        "business_artifacts": 0,
    }
    assert result["admission_consumed"] is False
    assert result["execution_started"] is False
    assert result["target_runtime_root_absent_before_and_after"] is True
    assert not target_runtime.exists()
    assert "fixture-secret-never-persist" not in output.read_text(encoding="utf-8")


def test_live_supervision_refuses_without_a_later_exact_execution_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = load_target()
    target_runtime = ROOT / target.runtime_root_ref
    terminal_before = (
        _sha256(target_runtime / "execution-result.json")
        if target_runtime.exists()
        else None
    )
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-secret-never-persist")
    authority = tmp_path / "not-authorized.json"
    authority.write_text(
        json.dumps(
            {
                "status": "implementation_only",
                "authority": {
                    "future_exact_live_execution_authorized": False,
                    "current_turn_admission_consumption_or_execution_authorized": False,
                },
                "source_authority": {"admission_digest": target.admission_digest},
                "exact_execution_target": {
                    "execution_identity": target.execution_identity
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        Fin012S3T03SupervisedLiveError,
        match="later_execution_authority_invalid",
    ):
        supervise_exact_execution(
            supervision_root=tmp_path / "supervision",
            execution_authority=authority,
        )
    if terminal_before is None:
        assert not target_runtime.exists()
    else:
        assert _sha256(target_runtime / "execution-result.json") == terminal_before


@pytest.mark.parametrize(
    ("behavior", "timeout_seconds", "expected_exit_code", "expected_reason"),
    (
        ("exit", 10, 17, "child_exit_without_terminal"),
        ("sleep", 1, None, "parent_timeout"),
    ),
)
def test_parent_real_subprocess_abnormal_exit_and_timeout_materialize_terminal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    behavior: str,
    timeout_seconds: int,
    expected_exit_code: int | None,
    expected_reason: str,
) -> None:
    target = load_target()
    runtime = tmp_path / f"runtime-{behavior}"
    supervision = tmp_path / f"supervision-{behavior}"
    envelope = load_bound_s3_t03_execution_envelope(ROOT)
    secret = f"fixture-secret-{behavior}-never-persist"
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)
    monkeypatch.setenv("FIN_IA_S3_T03_ALLOW_TEST_FIXTURE_CHILD", "1")
    claim_supervised_execution_identity(
        runtime,
        envelope,
        supervision_root=supervision,
    )
    command = _child_command("fixture-child", runtime, supervision) + [
        "--fixture-behavior",
        behavior,
    ]

    receipt = _run_child(
        command=command,
        runtime_root=runtime,
        supervision_root=supervision,
        timeout_seconds=timeout_seconds,
        mode=f"fixture_{behavior}",
        finalize_missing_terminal=True,
    )

    result = _load(runtime / "execution-result.json")
    state = _load(runtime / "execution-state.json")
    assert receipt["timed_out"] is (behavior == "sleep")
    if expected_exit_code is not None:
        assert receipt["exit_code"] == expected_exit_code
    assert receipt["automatic_retry_count"] == 0
    assert receipt["fallback_count"] == 0
    assert receipt["replay_count"] == 0
    assert receipt["relaunch_count"] == 0
    assert result["status"] == "failed"
    assert result["terminal"]["phase"] == "supervisor_exit"
    assert result["terminal"]["supervisor_exit"]["reason"] == expected_reason
    assert result["capture_objects"] == []
    assert result["artifacts"] == []
    assert state["status"] == "terminal"
    assert state["terminal_materialized"] is True
    persisted = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (*runtime.rglob("*"), *supervision.rglob("*"))
        if path.is_file()
    )
    assert secret not in persisted
    assert target.execution_identity in persisted


def test_parent_claim_and_supervision_root_are_exactly_once(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "runtime"
    supervision = tmp_path / "supervision"
    envelope = load_bound_s3_t03_execution_envelope(ROOT)
    claim_supervised_execution_identity(
        runtime,
        envelope,
        supervision_root=supervision,
    )

    with pytest.raises(Fin012S3T03RunnerError, match="already_claimed"):
        claim_supervised_execution_identity(
            runtime,
            envelope,
            supervision_root=supervision,
        )
    supervision.mkdir()
    with pytest.raises(FileExistsError):
        _run_child(
            command=[sys.executable, "-c", "raise SystemExit(0)"],
            runtime_root=runtime,
            supervision_root=supervision,
            timeout_seconds=10,
            mode="replay",
            finalize_missing_terminal=False,
        )


def test_parent_launch_failure_materializes_terminal_after_identity_claim(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "runtime-launch-failure"
    supervision = tmp_path / "supervision-launch-failure"
    envelope = load_bound_s3_t03_execution_envelope(ROOT)
    claim_supervised_execution_identity(
        runtime,
        envelope,
        supervision_root=supervision,
    )

    receipt = _run_child(
        command=[str(tmp_path / "executable-that-does-not-exist")],
        runtime_root=runtime,
        supervision_root=supervision,
        timeout_seconds=10,
        mode="fixture_launch_failure",
        finalize_missing_terminal=True,
    )

    result = _load(runtime / "execution-result.json")
    failure = _load(supervision / "launch-failure-receipt.json")
    assert receipt["launch_failed"] is True
    assert receipt["child_pid"] is None
    assert receipt["automatic_retry_count"] == 0
    assert failure["child_terminated_if_started"] is False
    assert result["status"] == "failed"
    assert result["terminal"]["supervisor_exit"]["reason"] == (
        "parent_launch_failure"
    )
    assert _load(runtime / "execution-state.json")["status"] == "terminal"


def test_runner_child_transition_accepts_only_the_matching_supervisor_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.workbench.backend.application import (
        fin_0_1_2_s3_t03_exact_live_runner as runner,
    )

    envelope = load_bound_s3_t03_execution_envelope(ROOT)
    runtime = tmp_path / "runtime"
    supervision = tmp_path / "supervision"
    claim_supervised_execution_identity(
        runtime,
        envelope,
        supervision_root=supervision,
    )
    runner._claim_execution_identity(runtime, envelope)
    state = _load(runtime / "execution-state.json")
    assert state["status"] == "execution_claimed"
    assert state["supervision_root"] == str(supervision.resolve())

    with pytest.raises(Fin012S3T03RunnerError, match="already_claimed"):
        runner._claim_execution_identity(runtime, envelope)


def test_implementation_projection_backlog_and_project_os_are_current() -> None:
    implementation = _load(IMPLEMENTATION)
    projection = _load(PROJECTION)
    backlog = _load(BACKLOG)["next_action"]
    target = load_target()

    assert implementation["status"].startswith("pass_zero_call_real_child")
    assert implementation["immutable_execution_inputs"]["admission_consumed"] is False
    assert implementation["immutable_execution_inputs"]["execution_started"] is False
    for row in implementation["implementation_bindings"]:
        path = ROOT / row["ref"]
        current_bytes = path.stat().st_size
        current_sha256 = _sha256(path)
        if current_bytes == row["bytes"] and current_sha256 == row["sha256"]:
            continue
        assert row["ref"] == (
            "tests/contract/test_fin_0_1_2_s3_t03_bound_launcher_"
            "parent_supervisor_zero_call_implementation.py"
        )
        successor = _load(TEST_SUCCESSOR)
        assert successor["historical_binding"] == {
            "ref": row["ref"],
            "sha256": row["sha256"],
            "bytes": row["bytes"],
        }
        assert successor["current_binding"] == {
            "ref": row["ref"],
            "sha256": current_sha256,
            "bytes": current_bytes,
        }
        assert successor["historical_implementation"]["sha256"] == _sha256(
            IMPLEMENTATION
        )
        assert successor["change_boundary"]["runtime_code_changed"] is False
        assert successor["change_boundary"][
            "historical_implementation_rewritten"
        ] is False
        assert successor["change_boundary"][
            "admission_model_business_or_budget_contract_changed"
        ] is False
    implementation_sha = _sha256(IMPLEMENTATION)
    assert projection["decision_binding"]["sha256"] == implementation_sha
    assert projection["current_truth"]["current_next_action"] == (
        "FIN-0.1.2-S3-T03-NVDA-EXACT-LIVE-EXECUTION-AUTHORITY-DECISION-R2"
    )
    if backlog["item_id"] == projection["current_truth"]["current_next_action"]:
        assert backlog["current_projection_sha256"] == _sha256(PROJECTION)
    else:
        assert backlog["item_id"] in {
            EXECUTION_NEXT,
            FAILURE_NEXT,
            LEAD_V8_PROOF_NEXT,
            REPLACEMENT_AUTHORITY_NEXT,
            CONTROLLED_SUCCESSOR_NEXT,
        }
        current = ROOT / backlog["current_projection_ref"]
        if backlog["item_id"] == EXECUTION_NEXT:
            assert current.name == "fin_ia_0_1_2_current_program_projection_v2_28.json"
            assert _load(current)["historical_projection_policy"][
                "superseded_projection"
            ].endswith("fin_ia_0_1_2_current_program_projection_v2_27.json")
        elif backlog["item_id"] == FAILURE_NEXT:
            assert current == CURRENT_PROJECTION
            assert backlog["S3_T03_fresh_admission_consumed"] is True
            assert backlog["S3_T03_execution_terminal_status"] == "failed"
            assert backlog["S3_T03_execution_result_sha256"] == _sha256(
                TERMINAL_RESULT
            )
        elif backlog["item_id"] == LEAD_V8_PROOF_NEXT:
            assert current == LEAD_V8_PROJECTION
            assert backlog["S3_T03_Lead_v8_status"] == (
                "engineering_pass_independent_proof_pending"
            )
        elif backlog["item_id"] == REPLACEMENT_AUTHORITY_NEXT:
            assert backlog["item_id"] == REPLACEMENT_AUTHORITY_NEXT
            assert current.name == "fin_ia_0_1_2_current_program_projection_v2_31.json"
            assert backlog["S3_T03_Lead_v8_status"] == (
                "engineering_pass_independent_two_fresh_process_zero_call_proof_pass"
            )
        else:
            assert backlog["item_id"] == CONTROLLED_SUCCESSOR_NEXT
            assert current.name == "fin_ia_0_1_2_current_program_projection_v2_32.json"
            assert backlog["S3_T03_replacement_admission_authority_status"] == (
                "blocked_controlled_successor_missing"
            )
        assert backlog["current_projection_sha256"] == _sha256(current)
    assert backlog["S3_T03_bound_launcher_parent_supervisor_missing"] is False
    if backlog["item_id"] in {
        FAILURE_NEXT,
        LEAD_V8_PROOF_NEXT,
        REPLACEMENT_AUTHORITY_NEXT,
        CONTROLLED_SUCCESSOR_NEXT,
    }:
        assert backlog["S3_T03_fresh_admission_consumed"] is True
        assert backlog["S3_T03_execution_started"] is True
        assert (ROOT / target.runtime_root_ref).exists()
    else:
        assert backlog["S3_T03_fresh_admission_consumed"] is False
        assert backlog["S3_T03_execution_started"] is False
        assert not (ROOT / target.runtime_root_ref).exists()
    root_cause_rows = [
        json.loads(line)
        for line in (
            ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if "RC-P36-107" in line
    ]
    assert root_cause_rows[-1]["status"] == "closed"
    assert root_cause_rows[-1]["full_chain_blocker"] is False
