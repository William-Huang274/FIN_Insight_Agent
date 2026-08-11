from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.research_runtime import (
    FIN01_DETERMINISTIC_PROFILE_REF,
    FIN01_S3_RUNTIME_FAMILY_REF,
    S3CellBranchObservation,
    compile_fin01_s3_three_cell_runtime_plan,
    consume_fin01_s3_role_context_plans,
)
from sec_agent.canonical_runtime.planning_service import (
    FIN01_S3_PROGRAM_CELL_CONTRACTS,
)


RELEASES = ROOT / "configs" / "releases"
T01 = RELEASES / "fin_ia_0_1_s3_t01_three_cell_decision_surface_asset_owner_freeze_v1_0.json"
T02 = RELEASES / "fin_ia_0_1_s3_t02_runtime_plan_branch_lineage_role_context_v1_0.json"
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
ROOT_CAUSES = ROOT / "docs" / "project_os" / "root_cause_issue_ledger.jsonl"


def _compile(*, observations=None):
    return compile_fin01_s3_three_cell_runtime_plan(
        case_id="case-fin01-s3-t02",
        work_unit_id="wu-fin01-s3-t02",
        attempt_id="attempt-fin01-s3-t02",
        research_run_id="research-run-fin01-s3-t02",
        execution_profile_version_ref=FIN01_DETERMINISTIC_PROFILE_REF,
        decision_surface_contract_ref="contract-fin01-s3-t02:v1",
        observations=observations,
    )


def _latest_root_causes() -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for line in ROOT_CAUSES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["issue_id"]] = row
    return rows


def test_t02_contract_records_exact_authority_implementation_and_open_boundaries() -> None:
    contract = json.loads(T02.read_text(encoding="utf-8"))
    assert contract["status"] == (
        "pass_after_independent_review_T03_ready_pending_separate_authorization"
    )
    assert contract["authority"]["S3_T02_implementation_and_zero_call_fixture_authorized"] is True
    assert contract["authority"]["S3_T03_execution_authorized"] is False
    assert contract["implementation"]["runtime_family_count"] == 1
    assert contract["implementation"]["active_cell_count"] == 3
    assert contract["implementation"]["parallel_runtime_registry_writer_store_or_business_truth_family_added"] is False
    assert contract["implementation"]["S2_consumed_identity_or_artifact_rewritten"] is False
    assert contract["implementation"]["bounded_agent_three_cell_model_execution_implemented"] is False
    assert contract["context_plan_contract"]["plan_count_per_runtime_plan"] == 9
    assert all(
        value == 0
        for key, value in contract["observed_counts"].items()
        if key != "ephemeral_isolated_test_fixture_runs"
    )
    assert all(row["closed_by_T02"] is False for row in contract["root_cause_reconcile"])


