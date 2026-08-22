from __future__ import annotations

from pathlib import Path
import sys
import json

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.workbench.backend.application.research_evidence_pack_service import (
    ResearchEvidencePackPrincipal,
    ResearchEvidencePackService,
)
from apps.workbench.backend.application.research_retrieval_service import (
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from scripts.research.run_s3_current_research_consumer_zero_call import _services
from sec_agent.research.current_consumer import compile_current_research_messages
from sec_agent.research.dynamic_research_runtime import (
    compile_dynamic_research_input_projection,
)
from sec_agent.research.actionable_research_evaluation import (
    evaluate_actionable_research_state,
)
from sec_agent.runtime_bridge.paths import resolve_runtime_paths


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            child for item in value.values() for child in _all_keys(item)
        }
    if isinstance(value, list):
        return {child for item in value for child in _all_keys(item)}
    return set()


@pytest.fixture(scope="module")
def service() -> ResearchEvidencePackService:
    return ResearchEvidencePackService.from_runtime_paths(
        ROOT, resolve_runtime_paths(ROOT)
    )


@pytest.mark.parametrize("case_key", ("DELL", "MU", "NVDA"))
def test_current_case_data_drives_action_feedback_checkpoint_and_evaluation(
    service: ResearchEvidencePackService, case_key: str
) -> None:
    principal = ResearchEvidencePackPrincipal(
        "current", frozenset({"current_product:read"})
    )
    current = service.get_case(case_key, principal)
    state = current["actionable_research_state"]
    quantitative = current["quantitative_authority"]
    evaluation = evaluate_actionable_research_state(
        state=state, quantitative_authority=quantitative
    )

    assert state["status"] == "runtime_injected_current_data_replay"
    assert state["research_actions"]
    assert len(state["research_actions"]) == len(
        state["actionable_uncertainties"]
    )
    assert state["accepted_plan_delta"]["validation_status"] == "accepted"
    assert state["session"]["active_plan_ref"] == state["accepted_plan"][
        "plan_ref"
    ]
    assert state["resume_receipt"]["status"] == "resume_replay_verified"
    assert state["stop_decision"]["decision"] == "continue"
    assert state["next_natural_node_token_budget_basis"][
        "execution_authority"
    ] is False
    assert state["summary"]["public_information_gap_authorized_count"] == 0
    assert not {
        "candidate_text",
        "private_source_material",
        "source_capture_ref",
    }.intersection(_all_keys(state))
    assert evaluation["status"] == "pass"
    assert evaluation["summary"]["passed_gate_count"] == 12
    assert evaluation["authority"]["S1_qualification_claimed"] is False
    assert evaluation["authority"]["S3_acceptance_claimed"] is False


def test_current_dell_data_is_consumed_by_each_dynamic_s3_research_cell(
    service: ResearchEvidencePackService,
) -> None:
    def load(relative: str) -> dict:
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    retrieval = ResearchRetrievalService.from_runtime_paths(
        ROOT, resolve_runtime_paths(ROOT)
    )
    permissions = frozenset({"current_product:read"})
    pack = service.get_case(
        "DELL", ResearchEvidencePackPrincipal("current", permissions)
    )
    controlled = retrieval.execute_controlled_plan(
        "DELL",
        load(
            "configs/research/evals/"
            "fin_ia_0_1_3_s3_dell_minimal_planner_canary_objective_v1_0.json"
        ),
        load(
            "tests/fixtures/research/"
            "fin_ia_0_1_3_s3_dell_planner_r1_atoms_v1_0.json"
        ),
        ResearchRetrievalPrincipal("current", permissions),
    )
    dynamic = compile_dynamic_research_input_projection(
        truth_spine_policy=load(
            "configs/research/"
            "fin_ia_0_1_3_s3_dynamic_truth_spine_policy_v1_0.json"
        ),
        consumer_policy=load(
            "configs/research/"
            "fin_ia_0_1_3_s3_current_research_consumer_policy_v1_4.json"
        ),
        controlled_plan=controlled,
        evidence_pack=pack,
        include_actionable_control_context=True,
    )["dynamic_research_input"]

    assert dynamic["research_control_context"]["status"] == (
        "current_action_feedback_checkpoint_bound_to_dynamic_input"
    )
    assert {tuple(row["quantitative_kinds"]) for row in dynamic["numeric_fact_cards"]} == {
        ("reported_fact",),
        ("deterministic_derived_metric",),
    }
    binding_counts = dynamic["research_control_context"][
        "quantitative_authority"
    ]["numeric_card_binding_mode_counts"]
    assert binding_counts["exact_authority_ref"] == 23
    assert binding_counts["economic_fact_signature_alias"] == 2
    alias_bound = [
        row
        for row in dynamic["numeric_fact_cards"]
        if row["quantitative_binding_mode"]
        == "economic_fact_signature_alias"
    ]
    assert {(row["ticker"], row["metric_id"]) for row in alias_bound} == {
        ("MU", "inventory"),
        ("NVDA", "inventory"),
    }
    assert all(row["quantitative_authority_refs"] for row in alias_bound)
    for cell in dynamic["cells"]:
        messages = compile_current_research_messages(
            dynamic,
            required_cell_ids=[cell["cell_id"]],
            submission_transport="final_tool",
        )
        visible = json.loads(messages[1]["content"])
        control = visible["research_control_context"]
        assert control["research_actions"]
        assert control["stop_decision"]["decision"] == "continue"
        assert control["checkpoint_resume"]["resume_status"] == (
            "resume_replay_verified"
        )
        assert control["token_budget_basis"]["execution_authority"] is False
