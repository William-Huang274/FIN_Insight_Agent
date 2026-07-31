from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEEPSEEK_MAINLINE = (
    "S4-T06-MU-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
    "CLASSIFIER-R5-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT"
)
DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_entry_shared_runtime_blocker_"
    "disposition_v1_0.json"
)
PROGRAM_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
DETAILED_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
IMPLEMENTATION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_shared_runtime_blocker_"
    "minimum_zero_call_implementation_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_disposition_binds_R11_failure_and_historical_transport_evidence() -> None:
    decision = _load(DECISION)
    source = decision["source_evidence"]

    for ref_key, sha_key in (
        ("global_audit_ref", "global_audit_sha256"),
        ("R11_failure_result_ref", "R11_failure_result_sha256"),
        (
            "historical_deepseek_strict_transport_pivot_ref",
            "historical_deepseek_strict_transport_pivot_sha256",
        ),
        (
            "provider_neutral_native_json_schema_adapter_ref",
            "provider_neutral_native_json_schema_adapter_sha256",
        ),
        (
            "historical_openai_native_route_result_ref",
            "historical_openai_native_route_result_sha256",
        ),
    ):
        assert _sha256(ROOT / source[ref_key]) == source[sha_key]
    assert source["R11_primary_failure_code"] == (
        "s4_case_numeric_authority_provider_narrative_invalid"
    )
    assert source["R11_secondary_failure_code"] == (
        "research_run_failure_observation_not_secret_safe"
    )
    assert source["historical_deepseek_beta_strict_attempts"] == 2
    assert source["historical_deepseek_beta_strict_closed_outputs"] == 0


def test_program_disposition_closes_paid_T05_series_without_R12_or_H01() -> None:
    decision = _load(DECISION)
    disposition = decision["program_disposition"]
    authority = decision["authority"]

    assert disposition["decision_label"] == "pivot"
    assert disposition["T05_paid_execution_series_closed"] is True
    assert disposition["R12_or_relabelled_same_contract_rerun"] == "forbidden"
    assert disposition["temporary_H01_label_retracted"] is True
    assert disposition["temporary_H01_label_was_executed"] is False
    assert disposition["new_phase_or_task_family_created"] is False
    assert disposition["scope_selected"] == (
        "S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER"
    )
    assert disposition["scope_is_T06_entry_readiness_work_not_T06_case_execution"]
    assert disposition["S4_T06"] == "not_entered_until_entry_blocker_is_cleared"
    assert authority["runtime_implementation_authorized"] is False
    assert authority["model_provider_or_network_call_authorized"] is False
    assert authority["R12_authorized"] is False
    assert all(
        value == 0
        for value in decision["observed_counts_this_decision"].values()
    )


def test_truth_kernel_has_only_aliases_and_finite_enums() -> None:
    decision = _load(DECISION)
    kernel = decision["selected_contracts"]["strict_truth_kernel"]
    routing = decision["selected_contracts"]["provider_capability_routing"]

    assert kernel["contract_ref"] == (
        "fin01.s4.strict_truth_kernel.numeric_judgment_selection:v1"
    )
    assert "arbitrary_free_text" in kernel["provider_wire_forbidden_values"]
    assert "provider_authored_material_numeric_value" in (
        kernel["provider_wire_forbidden_values"]
    )
    assert kernel[
        "all_string_values_must_be_schema_enums_or_schema_patterns_bound_to_request_local_alias_space"
    ]
    assert kernel["model_verifier_is_truth_owner"] is False
    assert kernel["independent_local_L1_recomputation_required"] is True
    assert routing["required_for_truth_kernel_nodes"] is True
    assert routing["deepseek_json_object_truth_kernel_binding"] == "rejected"
    assert routing["first_binding_candidate"] == (
        "openai_responses_native_json_schema"
    )
    assert routing["exact_provider_model_and_credential_binding"] == (
        "deferred_to_separate_availability_and_authority_gate"
    )


def test_atomic_terminal_core_cannot_be_vetoed_by_optional_telemetry() -> None:
    decision = _load(DECISION)
    terminal = decision["selected_contracts"][
        "atomic_failure_terminalization"
    ]
    acceptance = decision["minimum_zero_call_implementation_acceptance"]

    assert terminal["contract_ref"] == (
        "fin01.bounded_agent.atomic_failure_terminal_core_and_"
        "registered_observation:v1"
    )
    assert terminal["terminal_core_and_state_transition_are_atomic"] is True
    assert terminal[
        "optional_failure_observation_extension_may_veto_terminal_state"
    ] is False
    assert terminal["raw_rejected_extension_persisted"] is False
    assert terminal["adding_one_facade_allowlist_branch_only"] == (
        "rejected_as_insufficient"
    )
    assert acceptance[
        "unknown_extra_or_secret_like_failure_extension_terminalizes_failed_failed_failed_without_persisting_the_extension"
    ]
    assert acceptance[
        "usage_receipts_restricted_captures_and_completed_node_receipts_remain_core_owned_and_are_not_lost_by_extension_rejection"
    ]


