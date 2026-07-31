from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from sec_agent.research_graph_store import (
    S3BoundedGraphDecisionCellPackVersion,
    classify_s3_graph_edge_admissibility,
    consume_s3_bounded_graph_decision_cell_pack,
)
from tests.contract.test_fin_0_1_s3_t04_financial_numeric_fundamental_pack import (
    _run_payload,
)


RELEASES = ROOT / "configs" / "releases"
T05 = RELEASES / "fin_ia_0_1_s3_t05_bounded_graph_decision_cell_pack_v1_0.json"
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
ROOT_CAUSES = ROOT / "docs" / "project_os" / "root_cause_issue_ledger.jsonl"


def _latest_root_causes() -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for line in ROOT_CAUSES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            latest[row["issue_id"]] = row
    return latest


def test_t05_contract_advances_only_to_unapproved_t06() -> None:
    contract = json.loads(T05.read_text(encoding="utf-8"))
    backlog = json.loads(BACKLOG.read_text(encoding="utf-8"))
    roots = _latest_root_causes()
    assert contract["status"] == (
        "pass_after_independent_review_T06_ready_pending_separate_authorization"
    )
    assert contract["authority"]["S3_T05_zero_call_deterministic_fixture_authorized"] is True
    assert contract["authority"]["S3_T06_execution_authorized"] is False
    assert contract["implementation"]["decision_cell_projection_count"] == 3
    assert contract["implementation"]["graph_edge_projection_count"] == 3
    assert contract["implementation"]["market_price_in_typed_gap_count"] == 3
    assert contract["implementation"]["risk_context_count"] == 3
    assert backlog["next_action"]["item_id"] == (
        "S3-T09-EXACT-THREE-CELL-DEEPSEEK-LIVE-EXECUTION"
    )
    assert backlog["next_action"]["S3_T08_repair_execution_authorized"] is True
    assert backlog["next_action"]["S3_T09_execution_authorized"] is False
    for issue_id in (
        "RC-P36-024-graph-assets-not-projected-into-value-capture-decision-surface",
        "RC-P36-026-product-industry-selector-not-decision-surface-balanced",
        "RC-P36-027-market-capital-feedback-not-decision-surface-wired",
        "RC-P36-028-risk-counterevidence-not-risk-cell-projected",
    ):
        assert roots[issue_id]["verification_result"]["runtime_injected"] is True
        assert roots[issue_id]["verification_result"]["node_level_consumed"] is True
        assert roots[issue_id]["full_chain_blocker"] is True


def test_t05_runtime_persists_and_consumes_same_run_graph_pack(tmp_path: Path) -> None:
    payload = _run_payload(tmp_path)
    runtime_plan = payload["s3_runtime_plan"]
    pack = S3BoundedGraphDecisionCellPackVersion.model_validate(
        payload["s3_bounded_graph_product_market_risk_pack"]
    )
    receipts = consume_s3_bounded_graph_decision_cell_pack(
        pack,
        runtime_plan=runtime_plan,
        evidence_route_plan=payload["s3_evidence_route_plan"],
        financial_pack=payload["s3_financial_numeric_and_fundamental_pack"],
        analysis_preview=payload["result"],
    )
    assert payload["s3_bounded_graph_consumption_receipts"] == list(receipts)
    assert len(receipts) == 3
    assert pack.research_run_id == runtime_plan["research_run_id"]
    assert pack.runtime_plan_version_ref == runtime_plan["runtime_plan_version_ref"]
    assert pack.existing_local_research_graph_read_count == 1
    assert pack.additional_graph_read_count == 0


