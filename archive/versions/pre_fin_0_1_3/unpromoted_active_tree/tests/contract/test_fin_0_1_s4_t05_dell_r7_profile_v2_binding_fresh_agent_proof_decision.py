from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
)
from scripts.releases.prepare_fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_fresh_proof import (
    DECISION,
    IMPLEMENTATION,
    PROSPECTIVE_ADMISSION,
    build_decision,
)
from sec_agent.canonical_runtime.models import canonical_digest


ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_"
    "fresh_exact_admission_issuance_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_independent_R7_proof_is_reproducible_before_issuance() -> None:
    decision = _load(DECISION)
    if ISSUANCE.exists():
        assert _load(ISSUANCE)["source_proof_decision_sha256"] == _sha256(
            DECISION
        )
    else:
        assert build_decision() == decision
    assert decision["proof_generator"]["independent_invocations"] == 2
    assert decision["proof_generator"]["independent_outputs_equal"] is True


def test_R7_uses_new_overlay_bound_input_and_identity() -> None:
    decision = _load(DECISION)
    implementation = _load(IMPLEMENTATION)
    identity = decision["fresh_identity"]
    reaudit = decision["implementation_reaudit"]

    assert reaudit["implementation_sha256"] == _sha256(IMPLEMENTATION)
    assert reaudit["effective_runtime_binding_digest"] == (
        implementation["implementation_contract"][
            "effective_runtime_binding_digest"
        ]
    )
    assert reaudit["overlay_digest"] == implementation[
        "implementation_contract"
    ]["overlay_digest"]
    assert identity["input_digest"] != decision["prospective_admission"][
        "source_R6_input_digest"
    ]
    assert (
        identity["work_unit_id"].startswith("wu_p02_5_")
        and identity["attempt_id"].startswith("attempt_fin01_")
        and identity["research_run_id"].startswith("research_run_fin01_")
    )


def test_R7_prospective_admission_is_exact_and_unissued() -> None:
    decision = _load(DECISION)
    prospective = decision["prospective_admission"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        prospective["payload"]
    )

    admission.assert_profile_admissible()
    assert admission.admission_id.endswith("fresh-exact-admission-r7")
    assert admission.execution_mode.endswith("profile_v2_binding_r7")
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


def test_R7_fresh_proof_is_zero_call_and_read_only() -> None:
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
        freshness["R6_admission_consumed"],
        freshness["R6_rebound_or_reused"],
    ) == (True, True, True, False, False)
    assert set(decision["hard_boundaries"].values()) == {0}


def test_R7_proof_advances_only_to_admission_issuance() -> None:
    decision = _load(DECISION)
    assert decision["status"] == (
        "pass_zero_call_independent_R7_profile_v2_binding_"
        "fresh_proof_admission_issuance_pending"
    )
    assert decision["stage_acceptance"]["RC_P36_063"] == (
        "fresh_proof_pass_admission_issuance_pending"
    )
    assert decision["stage_acceptance"]["DELL_R2"] == "not_proven"
    assert decision["stage_acceptance"]["S4_T06"] == "not_entered"
    assert decision["next_action"] == (
        "S4-T05-DELL-R7-PROFILE-V2-BINDING-FRESH-EXACT-ADMISSION-"
        "ISSUANCE-DECISION"
    )
