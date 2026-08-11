from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_VERIFIER_STATE_MACHINE_REF,
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from scripts.releases.issue_fin_ia_0_1_s3_t09_atomic_terminalization_and_verifier_state_machine_fresh_exact_admission import (
    EXPECTED_ADMISSION_DIGEST,
    NEXT_ACTION,
    STATUS_DETAIL,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    _load_admission,
    load_execution_target,
)
from scripts.releases.supervise_fin_ia_0_1_s3_t09_exact_live_execution import (
    SUPERVISION_CONTRACT_REF,
)
from sec_agent.canonical_runtime.models import canonical_digest


RELEASES = ROOT / "configs" / "releases"
PROOF = RELEASES / (
    "fin_ia_0_1_s3_t09_atomic_terminalization_and_typed_"
    "verifier_state_machine_fresh_agent_proof_decision_v1_0.json"
)
ADMISSION = RELEASES / (
    "fin_ia_0_1_s3_t09_three_cell_deepseek_atomic_terminalization_"
    "verifier_state_machine_supervised_exact_admission_r1.json"
)
ISSUANCE = RELEASES / (
    "fin_ia_0_1_s3_t09_atomic_terminalization_and_typed_"
    "verifier_state_machine_fresh_exact_admission_issuance_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_issued_admission_is_exact_frozen_payload_and_runner_loadable() -> None:
    proof = _load(PROOF)
    payload = _load(ADMISSION)
    issuance = _load(ISSUANCE)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    admission.assert_profile_admissible()

    assert payload == proof["prospective_admission"]["payload"]
    digest = canonical_digest(admission.digest_payload())
    assert digest == proof["prospective_admission"]["digest"]
    assert digest == issuance["issued_admission"]["admission_digest"]
    assert digest == EXPECTED_ADMISSION_DIGEST
    target = load_execution_target(ISSUANCE)
    assert _load_admission(ADMISSION, target) == admission
    assert target.research_run_id == proof["identity"]["research_run_id"]


def test_issuance_reverifies_exact_code_and_failure_contracts() -> None:
    issuance = _load(ISSUANCE)
    proof = _load(PROOF)
    reverification = issuance["proof_reverification"]

    assert issuance["status"] == "issued_unconsumed_zero_call_preflight_pass"
    assert issuance["status_detail"] == STATUS_DETAIL
    assert reverification["generator_rerun_before_materialization"] is True
    assert reverification[
        "frozen_and_regenerated_critical_sections_equal"
    ] is True
    assert reverification["double_prepare_equal"] is True
    assert reverification["exact_code_bindings"] == proof[
        "exact_code_bindings"
    ]
    superseded = {
        "apps/workbench/backend/application/bounded_agent_executor.py",
        "scripts/releases/supervise_fin_ia_0_1_s3_t09_exact_live_execution.py",
        "scripts/releases/run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution.py",
    }
    for relative, digest in reverification["exact_code_bindings"].items():
        if relative in superseded:
            assert _sha256(ROOT / relative) != digest
        else:
            assert _sha256(ROOT / relative) == digest

    atomic = issuance[
        "atomic_failure_terminalization_acceptance_contract"
    ]
    verifier = issuance["typed_verifier_state_machine_acceptance_contract"]
    assert atomic["runtime_exception_path_command_count"] == 1
    assert atomic["separate_preterminal_capture_event_allowed"] is False
    assert verifier["contract_ref"] == (
        "fin01.s3.owner_grade_verifier_output_state_machine:v1"
    )
    assert verifier["positive_state_fixture_count"] == 3
    assert verifier["closed_negative_subtype_count"] == 7


def test_issuance_stops_before_consumption_supervisor_and_live_execution() -> None:
    issuance = _load(ISSUANCE)
    boundary = issuance["issuance_boundary"]
    observed = issuance["observed_counts"]

    assert issuance["issued_admission"]["consumed"] is False
    assert issuance["issued_admission"]["execution_started"] is False
    assert issuance["authority"][
        "admission_consumption_or_exact_live_execution_authorized"
    ] is False
    assert boundary == {
        "admission_issued": True,
        "admission_consumed": False,
        "execution_started": False,
        "supervisor_launched": False,
        "live_execution_started": False,
        "capture_replay_performed": False,
        "business_artifact_materialization_performed": False,
        "paired_comparison_performed": False,
        "owner_acceptance_performed": False,
    }
    assert observed["new_admissions"] == 1
    assert set(
        value for key, value in observed.items() if key != "new_admissions"
    ) == {0}


def test_supervision_and_factory_validation_remain_zero_call() -> None:
    issuance = _load(ISSUANCE)
    supervision = issuance["supervision_acceptance_contract"]
    callback_calls = 0

    def _must_not_call_provider(**_: object) -> dict:
        nonlocal callback_calls
        callback_calls += 1
        raise AssertionError("provider_callback_forbidden_in_issuance_test")

    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(ADMISSION)
    )
    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=_must_not_call_provider,
    )
    assert callback_calls == 0
    assert supervision["contract_ref"] == "fin01.s3.exact_run_supervision:v1"
    assert supervision["launch_path"] == "detached_supervisor_only"
    assert supervision["minimum_lifecycle_budget_seconds"] == 1_560
    assert supervision["parent_enforced_timeout_seconds"] is None
    assert supervision["parent_may_terminate_child"] is False
    assert supervision["monitoring_contract"] == "read_only_no_signal_no_retry"


def test_backlog_preserves_issuance_after_live_failure_gate() -> None:
    issuance = _load(ISSUANCE)
    next_action = _load(BACKLOG)["next_action"]

    assert issuance["next_action"] == NEXT_ACTION
    assert next_action["item_id"] == (
        "S3-T09-NULLABLE-REPAIR-OWNER-AND-WINDOWS-DIRECT-RUNNER-"
        "SUPERVISION-V2-FRESH-AGENT-PROOF-DECISION"
    )
    assert next_action["repair_implementation_complete"] is True
    assert next_action["fresh_exact_admission_issuance_authorized"] is False
    assert next_action["fresh_exact_admission_issued"] is False
    assert next_action["fresh_exact_admission_consumed"] is False
    assert next_action["fresh_exact_execution_authorized"] is False
    assert next_action["second_live_execution_authorized"] is False
    assert next_action["agent_execution_authorized"] is False
    assert next_action["fresh_exact_admission_issuance_ref"] == (
        ISSUANCE.relative_to(ROOT).as_posix()
    )
