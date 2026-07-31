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
    IMPLEMENTATION,
    PROSPECTIVE_ADMISSION,
    build_decision,
)
from sec_agent.canonical_runtime.models import canonical_digest


ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r9_specialist_validated_"
    "segment_union_capacity_fresh_exact_admission_issuance_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_profile_v3_capacity_proof_is_independent_and_reproducible() -> None:
    decision = _load(DECISION)

    if ISSUANCE.exists():
        assert _load(ISSUANCE)["source_proof_decision_sha256"] == _sha256(
            DECISION
        )
    else:
        assert build_decision() == decision
    assert decision["proof_generator"]["independent_invocations"] == 2
    assert decision["proof_generator"]["independent_outputs_equal"] is True


def test_profile_v3_capacity_and_exact_code_bindings_are_frozen() -> None:
    decision = _load(DECISION)
    implementation = _load(IMPLEMENTATION)
    reaudit = decision["implementation_reaudit"]

    assert reaudit["implementation_sha256"] == _sha256(IMPLEMENTATION)
    assert reaudit["research_profile_ref"] == (
        S4_DELL_THREE_CELL_RESEARCH_PROFILE_V3_REF
    )
    assert reaudit["capacity_contract_ref"] == (
        S3_SPECIALIST_LOCAL_ASSEMBLY_CAPACITY_CONTRACT_REF
    )
    assert reaudit["provider_local_segment_whole_caps"] == [
        6000,
        8192,
        24576,
    ]
    for relative_path, expected_digest in reaudit[
        "exact_code_bindings"
    ].items():
        assert _sha256(ROOT / relative_path) == expected_digest


def test_prospective_R9_admission_is_exact_and_materialized_only_by_issuance() -> None:
    decision = _load(DECISION)
    prospective = decision["prospective_admission"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        prospective["payload"]
    )

    admission.assert_profile_admissible()
    assert admission.research_profile_ref == (
        S4_DELL_THREE_CELL_RESEARCH_PROFILE_V3_REF
    )
    assert admission.admission_id.endswith("fresh-exact-admission-r9")
    assert admission.execution_mode.endswith(
        "validated_segment_union_capacity_r9"
    )
    assert admission.input_digest == decision["fresh_identity"]["input_digest"]
    assert canonical_digest(admission.digest_payload()) == prospective[
        "digest"
    ]
    assert PROSPECTIVE_ADMISSION.exists() is ISSUANCE.exists()
    assert (
        prospective["issued"],
        prospective["consumed"],
        prospective["execution_started"],
    ) == (False, False, False)


def test_profile_v3_capacity_fresh_proof_is_zero_call_and_read_only() -> None:
    decision = _load(DECISION)
    proof = decision["double_prepare_and_create_app"]
    freshness = decision["freshness_and_nonreuse"]

    assert proof["equal"] is True
    assert proof["clone_counts_before"] == proof["clone_counts_after"]
    assert proof["provider_callback_calls"] == 0
    assert proof["canonical_writes"] == 0
    assert (
        freshness["work_unit_absent"],
        freshness["attempt_absent"],
        freshness["research_run_absent"],
        freshness["R8_admission_consumed"],
        freshness["R8_rebound_or_reused"],
        freshness["R8_historical_failure_rewritten"],
    ) == (True, True, True, True, False, False)
    assert set(decision["hard_boundaries"].values()) == {0}


def test_profile_v3_capacity_proof_stops_before_R9_issuance() -> None:
    decision = _load(DECISION)

    assert decision["status"] == (
        "pass_zero_call_independent_profile_v3_capacity_fresh_proof_"
        "R9_admission_issuance_pending"
    )
    assert decision["stage_acceptance"]["RC_P36_065"] == (
        "fresh_proof_pass_R9_admission_issuance_pending"
    )
    assert decision["stage_acceptance"]["DELL_R2"] == "not_proven"
    assert decision["stage_acceptance"]["S4_T06"] == "not_entered"
    assert decision["next_action"] == (
        "S4-T05-DELL-R9-SPECIALIST-VALIDATED-SEGMENT-UNION-CAPACITY-"
        "FRESH-EXACT-ADMISSION-ISSUANCE-DECISION"
    )
