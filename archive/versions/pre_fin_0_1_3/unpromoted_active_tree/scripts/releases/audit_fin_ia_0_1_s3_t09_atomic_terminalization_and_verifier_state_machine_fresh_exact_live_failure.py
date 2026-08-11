from __future__ import annotations

import argparse
import hashlib
import inspect
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    DeepSeekS3ThreeCellNodeExecutor,
    S3_FOUR_LAYER_VERIFIER_LAYERS,
    S3_OWNER_GRADE_VERIFIER_STATE_MACHINE_REF,
    S3ThreeCellBoundedAgentExecutor,
)
from apps.workbench.backend.application.case_service import CaseService
from scripts.releases.prepare_fin_ia_0_1_s3_t09_paired_deterministic_baseline_decision import (
    _sha256,
    _tree_digest,
)


RUNTIME_ROOT = (
    ROOT
    / ".codex_runtime"
    / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
)
SUPERVISION_ROOT = (
    ROOT
    / ".codex_runtime"
    / "supervision"
    / "fin01-s3-t09-atomic-state-machine-supervised-r1"
)
RUNTIME_RESULT = (
    RUNTIME_ROOT
    / "atomic_state_machine_supervised_r1_live_execution_result.json"
)
OUTPUT = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s3_t09_atomic_terminalization_and_typed_"
    "verifier_state_machine_fresh_exact_live_execution_result_v1_0.json"
)
IDENTITY = {
    "work_unit_id": "wu_p02_5_1e93d822b376782fb7648693",
    "attempt_id": "attempt_fin01_d39d0f35211169de635d6643",
    "research_run_id": "research_run_fin01_1e49c5f66f867ce2ba5ab9e0",
}
ADMISSION_DIGEST = (
    "2b87b9360ed53ec060670446125065497f2625f9384839cb65c4482ea8c381e1"
)
TYPED_FINDING_KEYS = {
    "layer",
    "status",
    "issue_codes",
    "artifact_or_claim_refs",
    "repair_owner",
}
NEXT_ACTION = (
    "S3-T09-VERIFIER-REPAIR-OWNER-SENTINEL-AND-WINDOWS-SUPERVISOR-"
    "EXIT-RECEIPT-LOSS-ZERO-CALL-ROOT-CAUSE-DISPOSITION"
)
STATUS = (
    "terminal_failed_verifier_repair_owner_null_vs_string_sentinel_"
    "and_supervisor_exit_receipt_loss_no_retry_relaunch_or_rerun"
)


class FreshExactLiveFailureAuditError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise FreshExactLiveFailureAuditError(code)


