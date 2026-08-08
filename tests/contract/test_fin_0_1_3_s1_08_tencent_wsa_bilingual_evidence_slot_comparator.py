from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.project_os_preflight import run_project_os_preflight
from sec_agent.s1_08_tencent_wsa_bilingual_evidence_slot_comparator import (
    CASES,
    LANGUAGES,
    RUN_SCOPE,
    SLOTS,
    TencentWSABilingualComparatorError,
    build_comparator_terminal_result,
    evaluate_comparator,
    load_comparator_authority,
    load_query_plan,
    load_scoring_contract,
)


ROOT = Path(__file__).resolve().parents[2]
QUERY_PLAN_PATH = (
    ROOT
    / "configs/runtime/fin_ia_0_1_3_s1_08_tencent_wsa_bilingual_evidence_slot_query_plan_v1_0.json"
)
SCORING_PATH = (
    ROOT
    / "configs/eval/fin_ia_0_1_3_s1_08_tencent_wsa_bilingual_evidence_slot_scoring_contract_v1_0.json"
)
VISIBLE_PATH = (
    ROOT
    / "eval_sets/fin_0_1_3_same_evidence_v1/model_visible/shared_benchmark_evidence_pack_v1.json"
)
HIDDEN_PATH = (
    ROOT
    / "eval_sets/fin_0_1_3_same_evidence_v1/evaluator_only/hidden_gold_scoring_objects_v1.json"
)
R4_RESULT_PATH = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_tencent_wsa_standard_tier_r4_result_v1_0.json"
)
R4_ASSESSMENT_PATH = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_tencent_wsa_standard_tier_r4_quality_assessment_v1_0.json"
)
AUTHORITY_PATH = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_tencent_wsa_bilingual_evidence_slot_comparator_authority_v1_0.json"
)
LIVE_RESULT_PATH = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_tencent_wsa_bilingual_evidence_slot_comparator_result_v1_0.json"
)
LIVE_ASSESSMENT_PATH = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_tencent_wsa_bilingual_evidence_slot_comparator_assessment_v1_0.json"
)


def _inputs() -> tuple[dict, dict, dict, dict]:
    return (
        load_query_plan(QUERY_PLAN_PATH),
        load_scoring_contract(SCORING_PATH),
        json.loads(VISIBLE_PATH.read_text(encoding="utf-8")),
        json.loads(HIDDEN_PATH.read_text(encoding="utf-8")),
    )


def _fake_terminal() -> dict:
    plan, scoring, visible, _ = _inputs()
    source_by_id = {row["source_id"]: row for row in visible["source_registry"]}
    rows = []
    for ordinal, query in enumerate(plan["query_rows"], start=1):
        target_ids = scoring["target_sources_by_case_and_slot"][query["case_key"]][
            query["slot_id"]
        ]
        case_marker = query["case_markers"][0]
        slot_marker = query["slot_markers"][0]
        locators = []
        for rank, source_id in enumerate(target_ids, start=1):
            source = source_by_id[source_id]
            locator_body = {
                "provider_rank": rank,
                "canonical_url": source["url"],
                "source_domain": source["url"].split("/")[2],
                "title": f"{case_marker} {slot_marker} {source['title']}",
                "published_at_raw": source["published_on"],
                "passage": f"{case_marker} {slot_marker} primary source",
                "site": source["publisher"],
                "provider_score": 1.0,
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
                "canonical_url": (
                    f"https://independent{rank}-{ordinal}.com/{query['query_id'].lower()}"
                ),
                "source_domain": f"independent{rank}-{ordinal}.com",
                "title": f"{case_marker} {slot_marker} independent analysis",
                "published_at_raw": "2026-08-01",
                "passage": f"{case_marker} {slot_marker} evidence",
                "site": f"Independent {rank}",
                "provider_score": 0.5,
                "promotion_status": "candidate_locator_diagnostic_only",
                "evidence_promotion_allowed": False,
                "writer_citable": False,
                "financial_fact_authority": False,
                "numeric_authority": "none",
            }
            locators.append(
                {**locator_body, "locator_digest": canonical_digest(locator_body)}
            )
        rows.append(
            {
                "ordinal": ordinal,
                "query_id": query["query_id"],
                "case_key": query["case_key"],
                "slot_id": query["slot_id"],
                "language": query["language"],
                "status": "completed",
                "terminal_code": "response_materialized",
                "network_call_attempted": True,
                "request_capture": {"request_body": {"Query": query["query_text"]}},
                "provider_projection": {
                    "provider_version": "standard",
                    "normalized_unique_locator_count": len(locators),
                    "published_date_count": len(locators),
                    "locators": locators,
                },
                "failure": {},
                "elapsed_ms": 100 + ordinal,
                "capture_refs": {"fixture": True},
            }
        )
    return build_comparator_terminal_result(
        admission_id="fixture-comparator",
        source_commit="a" * 40,
        query_plan_digest=canonical_digest(plan),
        call_results=rows,
        elapsed_ms=3000,
        sdk_version="3.1.152",
    )


