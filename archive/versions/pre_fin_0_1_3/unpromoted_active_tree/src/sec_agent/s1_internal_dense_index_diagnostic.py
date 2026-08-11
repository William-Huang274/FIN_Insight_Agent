from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any, Callable, Mapping, Sequence

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s1_internal_bge_fusion_evaluation import (
    VECTOR_KIND_SUFFIXES,
    validate_internal_bge_fusion_evaluation_result,
)


SCHEMA = "fin_ia_0_1_3_s1_internal_dense_index_diagnostic_v1_0"


class S1InternalDenseIndexDiagnosticError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S1InternalDenseIndexDiagnosticError(code)


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "dense_index_diagnostic_json_object_required")
    return value


def _base_alias(value: str) -> str:
    if "::" not in value:
        return value
    prefix, suffix = value.rsplit("::", 1)
    return prefix if suffix in VECTOR_KIND_SUFFIXES else value


def _selected_aliases(row: Mapping[str, Any]) -> tuple[str, ...]:
    selected = dict(row.get("selected_candidate") or {})
    aliases = {
        str(selected.get(key) or "").strip()
        for key in ("source_evidence_id", "source_key", "evidence_id", "vector_id")
    }
    return tuple(sorted({_base_alias(item) for item in aliases if item}))


def classify_dense_target(*, present_in_index: bool, selected_rank: int | None) -> str:
    if not present_in_index:
        return "dense_index_freshness_gap"
    if selected_rank is None:
        return "semantic_retrieval_top24_gap"
    if selected_rank > 10:
        return "semantic_retrieval_top10_gap"
    return "retrieved_top10"


def _collision_count(result: Mapping[str, Any]) -> int:
    rankings = (result.get("candidate_generation") or {}).get("rankings") or {}
    total = 0
    for approach in ("dense_rankings", "fusion_rankings"):
        for candidates in (rankings.get(approach) or {}).values():
            for candidate in candidates:
                key = str(candidate.get("candidate_key") or "")
                if not key or "::" in key:
                    continue
                bases = {
                    _base_alias(str(alias))
                    for alias in candidate.get("aliases") or []
                    if "::" in str(alias)
                }
                if len(
                    [alias for alias in bases if alias.startswith(f"{key}::")]
                ) >= 2:
                    total += 1
    return total


def _default_client_factory(*, dependency_dir: str, uri: str) -> Any:
    if dependency_dir not in sys.path:
        sys.path.insert(0, dependency_dir)
    from pymilvus import MilvusClient

    return MilvusClient(uri=uri)


