from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from scipy.sparse import csr_matrix, load_npz, save_npz


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.object_retrieval_comparison import (  # noqa: E402
    CandidateScore,
    bm25_rank,
    dense_rank,
    eligible_object_indices,
    evaluate_route,
    load_compiled_objects,
    load_queries,
    map_reviewed_objects_to_compiled_successors,
    route_metrics,
    sparse_rank,
    union_candidate_ids,
)
from retrieval.query_plan import canonical_digest  # noqa: E402
from retrieval.text import tokenize  # noqa: E402


RESULT_SCHEMA_VERSION = "fin_ia_s1c_compiled_object_retriever_comparison_result_v1_0"
SUMMARY_SCHEMA_VERSION = (
    "fin_ia_s1c_compiled_object_retriever_comparison_summary_v1_0"
)


def _resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_lf_text(path: Path) -> str:
    """Hash tracked text independent of the checkout's CRLF/LF representation."""

    normalized = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path.name}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"jsonl_object_required:{path.name}:{line_number}")
            rows.append(value)
    return rows


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
    temporary.replace(path)


def _compact_result(
    result: Mapping[str, Any],
    *,
    full_output: Path,
    full_output_sha256: str,
) -> dict[str, Any]:
    execution = dict(result["execution"])
    for key in ("bge_model_identity", "qwen_model_identity"):
        identity = execution.get(key)
        if isinstance(identity, Mapping):
            execution[key] = {
                field: identity[field]
                for field in ("model_name", "directory_name", "model_digest")
                if field in identity
            }
    evaluation = dict(result["evaluation_contract"])
    mapping = evaluation.get("reviewed_object_successor_mapping")
    if isinstance(mapping, Mapping):
        evaluation["reviewed_object_successor_mapping"] = {
            "mapping_count": mapping.get("mapping_count"),
            "unmapped_count": mapping.get("unmapped_count"),
            "unmapped": mapping.get("unmapped"),
            "whole_table_projection_forbidden": mapping.get(
                "whole_table_projection_forbidden"
            ),
        }
    primary = result["primary_full_corpus_comparison"]
    compact_queries: list[dict[str, Any]] = []
    for query in primary["queries"]:
        compact_routes: dict[str, Any] = {}
        for route_id, route in query["routes"].items():
            compact_routes[route_id] = {
                key: value for key, value in route.items() if key != "candidates"
            }
        compact_queries.append({**query, "routes": compact_routes})
    validation = result["observed_validation_pairwise_comparison"]
    unsigned = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": result["status"],
        "recorded_at": result["recorded_at"],
        "storage": {
            "full_result_ref": _relative(full_output),
            "full_result_sha256": full_output_sha256,
            "full_result_digest": result["result_digest"],
            "tracked_summary_excludes_candidate_excerpts": True,
        },
        "bound_inputs": result["bound_inputs"],
        "execution": execution,
        "evaluation_contract": evaluation,
        "primary_full_corpus_comparison": {
            "query_count": primary["query_count"],
            "top_k": primary["top_k"],
            "candidate_pool": primary["candidate_pool"],
            "routes": primary["routes"],
            "queries": compact_queries,
        },
        "observed_validation_pairwise_comparison": {
            "split": validation["split"],
            "query_count": validation["query_count"],
            "routes": validation["routes"],
        },
        "database_lane": result["database_lane"],
        "authority": result["authority"],
        "known_boundary": result["known_boundary"],
    }
    return {**unsigned, "result_digest": canonical_digest(unsigned)}


def _validate_binding(
    path: Path,
    expected: str,
    code: str,
    *,
    tracked_text: bool,
) -> None:
    observed = _sha256_lf_text(path) if tracked_text else _sha256(path)
    if observed != expected:
        raise ValueError(code)


