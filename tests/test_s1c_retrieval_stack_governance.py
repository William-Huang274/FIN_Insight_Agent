from __future__ import annotations

import json
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1c_retrieval_stack_governance_v1_0.json"
)
TEST_PRECUT = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1c_retrieval_stack_test_precut_manifest_v1_0.json"
)


def _policy() -> dict[str, object]:
    return json.loads(POLICY.read_text(encoding="utf-8"))


def test_database_lane_is_first_class_and_stage_owned() -> None:
    payload = _policy()
    database = payload["database_lane"]
    ownership = payload["stage_ownership"]

    assert database["mandatory"] is True
    assert (
        database["current_active_baseline_audit"][
            "authoritative_company_financial_fact_mart"
        ]
        == "absent_from_current_active_runtime"
    )
    assert (
        database["prebaseline_historical_evidence_only"][
            "successor_latest_available_annual_exact_sql"
        ]
        == "9/9"
    )
    assert (
        database["prebaseline_historical_evidence_only"][
            "successor_current_quarter_exact_sql"
        ]
        == "0/6_typed_refresh_gap"
    )
    assert "EvidenceRequest_to_query_family_and_route_plan" in ownership["S1"]
    assert "authoritative_company_financial_fact_mart" in ownership["S2"]


def test_retrieval_bakeoff_covers_methods_without_granting_authority() -> None:
    payload = _policy()
    candidates = payload["retrieval_stack_candidates"]
    authority = payload["authority"]

    assert {
        "bm25_lexical_baseline",
        "bge_m3_dense_shadow",
        "bge_m3_learned_sparse_shadow",
        "bge_m3_multi_vector_shadow",
        "qwen3_embedding_0_6b_instruction_aware_shadow",
    }.issubset(candidates["candidate_lanes"])
    assert candidates["reranker_candidates"] == [
        "BAAI/bge-reranker-v2-m3",
        "Qwen/Qwen3-Reranker-0.6B",
    ]
    assert candidates["evidence_authority"] == "Evidence_Gate_only"
    assert authority["runtime_route_promoted"] is False
    assert authority["fine_tuning_authorized"] is False


def test_holdout_and_query_object_repairs_precede_model_selection() -> None:
    payload = _policy()
    evaluation = payload["evaluation_governance"]
    sequence = payload["approved_sequence"]

    assert evaluation["observed_validation_cases_not_pristine_test"] == [
        "ORCL",
        "ASML",
        "ANET",
    ]
    assert evaluation["effect_seeking_model_run_authorized"] is False
    assert sequence[:3] == [
        "freeze_retrieval_stack_database_lane_error_taxonomy_and_new_holdout_manifest",
        "split_query_families_and_compile_claim_table_context_views",
        "same_corpus_multi_retriever_bakeoff",
    ]
    assert payload["query_and_object_successor"]["training_authority"] is False


def test_database_and_text_routes_split_mixed_research_requests() -> None:
    payload = _policy()
    routing = payload["database_lane"]["routing_rules"]

    assert routing["exact_metric_period_unit_PIT_request"] == (
        "compile_to_typed_exact_fact_lookup"
    )
    assert routing["narrative_mechanism_risk_guidance_request"] == (
        "compile_to_text_and_graph_retrieval_lanes"
    )
    assert routing["mixed_numeric_and_narrative_request"].startswith(
        "split_into_sibling_fact_and_evidence_requests"
    )
    assert routing["text_table_numeric_authority"].endswith(
        "source_bound_typed_NumericFact"
    )


def test_business_error_taxonomy_requires_concrete_examples() -> None:
    payload = _policy()
    taxonomy = payload["business_error_taxonomy"]

    assert "wrong_case_subject" in taxonomy["hard_scope_errors"]
    assert "route_did_not_recall_available_target" in taxonomy[
        "candidate_generation_errors"
    ]
    assert "semantic_neighbor_wrong_evidence_role" in taxonomy[
        "ranking_and_role_errors"
    ]
    assert "text_candidate_treated_as_exact_numeric_authority" in taxonomy[
        "authority_errors"
    ]
    assert "concrete business-language example" in taxonomy[
        "reporting_rule"
    ]


def test_new_test_precut_is_unseen_frozen_and_not_trainable() -> None:
    payload = json.loads(TEST_PRECUT.read_text(encoding="utf-8"))
    frozen = payload["frozen_payload"]
    encoded = json.dumps(
        frozen,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    assert hashlib.sha256(encoded).hexdigest() == payload["frozen_payload_sha256"]
    assert [row["ticker"] for row in frozen["issuer_time_cases"]] == [
        "HPQ",
        "AVGO",
        "INTC",
    ]
    assert frozen["test_role"] == "test_precut_final_frozen_evaluation_only"
    assert "training_or_fine_tuning" in frozen["prohibited_uses"]
    assert payload["authority"] == {
        "pre_registered": True,
        "source_acquisition_started": False,
        "labels_created": False,
        "retriever_or_reranker_results_observed": False,
        "training_authorized": False,
    }
