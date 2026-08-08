from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s1_08_firecrawl_semantic_control import (
    RUN_SCOPE,
    S108FirecrawlSemanticControlError,
    build_terminal_result,
    evaluate_semantic_control,
    load_authority,
    load_plan,
    load_scoring_contract,
    normalize_firecrawl_response,
)


ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_plan_v1_0.json"
SCORING_PATH = ROOT / "configs/eval/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_scoring_v1_0.json"
VISIBLE_PATH = ROOT / "eval_sets/fin_0_1_3_same_evidence_v1/model_visible/shared_benchmark_evidence_pack_v1.json"
DECISION_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_domestic_provider_credential_readiness_and_firecrawl_control_authority_decision_v1_0.json"
PROOF_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_zero_call_proof_v1_0.json"
AUTHORITY_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_authority_v1_0.json"
A4_TERMINAL_PATH = ROOT / "artifacts/runtime/provider_market_scan/firecrawl_keyless_a4_customer_supply_en_20260808/terminal-result.json"
A4_ASSESSMENT_PATH = ROOT / "artifacts/runtime/provider_market_scan/firecrawl_keyless_a4_customer_supply_en_20260808/assessment.json"
EVALUATOR_PATH = ROOT / "scripts/releases/evaluate_fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control.py"
RESULT_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_result_v1_0.json"
ASSESSMENT_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_assessment_v1_0.json"
NEXT_SCOPE = "S1_08_DOMESTIC_PROVIDER_FRESH_CREDENTIAL_READINESS_AND_SAME_MATRIX_COMPARATOR_AUTHORITY_DECISION"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inputs() -> tuple[dict, dict, dict]:
    return (
        load_plan(PLAN_PATH),
        load_scoring_contract(SCORING_PATH),
        json.loads(VISIBLE_PATH.read_text(encoding="utf-8")),
    )


def _source_matches_owner(source_id: str, owner: str) -> bool:
    return f"SRC_{owner}_" in source_id


def _fake_terminal() -> dict:
    plan, scoring, visible = _inputs()
    source_by_id = {
        str(row["source_id"]): dict(row) for row in visible["source_registry"]
    }
    calls = []
    for row in plan["query_rows"]:
        targets = [
            source_id
            for source_id in scoring["target_sources_by_case_and_slot"][
                row["case_key"]
            ][row["evidence_slot_id"]]
            if _source_matches_owner(source_id, row["evidence_owner_entity_key"])
        ]
        locators = []
        for source_id in targets:
            source = source_by_id[source_id]
            locator_body = {
                "provider_rank": len(locators) + 1,
                "canonical_url": source["url"],
                "source_domain": source["url"].split("/")[2],
                "title": f"{row['owner_markers'][0]} {row['topic_markers'][0]} {source['title']}",
                "passage": f"{row['owner_markers'][0]} {row['topic_markers'][0]} primary disclosure",
                "published_at_raw": source["published_on"],
                "promotion_status": "candidate_locator_diagnostic_only",
                "evidence_promotion_allowed": False,
                "writer_citable": False,
                "financial_fact_authority": False,
                "numeric_authority": "none",
            }
            locators.append(
                {**locator_body, "locator_digest": canonical_digest(locator_body)}
            )
        while len(locators) < 5:
            rank = len(locators) + 1
            locator_body = {
                "provider_rank": rank,
                "canonical_url": f"https://independent-{row['case_key'].lower()}-{rank}.example/{row['ordinal']}",
                "source_domain": f"independent-{row['case_key'].lower()}-{rank}.example",
                "title": f"{row['owner_markers'][0]} {row['topic_markers'][0]} analysis",
                "passage": f"{row['owner_markers'][0]} {row['topic_markers'][0]} evidence",
                "published_at_raw": "2026-08-01",
                "promotion_status": "candidate_locator_diagnostic_only",
                "evidence_promotion_allowed": False,
                "writer_citable": False,
                "financial_fact_authority": False,
                "numeric_authority": "none",
            }
            locators.append(
                {**locator_body, "locator_digest": canonical_digest(locator_body)}
            )
        calls.append(
            {
                "ordinal": row["ordinal"],
                "intent_id": row["intent_id"],
                "case_key": row["case_key"],
                "evidence_slot_id": row["evidence_slot_id"],
                "evidence_owner_entity_key": row["evidence_owner_entity_key"],
                "language": row["language"],
                "status": "completed",
                "terminal_code": "response_materialized",
                "network_call_attempted": True,
                "http_status": 200,
                "request_capture": {"request_body": row["request_body"]},
                "provider_projection": {
                    "provider": "Firecrawl Search",
                    "provider_request_id": f"fixture-{row['ordinal']}",
                    "normalized_unique_locator_count": len(locators),
                    "published_date_count": len(locators),
                    "credits_used": 2,
                    "locators": locators,
                },
                "failure": {},
                "elapsed_ms": 100 + row["ordinal"],
                "capture_refs": {"fixture": True},
            }
        )
    return build_terminal_result(
        admission_id="fixture-firecrawl-semantic-control",
        source_commit="a" * 40,
        plan_digest=plan["plan_digest"],
        call_results=calls,
        elapsed_ms=3000,
    )