def test_t02_updates_root_causes_without_imputed_full_closeout() -> None:
    history = [
        json.loads(line)
        for line in ROOT_CAUSES.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    p30 = next(
        row
        for row in history
        if row["issue_id"] == "RC-P30-001-real-single-case-artifact-proof-pending"
        and row["status"]
        == "S3_T02_deterministic_three_cell_run_lineage_proven_exact_paid_case_artifact_pending"
    )
    p35 = next(
        row
        for row in history
        if row["issue_id"]
        == "RC-P35-021-ai-infra-decision-surface-not-runtime-contract"
        and row["status"]
        == "S3_T02_three_cell_runtime_plan_injected_node_context_consumed_remaining_data_judgment_delivery_subscopes_open"
    )
    assert p30["status"] == (
        "S3_T02_deterministic_three_cell_run_lineage_proven_exact_paid_case_artifact_pending"
    )
    assert p35["status"] == (
        "S3_T02_three_cell_runtime_plan_injected_node_context_consumed_remaining_data_judgment_delivery_subscopes_open"
    )
    assert p30["full_chain_blocker"] is p35["full_chain_blocker"] is True
    assert p30["verification_result"]["exact_paid_three_cell_artifact"] is False
    assert p35["verification_result"]["downstream_T03_T07_consumption_proven"] is False


def test_t02_compiles_exact_three_cell_lineage_inside_one_runtime_and_run() -> None:
    plan = _compile()
    replay = _compile()
    frozen = json.loads(T01.read_text(encoding="utf-8"))["decision_surface"]["cells"]

    assert plan == replay
    assert plan.runtime_family_ref == FIN01_S3_RUNTIME_FAMILY_REF
    assert plan.research_run_id == "research-run-fin01-s3-t02"
    assert len(plan.cell_branches) == 3
    assert len({row.cell_version_ref for row in plan.cell_branches}) == 3
    assert len({row.branch_version_ref for row in plan.cell_branches}) == 3
    assert {row.research_run_id for row in plan.cell_branches} == {
        plan.research_run_id
    }
    assert [row.program_cell_id for row in plan.cell_branches] == [
        row.program_cell_id for row in FIN01_S3_PROGRAM_CELL_CONTRACTS
    ] == [row["program_cell_id"] for row in frozen]
    assert [row.decision_question for row in plan.cell_branches] == [
        row["decision_question"] for row in frozen
    ]
    assert {
        plan.model_calls,
        plan.provider_calls,
        plan.network_calls,
        plan.external_tool_calls,
        plan.canonical_business_writes,
    } == {0}


def test_t02_different_observations_produce_bounded_branch_or_stop_decisions() -> None:
    plan = _compile(
        observations={
            "demand_authenticity_and_sustainability": S3CellBranchObservation(
                observation_type="accepted_evidence_available",
                refs=("evidence-demand:v1",),
                rationale="Accepted demand evidence is available.",
            ),
            "value_and_profit_capture": S3CellBranchObservation(
                observation_type="route_exhausted",
                refs=("gap-value:v1",),
                rationale="No segment and margin evidence remains reachable.",
            ),
            "bottleneck_counterevidence_and_what_would_change": (
                S3CellBranchObservation(
                    observation_type="material_counterevidence_available",
                    refs=("counterevidence-risk:v1",),
                    rationale="Material counterevidence must be considered first.",
                )
            ),
        }
    )
    decisions = {
        row.program_cell_id: (
            row.lead_branch_decision,
            row.branch_state,
            row.terminal_reason,
        )
        for row in plan.cell_branches
    }
    assert decisions["demand_authenticity_and_sustainability"] == (
        "continue_to_specialist",
        "active",
        None,
    )
    assert decisions["value_and_profit_capture"] == (
        "typed_stop_cannot_infer",
        "stopped",
        "route_exhausted_without_required_authoritative_evidence",
    )
    assert decisions["bottleneck_counterevidence_and_what_would_change"] == (
        "continue_to_specialist_counterevidence_first",
        "active",
        None,
    )


def test_t02_context_plans_are_role_scoped_distinct_and_reconstructable() -> None:
    plan = _compile()
    contexts = plan.role_context_plans
    assert len(contexts) == len({row.context_plan_version_ref for row in contexts}) == 9
    assert len({row.context_input_digest for row in contexts}) == 9
    assert Counter(row.target_node for row in contexts) == {
        "research_lead": 1,
        "domain_specialist": 3,
        "evidence_operator": 3,
        "memo_writer": 1,
        "verifier": 1,
    }
    specialist_cells = {
        row.program_cell_id
        for row in contexts
        if row.target_node == "domain_specialist"
    }
    assert specialist_cells == {
        row.program_cell_id for row in FIN01_S3_PROGRAM_CELL_CONTRACTS
    }
    evidence_contexts = [
        row for row in contexts if row.target_node == "evidence_operator"
    ]
    assert all(row.authority["may_use_source_network"] is False for row in evidence_contexts)
    assert all(
        "expected_conclusion"
        in {
            decision.context_ref
            for decision in row.selection_decisions
            if decision.decision == "dropped"
        }
        for row in evidence_contexts
    )
    writer = next(row for row in contexts if row.target_node == "memo_writer")
    verifier = next(row for row in contexts if row.target_node == "verifier")
    assert writer.authority["may_retrieve_sources"] is False
    assert writer.authority["may_use_tools"] is False
    assert verifier.authority["may_promote_evidence"] is False
    assert all(row.context_payload and row.selection_decisions for row in contexts)

    receipts = consume_fin01_s3_role_context_plans(plan)
    assert len(receipts) == 9
    assert {
        (row["target_node"], row["program_cell_id"], row["context_input_digest"])
        for row in receipts
    } == {
        (row.target_node, row.program_cell_id, row.context_input_digest)
        for row in contexts
    }
    assert all(row["model_calls"] == row["network_calls"] == 0 for row in receipts)


def test_t02_rejects_unknown_cell_observation_fail_closed() -> None:
    with pytest.raises(ValueError, match="s3_runtime_plan_unknown_cell_observation"):
        _compile(
            observations={
                "unapproved_fourth_cell": {
                    "observation_type": "no_runtime_observation",
                    "rationale": "Not part of FIN 0.1 scope.",
                }
            }
        )


def test_t02_context_consumption_rejects_tampered_plan_digest() -> None:
    plan = _compile()
    tampered = plan.model_copy(
        update={"decision_surface_contract_ref": "contract-tampered:v1"}
    )
    with pytest.raises(ValueError, match="s3_runtime_plan_digest_mismatch"):
        consume_fin01_s3_role_context_plans(tampered)

    tampered_counts = plan.model_copy(update={"model_calls": 1})
    with pytest.raises(ValueError, match="s3_runtime_plan_digest_mismatch"):
        consume_fin01_s3_role_context_plans(tampered_counts)


def test_t02_frozen_next_action_is_t03_while_current_backlog_advances() -> None:
    contract = json.loads(T02.read_text(encoding="utf-8"))
    backlog = json.loads(BACKLOG.read_text(encoding="utf-8"))
    assert contract["next_action"] == (
        "S3-T03-CELL-DRIVEN-EVIDENCE-REQUEST-ROUTE-PROMOTION-AND-SOURCEHUNTER-BOUNDARY"
    )
    assert contract["authority"]["S3_T03_execution_authorized"] is False
    assert backlog["next_action"]["item_id"] == (
        "S4-T05-DELL-EVIDENCE-ROLE-GROUP-MAPPING-AND-ACTUAL-DISPATCH-"
        "PREFLIGHT-ZERO-CALL-IMPLEMENTATION"
    )
    assert backlog["next_action"]["S3_T08_readiness_gate_status"] == (
        "pass_T09_ready_pending_separate_authority"
    )
    assert backlog["next_action"]["S3_T08_repair_execution_authorized"] is True
    assert backlog["next_action"]["S3_T09_execution_authorized"] is True
