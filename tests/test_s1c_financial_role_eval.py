from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVAL_SET = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1c_financial_role_eval_set_v1_1.json"
)
SHADOW_RESULT = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1c_cross_encoder_role_shadow_result_v1_1.json"
)


def test_role_eval_set_separates_primary_and_unseen_holdouts() -> None:
    payload = json.loads(EVAL_SET.read_text(encoding="utf-8"))
    primary = [row for row in payload["queries"] if row["split"] == "primary_three_case"]
    holdout = [row for row in payload["queries"] if row["split"] == "holdout_unseen_case"]

    assert len(primary) == 18
    assert len(holdout) == 17
    assert {row["case_key"] for row in primary} == {"DELL", "MU", "NVDA"}
    assert {row["case_key"] for row in holdout} == {"ORCL", "ASML", "ANET"}
    assert payload["label_policy"]["holdout_cases_forbidden_from_tuning"] == [
        "ANET",
        "ASML",
        "ORCL",
    ]
    assert payload["summary"]["primary_hard_negative_count"] == 65
    assert payload["summary"]["holdout_hard_negative_count"] == 34
    assert payload["label_policy"]["cross_slot_absence_is_not_negative"] is True


def test_role_eval_queries_do_not_contain_gold_document_identity() -> None:
    payload = json.loads(EVAL_SET.read_text(encoding="utf-8"))
    for row in payload["queries"]:
        query = row["query_text"].casefold()
        documents = [*row["positives"], *row["hard_negatives"]]
        assert all(str(item["document_id"]).casefold() not in query for item in documents)
        assert row["positives"]
        if row["split"] == "holdout_unseen_case":
            assert row["hard_negatives"]


def test_primary_hard_negatives_have_existing_business_reason_codes() -> None:
    payload = json.loads(EVAL_SET.read_text(encoding="utf-8"))
    negatives = [
        item
        for row in payload["queries"]
        if row["split"] == "primary_three_case"
        for item in row["hard_negatives"]
    ]
    assert negatives
    assert all(
        item["label"] == "existing_business_diagnostic_hard_negative"
        and item["reason_code"] != "no_automatic_business_error_detected"
        for item in negatives
    )


def test_holdout_negatives_are_explicit_adjudications_not_implicit_cross_slot_labels() -> None:
    payload = json.loads(EVAL_SET.read_text(encoding="utf-8"))
    for row in payload["queries"]:
        if row["split"] != "holdout_unseen_case":
            continue
        assert len(row["hard_negatives"]) >= 2
        assert all(
            item["label"] == "codex_supervised_role_contrast_hard_negative"
            and item["reason_code"]
            for item in row["hard_negatives"]
        )
        assert row["unjudged_same_case_document_count"] >= 0


def test_shadow_result_records_non_promotion_and_holdout_regression() -> None:
    payload = json.loads(SHADOW_RESULT.read_text(encoding="utf-8"))
    primary = payload["primary_candidate_ranking"]["routes"]
    holdout = payload["frozen_label_evaluation"]["splits"][
        "holdout_unseen_case"
    ]

    assert primary["sparse_bm25"]["target_recall_at_10"] == 0.944444
    assert primary["cross_encoder"]["target_recall_at_10"] == 0.944444
    assert primary["cross_encoder_role_gated"]["target_recall_at_10"] == 0.722222
    assert holdout["cross_encoder_top1_positive_rate"] == 0.823529
    assert holdout["role_gated_top1_positive_rate"] == 0.764706
    assert payload["authority"] == {
        "candidate_is_not_evidence": True,
        "evidence_promoted": False,
        "runtime_route_promoted": False,
        "fine_tuning_authorized": False,
        "s1_complete_claimed": False,
    }
