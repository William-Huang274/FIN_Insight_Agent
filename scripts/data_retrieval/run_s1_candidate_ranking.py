from __future__ import annotations

import argparse
import gc
import hashlib
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from typing import Any, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.candidate_ranking import (  # noqa: E402
    NeedRouteRanking,
    aggregate_all_need_pair_scores,
    evaluate_ranking,
    fuse_need_rankings,
    fuse_need_rankings_with_route_floors,
    rank_authority_indices,
    rank_need_dense_routes,
    rank_need_intent_alias_routes,
    rank_need_lexical_routes,
    rank_need_metric_row_routes,
    rank_need_sparse_routes,
    ranking_candidate_order_stable,
    rank_scores,
    role_guarded_primary_ranking,
    route_membership,
)
from retrieval.bounded_context import expand_bounded_candidate_context  # noqa: E402
from retrieval.contracts import load_financial_research_kernel  # noqa: E402
from retrieval.cross_encoder import (  # noqa: E402
    cross_encoder_model_identity,
    load_local_cross_encoder,
    load_local_qwen3_reranker,
    score_cross_encoder_pairs,
    score_qwen3_reranker_pairs,
)
from retrieval.embedding_runtime import (  # noqa: E402
    load_bge_m3_runtime,
    load_or_build_bge_m3_cache,
    load_or_build_qwen_embedding_cache,
    local_model_identity,
    sha256_file,
    sparse_weight_matrix,
)
from retrieval.evidence_role import evaluate_evidence_role  # noqa: E402
from retrieval.financial_evidence_shortlist import (  # noqa: E402
    rank_financial_evidence_shortlist,
)
from retrieval.object_retrieval_comparison import (  # noqa: E402
    CandidateScore,
    bm25_rank,
    load_compiled_objects,
)
from retrieval.query_atom_shadow import (  # noqa: E402
    apply_query_atom_label_adjudications,
    compile_atom_lane,
    eligible_atom_indices,
    label_eligibility_rows,
    load_query_atoms,
)
from retrieval.query_plan import canonical_digest  # noqa: E402
from retrieval.retrieval_need import compile_retrieval_needs  # noqa: E402
from retrieval.route_compiler import (  # noqa: E402
    load_query_object_fact_route_policy,
)
from retrieval.text import tokenize  # noqa: E402


POLICY_SCHEMA_VERSION = "fin_ia_s1_vs3_candidate_ranking_policy_v1_0"
POLICY_SUCCESSOR_SCHEMA_VERSION = "fin_ia_s1_vs3_candidate_ranking_policy_v1_1"
POLICY_SCHEMA_VERSIONS = frozenset(
    {POLICY_SCHEMA_VERSION, POLICY_SUCCESSOR_SCHEMA_VERSION}
)
RESULT_SCHEMA_VERSION = "fin_ia_s1_vs3_candidate_ranking_result_v1_0"
SUMMARY_SCHEMA_VERSION = "fin_ia_s1_vs3_candidate_ranking_summary_v1_0"
TYPED_ROUTE_PROOF_SCHEMA_VERSION = "fin_ia_s1_vs3_typed_route_proof_v1_0"


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path.name}")
    return value


def _load_policy(
    path: Path, *, _lineage: tuple[Path, ...] = ()
) -> dict[str, Any]:
    resolved = path.resolve()
    if resolved in _lineage:
        raise ValueError("candidate_ranking_policy_lineage_cycle")
    raw = _read_json(path)
    schema = raw.get("schema_version")
    if schema == POLICY_SCHEMA_VERSION:
        return raw
    if schema != POLICY_SUCCESSOR_SCHEMA_VERSION:
        raise ValueError("candidate_ranking_policy_schema_invalid")
    parent_path = _resolve(str(raw.get("parent_policy_ref") or ""))
    if _sha256_lf(parent_path) != str(raw.get("parent_policy_sha256_lf") or ""):
        raise ValueError("candidate_ranking_parent_policy_drift")
    parent = _load_policy(
        parent_path, _lineage=(*_lineage, resolved)
    )
    if parent.get("schema_version") not in POLICY_SCHEMA_VERSIONS:
        raise ValueError("candidate_ranking_parent_policy_schema_invalid")
    merged = dict(parent)
    merged.update(
        {
            "schema_version": schema,
            "status": raw["status"],
            "recorded_at": raw["recorded_at"],
            "experiment_id": raw["experiment_id"],
            "policy_lineage": {
                "parent_policy_ref": _relative(parent_path),
                "parent_policy_sha256_lf": raw["parent_policy_sha256_lf"],
                "inherited_policy_lineage": parent.get("policy_lineage"),
                "successor_basis": raw.get("successor_basis") or {},
            },
        }
    )
    for target, override in (
        ("bound_inputs", "bound_input_overrides"),
        ("candidate_contract", "candidate_contract_overrides"),
        ("decision_gates", "decision_gate_overrides"),
        ("token_budget_basis", "token_budget_basis_overrides"),
        ("authority", "authority_overrides"),
    ):
        values = dict(parent.get(target) or {})
        values.update(raw.get(override) or {})
        merged[target] = values
    return merged


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


def _sha256_lf(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _empty_cuda() -> None:
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def _required_cuda_execution_receipt() -> dict[str, Any]:
    """Bind learned retrieval execution to a real CUDA device.

    The S1 contract does not permit an implicit CPU fallback for embedding or
    Cross-Encoder work.  Capture the concrete device before loading any model
    so a completed result proves which accelerator executed the learned lanes.
    """

    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("candidate_ranking_cuda_runtime_missing") from exc
    if not torch.cuda.is_available():
        raise RuntimeError("candidate_ranking_cuda_required")
    device_index = int(torch.cuda.current_device())
    properties = torch.cuda.get_device_properties(device_index)
    return {
        "execution_device": f"cuda:{device_index}",
        "device_name": str(properties.name),
        "compute_capability": [int(properties.major), int(properties.minor)],
        "total_memory_bytes": int(properties.total_memory),
        "torch_version": str(torch.__version__),
        "cuda_runtime_version": str(torch.version.cuda or ""),
        "embedding_precision": "fp16",
        "reranker_precision": "fp16",
        "cpu_fallback_allowed": False,
        "failure_policy": "fail_closed_before_model_load",
    }


def _score_cache_key(
    *,
    scorer_id: str,
    model_digest: str,
    pair_manifest_digest: str,
    maximum_sequence_length: int,
    instruction: str = "",
) -> str:
    return canonical_digest(
        {
            "schema_version": "fin_ia_local_reranker_score_cache_key_v1_0",
            "scorer_id": scorer_id,
            "model_digest": model_digest,
            "pair_manifest_digest": pair_manifest_digest,
            "maximum_sequence_length": maximum_sequence_length,
            "instruction": instruction,
        }
    )


def _load_score_matrix_cache(
    path: Path, *, cache_key: str, pair_counts: Sequence[int]
) -> list[list[float]] | None:
    if not path.is_file():
        return None
    raw = _read_json(path)
    if (
        raw.get("schema_version") != "fin_ia_local_reranker_score_cache_v1_0"
        or raw.get("cache_key") != cache_key
        or raw.get("pair_counts") != list(pair_counts)
    ):
        return None
    matrix = raw.get("scores")
    if not isinstance(matrix, list) or len(matrix) != len(pair_counts):
        return None
    output: list[list[float]] = []
    for values, count in zip(matrix, pair_counts):
        if not isinstance(values, list) or len(values) != count:
            return None
        converted = [float(value) for value in values]
        if not all(np.isfinite(value) for value in converted):
            return None
        output.append(converted)
    return output


def _write_score_matrix_cache(
    path: Path,
    *,
    cache_key: str,
    pair_manifest_digest: str,
    scores: Sequence[Sequence[float]],
) -> None:
    _write_json(
        path,
        {
            "schema_version": "fin_ia_local_reranker_score_cache_v1_0",
            "cache_key": cache_key,
            "pair_manifest_digest": pair_manifest_digest,
            "pair_counts": [len(values) for values in scores],
            "scores": [[float(value) for value in values] for values in scores],
        },
    )


def _validate_bindings(policy: Mapping[str, Any]) -> dict[str, Path]:
    if policy.get("schema_version") not in POLICY_SCHEMA_VERSIONS:
        raise ValueError("candidate_ranking_policy_schema_invalid")
    bindings = policy.get("bound_inputs") or {}
    text_bindings = {
        "query_atom_eval": "query_atom_eval",
        "kernel": "kernel",
        "route_policy": "route_policy",
        "retrieval_need_policy": "retrieval_need_policy",
        "vs1_result": "vs1_result",
        "reviewed_claim_anchor_catalog": "reviewed_claim_anchor_catalog",
        "vs2_result": "vs2_result",
        "vs2_evaluator": "vs2_evaluator",
    }
    paths: dict[str, Path] = {}
    for key, prefix in text_bindings.items():
        path = _resolve(str(bindings[f"{prefix}_ref"]))
        if _sha256_lf(path) != str(bindings[f"{prefix}_sha256_lf"]):
            raise ValueError(f"candidate_ranking_binding_drift:{key}")
        paths[key] = path
    if bindings.get("financial_intent_ontology_ref"):
        intent_path = _resolve(str(bindings["financial_intent_ontology_ref"]))
        if _sha256_lf(intent_path) != str(
            bindings.get("financial_intent_ontology_sha256_lf") or ""
        ):
            raise ValueError(
                "candidate_ranking_binding_drift:financial_intent_ontology"
            )
        paths["financial_intent_ontology"] = intent_path
    if bindings.get("qrel_adjudication_ref"):
        adjudication_path = _resolve(str(bindings["qrel_adjudication_ref"]))
        if _sha256_lf(adjudication_path) != str(
            bindings.get("qrel_adjudication_sha256_lf") or ""
        ):
            raise ValueError("candidate_ranking_binding_drift:qrel_adjudication")
        paths["qrel_adjudication"] = adjudication_path
    object_path = _resolve(str(bindings["compiled_objects_ref"]))
    if sha256_file(object_path) != str(bindings["compiled_objects_sha256"]):
        raise ValueError("candidate_ranking_binding_drift:compiled_objects")
    paths["compiled_objects"] = object_path
    return paths


def _load_bound_query_atoms(paths: Mapping[str, Path]) -> tuple[Any, ...]:
    atoms = load_query_atoms(_read_json(paths["query_atom_eval"]))
    adjudication_path = paths.get("qrel_adjudication")
    if adjudication_path is None:
        return atoms
    adjudication = _read_json(adjudication_path)
    if (
        str(adjudication.get("parent_query_atom_eval_ref") or "")
        != _relative(paths["query_atom_eval"])
        or str(adjudication.get("parent_query_atom_eval_sha256_lf") or "")
        != _sha256_lf(paths["query_atom_eval"])
    ):
        raise ValueError("candidate_ranking_qrel_adjudication_parent_drift")
    return apply_query_atom_label_adjudications(atoms, adjudication)


def _model_identities(policy: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Path]]:
    models = policy["models"]
    paths = {
        key: _resolve(models[key]["local_directory"])
        for key in ("bge_embedding", "qwen_embedding", "bge_reranker", "qwen_reranker")
    }
    identities = {
        "bge_embedding": local_model_identity(paths["bge_embedding"], "BAAI/bge-m3"),
        "qwen_embedding": local_model_identity(
            paths["qwen_embedding"], "Qwen/Qwen3-Embedding-0.6B"
        ),
        "bge_reranker": cross_encoder_model_identity(paths["bge_reranker"]),
        "qwen_reranker": cross_encoder_model_identity(
            paths["qwen_reranker"], model_id="Qwen/Qwen3-Reranker-0.6B"
        ),
    }
    bindings = policy["bound_inputs"]
    for key, identity in identities.items():
        if identity["model_digest"] != bindings[f"{key}_model_digest"]:
            raise ValueError(f"candidate_ranking_model_drift:{key}")
    return identities, paths


