from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    DeepSeekS3ThreeCellNodeExecutor,
)


DECISION = (
    ROOT
    / "configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_segmented_first_"
    "segment_text_length_failure_root_cause_decision_v1_0.json"
)
RESULT = (
    ROOT
    / "configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_segmented_fresh_"
    "live_execution_result_v1_0.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_decision_preserves_exact_safe_failure_boundary() -> None:
    decision = _load(DECISION)
    result = _load(RESULT)
    boundary = decision["proven_failure_boundary"]
    disposition = result["failure_disposition"]
    assert boundary["provider_HTTP_transport_and_finish_reason_stop"] == "pass"
    assert boundary["native_JSON_object_parse"] == "pass"
    assert boundary["segment_exact_top_level_keys"] == "pass"
    assert boundary["program_cell_id_binding"] == "pass"
    assert boundary["combined_item_predicate"].startswith("failed_")
    assert boundary["second_segment_called"] is False
    assert boundary["artifact_count"] == 0
    assert (
        "whether_the_item_was_non_string_blank_or_over_320_unicode_characters"
        in decision["not_reconstructable"]
    )
    assert disposition["provider_HTTP_failure"] is False
    assert disposition["provider_JSON_syntax_failure"] is False


def test_current_segmented_request_exposes_generic_not_field_local_text_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        DeepSeekS3ThreeCellNodeExecutor,
        "_specialist_model_view",
        classmethod(
            lambda cls, payload: {
                "program_cell_id": "demand_authenticity_and_sustainability"
            }
        ),
    )
    system, request, _ = DeepSeekS3ThreeCellNodeExecutor._specialist_segment_request(
        node_id="domain_specialist:demand_authenticity_and_sustainability",
        segment_id="facts_explanation_and_terminal",
        payload={
            "input_contract_ref": "fixture",
            "input_digest": "fixture",
            "required_output_layers": [],
        },
        validated_segments={},
    )
    assert request["required_output_schema"]["explanation_layer"] == ["string"]
    assert request["output_constraints"][
        "maximum_narrative_item_unicode_characters"
    ] == 320
    assert "Treat output_constraints as rules" in system
    assert "Obey every cardinality, character, and byte limit" not in system


def test_decision_selects_owned_contract_and_telemetry_repair_without_relaxing_v3() -> None:
    decision = _load(DECISION)
    classification = decision["root_cause_classification"]
    selected = decision["selected_zero_call_implementation_contract"]
    assert classification["immediate_failure_class"] == (
        "provider_model_output_did_not_conform_to_application_text_contract"
    )
    assert classification["external_or_model_only_root_cause_confirmed"] is False
    assert selected["next_transport_ref"].endswith(":v2")
    assert selected["canonical_output_contract_ref_unchanged"].endswith(":v3")
    assert selected["local_maximum_narrative_item_unicode_characters_unchanged"] == 320
    assert selected["normalization_policy"] == {
        "truncate": False,
        "trim_into_acceptance": False,
        "coerce_non_string": False,
        "drop_invalid_item": False,
        "join_or_split_item": False,
    }
    assert set(selected["safe_text_failure_telemetry"]["allowed_subtypes"]) == {
        "item_not_string",
        "item_blank",
        "item_over_max_unicode_characters",
    }


def test_decision_remains_historical_and_backlog_advances_after_implementation() -> None:
    decision = _load(DECISION)
    backlog = _load(BACKLOG)
    next_action = backlog["next_action"]
    expected_decision = (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-FIELD-LOCAL-TEXT-CONTRACT-AND-"
        "SAFE-SUBTYPE-TELEMETRY-ZERO-CALL-IMPLEMENTATION"
    )
    expected_current = (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V5-RESEARCH-LEAD-OUTPUT-TRUNCATION-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    assert set(decision["observed_counts"].values()) == {0}
    assert decision["authority"]["implementation_authorized"] is False
    assert decision["authority"]["new_admission_or_model_execution_authorized"] is False
    assert decision["next_action"] == expected_decision
    assert next_action["item_id"] == expected_current
    assert next_action["text_contract_root_cause_decision_authorized"] is True
    assert next_action["text_contract_zero_call_repair_implementation_authorized"] is True
    assert next_action["text_contract_v2_fresh_agent_proof_decision_authorized"] is True
    assert next_action["agent_rerun_authorized"] is False
    assert next_action["replacement_admission_or_execution_authorized"] is False


def test_decision_contract_contains_no_plaintext_credential() -> None:
    rendered = DECISION.read_text(encoding="utf-8").lower()
    assert "sk-" not in rendered
    assert "fixture-secret" not in rendered
