from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from .candidate_ranking import NeedRouteRanking
from .object_retrieval_comparison import CandidateScore
from .retrieval_need import RetrievalNeed


class QualificationCudaRankingError(RuntimeError):
    """A learned qualification score attempted to leave CUDA FP16."""


def _required_cuda_fp16_device(torch: Any) -> Any:
    if not torch.cuda.is_available():
        raise QualificationCudaRankingError("qualification_cuda_ranking_required")
    return torch.device("cuda:0")


def _stable_rows(
    objects: Sequence[Mapping[str, Any]],
    eligible_indices: np.ndarray,
    scores: np.ndarray,
    *,
    limit: int,
) -> tuple[CandidateScore, ...]:
    rows = [
        CandidateScore(
            compiled_object_id=str(objects[int(raw_index)]["compiled_object_id"]),
            score=float(scores[position]),
        )
        for position, raw_index in enumerate(eligible_indices)
    ]
    rows.sort(key=lambda value: (-value.score, value.compiled_object_id))
    return tuple(rows[:limit])


def rank_need_dense_routes_cuda_fp16(
    *,
    route_id: str,
    objects: Sequence[Mapping[str, Any]],
    eligible_indices: np.ndarray,
    needs: Sequence[RetrievalNeed],
    document_embeddings: np.ndarray,
    query_embeddings: np.ndarray,
    per_need_limit: int,
) -> tuple[NeedRouteRanking, ...]:
    import torch

    if per_need_limit < 1:
        raise QualificationCudaRankingError("qualification_dense_limit_invalid")
    if document_embeddings.shape[0] != len(objects):
        raise QualificationCudaRankingError("qualification_dense_object_count_mismatch")
    if query_embeddings.shape[0] != len(needs):
        raise QualificationCudaRankingError("qualification_dense_query_count_mismatch")
    if eligible_indices.size == 0:
        return tuple(
            NeedRouteRanking(route_id=route_id, need_id=need.need_id, rows=())
            for need in needs
        )
    device = _required_cuda_fp16_device(torch)
    documents = torch.as_tensor(
        np.asarray(document_embeddings[eligible_indices]),
        device=device,
        dtype=torch.float16,
    )
    queries = torch.as_tensor(
        np.asarray(query_embeddings), device=device, dtype=torch.float16
    )
    if documents.shape[1] != queries.shape[1]:
        raise QualificationCudaRankingError("qualification_dense_dimension_mismatch")
    with torch.inference_mode():
        score_matrix = documents @ queries.transpose(0, 1)
    if score_matrix.device.type != "cuda" or score_matrix.dtype != torch.float16:
        raise QualificationCudaRankingError("qualification_dense_cuda_fp16_drift")
    if not bool(torch.isfinite(score_matrix).all().item()):
        raise QualificationCudaRankingError("qualification_dense_score_nonfinite")
    values = score_matrix.float().cpu().numpy()
    return tuple(
        NeedRouteRanking(
            route_id=route_id,
            need_id=need.need_id,
            rows=_stable_rows(
                objects,
                eligible_indices,
                values[:, index],
                limit=per_need_limit,
            ),
        )
        for index, need in enumerate(needs)
    )


