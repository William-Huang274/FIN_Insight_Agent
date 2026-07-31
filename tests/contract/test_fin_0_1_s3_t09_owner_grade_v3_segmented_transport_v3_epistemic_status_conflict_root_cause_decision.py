from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_executor import (
    DeepSeekS3ThreeCellNodeExecutor,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V3_REF,
    S3ThreeCellBoundedAgentExecutor,
)
from test_fin_0_1_s3_t09_owner_grade_semantic_actionability_zero_call_repair import (
    _cell_input,
)


DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_segmented_transport_v3_"
    "epistemic_status_statement_conflict_root_cause_decision_v1_0.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _claim(*, support_fact_ids: list[str], cannot_support: list[str]):
    return {
        "claim_id": "claim:cannot-infer",
        "statement": "现有权威事实不足以支持该归因。",
        "epistemic_status": "cannot_infer",
        "support_fact_ids": support_fact_ids,
        "context_refs": [],
        "scope": {
            "entity_ref": "NVDA",
            "business_scope_kind": "unknown",
            "business_scope_ref": "unknown",
            "period": "as_of",
            "metric_or_mechanism": "归因边界",
            "attribution_level": "none",
        },
        "qualification": "",
        "cannot_support": cannot_support,
    }


def test_transport_v3_omits_the_validator_cross_field_state_machine(
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
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V3_REF,
    )
    rendered = json.dumps(request, ensure_ascii=False, sort_keys=True)
    assert "required for cannot_infer" in rendered
    assert "epistemic_status_contract" not in request
    assert "cannot_infer requires support_fact_ids exactly []" not in rendered


def test_local_validator_rejects_each_unstated_cannot_infer_conflict_branch() -> None:
    cell = _cell_input("value_and_profit_capture", 2)
    fact = {
        "fact_id": "fact:1",
        "statement": "bounded",
        "support_type": "Numeric",
        "support_refs": [cell["authority_refs"]["numeric_refs"][0]],
        "boundary": "bounded",
    }
    for claim in (
        _claim(support_fact_ids=["fact:1"], cannot_support=["不能支持归因"]),
        _claim(support_fact_ids=[], cannot_support=[]),
        _claim(support_fact_ids=["fact:1"], cannot_support=[]),
    ):
        try:
            S3ThreeCellBoundedAgentExecutor._validate_owner_grade_claims(
                {"fact_layer": [fact], "judgment_layer": [claim]}, cell
            )
        except ValueError as exc:
            assert str(exc) == "s3_owner_grade_epistemic_status_statement_conflict"
        else:
            raise AssertionError("cannot_infer conflict must fail closed")


def test_decision_selects_versioned_state_machine_without_relaxing_validator() -> None:
    decision = _load(DECISION)
    audit = decision["zero_call_contract_audit"]
    assert audit["earliest_project_owned_root_cause"].startswith(
        "the local validator enforces"
    )
    assert audit["provider_or_model_only_root_cause_confirmed"] is False
    selected = decision["selected_zero_call_implementation_contract"]
    assert selected["next_transport_ref"].endswith(":v4")
    assert selected["historical_transport_v1_v2_v3_immutable"] is True
    assert selected["local_owner_grade_validator_unchanged"] is True
    contract = selected["provider_visible_epistemic_status_contract"]
    assert contract[
        "cannot_infer_requires_support_fact_ids_exactly_empty_array"
    ] is True
    assert contract[
        "cannot_infer_requires_one_or_more_nonblank_cannot_support_boundaries"
    ] is True


def test_decision_requires_restricted_raw_output_capture_for_future_admission() -> None:
    decision = _load(DECISION)
    persistence = decision["provider_output_persistence_prerequisite"]
    assert persistence["status"] == "implemented_and_fixture_verified_for_future_runs"
    assert persistence["historical_transport_v3_output_recoverable"] is False
    assert persistence["access_class"] == "internal_restricted_run_audit"
    assert decision["selected_zero_call_implementation_contract"][
        "future_admission_requirement"
    ].endswith("assistant_final_text_only:v1")


def test_backlog_advances_only_to_zero_call_transport_v4_implementation() -> None:
    next_action = _load(BACKLOG)["next_action"]
    assert next_action["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V5-RESEARCH-LEAD-OUTPUT-TRUNCATION-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    assert next_action["transport_v3_epistemic_status_root_cause_decision_authorized"] is True
    assert next_action["transport_v4_epistemic_status_zero_call_implementation_authorized"] is True
    assert next_action["agent_proof_decision_authorized"] is True
    assert next_action["admission_issuance_authorized"] is True
    assert next_action["agent_execution_authorized"] is False
    assert next_action["replacement_admission_or_execution_authorized"] is False


def test_decision_contains_no_plaintext_credential() -> None:
    rendered = DECISION.read_text(encoding="utf-8").lower()
    assert "sk-" not in rendered
    assert "fixture-secret" not in rendered