def _model_identity(model_dir: Path, expected_name: str) -> dict[str, Any]:
    config = model_dir / "config.json"
    weights = [
        path
        for name in ("model.safetensors", "pytorch_model.bin")
        if (path := model_dir / name).is_file()
    ]
    if not config.is_file() or not weights:
        raise ValueError(f"local_model_incomplete:{expected_name}")
    tokenizer_files = [
        path
        for name in ("tokenizer.json", "tokenizer_config.json", "sentencepiece.bpe.model")
        if (path := model_dir / name).is_file()
    ]
    files = [config, *weights, *tokenizer_files]
    body = {
        "model_name": expected_name,
        "directory_name": model_dir.name,
        "files": [
            {
                "name": path.name,
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in files
        ],
    }
    return {**body, "model_digest": canonical_digest(body)}


def _object_identity_digest(objects: Sequence[Mapping[str, Any]]) -> str:
    return canonical_digest([str(row["compiled_object_id"]) for row in objects])


def _sparse_matrix(rows: Sequence[Mapping[str, Any]], *, width: int) -> csr_matrix:
    row_indices: list[int] = []
    column_indices: list[int] = []
    values: list[float] = []
    for row_index, weights in enumerate(rows):
        for raw_token, raw_weight in weights.items():
            token = int(raw_token)
            if token < 0 or token >= width:
                raise ValueError("learned_sparse_token_out_of_range")
            weight = float(raw_weight)
            if weight == 0.0:
                continue
            row_indices.append(row_index)
            column_indices.append(token)
            values.append(weight)
    return csr_matrix(
        (np.asarray(values, dtype=np.float32), (row_indices, column_indices)),
        shape=(len(rows), width),
        dtype=np.float32,
    )


def _load_bge_runtime(model_dir: Path):
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
    from FlagEmbedding import BGEM3FlagModel

    return BGEM3FlagModel(str(model_dir), use_fp16=True, device="cuda")


def _bge_cache(
    *,
    objects: Sequence[Mapping[str, Any]],
    object_sha256: str,
    model_dir: Path,
    model_identity: Mapping[str, Any],
    cache_dir: Path,
    maximum_sequence_length: int,
    batch_size: int,
) -> tuple[np.ndarray, csr_matrix, dict[str, Any], Any]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    dense_path = cache_dir / "dense.float16.npy"
    sparse_path = cache_dir / "learned_sparse.float32.npz"
    manifest_path = cache_dir / "manifest.json"
    expected = {
        "schema_version": "fin_ia_s1c_bge_m3_compiled_object_cache_v1_0",
        "object_sha256": object_sha256,
        "object_identity_digest": _object_identity_digest(objects),
        "object_count": len(objects),
        "model_digest": str(model_identity["model_digest"]),
        "maximum_sequence_length": maximum_sequence_length,
        "dense_dtype": "float16",
        "learned_sparse_dtype": "float32",
    }
    cache_hit = False
    if dense_path.is_file() and sparse_path.is_file() and manifest_path.is_file():
        existing = _read_json(manifest_path)
        cache_hit = all(existing.get(key) == value for key, value in expected.items())
    runtime = _load_bge_runtime(model_dir)
    if not cache_hit:
        started = time.perf_counter()
        encoded = runtime.encode(
            [str(row["model_text"]) for row in objects],
            batch_size=batch_size,
            max_length=maximum_sequence_length,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        dense = np.asarray(encoded["dense_vecs"], dtype=np.float16)
        width = int(runtime.tokenizer.vocab_size)
        sparse = _sparse_matrix(encoded["lexical_weights"], width=width)
        np.save(dense_path, dense, allow_pickle=False)
        save_npz(sparse_path, sparse, compressed=True)
        elapsed = time.perf_counter() - started
        manifest = {
            **expected,
            "embedding_dimensions": int(dense.shape[1]),
            "sparse_vocabulary_size": int(sparse.shape[1]),
            "sparse_nonzero_count": int(sparse.nnz),
            "build_seconds": round(elapsed, 3),
            "dense_sha256": _sha256(dense_path),
            "sparse_sha256": _sha256(sparse_path),
        }
        _write_json(manifest_path, manifest)
    manifest = _read_json(manifest_path)
    dense = np.load(dense_path, mmap_mode="r")
    sparse = load_npz(sparse_path)
    if dense.shape[0] != len(objects) or sparse.shape[0] != len(objects):
        raise ValueError("bge_cache_shape_drift")
    return dense, sparse, {**manifest, "cache_hit": cache_hit}, runtime


def _load_qwen_runtime(model_dir: Path):
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        str(model_dir),
        device="cuda",
        local_files_only=True,
        trust_remote_code=True,
    )


def _qwen_cache(
    *,
    objects: Sequence[Mapping[str, Any]],
    object_sha256: str,
    model_dir: Path,
    model_identity: Mapping[str, Any],
    cache_dir: Path,
    maximum_sequence_length: int,
    batch_size: int,
) -> tuple[np.ndarray, dict[str, Any], Any]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    dense_path = cache_dir / "dense.float16.npy"
    manifest_path = cache_dir / "manifest.json"
    expected = {
        "schema_version": "fin_ia_s1c_qwen3_embedding_compiled_object_cache_v1_0",
        "object_sha256": object_sha256,
        "object_identity_digest": _object_identity_digest(objects),
        "object_count": len(objects),
        "model_digest": str(model_identity["model_digest"]),
        "maximum_sequence_length": maximum_sequence_length,
        "dense_dtype": "float16",
    }
    cache_hit = False
    if dense_path.is_file() and manifest_path.is_file():
        existing = _read_json(manifest_path)
        cache_hit = all(existing.get(key) == value for key, value in expected.items())
    runtime = _load_qwen_runtime(model_dir)
    runtime.max_seq_length = maximum_sequence_length
    if not cache_hit:
        started = time.perf_counter()
        dense = runtime.encode(
            [str(row["model_text"]) for row in objects],
            batch_size=batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=True,
        ).astype(np.float16)
        np.save(dense_path, dense, allow_pickle=False)
        elapsed = time.perf_counter() - started
        manifest = {
            **expected,
            "embedding_dimensions": int(dense.shape[1]),
            "build_seconds": round(elapsed, 3),
            "dense_sha256": _sha256(dense_path),
        }
        _write_json(manifest_path, manifest)
    manifest = _read_json(manifest_path)
    dense = np.load(dense_path, mmap_mode="r")
    if dense.shape[0] != len(objects):
        raise ValueError("qwen_cache_shape_drift")
    return dense, {**manifest, "cache_hit": cache_hit}, runtime


def _query_sparse_matrix(weights: Sequence[Mapping[str, Any]], width: int) -> csr_matrix:
    return _sparse_matrix(weights, width=width)


def _multi_vector_rank(
    *,
    runtime: Any,
    query_vector: np.ndarray,
    candidate_ids: Sequence[str],
    objects_by_id: Mapping[str, Mapping[str, Any]],
    maximum_sequence_length: int,
    batch_size: int,
    limit: int,
) -> list[CandidateScore]:
    if not candidate_ids:
        return []
    encoded = runtime.encode(
        [str(objects_by_id[identity]["model_text"]) for identity in candidate_ids],
        batch_size=batch_size,
        max_length=maximum_sequence_length,
        return_dense=False,
        return_sparse=False,
        return_colbert_vecs=True,
    )
    rows = [
        CandidateScore(
            compiled_object_id=identity,
            score=float(runtime.colbert_score(query_vector, document_vector).item()),
        )
        for identity, document_vector in zip(candidate_ids, encoded["colbert_vecs"])
    ]
    rows.sort(key=lambda row: (-row.score, row.compiled_object_id))
    return rows[:limit]


def _pairwise_validation(
    *,
    eval_set: Mapping[str, Any],
    bge_runtime: Any,
    qwen_runtime: Any | None,
    qwen_instruction: str,
    maximum_sequence_length: int,
    batch_size: int,
) -> dict[str, Any]:
    rows = [row for row in eval_set.get("queries") or () if row.get("split") == "holdout_unseen_case"]
    route_ids = [
        "bm25_lexical",
        "bge_m3_dense",
        "bge_m3_learned_sparse",
        "bge_m3_multi_vector",
    ]
    if qwen_runtime is not None:
        route_ids.append("qwen3_embedding_0_6b_dense")
    route_totals: dict[str, dict[str, Any]] = {
        route: {"pairwise_wins": 0, "pairwise_total": 0, "top1_positive": 0, "query_count": 0}
        for route in route_ids
    }
    query_details: list[dict[str, Any]] = []
    for query in rows:
        positives = list(query.get("positives") or ())
        negatives = list(query.get("hard_negatives") or ())
        if not positives or not negatives:
            continue
        documents = [*positives, *negatives]
        texts = [str(row["document_text"]) for row in documents]
        query_text = str(query["query_text"])
        bge_documents = bge_runtime.encode(
            texts,
            batch_size=batch_size,
            max_length=maximum_sequence_length,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=True,
        )
        bge_query = bge_runtime.encode(
            [query_text],
            batch_size=1,
            max_length=maximum_sequence_length,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=True,
        )
        tokenized = [tokenize(text) for text in texts]
        from rank_bm25 import BM25Okapi

        bm25_scores = BM25Okapi(tokenized).get_scores(tokenize(query_text))
        bge_dense_scores = np.asarray(bge_documents["dense_vecs"], dtype=np.float32) @ np.asarray(
            bge_query["dense_vecs"][0], dtype=np.float32
        )
        bge_sparse_scores = np.asarray(
            [
                bge_runtime.compute_lexical_matching_score(
                    bge_query["lexical_weights"][0], document
                )
                for document in bge_documents["lexical_weights"]
            ],
            dtype=np.float32,
        )
        bge_multi_scores = np.asarray(
            [
                float(
                    bge_runtime.colbert_score(
                        bge_query["colbert_vecs"][0], document
                    ).item()
                )
                for document in bge_documents["colbert_vecs"]
            ],
            dtype=np.float32,
        )
        route_scores = {
            "bm25_lexical": np.asarray(bm25_scores, dtype=np.float32),
            "bge_m3_dense": bge_dense_scores,
            "bge_m3_learned_sparse": bge_sparse_scores,
            "bge_m3_multi_vector": bge_multi_scores,
        }
        if qwen_runtime is not None:
            qwen_documents = qwen_runtime.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            qwen_query = qwen_runtime.encode(
                [query_text],
                batch_size=1,
                prompt=qwen_instruction,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )[0]
            route_scores["qwen3_embedding_0_6b_dense"] = (
                np.asarray(qwen_documents, dtype=np.float32)
                @ np.asarray(qwen_query, dtype=np.float32)
            )
        detail = {
            "query_id": str(query["query_id"]),
            "case_key": str(query["case_key"]),
            "slot_id": str(query["slot_id"]),
            "positive_count": len(positives),
            "hard_negative_count": len(negatives),
            "routes": {},
        }
        positive_count = len(positives)
        for route_id, scores in route_scores.items():
            wins = sum(
                float(scores[positive_index]) > float(scores[negative_index])
                for positive_index in range(positive_count)
                for negative_index in range(positive_count, len(documents))
            )
            pairs = positive_count * len(negatives)
            top_index = min(
                range(len(documents)),
                key=lambda index: (-float(scores[index]), str(documents[index]["document_id"])),
            )
            top_positive = top_index < positive_count
            totals = route_totals[route_id]
            totals["pairwise_wins"] += wins
            totals["pairwise_total"] += pairs
            totals["top1_positive"] += int(top_positive)
            totals["query_count"] += 1
            detail["routes"][route_id] = {
                "positive_over_hard_negative_pairwise_wins": wins,
                "pairwise_total": pairs,
                "top1_is_positive": top_positive,
                "top1_document_id": str(documents[top_index]["document_id"]),
            }
        query_details.append(detail)
    summaries = {}
    for route_id, totals in route_totals.items():
        summaries[route_id] = {
            **totals,
            "positive_over_hard_negative_pairwise_accuracy": _ratio(
                totals["pairwise_wins"], totals["pairwise_total"]
            ),
            "query_top1_positive_rate": _ratio(
                totals["top1_positive"], totals["query_count"]
            ),
        }
    return {
        "split": "observed_validation_forbidden_from_tuning",
        "query_count": len(query_details),
        "routes": summaries,
        "queries": query_details,
    }


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def run(
    *,
    policy_path: Path,
    bge_model_dir: Path,
    qwen_model_dir: Path | None,
    cache_root: Path,
    qwen_block_code: str | None = None,
) -> dict[str, Any]:
    policy = _read_json(policy_path)
    if policy.get("schema_version") != "fin_ia_s1c_compiled_object_retriever_comparison_policy_v1_0":
        raise ValueError("compiled_object_retriever_policy_invalid")
    bindings = policy["bound_inputs"]
    objects_path = _resolve(bindings["compiled_objects_ref"])
    result_path = _resolve(bindings["compiled_object_result_ref"])
    route_policy_path = _resolve(bindings["query_route_policy_ref"])
    qrels_path = _resolve(bindings["source_level_qrels_ref"])
    review_path = _resolve(bindings["object_role_review_ref"])
    eval_set_path = _resolve(bindings["six_case_role_eval_ref"])
    for path, key, code, tracked_text in (
        (objects_path, "compiled_objects_sha256", "compiled_object_population_drift", False),
        (result_path, "compiled_object_result_sha256", "compiled_object_result_drift", True),
        (route_policy_path, "query_route_policy_sha256", "query_route_policy_drift", True),
        (qrels_path, "source_level_qrels_sha256", "source_level_qrels_drift", True),
        (review_path, "object_role_review_sha256", "object_role_review_drift", True),
        (eval_set_path, "six_case_role_eval_sha256", "six_case_role_eval_drift", True),
    ):
        _validate_binding(
            path,
            str(bindings[key]),
            code,
            tracked_text=tracked_text,
        )
    objects = load_compiled_objects(_read_jsonl(objects_path))
    objects_by_id = {str(row["compiled_object_id"]): row for row in objects}
    queries = load_queries(_read_json(qrels_path))
    review_set = _read_json(review_path)
    eval_set = _read_json(eval_set_path)
    mapping = map_reviewed_objects_to_compiled_successors(objects, review_set)
    budgets = policy["budgets"]
    top_k = int(budgets["top_k"])
    candidate_pool = int(budgets["per_route_candidate_pool"])
    maximum_sequence_length = int(budgets["maximum_sequence_length"])
    batch_size = int(budgets["embedding_batch_size"])
    object_sha256 = _sha256(objects_path)
    bge_identity = _model_identity(bge_model_dir, "BAAI/bge-m3")
    if qwen_model_dir is None and not qwen_block_code:
        raise ValueError("qwen_model_or_typed_block_required")
    qwen_identity = (
        _model_identity(qwen_model_dir, "Qwen/Qwen3-Embedding-0.6B")
        if qwen_model_dir is not None
        else None
    )

    started = time.perf_counter()
    bge_dense, bge_sparse, bge_cache, bge_runtime = _bge_cache(
        objects=objects,
        object_sha256=object_sha256,
        model_dir=bge_model_dir,
        model_identity=bge_identity,
        cache_dir=cache_root / "bge_m3_v1",
        maximum_sequence_length=maximum_sequence_length,
        batch_size=batch_size,
    )
    qwen_dense = None
    qwen_cache = None
    qwen_runtime = None
    if qwen_model_dir is not None and qwen_identity is not None:
        qwen_dense, qwen_cache, qwen_runtime = _qwen_cache(
            objects=objects,
            object_sha256=object_sha256,
            model_dir=qwen_model_dir,
            model_identity=qwen_identity,
            cache_dir=cache_root / "qwen3_embedding_0_6b_v1",
            maximum_sequence_length=maximum_sequence_length,
            batch_size=batch_size,
        )
    qwen_instruction = next(
        str(row["query_instruction"])
        for row in policy["routes"]
        if row["route_id"] == "qwen3_embedding_0_6b_dense"
    )
    semantic_texts = [query.query_text("dense_bge_m3") for query in queries]
    bge_queries = bge_runtime.encode(
        semantic_texts,
        batch_size=batch_size,
        max_length=maximum_sequence_length,
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=True,
    )
    bge_query_sparse = _query_sparse_matrix(
        bge_queries["lexical_weights"], int(bge_sparse.shape[1])
    )
    qwen_queries = (
        qwen_runtime.encode(
            semantic_texts,
            batch_size=batch_size,
            prompt=qwen_instruction,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        if qwen_runtime is not None
        else None
    )
    query_results: list[dict[str, Any]] = []
    route_ids = [
        "bm25_lexical",
        "bge_m3_dense",
        "bge_m3_learned_sparse",
        "bge_m3_multi_vector_refinement",
    ]
    if qwen_runtime is not None:
        route_ids.append("qwen3_embedding_0_6b_dense")
    for query_index, query in enumerate(queries):
        eligible, exclusions = eligible_object_indices(objects, query)
        sparse_bm25 = bm25_rank(
            objects,
            eligible,
            query.query_text("sparse_bm25"),
            limit=candidate_pool,
        )
        bge_dense_rows = dense_rank(
            objects,
            eligible,
            bge_dense,
            bge_queries["dense_vecs"][query_index],
            limit=candidate_pool,
        )
        bge_sparse_rows = sparse_rank(
            objects,
            eligible,
            bge_sparse,
            bge_query_sparse[query_index],
            limit=candidate_pool,
        )
        qwen_rows = (
            dense_rank(
                objects,
                eligible,
                qwen_dense,
                qwen_queries[query_index],
                limit=candidate_pool,
            )
            if qwen_dense is not None and qwen_queries is not None
            else []
        )
        union = union_candidate_ids(
            [
                sparse_bm25,
                bge_dense_rows,
                bge_sparse_rows,
                *([qwen_rows] if qwen_rows else []),
            ],
            maximum=int(budgets["multi_vector_union_maximum"]),
        )
        multi_rows = _multi_vector_rank(
            runtime=bge_runtime,
            query_vector=bge_queries["colbert_vecs"][query_index],
            candidate_ids=union,
            objects_by_id=objects_by_id,
            maximum_sequence_length=maximum_sequence_length,
            batch_size=batch_size,
            limit=candidate_pool,
        )
        route_rows = {
            "bm25_lexical": sparse_bm25,
            "bge_m3_dense": bge_dense_rows,
            "bge_m3_learned_sparse": bge_sparse_rows,
            "bge_m3_multi_vector_refinement": multi_rows,
        }
        if qwen_rows:
            route_rows["qwen3_embedding_0_6b_dense"] = qwen_rows
        reviewed_targets = mapping["positive_compiled_object_ids_by_query"].get(
            query.qrel_id, []
        )
        routes = {
            route_id: evaluate_route(
                rows,
                objects_by_id,
                target_source_record_ids=query.target_current_source_record_ids,
                reviewed_positive_object_ids=reviewed_targets,
                top_k=top_k,
            )
            for route_id, rows in route_rows.items()
        }
        routes["bge_m3_multi_vector_refinement"]["candidate_union_count"] = len(union)
        routes["bge_m3_multi_vector_refinement"]["target_source_in_candidate_union"] = any(
            set(query.target_current_source_record_ids)
            & (
                set(objects_by_id[identity].get("lineage_source_record_ids") or ())
                | {str(objects_by_id[identity]["base_object_view"]["source_record_id"])}
            )
            for identity in union
        )
        query_results.append(
            {
                "qrel_id": query.qrel_id,
                "case_key": query.case_key,
                "evidence_slot_id": query.evidence_slot_id,
                "evidence_owner_ticker": query.evidence_owner_ticker,
                "relationship_direction": query.relationship_direction,
                "target_source_record_ids": list(query.target_current_source_record_ids),
                "reviewed_positive_compiled_object_ids": reviewed_targets,
                "eligible_object_count": int(eligible.size),
                "exclusion_counts": exclusions,
                "labels_joined_after_candidate_generation": True,
                "routes": routes,
            }
        )
        print(
            json.dumps(
                {
                    "progress": f"{query_index + 1}/{len(queries)}",
                    "qrel_id": query.qrel_id,
                    "eligible_objects": int(eligible.size),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    validation = _pairwise_validation(
        eval_set=eval_set,
        bge_runtime=bge_runtime,
        qwen_runtime=qwen_runtime,
        qwen_instruction=qwen_instruction,
        maximum_sequence_length=maximum_sequence_length,
        batch_size=batch_size,
    )
    elapsed = time.perf_counter() - started
    route_summary = {
        route_id: route_metrics(query_results, route_id) for route_id in route_ids
    }
    persistent_cache_bytes = sum(
        path.stat().st_size for path in cache_root.rglob("*") if path.is_file()
    )
    unsigned = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": (
            "compiled_object_retriever_comparison_complete_no_promotion"
            if qwen_runtime is not None
            else "compiled_object_bm25_bge_comparison_complete_qwen_transport_blocked"
        ),
        "recorded_at": "2026-08-12",
        "bound_inputs": {
            "policy_ref": _relative(policy_path),
            "policy_sha256": _sha256(policy_path),
            "compiled_objects_ref": _relative(objects_path),
            "compiled_objects_sha256": object_sha256,
            "compiled_object_count": len(objects),
            "source_level_qrels_ref": _relative(qrels_path),
            "source_level_qrels_sha256": _sha256_lf_text(qrels_path),
            "object_role_review_ref": _relative(review_path),
            "object_role_review_sha256": _sha256_lf_text(review_path),
            "six_case_role_eval_ref": _relative(eval_set_path),
            "six_case_role_eval_sha256": _sha256_lf_text(eval_set_path),
        },
        "execution": {
            "device": "cuda",
            "elapsed_seconds": round(elapsed, 3),
            "generation_model_calls": 0,
            "network_source_calls": 0,
            "training_steps": 0,
            "bge_model_identity": bge_identity,
            "qwen_model_identity": qwen_identity,
            "qwen_execution_state": (
                "executed" if qwen_runtime is not None else "not_executed_transport_blocked"
            ),
            "qwen_block_code": qwen_block_code,
            "bge_cache": bge_cache,
            "qwen_cache": qwen_cache,
            "persistent_cache_bytes": persistent_cache_bytes,
            "persistent_cache_within_budget": persistent_cache_bytes
            <= int(budgets["maximum_persistent_cache_bytes"]),
        },
        "evaluation_contract": {
            "source_record_target_is_not_object_target": True,
            "reviewed_object_successor_mapping": mapping,
            "legacy_whole_table_to_metric_row_projection": False,
            "multi_vector_scope": "candidate_union_refinement_not_full_corpus",
            "candidate_is_not_evidence": True,
            "numeric_authority": False,
        },
        "primary_full_corpus_comparison": {
            "query_count": len(query_results),
            "top_k": top_k,
            "candidate_pool": candidate_pool,
            "routes": route_summary,
            "queries": query_results,
        },
        "observed_validation_pairwise_comparison": validation,
        "database_lane": {
            "status": str(policy["database_lane"]["required_runtime_state_during_comparison"]),
            "owning_stage": "S2",
            "ranking_model_granted_numeric_authority": False,
            "company_financial_fact_mart_built": False,
        },
        "authority": {
            "route_promoted": False,
            "fine_tuning_authorized": False,
            "evidence_promoted": False,
            "numeric_fact_authority": False,
            "s1_complete_claimed": False,
            "s2_complete_claimed": False,
            "provisional_winner_decision_pending_business_review": True,
            "full_retriever_matrix_complete": qwen_runtime is not None,
        },
        "known_boundary": str(policy["known_boundary"]),
    }
    return {**unsigned, "result_digest": canonical_digest(unsigned)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare BM25, BGE-M3 dense/learned-sparse/multi-vector and Qwen3 "
            "Embedding over the same compiled candidate objects."
        )
    )
    parser.add_argument(
        "--policy",
        default=(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1c_compiled_object_retriever_comparison_policy_v1_0.json"
        ),
    )
    parser.add_argument("--bge-model", required=True)
    parser.add_argument("--qwen-model")
    parser.add_argument(
        "--qwen-block-code",
        help="Required typed reason when --qwen-model is intentionally absent.",
    )
    parser.add_argument(
        "--cache-root",
        default=(
            "data/workbench_private/"
            "fin_0_1_3_s1c_compiled_object_retriever_comparison/model_cache_v1"
        ),
    )
    parser.add_argument(
        "--output",
        default=(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1c_compiled_object_retriever_comparison_result_v1_0.json"
        ),
    )
    parser.add_argument(
        "--full-output-dir",
        default=(
            "data/workbench_private/"
            "fin_0_1_3_s1c_compiled_object_retriever_comparison/"
            "v1"
        ),
        help=(
            "Ignored private directory for content-addressed candidate excerpts and "
            "full pairwise details; --output receives only the compact tracked summary."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run(
        policy_path=_resolve(args.policy),
        bge_model_dir=_resolve(args.bge_model),
        qwen_model_dir=_resolve(args.qwen_model) if args.qwen_model else None,
        cache_root=_resolve(args.cache_root),
        qwen_block_code=args.qwen_block_code,
    )
    full_output = _resolve(args.full_output_dir) / (
        f"full_result_{result['result_digest']}.json"
    )
    _write_json(full_output, result)
    summary = _compact_result(
        result,
        full_output=full_output,
        full_output_sha256=_sha256(full_output),
    )
    output = _resolve(args.output)
    _write_json(output, summary)
    print(
        json.dumps(
            {
                "status": summary["status"],
                "execution": {
                    key: value
                    for key, value in summary["execution"].items()
                    if key not in {"bge_model_identity", "qwen_model_identity"}
                },
                "routes": summary["primary_full_corpus_comparison"]["routes"],
                "observed_validation": summary["observed_validation_pairwise_comparison"]["routes"],
                "authority": summary["authority"],
                "full_result_digest": result["result_digest"],
                "summary_result_digest": summary["result_digest"],
                "full_output": _relative(full_output),
                "output": _relative(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