def build_dense_index_diagnostic(
    *,
    repo_root: str | Path,
    r2_result_path: str | Path,
    qrels_path: str | Path,
    r2_policy_path: str | Path,
    client_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    result = validate_internal_bge_fusion_evaluation_result(
        _read(Path(r2_result_path))
    )
    _require(
        str(result.get("attempt_id") or "").endswith("v2_r2")
        and result.get("execution_kind") == "local_real_embedding",
        "dense_index_diagnostic_r2_result_invalid",
    )
    qrels = _read(Path(qrels_path))
    policy = _read(Path(r2_policy_path))
    _require(
        qrels.get("review_digest") == result.get("research_qrels_review_digest")
        and policy.get("attempt_id") == result.get("attempt_id"),
        "dense_index_diagnostic_input_binding_invalid",
    )
    runtime_ref = str(policy["immutable_inputs"]["milvus_runtime_ref"])
    runtime = _read(root / runtime_ref)
    resources = dict(policy["resource_bindings"])
    client = (client_factory or _default_client_factory)(
        dependency_dir=str(resources["milvus_dependencies_dir"]),
        uri=str(runtime["db_path"]),
    )
    collection = str(runtime["collection_name"])
    dense_rows = {
        str(row["bundle_id"]): dict(row)
        for row in result["evaluation"]["dense_bilingual_rrf"][
            "selected_target_ranks"
        ]
    }
    presence_cache: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    rows: list[dict[str, Any]] = []
    client.load_collection(collection_name=collection)
    try:
        for qrel in qrels.get("qrels") or []:
            bundle_id = str(qrel["bundle_id"])
            aliases = _selected_aliases(qrel)
            _require(bool(aliases), "dense_index_diagnostic_selected_alias_missing")
            if aliases not in presence_cache:
                encoded = ", ".join(
                    json.dumps(alias, ensure_ascii=False) for alias in aliases
                )
                presence_cache[aliases] = [
                    dict(item)
                    for item in client.query(
                        collection_name=collection,
                        filter=f"evidence_id in [{encoded}]",
                        output_fields=[
                            "vector_id",
                            "evidence_id",
                            "ticker",
                            "fiscal_year",
                            "form_type",
                            "vector_kind",
                        ],
                        limit=64,
                    )
                ]
            hits = presence_cache[aliases]
            dense = dense_rows[bundle_id]
            selected_rank = dense.get("selected_target_rank")
            rows.append(
                {
                    "bundle_id": bundle_id,
                    "case_key": str(qrel["case_key"]),
                    "evidence_slot_id": str(qrel["evidence_slot_id"]),
                    "evidence_owner_ticker": str(qrel["evidence_owner_ticker"]),
                    "selected_aliases": list(aliases),
                    "selected_retrieval_asset_id": str(
                        (qrel.get("selected_candidate") or {}).get(
                            "retrieval_asset_id"
                        )
                        or ""
                    ),
                    "present_in_milvus": bool(hits),
                    "matching_vector_count_capped_64": len(hits),
                    "dense_selected_target_rank": selected_rank,
                    "classification": classify_dense_target(
                        present_in_index=bool(hits),
                        selected_rank=(int(selected_rank) if selected_rank else None),
                    ),
                }
            )
    finally:
        client.release_collection(collection_name=collection)
    counts = Counter(row["classification"] for row in rows)
    unique_presence = {
        aliases: bool(hits) for aliases, hits in presence_cache.items()
    }
    body = {
        "schema_version": SCHEMA,
        "contract_ref": "fin_0_1_3.S1.internal_dense_index_diagnostic:v1",
        "recorded_at": "2026-08-09",
        "status": "terminal_succeeded_read_only_dense_index_diagnostic",
        "source_attempt": {
            "attempt_id": str(result["attempt_id"]),
            "result_digest": str(result["result_digest"]),
        },
        "identity_collision_regression": {
            "collision_count": _collision_count(result),
            "status": "pass" if _collision_count(result) == 0 else "failed",
        },
        "row_weighted_classification_counts": dict(sorted(counts.items())),
        "unique_selected_target_count": len(presence_cache),
        "unique_selected_targets_present_in_milvus": sum(unique_presence.values()),
        "unique_selected_targets_absent_from_milvus": sum(
            not value for value in unique_presence.values()
        ),
        "rows": rows,
        "observed_calls": {
            "network": 0,
            "provider": 0,
            "llm_model": 0,
            "embedding": 0,
            "milvus_metadata_queries": len(presence_cache),
            "milvus_vector_searches": 0,
            "rerank": 0,
            "evidence_promotion": 0,
        },
        "disposition": {
            "fusion_adopted": False,
            "production_candidate_baseline": "sparse_rrf",
            "dense_index_refresh_required": counts["dense_index_freshness_gap"] > 0,
            "semantic_query_or_ranking_gap_present": (
                counts["semantic_retrieval_top24_gap"] > 0
                or counts["semantic_retrieval_top10_gap"] > 0
            ),
            "reranker_evaluation_possible": False,
            "reranker_reason": "optional_local_resource_absent",
        },
        "preserved_boundaries": dict(result["preserved_boundaries"]),
        "known_boundary": (
            "This diagnostic separates index absence from top-24 semantic retrieval "
            "misses. It does not refresh Milvus, tune queries or fusion weights, "
            "download a reranker, promote Evidence, or change product acceptance."
        ),
    }
    _require(
        body["identity_collision_regression"]["status"] == "pass",
        "dense_index_diagnostic_identity_regression_failed",
    )
    return {**body, "diagnostic_digest": canonical_digest(body)}


def validate_dense_index_diagnostic(value: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(value)
    supplied = str(body.pop("diagnostic_digest", ""))
    _require(
        value.get("schema_version") == SCHEMA
        and value.get("status")
        == "terminal_succeeded_read_only_dense_index_diagnostic"
        and supplied == canonical_digest(body)
        and len(value.get("rows") or []) == 18
        and (value.get("identity_collision_regression") or {}).get("status")
        == "pass"
        and not any(
            int((value.get("observed_calls") or {}).get(key, -1))
            for key in (
                "network",
                "provider",
                "llm_model",
                "embedding",
                "milvus_vector_searches",
                "rerank",
                "evidence_promotion",
            )
        ),
        "dense_index_diagnostic_boundary_invalid",
    )
    return dict(value)


__all__ = [
    "SCHEMA",
    "S1InternalDenseIndexDiagnosticError",
    "build_dense_index_diagnostic",
    "classify_dense_target",
    "validate_dense_index_diagnostic",
]
