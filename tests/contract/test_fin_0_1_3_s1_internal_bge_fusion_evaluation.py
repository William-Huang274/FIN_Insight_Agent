from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_internal_bge_fusion_evaluation import (  # noqa: E402
    S1InternalBGEFusionEvaluationError,
    execute_internal_bge_fusion_evaluation,
    load_internal_bge_fusion_evaluation_policy,
    merge_ranked_lanes,
    validate_internal_bge_fusion_evaluation_result,
)


POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_internal_"
    "bge_fusion_evaluation_policy_v1_0.json"
)


def test_policy_binds_owner_qrels_and_local_resources_without_reranker() -> None:
    policy = load_internal_bge_fusion_evaluation_policy(
        POLICY_PATH, repo_root=ROOT
    )
    assert policy["run_scope"] == (
        "S1_INTERNAL_BGE_FUSION_AND_RERANK_EVALUATION"
    )
    assert policy["candidate_contract"]["bundle_count"] == 18
    assert policy["candidate_contract"][
        "milvus_fiscal_year_field_authority"
    ] == "reporting_fiscal_years"
    assert policy["resource_bindings"]["reranker"] == (
        "optional_resource_absent_not_executed"
    )
    assert policy["hard_boundaries"]["may_download_model_or_reranker"] is False


def test_lane_merge_is_order_stable_and_coalesces_same_evidence() -> None:
    bm25 = [
        {
            "route_rank": 2,
            "source_key": "EVIDENCE_A",
            "ticker": "NVDA",
            "fiscal_year": 2027,
        },
        {"route_rank": 1, "source_key": "EVIDENCE_B", "ticker": "NVDA"},
    ]
    dense = [
        {"rank": 1, "evidence_id": "EVIDENCE_A", "ticker": "NVDA"},
        {"rank": 2, "evidence_id": "EVIDENCE_C", "ticker": "NVDA"},
    ]
    weights = {"internal_bm25": 1.0, "dense_en": 1.0}
    first = merge_ranked_lanes(
        lanes={"internal_bm25": bm25, "dense_en": dense},
        weights=weights,
        rrf_k=60,
        top_k=4,
    )
    second = merge_ranked_lanes(
        lanes={
            "dense_en": list(reversed(dense)),
            "internal_bm25": list(reversed(bm25)),
        },
        weights=weights,
        rrf_k=60,
        top_k=4,
    )
    assert [item["candidate_key"] for item in first] == [
        item["candidate_key"] for item in second
    ]
    assert first[0]["candidate_key"] == "EVIDENCE_A"
    assert first[0]["route_ranks"] == {"dense_en": 1, "internal_bm25": 2}


class _FakeModel:
    def encode(self, texts, **_):
        assert len(texts) == 36
        return [[0.0] * 1024 for _ in texts]


class _FakeClient:
    def __init__(self) -> None:
        self.searches = 0
        self.loaded = False

    def load_collection(self, *, collection_name: str) -> None:
        assert collection_name
        self.loaded = True

    def search(self, **kwargs):
        assert self.loaded
        assert kwargs["limit"] == 24
        assert "fiscal_year in" in kwargs["filter"]
        self.searches += 1
        return [
            [
                {
                    "distance": 0.1,
                    "entity": {
                        "vector_id": f"FAKE_{self.searches}",
                        "evidence_id": f"FAKE_{self.searches}",
                        "ticker": "",
                        "fiscal_year": None,
                        "form_type": "",
                        "source_tier": "primary_sec_filing",
                        "vector_kind": "narrative_chunk",
                        "preview": "fake deterministic candidate",
                    },
                }
            ]
        ]

    def release_collection(self, *, collection_name: str) -> None:
        assert collection_name
        self.loaded = False


def test_full_fake_executes_36_embeddings_and_searches_then_loads_qrels() -> None:
    policy = load_internal_bge_fusion_evaluation_policy(
        POLICY_PATH, repo_root=ROOT
    )
    client = _FakeClient()
    result = execute_internal_bge_fusion_evaluation(
        policy=policy,
        repo_root=ROOT,
        model_factory=lambda _path, _device: _FakeModel(),
        client_factory=lambda **_: client,
        execution_kind="full_fake_zero_external_call",
    )
    assert client.searches == 36
    assert result["candidate_generation"]["status"] == (
        "terminal_before_qrels_load"
    )
    assert result["candidate_generation"][
        "qrels_loaded_after_candidate_generation"
    ] is True
    assert len(
        result["candidate_generation"]["preserved_sparse_typed_gaps"]
    ) == 1
    assert result["observed_calls"]["embedding_vectors"] == 36
    assert result["observed_calls"]["milvus_searches"] == 36
    assert result["adoption_decision"]["reranker"] == (
        "not_executed_optional_resource_absent"
    )
    assert result["preserved_boundaries"]["current_quarter_exact_sql"] == (
        "0_of_6_open"
    )


def test_result_boundary_mutation_fails_closed() -> None:
    policy = load_internal_bge_fusion_evaluation_policy(
        POLICY_PATH, repo_root=ROOT
    )
    result = execute_internal_bge_fusion_evaluation(
        policy=policy,
        repo_root=ROOT,
        model_factory=lambda _path, _device: _FakeModel(),
        client_factory=lambda **_: _FakeClient(),
        execution_kind="full_fake_zero_external_call",
    )
    mutated = deepcopy(result)
    mutated["preserved_boundaries"]["release"] = "qualified"
    with pytest.raises(
        S1InternalBGEFusionEvaluationError,
        match="internal_bge_fusion_result_digest_invalid",
    ):
        validate_internal_bge_fusion_evaluation_result(mutated)
