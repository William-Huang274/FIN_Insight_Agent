from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from threading import Lock
from typing import Any, Mapping, Sequence

import numpy as np

from .contracts import EvidenceRequest, FinancialResearchKernel
from .embedding_runtime import (
    load_qwen_embedding_runtime,
    local_model_identity,
    sha256_file,
)
from .object_retrieval_comparison import (
    CandidateScore,
    bm25_rank,
    dense_rank,
    load_compiled_objects,
    union_candidate_ids,
)
from .query_atom_shadow import QueryAtom, compile_atom_lane, eligible_atom_indices
from .query_plan import canonical_digest
from .route_compiler import QueryObjectFactRoutePolicy


HYBRID_RUNTIME_POLICY_SCHEMA_VERSION = (
    "fin_ia_s1c_hybrid_candidate_runtime_policy_v1_0"
)
HYBRID_RESULT_SCHEMA_VERSION = "fin_ia_s1c_hybrid_candidate_result_v1_0"

_REQUIRED_AUTHORITY = {
    "candidate_is_not_evidence": True,
    "numeric_authority": False,
    "embedding_grants_evidence_authority": False,
    "database_lane_remains_independent": True,
    "generation_model_calls_authorized": False,
}


class HybridCandidateRuntimeError(ValueError):
    """Fail-closed error for the provisional BM25 + Qwen candidate runtime."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise HybridCandidateRuntimeError(code)


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HybridCandidateRuntimeError(
            f"hybrid_candidate_json_invalid:{path.name}"
        ) from exc
    _require(isinstance(value, dict), f"hybrid_candidate_json_invalid:{path.name}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                _require(
                    isinstance(value, dict),
                    f"hybrid_candidate_jsonl_row_invalid:{line_number}",
                )
                rows.append(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HybridCandidateRuntimeError(
            f"hybrid_candidate_jsonl_invalid:{path.name}"
        ) from exc
    return rows


def _route_maps(
    rows: Sequence[CandidateScore],
) -> tuple[dict[str, int], dict[str, float]]:
    return (
        {row.compiled_object_id: rank for rank, row in enumerate(rows, start=1)},
        {row.compiled_object_id: float(row.score) for row in rows},
    )


def retrieve_hybrid_candidates(
    *,
    request: EvidenceRequest,
    kernel: FinancialResearchKernel,
    route_policy: QueryObjectFactRoutePolicy,
    objects: Sequence[Mapping[str, Any]],
    qwen_document_embeddings: np.ndarray,
    qwen_query_embedding: np.ndarray,
    first_stage_limit: int,
    candidate_union_limit: int,
    output_limit: int,
    max_candidates_per_source_record: int,
) -> dict[str, Any]:
    """Return a hard-filtered, source-diverse BM25 + Qwen candidate union."""

    _require(
        first_stage_limit >= output_limit >= 1
        and candidate_union_limit >= first_stage_limit
        and max_candidates_per_source_record >= 1,
        "hybrid_candidate_limits_invalid",
    )
    atom = QueryAtom(
        atom_id=f"RUNTIME::{request.request_id}",
        request_payload=request.as_dict(),
        positive_object_ids=(),
        hard_negative_object_ids=(),
        unjudged_object_ids=(),
        expected_roles_by_object_id={},
    )
    _, lane = compile_atom_lane(atom, kernel)
    eligible, exclusions = eligible_atom_indices(
        objects,
        atom=atom,
        lane=lane,
        route_policy=route_policy,
    )
    bm25 = bm25_rank(
        objects,
        eligible,
        lane.lexical_query,
        limit=first_stage_limit,
    )
    qwen = dense_rank(
        objects,
        eligible,
        qwen_document_embeddings,
        qwen_query_embedding,
        limit=first_stage_limit,
    )
    union_ids = union_candidate_ids(
        (bm25, qwen),
        maximum=candidate_union_limit,
    )
    bm25_ranks, bm25_scores = _route_maps(bm25)
    qwen_ranks, qwen_scores = _route_maps(qwen)
    objects_by_id = {str(row["compiled_object_id"]): row for row in objects}
    selected: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}
    for object_id in union_ids:
        row = objects_by_id[object_id]
        base = row["base_object_view"]
        source_id = str(base["source_record_id"])
        if source_counts.get(source_id, 0) >= max_candidates_per_source_record:
            continue
        source_counts[source_id] = source_counts.get(source_id, 0) + 1
        routes = []
        if object_id in bm25_ranks:
            routes.append("bm25_lexical")
        if object_id in qwen_ranks:
            routes.append("qwen3_embedding_0_6b_dense")
        selected.append(
            {
                "rank": len(selected) + 1,
                "compiled_object_id": object_id,
                "source_record_id": source_id,
                "lineage_source_record_ids": list(
                    row.get("lineage_source_record_ids") or (source_id,)
                ),
                "ticker": str(base["ticker"]),
                "company": str(base.get("company") or ""),
                "source_type": str(base["source_type"]),
                "source_tier": str(base["source_tier"]),
                "publication_date": str(base["publication_date"]),
                "period_end": str(base.get("period_end") or ""),
                "fiscal_year": base.get("fiscal_year"),
                "section": str(base.get("section") or ""),
                "subsection": str(base.get("subsection") or ""),
                "object_kind": str(row["object_kind"]),
                "model_text": str(row["model_text"]),
                "route_membership": routes,
                "route_ranks": {
                    "bm25_lexical": bm25_ranks.get(object_id),
                    "qwen3_embedding_0_6b_dense": qwen_ranks.get(object_id),
                },
                "route_scores": {
                    "bm25_lexical": bm25_scores.get(object_id),
                    "qwen3_embedding_0_6b_dense": qwen_scores.get(object_id),
                },
                "candidate_not_evidence": True,
                "numeric_authority": False,
            }
        )
        if len(selected) >= output_limit:
            break

    both = sum(len(row["route_membership"]) == 2 for row in selected)
    bm25_only = sum(row["route_membership"] == ["bm25_lexical"] for row in selected)
    qwen_only = sum(
        row["route_membership"] == ["qwen3_embedding_0_6b_dense"]
        for row in selected
    )
    body = {
        "schema_version": HYBRID_RESULT_SCHEMA_VERSION,
        "request_id": request.request_id,
        "facet_id": lane.facet_id,
        "evidence_owner_tickers": list(lane.evidence_owner_tickers),
        "route_id": "bm25_lexical_plus_qwen3_embedding_dense_union",
        "candidate_state": "candidate_not_evidence",
        "query": {
            "lexical": lane.lexical_query,
            "semantic": lane.semantic_query,
        },
        "summary": {
            "eligible_object_count": int(eligible.size),
            "bm25_first_stage_count": len(bm25),
            "qwen_first_stage_count": len(qwen),
            "union_count_before_source_quota": len(union_ids),
            "selected_count": len(selected),
            "selected_both_routes": both,
            "selected_bm25_only": bm25_only,
            "selected_qwen_only": qwen_only,
            "max_candidates_per_source_record": max_candidates_per_source_record,
            "hard_filter_exclusions": exclusions,
        },
        "candidates": selected,
        "authority": dict(_REQUIRED_AUTHORITY),
    }
    return {**body, "result_digest": canonical_digest(body)}


class LocalQwenHybridCandidateRuntime:
    """Local adapter around an immutable object store and Qwen embedding cache."""

    def __init__(
        self,
        *,
        objects: Sequence[Mapping[str, Any]],
        qwen_document_embeddings: np.ndarray,
        qwen_runtime: Any,
        query_instruction: str,
        first_stage_limit: int,
        candidate_union_limit: int,
        output_limit: int,
        max_candidates_per_source_record: int,
        runtime_identity: Mapping[str, Any],
    ) -> None:
        self._objects = tuple(objects)
        self._qwen_document_embeddings = qwen_document_embeddings
        self._qwen_runtime = qwen_runtime
        self._query_instruction = query_instruction
        self._first_stage_limit = first_stage_limit
        self._candidate_union_limit = candidate_union_limit
        self._output_limit = output_limit
        self._max_candidates_per_source_record = max_candidates_per_source_record
        self.runtime_identity = dict(runtime_identity)
        self._inference_lock = Lock()

    @classmethod
    def from_policy(
        cls,
        repository_root: str | Path,
        payload: Mapping[str, Any],
    ) -> "LocalQwenHybridCandidateRuntime":
        root = Path(repository_root).resolve()
        expected_fields = {
            "schema_version",
            "status",
            "object_store",
            "qwen_embedding",
            "candidate_contract",
            "authority",
        }
        _require(set(payload) == expected_fields, "hybrid_runtime_policy_fields_invalid")
        _require(
            payload.get("schema_version") == HYBRID_RUNTIME_POLICY_SCHEMA_VERSION,
            "hybrid_runtime_policy_schema_invalid",
        )
        _require(
            payload.get("status")
            == "provisional_local_embedding_adapter_not_evidence_authority",
            "hybrid_runtime_policy_status_invalid",
        )
        _require(
            payload.get("authority") == _REQUIRED_AUTHORITY,
            "hybrid_runtime_policy_authority_invalid",
        )
        object_policy = payload.get("object_store")
        model_policy = payload.get("qwen_embedding")
        candidate_policy = payload.get("candidate_contract")
        _require(
            isinstance(object_policy, Mapping)
            and isinstance(model_policy, Mapping)
            and isinstance(candidate_policy, Mapping),
            "hybrid_runtime_policy_shape_invalid",
        )
        objects_path = _resolve(root, str(object_policy.get("objects_ref") or ""))
        cache_path = _resolve(root, str(model_policy.get("dense_cache_ref") or ""))
        manifest_path = _resolve(root, str(model_policy.get("cache_manifest_ref") or ""))
        _require(
            objects_path.is_file() and cache_path.is_file() and manifest_path.is_file(),
            "hybrid_runtime_required_asset_missing",
        )
        manifest = _read_json(manifest_path)
        _require(
            sha256_file(objects_path) == str(object_policy.get("objects_sha256"))
            == str(manifest.get("object_sha256")),
            "hybrid_runtime_object_store_drift",
        )
        _require(
            sha256_file(cache_path) == str(manifest.get("dense_sha256")),
            "hybrid_runtime_embedding_cache_drift",
        )
        objects = load_compiled_objects(_read_jsonl(objects_path))
        dense = np.load(cache_path, mmap_mode="r")
        _require(
            dense.shape[0] == len(objects)
            and int(manifest.get("object_count") or 0) == len(objects),
            "hybrid_runtime_embedding_shape_drift",
        )
        env_name = str(model_policy.get("local_directory_env") or "").strip()
        configured = os.environ.get(env_name, "") if env_name else ""
        fallback = str(model_policy.get("development_fallback_local_directory") or "")
        model_dir = _resolve(root, configured or fallback)
        identity = local_model_identity(
            model_dir,
            str(model_policy.get("model_id") or ""),
        )
        _require(
            identity["model_digest"] == str(model_policy.get("model_digest"))
            == str(manifest.get("model_digest")),
            "hybrid_runtime_model_identity_drift",
        )
        runtime = load_qwen_embedding_runtime(model_dir)
        maximum_sequence_length = int(model_policy.get("maximum_sequence_length") or 0)
        _require(128 <= maximum_sequence_length <= 2048, "hybrid_runtime_sequence_limit_invalid")
        runtime.max_seq_length = maximum_sequence_length
        runtime_identity = {
            "object_sha256": str(manifest["object_sha256"]),
            "embedding_cache_sha256": str(manifest["dense_sha256"]),
            "model_digest": str(identity["model_digest"]),
            "object_count": len(objects),
        }
        return cls(
            objects=objects,
            qwen_document_embeddings=dense,
            qwen_runtime=runtime,
            query_instruction=str(model_policy.get("query_instruction") or "").strip(),
            first_stage_limit=int(candidate_policy.get("first_stage_limit") or 0),
            candidate_union_limit=int(candidate_policy.get("candidate_union_limit") or 0),
            output_limit=int(candidate_policy.get("output_limit") or 0),
            max_candidates_per_source_record=int(
                candidate_policy.get("max_candidates_per_source_record") or 0
            ),
            runtime_identity=runtime_identity,
        )

    def retrieve_many(
        self,
        requests: Sequence[EvidenceRequest],
        *,
        kernel: FinancialResearchKernel,
        route_policy: QueryObjectFactRoutePolicy,
    ) -> tuple[dict[str, Any], ...]:
        _require(bool(requests), "hybrid_runtime_requests_missing")
        lanes = []
        for request in requests:
            atom = QueryAtom(
                atom_id=f"RUNTIME::{request.request_id}",
                request_payload=request.as_dict(),
                positive_object_ids=(),
                hard_negative_object_ids=(),
                unjudged_object_ids=(),
                expected_roles_by_object_id={},
            )
            _, lane = compile_atom_lane(atom, kernel)
            lanes.append(lane)
        with self._inference_lock:
            encoded = np.asarray(
                self._qwen_runtime.encode(
                    [lane.semantic_query for lane in lanes],
                    batch_size=len(lanes),
                    prompt=self._query_instruction,
                    normalize_embeddings=True,
                    convert_to_numpy=True,
                    show_progress_bar=False,
                ),
                dtype=np.float32,
            )
        _require(
            encoded.shape[0] == len(requests),
            "hybrid_runtime_query_embedding_shape_invalid",
        )
        return tuple(
            retrieve_hybrid_candidates(
                request=request,
                kernel=kernel,
                route_policy=route_policy,
                objects=self._objects,
                qwen_document_embeddings=self._qwen_document_embeddings,
                qwen_query_embedding=encoded[index],
                first_stage_limit=self._first_stage_limit,
                candidate_union_limit=self._candidate_union_limit,
                output_limit=self._output_limit,
                max_candidates_per_source_record=(
                    self._max_candidates_per_source_record
                ),
            )
            for index, request in enumerate(requests)
        )


class LazyLocalQwenHybridCandidateRuntime:
    """Load the local model only when a controlled research plan needs it."""

    def __init__(
        self,
        repository_root: str | Path,
        policy: Mapping[str, Any],
    ) -> None:
        self._repository_root = Path(repository_root).resolve()
        self._policy = dict(policy)
        self._delegate: LocalQwenHybridCandidateRuntime | None = None
        self._load_lock = Lock()

    def _runtime(self) -> LocalQwenHybridCandidateRuntime:
        if self._delegate is None:
            with self._load_lock:
                if self._delegate is None:
                    self._delegate = LocalQwenHybridCandidateRuntime.from_policy(
                        self._repository_root,
                        self._policy,
                    )
        return self._delegate

    def retrieve_many(
        self,
        requests: Sequence[EvidenceRequest],
        *,
        kernel: FinancialResearchKernel,
        route_policy: QueryObjectFactRoutePolicy,
    ) -> tuple[dict[str, Any], ...]:
        return self._runtime().retrieve_many(
            requests,
            kernel=kernel,
            route_policy=route_policy,
        )


__all__ = [
    "HYBRID_RESULT_SCHEMA_VERSION",
    "HYBRID_RUNTIME_POLICY_SCHEMA_VERSION",
    "HybridCandidateRuntimeError",
    "LazyLocalQwenHybridCandidateRuntime",
    "LocalQwenHybridCandidateRuntime",
    "retrieve_hybrid_candidates",
]
