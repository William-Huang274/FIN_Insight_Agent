from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np  # noqa: E402

from retrieval.evidence_role import evaluate_evidence_role  # noqa: E402
from retrieval.query_plan import canonical_digest  # noqa: E402
from retrieval.ranking_comparison import (  # noqa: E402
    build_document_text,
    load_ranking_queries,
    rank_dense,
    rank_sparse,
)


POLICY_SCHEMA = "fin_ia_s1c_cross_encoder_role_shadow_policy_v1_0"
RESULT_SCHEMA = "fin_ia_s1c_cross_encoder_role_shadow_result_v1_0"
LEGACY_SLOT_MAP = {
    "customer_demand_and_deployment_validation": "demand_volume_quality",
    "issuer_results_and_management_commentary": "operating_performance",
    "regulatory_risk_and_financial_reconciliation": "regulatory_risk_and_financial_reconciliation",
    "supply_chain_capacity_and_counterevidence": "capacity_inputs_execution",
}


def _resolve(value: str | Path) -> Path:
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
                    raise ValueError("cross_encoder_record_not_object")
                rows.append(value)
    ids = [str(row.get("evidence_id") or "") for row in rows]
    if not all(ids) or len(ids) != len(set(ids)):
        raise ValueError("cross_encoder_record_identity_invalid")
    return rows


def _model_identity(model_dir: Path) -> dict[str, Any]:
    files = [model_dir / "config.json", model_dir / "model.safetensors"]
    if not all(path.is_file() for path in files):
        raise ValueError("cross_encoder_model_files_missing")
    rows = [
        {"name": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path)}
        for path in files
    ]
    body = {
        "model_id": "BAAI/bge-reranker-v2-m3",
        "local_directory_name": model_dir.name,
        "files": rows,
    }
    return {**body, "model_digest": canonical_digest(body)}


def _load_embedding_cache(
    *,
    cache_dir: Path,
    records: Sequence[Mapping[str, Any]],
    records_sha256: str,
) -> dict[str, np.ndarray]:
    manifest = _read_json(cache_dir / "manifest.json")
    if not (
        manifest.get("records_sha256") == records_sha256
        and manifest.get("record_count") == len(records)
        and manifest.get("normalized") is True
        and manifest.get("embedding_dimensions") == 1024
    ):
        raise ValueError("cross_encoder_bge_cache_contract_drift")
    matrix = np.load(cache_dir / "document_embeddings.npy", allow_pickle=False)
    if matrix.shape != (len(records), 1024):
        raise ValueError("cross_encoder_bge_cache_shape_drift")
    return {
        str(record["evidence_id"]): matrix[index]
        for index, record in enumerate(records)
    }


def _query_embeddings(
    queries: Sequence[Any], *, model_dir: Path, maximum_sequence_length: int
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
    matrix = model.encode(
        [query.query_text("dense_bge_m3") for query in queries],
        batch_size=8,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).astype(np.float32, copy=False)
    return {query.qrel_id: matrix[index] for index, query in enumerate(queries)}


def _load_cross_encoder(model_dir: Path, maximum_sequence_length: int) -> Any:
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        str(model_dir),
        local_files_only=True,
        dtype=torch.float16 if device.type == "cuda" else torch.float32,
    )
    model.to(device)
    model.eval()
    return tokenizer, model, device, maximum_sequence_length


def _score_pairs(
    runtime: Any,
    pairs: Sequence[tuple[str, str]],
    *,
    batch_size: int,
) -> list[float]:
    import torch

    tokenizer, model, device, maximum_sequence_length = runtime
    scores: list[float] = []
    for start in range(0, len(pairs), batch_size):
        batch = pairs[start : start + batch_size]
        encoded = tokenizer(
            [pair[0] for pair in batch],
            [pair[1] for pair in batch],
            padding=True,
            truncation=True,
            max_length=maximum_sequence_length,
            return_tensors="pt",
        )
        encoded = {key: value.to(device) for key, value in encoded.items()}
        with torch.inference_mode():
            logits = model(**encoded).logits.reshape(-1).float().cpu().tolist()
        scores.extend(float(value) for value in logits)
        if start and start % 100 == 0:
            print(f"scored_pairs={start}/{len(pairs)}", flush=True)
    return scores