def test_query_plan_is_complete_gold_blind_and_query_only() -> None:
    plan = load_query_plan(QUERY_PLAN_PATH)
    rows = plan["query_rows"]
    assert len(rows) == 24
    assert {
        (row["case_key"], row["slot_id"], row["language"]) for row in rows
    } == {
        (case_key, slot_id, language)
        for case_key in CASES
        for slot_id in SLOTS
        for language in LANGUAGES
    }
    serialized = json.dumps(rows, ensure_ascii=False)
    assert "https://" not in serialized
    assert "SRC_" not in serialized
    assert "DELL_E" not in serialized
    assert plan["budget"]["maximum_documented_cost_cny"] == 1.104


def test_gold_identifier_mutation_in_query_plan_fails_closed(tmp_path: Path) -> None:
    plan = load_query_plan(QUERY_PLAN_PATH)
    mutated = deepcopy(plan)
    mutated["query_rows"][0]["query_text"] += " SRC_DELL_Q1_FY27_CALL"
    path = tmp_path / "mutated.json"
    path.write_text(json.dumps(mutated), encoding="utf-8")
    with pytest.raises(
        TencentWSABilingualComparatorError,
        match="gold_blind_query_invalid",
    ):
        load_query_plan(path)


def test_scoring_contract_keeps_candidate_gate_before_reranker() -> None:
    scoring = load_scoring_contract(SCORING_PATH)
    gates = scoring["hard_gates_before_sourcehunter_integration"]
    assert gates["case_slot_target_in_pool_rate_across_language_union"] == 1.0
    assert gates["matched_target_date_accuracy"] == 1.0
    assert gates["reranker_or_document_fetch_during_comparator"] == 0
    assert scoring["decision_rules"]["target_in_pool_fails"].endswith(
        "before_ranking"
    )


def test_fake_three_case_bilingual_matrix_can_pass_every_preregistered_gate() -> None:
    plan, scoring, visible, hidden = _inputs()
    result = _fake_terminal()
    assessment = evaluate_comparator(
        result=result,
        query_plan=plan,
        scoring_contract=scoring,
        visible_pack=visible,
        hidden_scoring=hidden,
    )
    assert assessment["status"] == "pass"
    assert assessment["sourcehunter_integration_eligible"] is True
    assert all(assessment["hard_gate_results"].values())
    assert (
        assessment["combined_product_hidden_target_match"]["summary"][
            "target_in_pool_recall"
        ]
        == 1.0
    )
    assert assessment["aggregate"]["documented_total_cost_cny"] == 1.104


def test_missing_both_languages_for_one_slot_blocks_before_ranking() -> None:
    plan, scoring, visible, hidden = _inputs()
    result = _fake_terminal()
    target_ids = set(
        scoring["target_sources_by_case_and_slot"]["DELL"][
            "supply_chain_capacity_and_counterevidence"
        ]
    )
    source_urls = {
        row["url"]
        for row in visible["source_registry"]
        if row["source_id"] in target_ids
    }
    body = deepcopy(result)
    body.pop("result_digest")
    for call in body["call_results"]:
        if (
            call["case_key"] == "DELL"
            and call["slot_id"] == "supply_chain_capacity_and_counterevidence"
        ):
            call["provider_projection"]["locators"] = [
                row
                for row in call["provider_projection"]["locators"]
                if row["canonical_url"] not in source_urls
            ]
            call["provider_projection"]["normalized_unique_locator_count"] = len(
                call["provider_projection"]["locators"]
            )
            call["provider_projection"]["published_date_count"] = len(
                call["provider_projection"]["locators"]
            )
    mutated = {**body, "result_digest": canonical_digest(body)}
    assessment = evaluate_comparator(
        result=mutated,
        query_plan=plan,
        scoring_contract=scoring,
        visible_pack=visible,
        hidden_scoring=hidden,
    )
    assert assessment["status"] == "fail_diagnostic_only"
    assert assessment["sourcehunter_integration_eligible"] is False
    assert (
        assessment["hard_gate_results"][
            "case_slot_target_in_pool_rate_across_language_union"
        ]
        is False
    )
    assert assessment["decision"] == "remain_diagnostic_only_no_reranker_rescue"


