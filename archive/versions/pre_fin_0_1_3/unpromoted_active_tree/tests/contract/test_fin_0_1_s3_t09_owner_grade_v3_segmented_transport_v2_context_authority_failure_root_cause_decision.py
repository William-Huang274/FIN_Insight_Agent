from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    DeepSeekS3ThreeCellNodeExecutor,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V2_REF,
    S3ThreeCellBoundedAgentExecutor,
)
from test_fin_0_1_s3_t09_owner_grade_semantic_actionability_zero_call_repair import (
    _cell_input,
)


DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_segmented_transport_v2_"
    "context_authority_failure_root_cause_decision_v1_0.json"
)
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_segmented_text_contract_"
    "v2_fresh_live_execution_result_v1_0.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_decision_preserves_exact_live_failure_and_unknowns() -> None:
    decision = _load(DECISION)
    result = _load(RESULT)
    boundary = decision["proven_failure_boundary"]
    assert boundary["failure_code"] == "s3_owner_grade_claim_context_authority_invalid"
    assert result["provider_execution"]["failed_stage"] == (
        "domain_specialist:value_and_profit_capture:owner_grade_claim_cards"
    )
    assert boundary["artifact_count"] == 0
    assert "the_exact_invalid_context_ref_value" in decision["not_reconstructable"]
    assert decision["root_cause_classification"][
        "external_or_model_only_root_cause_confirmed"
    ] is False


def test_transport_v2_request_does_not_field_locally_bind_closed_context_list(
    monkeypatch,
) -> None:
    cell = _cell_input("value_and_profit_capture", 2)
    monkeypatch.setattr(
        DeepSeekS3ThreeCellNodeExecutor,
        "_specialist_model_view",
        classmethod(lambda cls, payload: payload["cell_input"]),
    )
    _, request, _ = DeepSeekS3ThreeCellNodeExecutor._specialist_segment_request(
        node_id="domain_specialist:value_and_profit_capture",
        segment_id="owner_grade_claim_cards",
        payload={
            "input_contract_ref": "fixture",
            "input_digest": "a" * 64,
            "cell_input": cell,
            "required_output_layers": [],
        },
        validated_segments={
            "facts_explanation_and_terminal": {
                "program_cell_id": "value_and_profit_capture",
                "fact_layer": [],
                "explanation_layer": ["bounded"],
                "remaining_gaps": ["bounded"],
                "terminal_class": "bounded",
            }
        },
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V2_REF,
    )
    context_instruction = request["required_output_schema"]["judgment_layer"][0][
        "context_refs"
    ]
    assert context_instruction == ["exact Candidate or Graph context ref"]
    assert "allowed_context_refs" not in json.dumps(request, sort_keys=True)
    surface = S3ThreeCellBoundedAgentExecutor._owner_grade_authority_surface(cell)
    assert surface["candidate_refs_not_evidence"]
    assert surface["graph_context_refs_not_evidence"]


def test_decision_selects_versioned_closed_set_repair_without_relaxation() -> None:
    decision = _load(DECISION)
    selected = decision["selected_zero_call_implementation_contract"]
    assert selected["next_transport_ref"].endswith(":v3")
    assert selected["historical_transport_v1_and_v2_immutable"] is True
    assert selected["canonical_output_contract_ref_unchanged"].endswith(":v3")
    assert selected["local_context_authority_validator_unchanged"] is True
    contract = selected["provider_visible_context_field_contract"]
    assert contract["output_context_refs_must_be_an_exact_subset"] is True
    assert contract["empty_array_required_when_no_allowed_context_is_used"] is True
    assert contract["no_dynamic_normalization_or_fuzzy_matching"] is True
    assert set(selected["safe_authority_failure_telemetry"]["allowed_subtypes"]) == {
        "item_not_nonblank_string",
        "evidence_or_numeric_ref_misclassified_as_context",
        "outside_current_cell_context_authority",
    }


def test_decision_records_audit_integrity_and_bounded_future_stop_line() -> None:
    decision = _load(DECISION)
    integrity = decision["audit_integrity"]
    assert integrity["target_logical_WorkUnit_Attempt_Run_Artifact_counts_after_audit"] == [
        6,
        6,
        6,
        13,
    ]
    assert integrity["target_new_logical_entities_or_objects"] == 0
    assert integrity["target_main_sqlite_file_digest_unchanged"] is False
    assert decision["future_live_stop_line"][
        "at_most_one_fresh_transport_v3_exact_live_proof_may_be_considered_under_later_separate_decision_issuance_and_execution_authorities"
    ] is True
    assert set(decision["observed_counts"].values()) == {0}


def test_backlog_advances_only_to_zero_call_transport_v3_implementation() -> None:
    decision = _load(DECISION)
    next_action = _load(BACKLOG)["next_action"]
    assert next_action["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V5-RESEARCH-LEAD-OUTPUT-TRUNCATION-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    assert next_action[
        "text_contract_v2_context_authority_failure_root_cause_decision_authorized"
    ] is True
    assert next_action[
        "transport_v3_context_authority_zero_call_implementation_authorized"
    ] is True
    assert next_action["replacement_admission_or_execution_authorized"] is False
    assert next_action["agent_rerun_authorized"] is False


def test_decision_contract_contains_no_plaintext_credential() -> None:
    rendered = DECISION.read_text(encoding="utf-8").lower()
    assert "sk-" not in rendered
    assert "fixture-secret" not in rendered
