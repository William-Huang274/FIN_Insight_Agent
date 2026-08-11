from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (  # noqa: E402
    S3_OWNER_GRADE_VERIFIER_STATE_MACHINE_REF,
    S3ThreeCellBoundedAgentAdmission,
)
from scripts.releases.issue_fin_ia_0_1_s3_t09_nullable_owner_and_supervision_v2_final_exact_admission import (  # noqa: E402
    ADMISSION,
    EXPECTED_ADMISSION_DIGEST,
    ISSUANCE,
    NEXT_ACTION,
    STATUS_DETAIL,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (  # noqa: E402
    _load_admission,
    load_execution_target,
)
from scripts.releases.supervise_fin_ia_0_1_s3_t09_exact_live_execution import (  # noqa: E402
    SUPERVISION_CONTRACT_REF,
    _validate_host_capability_receipt,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_final_v2_admission_is_issued_unconsumed_and_exactly_bound() -> None:
    issuance = _load(ISSUANCE)
    payload = _load(ADMISSION)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)

    assert issuance["status"] == "issued_unconsumed_zero_call_preflight_pass"
    assert issuance["status_detail"] == STATUS_DETAIL
    assert canonical_digest(admission.digest_payload()) == (
        EXPECTED_ADMISSION_DIGEST
    )
    assert issuance["issued_admission"]["admission_digest"] == (
        EXPECTED_ADMISSION_DIGEST
    )
    assert issuance["issued_admission"]["consumed"] is False
    assert issuance["issued_admission"]["execution_started"] is False
    assert issuance["issuance_boundary"]["supervisor_launched"] is False
    assert issuance["next_action"] == NEXT_ACTION


def test_final_v2_issuance_reverifies_code_nullable_and_supervision() -> None:
    issuance = _load(ISSUANCE)
    proof = issuance["proof_reverification"]
    nullable = issuance["nullable_owner_state_machine_v2_acceptance_contract"]
    supervision = issuance["supervision_v2_acceptance_contract"]

    assert proof["generator_rerun_before_materialization"] is True
    assert proof["frozen_and_regenerated_critical_sections_equal"] is True
    assert proof["double_prepare_equal"] is True
    superseded_after_historical_issuance = {
        "apps/workbench/backend/application/bounded_agent_executor.py",
    }
    for relative, digest in proof["exact_code_bindings"].items():
        current = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        if relative in superseded_after_historical_issuance:
            assert current != digest
        else:
            assert current == digest
    assert nullable["contract_ref"] == (
        S3_OWNER_GRADE_VERIFIER_STATE_MACHINE_REF
    )
    assert nullable["pass_repair_owner"] == "JSON_null"
    assert nullable["literal_string_none_allowed"] is False
    assert supervision["contract_ref"] == SUPERVISION_CONTRACT_REF
    assert supervision["launch_path"] == (
        "direct_actual_runner_no_intermediate_wrapper"
    )
    capability_path = ROOT / proof["host_capability_receipt_ref"]
    capability, capability_digest = _validate_host_capability_receipt(
        capability_path
    )
    assert capability_digest == proof["host_capability_receipt_sha256"]
    assert capability["durable_process_strategy"] == (
        "windows_CREATE_BREAKAWAY_FROM_JOB_direct_runner"
    )


def test_final_v2_issuance_loads_through_exact_runner_without_calls() -> None:
    issuance = _load(ISSUANCE)
    target = load_execution_target(ISSUANCE)
    admission = _load_admission(ADMISSION, target)

    assert target.work_unit_id == (
        issuance["exact_binding"]["predicted_work_unit_id"]
    )
    assert target.attempt_id == issuance["exact_binding"]["predicted_attempt_id"]
    assert target.research_run_id == (
        issuance["exact_binding"]["predicted_research_run_id"]
    )
    assert admission.retry_budget == 0
    assert admission.max_transport_attempts_per_call == 1
    assert admission.max_provider_calls == 12
    assert admission.max_total_cost_usd == 0.10


def test_final_v2_issuance_authorizes_one_execution_but_no_retry() -> None:
    issuance = _load(ISSUANCE)
    authority = issuance["authority"]
    envelope = issuance["execution_envelope"]
    counts = issuance["observed_counts"]

    assert authority[
        "admission_consumption_or_exact_live_execution_authorized"
    ] is True
    assert authority[
        "automatic_retry_fallback_patch_or_rerun_authorized"
    ] is False
    assert envelope["maximum_provider_calls"] == 12
    assert envelope["retry_budget"] == 0
    assert envelope["automatic_retry_repair_fallback_or_rerun_allowed"] is False
    assert counts["new_admissions"] == 1
    assert set(
        value for key, value in counts.items() if key != "new_admissions"
    ) == {0}
