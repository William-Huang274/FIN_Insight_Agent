from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.case_service import CaseService
from sec_agent.canonical_runtime.models import CommandEnvelope, canonical_digest, utc_now


RUNTIME_ROOT = (
    ROOT
    / ".codex_runtime"
    / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
)
EXACT_IDENTITY = {
    "work_unit_id": "wu_p02_5_2bbd547a60d876d3c676aafc",
    "attempt_id": "attempt_fin01_29a1eb04e4ea04e0c574ee76",
    "research_run_id": "research_run_fin01_f136c2d298568856bde6512e",
}
ADMISSION_ID = (
    "fin01-s3-t09-three-cell-deepseek-output-v4-verifier-schema-repair-"
    "exact-admission-r1"
)
EXPECTED_CAPTURE_STAGES = (
    "domain_specialist:demand_authenticity_and_sustainability:"
    "facts_explanation_and_terminal",
    "domain_specialist:demand_authenticity_and_sustainability:"
    "owner_grade_claim_cards",
    "domain_specialist:demand_authenticity_and_sustainability:"
    "actionable_what_would_change_tasks",
    "domain_specialist:value_and_profit_capture:facts_explanation_and_terminal",
    "domain_specialist:value_and_profit_capture:owner_grade_claim_cards",
    "domain_specialist:value_and_profit_capture:actionable_what_would_change_tasks",
    "domain_specialist:bottleneck_counterevidence_and_what_would_change:"
    "facts_explanation_and_terminal",
    "domain_specialist:bottleneck_counterevidence_and_what_would_change:"
    "owner_grade_claim_cards",
    "domain_specialist:bottleneck_counterevidence_and_what_would_change:"
    "actionable_what_would_change_tasks",
    "research_lead",
    "memo_writer",
    "verifier",
)
TERMINAL_REASON = (
    "bounded_agent_profile_error:BoundedAgentExecutionError:"
    "bounded_runtime_terminalization:"
    "orphaned_after_verifier_capture_before_artifact_persistence"
)
FAILURE_STAGE = (
    "bounded_runtime_terminalization:"
    "orphaned_after_verifier_capture_before_artifact_persistence"
)
FAILURE_CODE = "s3_bounded_execution_controller_timeout_orphan"
EXPECTED_TOKEN_TOTALS = {
    "input_tokens": 55186,
    "output_tokens": 6422,
    "total_tokens": 61608,
}
ESTIMATED_COST_USD_RANGE = {
    "lower_bound": 0.00578719,
    "upper_bound": 0.02959305,
    "basis": "gateway_event_tokens_cache_split_unavailable",
}


def _gateway_completion_summary(runtime_root: Path) -> dict[str, Any]:
    rows = []
    for line in (runtime_root / "gateway_events.jsonl").read_text(
        encoding="utf-8"
    ).splitlines():
        row = json.loads(line)
        trace = row.get("trace_tags")
        if (
            row.get("event_type") == "model_call_finished"
            and isinstance(trace, Mapping)
            and trace.get("research_run_id") == EXACT_IDENTITY["research_run_id"]
        ):
            rows.append(row)
    stages = tuple(str(row.get("role") or "") for row in rows)
    token_totals = {
        "input_tokens": sum(int(row.get("input_tokens") or 0) for row in rows),
        "output_tokens": sum(int(row.get("output_tokens") or 0) for row in rows),
        "total_tokens": sum(int(row.get("total_tokens") or 0) for row in rows),
    }
    if (
        len(rows) != 12
        or stages != EXPECTED_CAPTURE_STAGES
        or token_totals != EXPECTED_TOKEN_TOTALS
        or any(row.get("status") != "ok" for row in rows)
        or any(row.get("finish_reason") != "stop" for row in rows)
        or any(int(row.get("transport_attempt_count") or 0) != 1 for row in rows)
        or any(row.get("transport_failures") for row in rows)
    ):
        raise RuntimeError("s3_t09_orphan_gateway_completion_truth_mismatch")
    return {
        "model_calls": len(rows),
        "provider_calls": len(rows),
        "network_calls": len(rows),
        "transport_attempts": sum(
            int(row.get("transport_attempt_count") or 0) for row in rows
        ),
        "transport_failures": 0,
        "finish_reasons": sorted({str(row.get("finish_reason")) for row in rows}),
        "stages": list(stages),
        **token_totals,
    }


