from __future__ import annotations

from sec_agent.humanmade_gold_set_runtime import (
    build_ai_semis_fresh_all_specialist_gold_pass,
    build_multicase_goldset_evidence_depth_packs,
    compile_negative_gold_failure_fixtures,
    run_multicase_goldset_no_paid_audit,
)


def test_multicase_goldset_evidence_depth_packs_cover_all_cases() -> None:
    packs = build_multicase_goldset_evidence_depth_packs()

    assert packs["status"] == "pass"
    assert packs["case_count"] == 15
    assert packs["artifact_ready_count"] == 15
    assert packs["case_type_counts"]["deep_gold_case"] == 1
    assert packs["case_type_counts"]["rubric_gold_case"] == 8
    assert packs["case_type_counts"]["negative_gold_case"] == 6
    for pack in packs["packs"]:
        assert pack["status"] == "pass"
        assert pack["evidence_row_count"] >= 1
        assert pack["runtime_consumers"]
        assert pack["source_boundary"]


def test_rubric_packs_are_answer_exemplar_backed_not_empty_rules() -> None:
    packs = build_multicase_goldset_evidence_depth_packs()
    rubric_packs = [row for row in packs["packs"] if row["case_type"] == "rubric_gold_case"]

    assert len(rubric_packs) == 8
    for pack in rubric_packs:
        assert pack["answer_exemplar"]
        assert len(pack["required_items"]) >= 3
        assert pack["evidence_row_count"] >= len(pack["required_items"])
        assert any("Gold exemplar anchor" in row["fact"] for row in pack["evidence_rows"])
        assert "not a claim that live sector-specific retrieval/parser rows already exist" in pack["source_boundary"]


def test_ai_semis_fresh_all_specialist_gold_pass_is_not_targeted_composite() -> None:
    fresh = build_ai_semis_fresh_all_specialist_gold_pass()

    assert fresh["status"] == "pass"
    assert fresh["fresh_scope"] == "no_paid_fresh_projection_from_current_gold_depth_content_pack"
    assert fresh["role_count"] == 5
    assert fresh["role_pass_count"] == 5
    roles = {row["role_id"]: row for row in fresh["role_outputs"]}
    assert set(roles) == {
        "product_technology_analyst",
        "fundamental_analyst",
        "industry_supply_chain_analyst",
        "market_valuation_analyst",
        "risk_counterevidence_analyst",
    }
    for row in roles.values():
        assert row["status"] == "pass"
        assert row["judgment_candidates"]
        assert row["evidence_refs"]
        assert "No historical targeted specialist composite is reused" in row["freshness_boundary"]


def test_negative_failure_fixtures_target_aggregate_writer_and_final_memo() -> None:
    fixtures = compile_negative_gold_failure_fixtures()

    assert fixtures["status"] == "pass"
    assert fixtures["fixture_count"] == 6
    for fixture in fixtures["fixtures"]:
        assert fixture["status"] == "pass"
        assert fixture["target_artifact_stages"] == ["aggregate", "writer_payload", "final_memo"]
        assert fixture["correct_response_pattern"]
        assert "FinalVerifier.deterministic_failure_gate" in fixture["runtime_consumers"]


def test_multicase_no_paid_audit_passes_artifact_scope_without_paid_runs() -> None:
    audit = run_multicase_goldset_no_paid_audit()

    assert audit["status"] == "pass"
    assert audit["metrics"]["case_count"] == 15
    assert audit["metrics"]["artifact_ready_count"] == 15
    assert audit["metrics"]["fresh_all_specialist_pass_count"] == 1
    assert audit["metrics"]["negative_fixture_pass_count"] == 6
    assert audit["metrics"]["blocking_case_count"] == 0
    assert "paid_llm" in audit["scope"]["not_run"]
    assert "full_chain" in audit["scope"]["not_run"]
    assert audit["pre_writer_decision"]["allow_paid_memo_writer"] is False
