from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from sec_agent.langgraph_orchestrator import (
    S3SpecialistLeadCrossCellPackVersion,
    consume_s3_specialist_lead_cross_cell_pack,
    decide_s3_parallel_judgment_commit,
    decide_s3_targeted_repair_admission,
)
from tests.contract.test_fin_0_1_s3_t04_financial_numeric_fundamental_pack import (
    _run_payload,
)


RELEASES = ROOT / "configs" / "releases"
T06 = (
    RELEASES
    / "fin_ia_0_1_s3_t06_specialist_lead_cross_cell_synthesis_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
ROOT_CAUSES = ROOT / "docs" / "project_os" / "root_cause_issue_ledger.jsonl"


def _latest_root_causes() -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for line in ROOT_CAUSES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            latest[row["issue_id"]] = row
    return latest


def _pack(payload: dict[str, Any]) -> S3SpecialistLeadCrossCellPackVersion:
    return S3SpecialistLeadCrossCellPackVersion.model_validate(
        payload["s3_specialist_lead_cross_cell_pack"]
    )


def _consume(
    payload: dict[str, Any], pack: S3SpecialistLeadCrossCellPackVersion
) -> tuple[dict[str, Any], ...]:
    return consume_s3_specialist_lead_cross_cell_pack(
        pack,
        runtime_plan=payload["s3_runtime_plan"],
        evidence_route_plan=payload["s3_evidence_route_plan"],
        financial_pack=payload["s3_financial_numeric_and_fundamental_pack"],
        graph_pack=payload["s3_bounded_graph_product_market_risk_pack"],
    )


def test_t06_contract_advances_only_to_unapproved_t07() -> None:
    contract = json.loads(T06.read_text(encoding="utf-8"))
    backlog = json.loads(BACKLOG.read_text(encoding="utf-8"))
    root = _latest_root_causes()[
        "RC-P36-029-aggregate-judgment-planner-preserves-claims-but-not-decision-surface-adjudication"
    ]
    assert contract["status"] == (
        "pass_after_independent_review_T07_ready_pending_separate_authorization"
    )
    assert contract["authority"]["S3_T06_zero_call_deterministic_fixture_authorized"] is True
    assert contract["authority"]["S3_T07_execution_authorized"] is False
    assert contract["implementation"]["specialist_judgment_count"] == 3
    assert contract["implementation"]["lead_cross_cell_dependency_count"] == 3
    assert contract["implementation"]["targeted_repair_ticket_count"] == 3
    assert backlog["next_action"]["item_id"] == (
        "S3-T09-EXACT-THREE-CELL-DEEPSEEK-LIVE-EXECUTION"
    )
    assert backlog["next_action"]["S3_T08_repair_execution_authorized"] is True
    assert backlog["next_action"]["S3_T09_execution_authorized"] is False
    assert root["verification_result"]["runtime_injected"] is True
    assert root["verification_result"]["node_level_consumed"] is True
    assert root["full_chain_blocker"] is True


def test_t06_runtime_persists_same_run_pack_and_four_consumption_receipts(
    tmp_path: Path,
) -> None:
    payload = _run_payload(tmp_path)
    pack = _pack(payload)
    receipts = _consume(payload, pack)
    assert payload["s3_specialist_lead_consumption_receipts"] == list(receipts)
    assert len(receipts) == 4
    assert pack.research_run_id == payload["s3_runtime_plan"]["research_run_id"]
    assert {row["target_node"] for row in receipts} == {
        "domain_specialist",
        "research_lead",
    }


def test_t06_three_specialists_preserve_fact_explanation_and_judgment_layers(
    tmp_path: Path,
) -> None:
    pack = _pack(_run_payload(tmp_path))
    expected_cells = (
        "demand_authenticity_and_sustainability",
        "value_and_profit_capture",
        "bottleneck_counterevidence_and_what_would_change",
    )
    assert tuple(row.program_cell_id for row in pack.specialist_judgments) == expected_cells
    demand, value, risk = pack.specialist_judgments
    assert demand.fact_layer.fact_statements == ()
    assert risk.fact_layer.fact_statements == ()
    assert len(value.fact_layer.fact_statements) == 2
    assert len(value.fact_layer.deterministic_numeric_refs) == 2
    assert value.fact_layer.accepted_evidence_refs == ()
    assert len(value.fact_layer.deterministic_numeric_source_refs) == 3
    for judgment in pack.specialist_judgments:
        assert judgment.fact_layer.program_cell_id == judgment.program_cell_id
        assert judgment.explanation_layer.program_cell_id == judgment.program_cell_id
        assert judgment.decision_layer.program_cell_id == judgment.program_cell_id
        assert judgment.fact_layer.excluded_candidate_or_graph_refs
        assert judgment.explanation_layer.explanation_is_fact_authority is False
        assert judgment.decision_layer.remaining_gaps
        assert judgment.decision_layer.what_would_change
        assert judgment.specialist_model_consumed is False


def test_t06_lead_adds_dependency_conflict_and_variant_view_not_concatenation(
    tmp_path: Path,
) -> None:
    lead = _pack(_run_payload(tmp_path)).lead_synthesis
    assert len(lead.specialist_judgment_refs) == 3
    assert len(lead.dependencies) == 3
    assert len(lead.conflicts) == 3
    assert lead.synthesis_adds_new_adjudication is True
    assert lead.text_concatenation_only is False
    assert "company-level profitability" in lead.variant_view
    assert "not an admissible investment Alpha" in lead.variant_view
    assert lead.writer_admission_recommended is False
    assert all(row.numeric_override_authorized is False for row in lead.conflicts)


def test_t06_repairs_route_to_earliest_owner_and_repeat_fingerprint_stops(
    tmp_path: Path,
) -> None:
    pack = _pack(_run_payload(tmp_path))
    by_failure = {row.failure_type: row for row in pack.targeted_repairs}
    assert set(by_failure) == {"unsupported_claim", "numeric_conflict", "missing_source"}
    assert by_failure["unsupported_claim"].earliest_owner_ref.startswith(
        "src.sec_agent.langgraph_orchestrator:"
    )
    assert by_failure["numeric_conflict"].earliest_owner_ref.startswith(
        "src.sec_agent.canonical_runtime.parser_numeric:"
    )
    assert by_failure["missing_source"].earliest_owner_ref.startswith(
        "apps.workbench.backend.application.evidence_service:"
    )
    assert all(row.changed_dimensions for row in pack.targeted_repairs)
    admitted = [
        row
        for row in pack.repair_admission_decisions
        if row.decision == "admit_changed_targeted_repair"
    ]
    stopped = [
        row
        for row in pack.repair_admission_decisions
        if row.decision == "stop_repeated_same_fingerprint_without_new_information"
    ]
    assert len(admitted) == 3
    assert len(stopped) == 1
    assert stopped[0].failure_fingerprint == by_failure["unsupported_claim"].failure_fingerprint
    assert stopped[0].repair_ticket_ref is None
    assert stopped[0].execution_authorized is False

    direct = decide_s3_targeted_repair_admission(
        failure_fingerprint="same-fingerprint",
        matching_prior_failure_count=2,
        changed_dimensions=(),
        repair_ticket_ref="repair:v1",
    )
    assert direct.decision == "stop_repeated_same_fingerprint_without_new_information"


def test_t06_stale_or_late_parallel_output_cannot_commit_current_head(
    tmp_path: Path,
) -> None:
    decisions = _pack(_run_payload(tmp_path)).parallel_commit_decisions
    assert decisions[0].probe == "matching_snapshot"
    assert decisions[0].current_head_commit_authorized is True
    assert decisions[0].canonical_head_mutation_executed is False
    assert decisions[1].decision == "quarantine_stale_output"
    assert decisions[1].current_head_commit_authorized is False
    assert decisions[2].decision == "quarantine_late_superseded_output"
    assert decisions[2].current_head_commit_authorized is False

    late = decide_s3_parallel_judgment_commit(
        probe="late_superseded_output",
        current_head_dependency_digest="current",
        output_dependency_digest="current",
        output_arrival_status="late_after_supersession",
    )
    assert late.current_head_commit_authorized is False


def test_t06_consumer_recompiles_full_pack_and_rejects_fact_layer_tamper(
    tmp_path: Path,
) -> None:
    payload = _run_payload(tmp_path)
    pack = _pack(payload)
    demand = pack.specialist_judgments[0]
    tampered_fact = demand.fact_layer.model_copy(
        update={"fact_statements": ("candidate context proves durable demand",)}
    )
    tampered_demand = demand.model_copy(update={"fact_layer": tampered_fact})
    tampered = pack.model_copy(
        update={"specialist_judgments": (tampered_demand, *pack.specialist_judgments[1:])}
    )
    with pytest.raises(ValueError, match="s3_specialist_lead_pack_recompile_mismatch"):
        _consume(payload, tampered)
