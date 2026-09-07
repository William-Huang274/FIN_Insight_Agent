from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from scipy.sparse import csr_matrix

from retrieval.qualification_cuda_ranking import (
    QualificationCudaRankingError,
    _required_cuda_fp16_device,
    multi_vector_rankings_cuda_fp16,
    rank_need_dense_routes_cuda_fp16,
    rank_need_sparse_routes_cuda_fp16,
)
from retrieval.retrieval_need import RetrievalNeed


def _cuda_runtime_available() -> bool:
    try:
        import torch
    except ModuleNotFoundError:
        return False
    return bool(torch.cuda.is_available())


CUDA_RUNTIME_AVAILABLE = _cuda_runtime_available()


def _need() -> RetrievalNeed:
    return RetrievalNeed(
        need_id="N1",
        need_kind="product",
        facet_id="reported_results",
        evidence_owner_ticker="COST",
        relationship_direction="subject_self_disclosure",
        intent_terms=("membership",),
        role_cues=("result",),
        exact_phrases=(),
        lexical_query="membership",
        semantic_query="membership result",
        constraint_digest="x" * 64,
    )


def test_qualification_vector_scoring_fails_closed_without_cuda() -> None:
    fake_torch = SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: False),
        device=lambda value: value,
    )
    with pytest.raises(
        QualificationCudaRankingError, match="qualification_cuda_ranking_required"
    ):
        _required_cuda_fp16_device(fake_torch)


@pytest.mark.skipif(
    not CUDA_RUNTIME_AVAILABLE,
    reason="qualification vector scoring is intentionally CUDA-only",
)
def test_dense_and_learned_sparse_similarity_execute_on_cuda_fp16() -> None:
    objects = [
        {"compiled_object_id": "C1"},
        {"compiled_object_id": "C2"},
    ]
    eligible = np.asarray([0, 1], dtype=np.int64)
    need = _need()
    dense = rank_need_dense_routes_cuda_fp16(
        route_id="dense",
        objects=objects,
        eligible_indices=eligible,
        needs=(need,),
        document_embeddings=np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float16),
        query_embeddings=np.asarray([[1.0, 0.0]], dtype=np.float16),
        per_need_limit=2,
    )
    sparse = rank_need_sparse_routes_cuda_fp16(
        route_id="sparse",
        objects=objects,
        eligible_indices=eligible,
        needs=(need,),
        document_sparse=csr_matrix(
            np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
        ),
        query_sparse=csr_matrix(np.asarray([[1.0, 0.0]], dtype=np.float32)),
        per_need_limit=2,
    )
    assert [row.compiled_object_id for row in dense[0].rows] == ["C1", "C2"]
    assert [row.compiled_object_id for row in sparse[0].rows] == ["C1", "C2"]


@pytest.mark.skipif(
    not CUDA_RUNTIME_AVAILABLE,
    reason="qualification vector scoring is intentionally CUDA-only",
)
def test_multi_vector_similarity_does_not_use_flagembedding_cpu_helper() -> None:
    class FakeRuntime:
        def encode(self, texts, **kwargs):
            assert texts == ["document one", "document two"]
            return {
                "colbert_vecs": [
                    np.asarray([[1.0, 0.0], [1.0, 0.0]], dtype=np.float16),
                    np.asarray([[0.0, 1.0], [0.0, 1.0]], dtype=np.float16),
                ]
            }

        def colbert_score(self, *args, **kwargs):
            raise AssertionError("FlagEmbedding colbert_score is CPU-only and must not run")

    rows = multi_vector_rankings_cuda_fp16(
        runtime=FakeRuntime(),
        query_vectors=(np.asarray([[1.0, 0.0]], dtype=np.float16),),
        needs=(_need(),),
        candidate_ids=("C1", "C2"),
        objects_by_id={
            "C1": {"model_text": "document one"},
            "C2": {"model_text": "document two"},
        },
        maximum_sequence_length=32,
        batch_size=2,
    )
    assert [row.compiled_object_id for row in rows[0].rows] == ["C1", "C2"]