def test_rejected_options_prevent_prompt_retry_and_immediate_provider_switch() -> None:
    decision = _load(DECISION)
    rejected = {
        row["option"]: row["decision"]
        for row in decision["rejected_options"]
    }

    assert rejected["increase_prompt_emphasis_and_retry_R12"] == "rejected"
    assert rejected[
        "third_deepseek_beta_strict_tool_full_chain_attempt"
    ] == "rejected"
    assert rejected[
        "add_case_numeric_authority_to_the_facade_allowlist_only"
    ] == "rejected_as_incomplete"
    assert rejected[
        "immediate_openai_provider_switch_and_full_chain"
    ] == "rejected_without_separate_gate"
    assert rejected[
        "enter_MU_T06_while_DELL_truth_kernel_is_unqualified"
    ] == "rejected"


def test_anti_infinite_repair_ceiling_is_machine_enforced() -> None:
    decision = _load(DECISION)
    guard = decision["anti_infinite_repair_governance"]

    assert guard["maximum_zero_call_implementation_bundles_under_this_entry_gate"] == 1
    assert guard["automatic_follow_on_repair_bundles"] == 0
    assert guard["automatic_prompt_field_or_allowlist_patch_iterations"] == 0
    assert guard["maximum_single_node_provider_canaries_after_zero_call_acceptance"] == 1
    assert guard["provider_canary_automatic_retry_or_provider_hopping"] is False
    assert guard["DELL_R12_or_equivalent_full_chain_reproof"] == "forbidden"
    assert guard["T06_MU_exact_execution_is_part_of_this_gate"] is False


def test_backlogs_preserve_disposition_and_advance_after_the_one_bundle() -> None:
    decision = _load(DECISION)
    implementation = _load(IMPLEMENTATION)
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(DETAILED_BACKLOG)
    task = next(
        row for row in detailed["tasks"] if row["item_id"] == "S4-T05"
    )

    assert decision["next_action"] == (
        "S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER-"
        "MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )
    current = program["next_action"]["item_id"]
    assert current in {
        implementation["next_action"],
        "S4-T06-ENTRY-OPENAI-HTTP-429-RATE-OR-QUOTA-"
        "PROGRAM-DISPOSITION-DECISION",
        "S4-T06-ENTRY-SUB2API-PROVIDER-ROUTE-AND-CAPABILITY-"
        "CONTRACT-REBASELINE-DECISION",
        "S4-T06-ENTRY-SUB2API-SECURE-TRANSPORT-ENDPOINT-CONFIRMATION",
        "S4-T06-ENTRY-SUB2API-PUBLIC-NON-SENSITIVE-DIAGNOSTIC-"
        "CANARY-AUTHORITY-DECISION",
        "S4-T06-ENTRY-SUB2API-PUBLIC-NON-SENSITIVE-DIAGNOSTIC-"
        "CANARY-MINIMUM-ZERO-CALL-IMPLEMENTATION-AND-PREFLIGHT",
            "S4-T06-ENTRY-SUB2API-PUBLIC-NON-SENSITIVE-DIAGNOSTIC-"
            "CANARY-POST-RESULT-PROGRAM-DISPOSITION",
            DEEPSEEK_MAINLINE,
            "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
            "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION",
        }
    assert detailed["current_next_action"] == current
    assert task["S4_T06_entry_shared_runtime_blocker_disposition_ref"] == (
        DECISION.relative_to(ROOT).as_posix()
    )
    assert task["S4_T06_entry_shared_runtime_blocker_disposition_sha256"] == _sha256(DECISION)
    assert task["R12_authorized"] is False
    assert task["R12_launched"] is False
    assert task["S4_H01_label_status"] == "retracted_unexecuted"
    assert task["S4_T06_entry_blocker_status"] == (
        "minimum_zero_call_implementation_fixture_proven_one_bundle_"
        "consumed_engineering_proof_and_provider_capability_binding_"
        "pending_T06_not_entered"
    )
    assert task[
        "S4_T06_entry_shared_runtime_blocker_implementation_ref"
    ] == IMPLEMENTATION.relative_to(ROOT).as_posix()
    assert task[
        "S4_T06_entry_shared_runtime_blocker_implementation_sha256"
    ] == _sha256(IMPLEMENTATION)
    assert task[
        "S4_T06_entry_zero_call_implementation_bundles_consumed"
    ] == 1
    assert task["S4_T06_entry_maximum_zero_call_implementation_bundles"] == 1
    assert task["S4_T06_entry_automatic_follow_on_repairs"] == 0
