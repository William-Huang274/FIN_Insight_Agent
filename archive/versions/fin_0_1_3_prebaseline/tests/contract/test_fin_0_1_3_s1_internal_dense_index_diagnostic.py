from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_internal_dense_index_diagnostic import (  # noqa: E402
    S1InternalDenseIndexDiagnosticError,
    build_dense_index_diagnostic,
    classify_dense_target,
    validate_dense_index_diagnostic,
)


RESULT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_internal_"
    "dense_index_diagnostic_v1_0.json"
)


class _FakeClient:
    def __init__(self) -> None:
        self.loaded = False
        self.queries = 0

    def load_collection(self, *, collection_name: str) -> None:
        assert collection_name
        self.loaded = True

    def query(self, **kwargs):
        assert self.loaded
        assert kwargs["limit"] == 64
        assert kwargs["filter"].startswith("evidence_id in [")
        self.queries += 1
        return []

    def release_collection(self, *, collection_name: str) -> None:
        assert collection_name
        self.loaded = False


def test_classification_separates_index_and_ranking_gaps() -> None:
    assert classify_dense_target(present_in_index=False, selected_rank=None) == (
        "dense_index_freshness_gap"
    )
    assert classify_dense_target(present_in_index=True, selected_rank=None) == (
        "semantic_retrieval_top24_gap"
    )
    assert classify_dense_target(present_in_index=True, selected_rank=16) == (
        "semantic_retrieval_top10_gap"
    )
    assert classify_dense_target(present_in_index=True, selected_rank=3) == (
        "retrieved_top10"
    )


def test_fake_diagnostic_is_read_only_and_digest_bound() -> None:
    client = _FakeClient()
    result = build_dense_index_diagnostic(
        repo_root=ROOT,
        r2_result_path=ROOT
        / "configs/releases/fin_ia_0_1_3_s1_internal_bge_fusion_evaluation_attempt_r2.json",
        qrels_path=ROOT
        / "configs/releases/fin_ia_0_1_3_s1_internal_qrels_review_packet_v1_3.json",
        r2_policy_path=ROOT
        / "configs/runtime/fin_ia_0_1_3_s1_internal_bge_fusion_evaluation_policy_v1_1.json",
        client_factory=lambda **_: client,
    )
    assert result["status"] == (
        "terminal_succeeded_read_only_dense_index_diagnostic"
    )
    assert client.queries == result["unique_selected_target_count"]
    assert result["unique_selected_target_count"] == 10
    assert result["row_weighted_classification_counts"] == {
        "dense_index_freshness_gap": 18
    }
    assert result["identity_collision_regression"]["status"] == "pass"
    assert result["observed_calls"]["milvus_vector_searches"] == 0
    mutated = deepcopy(result)
    mutated["disposition"]["fusion_adopted"] = True
    with pytest.raises(
        S1InternalDenseIndexDiagnosticError,
        match="dense_index_diagnostic_boundary_invalid",
    ):
        validate_dense_index_diagnostic(mutated)


def test_materialized_diagnostic_preserves_exact_r2_root_cause_split() -> None:
    result = validate_dense_index_diagnostic(
        json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    )
    assert result["unique_selected_target_count"] == 10
    assert result["unique_selected_targets_present_in_milvus"] == 5
    assert result["unique_selected_targets_absent_from_milvus"] == 5
    assert result["row_weighted_classification_counts"] == {
        "dense_index_freshness_gap": 8,
        "retrieved_top10": 3,
        "semantic_retrieval_top10_gap": 1,
        "semantic_retrieval_top24_gap": 6,
    }
    assert result["disposition"] == {
        "fusion_adopted": False,
        "production_candidate_baseline": "sparse_rrf",
        "dense_index_refresh_required": True,
        "semantic_query_or_ranking_gap_present": True,
        "reranker_evaluation_possible": False,
        "reranker_reason": "optional_local_resource_absent",
    }
