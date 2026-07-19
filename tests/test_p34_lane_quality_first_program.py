import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_json(relative_path: str):
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def test_p34_ai_semis_rubric_has_quality_questions_and_bad_patterns():
    rubric = _load_json("docs/project_os/p34_ai_semis_lane_research_quality_rubric_v0_1.json")

    assert rubric["schema_version"] == "fin_insight_lane_research_quality_rubric_v0_1"
    assert rubric["lane"] == "AI/Semis"
    assert rubric["status"] == "active_quality_contract_documented_not_runtime_injected"
    assert len(rubric["core_questions"]) >= 7
    assert any("SKU revenue" in pattern for pattern in rubric["bad_answer_patterns"])
    assert "ai_capex_demand_pool" in rubric["minimum_analyst_depth"]["must_have_judgment_chains"]


def test_p34_ai_semis_judgment_chain_registry_covers_required_chains():
    registry = _load_json("docs/project_os/p34_ai_semis_judgment_chain_registry_v0_1.json")
    chain_ids = {chain["chain_id"] for chain in registry["chains"]}

    expected = {
        "jc_ai_capex_demand_pool",
        "jc_accelerator_architecture_competition",
        "jc_customer_deployment_oem_adoption",
        "jc_dell_ai_server_financial_quality",
        "jc_foundry_semicap_readthrough",
        "jc_market_price_in_capital_feedback",
        "jc_counter_thesis_what_would_change",
    }
    assert expected <= chain_ids
    for chain in registry["chains"]:
        assert chain["business_mechanism"]
        assert chain["minimum_quality_bar"]
        assert chain["writer_must_say"]


def test_p34_ai_semis_slot_contracts_map_all_p33_rows_to_quality_chains():
    mapping = _load_json("docs/project_os/p34_ai_semis_evidence_slot_contract_mapping_v0_1.json")
    p33_backfill = _load_json("docs/project_os/p33_goldset_live_source_backfill_v0_1.json")

    p33_ai_semis_rows = [
        row for row in p33_backfill["rows"] if row.get("case_id") == "ai_semis_dell_nvda_anchor_v0_1"
    ]
    p33_ids = {row["evidence_row_id"] for row in p33_ai_semis_rows}
    mapped_ids = {row["evidence_row_id"] for row in mapping["evidence_slot_contracts"]}

    assert len(p33_ids) == 20
    assert p33_ids == mapped_ids
    assert mapping["metrics"]["mapped_to_judgment_chain_count"] == 20
    for row in mapping["evidence_slot_contracts"]:
        assert row["judgment_chain_ids"]
        assert row["quality_role"]
        assert row["forbidden_substitutes"]
        assert row["required_fields"]
        assert row["source_route_family"]
        assert row["promotion_rule"]
        assert row["cannot_infer"]


def test_p34_slot_contract_preserves_strict_live_ready_count_from_p33():
    mapping = _load_json("docs/project_os/p34_ai_semis_evidence_slot_contract_mapping_v0_1.json")
    status_counts = {}
    for row in mapping["evidence_slot_contracts"]:
        status_counts[row["p33_backfill_status"]] = status_counts.get(row["p33_backfill_status"], 0) + 1

    assert status_counts["live_runtime_ready"] == 4
    assert status_counts["route_candidate_only_parser_lineage_pending"] == 1
    assert status_counts["source_route_candidate_weak_not_bound"] == 13
    assert status_counts["case_binding_required_before_live_lookup"] == 2
