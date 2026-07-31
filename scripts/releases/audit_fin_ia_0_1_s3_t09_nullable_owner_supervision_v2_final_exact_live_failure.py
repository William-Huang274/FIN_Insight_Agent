from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3,
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
)
from apps.workbench.backend.application.case_service import CaseService
from scripts.releases.prepare_fin_ia_0_1_s3_t09_paired_deterministic_baseline_decision import (
    _sha256,
    _tree_digest,
)
from sec_agent.canonical_runtime.models import canonical_digest


RUNTIME_ROOT = (
    ROOT
    / ".codex_runtime"
    / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
)
SUPERVISION_ROOT = (
    ROOT
    / ".codex_runtime"
    / "fin01-s3-t09-nullable-owner-supervision-v2-final-exact-run-r1"
)
RUNTIME_RESULT = (
    RUNTIME_ROOT
    / "nullable_supervision_v2_final_r1_live_execution_result.json"
)
OUTPUT = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s3_t09_nullable_owner_and_supervision_v2_final_"
    "exact_live_execution_result_v1_0.json"
)
ADMISSION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s3_t09_three_cell_deepseek_nullable_owner_"
    "supervision_v2_final_exact_admission_r1.json"
)
IDENTITY = {
    "work_unit_id": "wu_p02_5_870d16faa31ee622a270a581",
    "attempt_id": "attempt_fin01_747d6459f09956ced4a50f2e",
    "research_run_id": "research_run_fin01_6594b12567cdebecd441d31d",
}
ADMISSION_ID = (
    "fin01-s3-t09-three-cell-deepseek-nullable-owner-supervision-v2-"
    "final-exact-admission-r1"
)
ADMISSION_DIGEST = (
    "854a29f299c1d86f1cb86d75f97b0f344f13f9275a04298120789e44d9734f31"
)
NEXT_ACTION = (
    "S3-T09-FINAL-EXACT-LIVE-RESEARCH-LEAD-HARD-NARRATIVE-"
    "NONCONFORMANCE-DISPOSITION-DECISION"
)


class FinalExactLiveFailureAuditError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise FinalExactLiveFailureAuditError(code)


def _digest_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_count = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65_536), b""):
            byte_count += len(block)
            digest.update(block)
    return digest.hexdigest(), byte_count


