from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_VERIFIER_STATE_MACHINE_REF,
)
from scripts.releases.issue_fin_ia_0_1_s3_t09_claim_fact_link_policy_fresh_exact_admission import (
    render_issuance,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_atomic_terminalization_and_verifier_state_machine_fresh_exact_proof import (
    CODE_BINDING_PATHS,
    DECISION_STATUS,
    MINIMUM_LIFECYCLE_BUDGET_SECONDS,
    prepare,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    _load_admission,
    load_execution_target,
)
from scripts.releases.supervise_fin_ia_0_1_s3_t09_exact_live_execution import (
    SUPERVISION_CONTRACT_REF,
)


RELEASES = ROOT / "configs" / "releases"
DECISION = RELEASES / (
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
EXPECTED_ADMISSION_DIGEST = (
    "2b87b9360ed53ec060670446125065497f2625f9384839cb65c4482ea8c381e1"
)
ISSUANCE_ID = (
    "S3-T09-ATOMIC-CAPTURE-FAILURE-TERMINALIZATION-AND-TYPED-"
    "VERIFIER-STATE-MACHINE-FRESH-EXACT-ADMISSION-ISSUANCE"
)
NEXT_ACTION = (
    "S3-T09-ATOMIC-CAPTURE-FAILURE-TERMINALIZATION-AND-TYPED-"
    "VERIFIER-STATE-MACHINE-FRESH-EXACT-LIVE-EXECUTION"
)
STATUS_DETAIL = (
    "exact_frozen_payload_code_bindings_double_prepare_target_integrity_"
    "atomic_terminalization_typed_verifier_state_machine_and_detached_"
    "supervision_verified_admission_issued_unconsumed"
)


class AtomicTerminalizationExactAdmissionIssuanceError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise AtomicTerminalizationExactAdmissionIssuanceError(code)


def _assert_reprepared_proof(
    frozen: dict[str, Any], regenerated: dict[str, Any]
) -> None:
    for key in (
        "identity",
        "double_prepare",
        "prospective_admission",
        "target_read_only_audit",
        "exact_code_bindings",
        "atomic_failure_terminalization_acceptance_contract",
        "typed_verifier_state_machine_acceptance_contract",
        "supervision_acceptance_contract",
        "budget_and_stop_contract",
        "artifact_acceptance_contract",
    ):
        _require(
            regenerated.get(key) == frozen.get(key),
            f"frozen_proof_reprepare_mismatch:{key}",
        )
    _require(
        regenerated.get("status") == DECISION_STATUS,
        "reprepared_proof_status_mismatch",
    )
    _require(
        regenerated.get("double_prepare", {}).get("equal") is True,
        "reprepared_proof_double_prepare_not_equal",
    )
    _require(
        set((regenerated.get("observed_counts") or {}).values()) == {0},
        "reprepared_proof_not_zero_call",
    )


def render_atomic_issuance() -> tuple[dict[str, Any], dict[str, Any]]:
    _require(not ADMISSION.exists(), "atomic_terminalization_admission_exists")
    _require(not ISSUANCE.exists(), "atomic_terminalization_issuance_exists")

    frozen = json.loads(DECISION.read_text(encoding="utf-8"))
    regenerated = prepare()
    _assert_reprepared_proof(frozen, regenerated)

    payload, issuance = render_issuance(
        decision_path=DECISION,
        admission_path=ADMISSION,
        issuance_path=ISSUANCE,
        expected_decision_status=DECISION_STATUS,
        expected_admission_digest=EXPECTED_ADMISSION_DIGEST,
        schema_version=(
            "fin_ia_0_1_s3_t09_atomic_terminalization_and_typed_"
            "verifier_state_machine_fresh_exact_admission_issuance_v1_0"
        ),
        issuance_id=ISSUANCE_ID,
        user_instruction="继续",
        live_execution_authorized=False,
        next_action=NEXT_ACTION,
    )

    atomic = frozen["atomic_failure_terminalization_acceptance_contract"]
    verifier = frozen["typed_verifier_state_machine_acceptance_contract"]
    supervision = frozen["supervision_acceptance_contract"]
    _require(
        atomic["runtime_exception_path_command_count"] == 1
        and atomic["failure_command"] == "FAIL_RESEARCH_RUN"
        and atomic["separate_preterminal_capture_event_allowed"] is False,
        "atomic_terminalization_contract_not_frozen",
    )
    _require(
        verifier["contract_ref"] == S3_OWNER_GRADE_VERIFIER_STATE_MACHINE_REF
        and verifier["positive_state_fixture_count"] == 3
        and verifier["closed_negative_subtype_count"] == 7,
        "typed_verifier_state_machine_contract_not_frozen",
    )
    _require(
        supervision["contract_ref"] == SUPERVISION_CONTRACT_REF
        and supervision["minimum_lifecycle_budget_seconds"]
        == MINIMUM_LIFECYCLE_BUDGET_SECONDS
        and supervision["launch_path"] == "detached_supervisor_only"
        and supervision["parent_enforced_timeout_seconds"] is None
        and supervision["parent_may_terminate_child"] is False,
        "detached_supervision_contract_not_frozen",
    )
    _require(
        set(frozen["exact_code_bindings"])
        == {path.as_posix() for path in CODE_BINDING_PATHS},
        "exact_code_binding_surface_mismatch",
    )

    issuance["status_detail"] = STATUS_DETAIL
    issuance["proof_reverification"] = {
        "generator_rerun_before_materialization": True,
        "frozen_and_regenerated_critical_sections_equal": True,
        "double_prepare_equal": True,
        "prepared_payload_digest": regenerated["double_prepare"][
            "prepared_payload_digest"
        ],
        "prospective_admission_digest": EXPECTED_ADMISSION_DIGEST,
        "target_database_and_object_tree_digests_unchanged": True,
        "fresh_work_unit_attempt_and_research_run_absent": True,
        "exact_code_bindings": frozen["exact_code_bindings"],
        "exact_code_binding_count": len(frozen["exact_code_bindings"]),
    }
    issuance["atomic_failure_terminalization_acceptance_contract"] = atomic
    issuance["typed_verifier_state_machine_acceptance_contract"] = verifier
    issuance["supervision_acceptance_contract"] = supervision
    issuance["issuance_boundary"] = {
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
    issuance["observed_counts"].update(
        {
            "supervisor_launches": 0,
            "live_executions": 0,
            "capture_replays": 0,
            "paired_comparisons": 0,
            "owner_acceptance_writes": 0,
        }
    )
    return payload, issuance


def _write_and_validate(
    payload: dict[str, Any], issuance: dict[str, Any]
) -> None:
    temp_paths: list[Path] = []
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            prefix=".atomic-admission-",
            dir=RELEASES,
            delete=False,
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            temp_admission = Path(handle.name)
            temp_paths.append(temp_admission)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            prefix=".atomic-issuance-",
            dir=RELEASES,
            delete=False,
        ) as handle:
            json.dump(issuance, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            temp_issuance = Path(handle.name)
            temp_paths.append(temp_issuance)

        target = load_execution_target(temp_issuance)
        loaded = _load_admission(temp_admission, target)
        _require(
            loaded.admission_id
            == issuance["issued_admission"]["admission_id"],
            "runner_load_admission_id_mismatch",
        )
        os.replace(temp_admission, ADMISSION)
        temp_paths.remove(temp_admission)
        os.replace(temp_issuance, ISSUANCE)
        temp_paths.remove(temp_issuance)
    finally:
        for path in temp_paths:
            path.unlink(missing_ok=True)


def main() -> int:
    payload, issuance = render_atomic_issuance()
    _write_and_validate(payload, issuance)
    print(json.dumps(issuance, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
