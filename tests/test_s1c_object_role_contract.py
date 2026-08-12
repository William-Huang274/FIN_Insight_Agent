from __future__ import annotations

import json
from pathlib import Path

import pytest

from retrieval.evidence_role_contract import (
    EvidenceRoleContractError,
    assert_object_view_is_label_free,
    build_evidence_object_view,
    build_object_annotation,
    build_query_relation,
)


ROOT = Path(__file__).resolve().parents[1]
REVIEW_SET = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1c_object_role_review_set_v1_0.json"
)


def _record() -> dict[str, object]:
    return {
        "evidence_id": "CURRENT_DOC::DELL::10_Q::A::ITEM_2::BLOCK_0001::PART_01_OF_01",
        "ticker": "DELL",
        "company": "Dell Technologies",
        "source_type": "10-Q",
        "source_tier": "primary_sec_filing",
        "publication_date": "2026-05-28",
        "period_end": "2026-05-01",
        "fiscal_year": 2027,
        "section": "Item 2. Management's Discussion and Analysis",
        "subsection": "Results",
        "text": (
            "Revenue increased because of AI server shipments.\n"
            "[TABLE_START id=9 rows=2]\nRevenue | 10 | 8\n[TABLE_END]"
        ),
        "metadata": {"parent_document_id": "CURRENT_DOC::DELL::10_Q::A"},
    }


def _parent() -> dict[str, object]:
    return {
        "document_id": "CURRENT_DOC::DELL::10_Q::A",
        "ticker": "DELL",
        "company": "Dell Technologies",
        "source_type": "10-Q",
        "source_tier": "primary_sec_filing",
        "publication_date": "2026-05-28",
        "period_end": "2026-05-01",
        "fiscal_year": 2027,
    }


def _qrel() -> dict[str, str]:
    return {
        "qrel_id": "q1",
        "case_key": "DELL",
        "subject_ticker": "DELL",
        "evidence_slot_id": "issuer_results_and_management_commentary",
        "evidence_owner_ticker": "DELL",
        "relationship_direction": "subject_self_disclosure",
    }


def test_claim_and_metric_table_are_exact_source_bound_objects() -> None:
    claim = build_evidence_object_view(
        object_key="claim",
        object_form="claim",
        locator={
            "mode": "exact_text",
            "text": "Revenue increased because of AI server shipments.",
        },
        record=_record(),
        parent=_parent(),
    ).as_dict()
    table = build_evidence_object_view(
        object_key="table",
        object_form="metric_table",
        locator={"mode": "balanced_table", "table_id": "9"},
        record=_record(),
        parent=_parent(),
    ).as_dict()

    assert claim["surface_text"] == "Revenue increased because of AI server shipments."
    assert table["surface_text"].startswith("[TABLE_START id=9 rows=2]")
    assert table["surface_text"].endswith("[TABLE_END]")
    assert claim["candidate_not_evidence"] is True
    assert table["candidate_not_evidence"] is True
    assert_object_view_is_label_free(claim)
    assert_object_view_is_label_free(table)


def test_annotations_and_query_relations_never_copy_source_surface() -> None:
    view = build_evidence_object_view(
        object_key="claim",
        object_form="claim",
        locator={
            "mode": "exact_text",
            "text": "Revenue increased because of AI server shipments.",
        },
        record=_record(),
        parent=_parent(),
    ).as_dict()
    annotation = build_object_annotation(
        object_view=view,
        role_labels=["observed_operating_result"],
        fact_state_labels=["reported_observed"],
        reason_codes=["reported_result"],
        label_authority="test review",
    )
    relation = build_query_relation(
        review_id="review-1",
        qrel=_qrel(),
        object_view=view,
        relevance_judgement="positive",
        directness="subject_direct",
        background_state="core_evidence",
        reason_codes=["direct_result"],
        business_rationale_zh="当期结果直接回答问题。",
        label_authority="test review",
    )

    assert "surface_text" not in annotation
    assert "surface_text" not in relation
    assert relation["evidence_promoted"] is False


def test_parent_context_can_qualify_but_cannot_be_positive_evidence() -> None:
    view = build_evidence_object_view(
        object_key="parent",
        object_form="parent_context",
        locator={"mode": "parent_context"},
        record=_record(),
        parent=_parent(),
    ).as_dict()
    annotation = build_object_annotation(
        object_view=view,
        role_labels=[],
        fact_state_labels=["not_applicable"],
        reason_codes=["context_only"],
        label_authority="test review",
    )
    assert annotation["role_labels"] == []

    with pytest.raises(
        EvidenceRoleContractError,
        match="evidence_relation_parent_context_must_be_unjudged",
    ):
        build_query_relation(
            review_id="review-parent",
            qrel=_qrel(),
            object_view=view,
            relevance_judgement="positive",
            directness="context_only",
            background_state="bounded_context",
            reason_codes=["invalid_positive_context"],
            business_rationale_zh="父级不能单独证明事实。",
            label_authority="test review",
        )


def test_frozen_review_set_separates_objects_labels_and_holdouts() -> None:
    payload = json.loads(REVIEW_SET.read_text(encoding="utf-8"))
    summary = payload["summary"]
    assert summary["object_view_count"] == 24
    assert summary["object_form_counts"] == {
        "claim": 13,
        "metric_table": 6,
        "mixed_source_segment": 1,
        "navigation_or_boilerplate": 1,
        "parent_context": 3,
    }
    assert summary["judgement_counts"] == {
        "hard_negative": 12,
        "positive": 17,
        "unjudged": 6,
    }
    assert summary["primary_pack_unbound_claim_or_metric_surface_count"] == 45
    assert payload["separation_policy"]["holdout_cases_forbidden_from_design_tuning_and_training"] == [
        "ANET",
        "ASML",
        "ORCL",
    ]
    assert all(
        not {
            "role_labels",
            "fact_state_labels",
            "directness",
            "relevance_judgement",
        }.intersection(row)
        for row in payload["object_views"]
    )
    assert all("surface_text" not in row for row in payload["object_annotations"])
    assert all("surface_text" not in row for row in payload["query_relations"])
    assert {row["case_key"] for row in payload["query_relations"]} == {
        "DELL",
        "MU",
        "NVDA",
    }


def test_tsm_capacity_target_is_relevance_label_but_not_role_positive() -> None:
    payload = json.loads(REVIEW_SET.read_text(encoding="utf-8"))
    tsm_relations = [
        row
        for row in payload["query_relations"]
        if row["qrel_id"] in {"s1c_qrel_06", "s1c_qrel_12", "s1c_qrel_18"}
        and row["relevance_judgement"] == "unjudged"
    ]
    assert len(tsm_relations) == 3
    assert all(row["relevance_judgement"] == "unjudged" for row in tsm_relations)
    assert all(row["evidence_promoted"] is False for row in tsm_relations)
