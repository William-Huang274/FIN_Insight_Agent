from __future__ import annotations

import json
from pathlib import Path

from sec_agent.humanmade_gold_set_runtime import (
    assimilate_ai_semis_gold_depth_content_pack,
    build_pre_writer_humanmade_gold_set_gate,
    build_ai_semis_gold_depth_content_pack,
    compile_ai_semis_human_source_runtime_slots,
    compile_ai_semis_gold_specialist_judgment_materials,
    compile_negative_cases_to_failure_gates,
    compile_rubric_cases_to_vertical_playbook_contracts,
    materialize_ai_semis_human_source_rows,
    project_ai_semis_rows_to_investment_edges,
    run_briefing_pack_quality_gate,
    run_humanmade_gold_set_audit,
    run_research_lead_gold_depth_veto,
    synthetic_gold_briefing_fixture,
)
from sec_agent.memo_llm import MemoLLMConfig, route_memo_writer_llm


REPO_ROOT = Path(__file__).resolve().parents[1]
AGGREGATE_R7 = (
    REPO_ROOT
    / "eval/sec_cases/outputs/p33_gold_case_runs"
    / "p33_stepwise_aggregate_judgment_plan_after_required_item_gate_hardening_20260705_r7"
    / "p33_3_ai_semis_accelerator_dell_gold_case_v0_1"
    / "aggregate_judgment_plan_node_result.json"
)
WRITER_PAYLOAD = (
    REPO_ROOT
    / "eval/sec_cases/outputs/p33_gold_case_runs"
    / "p33_stepwise_memo_writer_payload_preflight_source_coverage_hardening_20260706_r1"
    / "p33_3_ai_semis_accelerator_dell_gold_case_v0_1"
    / "memo_writer_payload_preflight_summary.json"
)
ARTIFACT_AUDIT = REPO_ROOT / "docs/project_os/humanmade_gold_set_artifact_audit_v0_1.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_compiles_source_slots_rubric_contracts_and_negative_gates() -> None:
    source_slots = compile_ai_semis_human_source_runtime_slots()
    rubric_contracts = compile_rubric_cases_to_vertical_playbook_contracts()
    negative_gates = compile_negative_cases_to_failure_gates()

    assert source_slots["status"] == "pass_runtime_slots_compiled"
    assert source_slots["slot_count"] >= 10
    assert "official_product_architecture_spec" in source_slots["slot_type_counts"]
    assert "hyperscaler_capex_demand_pool" in source_slots["slot_type_counts"]
    assert rubric_contracts["contract_count"] == 8
    assert negative_gates["gate_count"] == 6


def test_gold_depth_content_pack_materializes_rows_edges_and_judgments() -> None:
    source_slots = compile_ai_semis_human_source_runtime_slots()
    rows = materialize_ai_semis_human_source_rows(source_slots)
    edges = project_ai_semis_rows_to_investment_edges(rows)
    materials = compile_ai_semis_gold_specialist_judgment_materials(rows, edges)

    assert rows["row_count"] >= 20
    assert rows["lane_counts"]["product_architecture_competition"] >= 5
    assert rows["lane_counts"]["dell_financial_quality_bridge"] >= 2
    assert rows["lane_counts"]["semicap_foundry_readthrough"] >= 4
    assert any("36 Grace CPUs" in row["fact"] for row in rows["rows"])
    assert any("GPU pass-through" in row["cannot_infer"] for row in rows["rows"])

    edge_roles = {edge["edge_investment_role"] for edge in edges["edges"]}
    assert "product_capability_to_oem_adoption" in edge_roles
    assert "substitution_and_pricing_pressure" in edge_roles
    assert "revenue_visibility_margin_quality_unresolved" in edge_roles
    assert "semicap_readthrough_by_mechanism" in edge_roles

    memo_slots = set(materials["memo_slot_counts"])
    assert "product_architecture_competition" in memo_slots
    assert "financial_quality" in memo_slots
    assert "semicap_readthrough" in memo_slots
    assert "market_price_in" in memo_slots
    assert "risk_counterevidence" in memo_slots
    assert all("Gold-depth" not in row["judgment"] for row in materials["materials"])