def test_t05_each_cell_has_one_typed_edge_with_visible_authority_and_followup(
    tmp_path: Path,
) -> None:
    pack = S3BoundedGraphDecisionCellPackVersion.model_validate(
        _run_payload(tmp_path)["s3_bounded_graph_product_market_risk_pack"]
    )
    expected_cells = (
        "demand_authenticity_and_sustainability",
        "value_and_profit_capture",
        "bottleneck_counterevidence_and_what_would_change",
    )
    assert tuple(row.program_cell_id for row in pack.graph_edges) == expected_cells
    assert tuple(row.program_cell_id for row in pack.decision_cells) == expected_cells
    assert len({row.use_case for row in pack.graph_edges}) == 3
    for edge in pack.graph_edges:
        assert edge.edge_type
        assert edge.authority_mode
        assert edge.source_ref and edge.source_snapshot_ref
        assert edge.source_as_of and edge.projection_as_of
        assert edge.claim_boundary and edge.forbidden_claims
        assert edge.followup_refs
        assert edge.direct_evidence_authorized is False
        assert edge.numeric_authority is False
        assert edge.mechanism_path_is_fact is False
        assert edge.writer_citable is False


def test_t05_naked_stale_inferred_and_conflicting_edges_fail_evidence_admission(
    tmp_path: Path,
) -> None:
    payload = _run_payload(tmp_path)
    pack = S3BoundedGraphDecisionCellPackVersion.model_validate(
        payload["s3_bounded_graph_product_market_risk_pack"]
    )
    assert {row.condition: row.rejection_code for row in pack.admissibility_probes} == {
        "naked": "graph_edge_missing_source_ref",
        "stale": "graph_edge_stale_as_of",
        "inferred": "graph_edge_inferred_hypothesis",
        "conflicting": "graph_edge_conflicting_sources",
    }
    assert all(row.accepted_as_evidence is False for row in pack.admissibility_probes)
    assert all(
        classify_s3_graph_edge_admissibility(edge.model_dump(mode="json"))
        == "graph_edge_inferred_hypothesis"
        for edge in pack.graph_edges
    )

    tampered_edge = pack.graph_edges[0].model_copy(
        update={"direct_evidence_authorized": True}
    )
    tampered = pack.model_copy(
        update={"graph_edges": (tampered_edge, *pack.graph_edges[1:])}
    )
    with pytest.raises(ValueError, match="s3_graph_decision_cell_pack_recompile_mismatch"):
        consume_s3_bounded_graph_decision_cell_pack(
            tampered,
            runtime_plan=payload["s3_runtime_plan"],
            evidence_route_plan=payload["s3_evidence_route_plan"],
            financial_pack=payload["s3_financial_numeric_and_fundamental_pack"],
            analysis_preview=payload["result"],
        )


def test_t05_graph_never_allocates_numbers_and_market_risk_remain_typed(
    tmp_path: Path,
) -> None:
    pack = S3BoundedGraphDecisionCellPackVersion.model_validate(
        _run_payload(tmp_path)["s3_bounded_graph_product_market_risk_pack"]
    )
    assert pack.graph_allocated_financial_numbers == 0
    assert pack.graph_edges_promoted_to_evidence == 0
    assert all(not row.context_refs for row in pack.market_price_in_contexts)
    assert all(
        row.status.startswith("typed_gap_no_same_as_of")
        and row.exact_market_fact_authorized is False
        for row in pack.market_price_in_contexts
    )
    assert all(
        row.probability_status == "typed_cannot_infer"
        and row.financial_impact_status == "typed_cannot_infer"
        and row.what_would_change
        for row in pack.risk_contexts
    )
    assert all(not row.accepted_evidence_refs for row in pack.decision_cells)


def test_t05_product_methods_are_runtime_inputs_not_paid_quality_claims(
    tmp_path: Path,
) -> None:
    pack = S3BoundedGraphDecisionCellPackVersion.model_validate(
        _run_payload(tmp_path)["s3_bounded_graph_product_market_risk_pack"]
    )
    assert len(pack.product_industry_inputs) == len(pack.skill_contracts) == 3
    assert all(
        row["technical_signal_is_financial_fact"] is False
        and row["graph_or_product_numeric_authority"] is False
        and row["direct_evidence_authorized"] is False
        for row in pack.product_industry_inputs
    )
    assert all(
        row["authority_grants"] == []
        and row["model_execution_authorized"] is False
        and row["network_execution_authorized"] is False
        for row in pack.skill_contracts
    )
    assert all(
        row.future_T06_specialist_input_eligible is True
        and row.current_specialist_model_consumed is False
        for row in pack.decision_cells
    )
