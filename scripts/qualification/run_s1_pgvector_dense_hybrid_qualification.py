from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any, Mapping, Sequence

import numpy as np

from scripts.qualification.run_s1_pgvector_candidate_plane import (
    EXPECTED_DENSE_SHA256,
    EXPECTED_MANIFEST_SHA256,
    EXPECTED_OBJECTS_SHA256,
    EXPECTED_QREL_MANIFEST_DIGEST,
    EXPECTED_QRELS_SHA256,
    QrelFilter,
    QualificationError,
    _database_receipt,
    _filter_clause,
    _load_and_validate_inputs,
    _object_eligible,
    _read_json,
    _roundtrip_and_vector_receipt,
    _target_ids,
    _validate_receipt,
    _validate_qrels_payload,
    canonical_digest,
    qrel_filter,
    sha256_file,
)


SCHEMA_VERSION = "fin_ia_s1_pgvector_dense_hybrid_qualification_v1_0"
CANDIDATE_ARTIFACT_SCHEMA_VERSION = (
    "fin_ia_s1_pgvector_dense_hybrid_label_free_candidates_v1_0"
)
QUALIFICATION_ROOT = Path(r"Z:\FIN_Insight_Agent_qualification")
IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
EXPECTED_RUNTIME_POLICY_SHA256 = (
    "6857a41fea14cd3ffd0e9e524a11d06955287a6bd28f37e63e9d1eb102df53ac"
)
EXPECTED_QUERY_MANIFEST_SHA256 = (
    "225fb2787fcaf769c053cf35d5b41552c0e3a1f6859e04f23599e1881ce190d9"
)
EXPECTED_QUERY_MANIFEST_RESULT_DIGEST = (
    "b959d602d3dc4db1aa8eeb98ecc3c4bab5ff9615bc2c580255f01faa365d70d5"
)
EXPECTED_QUERY_EMBEDDINGS_SHA256 = (
    "b2b200d57188098b20df09a0d366441d685a2adf90a01bb6229ae33ce084188f"
)
EXPECTED_QUERY_TEXT_DIGEST = (
    "993d7adaf686666029a7888435880507f885b4caf31e1f6106b69c9077dca5e2"
)
EXPECTED_PROMPTED_INPUT_DIGEST = (
    "6a22eb4f48666dc95fea06e176624380901dba30319b99a82800fe94a66bf086"
)
EXPECTED_INFERENCE_PACKAGE_DIGEST = (
    "6b2038c8c4b044a7feff6909abc6c84537abd4da2ce1ace9cf84e0c75ddefe66"
)
EXPECTED_MODEL_DIGEST = (
    "4a3dd5cbc715bf1031d9d10ed6c7f43ff38f2ac5bc19b7fbcdc21787c68be76c"
)
EXPECTED_CANDIDATE_PLANE_RECEIPT_SHA256 = (
    "378aa1b41a86d3b1eae559468551816eccf7b1b866489784e542b31ce31ec552"
)
EXPECTED_CANDIDATE_PLANE_RESULT_DIGEST = (
    "7442133c80e5c1afd4bfb09e3b9b2f06e1cc72269a5c8199f1a164f43ac4f264"
)
EXPECTED_OBJECT_IDENTITY_DIGEST = (
    "bde43d59fde98f59e4e11ad3354beea9cc2001067b9d7135afa7f3666e0eb98d"
)
EXPECTED_BM25_ORDERED_TOP64_BUNDLE_DIGEST = (
    "03ae09426f006091519a5d35c08072a1bb74197eb06fa4e8ceb0abaca6dd140c"
)
EXPECTED_TOKENIZER_SOURCE_SHA256 = (
    "7f9effe19633ff91ef27c2736a7095dbe27d6b21adb8221ecbf2daa4335347ae"
)
EXPECTED_CANDIDATE_PLANE_SCRIPT_SHA256 = (
    "ac37d67985b20af60bcdc27521abaab1185d86d46486e99d6f746b0af9bda0eb"
)
EXPECTED_POSTGRES_SERVER_VERSION = "16.15 (Debian 16.15-1.pgdg13+2)"
EXPECTED_PGVECTOR_EXTENSION_VERSION = "0.8.6"
EXPECTED_CLIENT_RUNTIME_VERSIONS = {
    "numpy": "2.4.6",
    "pgvector": "0.5.0",
    "psutil": "7.2.2",
    "psycopg": "3.3.4",
    "rank-bm25": "0.2.2",
}
FIRST_STAGE_LIMIT = 64
RRF_K = 60
PRODUCT_UNION_LIMIT = 96
MAXIMUM_RAW_UNION = FIRST_STAGE_LIMIT * 2
EXPECTED_BM25_BASELINE = {
    "target_in_top_16": 13,
    "target_in_top_64": 17,
    "mean_reciprocal_rank_at_64": 0.52577384,
}


@dataclass(frozen=True)
class RankingSpec:
    qrel_id: str
    filters: QrelFilter
    sparse_query_text: str