def _need_slices(counts: Sequence[int]) -> list[slice]:
    output: list[slice] = []
    offset = 0
    for count in counts:
        output.append(slice(offset, offset + count))
        offset += count
    return output


def _route_summary(
    rows: Sequence[CandidateScore], atom: Any, *, top_k: int
) -> dict[str, Any]:
    return evaluate_ranking(
        rows,
        positive_ids=atom.positive_object_ids,
        hard_negative_ids=atom.hard_negative_object_ids,
        top_k=top_k,
    )


def _multi_vector_rankings(
    *,
    runtime: Any,
    query_vectors: Sequence[np.ndarray],
    needs: Sequence[Any],
    candidate_ids: Sequence[str],
    objects_by_id: Mapping[str, Mapping[str, Any]],
    maximum_sequence_length: int,
    batch_size: int,
) -> tuple[tuple[NeedRouteRanking, ...], dict[str, str]]:
    if not candidate_ids:
        return (), {}
    encoded = runtime.encode(
        [str(objects_by_id[value]["model_text"]) for value in candidate_ids],
        batch_size=batch_size,
        max_length=maximum_sequence_length,
        return_dense=False,
        return_sparse=False,
        return_colbert_vecs=True,
    )
    document_vectors = encoded["colbert_vecs"]
    rankings: list[NeedRouteRanking] = []
    best_need: dict[str, tuple[float, str]] = {}
    for need, query_vector in zip(needs, query_vectors):
        rows = []
        for object_id, document_vector in zip(candidate_ids, document_vectors):
            score = float(runtime.colbert_score(query_vector, document_vector).item())
            rows.append(CandidateScore(object_id, score))
            if object_id not in best_need or score > best_need[object_id][0]:
                best_need[object_id] = (score, need.need_id)
        rows.sort(key=lambda value: (-value.score, value.compiled_object_id))
        rankings.append(
            NeedRouteRanking(
                route_id="bge_m3_multi_vector",
                need_id=need.need_id,
                rows=tuple(rows),
            )
        )
    return tuple(rankings), {key: value[1] for key, value in best_need.items()}


def _role_rows(
    *, atom: Any, lane: Any, candidate_ids: Sequence[str], objects_by_id: Mapping[str, Any]
) -> list[dict[str, Any]]:
    rows = []
    positives = set(atom.positive_object_ids)
    negatives = set(atom.hard_negative_object_ids)
    for object_id in candidate_ids:
        row = objects_by_id[object_id]
        base = row["base_object_view"]
        evaluation = evaluate_evidence_role(
            {
                "ticker": base.get("ticker"),
                "section": base.get("section"),
                "subsection": base.get("subsection"),
                "source_type": base.get("source_type"),
                "object_kind": row.get("object_kind"),
                "document_text": row.get("model_text"),
                "structured_projection": row.get("structured_projection"),
            },
            slot_id=lane.slot_id,
            facet_id=lane.facet_id,
            subject_ticker=lane.subject_ticker,
            evidence_owner_ticker=lane.evidence_owner_tickers[0],
            relationship_direction=lane.relationship_constraints[0],
        ).as_dict()
        judgement = (
            "positive"
            if object_id in positives
            else "hard_negative"
            if object_id in negatives
            else "unjudged"
        )
        rows.append(
            {
                "compiled_object_id": object_id,
                "judgement": judgement,
                "expected_roles": list(
                    atom.expected_roles_by_object_id.get(object_id, ())
                ),
                "evaluation": evaluation,
            }
        )
    return rows


def _role_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    positives = [row for row in rows if row["judgement"] == "positive"]
    negatives = [row for row in rows if row["judgement"] == "hard_negative"]
    positive_compatible = sum(
        row["evaluation"]["compatibility"] == "compatible" for row in positives
    )
    negative_suppressed = sum(
        row["evaluation"]["compatibility"] != "compatible" for row in negatives
    )
    return {
        "positive_count": len(positives),
        "hard_negative_count": len(negatives),
        "positive_compatible_rate": (
            round(positive_compatible / len(positives), 6) if positives else None
        ),
        "hard_negative_suppressed_or_abstained_rate": (
            round(negative_suppressed / len(negatives), 6) if negatives else None
        ),
    }


def _role_guarded_ranking(
    *,
    candidate_ids: Sequence[str],
    bge_rows: Sequence[CandidateScore],
    qwen_rows: Sequence[CandidateScore],
    role_rows: Sequence[Mapping[str, Any]],
) -> tuple[CandidateScore, ...]:
    compatibility = {
        row["compiled_object_id"]: row["evaluation"]["compatibility"]
        for row in role_rows
    }
    return role_guarded_primary_ranking(
        candidate_ids=candidate_ids,
        primary_rows=qwen_rows,
        shadow_rows=bge_rows,
        compatibility_by_id=compatibility,
    )


def _earliest_failure(
    *, atom: Any, label_audit: Sequence[Mapping[str, Any]], combined: Mapping[str, Any],
    rerankers: Mapping[str, Mapping[str, Any]], final_shortlist: Mapping[str, Any]
) -> str:
    if not atom.positive_object_ids:
        return "pre_registered_typed_gap_no_public_positive"
    eligible_positive = any(
        row["judgement"] == "positive" and row["eligible"] is True
        for row in label_audit
    )
    if not eligible_positive:
        return "object_or_hard_filter_boundary"
    if not combined["positive_target_in_ranking"]:
        return "first_stage_recall"
    if not any(row["positive_target_in_top_k"] for row in rerankers.values()):
        return "reranker_head"
    if not final_shortlist["positive_target_in_top_k"]:
        return "financial_shortlist_head"
    return "development_query_passed"


def _aggregate_routes(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, Any]:
    route_ids = sorted({route for row in rows for route in row[key]})
    output: dict[str, Any] = {}
    for route_id in route_ids:
        values = [row[key][route_id] for row in rows]
        positive = [row for row in values if row["positive_target_available"]]
        pair_total = sum(row["pairwise_comparisons"] for row in values)
        pair_wins = sum(row["pairwise_wins"] for row in values)
        output[route_id] = {
            "positive_atom_count": len(positive),
            "positive_target_in_ranking_count": sum(
                row["positive_target_in_ranking"] for row in positive
            ),
            "positive_target_in_top_k_count": sum(
                row["positive_target_in_top_k"] for row in positive
            ),
            "mean_reciprocal_rank": round(
                sum(row["reciprocal_rank"] for row in positive) / len(positive), 6
            ) if positive else 0.0,
            "hard_negative_in_ranking_count": sum(
                row["hard_negative_in_ranking_count"] for row in values
            ),
            "pairwise_accuracy": round(pair_wins / pair_total, 6) if pair_total else None,
        }
    return output