def rank_need_sparse_routes_cuda_fp16(
    *,
    route_id: str,
    objects: Sequence[Mapping[str, Any]],
    eligible_indices: np.ndarray,
    needs: Sequence[RetrievalNeed],
    document_sparse: Any,
    query_sparse: Any,
    per_need_limit: int,
) -> tuple[NeedRouteRanking, ...]:
    import torch

    if per_need_limit < 1:
        raise QualificationCudaRankingError("qualification_sparse_limit_invalid")
    if int(document_sparse.shape[0]) != len(objects):
        raise QualificationCudaRankingError("qualification_sparse_object_count_mismatch")
    if int(query_sparse.shape[0]) != len(needs):
        raise QualificationCudaRankingError("qualification_sparse_query_count_mismatch")
    if int(document_sparse.shape[1]) != int(query_sparse.shape[1]):
        raise QualificationCudaRankingError("qualification_sparse_dimension_mismatch")
    if eligible_indices.size == 0:
        return tuple(
            NeedRouteRanking(route_id=route_id, need_id=need.need_id, rows=())
            for need in needs
        )
    device = _required_cuda_fp16_device(torch)
    document_coo = document_sparse[eligible_indices].tocoo()
    document_indices = torch.as_tensor(
        np.vstack((document_coo.row, document_coo.col)),
        device=device,
        dtype=torch.long,
    )
    document_values = torch.as_tensor(
        document_coo.data, device=device, dtype=torch.float16
    )
    query_coo = query_sparse.tocoo()
    queries = torch.zeros(
        query_sparse.shape, device=device, dtype=torch.float16
    )
    if query_coo.nnz:
        queries[
            torch.as_tensor(query_coo.row, device=device, dtype=torch.long),
            torch.as_tensor(query_coo.col, device=device, dtype=torch.long),
        ] = torch.as_tensor(query_coo.data, device=device, dtype=torch.float16)
    # CUDA sparse addmm does not implement FP16.  Keep both operands and the
    # accumulation on CUDA FP16 by gathering each query's active token weight
    # and reducing document contributions with scatter_add_.  Falling back to
    # SciPy or CPU float32 here would violate the qualification contract.
    score_matrix = torch.zeros(
        (document_coo.shape[0], query_sparse.shape[0]),
        device=device,
        dtype=torch.float16,
    )
    with torch.inference_mode():
        for query_index in range(query_sparse.shape[0]):
            contributions = (
                document_values * queries[query_index, document_indices[1]]
            )
            score_matrix[:, query_index].scatter_add_(
                0, document_indices[0], contributions
            )
    if score_matrix.device.type != "cuda" or score_matrix.dtype != torch.float16:
        raise QualificationCudaRankingError("qualification_sparse_cuda_fp16_drift")
    if not bool(torch.isfinite(score_matrix).all().item()):
        raise QualificationCudaRankingError("qualification_sparse_score_nonfinite")
    values = score_matrix.float().cpu().numpy()
    return tuple(
        NeedRouteRanking(
            route_id=route_id,
            need_id=need.need_id,
            rows=_stable_rows(
                objects,
                eligible_indices,
                values[:, index],
                limit=per_need_limit,
            ),
        )
        for index, need in enumerate(needs)
    )


def multi_vector_rankings_cuda_fp16(
    *,
    runtime: Any,
    query_vectors: Sequence[np.ndarray],
    needs: Sequence[RetrievalNeed],
    candidate_ids: Sequence[str],
    objects_by_id: Mapping[str, Mapping[str, Any]],
    maximum_sequence_length: int,
    batch_size: int,
) -> tuple[NeedRouteRanking, ...]:
    import torch

    if not candidate_ids:
        return ()
    device = _required_cuda_fp16_device(torch)
    encoded = runtime.encode(
        [str(objects_by_id[value]["model_text"]) for value in candidate_ids],
        batch_size=batch_size,
        max_length=maximum_sequence_length,
        return_dense=False,
        return_sparse=False,
        return_colbert_vecs=True,
    )
    document_vectors = [
        torch.as_tensor(value, device=device, dtype=torch.float16)
        for value in encoded["colbert_vecs"]
    ]
    rankings: list[NeedRouteRanking] = []
    for need, raw_query in zip(needs, query_vectors):
        query = torch.as_tensor(raw_query, device=device, dtype=torch.float16)
        scores: list[float] = []
        with torch.inference_mode():
            for document in document_vectors:
                token_scores = query @ document.transpose(0, 1)
                score = token_scores.max(dim=1).values.mean()
                if score.device.type != "cuda" or score.dtype != torch.float16:
                    raise QualificationCudaRankingError(
                        "qualification_multi_vector_cuda_fp16_drift"
                    )
                if not bool(torch.isfinite(score).item()):
                    raise QualificationCudaRankingError(
                        "qualification_multi_vector_score_nonfinite"
                    )
                scores.append(float(score.float().cpu().item()))
        rows = [
            CandidateScore(candidate_id, score)
            for candidate_id, score in zip(candidate_ids, scores)
        ]
        rows.sort(key=lambda value: (-value.score, value.compiled_object_id))
        rankings.append(
            NeedRouteRanking(
                route_id="bge_m3_multi_vector",
                need_id=need.need_id,
                rows=tuple(rows),
            )
        )
    return tuple(rankings)


__all__ = [
    "QualificationCudaRankingError",
    "multi_vector_rankings_cuda_fp16",
    "rank_need_dense_routes_cuda_fp16",
    "rank_need_sparse_routes_cuda_fp16",
]
