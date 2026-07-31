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
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentExecutor,
)


DECISION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s3_t09_owner_grade_v3_first_specialist_schema_failure_"
    "root_cause_transport_decision_v1_0.json"
)
ADMISSION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_v3_exact_admission_v1_0.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_decision_identifies_provider_visible_schema_validator_contradiction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = _load(DECISION)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(_load(ADMISSION))
    diagnosed = decision["confirmed_project_owned_root_cause"]
    accepted = set(diagnosed["local_validator_accepted_top_level_keys"])
    rejected_constraints = set(
        diagnosed["provider_visible_but_local_validator_rejected_constraint_keys"]
    )
    monkeypatch.setattr(
        DeepSeekS3ThreeCellNodeExecutor,
        "_specialist_model_view",
        classmethod(lambda cls, payload: {"program_cell_id": "demand_authenticity_and_sustainability"}),
    )
    _, request, _ = DeepSeekS3ThreeCellNodeExecutor._node_request(
        "domain_specialist:demand_authenticity_and_sustainability",
        {
            "input_contract_ref": "fixture",
            "input_digest": "fixture",
            "cell_input": {"program_cell_id": "demand_authenticity_and_sustainability"},
            "required_output_layers": [],
        },
        admission,
    )
    assert diagnosed["provider_visible_required_output_schema_top_level_key_count"] == 14
    assert diagnosed["local_validator_accepted_top_level_key_count"] == 7
    provider_keys = set(request["required_output_schema"])
    assert provider_keys == accepted
    assert set(request["output_constraints"]) == rejected_constraints
    assert set(request["required_top_level_keys"]) == accepted
    assert request["additional_properties_allowed"] is False

    provider_literal_output = dict.fromkeys(accepted | rejected_constraints)
    provider_literal_output["program_cell_id"] = "demand_authenticity_and_sustainability"
    with pytest.raises(
        ValueError,
        match="s3_bounded_specialist_output_schema_invalid:demand_authenticity_and_sustainability",
    ):
        S3ThreeCellBoundedAgentExecutor._validate_specialist_output(
            provider_literal_output,
            {"program_cell_id": "demand_authenticity_and_sustainability"},
            output_contract_ref=admission.output_contract_ref,
        )


def test_decision_selects_segmented_local_assembly_without_relaxing_v3() -> None:
    decision = _load(DECISION)
    selected = decision["selected_zero_call_implementation_contract"]
    alternatives = {row["route"]: row["decision"] for row in decision["alternatives"]}
    assert alternatives["deepseek_segmented_owner_grade_specialist_with_local_assembly"] == "selected"
    assert alternatives["same_monolithic_v3_json_object_after_prompt_repair"] == "reject_as_next_live_route"
    assert alternatives["deepseek_beta_strict_named_function"] == "reject"
    assert selected["canonical_output_contract_ref_unchanged"] == (
        "fin01.s3.bounded_agent_three_cell_output:v3"
    )
    assert selected["logical_node_count_unchanged"] == 6
    assert [row["segment_id"] for row in selected["specialist_segments_per_cell"]] == [
        "facts_explanation_and_terminal",
        "owner_grade_claim_cards",
        "actionable_what_would_change_tasks",
    ]
    assert selected["provisional_maximum_semantic_provider_network_calls"] == [12, 12, 12]
    assert selected["retry_fallback_repair_or_rerun_budget"] == 0
    assert selected["first_failure_stop"] is True


def test_decision_remains_zero_call_and_current_backlog_records_implementation() -> None:
    decision = _load(DECISION)
    backlog = _load(BACKLOG)
    assert set(decision["observed_counts"].values()) == {0}
    assert decision["authority"]["implementation_authorized"] is False
    assert decision["authority"]["new_admission_or_execution_authorized"] is False
    assert decision["next_action"] == (
        "S3-T09-OWNER-GRADE-V3-DEEPSEEK-SEGMENTED-SPECIALIST-TRANSPORT-"
        "ZERO-CALL-IMPLEMENTATION"
    )
    assert backlog["next_action"]["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V5-RESEARCH-LEAD-OUTPUT-TRUNCATION-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    assert backlog["next_action"]["zero_call_root_cause_and_transport_decision_authorized"] is True
    assert backlog["next_action"]["segmented_specialist_transport_implementation_authorized"] is True
    assert backlog["next_action"]["fresh_segmented_exact_admission_decision_authorized"] is True
    assert backlog["next_action"]["fresh_segmented_exact_admission_issuance_authorized"] is True
    assert backlog["next_action"]["fresh_segmented_exact_admission_issued"] is True
    assert backlog["next_action"]["fresh_segmented_exact_admission_consumed"] is True
    assert backlog["next_action"]["text_contract_zero_call_repair_implementation_authorized"] is True
    assert backlog["next_action"]["text_contract_v2_fresh_agent_proof_decision_authorized"] is True
    assert backlog["next_action"]["replacement_admission_or_execution_authorized"] is False


def test_decision_sources_only_official_provider_docs_and_prior_project_evidence() -> None:
    decision = _load(DECISION)
    sources = decision["source_evidence"]["official_provider_sources"]
    assert len(sources) == 3
    assert all(source.startswith("https://api-docs.deepseek.com/") for source in sources)
    assert decision["source_evidence"]["model_provider_execution_network_calls"] == [0, 0, 0]