def _narrative_metrics(output: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(path: str, value: Any) -> None:
        length = len(value) if isinstance(value, str) else None
        rows.append(
            {
                "field_path": path,
                "unicode_characters": length,
                "over_hard_maximum_characters": (
                    max(0, length - 512) if length is not None else None
                ),
            }
        )

    for index, row in enumerate(output.get("cross_cell_dependencies") or []):
        add(
            f"cross_cell_dependencies[{index}].statement",
            row.get("statement") if isinstance(row, Mapping) else None,
        )
    for index, row in enumerate(output.get("conflict_adjudications") or []):
        for key in ("terminal_state_summary", "resolution_status", "statement"):
            add(
                f"conflict_adjudications[{index}].{key}",
                row.get(key) if isinstance(row, Mapping) else None,
            )
    variant = output.get("variant_view")
    add(
        "variant_view.statement",
        variant.get("statement") if isinstance(variant, Mapping) else None,
    )
    for index, row in enumerate(output.get("remaining_gaps") or []):
        add(
            f"remaining_gaps[{index}].statement",
            row.get("statement") if isinstance(row, Mapping) else None,
        )
    return rows


def audit(
    *,
    runtime_root: Path = RUNTIME_ROOT,
    supervision_root: Path = SUPERVISION_ROOT,
    runtime_result_path: Path = RUNTIME_RESULT,
) -> dict[str, Any]:
    runtime_root = runtime_root.resolve()
    supervision_root = supervision_root.resolve()
    runtime_result_path = runtime_result_path.resolve()
    canonical_root = runtime_root / "canonical-runtime"
    database_path = canonical_root / "canonical.sqlite"
    object_root = canonical_root / "objects"
    database_digest_before = _sha256(database_path)
    object_digest_before = _tree_digest(object_root)

    runtime_result = json.loads(runtime_result_path.read_text(encoding="utf-8"))
    _require(
        runtime_result.get("status")
        == "terminal_failed_admission_consumed_no_retry",
        "final_exact_runtime_result_not_terminal_failed",
    )
    identity = runtime_result.get("identity") or {}
    _require(
        identity.get("admission_id") == ADMISSION_ID
        and identity.get("admission_digest") == ADMISSION_DIGEST
        and all(identity.get(key) == value for key, value in IDENTITY.items()),
        "final_exact_runtime_identity_mismatch",
    )
    canonical = runtime_result.get("canonical_terminal_truth") or {}
    _require(
        [
            canonical.get("work_unit_state"),
            canonical.get("attempt_state"),
            canonical.get("research_run_state"),
        ]
        == ["failed", "failed", "failed"]
        and canonical.get("orphaned_run") is False
        and canonical.get("artifact_count") == 0,
        "final_exact_runtime_terminal_truth_mismatch",
    )

    provider = runtime_result.get("provider_execution") or {}
    observed = provider.get("observed_counts") or {}
    receipts = provider.get("usage_receipts") or []
    _require(
        observed
        == {
            "external_tool_calls": 0,
            "model_calls": 10,
            "network_calls": 10,
            "provider_calls": 10,
            "source_network_calls": 0,
        }
        and len(receipts) == 10
        and {str(row.get("status")) for row in receipts} == {"ok"}
        and {str(row.get("finish_reason")) for row in receipts} == {"stop"}
        and {int(row.get("transport_attempt_count") or 0) for row in receipts}
        == {1},
        "final_exact_provider_execution_summary_mismatch",
    )
    usage = {
        "input_tokens": sum(int(row["input_tokens"]) for row in receipts),
        "output_tokens": sum(int(row["output_tokens"]) for row in receipts),
        "total_tokens": sum(int(row["total_tokens"]) for row in receipts),
        "estimated_cost_usd": round(
            sum(float(row["estimated_cost_usd"]) for row in receipts), 8
        ),
        "transport_attempt_count": sum(
            int(row["transport_attempt_count"]) for row in receipts
        ),
    }
    _require(
        usage
        == {
            "input_tokens": 38_849,
            "output_tokens": 4_914,
            "total_tokens": 43_763,
            "estimated_cost_usd": 0.01797197,
            "transport_attempt_count": 10,
        },
        "final_exact_usage_summary_mismatch",
    )

    with tempfile.TemporaryDirectory(
        prefix="s3-t09-final-live-failure-audit-"
    ) as temp_dir:
        clone_canonical_root = Path(temp_dir) / "canonical-runtime"
        shutil.copytree(canonical_root, clone_canonical_root)
        service = CaseService.for_fixture_root(
            clone_canonical_root, repo_root=ROOT
        )
        facade = service._facade
        captures = facade.read_research_run_provider_output_captures(
            IDENTITY["research_run_id"]
        )
        events = facade.list_events(IDENTITY["research_run_id"])
    lead_rows = [
        row for row in captures if str(row.get("stage") or "") == "research_lead"
    ]
    _require(
        len(captures) == 10 and len(lead_rows) == 1,
        "final_exact_capture_cardinality_mismatch",
    )
    lead_capture = lead_rows[0]
    lead_text = str(lead_capture.get("assistant_output_text") or "")
    lead_output = json.loads(lead_text)
    expected_top_keys = {
        "cross_cell_dependencies",
        "conflict_adjudications",
        "variant_view",
        "remaining_gaps",
    }
    _require(
        isinstance(lead_output, Mapping)
        and set(lead_output) == expected_top_keys,
        "final_exact_lead_outer_shape_mismatch",
    )
    metrics = _narrative_metrics(lead_output)
    over_hard = [
        row
        for row in metrics
        if int(row.get("over_hard_maximum_characters") or 0) > 0
    ]
    aggregate_narrative_characters = sum(
        int(row["unicode_characters"])
        for row in metrics
        if row.get("unicode_characters") is not None
    )
    _require(
        [
            (row["field_path"], row["unicode_characters"], row["over_hard_maximum_characters"])
            for row in over_hard
        ]
        == [
            ("cross_cell_dependencies[0].statement", 571, 59),
            ("cross_cell_dependencies[1].statement", 533, 21),
            ("cross_cell_dependencies[2].statement", 528, 16),
        ]
        and aggregate_narrative_characters == 3_875
        and len(lead_text) == 5_195
        and len(lead_text.encode("utf-8")) == 5_195,
        "final_exact_lead_narrative_metrics_mismatch",
    )

    failure = runtime_result.get("failure_observation") or {}
    failure_telemetry = (
        (failure.get("failure_telemetry") or {}).get(
            "research_lead_contract"
        )
        or {}
    )
    _require(
        failure.get("stage") == "research_lead"
        and failure.get("failure_codes")
        == ["s3_bounded_research_lead_v3_text_item_over_max_unicode_characters"]
        and failure_telemetry.get("failure_family") == "text"
        and failure_telemetry.get("failure_subtype")
        == "item_over_max_unicode_characters"
        and failure_telemetry.get("field_id") == "cross_cell_dependencies"
        and failure_telemetry.get("failing_item_count") == 3,
        "final_exact_failure_telemetry_mismatch",
    )

    event_types = [str(row.get("event_type") or "") for row in events]
    failed_event = next(
        row for row in events if row.get("event_type") == "RESEARCH_RUN_FAILED"
    )
    capture_refs = (
        (failed_event.get("payload") or {}).get("provider_output_capture_refs")
        or []
    )
    _require(
        event_types
        == [
            "WORK_UNIT_STARTED",
            "ATTEMPT_STARTED",
            "SCHEDULER_LEASE_ACQUIRED",
            "RESEARCH_RUN_STARTED",
            "RESEARCH_RUN_FAILED",
            "ATTEMPT_FAILED",
            "WORK_UNIT_FAILED",
        ]
        and len(capture_refs) == 10,
        "final_exact_atomic_failure_event_contract_mismatch",
    )

    launch_path = supervision_root / "launch_receipt.json"
    command_path = supervision_root / "runner_command.json"
    exit_path = supervision_root / "exit_receipt.json"
    stdout_path = supervision_root / "runner.stdout.log"
    stderr_path = supervision_root / "runner.stderr.log"
    launch = json.loads(launch_path.read_text(encoding="utf-8"))
    command = json.loads(command_path.read_text(encoding="utf-8"))
    exit_receipt = json.loads(exit_path.read_text(encoding="utf-8"))
    stdout_digest, stdout_bytes = _digest_file(stdout_path)
    stderr_digest, stderr_bytes = _digest_file(stderr_path)
    _require(
        launch.get("contract_ref") == "fin01.s3.exact_run_supervision:v2"
        and launch.get("process_topology")
        == "direct_actual_runner_no_intermediate_wrapper"
        and launch.get("runner_pid") == exit_receipt.get("runner_pid")
        and launch.get("runner_process_identity")
        == exit_receipt.get("runner_process_identity")
        and exit_receipt.get("status") == "actual_runner_self_finalized"
        and exit_receipt.get("exit_code") == 0
        and exit_receipt.get("typed_unhandled_failure_code") is None
        and exit_receipt.get("stdout_sha256") == stdout_digest
        and exit_receipt.get("stdout_bytes") == stdout_bytes
        and exit_receipt.get("stderr_sha256") == stderr_digest
        and exit_receipt.get("stderr_bytes") == stderr_bytes
        and launch.get("parent_enforced_timeout_seconds") is None
        and launch.get("parent_may_terminate_child") is False
        and launch.get("monitoring_contract")
        == "read_only_no_signal_no_retry_no_relaunch"
        and all(
            int(row.get(key) or 0) == 0
            for row in (launch, command, exit_receipt)
            for key in (
                "automatic_retry_count",
                "fallback_count",
                "replay_count",
                "relaunch_count",
            )
        ),
        "final_exact_supervision_v2_receipt_mismatch",
    )

    profile = S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3
    historical_admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        json.loads(ADMISSION.read_text(encoding="utf-8"))
    )
    _require(
        historical_admission.research_profile_ref
        == S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3_REF
        and canonical_digest(historical_admission.digest_payload())
        == ADMISSION_DIGEST
        and profile.research_lead_narrative_target_characters == 320
        and profile.research_lead_narrative_hard_max_characters == 512
        and profile.research_lead_aggregate_narrative_max_characters == 3_200
        and historical_admission.output_contract_ref
        == "fin01.s3.bounded_agent_three_cell_output:v4",
        "final_exact_provider_visible_narrative_contract_mismatch",
    )

    boundaries = runtime_result.get("boundary_observation") or {}
    _require(
        boundaries.get("source_network_calls") == 0
        and boundaries.get("external_tool_calls") == 0
        and boundaries.get("live_business_case_head_writes") == 0
        and boundaries.get("raw_provider_response_persisted") is False
        and boundaries.get("private_chain_of_thought_persisted") is False
        and boundaries.get("credential_value_persisted") is False,
        "final_exact_boundary_observation_mismatch",
    )

    database_digest_after = _sha256(database_path)
    object_digest_after = _tree_digest(object_root)
    _require(
        database_digest_after == database_digest_before
        and object_digest_after == object_digest_before,
        "final_exact_safe_audit_changed_runtime",
    )
    return {
        "schema_version": (
            "fin_ia_0_1_s3_t09_nullable_owner_and_supervision_v2_final_"
            "exact_live_execution_result_v1_0"
        ),
        "status": (
            "terminal_failed_research_lead_profile_v3_hard_narrative_"
            "nonconformance_admission_consumed_no_retry_or_relaunch"
        ),
        "authority": {
            "user_instruction": (
                "继续，依次进入新 admission、最终 exact-live 和 T09 整体验收。"
            ),
            "one_final_exact_live_execution_authorized": True,
            "automatic_retry_fallback_patch_replay_relaunch_or_rerun_authorized": False,
            "acceptance_only_after_terminal_success_and_nine_artifacts": True,
        },
        "source_refs": {
            "proof": (
                "configs/releases/fin_ia_0_1_s3_t09_nullable_owner_and_"
                "supervision_v2_final_fresh_agent_proof_decision_v1_0.json"
            ),
            "issuance": (
                "configs/releases/fin_ia_0_1_s3_t09_nullable_owner_and_"
                "supervision_v2_final_fresh_exact_admission_issuance_v1_0.json"
            ),
            "admission": (
                "configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_"
                "nullable_owner_supervision_v2_final_exact_admission_r1.json"
            ),
            "runtime_result": runtime_result_path.relative_to(ROOT).as_posix(),
            "supervision_root": supervision_root.relative_to(ROOT).as_posix(),
        },
        "identity": {
            **IDENTITY,
            "admission_id": ADMISSION_ID,
            "admission_digest": ADMISSION_DIGEST,
            "admission_consumed": True,
        },
        "preflight": {
            "project_os_scoped_preflight": "pass",
            "exact_runner_preflight": "pass_exact_zero_call_execution_preflight",
            "transport_retries": 0,
            "target_counts_before": [21, 21, 21, 13],
        },
        "provider_execution": {
            "provider": provider.get("provider"),
            "model": provider.get("model"),
            "observed_counts": observed,
            "usage": usage,
            "specialist_segments_completed": 9,
            "research_lead_called": True,
            "memo_writer_called": False,
            "verifier_called": False,
            "all_status_ok": True,
            "all_finish_reason_stop": True,
            "retry_count": 0,
            "fallback_count": 0,
            "rerun_count": 0,
        },
        "restricted_capture_audit": {
            "capture_count": len(captures),
            "restricted_readback_count": len(captures),
            "research_lead_capture_count": len(lead_rows),
            "research_lead_capture_object_digest": str(
                lead_capture.get("object_digest") or ""
            )
            or "4a2fb6e447afaca0ca91309a975665ef6061a65a3df5f1727f3880e447c65ab0",
            "assistant_output_unicode_characters": len(lead_text),
            "assistant_output_utf8_bytes": len(lead_text.encode("utf-8")),
            "raw_assistant_output_persisted_in_result": False,
            "private_reasoning_persisted_in_result": False,
        },
        "research_lead_safe_structure": {
            "native_json_object": True,
            "top_level_keys": sorted(map(str, lead_output)),
            "field_cardinalities": {
                "cross_cell_dependencies": len(
                    lead_output["cross_cell_dependencies"]
                ),
                "conflict_adjudications": len(
                    lead_output["conflict_adjudications"]
                ),
                "variant_view": 1,
                "remaining_gaps": len(lead_output["remaining_gaps"]),
            },
            "quality_target_unicode_characters": 320,
            "hard_maximum_unicode_characters": 512,
            "aggregate_maximum_unicode_characters": 3_200,
            "aggregate_observed_unicode_characters": aggregate_narrative_characters,
            "aggregate_over_by": aggregate_narrative_characters - 3_200,
            "hard_failing_item_count": len(over_hard),
            "hard_failing_items": over_hard,
            "provider_output_text_copied_to_result": False,
        },
        "canonical_terminal_truth": {
            "work_unit_state": "failed",
            "attempt_state": "failed",
            "research_run_state": "failed",
            "terminal_reason": canonical.get("terminal_reason"),
            "orphaned_run": False,
            "artifact_count": 0,
            "event_types": event_types,
            "terminal_failure_event_capture_ref_count": len(capture_refs),
            "target_counts_after": [22, 22, 22, 13],
            "canonical_database_sha256": database_digest_after,
            "canonical_object_tree_sha256": object_digest_after,
        },
        "supervision_observation": {
            "contract_ref": launch["contract_ref"],
            "process_topology": launch["process_topology"],
            "launch_receipt_present": True,
            "runner_command_receipt_present": True,
            "exit_receipt_present": True,
            "runner_pid": int(launch["runner_pid"]),
            "runner_process_identity": launch["runner_process_identity"],
            "launch_and_exit_identity_match": True,
            "runner_self_finalized": True,
            "runner_exit_code": int(exit_receipt["exit_code"]),
            "stdout_sha256": stdout_digest,
            "stdout_bytes": stdout_bytes,
            "stderr_sha256": stderr_digest,
            "stderr_bytes": stderr_bytes,
            "monitor_signals_sent": 0,
            "automatic_retry_count": 0,
            "fallback_count": 0,
            "replay_count": 0,
            "relaunch_count": 0,
        },
        "root_cause_classification": {
            "first_credible_failure_stage": "research_lead",
            "direct_failure": (
                "three cross_cell_dependency statements exceeded the explicit "
                "512-character hard maximum; aggregate narrative also exceeded "
                "the explicit 3200-character maximum"
            ),
            "provider_returned_valid_json": True,
            "provider_finish_reason_stop": True,
            "provider_visible_hard_and_aggregate_limits_present": True,
            "local_validator_matches_profile": True,
            "project_request_validator_schema_drift_observed": False,
            "direct_model_output_contract_nonconformance": True,
            "supervision_model_related": False,
            "root_cause_id": (
                "RC-P36-047-s3-research-lead-v5-per-field-"
                "narrative-length-contract-gap"
            ),
            "disposition_selected_or_repair_authorized": False,
        },
        "acceptance": {
            "RC_P38_053_supervision_v2_fresh_live_proven": True,
            "RC_P36_052_nullable_owner_v2_live_reached": False,
            "nine_artifact_product_complete": False,
            "paired_comparison_performed": False,
            "owner_acceptance_performed": False,
            "S3_T09": "blocked",
            "T09_overall_acceptance_started": False,
        },
        "observed_counts": {
            "admission_consumptions": 1,
            "supervisor_launches": 1,
            "live_executions": 1,
            "model_calls": 10,
            "provider_calls": 10,
            "network_calls": 10,
            "source_network_calls": 0,
            "external_tool_calls": 0,
            "new_work_units": 1,
            "new_attempts": 1,
            "new_research_runs": 1,
            "new_business_artifacts": 0,
            "automatic_retries": 0,
            "fallbacks": 0,
            "patches": 0,
            "capture_replays": 0,
            "relaunches": 0,
            "reruns": 0,
            "paired_comparisons": 0,
            "owner_acceptance_writes": 0,
        },
        "next_action": NEXT_ACTION,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=RUNTIME_ROOT)
    parser.add_argument(
        "--supervision-root", type=Path, default=SUPERVISION_ROOT
    )
    parser.add_argument("--runtime-result", type=Path, default=RUNTIME_RESULT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = audit(
        runtime_root=args.runtime_root,
        supervision_root=args.supervision_root,
        runtime_result_path=args.runtime_result,
    )
    output = args.output.resolve()
    if output.exists():
        raise FinalExactLiveFailureAuditError(
            "final_exact_live_audit_output_already_exists"
        )
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
