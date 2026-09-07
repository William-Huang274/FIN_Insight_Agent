from __future__ import annotations

import pytest

from scripts.qualification.run_s1_qwen_query_embedding_qualification import (
    EXPECTED_QREL_MANIFEST_DIGEST,
    QueryEmbeddingQualificationError,
    _load_queries,
    canonical_digest,
)


def _payload() -> dict[str, object]:
    rows = [
        {
            "qrel_id": f"qrel-{index:02d}",
            "semantic_query_texts": [f"financial query {index}"],
            "target_current_source_record_ids": [f"SOURCE::{index:02d}"],
        }
        for index in range(18)
    ]
    return {
        "schema_version": "fin_ia_s1c_requalified_ranking_qrels_v1_0",
        "qrel_manifest_digest": EXPECTED_QREL_MANIFEST_DIGEST,
        "policy": {
            "labels_joined_after_candidate_generation": True,
            "target_ids_forbidden_from_query_text": True,
            "candidate_is_not_evidence": True,
        },
        "qrels": rows,
    }


def test_load_queries_preserves_frozen_order_without_targets() -> None:
    qrel_ids, queries = _load_queries(_payload())

    assert qrel_ids == [f"qrel-{index:02d}" for index in range(18)]
    assert queries == [f"financial query {index}" for index in range(18)]
    assert canonical_digest(queries) != canonical_digest(list(reversed(queries)))


def test_load_queries_rejects_cross_qrel_target_leakage() -> None:
    payload = _payload()
    rows = payload["qrels"]
    assert isinstance(rows, list)
    rows[0]["semantic_query_texts"] = ["find SOURCE::17"]

    with pytest.raises(
        QueryEmbeddingQualificationError,
        match="cross_qrel_target_leakage:qrel-00",
    ):
        _load_queries(payload)


def test_load_queries_rejects_duplicate_qrel_identity() -> None:
    payload = _payload()
    rows = payload["qrels"]
    assert isinstance(rows, list)
    rows[1]["qrel_id"] = rows[0]["qrel_id"]

    with pytest.raises(QueryEmbeddingQualificationError, match="qrel_id_duplicate"):
        _load_queries(payload)