def _role(
    record: Mapping[str, Any],
    *,
    slot_id: str,
    subject_ticker: str,
    evidence_owner_ticker: str,
    relationship_direction: str | None = None,
) -> dict[str, Any]:
    document = {
        **record,
        "document_text": str(
            record.get("document_text") or build_document_text(record)
        ),
    }
    return evaluate_evidence_role(
        document,
        slot_id=slot_id,
        subject_ticker=subject_ticker,
        evidence_owner_ticker=evidence_owner_ticker,
        relationship_direction=relationship_direction,
    ).as_dict()


def _target_rank(rows: Sequence[Mapping[str, Any]], targets: set[str]) -> int | None:
    for index, row in enumerate(rows, start=1):
        if str(row["source_record_id"]) in targets:
            return index
    return None


def _rank_metrics(rows: Sequence[Mapping[str, Any]], *, top_k: int) -> dict[str, Any]:
    ranks = [row.get("target_rank") for row in rows]
    matched = [rank for rank in ranks if isinstance(rank, int) and rank <= top_k]
    return {
        "query_count": len(rows),
        "target_recall_at_10": round(len(matched) / len(rows), 6) if rows else 0.0,
        "mrr": round(
            sum(1.0 / rank if isinstance(rank, int) else 0.0 for rank in ranks)
            / len(rows),
            6,
        )
        if rows
        else 0.0,
        "role_incompatible_top3": sum(
            candidate["role"]["compatibility"] == "incompatible"
            for row in rows
            for candidate in row["candidates"][:3]
        ),
        "role_abstain_top3": sum(
            candidate["role"]["compatibility"] == "abstain"
            for row in rows
            for candidate in row["candidates"][:3]
        ),
    }


def _primary_evaluation(
    *,
    records: Sequence[Mapping[str, Any]],
    queries: Sequence[Any],
    embedding_by_id: Mapping[str, np.ndarray],
    query_embeddings: Mapping[str, np.ndarray],
    score_lookup: Mapping[tuple[str, str], float],
    top_k: int,
    candidate_pool: int,
) -> dict[str, Any]:
    records_by_id = {str(row["evidence_id"]): row for row in records}
    route_rows: dict[str, list[dict[str, Any]]] = {
        "sparse_bm25": [],
        "cross_encoder": [],
        "cross_encoder_role_gated": [],
    }
    query_details: list[dict[str, Any]] = []
    ceiling_hits = 0
    for query in queries:
        sparse = rank_sparse(records, query)[:candidate_pool]
        dense = rank_dense(
            records,
            query,
            embedding_by_record_id=embedding_by_id,
            query_embedding=query_embeddings[query.qrel_id],
        )[:candidate_pool]
        union_ids = list(
            dict.fromkeys(
                str(row["source_record_id"]) for row in [*sparse, *dense]
            )
        )
        targets = set(query.target_current_source_record_ids)
        if targets.intersection(union_ids):
            ceiling_hits += 1
        role_slot = LEGACY_SLOT_MAP[query.evidence_slot_id]
        scored: list[dict[str, Any]] = []
        for record_id in union_ids:
            record = records_by_id[record_id]
            role = _role(
                record,
                slot_id=role_slot,
                subject_ticker=query.subject_ticker,
                evidence_owner_ticker=query.evidence_owner_ticker,
                relationship_direction=query.relationship_direction,
            )
            scored.append(
                {
                    "source_record_id": record_id,
                    "score": score_lookup[(query.qrel_id, record_id)],
                    "role": role,
                    "section": str(record.get("section") or ""),
                    "subsection": str(record.get("subsection") or ""),
                    "excerpt": str(record.get("text") or "")[:360],
                }
            )
        ce = sorted(scored, key=lambda row: (-row["score"], row["source_record_id"]))
        priority = {"compatible": 0, "abstain": 1, "incompatible": 2}
        gated = sorted(
            scored,
            key=lambda row: (
                priority[row["role"]["compatibility"]],
                -row["score"],
                row["source_record_id"],
            ),
        )
        sparse_projected = []
        for raw in sparse:
            record_id = str(raw["source_record_id"])
            record = records_by_id[record_id]
            sparse_projected.append(
                {
                    "source_record_id": record_id,
                    "score": round(float(raw["score"]), 8),
                    "role": _role(
                        record,
                        slot_id=role_slot,
                        subject_ticker=query.subject_ticker,
                        evidence_owner_ticker=query.evidence_owner_ticker,
                        relationship_direction=query.relationship_direction,
                    ),
                    "section": str(record.get("section") or ""),
                    "subsection": str(record.get("subsection") or ""),
                    "excerpt": str(record.get("text") or "")[:360],
                }
            )
        route_full = {
            "sparse_bm25": sparse_projected,
            "cross_encoder": ce,
            "cross_encoder_role_gated": gated,
        }
        route_candidates = {
            "sparse_bm25": sparse_projected[:top_k],
            "cross_encoder": ce[:top_k],
            "cross_encoder_role_gated": gated[:top_k],
        }
        detail = {
            "qrel_id": query.qrel_id,
            "case_key": query.case_key,
            "slot_id": query.evidence_slot_id,
            "role_slot_id": role_slot,
            "candidate_pool_count": len(union_ids),
            "target_in_candidate_pool": bool(targets.intersection(union_ids)),
            "routes": {},
        }
        for route_id, candidates in route_candidates.items():
            rank = _target_rank(route_full[route_id], targets)
            row = {
                "qrel_id": query.qrel_id,
                "target_rank": rank,
                "candidates": candidates,
            }
            route_rows[route_id].append(row)
            detail["routes"][route_id] = {
                "target_rank": rank,
                "top3": candidates[:3],
            }
        query_details.append(detail)
    return {
        "candidate_ceiling": {
            "query_count": len(queries),
            "target_in_union_pool_count": ceiling_hits,
            "target_in_union_pool_rate": round(ceiling_hits / len(queries), 6),
        },
        "routes": {
            route_id: _rank_metrics(rows, top_k=top_k)
            for route_id, rows in route_rows.items()
        },
        "queries": query_details,
    }