def test_plan_is_exactly_24_semantic_gold_blind_execution_units() -> None:
    plan = load_plan(PLAN_PATH)
    rows = plan["query_rows"]
    assert len(rows) == 24
    assert len({row["intent_id"] for row in rows}) == 24
    assert len({row["execution_unit_digest"] for row in rows}) == 24
    assert {row["case_key"] for row in rows} == {"DELL", "MU", "NVDA"}
    assert {row["evidence_slot_id"] for row in rows} == {
        "customer_demand_and_deployment_validation",
        "supply_chain_capacity_and_counterevidence",
    }
    serialized = json.dumps(rows, ensure_ascii=False)
    assert "https://" not in serialized
    assert "SRC_" not in serialized
    assert all(row["request_body"]["sources"] == ["web"] for row in rows)


def test_gold_or_url_mutation_in_plan_fails_closed(tmp_path: Path) -> None:
    plan = load_plan(PLAN_PATH)
    mutated = deepcopy(plan)
    mutated.pop("plan_digest")
    mutated["query_rows"][0]["query_text"] += " SRC_MSFT_Q3_FY26_CALL"
    mutated["query_rows"][0]["request_body"]["query"] = mutated["query_rows"][0][
        "query_text"
    ]
    mutated["plan_digest"] = canonical_digest(mutated)
    path = tmp_path / "mutated.json"
    path.write_text(json.dumps(mutated), encoding="utf-8")
    with pytest.raises(S108FirecrawlSemanticControlError, match="plan_row_invalid"):
        load_plan(path)


def test_normalizer_is_locator_only_deduplicated_and_non_promotable() -> None:
    projection = normalize_firecrawl_response(
        {
            "success": True,
            "creditsUsed": 2,
            "id": "fixture",
            "data": {
                "web": [
                    {
                        "url": "https://example.com/report/",
                        "title": "Report",
                        "description": "Evidence",
                        "position": 1,
                    },
                    {
                        "url": "https://example.com/report",
                        "title": "Duplicate",
                        "description": "Duplicate",
                        "position": 2,
                    },
                ]
            },
        }
    )
    assert projection["normalized_unique_locator_count"] == 1
    assert projection["credits_used"] == 2
    locator = projection["locators"][0]
    assert locator["evidence_promotion_allowed"] is False
    assert locator["financial_fact_authority"] is False
    assert locator["numeric_authority"] == "none"


def test_full_fake_matrix_passes_control_but_never_sourcehunter() -> None:
    plan, scoring, visible = _inputs()
    assessment = evaluate_semantic_control(
        result=_fake_terminal(),
        plan=plan,
        scoring_contract=scoring,
        visible_pack=visible,
    )
    assert assessment["status"] == "pass_control_lane"
    assert assessment["semantic_control_lane_qualified"] is True
    assert assessment["sourcehunter_integration_eligible"] is False
    assert assessment["domestic_provider_capability_established"] is False
    assert all(assessment["hard_gate_results"].values())
    assert assessment["aggregate"]["case_slot_target_in_pool"] == [6, 6]
    assert assessment["aggregate"]["credits_used"] == 48


def test_missing_one_case_slot_target_fails_before_ranking() -> None:
    plan, scoring, visible = _inputs()
    result = _fake_terminal()
    target_url = next(
        row["url"]
        for row in visible["source_registry"]
        if row["source_id"] == "SRC_MSFT_Q3_FY26_CALL"
    )
    body = deepcopy(result)
    body.pop("result_digest")
    for call in body["call_results"]:
        if (
            call["case_key"] == "DELL"
            and call["evidence_slot_id"]
            == "customer_demand_and_deployment_validation"
        ):
            locators = call["provider_projection"]["locators"]
            call["provider_projection"]["locators"] = [
                row for row in locators if row["canonical_url"] != target_url
            ]
    mutated = {**body, "result_digest": canonical_digest(body)}
    assessment = evaluate_semantic_control(
        result=mutated,
        plan=plan,
        scoring_contract=scoring,
        visible_pack=visible,
    )
    assert assessment["status"] == "fail_diagnostic_only"
    assert assessment["hard_gate_results"]["case_slot_target_in_pool_rate"] is False
    assert assessment["decision"] == "remain_diagnostic_only_no_reranker_rescue"


