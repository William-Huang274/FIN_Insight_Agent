from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


DECISION_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s3_minimal_natural_repair_canary_"
    "value_cost_risk_decision_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_decision_is_zero_call_and_does_not_authorize_live_or_report() -> None:
    decision = _load(DECISION_PATH)
    assert decision["scope"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_calls": 0,
        "retries": 0,
        "live_scope_registered": False,
        "live_runner_implemented": False,
        "live_admission_issued": False,
        "live_execution_authorized_by_this_record": False,
        "complete_report_authorized": False,
        "business_artifact_promotion": False,
    }


def test_decision_avoids_repeating_prior_demand_canaries() -> None:
    decision = _load(DECISION_PATH)
    assert decision["new_information_audit"][
        "dell_demand_natural_question_already_answered"
    ] is True
    selected = [
        row["option_id"]
        for row in decision["option_assessment"]
        if row["decision"] == "selected"
    ]
    assert selected == [
        "D_one_dell_current_pack_value_profit_repair_adjudication_canary"
    ]


def test_selected_canary_uses_current_pack_and_exact_affected_cells() -> None:
    selected = _load(DECISION_PATH)["selected_canary"]
    assert selected["current_pack_accepted_evidence"] == ["E021"]
    assert selected["boundary_evidence"] == ["E002", "E008", "E023"]
    assert selected["expected_affected_cell_ids"] == [
        "bottleneck_counterevidence_and_what_would_change",
        "cross_chain_price_in_and_expectations",
        "value_and_profit_capture",
        "writer_admission_boundary",
    ]
    assert selected["required_retained_gaps"] == [
        "audited_product_profit_bridge",
        "cash_conversion",
        "gross_margin",
    ]
    assert selected["model_numeric_surface_authority"] == (
        "alias_and_ref_selection_only"
    )


def test_next_step_is_zero_call_implementation_and_clean_proof_only() -> None:
    next_step = _load(DECISION_PATH)["authorized_next_implementation"]
    assert next_step["implement_provider_neutral_typed_repair_canary"] is True
    assert next_step["use_existing_s3_successor_state_transition"] is True
    assert next_step["perform_clean_independent_zero_call_proof"] is True
    assert next_step["register_or_execute_live_scope"] is False
    assert next_step["issue_live_admission"] is False
    assert next_step["execute_provider_call"] is False
    assert next_step["run_complete_report"] is False


def test_decision_digest_is_canonical() -> None:
    decision = _load(DECISION_PATH)
    body = {key: value for key, value in decision.items() if key != "decision_digest"}
    assert decision["decision_digest"] == canonical_digest(body)
