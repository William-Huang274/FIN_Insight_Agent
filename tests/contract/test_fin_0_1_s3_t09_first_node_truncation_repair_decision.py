from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = (
    ROOT
    / "configs/releases/fin_ia_0_1_s3_t09_first_node_truncation_repair_decision_v1_0.json"
)
RESULT = (
    ROOT
    / "configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution_result_v1_0.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_decision_is_grounded_in_the_consumed_terminal_failure() -> None:
    decision = _load(DECISION)
    result = _load(RESULT)
    source = decision["source_failure"]
    assert result["status"] == "terminal_failed_admission_consumed_no_retry"
    assert source["failed_stage"] == result["provider_execution"]["failed_stage"]
    assert source["input_tokens"] == result["provider_execution"]["input_tokens"] == 8973
    assert source["output_tokens"] == source["configured_output_cap"] == 1400
    assert source["finish_reason"] == "length"
    assert source["failure_code"] == "s3_bounded_node_output_truncated"


def test_selected_repair_preserves_research_inputs_and_removes_only_audit_duplication() -> None:
    decision = _load(DECISION)
    selected = decision["selected_repair_contract"]
    assert selected["canonical_input_and_digest_change_allowed"] is False
    assert selected["specialist_model_view_contract_ref"] == (
        "fin01.s3.specialist_model_view:v1"
    )
    retained = " ".join(selected["model_view_must_retain"]).lower()
    for required in ("T02", "T03", "T04", "T05", "Evidence", "Numeric", "Graph"):
        assert required.lower() in retained
    excluded = " ".join(selected["model_view_must_exclude"])
    assert "tool_selection_plan" in excluded
    assert "audit_only_ids_digests" in excluded
    assert selected["auditability"] == {
        "full_canonical_input_remains_persisted_and_digest_bound": True,
        "model_view_is_deterministically_derived": True,
        "node_receipt_must_record_model_view_contract_ref_and_digest": True,
        "output_is_still_validated_against_full_original_cell_authority": True,
    }


def test_decision_rejects_cap_only_and_closes_output_cardinality_and_cost() -> None:
    decision = _load(DECISION)
    options = {row["option"]: row["decision"] for row in decision["option_comparison"]}
    assert options == {
        "cap_only": "reject",
        "blind_input_compression_only": "reject",
        "role_specific_projection_plus_closed_output_budget_plus_moderate_cap_headroom": "select",
    }
    limits = decision["selected_repair_contract"]["specialist_output_limits"]
    assert limits["fact_layer_max_items"] == 3
    assert limits["maximum_unicode_characters_per_narrative_item"] == 320
    assert limits["maximum_serialized_utf8_bytes"] == 6000
    budget = decision["selected_repair_contract"]["token_and_cost_limits"]
    assert budget["aggregate_max_output_tokens"] == 3 * 2200 + 1200 + 1400 + 1000
    assert budget["prior_aggregate_max_output_tokens"] == 7800
    assert budget["incremental_output_only_cost_ceiling_usd"] == 0.002088
    assert budget["max_total_cost_usd"] == 0.1
    assert budget["retry_budget"] == 0


def test_measured_request_reduction_is_explicitly_bounded_as_an_estimate() -> None:
    audit = _load(DECISION)["request_size_audit"]
    assert [row["current_request_bytes"] for row in audit["cells"]] == [
        26852,
        33040,
        27666,
    ]
    assert [row["candidate_model_view_request_bytes"] for row in audit["cells"]] == [
        6659,
        12796,
        7989,
    ]
    assert all(row["reduction_percent"] >= 60 for row in audit["cells"])
    assert "not provider measurements" in audit["estimate_boundary"]


def test_backlog_preserves_zero_call_repair_decision_without_admission_or_execution() -> None:
    decision = _load(DECISION)
    backlog = _load(BACKLOG)
    assert decision["observed_counts"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_network_calls": 0,
        "external_tool_calls": 0,
        "new_admissions": 0,
        "live_runs": 0,
    }
    assert backlog["next_action"]["S3_T09_first_node_truncation_repair_decision_ref"] == (
        "configs/releases/fin_ia_0_1_s3_t09_first_node_truncation_repair_decision_v1_0.json"
    )
    assert backlog["next_action"][
        "S3_T09_first_node_truncation_repair_decision_authorized"
    ] is True
    assert backlog["next_action"]["replacement_admission_or_execution_authorized"] is False