def test_current_p33_artifacts_fail_humanmade_gold_set_quality_gate() -> None:
    audit = run_humanmade_gold_set_audit(
        aggregate_state=_read(AGGREGATE_R7),
        writer_payload=_read(WRITER_PAYLOAD),
        artifact_audit=_read(ARTIFACT_AUDIT),
    )

    assert audit["status"] == "fail"
    assert audit["pre_writer_decision"]["allow_paid_memo_writer"] is False
    briefing = audit["briefing_pack_quality_gate"]
    failed_lanes = {row["lane_id"] for row in briefing["checks"] if row["status"] == "fail"}
    assert "product_architecture_competition" in failed_lanes
    assert "dell_financial_quality_bridge" in failed_lanes
    assert "market_expectation_price_in" in failed_lanes
    assert audit["research_lead_gold_depth_veto"]["status"] == "fail"


def test_gold_depth_content_pack_passes_depth_gate_and_lead_veto() -> None:
    state = build_ai_semis_gold_depth_content_pack()
    gate = run_briefing_pack_quality_gate(aggregate_state=state, artifact_audit={"artifact_metrics": {}, "gold_item_results": []})
    veto = run_research_lead_gold_depth_veto(aggregate_state=state)

    assert gate["status"] == "pass"
    assert gate["fail_count"] == 0
    assert gate["observations"]["gold_content_profile"]["row_count"] >= 20
    assert gate["observations"]["gold_content_profile"]["specialist_material_count"] >= 5
    assert veto["status"] == "pass"
    assert veto["writer_allowed"] is True


def test_humanmade_gold_set_audit_passes_when_runtime_consumes_content_pack() -> None:
    state = build_ai_semis_gold_depth_content_pack()
    audit = run_humanmade_gold_set_audit(
        aggregate_state=state,
        writer_payload={},
        artifact_audit={"artifact_metrics": {}, "gold_item_results": []},
    )

    assert audit["status"] == "pass"
    assert audit["pre_writer_decision"]["allow_paid_memo_writer"] is True
    assert audit["briefing_pack_quality_gate"]["status"] == "pass"
    assert audit["research_lead_gold_depth_veto"]["status"] == "pass"


def test_assimilates_gold_depth_content_pack_into_current_runtime_artifact() -> None:
    state = _read(AGGREGATE_R7)
    assimilated = assimilate_ai_semis_gold_depth_content_pack(state)
    audit = run_humanmade_gold_set_audit(
        aggregate_state=assimilated,
        writer_payload={},
        artifact_audit={"artifact_metrics": {}, "gold_item_results": []},
    )
    gate = build_pre_writer_humanmade_gold_set_gate(assimilated)

    assimilation = assimilated["p33_gold_depth_runtime_assimilation"]
    assert assimilation["status"] == "runtime_assimilated"
    assert "evidence_fusion_bundle.authority_rows" in assimilation["consumption_points"]
    assert "memo_logic_plan.required_item_answer_plan" in assimilation["consumption_points"]
    assert assimilated["evidence_fusion_bundle"]["summary"]["gold_depth_content_row_count"] >= 20
    assert assimilated["product_intelligence_graph_projection"]["edge_count"] >= 8
    assert assimilated["gold_specialist_judgment_materials"]["material_count"] >= 5
    assert any(
        str(card.get("judgment_card_id") or "").startswith("gold_depth_judgment:")
        for card in assimilated["memo_logic_plan"]["judgment_cards"]
    )
    assert any(
        row.get("bridge_id", "").startswith("gold_depth_bridge:")
        for row in assimilated["memo_logic_plan"]["evidence_to_thesis_bridge"]
    )
    assert audit["status"] == "pass"
    assert gate["status"] == "pass"
    assert gate["pre_writer_decision"]["allow_paid_memo_writer"] is True


def test_synthetic_gold_briefing_fixture_is_real_content_pack() -> None:
    state = synthetic_gold_briefing_fixture()

    assert state["artifact_type"] == "ai_semis_gold_depth_content_pack"
    assert state["human_source_runtime_rows"]["row_count"] >= 20
    assert state["product_intelligence_graph_projection"]["edge_count"] >= 8
    assert state["specialist_judgment_materials"]["material_count"] >= 5


def test_memo_writer_route_blocks_p33_case_before_paid_call_when_gold_gate_fails() -> None:
    state = _read(AGGREGATE_R7)

    def _should_not_call(**_: object) -> dict:
        raise AssertionError("Memo writer LLM should not be called before HumanmadeGoldSetAudit passes.")

    result = route_memo_writer_llm(
        state,
        config=MemoLLMConfig(max_repair_attempts=0),
        call_chat_completion=_should_not_call,
    )

    route = result["memo_route_result"]
    assert route["status"] == "blocked_by_humanmade_gold_set_audit"
    assert route["total_tokens"] == 0
    assert route["humanmade_gold_set_gate"]["status"] == "fail"
