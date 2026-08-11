from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION_PATH = (
    ROOT
    / "configs/releases/fin_ia_0_1_s4_t05_dell_r7_post_verifier_untyped_valueerror_and_lost_failure_observability_zero_call_root_cause_disposition_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_disposition_binds_immutable_r7_failure_and_audited_code() -> None:
    decision = _load(DECISION_PATH)
    source = decision["source_failure"]
    audit = decision["zero_call_evidence_audit"]

    result_path = ROOT / source["result_ref"]
    assert result_path.is_file()
    assert _sha256(result_path) == source["result_sha256"]
    assert audit["bounded_executor_sha256"] == (
        "774ae41e51e64bbbf9edf10f54d0ad7bfe19723e377de03bed2086afba4ecd74"
    )
    assert audit["research_runtime_sha256"] == (
        "42512c3b8dfa6d0042d7f81d5175f863eff517ddf63a354c76f5a4aaa000e08d"
    )
    assert _sha256(ROOT / audit["exact_runner_ref"]) == (
        audit["exact_runner_sha256"]
    )

    assert source["gateway_completed_ok_stop_calls"] == 12
    assert source["runtime_failure_observation"] == {}
    assert source["raw_ValueError_message_persisted"] is False


def test_disposition_excludes_verifier_output_validation_but_not_guesses_throw_site() -> None:
    decision = _load(DECISION_PATH)
    audit = decision["zero_call_evidence_audit"]
    root_cause = decision["root_cause_disposition"]

    assert audit["verifier_provider_completion_proven"] is True
    assert audit["verifier_local_output_validation_failure_excluded"] is True
    assert audit["exact_throw_site_recoverable_from_immutable_evidence"] is False
    assert len(audit["remaining_reachable_bare_ValueError_families"]) >= 4
    assert root_cause["exact_R7_throw_site"] == (
        "not_recoverable_without_forbidden_guess_or_new_execution"
    )
    assert root_cause["model_instruction_noncompliance_established"] is False
    assert root_cause["verifier_schema_or_model_patch_selected"] is False


def test_disposition_selects_total_typed_post_provider_failure_envelope() -> None:
    decision = _load(DECISION_PATH)
    contract = decision["selected_minimum_implementation_contract"]
    ownership = contract["observation_ownership"]

    assert contract["contract_ref"] == (
        "fin01.bounded_agent.post_provider_failure_envelope:v1"
    )
    assert contract["typed_terminal_envelope_required_after_first_provider_receipt"]
    assert {
        "post_verifier_call_accounting",
        "execution_artifact_assembly",
        "adapter_output_conversion",
        "profile_result_validation",
        "profile_trace_recording",
    }.issubset(contract["single_lifecycle_phase_enum"])
    assert ownership["executor_or_shared_lifecycle_context_owns_accumulator"]
    assert ownership[
        "runtime_must_not_depend_on_optional_exception_attributes_as_the_only_receipt_source"
    ]
    assert contract["terminal_semantics"]["existing_hard_invariants_weakened"] is False


def test_disposition_requires_fault_injection_and_secret_safe_canonical_observation() -> None:
    decision = _load(DECISION_PATH)
    acceptance = decision["minimum_implementation_acceptance"]

    assert len(acceptance["deterministic_fault_injection_phases"]) == 5
    assert acceptance[
        "twelve_call_fault_fixture_preserves_12_usage_receipts_and_12_restricted_captures"
    ]
    assert acceptance["canonical_observed_counts_equal_accumulated_receipts"]
    assert acceptance[
        "raw_provider_text_private_reasoning_credentials_and_stack_trace_absent"
    ]
    assert acceptance["failure_creates_zero_business_Artifacts_and_zero_retry"]
    assert acceptance[
        "success_fixture_still_materializes_6_logical_nodes_12_calls_and_9_Artifacts"
    ]


def test_disposition_preserves_stop_boundary_and_requires_separate_implementation_authority() -> None:
    decision = _load(DECISION_PATH)
    authority = decision["authority"]
    counts = decision["observed_counts"]
    sequence = decision["R7_and_sequence_disposition"]

    assert authority["zero_call_audit_and_disposition_authorized"] is True
    assert authority["runtime_repair_authorized"] is False
    assert authority["new_admission_or_R7_relaunch_authorized"] is False
    assert all(value == 0 for value in counts.values())
    assert sequence["R7_second_execution_allowed"] is False
    assert sequence["paired_assessment"] == "not_authorized_after_failed_R7"
    assert sequence["S4_T06"] == "not_entered"
    assert decision["next_action"] == (
        "S4-T05-DELL-R7-TYPED-POST-PROVIDER-FAILURE-ENVELOPE-AND-CANONICAL-"
        "OBSERVABILITY-MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )
