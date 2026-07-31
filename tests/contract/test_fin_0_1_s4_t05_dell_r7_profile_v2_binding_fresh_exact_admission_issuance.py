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
    PROSPECTIVE_ADMISSION as ADMISSION,
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


def test_R7_admission_is_exact_frozen_payload() -> None:
    proof = _load(DECISION)
    issuance = _load(ISSUANCE)
    payload = _load(ADMISSION)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)

    admission.assert_profile_admissible()
    assert payload == proof["prospective_admission"]["payload"]
    assert canonical_digest(admission.digest_payload()) == proof[
        "prospective_admission"
    ]["digest"]
    assert proof["prospective_admission"]["digest"] == issuance[
        "issued_admission"
    ]["admission_digest"]
    assert issuance["source_proof_decision_sha256"] == _sha256(DECISION)


def test_R7_issuance_is_unconsumed_and_zero_call() -> None:
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


def test_R7_issuance_advances_only_to_execution_authority() -> None:
    issuance = _load(ISSUANCE)
    binding = issuance["exact_binding"]
    proof_identity = _load(DECISION)["fresh_identity"]

    assert binding["input_digest"] == proof_identity["input_digest"]
    assert binding["preparation_digest"] == proof_identity[
        "preparation_digest"
    ]
    assert binding["predicted_research_run_id"] == proof_identity[
        "research_run_id"
    ]
    assert issuance["execution_envelope"]["transport_retry_count"] == 0
    assert issuance["next_action"] == (
        "S4-T05-DELL-R7-PROFILE-V2-BINDING-EXACT-LIVE-EXECUTION-AND-"
        "SUCCESS-ONLY-PAIRED-ASSESSMENT-AUTHORITY-DECISION"
    )
