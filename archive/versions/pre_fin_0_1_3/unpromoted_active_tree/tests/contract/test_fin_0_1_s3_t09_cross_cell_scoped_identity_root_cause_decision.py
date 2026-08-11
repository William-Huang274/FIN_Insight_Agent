from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = (
    ROOT
    / "configs/releases/fin_ia_0_1_s3_t09_"
    "cross_cell_scoped_identity_zero_call_root_cause_decision_v1_0.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_decision_locates_shared_identity_contract_as_earliest_owner() -> None:
    decision = _read(DECISION)
    review = decision["independent_root_cause_review"]

    assert review["confirmed"] is True
    assert review["provider_fault_confirmed"] is False
    assert review["project_owned_contract_mismatch_confirmed"] is True
    assert review["earliest_owner"] == "shared_S3_claim_and_WWC_identity_scope_contract"
    assert review["observed_live_collision"] == {
        "identity_kind": "what_would_change",
        "local_ids": ["wwc-001", "wwc-002", "wwc-003"],
        "program_cell_ids": [
            "demand_and_revenue_conversion",
            "value_and_profit_capture",
        ],
    }
    assert review["same_shape_unobserved_risk"]["identity_kind"] == "claim"
    assert review["same_shape_unobserved_risk"]["confirmed_by_code_path"] is True


def test_selected_contract_uses_typed_cell_scope_without_rewriting_local_ids() -> None:
    contract = _read(DECISION)["selected_identity_contract"]

    assert contract["contract_ref"] == "fin01.s3.cell_scoped_research_identity:v1"
    assert contract["authoritative_fields"] == [
        "identity_kind",
        "program_cell_id",
        "local_id",
    ]
    assert contract["runtime_key"] == contract["authoritative_fields"]
    assert contract["identity_kinds"] == ["claim", "what_would_change"]
    assert contract["provider_local_id_preserved"] is True
    assert contract["provider_local_id_mutated_prefixed_or_rewritten"] is False
    assert contract["raw_local_id_only_cross_cell_join_allowed"] is False
    assert contract["same_local_id_in_different_cells_allowed"] is True
    assert contract["same_local_id_in_same_cell_allowed"] is False
    assert contract["duplicate_scoped_ref_allowed"] is False
    assert contract["prompt_schema_and_local_validator_source"] == (
        "one shared typed identity contract"
    )
    assert contract["versioning"]["specialist_transport_v8_required_only_for_identity_scope"] is False


def test_safe_telemetry_and_compatibility_are_fail_closed() -> None:
    decision = _read(DECISION)
    telemetry = decision["safe_failure_telemetry_contract"]
    compatibility = decision["compatibility_contract"]

    assert telemetry["failure_family"] == "cross_cell_scoped_identity"
    assert set(telemetry["allowed_fields"]) == {
        "identity_kind",
        "failure_subtype",
        "failing_item_count",
    }
    assert {
        telemetry["raw_local_ids_allowed"],
        telemetry["program_cell_ids_allowed"],
        telemetry["scoped_ref_digests_allowed"],
        telemetry["item_indexes_allowed"],
        telemetry["answer_text_or_private_reasoning_allowed"],
    } == {False}
    assert compatibility["historical_failed_run_or_provider_answer_rewritten"] is False
    assert compatibility["silent_prefix_remap_normalize_trim_drop_or_repair_allowed"] is False
    assert compatibility["historical_run_replay_preserves_original_failure"] is True
    assert compatibility["consumed_r2_admission_or_identity_reuse_allowed"] is False


def test_decision_is_zero_call_and_advances_only_to_implementation() -> None:
    decision = _read(DECISION)
    counts = decision["observed_counts"]
    authority = decision["authority"]

    assert set(counts.values()) == {0}
    assert authority["zero_call_root_cause_decision_authorized"] is True
    assert authority["runtime_code_prompt_schema_or_validator_implementation_authorized"] is False
    assert authority["admission_issuance_or_consumption_authorized"] is False
    assert authority[
        "model_provider_network_source_or_external_tool_call_authorized"
    ] is False
    assert decision["next_action"].endswith("ZERO-CALL-IMPLEMENTATION")
    assert decision["stage_decision"]["S3_T09"].startswith("blocked_")


def test_program_backlog_records_decision_and_preserves_stop_line() -> None:
    next_action = _read(BACKLOG)["next_action"]

    assert next_action["item_id"]
    assert next_action["cross_cell_scoped_identity_root_cause_decision_authorized"] is True
    assert next_action["cross_cell_scoped_identity_root_cause_decision_status"].startswith(
        "pass_shared_typed_cell_scoped"
    )
    assert next_action[
        "cross_cell_scoped_identity_zero_call_implementation_authorized"
    ] is True
    assert next_action["replacement_admission_or_execution_authorized"] is False
    assert next_action["agent_rerun_authorized"] is False
    assert next_action["owner_review_or_T10_authorized"] is False
