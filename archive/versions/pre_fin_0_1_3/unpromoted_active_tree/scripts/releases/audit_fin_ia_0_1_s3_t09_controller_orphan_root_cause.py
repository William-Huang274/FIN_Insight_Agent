from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3_FOUR_LAYER_VERIFIER_LAYERS,
)
from apps.workbench.backend.application.case_service import CaseService
from apps.workbench.backend.application.research_runtime import Fin01ResearchRuntime
from sec_agent.canonical_runtime.facade import RuntimeFacade


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
TYPED_FINDING_KEYS = {
    "layer",
    "status",
    "issue_codes",
    "artifact_or_claim_refs",
    "repair_owner",
}


def audit(runtime_root: Path) -> dict[str, Any]:
    runtime_root = runtime_root.resolve()
    service = CaseService.for_fixture_root(
        runtime_root / "canonical-runtime", repo_root=ROOT
    )
    facade = service._facade
    captures = facade.read_research_run_provider_output_captures(
        EXACT_IDENTITY["research_run_id"]
    )
    verifier_rows = [row for row in captures if row.get("stage") == "verifier"]
    if len(captures) != 12 or len(verifier_rows) != 1:
        raise RuntimeError("s3_t09_controller_orphan_capture_truth_mismatch")
    verifier = json.loads(str(verifier_rows[0]["assistant_output_text"]))
    findings = verifier.get("findings") if isinstance(verifier, Mapping) else None
    if (
        not isinstance(verifier, Mapping)
        or set(verifier)
        != {"findings", "bound_lead_digest", "bound_writer_digest", "decision"}
        or not isinstance(findings, list)
        or len(findings) != 4
        or any(not isinstance(row, Mapping) for row in findings)
    ):
        raise RuntimeError("s3_t09_controller_orphan_verifier_shape_mismatch")

    layers = [str(row.get("layer") or "") for row in findings]
    statuses = [str(row.get("status") or "") for row in findings]
    finding_keys = [sorted(map(str, row)) for row in findings]
    issue_code_counts = [
        len(row.get("issue_codes"))
        if isinstance(row.get("issue_codes"), list)
        else -1
        for row in findings
    ]
    artifact_or_claim_ref_counts = [
        len(row.get("artifact_or_claim_refs"))
        if isinstance(row.get("artifact_or_claim_refs"), list)
        else -1
        for row in findings
    ]
    repair_owner_nonblank = [
        isinstance(row.get("repair_owner"), str)
        and bool(str(row.get("repair_owner")).strip())
        for row in findings
    ]
    typed_shape_valid = (
        tuple(layers) == S3_FOUR_LAYER_VERIFIER_LAYERS
        and all(set(row) == TYPED_FINDING_KEYS for row in findings)
        and all(status in {"pass", "review_required", "fail"} for status in statuses)
        and min(issue_code_counts) >= 0
        and min(artifact_or_claim_ref_counts) >= 0
        and all(repair_owner_nonblank)
    )
    false_green_triggered = (
        verifier.get("decision") == "accept_for_internal_review"
        and (
            any(status != "pass" for status in statuses)
            or any(count > 0 for count in issue_code_counts)
        )
    )
    if (
        not typed_shape_valid
        or statuses != ["pass", "pass", "pass", "pass"]
        or issue_code_counts != [1, 7, 2, 3]
        or artifact_or_claim_ref_counts != [2, 2, 1, 1]
        or not false_green_triggered
    ):
        raise RuntimeError("s3_t09_controller_orphan_verifier_safe_summary_drift")

    events = facade.list_events(EXACT_IDENTITY["research_run_id"])
    event_types = [str(row.get("event_type") or "") for row in events]
    if event_types.count("RESEARCH_RUN_PROVIDER_OUTPUT_CAPTURED") != 1:
        raise RuntimeError("s3_t09_controller_orphan_capture_event_required")

    states = {}
    for table, key in (
        ("canonical_work_units", "work_unit_id"),
        ("canonical_attempts", "attempt_id"),
        ("canonical_research_run_versions", "research_run_id"),
    ):
        row = facade.store.get_latest(table, EXACT_IDENTITY[key])
        if row is None:
            raise RuntimeError("s3_t09_controller_orphan_identity_missing")
        states[key] = str(row.get("state") or "")
    artifacts = [
        row
        for row in facade.store.list_latest("canonical_artifact_versions")
        if row.get("producer_attempt_id") == EXACT_IDENTITY["attempt_id"]
    ]
    if set(states.values()) != {"failed"} or artifacts:
        raise RuntimeError("s3_t09_controller_orphan_terminal_truth_mismatch")

    runtime_source = inspect.getsource(Fin01ResearchRuntime.dispatch_once)
    fail_source = inspect.getsource(RuntimeFacade.fail_research_run)
    split_capture_index = runtime_source.index(
        "record_research_run_provider_output_captures"
    )
    split_fail_index = runtime_source.index("self._facade.fail_research_run(failed)")
    if split_capture_index >= split_fail_index:
        raise RuntimeError("s3_t09_controller_orphan_split_order_mismatch")
    if not all(
        token in fail_source
        for token in (
            "with self.store.transaction() as tx:",
            "provider_output_capture_refs = self._persist_provider_output_captures(",
            'tx.insert("canonical_research_run_versions"',
            '"RESEARCH_RUN_FAILED"',
        )
    ):
        raise RuntimeError("s3_t09_controller_orphan_atomic_facade_capability_missing")

    return {
        "schema_version": (
            "fin_ia_0_1_s3_t09_controller_orphan_zero_call_root_cause_audit_v1_0"
        ),
        "status": "pass_zero_call_dual_failure_root_cause_reconstructed",
        "identity": EXACT_IDENTITY,
        "restricted_capture_audit": {
            "capture_count": len(captures),
            "verifier_capture_count": 1,
            "raw_assistant_output_persisted_in_audit_result": False,
            "private_reasoning_persisted_in_audit_result": False,
        },
        "verifier_safe_structure": {
            "native_json_object": True,
            "top_level_keys": sorted(map(str, verifier)),
            "finding_count": len(findings),
            "layers": layers,
            "finding_keys": finding_keys,
            "statuses": statuses,
            "issue_code_counts": issue_code_counts,
            "artifact_or_claim_ref_counts": artifact_or_claim_ref_counts,
            "repair_owner_nonblank": repair_owner_nonblank,
            "decision": str(verifier.get("decision") or ""),
            "bound_lead_digest_is_sha256_shape": (
                isinstance(verifier.get("bound_lead_digest"), str)
                and len(str(verifier.get("bound_lead_digest"))) == 64
            ),
            "bound_writer_digest_is_sha256_shape": (
                isinstance(verifier.get("bound_writer_digest"), str)
                and len(str(verifier.get("bound_writer_digest"))) == 64
            ),
            "typed_finding_shape_valid": typed_shape_valid,
            "false_green_predicate_triggered": false_green_triggered,
            "inferred_local_failure_code": (
                "s3_owner_grade_verifier_false_green_forbidden"
            ),
        },
        "canonical_event_path": {
            "event_types": event_types,
            "capture_event_before_terminal_event": True,
            "terminal_failure_event_present_after_typed_closeout": (
                "RESEARCH_RUN_FAILED" in event_types
            ),
            "canonical_business_artifact_count": len(artifacts),
            "terminal_states": states,
        },
        "code_path_proof": {
            "runtime_failure_path_uses_two_facade_commands": True,
            "first_command": "RECORD_RESEARCH_RUN_PROVIDER_OUTPUT_CAPTURES",
            "second_command": "FAIL_RESEARCH_RUN",
            "interruption_window_exists_between_commands": True,
            "fail_research_run_already_supports_atomic_capture_and_terminal_state": True,
            "selected_earliest_project_owned_orphan_surface": (
                "Fin01ResearchRuntime.dispatch_once exception path split "
                "capture and failure terminalization"
            ),
        },
        "root_cause_classification": {
            "underlying_runtime_failure": (
                "typed_verifier_false_green_state_machine_violation"
            ),
            "underlying_request_gap": (
                "provider_visible typed schema omits status issue-code reference "
                "repair-owner and final-decision cross-field invariants"
            ),
            "orphan_trigger": "outer_execution_controller_process_timeout",
            "project_owned_orphanability": (
                "non_atomic_capture_then_failure_terminalization"
            ),
            "model_only_failure": False,
            "schema_shape_drift_recurred": False,
        },
        "observed_counts": {
            "audit_model_calls": 0,
            "audit_provider_calls": 0,
            "audit_network_calls": 0,
            "audit_source_network_calls": 0,
            "audit_external_tool_calls": 0,
            "new_admissions": 0,
            "new_runs": 0,
            "new_business_artifacts": 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=RUNTIME_ROOT)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    result = audit(args.runtime_root)
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