def _digest_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_count = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65_536), b""):
            byte_count += len(block)
            digest.update(block)
    return digest.hexdigest(), byte_count


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
        "fresh_exact_runtime_result_not_terminal_failed",
    )
    _require(
        runtime_result.get("identity", {}).get("admission_digest")
        == ADMISSION_DIGEST,
        "fresh_exact_runtime_admission_digest_mismatch",
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
        "fresh_exact_runtime_terminal_truth_mismatch",
    )

    provider = runtime_result.get("provider_execution") or {}
    observed = provider.get("observed_counts") or {}
    receipts = provider.get("usage_receipts") or []
    _require(
        observed
        == {
            "external_tool_calls": 0,
            "model_calls": 12,
            "network_calls": 12,
            "provider_calls": 12,
            "source_network_calls": 0,
        }
        and len(receipts) == 12
        and {str(row.get("status")) for row in receipts} == {"ok"}
        and {str(row.get("finish_reason")) for row in receipts} == {"stop"}
        and {int(row.get("transport_attempt_count") or 0) for row in receipts}
        == {1},
        "fresh_exact_provider_execution_summary_mismatch",
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
            "input_tokens": 53_346,
            "output_tokens": 5_527,
            "total_tokens": 58_873,
            "estimated_cost_usd": 0.02481146,
            "transport_attempt_count": 12,
        },
        "fresh_exact_usage_summary_mismatch",
    )

    with tempfile.TemporaryDirectory(
        prefix="s3-t09-live-failure-audit-"
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
    verifier_rows = [row for row in captures if row.get("stage") == "verifier"]
    _require(
        len(captures) == 12 and len(verifier_rows) == 1,
        "fresh_exact_capture_cardinality_mismatch",
    )
    verifier = json.loads(str(verifier_rows[0]["assistant_output_text"]))
    findings = verifier.get("findings") if isinstance(verifier, Mapping) else None
    _require(
        isinstance(verifier, Mapping)
        and set(verifier)
        == {"findings", "bound_lead_digest", "bound_writer_digest", "decision"}
        and isinstance(findings, list)
        and len(findings) == 4
        and all(isinstance(row, Mapping) for row in findings),
        "fresh_exact_verifier_outer_shape_mismatch",
    )
    finding_rows = [dict(row) for row in findings]
    layers = [str(row.get("layer") or "") for row in finding_rows]
    statuses = [str(row.get("status") or "") for row in finding_rows]
    issue_counts = [
        len(row["issue_codes"])
        if isinstance(row.get("issue_codes"), list)
        else -1
        for row in finding_rows
    ]
    ref_counts = [
        len(row["artifact_or_claim_refs"])
        if isinstance(row.get("artifact_or_claim_refs"), list)
        else -1
        for row in finding_rows
    ]
    repair_owner_types = [
        type(row.get("repair_owner")).__name__ for row in finding_rows
    ]
    _require(
        tuple(layers) == S3_FOUR_LAYER_VERIFIER_LAYERS
        and all(set(row) == TYPED_FINDING_KEYS for row in finding_rows)
        and statuses == ["pass", "pass", "pass", "pass"]
        and issue_counts == [0, 0, 0, 0]
        and ref_counts == [0, 0, 0, 0]
        and repair_owner_types
        == ["NoneType", "NoneType", "NoneType", "NoneType"]
        and verifier.get("decision") == "accept_for_internal_review",
        "fresh_exact_verifier_safe_structure_drift",
    )

    event_types = [str(row.get("event_type") or "") for row in events]
    failed_event = next(
        row
        for row in events
        if row.get("event_type") == "RESEARCH_RUN_FAILED"
    )
    failed_payload = failed_event.get("payload") or {}
    capture_refs = failed_payload.get("provider_output_capture_refs") or []
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
        and len(capture_refs) == 12
        and "RESEARCH_RUN_PROVIDER_OUTPUT_CAPTURED" not in event_types,
        "fresh_exact_atomic_failure_event_contract_mismatch",
    )

    launch_path = supervision_root / "launch_receipt.json"
    command_path = supervision_root / "child_command.json"
    exit_path = supervision_root / "exit_receipt.json"
    stdout_path = supervision_root / "child.stdout.log"
    stderr_path = supervision_root / "child.stderr.log"
    launch = json.loads(launch_path.read_text(encoding="utf-8"))
    command = json.loads(command_path.read_text(encoding="utf-8"))
    stdout_digest, stdout_bytes = _digest_file(stdout_path)
    stderr_digest, stderr_bytes = _digest_file(stderr_path)
    _require(
        launch.get("contract_ref") == "fin01.s3.exact_run_supervision:v1"
        and launch.get("parent_enforced_timeout_seconds") is None
        and launch.get("parent_may_terminate_child") is False
        and launch.get("monitoring_contract") == "read_only_no_signal_no_retry"
        and launch.get("automatic_retry_count") == 0
        and launch.get("fallback_count") == 0
        and launch.get("replay_count") == 0
        and command.get("automatic_retry_count") == 0
        and command.get("fallback_count") == 0
        and command.get("replay_count") == 0
        and not exit_path.exists()
        and runtime_result_path.exists(),
        "fresh_exact_supervision_receipt_truth_mismatch",
    )

    validator_source = inspect.getsource(
        S3ThreeCellBoundedAgentExecutor._validate_verifier_output
    )
    request_source = inspect.getsource(
        DeepSeekS3ThreeCellNodeExecutor._node_request
    )
    _require(
        '"repair_owner": "string"' in request_source
        and '"repair_owner": "must_equal_none"' in request_source
        and 'not isinstance(row.get("repair_owner"), str)' in validator_source
        and 'not str(row.get("repair_owner") or "").strip()'
        in validator_source,
        "fresh_exact_repair_owner_contract_source_mismatch",
    )

    database_digest_after = _sha256(database_path)
    object_digest_after = _tree_digest(object_root)
    _require(
        database_digest_after == database_digest_before
        and object_digest_after == object_digest_before,
        "fresh_exact_safe_audit_changed_runtime",
    )
    return {
        "schema_version": (
            "fin_ia_0_1_s3_t09_atomic_terminalization_and_typed_"
            "verifier_state_machine_fresh_exact_live_execution_result_v1_0"
        ),
        "status": STATUS,
        "authority": {
            "user_instruction": "继续",
            "fresh_exact_live_execution_authorized": True,
            "automatic_retry_fallback_patch_replay_relaunch_or_rerun_authorized": (
                False
            ),
            "paired_comparison_owner_acceptance_T10_S4_release_or_production_authorized": (
                False
            ),
        },
        "source_refs": {
            "issuance": (
                "configs/releases/fin_ia_0_1_s3_t09_atomic_terminalization_"
                "and_typed_verifier_state_machine_fresh_exact_admission_"
                "issuance_v1_0.json"
            ),
            "runtime_result": runtime_result_path.relative_to(ROOT).as_posix(),
            "supervision_root": supervision_root.relative_to(ROOT).as_posix(),
        },
        "identity": {
            **IDENTITY,
            "admission_digest": ADMISSION_DIGEST,
            "admission_consumed": True,
        },
        "preflight": {
            "project_os_scoped_preflight": "pass",
            "exact_runner_preflight": "pass_exact_zero_call_execution_preflight",
            "transport_retries": 0,
            "target_counts_before": [20, 20, 20, 13],
        },
        "provider_execution": {
            "provider": provider.get("provider"),
            "model": provider.get("model"),
            "observed_counts": observed,
            "usage": usage,
            "all_status_ok": True,
            "all_finish_reason_stop": True,
            "retry_count": 0,
            "fallback_count": 0,
            "patch_count": 0,
            "relaunch_count": 0,
            "rerun_count": 0,
        },
        "restricted_capture_audit": {
            "capture_count": len(captures),
            "restricted_readback_count": len(captures),
            "verifier_capture_count": len(verifier_rows),
            "raw_assistant_output_persisted_in_result": False,
            "private_reasoning_persisted_in_result": False,
        },
        "verifier_safe_structure": {
            "contract_ref": S3_OWNER_GRADE_VERIFIER_STATE_MACHINE_REF,
            "native_json_object": True,
            "top_level_keys": sorted(map(str, verifier)),
            "finding_count": len(finding_rows),
            "layers": layers,
            "finding_keys": [
                sorted(map(str, row)) for row in finding_rows
            ],
            "statuses": statuses,
            "issue_code_counts": issue_counts,
            "artifact_or_claim_ref_counts": ref_counts,
            "repair_owner_types": repair_owner_types,
            "decision": str(verifier.get("decision") or ""),
            "bound_lead_digest_is_sha256_shape": (
                isinstance(verifier.get("bound_lead_digest"), str)
                and len(str(verifier["bound_lead_digest"])) == 64
            ),
            "bound_writer_digest_is_sha256_shape": (
                isinstance(verifier.get("bound_writer_digest"), str)
                and len(str(verifier["bound_writer_digest"])) == 64
            ),
            "state_machine_semantics_satisfied": True,
            "required_string_shape_satisfied": False,
            "local_failure_code": "s3_bounded_verifier_finding_schema_invalid",
        },
        "canonical_terminal_truth": {
            "work_unit_state": "failed",
            "attempt_state": "failed",
            "research_run_state": "failed",
            "orphaned_run": False,
            "artifact_count": 0,
            "event_types": event_types,
            "terminal_failure_event_capture_ref_count": len(capture_refs),
            "separate_preterminal_capture_event_present": False,
            "atomic_capture_bearing_failure_transaction_live_proven": True,
            "target_counts_after": [21, 21, 21, 13],
            "canonical_database_sha256": database_digest_after,
            "canonical_object_tree_sha256": object_digest_after,
        },
        "supervision_observation": {
            "contract_ref": launch["contract_ref"],
            "launch_receipt_present": True,
            "child_command_receipt_present": True,
            "supervisor_pid": int(launch["supervisor_pid"]),
            "runner_pid_observed": 35_312,
            "wrapper_pid_alive_when_observed_after_launch": False,
            "runner_alive_after_wrapper_loss_when_observed": True,
            "runner_naturally_exited_without_signal": True,
            "runtime_result_present": True,
            "exit_receipt_present": False,
            "stdout_sha256": stdout_digest,
            "stdout_bytes": stdout_bytes,
            "stderr_sha256": stderr_digest,
            "stderr_bytes": stderr_bytes,
            "raw_provider_body_in_audit_result": False,
            "credential_value_in_audit_result": False,
            "monitor_signals_sent": 0,
            "automatic_retry_count": 0,
            "fallback_count": 0,
            "replay_count": 0,
            "relaunch_count": 0,
        },
        "root_cause_classification": {
            "verifier_direct_failure": (
                "provider_returned_JSON_null_for_repair_owner_while_"
                "required_output_schema_declared_string"
            ),
            "provider_state_machine_semantics_followed": True,
            "project_owned_request_ambiguity": (
                "repair_owner_declared_string_but_pass_rule_says_"
                "must_equal_none_without_explicit_string_literal_sentinel"
            ),
            "local_validator_drift_from_provider_state_machine_semantics": (
                "pre_state_machine_shape_gate_requires_nonempty_string"
            ),
            "model_only_failure": False,
            "supervision_failure": (
                "detached_wrapper_lost_before_exit_receipt_while_runner_"
                "continued_and_reached_canonical_terminal_failure"
            ),
            "supervision_model_related": False,
            "new_root_cause_ids": [
                "RC-P36-052-verifier-repair-owner-none-sentinel-ambiguity",
                "RC-P38-053-windows-detached-wrapper-exit-receipt-loss",
            ],
        },
        "acceptance": {
            "RC_P38_050_atomic_failure_terminalization_live_proven": True,
            "RC_P36_051_state_machine_semantics_live_followed": True,
            "supervision_contract_complete": False,
            "typed_verifier_end_to_end_complete": False,
            "nine_artifact_product_complete": False,
            "paired_comparison_performed": False,
            "owner_acceptance_performed": False,
            "S3_T09": "blocked",
        },
        "observed_counts": {
            "admission_consumptions": 1,
            "supervisor_launches": 1,
            "live_executions": 1,
            "model_calls": 12,
            "provider_calls": 12,
            "network_calls": 12,
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
        raise FreshExactLiveFailureAuditError(
            "fresh_exact_live_audit_output_already_exists"
        )
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
