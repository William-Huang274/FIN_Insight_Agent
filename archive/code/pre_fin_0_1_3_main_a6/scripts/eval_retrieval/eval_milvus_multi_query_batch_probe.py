"""Probe Milvus multi-query-vector batch search on an existing collection.

This script does not rebuild vectors and does not change the agent runtime. It
compares sequential per-probe searches with one batched Milvus search over the
same query embeddings, then reports whether a GPU index is likely to have room
to help once research questions are decomposed into multiple semantic probes.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASES_PATH = REPO_ROOT / "tests" / "fixtures" / "fin_agent_retrieval_ab_cases_v0_1.jsonl"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "eval" / "sec_cases" / "outputs" / "milvus_multi_query_batch_probe"
DEFAULT_VECTOR_KINDS = [
    "paraphrase_context",
    "relationship_context",
    "narrative_chunk",
    "metric_row",
    "table_row",
    "table_chunk",
]
SCHEMA_VERSION = "fin_agent_milvus_multi_query_batch_probe_v0.1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Milvus multi-query-vector batch probe.")
    parser.add_argument("--cases-path", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--milvus-uri", default=os.environ.get("MILVUS_URI") or os.environ.get("MILVUS_DB_PATH") or "")
    parser.add_argument("--collection-name", default=os.environ.get("MILVUS_COLLECTION_NAME", ""))
    parser.add_argument("--embedding-model", default=os.environ.get("MILVUS_EMBEDDING_MODEL") or os.environ.get("BGE_EMBEDDING_MODEL") or "")
    parser.add_argument("--device", default=os.environ.get("MILVUS_EMBEDDING_DEVICE") or os.environ.get("BGE_DEVICE") or "cuda")
    parser.add_argument("--embedding-batch-size", type=int, default=int(os.environ.get("MILVUS_PROBE_EMBEDDING_BATCH_SIZE", "32")))
    parser.add_argument("--embedding-max-seq-length", type=int, default=int(os.environ.get("MILVUS_PROBE_EMBEDDING_MAX_SEQ_LENGTH", "512")))
    parser.add_argument("--top-k", type=int, default=40)
    parser.add_argument("--per-probe-top-k", type=int, default=40)
    parser.add_argument("--max-probes-per-case", type=int, default=8)
    parser.add_argument("--vector-kinds", default=",".join(DEFAULT_VECTOR_KINDS))
    parser.add_argument("--search-rounds", type=int, default=3)
    parser.add_argument("--warmup-rounds", type=int, default=1)
    parser.add_argument("--query-expansion", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not str(args.milvus_uri).strip():
        raise ValueError("--milvus-uri or MILVUS_URI/MILVUS_DB_PATH is required")
    if not str(args.collection_name).strip():
        raise ValueError("--collection-name or MILVUS_COLLECTION_NAME is required")
    if not str(args.embedding_model).strip():
        raise ValueError("--embedding-model or MILVUS_EMBEDDING_MODEL is required")

    run_id = args.run_id or _default_run_id()
    run_dir = args.output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    cases = _load_cases(args.cases_path)
    if args.case_id:
        wanted = {str(item) for item in args.case_id}
        cases = [case for case in cases if str(case.get("case_id") or "") in wanted]
    if not cases:
        raise ValueError(f"No cases selected from {args.cases_path}")

    _set_torch_fast_env()
    from pymilvus import MilvusClient
    from sentence_transformers import SentenceTransformer
    import torch

    device = _resolve_device(str(args.device), torch)
    model = SentenceTransformer(str(args.embedding_model), device=device)
    if int(args.embedding_max_seq_length or 0) > 0:
        model.max_seq_length = int(args.embedding_max_seq_length)
    client = MilvusClient(uri=str(args.milvus_uri))
    _load_collection_for_search(client, str(args.collection_name))

    selected_vector_kinds = _string_list(args.vector_kinds) or list(DEFAULT_VECTOR_KINDS)
    resource_before = _resource_snapshot(torch)
    results: list[dict[str, Any]] = []
    started = time.perf_counter()
    try:
        for case in cases:
            print(json.dumps({"case_progress": "start", "case_id": case.get("case_id")}, ensure_ascii=False), file=sys.stderr, flush=True)
            result = _run_case(
                case=case,
                client=client,
                collection_name=str(args.collection_name),
                model=model,
                vector_kinds=selected_vector_kinds,
                embedding_batch_size=max(1, int(args.embedding_batch_size)),
                top_k=max(1, int(args.top_k)),
                per_probe_top_k=max(1, int(args.per_probe_top_k)),
                max_probes=max(1, int(args.max_probes_per_case)),
                search_rounds=max(1, int(args.search_rounds)),
                warmup_rounds=max(0, int(args.warmup_rounds)),
                query_expansion=bool(args.query_expansion),
            )
            results.append(result)
            print(
                json.dumps(
                    {
                        "case_progress": "done",
                        "case_id": case.get("case_id"),
                        "probe_count": result["probe_count"],
                        "batch_search_ms_median": result["timings"]["batch_search_ms"]["median"],
                        "sequential_search_ms_median": result["timings"]["sequential_search_ms"]["median"],
                    },
                    ensure_ascii=False,
                ),
                file=sys.stderr,
                flush=True,
            )
    finally:
        _close_client(client)

    resource_after = _resource_snapshot(torch)
    summary = _summarize(
        results,
        run_id=run_id,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
        args=args,
        device=device,
        vector_kinds=selected_vector_kinds,
        resource_before=resource_before,
        resource_after=resource_after,
    )
    (run_dir / "case_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["gate_status"] == "pass" else 2


def _run_case(
    *,
    case: Mapping[str, Any],
    client: Any,
    collection_name: str,
    model: Any,
    vector_kinds: list[str],
    embedding_batch_size: int,
    top_k: int,
    per_probe_top_k: int,
    max_probes: int,
    search_rounds: int,
    warmup_rounds: int,
    query_expansion: bool,
) -> dict[str, Any]:
    probes = _case_probes(case, max_probes=max_probes, query_expansion=query_expansion)
    expr = _milvus_expr(case, vector_kinds=vector_kinds)
    output_fields = _output_fields()

    encode_sequential_samples: list[int] = []
    for _ in range(warmup_rounds):
        _encode_batch(model, probes, batch_size=embedding_batch_size)
    for _ in range(search_rounds):
        start = time.perf_counter()
        for probe in probes:
            _encode_batch(model, [probe], batch_size=1)
        encode_sequential_samples.append(_elapsed_ms(start))

    encode_batch_samples: list[int] = []
    embeddings = _encode_batch(model, probes, batch_size=embedding_batch_size)
    for _ in range(search_rounds):
        start = time.perf_counter()
        embeddings = _encode_batch(model, probes, batch_size=embedding_batch_size)
        encode_batch_samples.append(_elapsed_ms(start))

    for _ in range(warmup_rounds):
        client.search(
            collection_name=collection_name,
            data=[embeddings[0]],
            anns_field="embedding",
            limit=max(1, int(per_probe_top_k)),
            filter=expr,
            output_fields=output_fields,
        )

    sequential_search_samples: list[int] = []
    sequential_hits: list[dict[str, Any]] = []
    for _ in range(search_rounds):
        start = time.perf_counter()
        hit_lists = []
        for embedding in embeddings:
            hit_lists.append(
                client.search(
                    collection_name=collection_name,
                    data=[embedding],
                    anns_field="embedding",
                    limit=max(1, int(per_probe_top_k)),
                    filter=expr,
                    output_fields=output_fields,
                )[0]
            )
        sequential_search_samples.append(_elapsed_ms(start))
        sequential_hits = _merge_query_hit_lists(hit_lists, top_k=top_k)

    batch_search_samples: list[int] = []
    batch_hits: list[dict[str, Any]] = []
    for _ in range(search_rounds):
        start = time.perf_counter()
        hit_lists = client.search(
            collection_name=collection_name,
            data=embeddings,
            anns_field="embedding",
            limit=max(1, int(per_probe_top_k)),
            filter=expr,
            output_fields=output_fields,
        )
        batch_search_samples.append(_elapsed_ms(start))
        batch_hits = _merge_query_hit_lists(hit_lists, top_k=top_k)

    sequential_eval = _evaluate_hits(sequential_hits, case=case, top_k=top_k)
    batch_eval = _evaluate_hits(batch_hits, case=case, top_k=top_k)
    timings = {
        "sequential_encode_ms": _sample_stats(encode_sequential_samples),
        "batch_encode_ms": _sample_stats(encode_batch_samples),
        "sequential_search_ms": _sample_stats(sequential_search_samples),
        "batch_search_ms": _sample_stats(batch_search_samples),
    }
    return {
        "case_id": case.get("case_id"),
        "category": case.get("category"),
        "query": case.get("query") or case.get("prompt"),
        "probes": probes,
        "probe_count": len(probes),
        "filter_expr": expr,
        "timings": timings,
        "speedups": {
            "encode_batch_vs_sequential": _ratio(timings["sequential_encode_ms"]["median"], timings["batch_encode_ms"]["median"]),
            "search_batch_vs_sequential": _ratio(timings["sequential_search_ms"]["median"], timings["batch_search_ms"]["median"]),
        },
        "sequential": sequential_eval,
        "batch": batch_eval,
        "gate_status": "pass" if _case_passes(case, batch_eval) else "warn",
    }


def _case_probes(case: Mapping[str, Any], *, max_probes: int, query_expansion: bool) -> list[str]:
    base = str(case.get("query") or case.get("prompt") or "").strip()
    probes = [base] if base else []
    if query_expansion:
        probes.extend(_generic_expanded_queries(case))
    probes.extend(_investment_lens_queries(case))
    return _dedupe_strings([probe for probe in probes if probe])[:max(1, int(max_probes))]


def _generic_expanded_queries(case: Mapping[str, Any]) -> list[str]:
    query = str(case.get("query") or case.get("prompt") or "").strip()
    tickers = " ".join(str(item).upper() for item in case.get("tickers") or case.get("search_scope_tickers") or [])
    terms = " ".join(str(item) for item in case.get("terms_any") or case.get("metric_terms_any") or case.get("metric_families") or [])
    category = str(case.get("category") or "")
    probes = []
    if tickers or terms:
        probes.append(" ".join(part for part in (tickers, terms, query) if part))
    if category in {"relationship", "scope_decision"}:
        probes.append(" ".join(part for part in (tickers, "economic linkage upstream downstream customer supplier supply chain", terms) if part))
    if category in {"paraphrase", "scope_decision"}:
        probes.append(" ".join(part for part in (tickers, "plain language SEC filing evidence canonical financial terms", terms) if part))
    return probes


def _investment_lens_queries(case: Mapping[str, Any]) -> list[str]:
    text = " ".join(
        [
            str(case.get("query") or ""),
            str(case.get("prompt") or ""),
            " ".join(str(item) for item in case.get("tickers") or []),
            " ".join(str(item) for item in case.get("search_scope_tickers") or []),
            " ".join(str(item) for item in case.get("terms_any") or []),
            " ".join(str(item) for item in case.get("metric_families") or []),
        ]
    ).lower()
    if not any(term in text for term in ("nvda", "nvidia", "ai", "accelerated", "cloud", "hbm", "data center", "infrastructure")):
        return []
    tickers = " ".join(str(item).upper() for item in case.get("tickers") or case.get("search_scope_tickers") or ["NVDA"])
    return [
        f"{tickers} company fundamentals revenue gross margin operating margin cash flow data center",
        f"{tickers} cloud capex demand hyperscaler infrastructure spending AI accelerated computing",
        f"{tickers} memory HBM foundry semiconductor equipment supply chain capacity constraints",
        f"{tickers} server networking power downstream data center infrastructure demand transmission",
        f"{tickers} export control China restrictions customer concentration risk counterevidence",
        f"{tickers} market reaction valuation investor expectations AI infrastructure growth durability",
    ]


def _encode_batch(model: Any, probes: list[str], *, batch_size: int) -> list[list[float]]:
    embeddings = model.encode(
        probes,
        batch_size=max(1, int(batch_size)),
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return [[float(item) for item in embedding.tolist()] for embedding in embeddings]


def _merge_query_hit_lists(hit_lists: Iterable[Iterable[Any]], *, top_k: int) -> list[dict[str, Any]]:
    scores: dict[str, float] = defaultdict(float)
    support: dict[str, dict[str, Any]] = {}
    for query_index, hits in enumerate(hit_lists):
        query_weight = 1.0 if query_index == 0 else 0.85
        for rank, hit in enumerate(hits, start=1):
            entity = dict(hit.get("entity") or {}) if isinstance(hit, Mapping) else {}
            evidence_id = str(entity.get("evidence_id") or "").strip()
            if not evidence_id:
                continue
            scores[evidence_id] += query_weight * _semantic_hit_weight(entity) / (60.0 + rank)
            item = support.setdefault(evidence_id, dict(entity))
            if rank < int(item.get("best_raw_rank") or 999999):
                item.update(entity)
                item["best_raw_rank"] = rank
            item.setdefault("matched_query_indices", [])
            item["matched_query_indices"].append(query_index)
            item.setdefault("vector_kinds", [])
            if str(entity.get("vector_kind") or ""):
                item["vector_kinds"].append(str(entity.get("vector_kind") or ""))
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[: max(1, int(top_k))]
    out: list[dict[str, Any]] = []
    for rank, (evidence_id, score) in enumerate(ranked, start=1):
        item = dict(support[evidence_id])
        item["rank"] = rank
        item["score"] = score
        item["evidence_id"] = evidence_id
        item["matched_query_indices"] = sorted(set(int(idx) for idx in item.get("matched_query_indices") or []))
        item["vector_kinds"] = sorted({str(kind) for kind in item.get("vector_kinds") or [] if str(kind)})
        out.append(item)
    return out


def _semantic_hit_weight(entity: Mapping[str, Any]) -> float:
    kind = str(entity.get("vector_kind") or "")
    role = str(entity.get("vector_role") or "")
    scope = str(entity.get("semantic_scope") or "")
    weight = 1.0
    if kind in {"relationship_context", "paraphrase_context", "metric_row", "table_row"}:
        weight += 0.12
    if role in {"economic_linkage_context", "plain_language_context"}:
        weight += 0.08
    if scope in {"relationship", "paraphrase"}:
        weight += 0.06
    return weight


def _evaluate_hits(hits: list[dict[str, Any]], *, case: Mapping[str, Any], top_k: int) -> dict[str, Any]:
    rows = hits[: max(1, int(top_k))]
    terms = [str(item).lower() for item in case.get("terms_any") or [] if str(item).strip()]
    tickers = {str(item).upper() for item in case.get("tickers") or case.get("search_scope_tickers") or []}
    row_tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if str(row.get("ticker") or "").upper() in tickers})
    usable = [row for row in rows if _row_has_any_term(row, terms)]
    return {
        "row_count": len(rows),
        "usable_evidence_rows": len(usable),
        "ticker_coverage": row_tickers,
        "ticker_coverage_count": len(row_tickers),
        "vector_kind_counts": _count_by(rows, "vector_kind", fallback_key="vector_kinds"),
        "item_code_counts": _count_by(rows, "item_code"),
        "source_tier_counts": _count_by(rows, "source_tier"),
        "matched_query_count": len({idx for row in rows for idx in row.get("matched_query_indices") or []}),
        "top_ids": [row.get("evidence_id") for row in rows[:5]],
        "top_previews": [_preview(str(row.get("preview") or ""), 180) for row in rows[:3]],
    }


def _case_passes(case: Mapping[str, Any], evaluation: Mapping[str, Any]) -> bool:
    min_rows = int(case.get("min_usable_evidence_rows") or 1)
    min_tickers = int(case.get("min_ticker_coverage") or min(1, len(case.get("tickers") or case.get("search_scope_tickers") or [])))
    return int(evaluation.get("row_count") or 0) > 0 and int(evaluation.get("ticker_coverage_count") or 0) >= min_tickers and int(evaluation.get("usable_evidence_rows") or 0) >= min_rows


def _milvus_expr(case: Mapping[str, Any], *, vector_kinds: list[str]) -> str:
    clauses = []
    tickers = [str(item).upper() for item in case.get("tickers") or case.get("search_scope_tickers") or [] if str(item).strip()]
    years = [int(item) for item in case.get("years") or [] if str(item).isdigit()]
    forms = [_normalize_form_type(item) for item in case.get("filing_types") or [] if str(item).strip()]
    source_tiers = [str(item) for item in case.get("source_tiers") or [] if str(item).strip()]
    if tickers:
        clauses.append(_milvus_in_clause("ticker", tickers))
    if years:
        clauses.append("fiscal_year in [" + ", ".join(str(year) for year in years) + "]")
    if forms:
        clauses.append(_milvus_in_clause("form_type", forms))
    if source_tiers:
        clauses.append(_milvus_in_clause("source_tier", source_tiers))
    if vector_kinds:
        clauses.append(_milvus_in_clause("vector_kind", vector_kinds))
    return " and ".join(clauses)


def _output_fields() -> list[str]:
    return [
        "vector_id",
        "evidence_id",
        "ticker",
        "fiscal_year",
        "form_type",
        "source_tier",
        "item_code",
        "category_slug",
        "period_type",
        "contains_table",
        "vector_kind",
        "vector_role",
        "semantic_scope",
        "intent_tags",
        "relationship_role",
        "object_type",
        "preview",
    ]


def _load_cases(path: Path) -> list[dict[str, Any]]:
    cases = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                cases.append(json.loads(line))
    return cases


def _summarize(
    results: list[dict[str, Any]],
    *,
    run_id: str,
    elapsed_ms: int,
    args: argparse.Namespace,
    device: str,
    vector_kinds: list[str],
    resource_before: dict[str, Any],
    resource_after: dict[str, Any],
) -> dict[str, Any]:
    search_speedups = [float((row.get("speedups") or {}).get("search_batch_vs_sequential") or 0.0) for row in results]
    encode_speedups = [float((row.get("speedups") or {}).get("encode_batch_vs_sequential") or 0.0) for row in results]
    batch_search = [int(((row.get("timings") or {}).get("batch_search_ms") or {}).get("median") or 0) for row in results]
    seq_search = [int(((row.get("timings") or {}).get("sequential_search_ms") or {}).get("median") or 0) for row in results]
    probe_counts = [int(row.get("probe_count") or 0) for row in results]
    pass_count = sum(1 for row in results if row.get("gate_status") == "pass")
    gpu_index_room = any(count >= 4 for count in probe_counts) and (_mean(search_speedups) >= 1.15 or _mean(batch_search) >= 250)
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "gate_status": "pass" if pass_count == len(results) else "warn",
        "case_count": len(results),
        "pass_count": pass_count,
        "elapsed_ms": elapsed_ms,
        "milvus": {
            "uri": str(args.milvus_uri),
            "collection_name": str(args.collection_name),
            "vector_kinds": vector_kinds,
            "embedding_model": str(args.embedding_model),
            "device": device,
        },
        "aggregate": {
            "avg_probe_count": _mean(probe_counts),
            "avg_search_batch_vs_sequential_speedup": _mean(search_speedups),
            "avg_encode_batch_vs_sequential_speedup": _mean(encode_speedups),
            "avg_sequential_search_ms": _mean(seq_search),
            "avg_batch_search_ms": _mean(batch_search),
            "gpu_index_room_signal": gpu_index_room,
        },
        "resources": {"before": resource_before, "after": resource_after},
        "case_results": [
            {
                "case_id": row.get("case_id"),
                "probe_count": row.get("probe_count"),
                "gate_status": row.get("gate_status"),
                "search_batch_vs_sequential": (row.get("speedups") or {}).get("search_batch_vs_sequential"),
                "batch_ticker_coverage_count": (row.get("batch") or {}).get("ticker_coverage_count"),
                "batch_vector_kind_counts": (row.get("batch") or {}).get("vector_kind_counts"),
            }
            for row in results
        ],
    }


def _resource_snapshot(torch_module: Any) -> dict[str, Any]:
    snapshot: dict[str, Any] = {"time_utc": datetime.now(timezone.utc).isoformat()}
    try:
        if torch_module.cuda.is_available():
            snapshot["torch_cuda_memory_allocated_mb"] = round(torch_module.cuda.memory_allocated() / 1024 / 1024, 2)
            snapshot["torch_cuda_max_memory_allocated_mb"] = round(torch_module.cuda.max_memory_allocated() / 1024 / 1024, 2)
    except Exception as exc:  # noqa: BLE001
        snapshot["torch_cuda_error"] = f"{type(exc).__name__}:{exc}"[:300]
    try:
        proc = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total,power.draw",
                "--format=csv,noheader,nounits",
            ],
            check=False,
            text=True,
            capture_output=True,
            timeout=5,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            first = [part.strip() for part in proc.stdout.strip().splitlines()[0].split(",")]
            snapshot["nvidia_smi"] = {
                "gpu_util_pct": _safe_float(first[0]) if len(first) > 0 else None,
                "memory_used_mb": _safe_float(first[1]) if len(first) > 1 else None,
                "memory_total_mb": _safe_float(first[2]) if len(first) > 2 else None,
                "power_w": _safe_float(first[3]) if len(first) > 3 else None,
            }
    except Exception as exc:  # noqa: BLE001
        snapshot["nvidia_smi_error"] = f"{type(exc).__name__}:{exc}"[:300]
    return snapshot


def _set_torch_fast_env() -> None:
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "true")
    os.environ.setdefault("OMP_NUM_THREADS", str(os.cpu_count() or 8))


def _resolve_device(device: str, torch_module: Any) -> str:
    requested = str(device or "").strip().lower()
    if requested in {"cuda", "gpu"} and torch_module.cuda.is_available():
        try:
            torch_module.backends.cuda.matmul.allow_tf32 = True
            torch_module.set_float32_matmul_precision("high")
        except Exception:
            pass
        return "cuda"
    if requested not in {"", "auto", "default", "cuda", "gpu"}:
        return requested
    return "cuda" if torch_module.cuda.is_available() else "cpu"


def _load_collection_for_search(client: Any, collection_name: str) -> None:
    load = getattr(client, "load_collection", None)
    if not callable(load):
        return
    try:
        load(collection_name=collection_name)
    except TypeError:
        load(collection_name)


def _close_client(client: Any) -> None:
    for name in ("close", "disconnect"):
        method = getattr(client, name, None)
        if callable(method):
            try:
                method()
            except Exception:
                pass
            return


def _normalize_form_type(value: Any) -> str:
    text = str(value or "").upper().replace(" ", "")
    return text.replace("10K", "10-K").replace("10Q", "10-Q").replace("8K", "8-K")


def _milvus_in_clause(field: str, values: Iterable[str]) -> str:
    quoted = ", ".join(json.dumps(str(value), ensure_ascii=False) for value in values)
    return f"{field} in [{quoted}]"


def _count_by(rows: list[dict[str, Any]], key: str, *, fallback_key: str = "") -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        values = _string_list(row.get(key))
        if not values and fallback_key:
            values = _string_list(row.get(fallback_key))
        for value in values:
            counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = value.replace("|", ",").split(",")
        return [part.strip() for part in parts if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _row_has_any_term(row: Mapping[str, Any], terms: list[str]) -> bool:
    if not terms:
        return bool(str(row.get("preview") or "").strip())
    text = str(row.get("preview") or "").lower()
    return any(term in text for term in terms)


def _sample_stats(values: list[int]) -> dict[str, Any]:
    if not values:
        return {"samples": [], "min": 0, "median": 0, "max": 0, "mean": 0.0}
    ordered = sorted(int(value) for value in values)
    mid = len(ordered) // 2
    median = ordered[mid] if len(ordered) % 2 else int((ordered[mid - 1] + ordered[mid]) / 2)
    return {"samples": values, "min": ordered[0], "median": median, "max": ordered[-1], "mean": round(sum(ordered) / len(ordered), 3)}


def _ratio(numerator: Any, denominator: Any) -> float:
    den = float(denominator or 0)
    if den <= 0:
        return 0.0
    return round(float(numerator or 0) / den, 4)


def _mean(values: list[Any]) -> float:
    nums = [float(value) for value in values if value is not None]
    return round(sum(nums) / len(nums), 4) if nums else 0.0


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def _preview(text: str, limit: int = 220) -> str:
    normalized = " ".join(str(text or "").split())
    return normalized[:limit]


def _dedupe_strings(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = " ".join(str(value).lower().split())
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(str(value).strip())
    return out


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _default_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_milvus_multi_query_batch_probe_%H%M%S")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
