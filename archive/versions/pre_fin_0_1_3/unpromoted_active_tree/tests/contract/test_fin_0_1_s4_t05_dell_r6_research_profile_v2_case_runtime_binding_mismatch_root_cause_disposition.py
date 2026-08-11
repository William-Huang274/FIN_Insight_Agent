from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
R7_BINDING_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_versioned_"
    "case_runtime_binding_and_create_app_preflight_minimum_zero_call_"
    "implementation_v1_0.json"
)
DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r6_research_profile_v2_"
    "case_runtime_binding_mismatch_zero_call_root_cause_disposition_v1_0.json"
)
FAILURE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_specialist_wwc_judgment_"
    "atom_r6_exact_live_execution_pre_admission_failure_result_v1_0.json"
)
CASE_PACK = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t02_dell_oem_exact_case_pack_v1_0.json"
)
R6_ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_specialist_wwc_judgment_"
    "atom_fresh_exact_admission_r6.json"
)
PROGRAM = ROOT / (
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
DETAILED = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
NEXT_ACTION = (
    "S4-T05-DELL-R7-PROFILE-V2-VERSIONED-CASE-RUNTIME-BINDING-AND-"
    "CREATE-APP-PREFLIGHT-MINIMUM-ZERO-CALL-IMPLEMENTATION"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_decision_binds_failure_case_pack_and_r6_without_calls() -> None:
    decision = _load(DECISION)
    source = decision["source_failure"]
    audit = decision["zero_call_artifact_and_code_audit"]
    authority = decision["authority"]

    assert source["result_sha256"] == _sha256(FAILURE)
    assert audit["DELL_case_pack_sha256"] == _sha256(CASE_PACK)
    assert audit["R6_admission_sha256"] == _sha256(R6_ADMISSION)
    assert source["failure_code"] == (
        "s4_admission_research_profile_binding_mismatch"
    )
    assert source["admission_issued_consumed_canonical_execution"] == [
        True,
        False,
        False,
    ]
    assert authority["runtime_binding_overlay_or_preflight_implementation_authorized"] is False
    assert authority["R6_admission_mutation_consumption_relaunch_or_reclassification_authorized"] is False
    assert all(value == 0 for value in decision["observed_counts"].values())


def test_root_cause_is_post_prepare_profile_change_and_not_model_fault() -> None:
    decision = _load(DECISION)
    disposition = decision["root_cause_disposition"]
    audit = decision["zero_call_artifact_and_code_audit"]

    assert audit["DELL_case_pack_frozen_research_profile_target_ref"].endswith(
        ":v1"
    )
    assert decision["source_failure"][
        "exact_admission_research_profile_ref"
    ].endswith(":v2")
    assert "after the S4 exact input had already been compiled" in disposition[
        "earliest_project_owned_faulty_artifact"
    ]
    assert disposition["classification"] == (
        "L1_exact_runtime_binding_integrity_fail_closed"
    )
    assert disposition["model_or_provider_fault"] is False
    assert disposition["runtime_guard_should_be_removed_or_weakened"] is False


def test_selected_contract_preserves_base_binding_and_adds_versioned_overlay() -> None:
    contract = _load(DECISION)["selected_minimum_implementation_contract"]
    base = contract["base_binding"]
    overlay = contract["versioned_profile_overlay"]
    effective = contract["effective_exact_binding"]

    assert contract["contract_ref"] == (
        "fin01.s4.case_runtime_research_profile_overlay:v1"
    )
    assert base["base_research_profile_ref"].endswith(":v1")
    assert base["historical_default_loader_behavior_preserved"] is True
    assert overlay["requested_research_profile_ref_source"] == "exact admission"
    assert overlay["allowed_profile_source"] == (
        "registered BoundedResearchProfile only"
    )
    assert "base_runtime_binding_digest" in overlay["lineage_fields"]
    assert "research_profile_contract_digest" in overlay["lineage_fields"]
    assert overlay["base_binding_or_case_pack_mutation_allowed"] is False
    assert effective["research_profile_ref"].endswith(":v2")
    assert effective["recompute_all_seven_consumer_injection_digests"] is True
    assert effective[
        "exact_input_admission_runtime_and_executor_must_share_same_effective_binding"
    ] is True
    assert effective["silent_reuse_of_R6_input_digest_or_identity"] is False


def test_shared_resolver_and_create_app_preflight_close_the_coverage_gap() -> None:
    contract = _load(DECISION)["selected_minimum_implementation_contract"]
    resolver = contract["shared_resolver"]
    preflight = contract["create_app_or_equivalent_preflight"]

    assert "both runner preflight and Fin01ResearchRuntime" in resolver[
        "required_functional_owner"
    ]
    assert resolver[
        "runner_preflight_must_resolve_before_credential_or_process_launch"
    ] is True
    assert resolver["application_runtime_must_reuse_same_resolver"] is True
    assert resolver[
        "executor_input_binding_and_admission_profile_equality_remains_fail_closed"
    ] is True
    assert preflight["disposable_clone_only"] is True
    assert preflight["provider_callback_forbidden"] is True
    assert preflight["canonical_write_forbidden"] is True
    assert preflight["must_fail_before_launch_on_profile_binding_drift"] is True
    assert preflight[
        "must_pass_for_one_coherent_effective_v2_binding"
    ] is True


def test_r6_is_preserved_but_cannot_be_rebound_or_relaunched() -> None:
    decision = _load(DECISION)
    r6 = decision["R6_and_future_admission_disposition"]
    rejected = {
        row["option"]: row["decision"]
        for row in decision["rejected_and_deferred_alternatives"]
    }

    assert r6["R6_status"] == (
        "issued_unconsumed_invalid_for_relaunch_due_to_internal_exact_"
        "binding_inconsistency"
    )
    assert r6["R6_admission_file_preserved_immutable"] is True
    assert r6["R6_consumption_relaunch_or_in_place_rebinding_allowed"] is False
    assert r6["R6_identity_reuse_allowed"] is False
    assert r6["future_admission_label"] == "R7_or_later_fresh_exact_admission"
    assert r6["future_admission_requires_new_input_preparation_and_digest"] is True
    assert rejected["remove_or_relax_the_runtime_profile_equality_guard"] == (
        "rejected"
    )
    assert rejected["reuse_R6_identity_and_relaunch_after_local_patch"] == (
        "rejected"
    )


def test_project_state_advances_only_to_zero_call_implementation() -> None:
    decision = _load(DECISION)
    program = _load(PROGRAM)
    detailed = _load(DETAILED)
    t05 = next(
        row for row in detailed["tasks"] if row["item_id"] == "S4-T05"
    )

    assert decision["next_action"] == NEXT_ACTION
    assert decision["stage_acceptance"]["RC_P36_063"].endswith(
        "implementation_pending"
    )
    assert decision["stage_acceptance"]["DELL_R2"] == "not_proven"
    assert decision["stage_acceptance"]["S4_T06"] == "not_entered"
    assert decision["sequence_boundary"]["implementation_in_this_decision"] is False
    current_next = _load(
        ROOT / "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_exact_live_execution_failure_result_v1_0.json"
    )["next_action"]
    assert program["next_action"]["item_id"] == current_next
    assert detailed["current_next_action"] == current_next
    assert program["next_action"]["current_S4_T05_RC_P36_063_status"] == (
        "R7_profile_binding_path_reached_not_terminal_failure"
    )
    assert t05["RC_P36_063_status"] == (
        "R7_profile_binding_path_reached_not_terminal_failure"
    )
    assert t05["paired_assessment_performed"] is False