def test_r4_assessment_is_digest_bound_and_does_not_overclaim_standard() -> None:
    result = json.loads(R4_RESULT_PATH.read_text(encoding="utf-8"))
    assessment = json.loads(R4_ASSESSMENT_PATH.read_text(encoding="utf-8"))
    body = dict(assessment)
    digest = body.pop("assessment_digest")
    assert digest == canonical_digest(body)
    assert assessment["result_digest"] == result["result_digest"]
    quality = assessment["research_quality_assessment"]
    assert quality["topical_useful_at_10"]["count"] == 10
    assert quality["evidence_eligible_useful_at_10"]["count"] == 0
    assert quality["target_in_pool"]["DELL_hidden_target_groups_satisfied"] == 0
    assert quality["source_diversity"]["independent_publisher_ecosystem_count"] == 1
    assert assessment["stage_and_promotion_boundary"][
        "sourcehunter_integration_allowed"
    ] is False


def test_comparator_authority_is_bounded_and_non_promotable() -> None:
    authority = load_comparator_authority(AUTHORITY_PATH)
    execution = authority["execution_contract"]
    assert authority["authorized_scope"] == RUN_SCOPE
    assert execution["provider_call_ceiling"] == 24
    assert execution["network_call_ceiling"] == 24
    assert execution["retry_ceiling"] == 0
    assert execution["maximum_documented_cost_cny"] == 1.104
    assert execution["document_fetch_ceiling"] == 0
    assert execution["evidence_promotion_allowed"] is False
    assert execution["sourcehunter_integration_allowed"] is False


def test_consumed_comparator_scope_is_registered_but_no_longer_authorized() -> None:
    preflight = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    assert preflight["status"] == "blocked"
    assert preflight["scope_resolution"]["status"] == "registered"
    assert preflight["scope_resolution"]["owner_stage"] == "S1"
    assert preflight["contract_errors"] == []
    assert preflight["open_full_chain_blocker_count"] >= 1
    assert all(
        RUN_SCOPE not in blocker["allowed_run_scopes"]
        for blocker in preflight["open_full_chain_blockers"]
    )


def test_live_comparator_terminal_and_assessment_are_immutable_and_honest() -> None:
    result = json.loads(LIVE_RESULT_PATH.read_text(encoding="utf-8"))
    assessment = json.loads(LIVE_ASSESSMENT_PATH.read_text(encoding="utf-8"))

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
        "typed_failed_calls": 0,
        "retry_calls": 0,
        "model_calls": 0,
        "document_fetches": 0,
        "evidence_promotions": 0,
    }
    assert len(result["call_results"]) == 24
    assert {
        row["provider_projection"]["provider_version"]
        for row in result["call_results"]
    } == {"standard"}
    assert result["capability_boundary"]["ranking_or_reranker_allowed"] is False
    assert result["capability_boundary"]["sourcehunter_integration_allowed"] is False

    assessment_body = dict(assessment)
    assessment_digest = assessment_body.pop("assessment_digest")
    assert assessment_digest == canonical_digest(assessment_body)
    assert assessment["result_digest"] == result_digest
    assert assessment["status"] == "fail_diagnostic_only"
    assert assessment["sourcehunter_integration_eligible"] is False
    assert assessment["decision"] == "remain_diagnostic_only_no_reranker_rescue"
    assert assessment["aggregate"][
        "case_slot_target_in_pool_rate_across_language_union"
    ] == 0.0
    assert assessment["combined_product_hidden_target_match"]["summary"][
        "target_in_pool_recall"
    ] == 0.0
    assert all(
        row["mean_evidence_eligible_useful_at_10"] == 0.0
        for row in assessment["case_language_summaries"]
    )
    assert assessment["aggregate"]["documented_total_cost_cny"] == 1.104
    assert assessment["aggregate"]["latency_ms"]["p95"] == 941
    assert assessment["hard_gate_results"][
        "case_slot_target_in_pool_rate_across_language_union"
    ] is False
    assert assessment["hard_gate_results"][
        "reranker_or_document_fetch_during_comparator"
    ] is True
