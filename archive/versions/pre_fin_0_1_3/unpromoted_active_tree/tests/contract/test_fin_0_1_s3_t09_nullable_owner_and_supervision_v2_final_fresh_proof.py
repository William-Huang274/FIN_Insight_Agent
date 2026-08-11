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
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_nullable_owner_and_supervision_v2_final_fresh_proof import (  # noqa: E402
    CODE_BINDING_PATHS,
    DECISION_STATUS,
    HOST_CAPABILITY_RECEIPT,
    NEXT_ACTION,
    prepare,
)
from scripts.releases.supervise_fin_ia_0_1_s3_t09_exact_live_execution import (  # noqa: E402
    SUPERVISION_CONTRACT_REF,
    _validate_host_capability_receipt,
)


DECISION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s3_t09_nullable_owner_and_supervision_v2_final_"
    "fresh_agent_proof_decision_v1_0.json"
)
FINAL_LIVE_RESULT = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s3_t09_nullable_owner_and_supervision_v2_final_"
    "exact_live_execution_result_v1_0.json"
)


def _load() -> dict:
    return json.loads(DECISION.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_final_v2_proof_freezes_fresh_identity_and_zero_call_boundary() -> None:
    proof = _load()
    identity = proof["identity"]
    prospective = proof["prospective_admission"]

    assert proof["status"] == DECISION_STATUS
    assert set(proof["observed_counts"].values()) == {0}
    assert proof["double_prepare"]["equal"] is True
    assert proof["freshness_and_nonreuse"][
        "distinct_from_all_prior_agent_and_baseline_runs"
    ] is True
    assert identity["work_unit_id"] == (
        "wu_p02_5_870d16faa31ee622a270a581"
    )
    assert identity["attempt_id"] == (
        "attempt_fin01_747d6459f09956ced4a50f2e"
    )
    assert identity["research_run_id"] == (
        "research_run_fin01_6594b12567cdebecd441d31d"
    )
    assert prospective["digest"] == (
        "854a29f299c1d86f1cb86d75f97b0f344f13f9275a04298120789e44d9734f31"
    )
    assert prospective["admission_issued"] is False
    assert prospective["admission_consumed"] is False
    assert prospective["execution_started"] is False
    assert proof["next_action"] == NEXT_ACTION


def test_final_v2_proof_binds_current_code_and_host_capability() -> None:
    proof = _load()
    assert set(proof["exact_code_bindings"]) == {
        path.as_posix() for path in CODE_BINDING_PATHS
    }
    superseded_after_historical_proof = {
        "apps/workbench/backend/application/bounded_agent_executor.py",
    }
    for relative, digest in proof["exact_code_bindings"].items():
        if relative in superseded_after_historical_proof:
            assert _sha256(ROOT / relative) != digest
        else:
            assert _sha256(ROOT / relative) == digest

    nullable = proof["nullable_owner_state_machine_v2_acceptance_contract"]
    supervision = proof["supervision_v2_acceptance_contract"]
    capability, capability_digest = _validate_host_capability_receipt(
        HOST_CAPABILITY_RECEIPT
    )
    assert nullable["contract_ref"] == (
        S3_OWNER_GRADE_VERIFIER_STATE_MACHINE_REF
    )
    assert nullable["pass_repair_owner"] == "JSON_null"
    assert nullable["literal_string_none_allowed"] is False
    assert nullable["closed_negative_fixture_count_at_least"] >= 10
    assert supervision["contract_ref"] == SUPERVISION_CONTRACT_REF
    assert supervision["launch_path"] == (
        "direct_actual_runner_no_intermediate_wrapper"
    )
    assert supervision["host_capability_receipt_sha256"] == capability_digest
    assert capability["status"] == (
        "pass_direct_runner_survived_launcher_and_self_finalized"
    )


def test_final_v2_proof_is_reproducible_before_consumption_or_bound_afterward() -> None:
    frozen = _load()
    if FINAL_LIVE_RESULT.exists():
        live = json.loads(FINAL_LIVE_RESULT.read_text(encoding="utf-8"))
        assert live["identity"]["work_unit_id"] == frozen["identity"][
            "work_unit_id"
        ]
        assert live["identity"]["attempt_id"] == frozen["identity"][
            "attempt_id"
        ]
        assert live["identity"]["research_run_id"] == frozen["identity"][
            "research_run_id"
        ]
        assert live["identity"]["admission_digest"] == frozen[
            "prospective_admission"
        ]["digest"]
        assert live["identity"]["admission_consumed"] is True
        return
    regenerated = prepare()
    for key in (
        "identity",
        "double_prepare",
        "prospective_admission",
        "target_read_only_audit",
        "exact_code_bindings",
        "nullable_owner_state_machine_v2_acceptance_contract",
        "supervision_v2_acceptance_contract",
        "budget_and_stop_contract",
        "artifact_acceptance_contract",
    ):
        assert regenerated[key] == frozen[key]
    assert set(regenerated["observed_counts"].values()) == {0}


def test_final_v2_proof_preserves_product_acceptance_and_stop_rules() -> None:
    proof = _load()
    artifact = proof["artifact_acceptance_contract"]
    governance = proof["experiment_governance"]

    assert artifact["success_requires_logical_nodes"] == 6
    assert artifact["success_requires_provider_calls"] == 12
    assert artifact["success_requires_artifact_families"] == 9
    assert artifact["success_requires_terminal_states"] == [
        "succeeded",
        "succeeded",
        "succeeded",
    ]
    assert artifact["nullable_owner_state_machine_v2_must_pass"] is True
    assert artifact["supervision_v2_contract_must_pass"] is True
    assert governance[
        "automatic_retry_fallback_patch_replay_relaunch_or_rerun_authorized"
    ] is False
    assert governance[
        "current_user_authorizes_ordered_issuance_execution_and_acceptance"
    ] is True
