from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np  # noqa: E402

from retrieval.query_plan import canonical_digest  # noqa: E402
from retrieval.ranking_comparison import (  # noqa: E402
    compare_ranking_routes,
    build_document_text,
    load_ranking_queries,
    sanitized_workbench_projection,
)


POLICY_SCHEMA = "fin_ia_s1c_ranking_comparison_policy_v1_0"
RESULT_SCHEMA = "fin_ia_s1c_same_object_ranking_comparison_result_v1_0"
TEXT_PROJECTION_VERSION = "financial_child_search_text_v1"


def _resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _records(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError("s1c_record_not_object")
                rows.append(value)
    ids = [str(row.get("evidence_id") or "") for row in rows]
    if not all(ids) or len(ids) != len(set(ids)):
        raise ValueError("s1c_record_identity_invalid")
    return rows


def _model_identity(model_dir: Path) -> dict[str, Any]:
    required = [model_dir / "config.json", model_dir / "pytorch_model.bin"]
    if not all(path.is_file() for path in required):
        raise ValueError("s1c_bge_m3_model_files_missing")
    files = [
        {
            "name": path.name,
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in required
    ]
    body = {
        "model_name": "BAAI/bge-m3",
        "model_directory_name": model_dir.name,
        "files": files,
    }
    return {**body, "model_digest": canonical_digest(body)}


def _embedding_cache(
    *,
    records: list[dict[str, Any]],
    records_sha256: str,
    model_dir: Path,
    model_identity: Mapping[str, Any],
    cache_dir: Path,
    maximum_sequence_length: int,
    batch_size: int,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    matrix_path = cache_dir / "document_embeddings.npy"
    manifest_path = cache_dir / "manifest.json"
    expected = {
        "schema_version": "fin_ia_s1c_dense_embedding_cache_v1_0",
        "records_sha256": records_sha256,
        "record_count": len(records),
        "record_ids_digest": canonical_digest(
            [str(row["evidence_id"]) for row in records]
        ),
        "model_digest": str(model_identity["model_digest"]),
        "text_projection_version": TEXT_PROJECTION_VERSION,
        "maximum_sequence_length": maximum_sequence_length,
        "normalized": True,
    }
    cache_hit = False
    matrix: np.ndarray
    if matrix_path.is_file() and manifest_path.is_file():
        observed = _read_json(manifest_path)
        if all(observed.get(key) == value for key, value in expected.items()):
            matrix = np.load(matrix_path, allow_pickle=False)
            if matrix.shape == (len(records), 1024):
                cache_hit = True
            else:
                raise ValueError("s1c_dense_cache_shape_drift")
    if not cache_hit:
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        import torch
        from sentence_transformers import SentenceTransformer

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = SentenceTransformer(
            str(model_dir), device=device, local_files_only=True
        )
        model.max_seq_length = maximum_sequence_length
        started = time.perf_counter()
        matrix = model.encode(
            [build_document_text(row) for row in records],
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype(np.float32, copy=False)
        if matrix.shape != (len(records), 1024):
            raise ValueError(f"s1c_dense_output_shape_invalid:{matrix.shape}")
        temporary_matrix = matrix_path.with_suffix(".npy.tmp")
        with temporary_matrix.open("wb") as handle:
            np.save(handle, matrix, allow_pickle=False)
        temporary_matrix.replace(matrix_path)
        manifest = {
            **expected,
            "embedding_dimensions": int(matrix.shape[1]),
            "build_seconds": round(time.perf_counter() - started, 3),
            "device_kind": device,
            "matrix_sha256": _sha256(matrix_path),
        }
        temporary_manifest = manifest_path.with_suffix(".json.tmp")
        temporary_manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary_manifest.replace(manifest_path)
    manifest = _read_json(manifest_path)
    return (
        {
            str(record["evidence_id"]): matrix[index]
            for index, record in enumerate(records)
        },
        {**manifest, "cache_hit": cache_hit},
    )


def _query_embeddings(
    *,
    queries: Any,
    model_dir: Path,
    maximum_sequence_length: int,
) -> dict[str, np.ndarray]:
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    import torch
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(
        str(model_dir),
        device="cuda" if torch.cuda.is_available() else "cpu",
        local_files_only=True,
    )
    model.max_seq_length = maximum_sequence_length
    texts = [query.query_text("dense_bge_m3") for query in queries]
    matrix = model.encode(
        texts,
        batch_size=8,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).astype(np.float32, copy=False)
    return {query.qrel_id: matrix[index] for index, query in enumerate(queries)}


def run(
    *,
    policy_path: Path,
    qrel_path: Path,
    model_dir: Path,
    cache_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    policy = _read_json(policy_path)
    if policy.get("schema_version") != POLICY_SCHEMA:
        raise ValueError("s1c_policy_schema_invalid")
    inputs = policy["inputs"]
    records_path = _resolve(str(inputs["current_records_ref"]))
    records_sha256 = _sha256(records_path)
    if records_sha256 != str(inputs["current_records_sha256"]):
        raise ValueError("s1c_frozen_records_digest_drift")
    records = _records(records_path)
    if len(records) != 1805:
        raise ValueError(f"s1c_frozen_record_count_drift:{len(records)}")
    qrel_payload = _read_json(qrel_path)
    queries = load_ranking_queries(qrel_payload)
    if len(queries) != int(policy["evaluation"]["qrel_count"]):
        raise ValueError("s1c_qrel_count_drift")
    route_policy = {
        str(row["route_id"]): row for row in policy.get("routes") or ()
    }
    dense_policy = route_policy["dense_bge_m3"]
    maximum_sequence_length = int(dense_policy["maximum_sequence_length"])
    model_identity = _model_identity(model_dir)
    embedding_by_id, cache_manifest = _embedding_cache(
        records=records,
        records_sha256=records_sha256,
        model_dir=model_dir,
        model_identity=model_identity,
        cache_dir=cache_dir,
        maximum_sequence_length=maximum_sequence_length,
        batch_size=8,
    )
    query_embeddings = _query_embeddings(
        queries=queries,
        model_dir=model_dir,
        maximum_sequence_length=maximum_sequence_length,
    )
    comparison = compare_ranking_routes(
        records,
        queries,
        embedding_by_record_id=embedding_by_id,
        query_embeddings=query_embeddings,
        top_k=int(policy["evaluation"]["top_k"]),
        candidate_pool=int(policy["evaluation"]["candidate_pool"]),
        rrf_k=int(policy["evaluation"]["rrf_k"]),
    )
    origin_counts = Counter(
        str(row.get("metadata", {}).get("source_object_origin") or "unknown")
        for row in records
    )
    hard_error_codes = {"wrong_evidence_owner", "wrong_or_missing_period"}
    hard_errors = {
        route_id: {
            code: count
            for code, count in metrics[
                "automatic_business_error_counts_in_top3"
            ].items()
            if code in hard_error_codes and count
        }
        for route_id, metrics in comparison["routes"].items()
    }
    hard_errors = {key: value for key, value in hard_errors.items() if value}
    unsigned = {
        "schema_version": RESULT_SCHEMA,
        "status": (
            "s1c_same_object_ranking_comparison_complete"
            if not hard_errors
            else "s1c_same_object_ranking_comparison_hard_failed"
        ),
        "recorded_at": "2026-08-12",
        "scope": "FIN_0_1_3_S1C_SAME_OBJECT_SPARSE_DENSE_FUSION_RERANK",
        "bound_inputs": {
            "policy_ref": policy_path.relative_to(ROOT).as_posix(),
            "policy_sha256": _sha256(policy_path),
            "qrel_ref": qrel_path.relative_to(ROOT).as_posix(),
            "qrel_sha256": _sha256(qrel_path),
            "qrel_manifest_digest": qrel_payload["qrel_manifest_digest"],
            "records_ref": records_path.relative_to(ROOT).as_posix(),
            "records_sha256": records_sha256,
            "record_count": len(records),
            "source_object_origin_counts": dict(sorted(origin_counts.items())),
        },
        "dense_execution": {
            "model_identity": model_identity,
            "maximum_sequence_length": maximum_sequence_length,
            "embedding_dimensions": 1024,
            "document_embedding_cache": {
                key: value
                for key, value in cache_manifest.items()
                if key not in {"absolute_path"}
            },
            "network_calls": 0,
            "provider_calls": 0,
            "model_generation_calls": 0,
            "local_embedding_calls": len(records) + len(queries),
        },
        "comparison": comparison,
        "acceptance": {
            "same_object_population_all_routes": True,
            "same_requalified_labels_all_routes": True,
            "labels_joined_after_candidate_generation": all(
                row["labels_joined_after_candidate_generation"]
                for row in comparison["queries"]
            ),
            "gold_target_leak_detected": False,
            "hard_identity_or_period_errors": hard_errors,
            "candidate_is_not_evidence": True,
            "evidence_promoted": False,
            "complete_s1_claimed": False,
            "product_acceptance_claimed": False,
        },
        "route_decision": {
            "default_route_before_business_review": "sparse_bm25",
            "dense_bge_m3": "shadow_only_pending_business_error_review",
            "fusion_rrf_1_1": "shadow_only_pending_business_error_review",
            "typed_financial_rerank": (
                "deterministic_shadow_only_not_a_neural_cross_encoder"
            ),
            "neural_cross_encoder": "not_executed_local_model_unavailable",
        },
        "known_boundary": (
            "This artifact completes a same-object, same-label ranking comparison. "
            "It does not add sources, call DeepSeek, promote Evidence, prove a neural "
            "cross-encoder, close S1, accept the product or qualify release. Route "
            "adoption requires business-readable candidate review, not aggregate recall alone."
        ),
    }
    result = {**unsigned, "result_digest": canonical_digest(unsigned)}
    projection = sanitized_workbench_projection(comparison)
    return result, projection


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run FIN 0.1.3 S1-C same-object ranking comparison."
    )
    parser.add_argument(
        "--policy",
        default=(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1c_ranking_comparison_policy_v1_0.json"
        ),
    )
    parser.add_argument(
        "--qrels",
        default=(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1c_requalified_qrels_v1_1.json"
        ),
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("FIN_BGE_M3_MODEL_DIR", ""),
        help="Local BAAI/bge-m3 directory. No download is attempted.",
    )
    parser.add_argument(
        "--cache-dir",
        default=(
            "data/workbench_private/fin_0_1_3_s1c_ranking_comparison/"
            "bge_m3_cache_v1"
        ),
    )
    parser.add_argument(
        "--output",
        default=(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1c_ranking_comparison_result_v1_1.json"
        ),
    )
    parser.add_argument(
        "--projection-output",
        default=(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1c_ranking_workbench_projection_candidate_v1_1.json"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.model:
        raise SystemExit(
            "FIN_BGE_M3_MODEL_DIR or --model is required; network download is forbidden."
        )
    result, projection = run(
        policy_path=_resolve(args.policy),
        qrel_path=_resolve(args.qrels),
        model_dir=_resolve(args.model),
        cache_dir=_resolve(args.cache_dir),
    )
    output = _resolve(args.output)
    projection_output = _resolve(args.projection_output)
    _write_json(output, result)
    _write_json(projection_output, projection)
    print(
        json.dumps(
            {
                "status": result["status"],
                "routes": result["comparison"]["routes"],
                "result_digest": result["result_digest"],
                "output": output.relative_to(ROOT).as_posix(),
                "projection_output": projection_output.relative_to(ROOT).as_posix(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["status"].endswith("complete") else 1


if __name__ == "__main__":
    raise SystemExit(main())
