from __future__ import annotations

import argparse
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
EXACT_IDENTITY = {
    "work_unit_id": "wu_p02_5_faa27f97931244939f6daf3f",
    "attempt_id": "attempt_fin01_1de0ba5e8037f6d2953d1733",
    "research_run_id": "research_run_fin01_e418d7086d4a1d253e9b2c9b",
}
TERMINAL_REASON = (
    "bounded_agent_profile_error:BoundedAgentExecutionError:"
    "memo_writer:canonical_terminalization_interrupted"
)


def close(runtime_root: Path) -> dict[str, object]:
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
        raise RuntimeError("s3_t09_orphan_closeout_exact_identity_missing")
    if {
        "work_unit_id": work_unit.get("work_unit_id"),
        "attempt_id": attempt.get("attempt_id"),
        "research_run_id": run.get("research_run_id"),
    } != EXACT_IDENTITY:
        raise RuntimeError("s3_t09_orphan_closeout_exact_identity_mismatch")
    artifacts = [
        row
        for row in facade.store.list_latest("canonical_artifact_versions")
        if row.get("producer_attempt_id") == EXACT_IDENTITY["attempt_id"]
    ]
    if artifacts:
        raise RuntimeError("s3_t09_orphan_closeout_requires_zero_artifacts")
    states = (work_unit.get("state"), attempt.get("state"), run.get("state"))
    if states == ("failed", "failed", "failed"):
        if run.get("terminal_reason") != TERMINAL_REASON:
            raise RuntimeError("s3_t09_orphan_closeout_terminal_truth_conflict")
    elif states == ("running", "running", "running"):
        events = facade.list_events(EXACT_IDENTITY["research_run_id"])
        if any(
            row.get("event_type")
            in {"RESEARCH_RUN_COMPLETED", "RESEARCH_RUN_FAILED"}
            for row in events
        ):
            raise RuntimeError("s3_t09_orphan_closeout_terminal_event_conflict")
        start_event = next(
            (
                row
                for row in events
                if row.get("event_type") == "RESEARCH_RUN_STARTED"
            ),
            None,
        )
        if start_event is None:
            raise RuntimeError("s3_t09_orphan_closeout_start_event_required")
        command = CommandEnvelope(
            command_id=(
                "fin01_s3_t09_research_lead_v3_orphan_closeout_"
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
                + ":typed-orphan-closeout:v1"
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
                "failure_type": "bounded_agent_profile_execution_interrupted",
                "terminal_reason": TERMINAL_REASON,
                "failure_observation": {
                    "stage": (
                        "bounded_runtime_terminalization:"
                        "orphaned_after_memo_writer_validation"
                    ),
                    "failure_codes": [
                        "s3_bounded_canonical_terminalization_interrupted"
                    ],
                    "observed_counts": {
                        "model_calls": 11,
                        "provider_calls": 11,
                        "network_calls": 11,
                        "source_network_calls": 0,
                        "external_tool_calls": 0,
                    },
                    "estimated_cost_usd": 0.02554755,
                    "usage_receipts": [],
                    "private_reasoning_persisted": False,
                    "raw_provider_response_persisted": False,
                },
            },
        )
        facade.fail_research_run(command)
    else:
        raise RuntimeError("s3_t09_orphan_closeout_requires_exact_running_or_failed")

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
        raise RuntimeError("s3_t09_orphan_closeout_postcondition_failed")
    return {
        "status": "typed_orphan_closeout_succeeded_zero_call",
        "identity": EXACT_IDENTITY,
        "terminal_reason": TERMINAL_REASON,
        "canonical_terminal_truth": closed,
        "artifact_count": 0,
        "model_provider_network_calls": [0, 0, 0],
        "historical_provider_output_capture_recoverable": False,
        "historical_usage_receipts_reconstructed": False,
        "estimated_cost_usd_basis": "conservative_reconstructable_upper_bound",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=RUNTIME_ROOT)
    args = parser.parse_args()
    print(json.dumps(close(args.runtime_root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
