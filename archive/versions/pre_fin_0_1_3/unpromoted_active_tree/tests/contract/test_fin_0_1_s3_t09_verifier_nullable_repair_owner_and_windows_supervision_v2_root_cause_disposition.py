from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

RELEASES = ROOT / "configs" / "releases"
DECISION = RELEASES / (
    "fin_ia_0_1_s3_t09_verifier_nullable_repair_owner_and_windows_"
    "direct_runner_supervision_v2_zero_call_root_cause_disposition_v1_0.json"
)
LIVE_RESULT = RELEASES / (
    "fin_ia_0_1_s3_t09_atomic_terminalization_and_typed_verifier_"
    "state_machine_fresh_exact_live_execution_result_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
NEXT_ACTION = (
    "S3-T09-NULLABLE-REPAIR-OWNER-AND-WINDOWS-DIRECT-RUNNER-"
    "SELF-FINALIZING-SUPERVISION-V2-ZERO-CALL-IMPLEMENTATION"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_live_evidence_proves_semantic_pass_and_null_shape_conflict() -> None:
    live = _load(LIVE_RESULT)
    verifier = live["verifier_safe_structure"]
    root_cause = live["root_cause_classification"]

    assert verifier["statuses"] == ["pass", "pass", "pass", "pass"]
    assert verifier["issue_code_counts"] == [0, 0, 0, 0]
    assert verifier["artifact_or_claim_ref_counts"] == [0, 0, 0, 0]
    assert verifier["repair_owner_types"] == ["NoneType"] * 4
    assert verifier["state_machine_semantics_satisfied"] is True
    assert verifier["required_string_shape_satisfied"] is False
    assert root_cause["model_only_failure"] is False


def test_disposition_binds_the_preimplementation_source_digests() -> None:
    decision = _load(DECISION)
    digests = decision["source_digests"]
    current_verifier = hashlib.sha256(
        (
            ROOT
            / "apps/workbench/backend/application/bounded_agent_executor.py"
        ).read_bytes()
    ).hexdigest()
    current_supervisor = hashlib.sha256(
        (
            ROOT
            / "scripts/releases/"
            "supervise_fin_ia_0_1_s3_t09_exact_live_execution.py"
        ).read_bytes()
    ).hexdigest()

    assert digests["verifier_request_and_validator_owner_sha256"] == (
        "7fe4fa1803039589a8d8e82bf2168925378b5adedf9b070af2d0e203c4077035"
    )
    assert digests["supervision_owner_sha256"] == (
        "8807ff831d5f46833d8461459e7e1af96107835bf6cf7ebe575e98c50583f74f"
    )
    assert current_verifier != digests[
        "verifier_request_and_validator_owner_sha256"
    ]
    assert current_supervisor != digests["supervision_owner_sha256"]


def test_disposition_selects_nullable_v2_and_direct_runner_supervision_v2() -> None:
    decision = _load(DECISION)
    selected = decision["selected_zero_call_implementation_contract"]
    nullable = selected["nullable_repair_owner_state_machine_v2"]
    supervision = selected[
        "windows_direct_runner_self_finalizing_supervision_v2"
    ]

    assert decision["status"] == (
        "pass_zero_call_dual_root_cause_frozen_nullable_repair_owner_"
        "and_windows_direct_runner_self_finalizing_supervision_v2_selected"
    )
    assert nullable["contract_ref"].endswith(":v2")
    assert nullable["required_output_schema"]["pass_repair_owner"] == (
        "must_be_JSON_null"
    )
    assert nullable["required_output_schema"]["literal_string_none_allowed"] is (
        False
    )
    assert nullable["normalization_or_silent_rewrite_allowed"] is False
    assert supervision["contract_ref"].endswith(":v2")
    assert "actual exact runner directly" in supervision["process_topology"]
    assert supervision["pid_reuse_guard_required"] is True
    assert supervision["read_only_monitor_may_signal_or_terminate"] is False
    assert supervision["host_job_lifetime_preflight"][
        "required_before_admission_consumption"
    ] is True


def test_disposition_preserves_zero_call_authority_and_routes_implementation() -> None:
    decision = _load(DECISION)
    backlog = _load(BACKLOG)

    assert decision["next_action"] == NEXT_ACTION
    assert set(decision["observed_counts"].values()) == {0}
    assert decision["authority"]["repair_implementation_authorized"] is False
    assert decision["authority"][
        "new_admission_or_second_live_execution_authorized"
    ] is False
    assert backlog["next_action"]["item_id"] == (
        "S3-T09-NULLABLE-REPAIR-OWNER-AND-WINDOWS-DIRECT-RUNNER-"
        "SUPERVISION-V2-FRESH-AGENT-PROOF-DECISION"
    )
    assert backlog["next_action"]["root_cause_disposition_authorized"] is True
    assert backlog["next_action"]["repair_implementation_authorized"] is True
    assert backlog["next_action"]["repair_implementation_complete"] is True
    assert backlog["next_action"]["agent_execution_authorized"] is False
    assert backlog["next_action"]["second_live_execution_authorized"] is False