def test_decision_selects_semantic_only_and_never_persists_secret_values() -> None:
    decision = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
    assert decision["lane_decision"]["selected_lane"] == "semantic_open_web"
    assert decision["lane_decision"]["selected_execution_units"] == 24
    assert decision["lane_decision"]["combined_46_unit_execution_authorized"] is False
    assert decision["credential_readiness"]["credential_values_read_back_or_persisted"] is False
    assert decision["lane_decision"]["live_execution_authorized_by_this_decision"] is False


def test_zero_call_proof_binds_immutable_a4_capture_replay() -> None:
    proof = json.loads(PROOF_PATH.read_text(encoding="utf-8"))
    replay = proof["historical_capture_replay_binding"]
    assert replay["terminal_sha256"] == _sha256(A4_TERMINAL_PATH)
    assert replay["assessment_sha256"] == _sha256(A4_ASSESSMENT_PATH)
    assert replay["observed_exact_target_in_pool"] == [0, 6]
    assert proof["authority"]["network_calls"] == 0
    assert proof["authority"]["live_execution_authorized"] is False


def test_evaluator_loads_gold_only_after_terminal_guard() -> None:
    source = EVALUATOR_PATH.read_text(encoding="utf-8")
    guard = source.index("firecrawl_semantic_gold_load_before_terminal_forbidden")
    scoring_load = source.index("load_scoring_contract(args.scoring)")
    visible_load = source.index("args.visible_pack.read_text")
    assert guard < scoring_load
    assert guard < visible_load


def test_exact_live_authority_is_digest_bound_semantic_only_and_unconsumed() -> None:
    authority = load_authority(AUTHORITY_PATH)
    execution = authority["execution_contract"]
    assert authority["authorized_scope"] == RUN_SCOPE
    assert authority["status"] == "issued_unconsumed"
    assert execution["selected_lane"] == "semantic_open_web"
    assert execution["planned_execution_units"] == 24
    assert execution["provider_call_ceiling"] == 24
    assert execution["retry_ceiling"] == 0
    assert execution["precise_official_lane_allowed"] is False
    assert execution["combined_46_unit_execution_allowed"] is False
    assert execution["gold_load_before_aggregate_terminal_allowed"] is False


def test_consumed_exact_live_scope_is_blocked_and_domestic_handoff_is_allowed() -> None:
    from sec_agent.project_os_preflight import run_project_os_preflight

    preflight = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    assert preflight["status"] == "blocked"
    assert preflight["contract_errors"] == []
    assert preflight["scope_resolution"]["status"] == "registered"
    assert preflight["scope_resolution"]["operation_class"] == "diagnostic_search_execution"
    handoff = run_project_os_preflight(ROOT, run_scope=NEXT_SCOPE)
    assert handoff["status"] == "pass"
    assert handoff["contract_errors"] == []


def test_live_terminal_and_assessment_are_digest_bound_and_honest() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    result_body = dict(result)
    result_digest = result_body.pop("result_digest")
    assert result_digest == canonical_digest(result_body)
    assert result["status"] == "completed"
    assert result["admission_consumed"] is True
    assert result["observed_counts"] == {
        "planned_queries": 24,
        "terminalized_queries": 24,
        "provider_calls": 24,
        "network_calls": 24,
        "successful_calls": 24,
        "typed_failed_or_not_attempted_calls": 0,
        "retry_calls": 0,
        "model_calls": 0,
        "document_fetches": 0,
        "evidence_promotions": 0,
    }
    assert result["credits_used"] == 48
    assert result["capability_boundary"]["sourcehunter_integration_allowed"] is False
    assert result["capability_boundary"]["domestic_provider_capability_established"] is False

    assessment = json.loads(ASSESSMENT_PATH.read_text(encoding="utf-8"))
    assessment_body = dict(assessment)
    assessment_digest = assessment_body.pop("assessment_digest")
    assert assessment_digest == canonical_digest(assessment_body)
    assert assessment["result_digest"] == result_digest
    assert assessment["status"] == "fail_diagnostic_only"
    assert assessment["semantic_control_lane_qualified"] is False
    assert assessment["sourcehunter_integration_eligible"] is False
    assert assessment["aggregate"]["topical_useful_count"] == 133
    assert assessment["aggregate"]["topical_useful_denominator"] == 240
    assert assessment["aggregate"]["case_slot_target_in_pool"] == [5, 6]
    assert assessment["aggregate"]["matched_target_date_observations"] == 6
    assert assessment["aggregate"]["matched_target_date_accuracy"] == 0.0
    assert assessment["aggregate"]["credits_used"] == 48
    assert assessment["aggregate"]["latency_ms"]["p95"] == 6877
    assert assessment["hard_gate_results"]["case_slot_target_in_pool_rate"] is False
    assert assessment["hard_gate_results"]["matched_target_date_accuracy"] is False
    assert assessment["decision"] == "remain_diagnostic_only_no_reranker_rescue"