def _frozen_label_evaluation(
    eval_set: Mapping[str, Any],
    score_lookup: Mapping[tuple[str, str], float],
) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    details: list[dict[str, Any]] = []
    for split in ("primary_three_case", "holdout_unseen_case"):
        rows = [row for row in eval_set["queries"] if row["split"] == split]
        pair_total = 0
        pair_correct = 0
        positive_compatible = 0
        positive_total = 0
        negative_incompatible = 0
        negative_total = 0
        positive_abstain = 0
        negative_abstain = 0
        top1_positive = 0
        top3_positive = 0
        gated_top1_positive = 0
        gated_top3_positive = 0
        for row in rows:
            query_id = str(row["query_id"])
            slot_id = LEGACY_SLOT_MAP.get(str(row["slot_id"]), str(row["slot_id"]))
            documents: list[dict[str, Any]] = []
            positive_ids = {str(item["document_id"]) for item in row["positives"]}
            for label_kind, items in (
                ("positive", row["positives"]),
                ("hard_negative", row["hard_negatives"]),
            ):
                for item in items:
                    document_id = str(item["document_id"])
                    role = _role(
                        item,
                        slot_id=slot_id,
                        subject_ticker=str(row["case_key"]),
                        evidence_owner_ticker=str(item.get("ticker") or row["case_key"]),
                    )
                    documents.append(
                        {
                            "document_id": document_id,
                            "label_kind": label_kind,
                            "score": score_lookup[(query_id, document_id)],
                            "role": role,
                        }
                    )
                    if label_kind == "positive":
                        positive_total += 1
                        positive_compatible += role["compatibility"] == "compatible"
                        positive_abstain += role["compatibility"] == "abstain"
                    else:
                        negative_total += 1
                        negative_incompatible += role["compatibility"] == "incompatible"
                        negative_abstain += role["compatibility"] == "abstain"
            positives = [item for item in documents if item["label_kind"] == "positive"]
            negatives = [
                item for item in documents if item["label_kind"] == "hard_negative"
            ]
            for positive in positives:
                for negative in negatives:
                    pair_total += 1
                    pair_correct += positive["score"] > negative["score"]
            ranked = sorted(
                documents, key=lambda item: (-item["score"], item["document_id"])
            )
            priority = {"compatible": 0, "abstain": 1, "incompatible": 2}
            gated = sorted(
                documents,
                key=lambda item: (
                    priority[item["role"]["compatibility"]],
                    -item["score"],
                    item["document_id"],
                ),
            )
            top1_positive += bool(ranked and ranked[0]["document_id"] in positive_ids)
            top3_positive += bool(
                positive_ids.intersection(item["document_id"] for item in ranked[:3])
            )
            gated_top1_positive += bool(
                gated and gated[0]["document_id"] in positive_ids
            )
            gated_top3_positive += bool(
                positive_ids.intersection(item["document_id"] for item in gated[:3])
            )
            details.append(
                {
                    "query_id": query_id,
                    "split": split,
                    "cross_encoder_top3": ranked[:3],
                    "role_gated_top3": gated[:3],
                }
            )
        count = len(rows)
        summaries[split] = {
            "query_count": count,
            "pairwise_comparisons": pair_total,
            "positive_over_hard_negative_pairwise_accuracy": round(
                pair_correct / pair_total, 6
            )
            if pair_total
            else 0.0,
            "cross_encoder_top1_positive_rate": round(top1_positive / count, 6)
            if count
            else 0.0,
            "cross_encoder_top3_positive_rate": round(top3_positive / count, 6)
            if count
            else 0.0,
            "role_gated_top1_positive_rate": round(
                gated_top1_positive / count, 6
            )
            if count
            else 0.0,
            "role_gated_top3_positive_rate": round(
                gated_top3_positive / count, 6
            )
            if count
            else 0.0,
            "positive_role_compatibility_rate": round(
                positive_compatible / positive_total, 6
            )
            if positive_total
            else 0.0,
            "positive_role_abstain_rate": round(positive_abstain / positive_total, 6)
            if positive_total
            else 0.0,
            "negative_role_incompatible_rate": round(
                negative_incompatible / negative_total, 6
            )
            if negative_total
            else 0.0,
            "negative_role_abstain_rate": round(negative_abstain / negative_total, 6)
            if negative_total
            else 0.0,
        }
    return {"splits": summaries, "queries": details}


