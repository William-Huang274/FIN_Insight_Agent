from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_SPECIALIST_LOCAL_ASSEMBLY_CAPACITY_CONTRACT_REF,
    S4_DELL_THREE_CELL_RESEARCH_PROFILE_V3_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
)
from scripts.releases.prepare_fin_ia_0_1_s4_t05_dell_r8_specialist_validated_segment_union_capacity_fresh_proof import (
    DECISION,
    PROSPECTIVE_ADMISSION as ADMISSION,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_paired_deterministic_baseline_decision import (
    _logical_snapshot,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    load_execution_target,
)
from sec_agent.canonical_runtime.models import canonical_digest


ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r9_specialist_validated_"
    "segment_union_capacity_fresh_exact_admission_issuance_v1_0.json"
)
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r9_specialist_validated_"
    "segment_union_capacity_exact_live_execution_failure_result_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_R9_capacity_admission_is_exact_frozen_payload() -> None:
    proof = _load(DECISION)
    issuance = _load(ISSUANCE)
    payload = _load(ADMISSION)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)

    admission.assert_profile_admissible()
    assert payload == proof["prospective_admission"]["payload"]
    assert admission.research_profile_ref == (
        S4_DELL_THREE_CELL_RESEARCH_PROFILE_V3_REF
    )
    assert canonical_digest(admission.digest_payload()) == proof[
        "prospective_admission"
    ]["digest"]
    assert proof["prospective_admission"]["digest"] == issuance[
        "issued_admission"
    ]["admission_digest"]
    assert issuance["source_proof_decision_sha256"] == _sha256(DECISION)


def test_R9_capacity_issuance_is_unconsumed_and_zero_call() -> None:
    issuance = _load(ISSUANCE)
    issued = issuance["issued_admission"]
    boundary = issuance["issuance_boundary"]

    assert issuance["status"] == "issued_unconsumed_zero_call_preflight_pass"
    assert (
        issued["issued"],
        issued["consumed"],
        issued["execution_started"],
    ) == (True, False, False)
    assert (
        boundary["admission_issued"],
        boundary["admission_consumed"],
        boundary["execution_started"],
        boundary["model_or_provider_call_started"],
    ) == (True, False, False, False)
    assert issuance["zero_call_preflight"]["provider_callback_calls"] == 0
    assert issuance["observed_counts"]["new_admissions"] == 1
    assert set(
        value
        for key, value in issuance["observed_counts"].items()
        if key != "new_admissions"
    ) == {0}


def test_R9_capacity_binding_and_budget_are_frozen() -> None:
    issuance = _load(ISSUANCE)
    binding = issuance["exact_binding"]
    envelope = issuance["execution_envelope"]
    proof_identity = _load(DECISION)["fresh_identity"]

    assert binding["predicted_work_unit_id"] == proof_identity[
        "work_unit_id"
    ]
    assert binding["predicted_attempt_id"] == proof_identity["attempt_id"]
    assert binding["predicted_research_run_id"] == proof_identity[
        "research_run_id"
    ]
    assert binding["research_profile_ref"] == (
        S4_DELL_THREE_CELL_RESEARCH_PROFILE_V3_REF
    )
    assert binding["capacity_contract_ref"] == (
        S3_SPECIALIST_LOCAL_ASSEMBLY_CAPACITY_CONTRACT_REF
    )
    assert binding["provider_local_segment_whole_caps"] == [
        6000,
        8192,
        24576,
    ]
    assert envelope["maximum_provider_calls"] == 12
    assert envelope["maximum_output_tokens_total"] == 18000
    assert envelope["maximum_total_cost_usd"] == 0.1
    assert envelope["transport_retry_count"] == 0


def test_R9_capacity_issuance_advances_only_to_execution_authority() -> None:
    issuance = _load(ISSUANCE)
    target = load_execution_target(ISSUANCE)

    assert issuance["stage_acceptance"]["DELL_R2"] == "not_proven"
    assert issuance["stage_acceptance"]["S4_T06"] == "not_entered"
    assert target.admission_digest == issuance["issued_admission"][
        "admission_digest"
    ]
    assert target.work_unit_id == issuance["exact_binding"][
        "predicted_work_unit_id"
    ]
    assert target.attempt_id == issuance["exact_binding"][
        "predicted_attempt_id"
    ]
    assert target.research_run_id == issuance["exact_binding"][
        "predicted_research_run_id"
    ]
    snapshot = _logical_snapshot(
        ROOT / target.runtime_root_ref / "canonical-runtime/canonical.sqlite",
        target.case_id,
    )
    if RESULT.exists():
        result = _load(RESULT)
        assert target.work_unit_id in snapshot["work_unit_ids"]
        assert target.attempt_id in snapshot["attempt_ids"]
        assert target.research_run_id in snapshot["research_run_ids"]
        assert result["admission"]["consumed"] is True
        assert result["canonical_terminal_truth"]["work_unit_state"] == "failed"
        assert result["canonical_terminal_truth"]["attempt_state"] == "failed"
        assert (
            result["canonical_terminal_truth"]["research_run_state"]
            == "failed"
        )
    else:
        assert target.work_unit_id not in snapshot["work_unit_ids"]
        assert target.attempt_id not in snapshot["attempt_ids"]
        assert target.research_run_id not in snapshot["research_run_ids"]
    assert issuance["next_action"] == (
        "S4-T05-DELL-R9-SPECIALIST-VALIDATED-SEGMENT-UNION-CAPACITY-"
        "EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT-"
        "AUTHORITY-DECISION"
    )
