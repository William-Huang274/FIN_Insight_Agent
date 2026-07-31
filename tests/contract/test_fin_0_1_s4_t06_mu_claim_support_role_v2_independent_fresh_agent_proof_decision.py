from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_V2_REF,
)
from scripts.releases.prepare_fin_ia_0_1_s4_t06_mu_claim_support_role_v2_fresh_proof import (
    DECISION,
    IMPLEMENTATION,
    NEXT_ACTION,
    PROSPECTIVE_ADMISSION,
    S4T06ClaimSupportRoleV2FreshProofError,
    build_decision,
)
from sec_agent.canonical_runtime.models import canonical_digest


EXECUTION_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_claim_support_role_v2_r7_"
    "exact_live_execution_failure_result_v1_0.json"
)


def _lifecycle_aware_decision() -> dict:
    if EXECUTION_RESULT.exists():
        return json.loads(DECISION.read_text(encoding="utf-8"))
    return build_decision(
        require_prospective_absent=not PROSPECTIVE_ADMISSION.exists()
    )


def test_v2_fresh_proof_is_independent_zero_call_and_target_read_only() -> None:
    result = _lifecycle_aware_decision()
    assert result["status"] == (
        "pass_zero_call_double_disposable_runtime_v2_fresh_proof_"
        "admission_authority_pending"
    )
    assert result["proof_generator"]["independent_invocations"] == 2
    assert result["proof_generator"]["independent_outputs_equal"] is True
    assert result["double_prepare"]["equal"] is True
    assert result["double_prepare"]["clone_execution_counts_before"] == (
        result["double_prepare"]["clone_execution_counts_after"]
    )
    assert result["target_read_only_audit"]["target_state_unchanged"] is True
    assert set(result["hard_boundaries"].values()) == {0}
    assert result["independent_fixture_reproof"][
        "compiled_contract_ref"
    ] == S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_V2_REF
    assert result["independent_fixture_reproof"][
        "three_case_positive_nodes_callbacks_captures_artifacts"
    ] == {
        "DELL": [6, 12, 12, 9],
        "MU": [6, 12, 12, 9],
        "NVDA": [6, 12, 12, 9],
    }


def test_v2_prospective_R7_digest_is_stable_across_lifecycle() -> None:
    result = _lifecycle_aware_decision()
    prospective = result["prospective_R7_admission"]
    assert canonical_digest(prospective["payload"]) == prospective["digest"]
    assert prospective["payload"][
        "judgment_atom_compiled_contract_ref"
    ] == S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_V2_REF
    assert prospective["compiled_contract_v2_bound"] is True
    assert prospective["issued"] is False
    assert prospective["consumed"] is False
    assert prospective["execution_started"] is False
    if PROSPECTIVE_ADMISSION.exists():
        assert json.loads(
            PROSPECTIVE_ADMISSION.read_text(encoding="utf-8")
        ) == prospective["payload"]
    assert result["next_action"] == NEXT_ACTION
    assert result["next_action_authorized"] is False


def test_v2_fresh_proof_fails_closed_on_implementation_binding_drift(
    tmp_path: Path,
) -> None:
    implementation = json.loads(IMPLEMENTATION.read_text(encoding="utf-8"))
    implementation["runtime_changes"]["compiled_contract"]["sha256"] = "0" * 64
    mutated = tmp_path / "mutated-implementation.json"
    mutated.write_text(
        json.dumps(implementation, ensure_ascii=False),
        encoding="utf-8",
    )
    from scripts.releases.prepare_fin_ia_0_1_s4_t06_mu_claim_support_role_v2_fresh_proof import (
        prepare,
    )

    with pytest.raises(
        S4T06ClaimSupportRoleV2FreshProofError,
        match="implementation_code_binding_drift",
    ):
        prepare(
            implementation_path=mutated,
            require_prospective_absent=False,
        )


def test_persisted_v2_fresh_proof_matches_current_generator() -> None:
    actual = json.loads(DECISION.read_text(encoding="utf-8"))
    if EXECUTION_RESULT.exists():
        execution = json.loads(EXECUTION_RESULT.read_text(encoding="utf-8"))
        assert execution["source_authority"]["admission_digest"] == actual[
            "prospective_R7_admission"
        ]["digest"]
        assert execution["execution_identity"]["work_unit_id"] == actual[
            "fresh_identity"
        ]["work_unit_id"]
    else:
        expected = build_decision(
            require_prospective_absent=not PROSPECTIVE_ADMISSION.exists()
        )
        assert actual == expected
