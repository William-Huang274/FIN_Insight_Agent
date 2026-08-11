from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.case_service import CaseService
from sec_agent.canonical_runtime.models import (
    CommandEnvelope,
    canonical_digest,
    utc_now,
)


RUNTIME_ROOT = (
    ROOT
    / ".codex_runtime"
    / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
)
SUPERVISION_ROOT = (
    ROOT
    / ".codex_runtime"
    / "fin01-s4-t05-dell-r11-numeric-identity-supervision-r1"
)
EXACT_IDENTITY = {
    "work_unit_id": "wu_p02_5_91b6655f9bf7d565f8aeaf38",
    "attempt_id": "attempt_fin01_ea1feababa4b33997ca096df",
    "research_run_id": "research_run_fin01_bee8a3fa962af0bafdc73fc1",
}
EXPECTED_EXIT_RECEIPT_SHA256 = (
    "b1092113ae479d66014be508de9937be585f6d3753990fa970e188b57ee2347e"
)
EXPECTED_RECORDED_STDERR_SHA256 = (
    "23f36665a545052147d887aed4167a78ce210c4a9203c8d154a6a3cd2c06fd81"
)
EXPECTED_EXECUTOR_SHA256 = (
    "bb5196ac7ef9f7b9a618803063ff1ba8b4dae564623a02fc8cc06b26f560fe57"
)
TERMINAL_REASON = (
    "bounded_agent_profile_error:BoundedAgentExecutionError:"
    "specialist_numeric_narrative_l1:"
    "failure_observation_allowlist_orphan"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_supervised_failure(supervision_root: Path) -> dict[str, object]:
    exit_receipt_path = supervision_root.resolve() / "exit_receipt.json"
    stderr_path = supervision_root.resolve() / "runner.stderr.log"
    if _sha256(exit_receipt_path) != EXPECTED_EXIT_RECEIPT_SHA256:
        raise RuntimeError("s4_t05_r11_exit_receipt_digest_mismatch")
    receipt = json.loads(exit_receipt_path.read_text(encoding="utf-8"))
    required = {
        "status": "actual_runner_self_finalized",
        "exit_code": 1,
        "typed_unhandled_failure_code": "unhandled_ArtifactValidationError",
        "runtime_result_ref": None,
        "stderr_sha256": EXPECTED_RECORDED_STDERR_SHA256,
        "automatic_retry_count": 0,
        "fallback_count": 0,
        "replay_count": 0,
        "relaunch_count": 0,
        "raw_provider_body_in_receipt": False,
        "credential_value_in_receipt": False,
    }
    for key, expected in required.items():
        if receipt.get(key) != expected:
            raise RuntimeError(f"s4_t05_r11_exit_receipt_{key}_mismatch")
    stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
    required_stderr_markers = (
        'bounded_agent_executor.py", line 8064, in _call_json_object',
        "BoundedAgentExecutionError: bounded_agent_execution_failed",
        "research_run_failure_observation_not_secret_safe",
    )
    if any(marker not in stderr for marker in required_stderr_markers):
        raise RuntimeError("s4_t05_r11_stderr_failure_chain_incomplete")
    executor_path = (
        ROOT
        / "apps"
        / "workbench"
        / "backend"
        / "application"
        / "bounded_agent_executor.py"
    )
    if _sha256(executor_path) != EXPECTED_EXECUTOR_SHA256:
        raise RuntimeError("s4_t05_r11_executor_digest_mismatch")
    executor_lines = executor_path.read_text(encoding="utf-8").splitlines()
    if (
        executor_lines[8063].strip() != "self._stop("
        or "s4_case_numeric_authority_provider_narrative_invalid"
        not in executor_lines[8066]
    ):
        raise RuntimeError("s4_t05_r11_executor_failure_site_mismatch")
    return receipt


def close(runtime_root: Path, supervision_root: Path) -> dict[str, object]:
    receipt = _require_supervised_failure(supervision_root)
    service = CaseService.for_fixture_root(
        runtime_root.resolve() / "canonical-runtime", repo_root=ROOT
    )
    facade = service._facade
    work_unit = facade.store.get_latest(
        "canonical_work_units", EXACT_IDENTITY["work_unit_id"]
    )
    attempt = facade.store.get_latest(
        "canonical_attempts", EXACT_IDENTITY["attempt_id"]
    )
    run = facade.store.get_latest(
        "canonical_research_run_versions", EXACT_IDENTITY["research_run_id"]
    )
    if not all((work_unit, attempt, run)):
        raise RuntimeError("s4_t05_r11_orphan_closeout_exact_identity_missing")
    if {
        "work_unit_id": work_unit.get("work_unit_id"),
        "attempt_id": attempt.get("attempt_id"),
        "research_run_id": run.get("research_run_id"),
    } != EXACT_IDENTITY:
        raise RuntimeError("s4_t05_r11_orphan_closeout_exact_identity_mismatch")
    artifacts = [
        row
        for row in facade.store.list_latest("canonical_artifact_versions")
        if row.get("producer_attempt_id") == EXACT_IDENTITY["attempt_id"]
    ]
    if artifacts:
        raise RuntimeError("s4_t05_r11_orphan_closeout_requires_zero_artifacts")
    states = (work_unit.get("state"), attempt.get("state"), run.get("state"))
    if states == ("failed", "failed", "failed"):
        if run.get("terminal_reason") != TERMINAL_REASON:
            raise RuntimeError("s4_t05_r11_orphan_closeout_terminal_truth_conflict")
    elif states == ("running", "running", "running"):
        events = facade.list_events(EXACT_IDENTITY["research_run_id"])
        if any(
            row.get("event_type")
            in {"RESEARCH_RUN_COMPLETED", "RESEARCH_RUN_FAILED"}
            for row in events
        ):
            raise RuntimeError("s4_t05_r11_orphan_closeout_terminal_event_conflict")
        start_event = next(
            (
                row
                for row in events
                if row.get("event_type") == "RESEARCH_RUN_STARTED"
            ),
            None,
        )
        if start_event is None:
            raise RuntimeError("s4_t05_r11_orphan_closeout_start_event_required")
        command = CommandEnvelope(
            command_id=(
                "fin01_s4_t05_dell_r11_numeric_identity_orphan_closeout_"
                + canonical_digest(EXACT_IDENTITY)[:24]
            ),
            command_type="FAIL_RESEARCH_RUN",
            tenant_id=str(work_unit["tenant_id"]),
            project_id=str(work_unit["project_id"]),
            case_id=str(work_unit["case_id"]),
            actor_snapshot_ref=str(work_unit["actor_snapshot_ref"]),
            permission_snapshot_ref=str(work_unit["permission_snapshot_ref"]),
            policy_config_refs=tuple(attempt.get("policy_config_refs") or ()),
            idempotency_key=(
                str(work_unit["idempotency_key"])
                + ":typed-orphan-closeout:r11:v1"
            ),
            expected_state_version=1,
            causation_event_id=str(start_event["event_id"]),
            correlation_id=str(work_unit["correlation_id"]),
            requested_at=utc_now(),
            payload={
                **EXACT_IDENTITY,
                "input_head_digest": str(attempt["input_head_digest"]),
                "lease_owner_ref": str(attempt["lease_owner_ref"]),
                "lease_fencing_token": int(attempt["lease_fencing_token"]),
                "failure_type": "bounded_agent_profile_execution_failed",
                "terminal_reason": TERMINAL_REASON,
                "failure_observation": {
                    "stage": (
                        "specialist_numeric_narrative_validation:"
                        "canonical_failure_terminalization"
                    ),
                    "failure_codes": [
                        "bounded_agent_s4_case_numeric_authority_provider_narrative_invalid",
                        "bounded_agent_failure_observation_allowlist_orphan",
                    ],
                    "observed_counts": {
                        "model_calls": 1,
                        "provider_calls": 1,
                        "network_calls": 1,
                        "source_network_calls": 0,
                        "external_tool_calls": 0,
                    },
                    "estimated_cost_usd": 0.0,
                    "usage_receipts": [],
                    "private_reasoning_persisted": False,
                    "raw_provider_response_persisted": False,
                },
            },
        )
        facade.fail_research_run(command)
    else:
        raise RuntimeError("s4_t05_r11_orphan_closeout_requires_exact_running_or_failed")

    closed = {
        "work_unit_state": facade.store.get_latest(
            "canonical_work_units", EXACT_IDENTITY["work_unit_id"]
        )["state"],
        "attempt_state": facade.store.get_latest(
            "canonical_attempts", EXACT_IDENTITY["attempt_id"]
        )["state"],
        "research_run_state": facade.store.get_latest(
            "canonical_research_run_versions",
            EXACT_IDENTITY["research_run_id"],
        )["state"],
    }
    if set(closed.values()) != {"failed"}:
        raise RuntimeError("s4_t05_r11_orphan_closeout_postcondition_failed")
    return {
        "status": "typed_orphan_closeout_succeeded_zero_call",
        "identity": EXACT_IDENTITY,
        "terminal_reason": TERMINAL_REASON,
        "canonical_terminal_truth": closed,
        "artifact_count": 0,
        "closeout_model_provider_network_calls": [0, 0, 0],
        "failed_run_observed_model_provider_network_calls": [1, 1, 1],
        "failed_run_call_count_basis": (
            "first_specialist_provider_return_reached_numeric_narrative_validation;"
            "supervisor_records_zero_retry_fallback_replay_relaunch"
        ),
        "provider_output_capture_recoverable": False,
        "usage_receipts_reconstructed": False,
        "estimated_cost_usd_persisted": 0.0,
        "supervisor_exit_code": receipt["exit_code"],
        "supervisor_typed_unhandled_failure_code": receipt[
            "typed_unhandled_failure_code"
        ],
        "r12_authorized_or_launched": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=RUNTIME_ROOT)
    parser.add_argument("--supervision-root", type=Path, default=SUPERVISION_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(
        close(args.runtime_root, args.supervision_root),
        ensure_ascii=False,
        indent=2,
    )
    if args.output is not None:
        args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
        args.output.resolve().write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
