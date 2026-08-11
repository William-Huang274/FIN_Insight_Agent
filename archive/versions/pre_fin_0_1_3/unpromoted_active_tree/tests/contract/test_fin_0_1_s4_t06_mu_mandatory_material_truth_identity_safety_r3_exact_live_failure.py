from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t06_mu_mandatory_material_truth_identity_safety_"
    "closure_r3_exact_live_execution_failure_result_v1_0.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_r3_failure_binds_immutable_runtime_and_supervision_evidence() -> None:
    result = _load(RESULT)
    sources = result["source_bindings"]
    for ref_key, digest_key in (
        ("proof_ref", "proof_sha256"),
        ("issuance_ref", "issuance_sha256"),
        ("admission_ref", "admission_sha256"),
        ("runtime_result_ref", "runtime_result_sha256"),
        ("supervision_launch_ref", "supervision_launch_sha256"),
        ("supervision_exit_ref", "supervision_exit_sha256"),
    ):
        assert _sha256(ROOT / sources[ref_key]) == sources[digest_key]


def test_r3_terminal_truth_and_first_failure_are_content_free() -> None:
    result = _load(RESULT)
    assert list(
        result["canonical_terminal_truth"][key]
        for key in (
            "work_unit_state",
            "attempt_state",
            "research_run_state",
        )
    ) == ["failed", "failed", "failed"]
    assert result["canonical_terminal_truth"]["artifact_count"] == 0
    execution = result["provider_execution"]
    assert [
        execution["semantic_model_calls"],
        execution["provider_calls"],
        execution["network_calls"],
    ] == [1, 1, 1]
    assert execution["finish_reason"] == "stop"
    assert execution["retry_count"] == 0
    failure = result["first_credible_failure"]
    assert failure["failure_code"] == (
        "s4_case_delivery_identity_provider_narrative_invalid"
    )
    assert failure["failure_subtype"] == (
        "provider_authored_case_entity_token"
    )
    assert failure["raw_text_persisted_in_result"] is False


def test_r3_correct_local_identity_only_and_sequence_stops() -> None:
    result = _load(RESULT)
    audit = result["restricted_content_free_reaudit"]
    assert audit["current_case_ticker_occurrences"] == 4
    assert set(audit["nonlocal_known_ticker_occurrences"].values()) == {0}
    sequence = result["sequence_disposition"]
    assert sequence["paired_L1_to_L4_assessment"] == (
        "not_eligible_not_performed"
    )
    assert sequence["owner_acceptance"] == "not_eligible_not_performed"
    assert sequence["S4_T07"] == "not_entered"
    assert result["stop_rule"]["automatic_R4_or_micro_patch_performed"] is False