def _qualification_path(path: Path) -> Path:
    resolved = path.resolve()
    root = QUALIFICATION_ROOT.resolve()
    try:
        common = Path(os.path.commonpath((str(root), str(resolved))))
    except ValueError as exc:
        raise QualificationError(
            f"qualification_path_drive_mismatch:{path}"
        ) from exc
    if str(common).casefold() != str(root).casefold() or resolved == root:
        raise QualificationError(f"qualification_path_outside_root:{path}")
    return resolved


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _git_state(repository_root: Path) -> dict[str, Any]:
    def invoke(*arguments: str) -> str:
        return subprocess.run(
            ["git", "-C", str(repository_root), *arguments],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    status = invoke("status", "--short")
    return {
        "head": invoke("rev-parse", "HEAD"),
        "branch": invoke("branch", "--show-current"),
        "dirty": bool(status),
        "status_digest": canonical_digest(status.splitlines()),
    }


def _tokenize(text: str) -> list[str]:
    """Exact copy of src/retrieval/text.py::tokenize for an isolated lab env."""
    return re.findall(r"[a-z0-9][a-z0-9&'/-]*", text.lower())


def _query_text(values: Any, *, field: str) -> str:
    rows = [str(value).strip() for value in values or () if str(value).strip()]
    if not rows:
        raise QualificationError(f"qrel_{field}_missing")
    return "\n".join(rows)


def _ranking_specs(qrels: Sequence[Mapping[str, Any]]) -> list[RankingSpec]:
    specs: list[RankingSpec] = []
    all_targets = [target for qrel in qrels for target in _target_ids(qrel)]
    for qrel in qrels:
        qrel_id = str(qrel.get("qrel_id") or "")
        sparse_text = _query_text(
            qrel.get("sparse_query_texts"), field="sparse_query_text"
        )
        semantic_text = _query_text(
            qrel.get("semantic_query_texts"), field="semantic_query_text"
        )
        combined = f"{sparse_text}\n{semantic_text}".casefold()
        if any(target.casefold() in combined for target in all_targets):
            raise QualificationError(f"cross_qrel_target_leakage:{qrel_id}")
        specs.append(
            RankingSpec(
                qrel_id=qrel_id,
                filters=qrel_filter(qrel),
                sparse_query_text=sparse_text,
            )
        )
    return specs


def _validate_runtime_policy(path: Path) -> dict[str, Any]:
    if sha256_file(path) != EXPECTED_RUNTIME_POLICY_SHA256:
        raise QualificationError("runtime_policy_digest_mismatch")
    policy = _read_json(path)
    contract = policy.get("candidate_contract")
    if not isinstance(contract, Mapping):
        raise QualificationError("candidate_contract_missing")
    observed = {
        "first_stage_limit": int(contract.get("first_stage_limit") or 0),
        "candidate_union_limit": int(contract.get("candidate_union_limit") or 0),
        "output_limit": int(contract.get("output_limit") or 0),
    }
    expected = {
        "first_stage_limit": FIRST_STAGE_LIMIT,
        "candidate_union_limit": PRODUCT_UNION_LIMIT,
        "output_limit": 16,
    }
    if observed != expected:
        raise QualificationError(f"candidate_contract_drift:{observed}:{expected}")
    return policy


def _validate_candidate_plane_receipt(
    path: Path, *, schema: str
) -> dict[str, Any]:
    if sha256_file(path) != EXPECTED_CANDIDATE_PLANE_RECEIPT_SHA256:
        raise QualificationError("candidate_plane_receipt_file_digest_mismatch")
    receipt = _read_json(path)
    unsigned = dict(receipt)
    result_digest = str(unsigned.pop("result_digest", ""))
    if (
        result_digest != EXPECTED_CANDIDATE_PLANE_RESULT_DIGEST
        or canonical_digest(unsigned) != result_digest
    ):
        raise QualificationError("candidate_plane_receipt_result_digest_mismatch")
    candidate = receipt.get("candidate")
    inputs = receipt.get("inputs")
    database = receipt.get("database")
    roundtrip = receipt.get("roundtrip")
    if not all(
        isinstance(value, Mapping)
        for value in (candidate, inputs, database, roundtrip)
    ):
        raise QualificationError("candidate_plane_receipt_sections_missing")
    assert isinstance(candidate, Mapping)
    assert isinstance(inputs, Mapping)
    assert isinstance(database, Mapping)
    assert isinstance(roundtrip, Mapping)
    observed = {
        "status": receipt.get("status"),
        "schema": candidate.get("schema"),
        "operation_mode": candidate.get("operation_mode"),
        "objects_sha256": inputs.get("objects_sha256"),
        "dense_sha256": inputs.get("dense_sha256"),
        "manifest_sha256": inputs.get("manifest_sha256"),
        "qrels_sha256": inputs.get("qrels_sha256"),
        "object_identity_digest": inputs.get("object_identity_digest"),
        "server_version": database.get("server_version"),
        "pgvector_extension_version": database.get("pgvector_extension_version"),
        "object_count": database.get("object_count"),
        "authority_violation_count": database.get("authority_violation_count"),
        "roundtrip": roundtrip.get("all_identity_payload_embedding_roundtrip"),
        "database_identity_digest": roundtrip.get(
            "database_object_identity_digest"
        ),
    }
    expected = {
        "status": "bounded_development_restart_readback_pass",
        "schema": schema,
        "operation_mode": "verify_existing_after_restart",
        "objects_sha256": EXPECTED_OBJECTS_SHA256,
        "dense_sha256": EXPECTED_DENSE_SHA256,
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "qrels_sha256": EXPECTED_QRELS_SHA256,
        "object_identity_digest": EXPECTED_OBJECT_IDENTITY_DIGEST,
        "server_version": EXPECTED_POSTGRES_SERVER_VERSION,
        "pgvector_extension_version": EXPECTED_PGVECTOR_EXTENSION_VERSION,
        "object_count": 34199,
        "authority_violation_count": 0,
        "roundtrip": True,
        "database_identity_digest": EXPECTED_OBJECT_IDENTITY_DIGEST,
    }
    if observed != expected:
        raise QualificationError(
            f"candidate_plane_receipt_contract_mismatch:{observed}:{expected}"
        )
    return {
        "receipt_sha256": EXPECTED_CANDIDATE_PLANE_RECEIPT_SHA256,
        "result_digest": result_digest,
        "attempt_id": receipt.get("attempt_id"),
        "status": receipt.get("status"),
    }


def _validate_client_runtime_versions() -> dict[str, str]:
    observed = {
        "numpy": np.__version__,
        "pgvector": importlib.metadata.version("pgvector"),
        "psutil": importlib.metadata.version("psutil"),
        "psycopg": importlib.metadata.version("psycopg"),
        "rank-bm25": importlib.metadata.version("rank-bm25"),
    }
    if observed != EXPECTED_CLIENT_RUNTIME_VERSIONS:
        raise QualificationError(
            f"client_runtime_version_drift:{observed}:{EXPECTED_CLIENT_RUNTIME_VERSIONS}"
        )
    return observed


def _validate_query_artifact(
    *,
    query_manifest_path: Path,
    query_embeddings_path: Path,
    qrel_ids: Sequence[str],
) -> tuple[np.ndarray, dict[str, Any], dict[str, Any]]:
    if sha256_file(query_manifest_path) != EXPECTED_QUERY_MANIFEST_SHA256:
        raise QualificationError("query_manifest_file_digest_mismatch")
    manifest = _read_json(query_manifest_path)
    unsigned = dict(manifest)
    result_digest = str(unsigned.pop("result_digest", ""))
    if (
        result_digest != EXPECTED_QUERY_MANIFEST_RESULT_DIGEST
        or canonical_digest(unsigned) != result_digest
    ):
        raise QualificationError("query_manifest_result_digest_mismatch")
    if manifest.get("status") != "bounded_development_query_embedding_pass":
        raise QualificationError("query_embedding_status_mismatch")
    authority = manifest.get("authority")
    if not (
        isinstance(authority, Mapping)
        and authority.get("candidate_is_not_evidence") is True
        and authority.get("development_qrels_only") is True
        and authority.get("blind_qualification") is False
        and authority.get("evidence_admission_authorized") is False
        and authority.get("production_cutover_authorized") is False
    ):
        raise QualificationError("query_embedding_authority_mismatch")
    inputs = manifest.get("inputs")
    model = manifest.get("model")
    output = manifest.get("output")
    if not all(isinstance(value, Mapping) for value in (inputs, model, output)):
        raise QualificationError("query_manifest_sections_missing")
    assert isinstance(inputs, Mapping)
    assert isinstance(model, Mapping)
    assert isinstance(output, Mapping)
    observed_contract = {
        "qrels_sha256": inputs.get("qrels_sha256"),
        "qrel_manifest_digest": inputs.get("qrel_manifest_digest"),
        "query_text_digest": inputs.get("query_text_digest"),
        "prompted_input_digest": inputs.get("prompted_input_digest"),
        "qrel_order": list(inputs.get("qrel_order") or ()),
        "model_digest": (model.get("model_identity") or {}).get("model_digest"),
        "inference_package_digest": (
            model.get("inference_package_identity") or {}
        ).get("package_digest"),
        "embedding_sha256": output.get("embedding_sha256"),
        "shape": list(output.get("shape") or ()),
        "dtype": output.get("dtype"),
    }
    expected_contract = {
        "qrels_sha256": EXPECTED_QRELS_SHA256,
        "qrel_manifest_digest": EXPECTED_QREL_MANIFEST_DIGEST,
        "query_text_digest": EXPECTED_QUERY_TEXT_DIGEST,
        "prompted_input_digest": EXPECTED_PROMPTED_INPUT_DIGEST,
        "qrel_order": list(qrel_ids),
        "model_digest": EXPECTED_MODEL_DIGEST,
        "inference_package_digest": EXPECTED_INFERENCE_PACKAGE_DIGEST,
        "embedding_sha256": EXPECTED_QUERY_EMBEDDINGS_SHA256,
        "shape": [len(qrel_ids), 1024],
        "dtype": "float32",
    }
    if observed_contract != expected_contract:
        raise QualificationError(
            f"query_artifact_contract_mismatch:{observed_contract}:{expected_contract}"
        )
    if sha256_file(query_embeddings_path) != EXPECTED_QUERY_EMBEDDINGS_SHA256:
        raise QualificationError("query_embeddings_file_digest_mismatch")
    embeddings = np.load(query_embeddings_path, allow_pickle=False)
    if embeddings.shape != (len(qrel_ids), 1024) or embeddings.dtype != np.float32:
        raise QualificationError("query_embeddings_shape_or_dtype_mismatch")
    if not np.isfinite(embeddings).all():
        raise QualificationError("query_embeddings_non_finite")
    norms = np.linalg.norm(embeddings, axis=1)
    if float(norms.min()) < 0.999 or float(norms.max()) > 1.001:
        raise QualificationError("query_embeddings_norm_drift")
    receipt = {
        "query_manifest_sha256": EXPECTED_QUERY_MANIFEST_SHA256,
        "query_manifest_result_digest": result_digest,
        "query_embeddings_sha256": EXPECTED_QUERY_EMBEDDINGS_SHA256,
        "query_text_digest": EXPECTED_QUERY_TEXT_DIGEST,
        "prompted_input_digest": EXPECTED_PROMPTED_INPUT_DIGEST,
        "model_digest": EXPECTED_MODEL_DIGEST,
        "inference_package_digest": EXPECTED_INFERENCE_PACKAGE_DIGEST,
        "shape": list(embeddings.shape),
        "dtype": str(embeddings.dtype),
        "minimum_l2_norm": float(norms.min()),
        "maximum_l2_norm": float(norms.max()),
    }
    return embeddings, manifest, receipt


def _eligible_indices(
    objects: Sequence[Mapping[str, Any]], filters: QrelFilter
) -> list[int]:
    return [
        index
        for index, row in enumerate(objects)
        if _object_eligible(row, filters)
    ]


def _candidate_rows_from_scores(
    *,
    objects: Sequence[Mapping[str, Any]],
    eligible_indices: Sequence[int],
    scores: Sequence[float],
    limit: int,
) -> list[dict[str, Any]]:
    ranked = sorted(
        range(len(eligible_indices)),
        key=lambda local_index: (
            -float(scores[local_index]),
            str(objects[eligible_indices[local_index]]["compiled_object_id"]),
        ),
    )[:limit]
    return [
        {
            "compiled_object_id": str(
                objects[eligible_indices[local_index]]["compiled_object_id"]
            ),
            "score": float(scores[local_index]),
        }
        for local_index in ranked
    ]


def _numpy_exact(
    *,
    objects: Sequence[Mapping[str, Any]],
    dense: Any,
    eligible_indices: Sequence[int],
    query: np.ndarray,
    limit: int,
) -> list[dict[str, Any]]:
    if not eligible_indices:
        return []
    matrix = np.asarray(dense[list(eligible_indices)], dtype=np.float32)
    scores = matrix @ np.asarray(query, dtype=np.float32)
    return _candidate_rows_from_scores(
        objects=objects,
        eligible_indices=eligible_indices,
        scores=scores,
        limit=limit,
    )


def _bm25(
    *,
    objects: Sequence[Mapping[str, Any]],
    eligible_indices: Sequence[int],
    query_text: str,
    limit: int,
) -> list[dict[str, Any]]:
    from rank_bm25 import BM25Okapi

    query_tokens = _tokenize(query_text)
    if not eligible_indices or not query_tokens:
        return []
    corpus = [
        _tokenize(str(objects[index].get("model_text") or ""))
        for index in eligible_indices
    ]
    scores = BM25Okapi(corpus).get_scores(query_tokens)
    return _candidate_rows_from_scores(
        objects=objects,
        eligible_indices=eligible_indices,
        scores=scores,
        limit=limit,
    )


def reciprocal_rank_fusion(
    routes: Sequence[Sequence[Mapping[str, Any]]],
    *,
    rrf_k: int = RRF_K,
    limit: int = PRODUCT_UNION_LIMIT,
) -> list[dict[str, Any]]:
    if rrf_k <= 0 or limit <= 0:
        raise QualificationError("rrf_parameters_invalid")
    scores: dict[str, float] = {}
    for route in routes:
        identities: set[str] = set()
        for rank, row in enumerate(route, start=1):
            identity = str(row["compiled_object_id"])
            if identity in identities:
                raise QualificationError(f"rrf_route_duplicate:{identity}")
            identities.add(identity)
            scores[identity] = scores.get(identity, 0.0) + 1.0 / (rrf_k + rank)
    ordered = sorted(scores, key=lambda identity: (-scores[identity], identity))
    return [
        {"compiled_object_id": identity, "score": scores[identity]}
        for identity in ordered[:limit]
    ]


def _rrf_reference(
    left: Sequence[Mapping[str, Any]],
    right: Sequence[Mapping[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    ranks_left = {
        str(row["compiled_object_id"]): rank
        for rank, row in enumerate(left, start=1)
    }
    ranks_right = {
        str(row["compiled_object_id"]): rank
        for rank, row in enumerate(right, start=1)
    }
    identities = set(ranks_left) | set(ranks_right)
    scored = [
        {
            "compiled_object_id": identity,
            "score": (
                (1.0 / (RRF_K + ranks_left[identity]) if identity in ranks_left else 0.0)
                + (1.0 / (RRF_K + ranks_right[identity]) if identity in ranks_right else 0.0)
            ),
        }
        for identity in identities
    ]
    return sorted(
        scored,
        key=lambda row: (-float(row["score"]), str(row["compiled_object_id"])),
    )[:limit]


def _rrf_equal(
    observed: Sequence[Mapping[str, Any]],
    expected: Sequence[Mapping[str, Any]],
) -> bool:
    if [row["compiled_object_id"] for row in observed] != [
        row["compiled_object_id"] for row in expected
    ]:
        return False
    return all(
        abs(float(left["score"]) - float(right["score"])) <= 1e-15
        for left, right in zip(observed, expected, strict=True)
    )


def _postgres_exact(
    connection: Any,
    *,
    schema: str,
    filters: QrelFilter,
    query: np.ndarray,
    query_kind: str,
    limit: int,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    from pgvector import HalfVector, Vector
    from psycopg import sql

    if query_kind == "float32_vector":
        query_value = Vector(np.asarray(query, dtype=np.float32))
        expression = sql.SQL("embedding::vector(1024) <#> q.value")
        query_cast = sql.SQL("%s::vector(1024)")
    elif query_kind == "native_halfvec":
        query_value = HalfVector(np.asarray(query, dtype=np.float32))
        expression = sql.SQL("embedding <#> q.value")
        query_cast = sql.SQL("%s::halfvec(1024)")
    else:
        raise QualificationError(f"postgres_query_kind_invalid:{query_kind}")
    where, parameters = _filter_clause(filters)
    schema_id = sql.Identifier(schema)
    statement = sql.SQL(
        "WITH q(value) AS (VALUES ({})) "
        "SELECT ordinal, compiled_object_id, lineage_source_record_ids, -({}) AS score "
        "FROM {}.candidate_objects CROSS JOIN q "
        f"WHERE {where} "
        "ORDER BY {}, compiled_object_id LIMIT %s"
    ).format(query_cast, expression, schema_id, expression)
    values = (query_value, *parameters, limit)
    rows = connection.execute(statement, values).fetchall()
    candidates = [
        {
            "compiled_object_id": str(row[1]),
            "score": float(row[3]),
        }
        for row in rows
    ]
    eligible_statement = sql.SQL(
        "SELECT compiled_object_id FROM {}.candidate_objects "
        f"WHERE {where} ORDER BY compiled_object_id"
    ).format(schema_id)
    eligible_ids = [
        str(row[0])
        for row in connection.execute(
            eligible_statement, tuple(parameters)
        ).fetchall()
    ]
    explain_statement = sql.SQL("EXPLAIN (FORMAT JSON) ") + statement
    raw_plan = connection.execute(explain_statement, values).fetchone()[0]
    plan_root = raw_plan[0]["Plan"] if isinstance(raw_plan, list) else raw_plan["Plan"]
    node_types: list[str] = []
    index_names: list[str] = []

    def visit(node: Mapping[str, Any]) -> None:
        node_types.append(str(node.get("Node Type") or ""))
        if node.get("Index Name"):
            index_names.append(str(node["Index Name"]))
        for child in node.get("Plans") or ():
            visit(child)

    visit(plan_root)
    if any("embedding" in value.casefold() for value in index_names):
        raise QualificationError("ann_index_used_in_exact_route")
    if any(
        "index" in value.casefold() or "bitmap" in value.casefold()
        for value in node_types
    ):
        raise QualificationError("indexed_plan_used_in_forced_exact_route")
    return candidates, eligible_ids, {
        "node_types": node_types,
        "index_names": index_names,
        "plan_digest": canonical_digest(raw_plan),
    }


def _candidate_ids(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    return [str(row["compiled_object_id"]) for row in rows]


def _candidate_digest(rows: Sequence[Mapping[str, Any]]) -> str:
    return canonical_digest(
        [
            {
                "compiled_object_id": str(row["compiled_object_id"]),
                "score": float(row["score"]),
            }
            for row in rows
        ]
    )


def _parity_receipt(
    reference: Sequence[Mapping[str, Any]],
    observed: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    reference_ids = _candidate_ids(reference)
    observed_ids = _candidate_ids(observed)
    reference_scores = {
        str(row["compiled_object_id"]): float(row["score"])
        for row in reference
    }
    observed_scores = {
        str(row["compiled_object_id"]): float(row["score"])
        for row in observed
    }
    common = set(reference_scores) & set(observed_scores)
    maximum_score_delta = max(
        (
            abs(reference_scores[identity] - observed_scores[identity])
            for identity in common
        ),
        default=float("inf"),
    )
    return {
        "ordered_ids_exact": reference_ids == observed_ids,
        "reference_ordered_id_digest": canonical_digest(reference_ids),
        "observed_ordered_id_digest": canonical_digest(observed_ids),
        "common_candidate_count": len(common),
        "maximum_common_score_absolute_delta": maximum_score_delta,
        "score_delta_within_1e_5": maximum_score_delta <= 1e-5,
    }


def _first_target_rank(
    rows: Sequence[Mapping[str, Any]],
    *,
    objects_by_id: Mapping[str, Mapping[str, Any]],
    target_ids: Sequence[str],
    limit: int = FIRST_STAGE_LIMIT,
) -> int | None:
    targets = set(target_ids)
    for rank, candidate in enumerate(rows[:limit], start=1):
        row = objects_by_id[str(candidate["compiled_object_id"])]
        lineage = {
            str(value) for value in row.get("lineage_source_record_ids") or ()
        }
        base = row.get("base_object_view")
        if isinstance(base, Mapping):
            lineage.add(str(base.get("source_record_id") or ""))
        if targets.intersection(lineage):
            return rank
    return None


def _eligible_target_count(
    eligible_ids: Sequence[str],
    *,
    objects_by_id: Mapping[str, Mapping[str, Any]],
    target_ids: Sequence[str],
) -> int:
    targets = set(target_ids)
    count = 0
    for identity in eligible_ids:
        row = objects_by_id[identity]
        lineage = {
            str(value) for value in row.get("lineage_source_record_ids") or ()
        }
        base = row.get("base_object_view")
        if isinstance(base, Mapping):
            lineage.add(str(base.get("source_record_id") or ""))
        count += bool(targets.intersection(lineage))
    return count


def _route_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    eligible = [row for row in rows if int(row["eligible_target_count"]) > 0]
    ranks = [
        int(row["target_rank_at_64"])
        for row in eligible
        if row.get("target_rank_at_64") is not None
    ]
    return {
        "qrel_count": len(rows),
        "eligible_qrel_count": len(eligible),
        "target_in_top_10": sum(rank <= 10 for rank in ranks),
        "target_in_top_16": sum(rank <= 16 for rank in ranks),
        "target_in_top_64": len(ranks),
        "mean_reciprocal_rank_at_64": (
            round(sum(1.0 / rank for rank in ranks) / len(eligible), 8)
            if eligible
            else 0.0
        ),
        "zero_eligible_target_qrel_ids": [
            str(row["qrel_id"])
            for row in rows
            if int(row["eligible_target_count"]) == 0
        ],
    }


def _route_evaluation(
    *,
    qrel_id: str,
    rows: Sequence[Mapping[str, Any]],
    eligible_ids: Sequence[str],
    objects_by_id: Mapping[str, Mapping[str, Any]],
    target_ids: Sequence[str],
) -> dict[str, Any]:
    rank = _first_target_rank(
        rows,
        objects_by_id=objects_by_id,
        target_ids=target_ids,
    )
    return {
        "qrel_id": qrel_id,
        "eligible_target_count": _eligible_target_count(
            eligible_ids,
            objects_by_id=objects_by_id,
            target_ids=target_ids,
        ),
        "target_rank_at_64": rank,
        "target_in_top_10": rank is not None and rank <= 10,
        "target_in_top_16": rank is not None and rank <= 16,
        "target_in_top_64": rank is not None,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    import psycopg
    import psutil
    from pgvector.psycopg import register_vector

    receipt_path = _qualification_path(Path(args.receipt))
    candidate_artifact_path = _qualification_path(Path(args.candidate_artifact))
    if receipt_path.parent != candidate_artifact_path.parent:
        raise QualificationError("attempt_outputs_must_share_directory")
    if receipt_path.exists() or candidate_artifact_path.exists():
        raise QualificationError("fresh_attempt_output_already_exists")
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    if args.host not in {"127.0.0.1", "::1"}:
        raise QualificationError("database_host_must_be_loopback")
    if IDENTIFIER.fullmatch(args.schema) is None:
        raise QualificationError(f"invalid_schema:{args.schema}")
    password = os.environ.get(args.password_env)
    if not password:
        raise QualificationError(f"database_password_env_missing:{args.password_env}")

    input_paths = {
        "objects": Path(args.objects).resolve(),
        "dense": Path(args.dense).resolve(),
        "dense_manifest": Path(args.dense_manifest).resolve(),
        "qrels": Path(args.qrels).resolve(),
        "runtime_policy": Path(args.runtime_policy).resolve(),
        "query_manifest": Path(args.query_manifest).resolve(),
        "query_embeddings": Path(args.query_embeddings).resolve(),
        "candidate_plane_receipt": Path(args.candidate_plane_receipt).resolve(),
    }
    for name, path in input_paths.items():
        if not path.is_file():
            raise QualificationError(f"input_file_missing:{name}:{path}")

    started = time.perf_counter()
    process = psutil.Process()
    observed_rss = [process.memory_info().rss]
    repository_root = Path(__file__).resolve().parents[2]
    tokenizer_source_path = repository_root / "src" / "retrieval" / "text.py"
    candidate_plane_script_path = (
        repository_root
        / "scripts"
        / "qualification"
        / "run_s1_pgvector_candidate_plane.py"
    )
    if sha256_file(tokenizer_source_path) != EXPECTED_TOKENIZER_SOURCE_SHA256:
        raise QualificationError("production_tokenizer_source_digest_mismatch")
    if (
        sha256_file(candidate_plane_script_path)
        != EXPECTED_CANDIDATE_PLANE_SCRIPT_SHA256
    ):
        raise QualificationError("candidate_plane_script_digest_mismatch")
    execution_start_identity = {
        "qualification_script_sha256": sha256_file(Path(__file__).resolve()),
        "candidate_plane_script_sha256": sha256_file(
            candidate_plane_script_path
        ),
        "production_tokenizer_source_sha256": sha256_file(
            tokenizer_source_path
        ),
        "repository": _git_state(repository_root),
    }
    input_start_hashes = {
        name: sha256_file(path) for name, path in input_paths.items()
    }
    objects, dense, dense_manifest, object_receipt = _load_and_validate_inputs(
        objects_path=input_paths["objects"],
        dense_path=input_paths["dense"],
        manifest_path=input_paths["dense_manifest"],
    )
    qrels_payload = _read_json(input_paths["qrels"])
    qrels = _validate_qrels_payload(
        qrels_payload,
        observed_sha256=sha256_file(input_paths["qrels"]),
    )
    specs = _ranking_specs(qrels)
    policy = _validate_runtime_policy(input_paths["runtime_policy"])
    client_runtime_versions = _validate_client_runtime_versions()
    candidate_plane_receipt = _validate_candidate_plane_receipt(
        input_paths["candidate_plane_receipt"], schema=args.schema
    )
    qrel_ids = [spec.qrel_id for spec in specs]
    queries, query_manifest, query_receipt = _validate_query_artifact(
        query_manifest_path=input_paths["query_manifest"],
        query_embeddings_path=input_paths["query_embeddings"],
        qrel_ids=qrel_ids,
    )
    qwen_policy = policy.get("qwen_embedding")
    if not (
        isinstance(qwen_policy, Mapping)
        and qwen_policy.get("model_digest") == EXPECTED_MODEL_DIGEST
        and qwen_policy.get("query_instruction")
        == query_manifest.get("model", {}).get("query_instruction")
    ):
        raise QualificationError("runtime_query_model_contract_mismatch")
    objects_by_id = {
        str(row["compiled_object_id"]): row for row in objects
    }
    observed_rss.append(process.memory_info().rss)

    connection = psycopg.connect(
        host=args.host,
        port=args.port,
        dbname=args.database,
        user=args.user,
        password=password,
        application_name="finsight_s1_dense_hybrid_qualification",
        connect_timeout=10,
        autocommit=True,
    )
    candidate_queries: list[dict[str, Any]] = []
    timing = {
        "numpy_exact": 0.0,
        "postgres_exact_float32_query": 0.0,
        "postgres_native_halfvec_query": 0.0,
        "python_rank_bm25": 0.0,
        "rrf": 0.0,
    }
    try:
        register_vector(connection)
        connection.execute("SET statement_timeout = '20min'")
        connection.execute("SET enable_indexscan = off")
        connection.execute("SET enable_indexonlyscan = off")
        connection.execute("SET enable_bitmapscan = off")
        if not connection.execute(
            "SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = %s)",
            (args.schema,),
        ).fetchone()[0]:
            raise QualificationError(f"existing_schema_missing:{args.schema}")
        database_identity_receipt = _database_receipt(
            connection, schema=args.schema
        )
        database_roundtrip_receipt = _roundtrip_and_vector_receipt(
            connection,
            schema=args.schema,
            objects=objects,
            dense=dense,
        )
        _validate_receipt(
            input_receipt=object_receipt,
            database=database_identity_receipt,
            roundtrip=database_roundtrip_receipt,
        )
        database_count = int(database_identity_receipt["object_count"])
        database_version = str(database_identity_receipt["server_version"])
        extension_version = str(
            database_identity_receipt["pgvector_extension_version"]
        )
        if database_version != EXPECTED_POSTGRES_SERVER_VERSION:
            raise QualificationError("postgres_server_version_drift")
        if extension_version != EXPECTED_PGVECTOR_EXTENSION_VERSION:
            raise QualificationError("pgvector_extension_version_drift")

        for ordinal, (spec, query) in enumerate(zip(specs, queries, strict=True)):
            eligible_indices = _eligible_indices(objects, spec.filters)
            eligible_ids = sorted(
                str(objects[index]["compiled_object_id"])
                for index in eligible_indices
            )
            route_started = time.perf_counter()
            numpy_rows = _numpy_exact(
                objects=objects,
                dense=dense,
                eligible_indices=eligible_indices,
                query=query,
                limit=FIRST_STAGE_LIMIT,
            )
            timing["numpy_exact"] += time.perf_counter() - route_started

            route_started = time.perf_counter()
            postgres_rows, postgres_eligible_ids, postgres_plan = _postgres_exact(
                connection,
                schema=args.schema,
                filters=spec.filters,
                query=query,
                query_kind="float32_vector",
                limit=FIRST_STAGE_LIMIT,
            )
            timing["postgres_exact_float32_query"] += (
                time.perf_counter() - route_started
            )

            route_started = time.perf_counter()
            halfvec_rows, halfvec_eligible_ids, halfvec_plan = _postgres_exact(
                connection,
                schema=args.schema,
                filters=spec.filters,
                query=query,
                query_kind="native_halfvec",
                limit=FIRST_STAGE_LIMIT,
            )
            timing["postgres_native_halfvec_query"] += (
                time.perf_counter() - route_started
            )

            route_started = time.perf_counter()
            bm25_rows = _bm25(
                objects=objects,
                eligible_indices=eligible_indices,
                query_text=spec.sparse_query_text,
                limit=FIRST_STAGE_LIMIT,
            )
            timing["python_rank_bm25"] += time.perf_counter() - route_started

            if eligible_ids != postgres_eligible_ids or eligible_ids != halfvec_eligible_ids:
                raise QualificationError(
                    f"eligible_identity_mismatch:{spec.qrel_id}"
                )
            eligible_set = set(eligible_ids)
            expected_first_stage_count = min(FIRST_STAGE_LIMIT, len(eligible_ids))
            for route_name, route in (
                ("numpy_exact", numpy_rows),
                ("postgres_exact", postgres_rows),
                ("postgres_native_halfvec", halfvec_rows),
                ("python_rank_bm25", bm25_rows),
            ):
                route_ids = _candidate_ids(route)
                if len(route) != expected_first_stage_count:
                    raise QualificationError(
                        f"candidate_count_mismatch:{spec.qrel_id}:{route_name}:{len(route)}:{expected_first_stage_count}"
                    )
                if len(route_ids) != len(set(route_ids)):
                    raise QualificationError(
                        f"candidate_identity_duplicate:{spec.qrel_id}:{route_name}"
                    )
                violations = set(_candidate_ids(route)) - eligible_set
                if violations:
                    raise QualificationError(
                        f"hard_filter_violation:{spec.qrel_id}:{route_name}:{sorted(violations)[:3]}"
                    )

            route_started = time.perf_counter()
            rrf_numpy = reciprocal_rank_fusion(
                (bm25_rows, numpy_rows), limit=PRODUCT_UNION_LIMIT
            )
            rrf_postgres = reciprocal_rank_fusion(
                (bm25_rows, postgres_rows), limit=PRODUCT_UNION_LIMIT
            )
            rrf_numpy_reference = _rrf_reference(
                bm25_rows, numpy_rows, limit=PRODUCT_UNION_LIMIT
            )
            rrf_postgres_reference = _rrf_reference(
                bm25_rows, postgres_rows, limit=PRODUCT_UNION_LIMIT
            )
            timing["rrf"] += time.perf_counter() - route_started
            if not _rrf_equal(rrf_numpy, rrf_numpy_reference) or not _rrf_equal(
                rrf_postgres, rrf_postgres_reference
            ):
                raise QualificationError(f"rrf_reference_mismatch:{spec.qrel_id}")
            expected_numpy_rrf_count = min(
                PRODUCT_UNION_LIMIT,
                len(set(_candidate_ids(bm25_rows)) | set(_candidate_ids(numpy_rows))),
            )
            expected_postgres_rrf_count = min(
                PRODUCT_UNION_LIMIT,
                len(
                    set(_candidate_ids(bm25_rows))
                    | set(_candidate_ids(postgres_rows))
                ),
            )
            if (
                len(rrf_numpy) != expected_numpy_rrf_count
                or len(rrf_postgres) != expected_postgres_rrf_count
                or len(_candidate_ids(rrf_numpy))
                != len(set(_candidate_ids(rrf_numpy)))
                or len(_candidate_ids(rrf_postgres))
                != len(set(_candidate_ids(rrf_postgres)))
            ):
                raise QualificationError(f"rrf_candidate_contract_invalid:{spec.qrel_id}")

            quantized_query = np.asarray(query, dtype=np.float16).astype(np.float32)
            quantization_delta = np.abs(np.asarray(query) - quantized_query)
            candidate_queries.append(
                {
                    "qrel_id": spec.qrel_id,
                    "query_ordinal": ordinal,
                    "eligible_object_count": len(eligible_ids),
                    "eligible_object_id_digest": canonical_digest(eligible_ids),
                    "raw_bm25_dense_union_count": len(
                        set(_candidate_ids(bm25_rows)) | set(_candidate_ids(numpy_rows))
                    ),
                    "query_halfvec_quantization": {
                        "float32_norm": float(np.linalg.norm(query)),
                        "halfvec_roundtrip_norm": float(np.linalg.norm(quantized_query)),
                        "maximum_absolute_delta": float(quantization_delta.max()),
                        "mean_absolute_delta": float(quantization_delta.mean()),
                    },
                    "routes": {
                        "numpy_float16_document_float32_query_exact_ip": {
                            "candidate_digest": _candidate_digest(numpy_rows),
                            "candidates": numpy_rows,
                        },
                        "postgres_halfvec_cast_vector_float32_query_exact_ip": {
                            "candidate_digest": _candidate_digest(postgres_rows),
                            "query_plan": postgres_plan,
                            "candidates": postgres_rows,
                        },
                        "postgres_native_halfvec_query_exact_ip": {
                            "candidate_digest": _candidate_digest(halfvec_rows),
                            "query_plan": halfvec_plan,
                            "candidates": halfvec_rows,
                        },
                        "python_rank_bm25_filtered_baseline": {
                            "candidate_digest": _candidate_digest(bm25_rows),
                            "candidates": bm25_rows,
                        },
                        "rrf_bm25_plus_numpy_exact_reference": {
                            "candidate_digest": _candidate_digest(rrf_numpy),
                            "candidates": rrf_numpy,
                        },
                        "rrf_bm25_plus_postgres_exact": {
                            "candidate_digest": _candidate_digest(rrf_postgres),
                            "candidates": rrf_postgres,
                        },
                    },
                    "pre_label_technical_comparison": {
                        "postgres_exact_vs_numpy": _parity_receipt(
                            numpy_rows, postgres_rows
                        ),
                        "postgres_rrf_vs_numpy_rrf": _parity_receipt(
                            rrf_numpy, rrf_postgres
                        ),
                        "native_halfvec_vs_numpy_top64_overlap": round(
                            len(
                                set(_candidate_ids(numpy_rows))
                                & set(_candidate_ids(halfvec_rows))
                            )
                            / max(1, len(numpy_rows)),
                            8,
                        ),
                    },
                }
            )
            observed_rss.append(process.memory_info().rss)
    finally:
        connection.close()

    bm25_bundle_body = [
        {
            "qrel_id": str(query["qrel_id"]),
            "ordered_ids": _candidate_ids(
                query["routes"]["python_rank_bm25_filtered_baseline"][
                    "candidates"
                ]
            ),
        }
        for query in candidate_queries
    ]
    bm25_ordered_top64_bundle_digest = canonical_digest(bm25_bundle_body)
    if (
        bm25_ordered_top64_bundle_digest
        != EXPECTED_BM25_ORDERED_TOP64_BUNDLE_DIGEST
    ):
        raise QualificationError(
            f"python_bm25_ordered_top64_bundle_drift:{bm25_ordered_top64_bundle_digest}"
        )

    label_free_artifact: dict[str, Any] = {
        "schema_version": CANDIDATE_ARTIFACT_SCHEMA_VERSION,
        "status": "label_free_candidates_frozen_before_evaluation",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "attempt_id": args.attempt_id,
        "authority": {
            "candidate_is_not_evidence": True,
            "target_ids_absent": True,
            "labels_joined_after_artifact_freeze": True,
            "development_qrels_only": True,
            "evidence_admission_authorized": False,
            "numeric_authority": False,
            "production_cutover_authorized": False,
        },
        "inputs": {
            "objects_sha256": EXPECTED_OBJECTS_SHA256,
            "document_dense_sha256": EXPECTED_DENSE_SHA256,
            "document_dense_manifest_sha256": EXPECTED_MANIFEST_SHA256,
            "qrels_sha256": EXPECTED_QRELS_SHA256,
            "qrel_manifest_digest": EXPECTED_QREL_MANIFEST_DIGEST,
            "candidate_plane_receipt": candidate_plane_receipt,
            "bm25_ordered_top64_bundle_digest": (
                bm25_ordered_top64_bundle_digest
            ),
            **query_receipt,
        },
        "ranking_contract": {
            "first_stage_limit": FIRST_STAGE_LIMIT,
            "rrf_k": RRF_K,
            "product_union_limit": PRODUCT_UNION_LIMIT,
            "maximum_raw_two_route_union": MAXIMUM_RAW_UNION,
            "score_order": "descending_score_then_compiled_object_id_ascending",
            "document_dense_dtype": "float16_cast_to_float32_for_numpy_reference",
            "query_dense_dtype": "float32_except_explicit_native_halfvec_challenger",
            "bm25_tokenizer": "src/retrieval/text.py regex contract",
            "bm25_idf_scope": "per_qrel_hard_filtered_eligible_corpus",
        },
        "implementation": execution_start_identity,
        "queries": candidate_queries,
    }
    target_strings = [target for qrel in qrels for target in _target_ids(qrel)]
    candidate_serialized = json.dumps(
        label_free_artifact,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    folded_candidate_serialized = candidate_serialized.casefold()
    if any(target.casefold() in folded_candidate_serialized for target in target_strings):
        raise QualificationError("target_id_present_in_label_free_candidate_artifact")
    label_free_artifact["result_digest"] = canonical_digest(label_free_artifact)
    _atomic_write_json(candidate_artifact_path, label_free_artifact)
    candidate_artifact_sha256 = sha256_file(candidate_artifact_path)
    frozen_artifact = _read_json(candidate_artifact_path)
    frozen_unsigned = dict(frozen_artifact)
    frozen_result_digest = str(frozen_unsigned.pop("result_digest", ""))
    if (
        frozen_result_digest != label_free_artifact["result_digest"]
        or canonical_digest(frozen_unsigned) != frozen_result_digest
        or sha256_file(candidate_artifact_path) != candidate_artifact_sha256
    ):
        raise QualificationError("label_free_candidate_artifact_replay_mismatch")
    frozen_candidate_queries = frozen_artifact.get("queries")
    if not isinstance(frozen_candidate_queries, list) or len(
        frozen_candidate_queries
    ) != len(qrels):
        raise QualificationError("label_free_candidate_query_count_mismatch")

    evaluation_by_route: dict[str, list[dict[str, Any]]] = {
        route: []
        for route in (
            "numpy_exact",
            "postgres_exact",
            "postgres_native_halfvec",
            "python_rank_bm25",
            "rrf_numpy_reference",
            "rrf_postgres_exact",
        )
    }
    per_qrel: list[dict[str, Any]] = []
    all_postgres_parity = True
    all_postgres_score_delta = True
    all_halfvec_overlap = True
    all_postgres_target_rank = True
    all_postgres_rrf_ordered_ids = True
    all_postgres_rrf_score_delta = True
    halfvec_target_loss_qrels: list[str] = []
    union_target_present_count = 0
    for qrel, candidate_query in zip(qrels, frozen_candidate_queries, strict=True):
        qrel_id = str(qrel["qrel_id"])
        target_ids = _target_ids(qrel)
        eligible_ids = sorted(
            str(objects[index]["compiled_object_id"])
            for index in _eligible_indices(objects, qrel_filter(qrel))
        )
        route_map = candidate_query["routes"]
        rows_by_route = {
            "numpy_exact": route_map[
                "numpy_float16_document_float32_query_exact_ip"
            ]["candidates"],
            "postgres_exact": route_map[
                "postgres_halfvec_cast_vector_float32_query_exact_ip"
            ]["candidates"],
            "postgres_native_halfvec": route_map[
                "postgres_native_halfvec_query_exact_ip"
            ]["candidates"],
            "python_rank_bm25": route_map[
                "python_rank_bm25_filtered_baseline"
            ]["candidates"],
            "rrf_numpy_reference": route_map[
                "rrf_bm25_plus_numpy_exact_reference"
            ]["candidates"],
            "rrf_postgres_exact": route_map[
                "rrf_bm25_plus_postgres_exact"
            ]["candidates"],
        }
        evaluated: dict[str, dict[str, Any]] = {}
        for route_name, rows in rows_by_route.items():
            result = _route_evaluation(
                qrel_id=qrel_id,
                rows=rows,
                eligible_ids=eligible_ids,
                objects_by_id=objects_by_id,
                target_ids=target_ids,
            )
            evaluation_by_route[route_name].append(result)
            evaluated[route_name] = result
        parity = candidate_query["pre_label_technical_comparison"][
            "postgres_exact_vs_numpy"
        ]
        rrf_parity = candidate_query["pre_label_technical_comparison"][
            "postgres_rrf_vs_numpy_rrf"
        ]
        all_postgres_parity &= bool(parity["ordered_ids_exact"])
        all_postgres_score_delta &= bool(parity["score_delta_within_1e_5"])
        all_postgres_rrf_ordered_ids &= bool(rrf_parity["ordered_ids_exact"])
        all_postgres_rrf_score_delta &= bool(
            rrf_parity["score_delta_within_1e_5"]
        )
        all_halfvec_overlap &= (
            float(
                candidate_query["pre_label_technical_comparison"][
                    "native_halfvec_vs_numpy_top64_overlap"
                ]
            )
            >= 0.95
        )
        numpy_rank = evaluated["numpy_exact"]["target_rank_at_64"]
        postgres_rank = evaluated["postgres_exact"]["target_rank_at_64"]
        halfvec_rank = evaluated["postgres_native_halfvec"]["target_rank_at_64"]
        all_postgres_target_rank &= numpy_rank == postgres_rank
        if numpy_rank is not None and halfvec_rank is None:
            halfvec_target_loss_qrels.append(qrel_id)
        raw_union = set(
            _candidate_ids(rows_by_route["python_rank_bm25"])
        ) | set(_candidate_ids(rows_by_route["numpy_exact"]))
        if _first_target_rank(
            [{"compiled_object_id": identity} for identity in sorted(raw_union)],
            objects_by_id=objects_by_id,
            target_ids=target_ids,
            limit=len(raw_union),
        ) is not None:
            union_target_present_count += 1
        per_qrel.append(
            {
                "qrel_id": qrel_id,
                "eligible_target_count": evaluated["numpy_exact"][
                    "eligible_target_count"
                ],
                "route_target_ranks_at_64": {
                    route: result["target_rank_at_64"]
                    for route, result in evaluated.items()
                },
                "postgres_exact_target_rank_matches_numpy": numpy_rank
                == postgres_rank,
                "native_halfvec_lost_numpy_top64_target": numpy_rank is not None
                and halfvec_rank is None,
                "bm25_numpy_dense_raw_union_target_present": (
                    _first_target_rank(
                        [
                            {"compiled_object_id": identity}
                            for identity in sorted(raw_union)
                        ],
                        objects_by_id=objects_by_id,
                        target_ids=target_ids,
                        limit=len(raw_union),
                    )
                    is not None
                ),
            }
        )

    summaries = {
        route: _route_summary(rows) for route, rows in evaluation_by_route.items()
    }
    observed_bm25_baseline = {
        key: summaries["python_rank_bm25"][key]
        for key in EXPECTED_BM25_BASELINE
    }
    if observed_bm25_baseline != EXPECTED_BM25_BASELINE:
        raise QualificationError(
            f"python_bm25_baseline_drift:{observed_bm25_baseline}:{EXPECTED_BM25_BASELINE}"
        )
    numpy_mrr = summaries["numpy_exact"]["mean_reciprocal_rank_at_64"]
    halfvec_mrr = summaries["postgres_native_halfvec"][
        "mean_reciprocal_rank_at_64"
    ]
    halfvec_mrr_ratio = halfvec_mrr / numpy_mrr if numpy_mrr else 1.0
    postgres_exact_pass = (
        all_postgres_parity
        and all_postgres_score_delta
        and all_postgres_target_rank
    )
    halfvec_pass = (
        all_halfvec_overlap
        and not halfvec_target_loss_qrels
        and halfvec_mrr_ratio >= 0.99
    )
    best_single_top64 = max(
        summaries["python_rank_bm25"]["target_in_top_64"],
        summaries["numpy_exact"]["target_in_top_64"],
    )
    best_single_mrr = max(
        summaries["python_rank_bm25"]["mean_reciprocal_rank_at_64"],
        summaries["numpy_exact"]["mean_reciprocal_rank_at_64"],
    )
    rrf_reference_summary = summaries["rrf_numpy_reference"]
    rrf_postgres_summary = summaries["rrf_postgres_exact"]
    rrf_reference_quality_threshold_met = (
        rrf_reference_summary["target_in_top_64"] >= best_single_top64
        and rrf_reference_summary["mean_reciprocal_rank_at_64"]
        >= best_single_mrr * 0.99
    )
    postgres_rrf_parity_pass = (
        all_postgres_rrf_ordered_ids and all_postgres_rrf_score_delta
    )
    rrf_postgres_quality_threshold_met = (
        rrf_postgres_summary["target_in_top_64"] >= best_single_top64
        and rrf_postgres_summary["mean_reciprocal_rank_at_64"]
        >= best_single_mrr * 0.99
    )
    rrf_quality_pass = (
        postgres_exact_pass
        and postgres_rrf_parity_pass
        and rrf_postgres_quality_threshold_met
    )
    all_targets_eligible = all(
        int(row["eligible_target_count"]) > 0 for row in per_qrel
    )
    if not all_targets_eligible:
        raise QualificationError("source_level_target_missing_after_hard_filters")

    input_end_hashes = {
        name: sha256_file(path) for name, path in input_paths.items()
    }
    execution_end_identity = {
        "qualification_script_sha256": sha256_file(Path(__file__).resolve()),
        "candidate_plane_script_sha256": sha256_file(
            candidate_plane_script_path
        ),
        "production_tokenizer_source_sha256": sha256_file(
            tokenizer_source_path
        ),
        "repository": _git_state(repository_root),
    }
    if input_end_hashes != input_start_hashes:
        raise QualificationError("input_changed_during_execution")
    relevant_identity_fields = (
        "qualification_script_sha256",
        "candidate_plane_script_sha256",
        "production_tokenizer_source_sha256",
    )
    if any(
        execution_end_identity[field] != execution_start_identity[field]
        for field in relevant_identity_fields
    ):
        raise QualificationError("implementation_changed_during_execution")
    if any(
        execution_end_identity["repository"][field]
        != execution_start_identity["repository"][field]
        for field in ("head", "branch")
    ):
        raise QualificationError("repository_head_or_branch_changed_during_execution")
    unrelated_repository_status_changed = (
        execution_end_identity["repository"]["status_digest"]
        != execution_start_identity["repository"]["status_digest"]
    )

    observed_rss.append(process.memory_info().rss)
    pgvector_exact_qualified = postgres_exact_pass
    native_halfvec_adopt_pilot = pgvector_exact_qualified and halfvec_pass
    hybrid_adopt_pilot = pgvector_exact_qualified and rrf_quality_pass
    gates = {
        "INPUT_INTEGRITY_PASS": True,
        "QUERY_ARTIFACT_PASS": True,
        "NUMPY_REFERENCE_MATERIALIZED": True,
        "POSTGRES_EXACT_PARITY_PASS": postgres_exact_pass,
        "PGVECTOR_EXACT_QUALIFIED": pgvector_exact_qualified,
        "HALFVEC_QUANTIZATION_PASS": halfvec_pass,
        "RRF_IMPLEMENTATION_PASS": True,
        "PG_RRF_PARITY_PASS": postgres_rrf_parity_pass,
        "RRF_REFERENCE_QUALITY_THRESHOLD_MET": (
            rrf_reference_quality_threshold_met
        ),
        "RRF_QUALITY_ADOPT_PILOT": rrf_quality_pass,
        "RRF_QUALITY_HOLD": not rrf_quality_pass,
        "HYBRID_ADOPT_PILOT": hybrid_adopt_pilot,
    }
    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "bounded_development_dense_hybrid_evaluated",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "attempt_id": args.attempt_id,
        "authority": {
            "candidate_is_not_evidence": True,
            "development_qrels_only": True,
            "blind_qualification": False,
            "labels_joined_after_candidate_artifact_freeze": True,
            "evidence_admission_authorized": False,
            "numeric_authority": False,
            "reranker_authorized": False,
            "production_cutover_authorized": False,
        },
        "inputs": {
            **object_receipt,
            "qrels_sha256": EXPECTED_QRELS_SHA256,
            "qrel_manifest_digest": EXPECTED_QREL_MANIFEST_DIGEST,
            "runtime_policy_sha256": EXPECTED_RUNTIME_POLICY_SHA256,
            "candidate_plane_receipt": candidate_plane_receipt,
            "bm25_ordered_top64_bundle_digest": (
                bm25_ordered_top64_bundle_digest
            ),
            **query_receipt,
            "label_free_candidate_artifact_ref": str(candidate_artifact_path),
            "label_free_candidate_artifact_sha256": candidate_artifact_sha256,
            "label_free_candidate_artifact_result_digest": label_free_artifact[
                "result_digest"
            ],
        },
        "database": {
            "schema": args.schema,
            "server_version": database_version,
            "pgvector_extension_version": extension_version,
            "object_count": database_count,
            "exact_scan_forced": True,
            "hnsw_evaluated": False,
            "identity_and_authority_receipt": database_identity_receipt,
            "full_payload_embedding_roundtrip": database_roundtrip_receipt,
        },
        "gates": gates,
        "decisions": {
            "pgvector_exact_candidate_plane": (
                "ADOPT_PILOT" if pgvector_exact_qualified else "HOLD_PARITY"
            ),
            "postgres_native_halfvec_query": (
                "ADOPT_PILOT"
                if native_halfvec_adopt_pilot
                else "HOLD_QUANTIZATION"
            ),
            "bm25_plus_pgvector_rrf_final_order": (
                "ADOPT_PILOT" if hybrid_adopt_pilot else "HOLD_QUALITY"
            ),
            "bm25_plus_pgvector_candidate_union": (
                "ADOPT_PILOT_CANDIDATE_RECALL"
                if pgvector_exact_qualified
                and union_target_present_count == len(qrels)
                else "HOLD_CANDIDATE_RECALL"
            ),
        },
        "development_evaluation": {
            "metric_scope": "source-level target rank at 64 over 18 historically exposed development qrels",
            "summaries": summaries,
            "bm25_plus_numpy_dense_raw_union_target_present": union_target_present_count,
            "postgres_exact": {
                "all_top64_ordered_ids_exact": all_postgres_parity,
                "all_common_scores_within_1e_5": all_postgres_score_delta,
                "all_source_target_ranks_exact": all_postgres_target_rank,
            },
            "native_halfvec": {
                "all_top64_overlap_at_least_0_95": all_halfvec_overlap,
                "source_target_loss_qrel_ids": halfvec_target_loss_qrels,
                "mrr_ratio_to_numpy_reference": halfvec_mrr_ratio,
            },
            "rrf_quality": {
                "best_single_top64": best_single_top64,
                "reference_rrf_top64": rrf_reference_summary[
                    "target_in_top_64"
                ],
                "postgres_rrf_top64": rrf_postgres_summary[
                    "target_in_top_64"
                ],
                "best_single_mrr_at_64": best_single_mrr,
                "reference_rrf_mrr_at_64": rrf_reference_summary[
                    "mean_reciprocal_rank_at_64"
                ],
                "postgres_rrf_mrr_at_64": rrf_postgres_summary[
                    "mean_reciprocal_rank_at_64"
                ],
                "postgres_rrf_ordered_ids_match_reference": (
                    all_postgres_rrf_ordered_ids
                ),
                "postgres_rrf_scores_match_reference": (
                    all_postgres_rrf_score_delta
                ),
                "reference_quality_threshold_met": (
                    rrf_reference_quality_threshold_met
                ),
                "postgres_quality_threshold_met": (
                    rrf_postgres_quality_threshold_met
                ),
                "adopt_pilot_threshold_met": rrf_quality_pass,
            },
            "per_qrel": per_qrel,
        },
        "runtime": {
            "numpy": np.__version__,
            "psycopg": importlib.metadata.version("psycopg"),
            "pgvector_python": importlib.metadata.version("pgvector"),
            "rank_bm25": importlib.metadata.version("rank-bm25"),
            "psutil": importlib.metadata.version("psutil"),
            "peak_observed_process_rss_bytes": max(observed_rss),
        },
        "implementation": {
            "start": execution_start_identity,
            "end": execution_end_identity,
            "relevant_implementation_unchanged": True,
            "repository_head_and_branch_unchanged": True,
            "unrelated_repository_status_changed": (
                unrelated_repository_status_changed
            ),
        },
        "timing_seconds": {
            **{key: round(value, 6) for key, value in timing.items()},
            "total": round(time.perf_counter() - started, 6),
        },
        "TokenBudgetBasis": {
            "node_purpose": "No model call in this evaluator; consume the separately frozen Qwen query-vector artifact for candidate ranking.",
            "input_scale": "18 development qrels, 34,199 candidate objects, top-64 per first-stage route.",
            "required_output": "Label-free candidate artifact followed by source-level development metrics and layered technical gates.",
            "schema_burden": "Fixed identity, filter, vector dtype, RRF and Candidate-not-Evidence contracts.",
            "materiality_and_quality_risk": "A ranking miss can hide a source candidate but cannot grant Evidence or numeric authority.",
            "comparable_run_evidence": "Frozen Python BM25 and NumPy exact routes remain in the same receipt.",
            "reasoning_profile": "Deterministic numeric retrieval evaluation; no generative reasoning.",
            "stop_and_truncation": "Fail on any input, identity, filter, target-availability or label-free artifact violation; do not truncate beyond pre-registered pools.",
        },
        "known_boundaries": [
            "These qrels are development labels with historical exposure, not a blind holdout.",
            "The v1_9 query instruction differs from the older compiled-object comparison instruction, so old Qwen shadow counts are not input-parity baselines.",
            "Only source-level positive targets are available; precision and nDCG are not claimed.",
            "PostgreSQL native full-text search previously failed to match the rank_bm25 baseline and is not used as BM25 parity here.",
            "HNSW, reranking, Evidence admission, S2, reports, products and releases are outside this attempt.",
        ],
    }
    receipt["result_digest"] = canonical_digest(receipt)
    _atomic_write_json(receipt_path, receipt)
    return receipt


def _write_failure_receipt(args: argparse.Namespace, exc: Exception) -> None:
    try:
        path = _qualification_path(Path(args.receipt))
        if path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        message = str(exc)
        secret = os.environ.get(getattr(args, "password_env", "PGPASSWORD"), "")
        if secret:
            message = message.replace(secret, "[REDACTED]")
        receipt: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "status": "failed_immutable_attempt",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "attempt_id": str(getattr(args, "attempt_id", "unknown")),
            "error_type": type(exc).__name__,
            "error": message,
            "failed_attempt_must_not_be_promoted": True,
            "production_cutover_authorized": False,
        }
        receipt["result_digest"] = canonical_digest(receipt)
        _atomic_write_json(path, receipt)
    except Exception:
        return


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--candidate-artifact", required=True)
    parser.add_argument("--objects", required=True)
    parser.add_argument("--dense", required=True)
    parser.add_argument("--dense-manifest", required=True)
    parser.add_argument("--qrels", required=True)
    parser.add_argument("--runtime-policy", required=True)
    parser.add_argument("--query-manifest", required=True)
    parser.add_argument("--query-embeddings", required=True)
    parser.add_argument("--candidate-plane-receipt", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=55434)
    parser.add_argument("--database", default="finsight_s1")
    parser.add_argument("--user", default="finsight")
    parser.add_argument("--password-env", default="PGPASSWORD")
    parser.add_argument("--schema", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        receipt = run(args)
    except Exception as exc:
        _write_failure_receipt(args, exc)
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 1
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "attempt_id": receipt["attempt_id"],
                "gates": receipt["gates"],
                "decisions": receipt["decisions"],
                "summaries": receipt["development_evaluation"]["summaries"],
                "result_digest": receipt["result_digest"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