def close(runtime_root: Path) -> dict[str, object]:
    runtime_root = runtime_root.resolve()
    gateway_summary = _gateway_completion_summary(runtime_root)
    service = CaseService.for_fixture_root(
        runtime_root / "canonical-runtime", repo_root=ROOT
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
    events = facade.list_events(EXACT_IDENTITY["research_run_id"])
    capture_events = [
        row
        for row in events
        if row.get("event_type") == "RESEARCH_RUN_PROVIDER_OUTPUT_CAPTURED"
    ]
    if len(capture_events) != 1:
        raise RuntimeError("s3_t09_orphan_closeout_capture_event_cardinality_invalid")
    capture_payload = capture_events[0].get("payload") or {}
    capture_refs = capture_payload.get("provider_output_capture_refs") or []
    if (
        len(capture_refs) != 12
        or tuple(str(row.get("stage") or "") for row in capture_refs)
        != EXPECTED_CAPTURE_STAGES
        or any(not row.get("assistant_output_present") for row in capture_refs)
    ):
        raise RuntimeError("s3_t09_orphan_closeout_capture_truth_mismatch")
    capture_readback = facade.read_research_run_provider_output_captures(
        EXACT_IDENTITY["research_run_id"]
    )
    if len(capture_readback) != 12:
        raise RuntimeError("s3_t09_orphan_closeout_capture_readback_mismatch")

    states = (work_unit.get("state"), attempt.get("state"), run.get("state"))
    if states == ("failed", "failed", "failed"):
        if run.get("terminal_reason") != TERMINAL_REASON:
            raise RuntimeError("s3_t09_orphan_closeout_terminal_truth_conflict")
    elif states == ("running", "running", "running"):
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
                "fin01_s3_t09_output_v4_verifier_schema_repair_orphan_closeout_"
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
                + ":output-v4-verifier-schema-repair-orphan-closeout:v1"
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
                "failure_type": "bounded_agent_execution_controller_interrupted",
                "terminal_reason": TERMINAL_REASON,
                "failure_observation": {
                    "stage": FAILURE_STAGE,
                    "failure_codes": [FAILURE_CODE],
                    "observed_counts": {
                        "model_calls": 12,
                        "provider_calls": 12,
                        "network_calls": 12,
                        "source_network_calls": 0,
                        "external_tool_calls": 0,
                    },
                    "estimated_cost_usd": ESTIMATED_COST_USD_RANGE["upper_bound"],
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
    terminal_events = [
        row
        for row in facade.list_events(EXACT_IDENTITY["research_run_id"])
        if row.get("event_type")
        in {"RESEARCH_RUN_COMPLETED", "RESEARCH_RUN_FAILED"}
    ]
    if (
        len(terminal_events) != 1
        or terminal_events[0].get("event_type") != "RESEARCH_RUN_FAILED"
    ):
        raise RuntimeError("s3_t09_orphan_closeout_terminal_event_postcondition_failed")
    return {
        "schema_version": (
            "fin_ia_0_1_s3_t09_output_v4_verifier_schema_repair_"
            "orphan_typed_closeout_result_v1_0"
        ),
        "status": "typed_orphan_closeout_succeeded_zero_call",
        "admission_id": ADMISSION_ID,
        "identity": EXACT_IDENTITY,
        "terminal_reason": TERMINAL_REASON,
        "failure_stage": FAILURE_STAGE,
        "failure_code": FAILURE_CODE,
        "canonical_terminal_truth": {
            **closed,
            "artifact_count": 0,
            "orphaned_run": False,
        },
        "completed_provider_execution": gateway_summary,
        "provider_output_capture": {
            "capture_count": len(capture_refs),
            "restricted_readback_count": len(capture_readback),
            "assistant_output_present_count": sum(
                bool(row.get("assistant_output_present")) for row in capture_refs
            ),
            "stages": [str(row.get("stage") or "") for row in capture_refs],
            "recoverable_for_audit_only": True,
            "replayed_or_promoted_to_business_artifacts": False,
        },
        "estimated_cost_usd_range": ESTIMATED_COST_USD_RANGE,
        "exact_usage_receipts_available": False,
        "closeout_model_provider_network_calls": [0, 0, 0],
        "retry_count": 0,
        "fallback_count": 0,
        "rerun_count": 0,
        "t09_acceptance_eligible": False,
        "t09_acceptance_blocker": "zero_canonical_business_artifacts",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=RUNTIME_ROOT)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    result = close(args.runtime_root)
    if args.output is not None:
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