def run(
    *,
    policy_path: Path,
    qrel_path: Path,
    eval_set_path: Path,
    records_path: Path,
    bge_model_dir: Path,
    bge_cache_dir: Path,
    cross_encoder_model_dir: Path,
) -> dict[str, Any]:
    policy = _read_json(policy_path)
    if policy.get("schema_version") != POLICY_SCHEMA:
        raise ValueError("cross_encoder_shadow_policy_invalid")
    qrels = _read_json(qrel_path)
    eval_set = _read_json(eval_set_path)
    if (
        _sha256(qrel_path) != policy["bound_inputs"]["qrels_sha256"]
        or eval_set.get("eval_set_digest")
        != policy["bound_inputs"]["eval_set_digest"]
        or _sha256(records_path) != policy["bound_inputs"]["records_sha256"]
    ):
        raise ValueError("cross_encoder_shadow_bound_input_drift")
    records = _records(records_path)
    queries = load_ranking_queries(qrels)
    records_sha = _sha256(records_path)
    embedding_by_id = _load_embedding_cache(
        cache_dir=bge_cache_dir,
        records=records,
        records_sha256=records_sha,
    )
    query_embeddings = _query_embeddings(
        queries, model_dir=bge_model_dir, maximum_sequence_length=2048
    )
    candidate_pool = int(policy["candidate_ceiling"]["per_route_top_k"])
    records_by_id = {str(row["evidence_id"]): row for row in records}
    candidate_ids_by_query: dict[str, list[str]] = {}
    for query in queries:
        sparse = rank_sparse(records, query)[:candidate_pool]
        dense = rank_dense(
            records,
            query,
            embedding_by_record_id=embedding_by_id,
            query_embedding=query_embeddings[query.qrel_id],
        )[:candidate_pool]
        candidate_ids_by_query[query.qrel_id] = list(
            dict.fromkeys(str(row["source_record_id"]) for row in [*sparse, *dense])
        )

    pair_payloads: dict[tuple[str, str], tuple[str, str]] = {}
    query_text_by_id = {
        query.qrel_id: query.query_text("dense_bge_m3") for query in queries
    }
    for query_id, record_ids in candidate_ids_by_query.items():
        for record_id in record_ids:
            pair_payloads[(query_id, record_id)] = (
                query_text_by_id[query_id],
                build_document_text(records_by_id[record_id]),
            )
    for row in eval_set["queries"]:
        query_id = str(row["query_id"])
        for item in [*row["positives"], *row["hard_negatives"]]:
            pair_payloads[(query_id, str(item["document_id"]))] = (
                str(row["query_text"]),
                str(item["document_text"]),
            )

    model_identity = _model_identity(cross_encoder_model_dir)
    import torch

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    runtime = _load_cross_encoder(
        cross_encoder_model_dir,
        int(policy["model"]["maximum_sequence_length"]),
    )
    started = time.perf_counter()
    keys = list(pair_payloads)
    scores = _score_pairs(
        runtime,
        [pair_payloads[key] for key in keys],
        batch_size=int(policy["model"]["batch_size"]),
    )
    elapsed = time.perf_counter() - started
    score_lookup = {key: score for key, score in zip(keys, scores)}
    peak_gpu_memory = (
        int(torch.cuda.max_memory_allocated()) if torch.cuda.is_available() else 0
    )
    primary = _primary_evaluation(
        records=records,
        queries=queries,
        embedding_by_id=embedding_by_id,
        query_embeddings=query_embeddings,
        score_lookup=score_lookup,
        top_k=int(policy["evaluation"]["top_k"]),
        candidate_pool=candidate_pool,
    )
    frozen = _frozen_label_evaluation(eval_set, score_lookup)
    unsigned = {
        "schema_version": RESULT_SCHEMA,
        "status": "cross_encoder_and_evidence_role_shadow_complete",
        "recorded_at": "2026-08-12",
        "experiment_id": str(policy["experiment_id"]),
        "bound_inputs": {
            "policy_ref": policy_path.relative_to(ROOT).as_posix(),
            "policy_sha256": _sha256(policy_path),
            "qrels_ref": qrel_path.relative_to(ROOT).as_posix(),
            "qrels_sha256": _sha256(qrel_path),
            "qrel_manifest_digest": str(qrels["qrel_manifest_digest"]),
            "eval_set_ref": eval_set_path.relative_to(ROOT).as_posix(),
            "eval_set_sha256": _sha256(eval_set_path),
            "eval_set_digest": str(eval_set["eval_set_digest"]),
            "records_ref": records_path.relative_to(ROOT).as_posix(),
            "records_sha256": records_sha,
        },
        "execution": {
            "model_identity": model_identity,
            "candidate_pool_per_sparse_and_dense_route": candidate_pool,
            "scored_pair_count": len(keys),
            "maximum_sequence_length": int(policy["model"]["maximum_sequence_length"]),
            "batch_size": int(policy["model"]["batch_size"]),
            "device": str(runtime[2]),
            "elapsed_seconds": round(elapsed, 3),
            "pairs_per_second": round(len(keys) / elapsed, 3),
            "peak_gpu_memory_bytes": peak_gpu_memory,
            "network_calls_during_evaluation": 0,
            "training_steps": 0,
            "generation_model_calls": 0,
        },
        "primary_candidate_ranking": primary,
        "frozen_label_evaluation": frozen,
        "authority": {
            "candidate_is_not_evidence": True,
            "evidence_promoted": False,
            "runtime_route_promoted": False,
            "fine_tuning_authorized": False,
            "s1_complete_claimed": False,
        },
        "known_boundary": (
            "This is an offline shadow evaluation on a frozen current object store and "
            "previously reviewed holdouts. Cross-encoder scores and deterministic role "
            "labels cannot promote Evidence. Results decide whether further model or "
            "role work is justified; they do not close S1 or authorize S1-D."
        ),
    }
    return {**unsigned, "result_digest": canonical_digest(unsigned)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run bounded BGE reranker and Evidence Role shadow evaluation."
    )
    parser.add_argument(
        "--policy",
        default="configs/retrieval/fin_ia_0_1_3_s1c_cross_encoder_role_shadow_policy_v1_1.json",
    )
    parser.add_argument(
        "--qrels",
        default="configs/retrieval/fin_ia_0_1_3_s1c_requalified_qrels_v1_1.json",
    )
    parser.add_argument(
        "--eval-set",
        default="configs/retrieval/fin_ia_0_1_3_s1c_financial_role_eval_set_v1_1.json",
    )
    parser.add_argument(
        "--records",
        default="data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/v1/records.jsonl",
    )
    parser.add_argument("--bge-model", required=True)
    parser.add_argument(
        "--bge-cache",
        default="data/workbench_private/fin_0_1_3_s1c_ranking_comparison/bge_m3_cache_v1",
    )
    parser.add_argument("--cross-encoder-model", required=True)
    parser.add_argument(
        "--output",
        default="configs/retrieval/fin_ia_0_1_3_s1c_cross_encoder_role_shadow_result_v1_1.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run(
        policy_path=_resolve(args.policy),
        qrel_path=_resolve(args.qrels),
        eval_set_path=_resolve(args.eval_set),
        records_path=_resolve(args.records),
        bge_model_dir=_resolve(args.bge_model),
        bge_cache_dir=_resolve(args.bge_cache),
        cross_encoder_model_dir=_resolve(args.cross_encoder_model),
    )
    output = _resolve(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(output)
    print(
        json.dumps(
            {
                "status": result["status"],
                "execution": result["execution"],
                "primary_routes": result["primary_candidate_ranking"]["routes"],
                "frozen_splits": result["frozen_label_evaluation"]["splits"],
                "result_digest": result["result_digest"],
                "output": output.relative_to(ROOT).as_posix(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