def _vs1_reviewed_successors(
    *, catalog: Mapping[str, Any], objects: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    targets = [
        row for row in catalog.get("entries") or ()
        if row.get("case_key") == "DELL"
        and row.get("evidence_item_digest")
        in {
            "b8880e2b4c9fe482e2721a00b636ed8cf689f9b0a3ba67a661085a1eacfd11e1",
            "af11bf4358e167dbf7f1105d981a56a6b568dc92362b2753e2278aaa901294b1",
        }
    ]
    mappings = []
    for target in targets:
        source = str(target["source_record_id"])
        text = " ".join(str(target["anchor_text"]).replace("mid- single", "mid-single").split())
        matches = []
        for row in objects:
            base = row["base_object_view"]
            if str(base["source_record_id"]) != source:
                continue
            candidate = " ".join(str(row["model_text"]).split())
            if text.casefold() in candidate.casefold() or candidate.casefold() in text.casefold():
                matches.append(str(row["compiled_object_id"]))
        mappings.append(
            {
                "evidence_item_digest": target["evidence_item_digest"],
                "source_record_id": source,
                "compiled_object_ids": sorted(set(matches)),
                "unique_successor": len(set(matches)) == 1,
            }
        )
    return {
        "reviewed_target_count": len(targets),
        "unique_successor_count": sum(row["unique_successor"] for row in mappings),
        "mappings": mappings,
    }


def _adapt_vs2_financial_objects(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Adapt typed retrieval children without granting Evidence authority."""

    output: list[dict[str, Any]] = []
    identities: set[str] = set()
    for raw in rows:
        metadata = raw.get("metadata") or {}
        identity = str(raw.get("evidence_id") or "")
        text = str(raw.get("text") or "").strip()
        if not (
            identity
            and identity not in identities
            and text
            and metadata.get("candidate_is_not_evidence") is True
            and metadata.get("numeric_fact_authority") is False
        ):
            raise ValueError("vs2_replay_object_contract_invalid")
        identities.add(identity)
        evidence_type = str(raw.get("evidence_type") or "")
        object_kind = (
            "metric_row"
            if evidence_type == "financial_table_metric_row"
            else "claim"
        )
        metric_label = ""
        if object_kind == "metric_row" and "Selected metric row:" in text:
            selected = text.rsplit("Selected metric row:", 1)[-1].strip()
            metric_label = selected.split("|", 1)[0].strip()
        output.append(
            {
                "schema_version": "fin_ia_s1_vs3_development_replay_object_v1_0",
                "compiled_object_id": identity,
                "object_kind": object_kind,
                "model_text": text,
                "base_object_view": {
                    "object_key": identity,
                    "source_record_id": identity,
                    "parent_document_id": str(metadata.get("parent_document_id") or ""),
                    "ticker": str(raw.get("ticker") or ""),
                    "company": str(raw.get("company") or ""),
                    "source_type": str(raw.get("source_type") or ""),
                    "source_tier": str(raw.get("source_tier") or ""),
                    "publication_date": str(raw.get("publication_date") or ""),
                    "period_end": str(raw.get("period_end") or ""),
                    "fiscal_year": raw.get("fiscal_year"),
                    "section": str(raw.get("section") or ""),
                    "subsection": str(raw.get("subsection") or ""),
                    "surface_text": text,
                    "candidate_not_evidence": True,
                },
                "structured_projection": {"metric_row_label": metric_label},
                "context_links": {
                    key: metadata[key]
                    for key in (
                        "parent_document_id",
                        "parent_page_object_id",
                        "parent_table_object_id",
                        "linked_table_object_ids",
                        "left_object_id",
                        "right_object_id",
                    )
                    if metadata.get(key)
                },
                "candidate_not_evidence": True,
                "numeric_authority": False,
                "evidence_promoted": False,
                "source_evidence_type": evidence_type,
            }
        )
    return output


def _namespace_lane(raw: Mapping[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        lane_id=str(raw["lane_id"]),
        slot_id=str(raw["slot_id"]),
        facet_id=str(raw["facet_id"]),
        business_question_zh=str(raw["business_question_zh"]),
        subject_ticker=str(raw["subject_ticker"]),
        evidence_owner_tickers=tuple(raw["evidence_owner_tickers"]),
        relationship_constraints=tuple(raw["relationship_constraints"]),
        publication_date_lte=str(raw["publication_date_lte"]),
        source_types=tuple(raw["source_types"]),
        required_source_roles=tuple(raw["required_source_roles"]),
        exact_queries=tuple(raw["exact_queries"]),
        lexical_query=str(raw["lexical_query"]),
        semantic_query=str(raw["semantic_query"]),
        forbidden_expansions=tuple(raw["forbidden_expansions"]),
    )


def _namespace_request(raw: Mapping[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        request_id=str(raw["request_id"]),
        requested_facet_ids=tuple(raw["requested_facet_ids"]),
        metric_intents=tuple(raw["metric_intents"]),
        product_intents=tuple(raw["product_intents"]),
        acceptable_proxy=bool(raw.get("acceptable_proxy")),
    )


def _resolve_vs2_targets(
    objects: Sequence[Mapping[str, Any]], reference: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Join evaluator-only targets after all natural candidates are scored."""

    output: list[dict[str, Any]] = []
    for selector in reference.get("reviewed_target_selectors") or ():
        evidence_type = str(selector.get("evidence_type") or "")
        anchors = tuple(str(value) for value in selector.get("contains_all") or ())
        matches = [
            str(row["compiled_object_id"])
            for row in objects
            if str(row.get("source_evidence_type") or "") == evidence_type
            and all(anchor in str(row.get("model_text") or "") for anchor in anchors)
        ]
        if len(matches) != 1:
            raise ValueError(
                f"vs2_replay_target_selector_not_unique:{evidence_type}:{len(matches)}"
            )
        output.append(
            {
                "evidence_type": evidence_type,
                "contains_all": list(anchors),
                "compiled_object_id": matches[0],
            }
        )
    if not output:
        raise ValueError("vs2_replay_targets_empty")
    return output


def run_vs2_replay(*, policy_path: Path, cache_root: Path) -> dict[str, Any]:
    policy = _load_policy(policy_path)
    paths = _validate_bindings(policy)
    identities, model_paths = _model_identities(policy)
    result = _read_json(paths["vs2_result"])
    payloads = result.get("payloads") or {}
    request_raw = payloads.get("evidence_request") or {}
    lanes = (payloads.get("query_facet_plan") or {}).get("lanes") or []
    if len(lanes) != 1:
        raise ValueError("vs2_replay_lane_count_invalid")
    request = _namespace_request(request_raw)
    lane = _namespace_lane(lanes[0])
    need_policy = _read_json(paths["retrieval_need_policy"])
    intent_ontology = (
        _read_json(paths["financial_intent_ontology"])
        if "financial_intent_ontology" in paths
        else None
    )
    need_set = compile_retrieval_needs(
        request=request,
        lane=lane,
        policy=need_policy,
        intent_ontology=intent_ontology,
    )
    raw_objects = _read_jsonl(
        ROOT
        / "data/workbench_private/s1_vs2_complex_pdf/v1/financial_objects.jsonl"
    )
    objects = _adapt_vs2_financial_objects(raw_objects)
    object_identity = canonical_digest(objects)
    eligible = np.arange(len(objects), dtype=np.int64)
    contract = policy["candidate_contract"]
    model_policy = policy["models"]
    per_need_limit = int(contract["first_stage_per_need_limit"])
    union_limit = int(contract["atom_candidate_union_limit"])
    top_k = int(contract["top_k"])

    bge_dense, bge_sparse, bge_cache, bge_runtime = load_or_build_bge_m3_cache(
        objects=objects,
        object_sha256=object_identity,
        model_dir=model_paths["bge_embedding"],
        model_identity=identities["bge_embedding"],
        cache_dir=cache_root / "vs2_bge_m3_objects_v1",
        maximum_sequence_length=int(model_policy["bge_embedding"]["maximum_sequence_length"]),
        batch_size=int(model_policy["bge_embedding"]["batch_size"]),
    )
    bge_queries = bge_runtime.encode(
        [need.semantic_query for need in need_set.needs],
        batch_size=4,
        max_length=int(model_policy["bge_embedding"]["maximum_sequence_length"]),
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=True,
    )
    bge_query_dense = np.asarray(bge_queries["dense_vecs"], dtype=np.float32)
    bge_query_sparse = sparse_weight_matrix(
        bge_queries["lexical_weights"], width=int(bge_sparse.shape[1])
    )
    lexical = rank_need_lexical_routes(
        objects=objects,
        eligible_indices=eligible,
        needs=need_set.needs,
        per_need_limit=per_need_limit,
    )
    metric_rows = rank_need_metric_row_routes(
        objects=objects,
        eligible_indices=eligible,
        needs=need_set.needs,
        per_need_limit=per_need_limit,
    )
    intent_alias_rows = rank_need_intent_alias_routes(
        objects=objects,
        eligible_indices=eligible,
        needs=need_set.needs,
        per_need_limit=per_need_limit,
    )
    bge_dense_routes = rank_need_dense_routes(
        route_id="bge_m3_dense",
        objects=objects,
        eligible_indices=eligible,
        needs=need_set.needs,
        document_embeddings=bge_dense,
        query_embeddings=bge_query_dense,
        per_need_limit=per_need_limit,
    )
    bge_sparse_routes = rank_need_sparse_routes(
        route_id="bge_m3_learned_sparse",
        objects=objects,
        eligible_indices=eligible,
        needs=need_set.needs,
        document_sparse=bge_sparse,
        query_sparse=bge_query_sparse,
        per_need_limit=per_need_limit,
    )

    qwen_dense, qwen_cache, qwen_runtime = load_or_build_qwen_embedding_cache(
        objects=objects,
        object_sha256=object_identity,
        model_dir=model_paths["qwen_embedding"],
        model_identity=identities["qwen_embedding"],
        cache_dir=cache_root / "vs2_qwen3_objects_v1",
        maximum_sequence_length=int(model_policy["qwen_embedding"]["maximum_sequence_length"]),
        batch_size=int(model_policy["qwen_embedding"]["batch_size"]),
    )
    qwen_query_dense = np.asarray(
        qwen_runtime.encode(
            [need.semantic_query for need in need_set.needs],
            batch_size=int(model_policy["qwen_embedding"]["batch_size"]),
            prompt=str(model_policy["qwen_embedding"]["query_instruction"]),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ),
        dtype=np.float32,
    )
    qwen_routes = rank_need_dense_routes(
        route_id="qwen3_embedding_0_6b_dense",
        objects=objects,
        eligible_indices=eligible,
        needs=need_set.needs,
        document_embeddings=qwen_dense,
        query_embeddings=qwen_query_dense,
        per_need_limit=per_need_limit,
    )
    first_stage_routes = (
        *lexical,
        *metric_rows,
        *intent_alias_rows,
        *bge_dense_routes,
        *bge_sparse_routes,
        *qwen_routes,
    )
    combined = fuse_need_rankings(
        first_stage_routes,
        maximum=union_limit,
        reciprocal_rank_constant=int(contract["reciprocal_rank_constant"]),
    )
    candidate_ids = [row.compiled_object_id for row in combined]
    objects_by_id = {str(row["compiled_object_id"]): row for row in objects}
    multi_rankings, best_need = _multi_vector_rankings(
        runtime=bge_runtime,
        query_vectors=list(bge_queries["colbert_vecs"]),
        needs=need_set.needs,
        candidate_ids=candidate_ids[: int(contract["multi_vector_pool_limit"])],
        objects_by_id=objects_by_id,
        maximum_sequence_length=int(model_policy["bge_embedding"]["maximum_sequence_length"]),
        batch_size=int(model_policy["bge_embedding"]["batch_size"]),
    )
    del bge_runtime, qwen_runtime
    _empty_cuda()

    rerank_ids = candidate_ids[: int(contract["reranker_pool_limit"])]
    need_by_id = {row.need_id: row for row in need_set.needs}
    rerank_each_candidate_against_all_needs = bool(
        contract.get("rerank_each_candidate_against_all_needs")
    )
    pairs = (
        [
            (need.semantic_query, str(objects_by_id[object_id]["model_text"]))
            for object_id in rerank_ids
            for need in need_set.needs
        ]
        if rerank_each_candidate_against_all_needs
        else [
            (
                need_by_id[best_need[object_id]].semantic_query,
                str(objects_by_id[object_id]["model_text"]),
            )
            for object_id in rerank_ids
        ]
    )
    bge_reranker = load_local_cross_encoder(
        model_paths["bge_reranker"],
        maximum_sequence_length=int(model_policy["bge_reranker"]["maximum_sequence_length"]),
    )
    bge_pair_scores = score_cross_encoder_pairs(
        bge_reranker,
        pairs,
        batch_size=int(model_policy["bge_reranker"]["batch_size"]),
        progress_every=None,
    )
    bge_rows = (
        aggregate_all_need_pair_scores(
            candidate_ids=rerank_ids,
            need_ids=tuple(value.need_id for value in need_set.needs),
            pair_scores=bge_pair_scores,
        )[0]
        if rerank_each_candidate_against_all_needs
        else rank_scores(rerank_ids, bge_pair_scores)
    )
    del bge_reranker
    _empty_cuda()
    qwen_reranker = load_local_qwen3_reranker(
        model_paths["qwen_reranker"],
        maximum_sequence_length=int(model_policy["qwen_reranker"]["maximum_sequence_length"]),
        instruction=str(model_policy["qwen_reranker"]["instruction"]),
    )
    qwen_pair_scores = score_qwen3_reranker_pairs(
        qwen_reranker,
        pairs,
        batch_size=int(model_policy["qwen_reranker"]["batch_size"]),
    )
    qwen_rows = (
        aggregate_all_need_pair_scores(
            candidate_ids=rerank_ids,
            need_ids=tuple(value.need_id for value in need_set.needs),
            pair_scores=qwen_pair_scores,
        )[0]
        if rerank_each_candidate_against_all_needs
        else rank_scores(rerank_ids, qwen_pair_scores)
    )
    del qwen_reranker
    _empty_cuda()

    # Evaluator-only reference is deliberately loaded after natural scoring.
    reference_rows = _read_jsonl(paths["vs2_evaluator"])
    if len(reference_rows) != 1:
        raise ValueError("vs2_replay_reference_count_invalid")
    reference = reference_rows[0]["expected_outcome"]
    targets = _resolve_vs2_targets(objects, reference)
    target_ids = [row["compiled_object_id"] for row in targets]
    fake_atom = SimpleNamespace(
        positive_object_ids=tuple(target_ids),
        hard_negative_object_ids=(),
        expected_roles_by_object_id={},
    )
    roles = _role_rows(
        atom=fake_atom,
        lane=lane,
        candidate_ids=rerank_ids,
        objects_by_id=objects_by_id,
    )
    role_guarded = _role_guarded_ranking(
        candidate_ids=rerank_ids,
        bge_rows=bge_rows,
        qwen_rows=qwen_rows,
        role_rows=roles,
    )
    rankings = {
        "combined_need_union": combined,
        "bge_m3_multi_vector_refinement": fuse_need_rankings(
            multi_rankings,
            maximum=len(rerank_ids),
            reciprocal_rank_constant=int(contract["reciprocal_rank_constant"]),
        ),
        "bge_reranker_v2_m3": bge_rows,
        "qwen3_reranker_0_6b": qwen_rows,
        "role_guarded_dual_reranker_shadow": role_guarded,
    }
    rank_maps = {
        route_id: {
            row.compiled_object_id: rank for rank, row in enumerate(rows, 1)
        }
        for route_id, rows in rankings.items()
    }
    cross_encoder_ranks_by_id = {
        object_id: {
            route_id: ranks.get(object_id)
            for route_id, ranks in rank_maps.items()
            if route_id
            in {
                "bge_reranker_v2_m3",
                "qwen3_reranker_0_6b",
                "role_guarded_dual_reranker_shadow",
            }
        }
        for object_id in candidate_ids
    }
    shortlist = rank_financial_evidence_shortlist(
        union_object_ids=candidate_ids,
        objects_by_id=objects_by_id,
        lane=lane,
        route_membership=route_membership(first_stage_routes, candidate_ids),
        cross_encoder_ranks_by_id=cross_encoder_ranks_by_id,
        request=request_raw if intent_ontology is not None else None,
        intent_ontology=intent_ontology,
        retrieval_needs=[value.as_dict() for value in need_set.needs],
    )
    shortlist_top_ids = [
        str(value["compiled_object_id"]) for value in shortlist[:top_k]
    ]
    include_revision_context = any(
        phrase in " ".join(
            (
                *(str(value) for value in request_raw.get("metric_intents") or ()),
                *(str(value) for value in request_raw.get("forbidden_proxy") or ()),
            )
        ).casefold()
        for phrase in ("year over year", "comparative", "restatement", "adjusted")
    )
    context_expansion = expand_bounded_candidate_context(
        selected_object_ids=shortlist_top_ids,
        objects_by_id=objects_by_id,
        include_document_revision_context=include_revision_context,
        maximum_context_per_candidate=6,
    )
    final_review_ids = set(shortlist_top_ids) | set(
        context_expansion["expanded_context_object_ids"]
    )
    selector_results = []
    for target in targets:
        object_id = target["compiled_object_id"]
        selector_results.append(
            {
                **target,
                "route_ranks": {
                    route_id: ranks.get(object_id)
                    for route_id, ranks in rank_maps.items()
                },
                "in_combined_pool": object_id in rank_maps["combined_need_union"],
                "in_any_top_k": any(
                    ranks.get(object_id, top_k + 1) <= top_k
                    for ranks in rank_maps.values()
                ),
                "in_financial_shortlist_top_k": object_id in shortlist_top_ids,
                "attached_as_bounded_context": (
                    object_id
                    in context_expansion["expanded_context_object_ids"]
                ),
                "in_final_review_surface": object_id in final_review_ids,
            }
        )
    minimum = int(policy["decision_gates"]["vs2_complex_target_in_pool_minimum"])
    review_minimum = int(
        policy["decision_gates"].get(
            "vs2_complex_target_in_review_window_minimum", 0
        )
    )
    in_pool = sum(row["in_combined_pool"] for row in selector_results)
    in_review = sum(row["in_final_review_surface"] for row in selector_results)
    unsigned = {
        "schema_version": "fin_ia_s1_vs3_vs2_same_runtime_replay_result_v1_0",
        "status": "vs2_same_runtime_candidate_replay_complete",
        "recorded_at": "2026-08-17",
        "bound_inputs": {
            "policy_ref": _relative(policy_path),
            "policy_sha256_lf": _sha256_lf(policy_path),
            "vs2_result_ref": _relative(paths["vs2_result"]),
            "vs2_result_sha256_lf": _sha256_lf(paths["vs2_result"]),
            "vs2_evaluator_ref": _relative(paths["vs2_evaluator"]),
            "vs2_evaluator_sha256_lf": _sha256_lf(paths["vs2_evaluator"]),
            "object_identity_digest": object_identity,
        },
        "execution": {
            "object_count": len(objects),
            "retrieval_need_count": len(need_set.needs),
            "candidate_pool_count": len(candidate_ids),
            "network_calls": 0,
            "generation_model_calls": 0,
            "training_steps": 0,
            "bge_embedding_cache": bge_cache,
            "qwen_embedding_cache": qwen_cache,
            "labels_joined_after_candidate_generation": True,
            "financial_shortlist_top_ids": shortlist_top_ids,
            "bounded_context_expansion": context_expansion,
        },
        "selector_results": selector_results,
        "summary": {
            "reviewed_target_count": len(targets),
            "target_in_combined_pool_count": in_pool,
            "target_in_any_top_k_count": sum(row["in_any_top_k"] for row in selector_results),
            "minimum_required_in_pool": minimum,
            "target_in_financial_shortlist_top_k_count": sum(
                row["in_financial_shortlist_top_k"] for row in selector_results
            ),
            "target_attached_as_bounded_context_count": sum(
                row["attached_as_bounded_context"] for row in selector_results
            ),
            "target_in_final_review_surface_count": in_review,
            "minimum_required_in_final_review_surface": review_minimum,
            "same_runtime_replay_passed": (
                in_pool >= minimum and in_review >= review_minimum
            ),
        },
        "authority": {
            "development_case_only": True,
            "candidate_is_not_evidence": True,
            "numeric_fact_authority": False,
            "IFX_is_not_a_product_case": True,
            "runtime_route_promotion_authorized": False,
        },
    }
    return {**unsigned, "result_digest": canonical_digest(unsigned)}


def run(*, policy_path: Path, cache_root: Path) -> dict[str, Any]:
    cuda_execution_receipt = _required_cuda_execution_receipt()
    policy = _load_policy(policy_path)
    paths = _validate_bindings(policy)
    kernel = load_financial_research_kernel(_read_json(paths["kernel"]))
    route_policy = load_query_object_fact_route_policy(
        _read_json(paths["route_policy"]), kernel
    )
    need_policy = _read_json(paths["retrieval_need_policy"])
    intent_ontology = (
        _read_json(paths["financial_intent_ontology"])
        if "financial_intent_ontology" in paths
        else None
    )
    atoms = _load_bound_query_atoms(paths)
    objects = list(load_compiled_objects(_read_jsonl(paths["compiled_objects"])))
    objects_by_id = {str(row["compiled_object_id"]): row for row in objects}
    object_sha256 = sha256_file(paths["compiled_objects"])
    identities, model_paths = _model_identities(policy)
    model_policy = policy["models"]
    contract = policy["candidate_contract"]
    per_need_limit = int(contract["first_stage_per_need_limit"])
    union_limit = int(contract["atom_candidate_union_limit"])
    reranker_limit = int(contract["reranker_pool_limit"])
    top_k = int(contract["top_k"])

    compiled = []
    all_needs = []
    for atom in atoms:
        request, lane = compile_atom_lane(atom, kernel)
        need_set = compile_retrieval_needs(
            request=request,
            lane=lane,
            policy=need_policy,
            intent_ontology=intent_ontology,
        )
        eligible, exclusions = eligible_atom_indices(
            objects, atom=atom, lane=lane, route_policy=route_policy
        )
        rankable, projection_only = rank_authority_indices(
            objects,
            eligible,
            allowed_object_kinds=contract.get(
                "rank_authority_object_kinds", ("claim", "metric_row")
            ),
        )
        compiled.append(
            {
                "atom": atom,
                "request": request,
                "lane": lane,
                "need_set": need_set,
                "eligible": eligible,
                "rankable": rankable,
                "exclusions": exclusions,
                "projection_only": projection_only,
            }
        )
        all_needs.extend(need_set.needs)
    slices = _need_slices([len(row["need_set"].needs) for row in compiled])

    bge_dense, bge_sparse, bge_cache, bge_runtime = load_or_build_bge_m3_cache(
        objects=objects,
        object_sha256=object_sha256,
        model_dir=model_paths["bge_embedding"],
        model_identity=identities["bge_embedding"],
        cache_dir=cache_root / "bge_m3_sentence_objects_v4",
        maximum_sequence_length=int(model_policy["bge_embedding"]["maximum_sequence_length"]),
        batch_size=int(model_policy["bge_embedding"]["batch_size"]),
    )
    started = time.perf_counter()
    bge_queries = bge_runtime.encode(
        [need.semantic_query for need in all_needs],
        batch_size=4,
        max_length=int(model_policy["bge_embedding"]["maximum_sequence_length"]),
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=True,
    )
    bge_query_seconds = time.perf_counter() - started
    bge_query_dense = np.asarray(bge_queries["dense_vecs"], dtype=np.float32)
    bge_query_sparse = sparse_weight_matrix(
        bge_queries["lexical_weights"], width=int(bge_sparse.shape[1])
    )
    bge_query_multi = list(bge_queries["colbert_vecs"])
    del bge_runtime
    _empty_cuda()

    qwen_dense, qwen_cache, qwen_runtime = load_or_build_qwen_embedding_cache(
        objects=objects,
        object_sha256=object_sha256,
        model_dir=model_paths["qwen_embedding"],
        model_identity=identities["qwen_embedding"],
        cache_dir=cache_root / "qwen3_embedding_sentence_objects_v4",
        maximum_sequence_length=int(model_policy["qwen_embedding"]["maximum_sequence_length"]),
        batch_size=int(model_policy["qwen_embedding"]["batch_size"]),
    )
    started = time.perf_counter()
    qwen_query_dense = np.asarray(
        qwen_runtime.encode(
            [need.semantic_query for need in all_needs],
            batch_size=int(model_policy["qwen_embedding"]["batch_size"]),
            prompt=str(model_policy["qwen_embedding"]["query_instruction"]),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ),
        dtype=np.float32,
    )
    qwen_query_seconds = time.perf_counter() - started
    del qwen_runtime
    _empty_cuda()

    atom_rows: list[dict[str, Any]] = []
    first_stage_manifests = []
    for row, query_slice in zip(compiled, slices):
        atom = row["atom"]
        lane = row["lane"]
        needs = row["need_set"].needs
        lexical = rank_need_lexical_routes(
            objects=objects,
            eligible_indices=row["rankable"],
            needs=needs,
            per_need_limit=per_need_limit,
        )
        metric_rows = rank_need_metric_row_routes(
            objects=objects,
            eligible_indices=row["rankable"],
            needs=needs,
            per_need_limit=per_need_limit,
        )
        intent_alias_rows = rank_need_intent_alias_routes(
            objects=objects,
            eligible_indices=row["rankable"],
            needs=needs,
            per_need_limit=per_need_limit,
        )
        bge_dense_routes = rank_need_dense_routes(
            route_id="bge_m3_dense",
            objects=objects,
            eligible_indices=row["rankable"],
            needs=needs,
            document_embeddings=bge_dense,
            query_embeddings=bge_query_dense[query_slice],
            per_need_limit=per_need_limit,
        )
        bge_sparse_routes = rank_need_sparse_routes(
            route_id="bge_m3_learned_sparse",
            objects=objects,
            eligible_indices=row["rankable"],
            needs=needs,
            document_sparse=bge_sparse,
            query_sparse=bge_query_sparse[query_slice],
            per_need_limit=per_need_limit,
        )
        qwen_dense_routes = rank_need_dense_routes(
            route_id="qwen3_embedding_0_6b_dense",
            objects=objects,
            eligible_indices=row["rankable"],
            needs=needs,
            document_embeddings=qwen_dense,
            query_embeddings=qwen_query_dense[query_slice],
            per_need_limit=per_need_limit,
        )
        all_first_stage = (
            *lexical,
            *metric_rows,
            *intent_alias_rows,
            *bge_dense_routes,
            *bge_sparse_routes,
            *qwen_dense_routes,
        )
        route_groups = {
            "bm25_need_lexical": tuple(
                value for value in lexical if value.route_id == "bm25_need_lexical"
            ),
            "typed_exact_phrase": tuple(
                value for value in lexical if value.route_id == "typed_exact_phrase"
            ),
            "typed_metric_row_exact": metric_rows,
            "typed_intent_alias_groups": intent_alias_rows,
            "bge_m3_dense": bge_dense_routes,
            "bge_m3_learned_sparse": bge_sparse_routes,
            "qwen3_embedding_0_6b_dense": qwen_dense_routes,
        }
        route_rows = {
            route_id: fuse_need_rankings(
                rankings,
                maximum=union_limit,
                reciprocal_rank_constant=int(contract["reciprocal_rank_constant"]),
            ) if rankings else ()
            for route_id, rankings in route_groups.items()
        }
        broad_bm25 = tuple(
            bm25_rank(
                objects,
                row["rankable"],
                lane.lexical_query,
                limit=union_limit,
            )
        )
        route_floors = contract.get("candidate_union_route_minimum_per_need") or {}
        combined = (
            fuse_need_rankings_with_route_floors(
                all_first_stage,
                maximum=union_limit,
                route_minimum_per_need=route_floors,
                reciprocal_rank_constant=int(contract["reciprocal_rank_constant"]),
            )
            if route_floors
            else fuse_need_rankings(
                all_first_stage,
                maximum=union_limit,
                reciprocal_rank_constant=int(contract["reciprocal_rank_constant"]),
            )
        )
        candidate_ids = [value.compiled_object_id for value in combined]
        first_stage_manifests.append(
            {
                "rankings": all_first_stage,
                "combined": combined,
                "candidate_ids": candidate_ids,
                "needs": needs,
                "query_slice": query_slice,
            }
        )
        atom_rows.append(
            {
                "atom_id": atom.atom_id,
                "case_key": str(atom.request_payload["case_key"]),
                "slot_id": lane.slot_id,
                "facet_id": lane.facet_id,
                "evidence_owner_ticker": lane.evidence_owner_tickers[0],
                "relationship_direction": lane.relationship_constraints[0],
                "hard_eligible_object_count": int(row["eligible"].size),
                "rank_authority_object_count": int(row["rankable"].size),
                "projection_only_counts": row["projection_only"],
                "exclusion_counts": row["exclusions"],
                "retrieval_need_set": row["need_set"].as_dict(),
                "first_stage": {
                    "broad_lane_bm25_baseline": _route_summary(
                        broad_bm25, atom, top_k=top_k
                    ),
                    **{
                        route_id: _route_summary(values, atom, top_k=top_k)
                        for route_id, values in route_rows.items()
                    },
                    "combined_need_union": _route_summary(
                        combined, atom, top_k=top_k
                    ),
                },
                "candidate_union_ids": candidate_ids,
                "route_membership": route_membership(
                    all_first_stage, candidate_ids
                ),
                "candidate_not_evidence": True,
                "numeric_authority": False,
            }
        )

    bge_runtime = load_bge_m3_runtime(model_paths["bge_embedding"])
    multi_seconds = 0.0
    pair_manifests: list[list[tuple[str, str]]] = []
    rerank_each_candidate_against_all_needs = bool(
        contract.get("rerank_each_candidate_against_all_needs")
    )
    for index, (row, manifest, query_slice) in enumerate(
        zip(compiled, first_stage_manifests, slices)
    ):
        candidate_ids = manifest["candidate_ids"][: int(contract["multi_vector_pool_limit"])]
        started = time.perf_counter()
        multi_rankings, best_need = _multi_vector_rankings(
            runtime=bge_runtime,
            query_vectors=bge_query_multi[query_slice],
            needs=manifest["needs"],
            candidate_ids=candidate_ids,
            objects_by_id=objects_by_id,
            maximum_sequence_length=int(model_policy["bge_embedding"]["maximum_sequence_length"]),
            batch_size=int(model_policy["bge_embedding"]["batch_size"]),
        )
        multi_seconds += time.perf_counter() - started
        multi_rows = fuse_need_rankings(
            multi_rankings,
            maximum=len(candidate_ids),
            reciprocal_rank_constant=int(contract["reciprocal_rank_constant"]),
        )
        atom_rows[index]["first_stage"]["bge_m3_multi_vector_refinement"] = (
            _route_summary(multi_rows, row["atom"], top_k=top_k)
        )
        manifest["multi_rows"] = multi_rows
        need_by_id = {value.need_id: value for value in manifest["needs"]}
        rerank_ids = manifest["candidate_ids"][:reranker_limit]
        manifest["rerank_ids"] = rerank_ids
        manifest["best_need"] = best_need
        if rerank_each_candidate_against_all_needs:
            pair_manifests.append(
                [
                    (need.semantic_query, str(objects_by_id[object_id]["model_text"]))
                    for object_id in rerank_ids
                    for need in manifest["needs"]
                ]
            )
        else:
            pair_manifests.append(
                [
                    (
                        need_by_id[best_need[object_id]].semantic_query,
                        str(objects_by_id[object_id]["model_text"]),
                    )
                    for object_id in rerank_ids
                ]
            )
    del bge_runtime
    _empty_cuda()

    pair_manifest_digest = canonical_digest(pair_manifests)
    pair_counts = [len(values) for values in pair_manifests]
    score_cache_root = cache_root / "reranker_score_cache_v1"

    bge_cache_key = _score_cache_key(
        scorer_id="bge_sequence_classification_v1",
        model_digest=str(identities["bge_reranker"]["model_digest"]),
        pair_manifest_digest=pair_manifest_digest,
        maximum_sequence_length=int(
            model_policy["bge_reranker"]["maximum_sequence_length"]
        ),
    )
    bge_score_cache_path = score_cache_root / f"bge_{bge_cache_key}.json"
    bge_scores = _load_score_matrix_cache(
        bge_score_cache_path,
        cache_key=bge_cache_key,
        pair_counts=pair_counts,
    )
    bge_score_cache_reused = bge_scores is not None
    started = time.perf_counter()
    if bge_scores is None:
        bge_reranker = load_local_cross_encoder(
            model_paths["bge_reranker"],
            maximum_sequence_length=int(
                model_policy["bge_reranker"]["maximum_sequence_length"]
            ),
        )
        bge_scores = [
            score_cross_encoder_pairs(
                bge_reranker,
                pairs,
                batch_size=int(model_policy["bge_reranker"]["batch_size"]),
                progress_every=None,
            )
            for pairs in pair_manifests
        ]
        _write_score_matrix_cache(
            bge_score_cache_path,
            cache_key=bge_cache_key,
            pair_manifest_digest=pair_manifest_digest,
            scores=bge_scores,
        )
        del bge_reranker
        _empty_cuda()
    bge_reranker_seconds = time.perf_counter() - started

    qwen_instruction = str(model_policy["qwen_reranker"]["instruction"])
    qwen_cache_key = _score_cache_key(
        scorer_id="qwen3_yes_no_causal_lm_v1",
        model_digest=str(identities["qwen_reranker"]["model_digest"]),
        pair_manifest_digest=pair_manifest_digest,
        maximum_sequence_length=int(
            model_policy["qwen_reranker"]["maximum_sequence_length"]
        ),
        instruction=qwen_instruction,
    )
    qwen_score_cache_path = score_cache_root / f"qwen_{qwen_cache_key}.json"
    qwen_scores = _load_score_matrix_cache(
        qwen_score_cache_path,
        cache_key=qwen_cache_key,
        pair_counts=pair_counts,
    )
    qwen_score_cache_reused = qwen_scores is not None
    started = time.perf_counter()
    if qwen_scores is None:
        qwen_reranker = load_local_qwen3_reranker(
            model_paths["qwen_reranker"],
            maximum_sequence_length=int(
                model_policy["qwen_reranker"]["maximum_sequence_length"]
            ),
            instruction=qwen_instruction,
        )
        qwen_scores = [
            score_qwen3_reranker_pairs(
                qwen_reranker,
                pairs,
                batch_size=int(model_policy["qwen_reranker"]["batch_size"]),
            )
            for pairs in pair_manifests
        ]
        _write_score_matrix_cache(
            qwen_score_cache_path,
            cache_key=qwen_cache_key,
            pair_manifest_digest=pair_manifest_digest,
            scores=qwen_scores,
        )
        del qwen_reranker
        _empty_cuda()
    qwen_reranker_seconds = time.perf_counter() - started

    for index, (row, manifest) in enumerate(zip(compiled, first_stage_manifests)):
        atom = row["atom"]
        rerank_ids = manifest["rerank_ids"]
        if rerank_each_candidate_against_all_needs:
            need_ids = tuple(value.need_id for value in manifest["needs"])
            bge_rows, bge_best_need = aggregate_all_need_pair_scores(
                candidate_ids=rerank_ids,
                need_ids=need_ids,
                pair_scores=bge_scores[index],
            )
            qwen_rows, qwen_best_need = aggregate_all_need_pair_scores(
                candidate_ids=rerank_ids,
                need_ids=need_ids,
                pair_scores=qwen_scores[index],
            )
        else:
            bge_rows = rank_scores(rerank_ids, bge_scores[index])
            qwen_rows = rank_scores(rerank_ids, qwen_scores[index])
            bge_best_need = dict(manifest["best_need"])
            qwen_best_need = dict(manifest["best_need"])
        roles = _role_rows(
            atom=atom,
            lane=row["lane"],
            candidate_ids=rerank_ids,
            objects_by_id=objects_by_id,
        )
        audit = label_eligibility_rows(
            objects,
            atom=atom,
            lane=row["lane"],
            route_policy=route_policy,
        )
        eligibility_by_id = {
            str(value["compiled_object_id"]): value for value in audit
        }
        judged_role_ids = tuple(
            dict.fromkeys(
                (*atom.positive_object_ids, *atom.hard_negative_object_ids)
            )
        )
        judged_roles = _role_rows(
            atom=atom,
            lane=row["lane"],
            candidate_ids=judged_role_ids,
            objects_by_id=objects_by_id,
        )
        for judged_row in judged_roles:
            eligibility = eligibility_by_id[judged_row["compiled_object_id"]]
            judged_row["eligibility"] = {
                "eligible": bool(eligibility["eligible"]),
                "exclusion_reason": eligibility["exclusion_reason"],
            }
        eligible_judged_roles = [
            value
            for value in judged_roles
            if value["eligibility"]["eligible"]
        ]
        role_guarded = _role_guarded_ranking(
            candidate_ids=rerank_ids,
            bge_rows=bge_rows,
            qwen_rows=qwen_rows,
            role_rows=roles,
        )
        cross_rankings = {
            "bge_reranker_v2_m3": bge_rows,
            "qwen3_reranker_0_6b": qwen_rows,
            "role_guarded_dual_reranker_shadow": role_guarded,
        }
        cross_rank_maps = {
            route_id: {
                value.compiled_object_id: rank
                for rank, value in enumerate(values, start=1)
            }
            for route_id, values in cross_rankings.items()
        }
        shortlist = rank_financial_evidence_shortlist(
            union_object_ids=manifest["candidate_ids"],
            objects_by_id=objects_by_id,
            lane=row["lane"],
            route_membership=atom_rows[index]["route_membership"],
            cross_encoder_ranks_by_id={
                object_id: {
                    route_id: ranks.get(object_id)
                    for route_id, ranks in cross_rank_maps.items()
                }
                for object_id in manifest["candidate_ids"]
            },
            request=atom.request_payload if intent_ontology is not None else None,
            intent_ontology=intent_ontology,
            retrieval_needs=[value.as_dict() for value in manifest["needs"]],
        )
        shortlist_rows = tuple(
            CandidateScore(
                compiled_object_id=str(value["compiled_object_id"]),
                score=float(len(shortlist) - rank),
            )
            for rank, value in enumerate(shortlist)
        )
        rerankers = {
            "bge_reranker_v2_m3": _route_summary(bge_rows, atom, top_k=top_k),
            "qwen3_reranker_0_6b": _route_summary(qwen_rows, atom, top_k=top_k),
            "role_guarded_dual_reranker_shadow": _route_summary(
                role_guarded, atom, top_k=top_k
            ),
            "financial_evidence_shortlist_v1": _route_summary(
                shortlist_rows, atom, top_k=top_k
            ),
        }
        route_floors = contract.get("candidate_union_route_minimum_per_need") or {}
        reversed_fusion = (
            fuse_need_rankings_with_route_floors(
                tuple(reversed(manifest["rankings"])),
                maximum=union_limit,
                route_minimum_per_need=route_floors,
                reciprocal_rank_constant=int(contract["reciprocal_rank_constant"]),
            )
            if route_floors
            else fuse_need_rankings(
                tuple(reversed(manifest["rankings"])),
                maximum=union_limit,
                reciprocal_rank_constant=int(contract["reciprocal_rank_constant"]),
            )
        )
        whitespace_stable = all(
            tokenize(str(objects_by_id[item["compiled_object_id"]]["model_text"]))
            == tokenize(
                " \n ".join(
                    str(objects_by_id[item["compiled_object_id"]]["model_text"]).split()
                )
            )
            for item in audit
            if item["compiled_object_id"] in objects_by_id
        )
        atom_rows[index].update(
            {
                "rerankers": rerankers,
                "evidence_role": {
                    "rows": roles,
                    "metrics": _role_metrics(roles),
                    "judged_label_rows": judged_roles,
                    "judged_label_metrics": _role_metrics(eligible_judged_roles),
                    "judged_label_metrics_scope": (
                        "hard_boundary_eligible_labels_only"
                    ),
                    "ineligible_judged_label_count": (
                        len(judged_roles) - len(eligible_judged_roles)
                    ),
                    "runtime_authority": "shadow_only",
                    "ranking_strategy": (
                        "qwen_primary_with_evidence_role_strata_and_bge_tie_shadow"
                    ),
                },
                "reranker_need_selection": {
                    "strategy": (
                        "each_reranker_scores_every_bounded_need_then_selects_own_best"
                        if rerank_each_candidate_against_all_needs
                        else "bge_multi_vector_preselects_one_need_for_both_rerankers"
                    ),
                    "pair_count_per_reranker": len(pair_manifests[index]),
                    "bge_best_need_by_candidate": bge_best_need,
                    "qwen_best_need_by_candidate": qwen_best_need,
                },
                "reranker_ranked_ids": {
                    "bge_reranker_v2_m3": [
                        value.compiled_object_id for value in bge_rows
                    ],
                    "qwen3_reranker_0_6b": [
                        value.compiled_object_id for value in qwen_rows
                    ],
                    "role_guarded_dual_reranker_shadow": [
                        value.compiled_object_id for value in role_guarded
                    ],
                    "financial_evidence_shortlist_v1": [
                        value.compiled_object_id for value in shortlist_rows
                    ],
                },
                "financial_evidence_shortlist": {
                    "top_rows": list(shortlist[: max(top_k, 20)]),
                    "candidate_count": len(shortlist),
                    "candidate_is_not_evidence": True,
                    "numeric_authority": False,
                    "ranking_basis": (
                        "typed_intent_role_source_period_directness_routes_and_cross_encoder"
                    ),
                },
                "label_eligibility": audit,
                "stability": {
                    "need_order_union_stable": [
                        value.compiled_object_id for value in reversed_fusion
                    ] == manifest["candidate_ids"],
                    "candidate_pair_order_stable": ranking_candidate_order_stable(
                        candidate_ids=rerank_ids,
                        rows=bge_rows,
                    ),
                    "label_text_whitespace_tokenization_stable": whitespace_stable,
                },
            }
        )
        atom_rows[index]["earliest_failure_layer"] = _earliest_failure(
            atom=atom,
            label_audit=audit,
            combined=atom_rows[index]["first_stage"]["combined_need_union"],
            rerankers=rerankers,
            final_shortlist=rerankers["financial_evidence_shortlist_v1"],
        )

    first_stage_summary = _aggregate_routes(atom_rows, "first_stage")
    reranker_summary = _aggregate_routes(atom_rows, "rerankers")
    positive_atoms = sum(bool(atom.positive_object_ids) for atom in atoms)
    stable_checks = [
        value for row in atom_rows for value in row["stability"].values()
    ]
    candidate_role_rows = [
        role for row in atom_rows for role in row["evidence_role"]["rows"]
    ]
    judged_role_rows = [
        role
        for row in atom_rows
        for role in row["evidence_role"]["judged_label_rows"]
    ]
    eligible_judged_role_rows = [
        role
        for role in judged_role_rows
        if role.get("eligibility", {}).get("eligible") is True
    ]
    candidate_role_metrics = _role_metrics(candidate_role_rows)
    role_metrics = _role_metrics(eligible_judged_role_rows)
    earliest_counts: dict[str, int] = {}
    for row in atom_rows:
        key = row["earliest_failure_layer"]
        earliest_counts[key] = earliest_counts.get(key, 0) + 1
    first_stage_candidates = [
        (route_id, metrics)
        for route_id, metrics in first_stage_summary.items()
        if route_id != "broad_lane_bm25_baseline"
    ]
    provisional_first_stage = max(
        first_stage_candidates,
        key=lambda item: (
            item[1]["positive_target_in_ranking_count"],
            item[1]["positive_target_in_top_k_count"],
            item[1]["mean_reciprocal_rank"],
            -item[1]["hard_negative_in_ranking_count"],
            item[0],
        ),
    )[0]
    provisional_reranker = max(
        reranker_summary.items(),
        key=lambda item: (
            item[1]["positive_target_in_top_k_count"],
            item[1]["mean_reciprocal_rank"],
            -item[1]["hard_negative_in_ranking_count"],
            item[0],
        ),
    )[0]
    union_metrics = first_stage_summary["combined_need_union"]
    gates = policy["decision_gates"]
    union_rate = (
        union_metrics["positive_target_in_ranking_count"] / positive_atoms
        if positive_atoms else 0.0
    )
    head_stability = sum(stable_checks) / len(stable_checks) if stable_checks else 0.0
    vs1_mapping = _vs1_reviewed_successors(
        catalog=_read_json(paths["reviewed_claim_anchor_catalog"]), objects=objects
    )
    candidate_generation_gate_passed = (
        union_rate >= float(gates["positive_target_in_union_minimum_rate"])
        and head_stability >= float(gates["head_stability_minimum"])
        and vs1_mapping["unique_successor_count"]
        == vs1_mapping["reviewed_target_count"]
    )
    unsigned = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "vs3_candidate_ranking_complete_development_decision_materialized",
        "recorded_at": "2026-08-17",
        "experiment_id": policy["experiment_id"],
        "bound_inputs": {
            "policy_ref": _relative(policy_path),
            "policy_sha256_lf": _sha256_lf(policy_path),
            **{
                key + "_ref": _relative(path)
                for key, path in paths.items()
            },
            "compiled_objects_sha256": object_sha256,
        },
        "execution": {
            "cuda_execution_receipt": cuda_execution_receipt,
            "model_identities": identities,
            "bge_embedding_cache": bge_cache,
            "qwen_embedding_cache": qwen_cache,
            "bge_query_seconds": round(bge_query_seconds, 3),
            "qwen_query_seconds": round(qwen_query_seconds, 3),
            "bge_multi_vector_seconds": round(multi_seconds, 3),
            "bge_reranker_seconds": round(bge_reranker_seconds, 3),
            "qwen_reranker_seconds": round(qwen_reranker_seconds, 3),
            "reranker_score_cache": {
                "pair_manifest_digest": pair_manifest_digest,
                "bge_cache_key": bge_cache_key,
                "bge_reused": bge_score_cache_reused,
                "qwen_cache_key": qwen_cache_key,
                "qwen_reused": qwen_score_cache_reused,
            },
            "reranker_pair_count_per_model": sum(
                len(values) for values in pair_manifests
            ),
            "network_calls": 0,
            "generation_model_calls": 0,
            "training_steps": 0,
            "labels_joined_after_candidate_generation": True,
        },
        "summary": {
            "atom_count": len(atoms),
            "case_count": len({row["case_key"] for row in atom_rows}),
            "positive_atom_count": positive_atoms,
            "typed_gap_atom_count": len(atoms) - positive_atoms,
            "retrieval_need_count": len(all_needs),
            "first_stage": first_stage_summary,
            "rerankers": reranker_summary,
            "evidence_role": role_metrics,
            "candidate_pool_evidence_role": candidate_role_metrics,
            "earliest_failure_counts": dict(sorted(earliest_counts.items())),
            "head_stability_rate": round(head_stability, 6),
            "positive_target_in_combined_union_rate": round(union_rate, 6),
            "vs1_reviewed_successor_mapping": vs1_mapping,
        },
        "atoms": atom_rows,
        "decision": {
            "provisional_first_stage_route": provisional_first_stage,
            "provisional_reranker_route": provisional_reranker,
            "candidate_generation_gate_passed": candidate_generation_gate_passed,
            "runtime_route_promotion_authorized": False,
            "runtime_route_promotion_blocker": (
                "composite_vs1_vs2_head_quality_and_candidate_decision_gate_required"
            ),
            "evidence_role_runtime_authority": "shadow_only",
            "fine_tuning_eligible": len(eligible_judged_role_rows)
            >= int(gates["minimum_reviewed_relations_before_fine_tuning"])
            and len({row["case_key"] for row in atom_rows})
            >= int(gates["minimum_development_cases_before_fine_tuning"]),
            "fine_tuning_authorized": False,
            "vs2_complex_vertical_evaluation": "pending_same_runtime_replay",
            "vs4_acquisition_authorized": False,
            "s1_complete_claimed": False,
        },
        "token_budget_basis": policy["token_budget_basis"],
        "authority": policy["authority"],
    }
    return {**unsigned, "result_digest": canonical_digest(unsigned)}


def run_typed_route_proof(*, policy_path: Path) -> dict[str, Any]:
    """Prove the label-blind typed routes before any local model scoring.

    Labels and pre-registered expectations are joined only after every route
    has been compiled.  The proof therefore checks whether request semantics
    can recover or exclude known business objects without leaking qrel IDs
    into query construction.
    """

    policy = _load_policy(policy_path)
    paths = _validate_bindings(policy)
    kernel = load_financial_research_kernel(_read_json(paths["kernel"]))
    route_policy = load_query_object_fact_route_policy(
        _read_json(paths["route_policy"]), kernel
    )
    need_policy = _read_json(paths["retrieval_need_policy"])
    if "financial_intent_ontology" not in paths:
        raise ValueError("typed_route_proof_financial_intent_ontology_missing")
    intent_ontology = _read_json(paths["financial_intent_ontology"])
    atoms = _load_bound_query_atoms(paths)
    objects = list(load_compiled_objects(_read_jsonl(paths["compiled_objects"])))
    contract = policy["candidate_contract"]
    per_need_limit = int(contract["first_stage_per_need_limit"])

    atom_rows: list[dict[str, Any]] = []
    route_index: dict[tuple[str, str], dict[str, Any]] = {}
    for atom in atoms:
        request, lane = compile_atom_lane(atom, kernel)
        need_set = compile_retrieval_needs(
            request=request,
            lane=lane,
            policy=need_policy,
            intent_ontology=intent_ontology,
        )
        eligible, exclusions = eligible_atom_indices(
            objects, atom=atom, lane=lane, route_policy=route_policy
        )
        rankable, projection_only = rank_authority_indices(
            objects,
            eligible,
            allowed_object_kinds=contract.get(
                "rank_authority_object_kinds", ("claim", "metric_row")
            ),
        )
        rankings = (
            *rank_need_metric_row_routes(
                objects=objects,
                eligible_indices=rankable,
                needs=need_set.needs,
                per_need_limit=per_need_limit,
            ),
            *rank_need_intent_alias_routes(
                objects=objects,
                eligible_indices=rankable,
                needs=need_set.needs,
                per_need_limit=per_need_limit,
            ),
        )
        routes: dict[str, list[dict[str, Any]]] = {}
        best_rank_by_route: dict[str, dict[str, int]] = {}
        for ranking in rankings:
            object_ids = [row.compiled_object_id for row in ranking.rows]
            routes.setdefault(ranking.route_id, []).append(
                {
                    "need_id": ranking.need_id,
                    "object_ids": object_ids,
                }
            )
            best = best_rank_by_route.setdefault(ranking.route_id, {})
            for rank, object_id in enumerate(object_ids, start=1):
                best[object_id] = min(rank, best.get(object_id, rank))
        route_rows: dict[str, Any] = {}
        for route_id, need_rows in sorted(routes.items()):
            best = best_rank_by_route[route_id]
            route_rows[route_id] = {
                "need_results": need_rows,
                "best_rank_by_object_id": dict(
                    sorted(best.items(), key=lambda item: (item[1], item[0]))
                ),
                "positive_object_ids_recalled": sorted(
                    set(best).intersection(atom.positive_object_ids)
                ),
                "hard_negative_object_ids_recalled": sorted(
                    set(best).intersection(atom.hard_negative_object_ids)
                ),
            }
            route_index[(atom.atom_id, route_id)] = route_rows[route_id]
        atom_rows.append(
            {
                "atom_id": atom.atom_id,
                "request_id": request.request_id,
                "retrieval_need_set": need_set.as_dict(),
                "eligible_object_count": int(eligible.size),
                "rankable_object_count": int(rankable.size),
                "hard_filter_exclusions": exclusions,
                "projection_only_exclusions": projection_only,
                "routes": route_rows,
            }
        )

    expectation_rows: list[dict[str, Any]] = []
    expectations = contract.get("typed_route_proof_expectations") or []
    if not isinstance(expectations, list) or not expectations:
        raise ValueError("typed_route_proof_expectations_missing")
    for expectation in expectations:
        atom_id = str(expectation.get("atom_id") or "")
        route_id = str(expectation.get("route_id") or "")
        route = route_index.get((atom_id, route_id))
        if route is None:
            raise ValueError(
                f"typed_route_proof_route_missing:{atom_id}:{route_id}"
            )
        best = route["best_rank_by_object_id"]
        maximum_rank = int(expectation.get("maximum_rank") or per_need_limit)
        required = [str(value) for value in expectation.get("must_recall_object_ids") or ()]
        required_any = [
            str(value) for value in expectation.get("must_recall_any_object_ids") or ()
        ]
        excluded = [str(value) for value in expectation.get("must_exclude_object_ids") or ()]
        required_passed = all(
            object_id in best and int(best[object_id]) <= maximum_rank
            for object_id in required
        )
        any_passed = not required_any or any(
            object_id in best and int(best[object_id]) <= maximum_rank
            for object_id in required_any
        )
        exclusion_passed = all(object_id not in best for object_id in excluded)
        expectation_rows.append(
            {
                "atom_id": atom_id,
                "route_id": route_id,
                "business_meaning": str(expectation.get("business_meaning") or ""),
                "maximum_rank": maximum_rank,
                "must_recall_ranks": {
                    object_id: best.get(object_id) for object_id in required
                },
                "must_recall_any_ranks": {
                    object_id: best.get(object_id) for object_id in required_any
                },
                "must_exclude_presence": {
                    object_id: object_id in best for object_id in excluded
                },
                "passed": required_passed and any_passed and exclusion_passed,
            }
        )

    unsigned = {
        "schema_version": TYPED_ROUTE_PROOF_SCHEMA_VERSION,
        "status": "passed" if all(row["passed"] for row in expectation_rows) else "failed",
        "recorded_at": policy["recorded_at"],
        "experiment_id": f"{policy['experiment_id']}::TYPED-ROUTE-PROOF",
        "bound_inputs": {
            key: value
            for key, value in policy["bound_inputs"].items()
            if key.endswith("_ref") or "sha256" in key
        },
        "execution": {
            "network_calls": 0,
            "generation_model_calls": 0,
            "embedding_model_calls": 0,
            "reranker_model_calls": 0,
            "labels_joined_after_route_generation": True,
        },
        "expectations": expectation_rows,
        "atom_results": atom_rows,
        "summary": {
            "atom_count": len(atom_rows),
            "expectation_count": len(expectation_rows),
            "expectation_pass_count": sum(row["passed"] for row in expectation_rows),
            "typed_route_proof_passed": all(
                row["passed"] for row in expectation_rows
            ),
        },
        "authority": {
            "candidate_is_not_evidence": True,
            "numeric_fact_authority": False,
            "runtime_route_promotion_authorized": False,
            "s1_complete_claimed": False,
        },
    }
    return {**unsigned, "result_digest": canonical_digest(unsigned)}


def _compact(result: Mapping[str, Any], *, full_path: Path) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": result["status"],
        "recorded_at": result["recorded_at"],
        "experiment_id": result["experiment_id"],
        "storage": {
            "full_result_ref": _relative(full_path),
            "full_result_sha256": sha256_file(full_path),
            "full_result_digest": result["result_digest"],
        },
        "bound_inputs": result["bound_inputs"],
        "execution": result["execution"],
        "summary": result["summary"],
        "decision": result["decision"],
        "token_budget_basis": result["token_budget_basis"],
        "authority": result["authority"],
        "result_digest": result["result_digest"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the canonical S1 VS3 ranking vertical.")
    parser.add_argument(
        "--mode",
        choices=("canonical", "vs2-replay", "typed-route-proof"),
        default="canonical",
    )
    parser.add_argument(
        "--policy",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs3_candidate_ranking_policy_v1_0.json",
    )
    parser.add_argument(
        "--cache-root",
        default=".codex_runtime/fin_0_1_3_s1_vs3_candidate_ranking",
    )
    parser.add_argument(
        "--full-output-root",
        default="data/workbench_private/fin_0_1_3_s1_vs3_candidate_ranking/v1_0",
    )
    parser.add_argument(
        "--summary-output",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs3_candidate_ranking_result_v1_0.json",
    )
    parser.add_argument(
        "--vs2-replay-output",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs3_vs2_same_runtime_replay_result_v1_0.json",
    )
    parser.add_argument(
        "--typed-route-proof-output",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs3_typed_intent_route_proof_result_v1_0.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.mode == "typed-route-proof":
        proof = run_typed_route_proof(policy_path=_resolve(args.policy))
        _write_json(_resolve(args.typed_route_proof_output), proof)
        print(json.dumps(proof["summary"], ensure_ascii=False, indent=2))
        print(json.dumps(proof["expectations"], ensure_ascii=False, indent=2))
        return 0 if proof["summary"]["typed_route_proof_passed"] else 2
    if args.mode == "vs2-replay":
        replay = run_vs2_replay(
            policy_path=_resolve(args.policy), cache_root=_resolve(args.cache_root)
        )
        _write_json(_resolve(args.vs2_replay_output), replay)
        print(json.dumps(replay["summary"], ensure_ascii=False, indent=2))
        return 0
    result = run(
        policy_path=_resolve(args.policy), cache_root=_resolve(args.cache_root)
    )
    full_root = _resolve(args.full_output_root)
    full_path = full_root / f"full_result_{result['result_digest']}.json"
    _write_json(full_path, result)
    summary = _compact(result, full_path=full_path)
    _write_json(_resolve(args.summary_output), summary)
    print(json.dumps(summary["summary"], ensure_ascii=False, indent=2))
    print(json.dumps(summary["decision"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
