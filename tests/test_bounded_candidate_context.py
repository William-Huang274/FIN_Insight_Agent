from __future__ import annotations

from retrieval.bounded_context import expand_bounded_candidate_context


def _row(
    object_id: str,
    *,
    evidence_type: str,
    links: dict[str, object],
    kind: str = "claim",
) -> dict[str, object]:
    return {
        "compiled_object_id": object_id,
        "object_kind": kind,
        "source_evidence_type": evidence_type,
        "context_links": links,
    }


def test_metric_row_attaches_explicit_table_footnote_cross_page_and_revision() -> None:
    objects = {
        "row": _row(
            "row",
            evidence_type="financial_table_metric_row",
            kind="metric_row",
            links={
                "parent_document_id": "doc",
                "parent_page_object_id": "page",
                "parent_table_object_id": "table",
            },
        ),
        "table": _row(
            "table",
            evidence_type="financial_table_region",
            links={"parent_document_id": "doc"},
        ),
        "page": _row(
            "page",
            evidence_type="pdf_page_context",
            links={"parent_document_id": "doc"},
        ),
        "footnote": _row(
            "footnote",
            evidence_type="financial_table_footnote",
            links={
                "parent_document_id": "doc",
                "linked_table_object_ids": ["table"],
            },
        ),
        "continuation": _row(
            "continuation",
            evidence_type="cross_page_table_continuation_candidate",
            links={
                "parent_document_id": "doc",
                "left_object_id": "row",
                "right_object_id": "row-next",
            },
        ),
        "revision": _row(
            "revision",
            evidence_type="revision_or_restatement_context",
            links={"parent_document_id": "doc"},
        ),
        "unrelated": _row(
            "unrelated",
            evidence_type="financial_table_metric_row",
            links={"parent_document_id": "doc", "parent_table_object_id": "other"},
        ),
    }

    result = expand_bounded_candidate_context(
        selected_object_ids=("row",),
        objects_by_id=objects,
        include_document_revision_context=True,
    )

    assert result["expanded_context_object_ids"] == [
        "table",
        "footnote",
        "continuation",
        "revision",
        "page",
    ]
    assert "unrelated" not in result["expanded_context_object_ids"]
    assert all(row["candidate_not_evidence"] for row in result["expansions"])
    assert result["authority"]["context_is_not_independent_evidence"] is True


def test_revision_context_requires_explicit_request_scope() -> None:
    objects = {
        "row": _row(
            "row",
            evidence_type="financial_table_metric_row",
            kind="metric_row",
            links={"parent_document_id": "doc"},
        ),
        "revision": _row(
            "revision",
            evidence_type="revision_or_restatement_context",
            links={"parent_document_id": "doc"},
        ),
    }
    result = expand_bounded_candidate_context(
        selected_object_ids=("row",),
        objects_by_id=objects,
        include_document_revision_context=False,
    )
    assert result["expanded_context_object_ids"] == []
