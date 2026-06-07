"""Run retrieval-only BM25/ObjectBM25 vs Milvus semantic A/B diagnostics.

This script does not call an LLM and does not connect Milvus to the agent
runtime. It builds a small Milvus Lite collection for the requested cases,
then compares lexical, structured-object, semantic, and hybrid RRF recall.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVIDENCE_PATH = Path(
    "Z:/FIN_Insight_Agent_artifacts/evidence_objects/"
    "sector_depth_full238_us_v0_5_mixed_with_8k_evidence_fy2023_2027.jsonl"
)
DEFAULT_BM25_INDEX_DIR = Path(
    "Z:/FIN_Insight_Agent_artifacts/indexes/bm25/"
    "sector_depth_full238_us_v0_5_mixed_with_8k_fy2023_2027"
)
DEFAULT_OBJECT_BM25_INDEX_DIR = Path(
    "Z:/FIN_Insight_Agent_artifacts/indexes/bm25/"
    "sector_depth_full238_us_v0_5_mixed_with_8k_fy2023_2027_objects"
)
DEFAULT_CASES_PATH = REPO_ROOT / "tests" / "fixtures" / "fin_agent_retrieval_ab_cases_v0_1.jsonl"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "eval" / "sec_cases" / "outputs" / "milvus_retrieval_ab"
DEFAULT_MILVUS_DEPS_PATH = Path("Z:/FIN_Insight_Agent_artifacts/python_deps/milvus_lite")
DEFAULT_MILVUS_DIR = Path("Z:/FIN_Insight_Agent_artifacts/milvus")
DEFAULT_EMBEDDING_MODEL = Path(
    "D:/hf_cache/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181"
)
SCHEMA_VERSION = "fin_agent_milvus_retrieval_ab_v0.3"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Milvus retrieval-only A/B diagnostic.")
    parser.add_argument("--evidence-path", type=Path, default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--bm25-index-dir", type=Path, default=DEFAULT_BM25_INDEX_DIR)
    parser.add_argument("--object-bm25-index-dir", type=Path, default=DEFAULT_OBJECT_BM25_INDEX_DIR)
    parser.add_argument("--cases-path", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--milvus-deps-path", type=Path, default=DEFAULT_MILVUS_DEPS_PATH)
    parser.add_argument("--milvus-dir", type=Path, default=DEFAULT_MILVUS_DIR)
    parser.add_argument("--reuse-milvus-db", type=Path, default=None)
    parser.add_argument("--reuse-milvus-collection-name", default="")
    parser.add_argument("--reuse-milvus-collection-rows", type=int, default=0)
    parser.add_argument("--embedding-model", type=Path, default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--device", default=os.environ.get("MILVUS_AB_EMBED_DEVICE", "cuda"))
    parser.add_argument("--object-vector-seed-path", type=Path, default=None)
    parser.add_argument("--collection-max-rows", type=int, default=20000)
    parser.add_argument("--object-vector-max-rows", type=int, default=4000)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--bm25-top-k", type=int, default=60)
    parser.add_argument("--object-top-k", type=int, default=60)
    parser.add_argument("--milvus-top-k", type=int, default=60)
    parser.add_argument("--embedding-batch-size", type=int, default=16)
    parser.add_argument("--embedding-max-seq-length", type=int, default=512)
    parser.add_argument("--vector-text-max-chars", type=int, default=1800)
    parser.add_argument("--insert-batch-size", type=int, default=256)
    parser.add_argument("--disable-object-vectors", action="store_true")
    parser.add_argument(
        "--disable-object-baseline",
        action="store_true",
        help="Run BM25 + Milvus diagnostics without ObjectBM25 when an expanded object index is not available.",
    )
    parser.add_argument("--disable-query-expansion", action="store_true")
    parser.add_argument(
        "--use-all-evidence",
        action="store_true",
        help=(
            "Build the Milvus collection from every evidence row in --evidence-path instead of "
            "the ticker/year/form subset implied by retrieval cases. Pair with "
            "--collection-max-rows 0 for an uncapped staging collection."
        ),
    )
    parser.add_argument("--milvus-build-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.time()
    run_id = args.run_id or _default_run_id()
    run_dir = args.output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    cases = _load_cases(args.cases_path)
    if args.case_id:
        wanted = {str(item) for item in args.case_id}
        cases = [case for case in cases if str(case.get("case_id") or "") in wanted]
    if not cases:
        raise ValueError(f"No retrieval A/B cases found at {args.cases_path}")

    _install_import_paths(args.milvus_deps_path)
    from pymilvus import DataType, MilvusClient
    from sentence_transformers import SentenceTransformer
    import torch

    bm25_cls = None
    object_bm25_cls = None
    if not args.milvus_build_only:
        from retrieval.bm25_retriever import BM25Retriever
        from retrieval.object_bm25_retriever import ObjectBM25Retriever

        bm25_cls = BM25Retriever
        object_bm25_cls = ObjectBM25Retriever
    elif not args.disable_object_vectors and args.object_vector_seed_path is None:
        from retrieval.object_bm25_retriever import ObjectBM25Retriever

        object_bm25_cls = ObjectBM25Retriever

    case_tickers = sorted({ticker.upper() for case in cases for ticker in case.get("tickers", [])})
    case_years = sorted({int(year) for case in cases for year in case.get("years", []) if str(year).isdigit()})
    case_source_tiers = sorted({tier for case in cases for tier in case.get("source_tiers", [])})
    case_form_types = sorted({form for case in cases for form in case.get("filing_types", [])})
    if args.use_all_evidence:
        tickers: list[str] = []
        years: list[int] = []
        source_tiers: list[str] = []
        form_types: list[str] = []
    else:
        tickers = case_tickers
        years = case_years
        source_tiers = case_source_tiers
        form_types = case_form_types

    evidence_rows = _load_evidence_subset(
        args.evidence_path,
        tickers=tickers,
        years=years,
        source_tiers=source_tiers,
        form_types=form_types,
        max_rows=args.collection_max_rows,
    )
    if not evidence_rows:
        raise ValueError("Milvus collection subset is empty; check case ticker/year/source filters.")
    bm25 = bm25_cls(args.bm25_index_dir) if bm25_cls is not None else None
    object_bm25 = None if args.disable_object_baseline else object_bm25_cls(args.object_bm25_index_dir) if object_bm25_cls is not None else None
    query_expansion_enabled = not bool(args.disable_query_expansion)
    reusing_milvus = args.reuse_milvus_db is not None
    object_vector_rows: list[dict[str, Any]] = []
    vector_rows: list[dict[str, Any]] = []
    if not reusing_milvus:
        if args.disable_object_vectors:
            object_vector_rows = []
        elif args.object_vector_seed_path is not None:
            object_vector_rows = _load_object_vector_seed_rows(
                args.object_vector_seed_path,
                max_rows=args.object_vector_max_rows,
            )
        else:
            if object_bm25 is None:
                raise ValueError("Object vector rows need ObjectBM25 or --object-vector-seed-path.")
            object_vector_rows = _collect_object_vector_seed_rows(
                cases=cases,
                object_bm25=object_bm25,
                max_rows=args.object_vector_max_rows,
                top_k=max(args.object_top_k, args.milvus_top_k),
                query_expansion_enabled=query_expansion_enabled,
            )
        vector_rows = _build_vector_records(
            evidence_rows=evidence_rows,
            object_rows=object_vector_rows,
            max_chars=args.vector_text_max_chars,
        )
        if not vector_rows:
            raise ValueError("Milvus vector row set is empty after building typed vector records.")

    device = args.device
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"
    try:
        model = SentenceTransformer(str(args.embedding_model), device=device)
    except Exception as exc:
        if device != "cuda" or "out of memory" not in str(exc).lower():
            raise
        try:
            torch.cuda.empty_cache()
        except Exception:
            pass
        device = "cpu"
        model = SentenceTransformer(str(args.embedding_model), device=device)
    if int(args.embedding_max_seq_length or 0) > 0:
        model.max_seq_length = int(args.embedding_max_seq_length)
    probe_embedding = model.encode(
        ["dimension probe"],
        batch_size=1,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    dim = int(probe_embedding.shape[1])

    if reusing_milvus:
        milvus_db = args.reuse_milvus_db
        collection_name = args.reuse_milvus_collection_name or _discover_milvus_collection_name(milvus_db)
    else:
        milvus_db = args.milvus_dir / run_id / "milvus_lite.db"
        milvus_db.parent.mkdir(parents=True, exist_ok=True)
        collection_name = _collection_name(run_id)
        build_client = MilvusClient(uri=str(milvus_db))
        try:
            _create_collection(build_client, collection_name, dim, DataType, MilvusClient)
            _insert_vector_rows(
                client=build_client,
                collection_name=collection_name,
                model=model,
                rows=vector_rows,
                batch_size=args.embedding_batch_size,
                insert_batch_size=args.insert_batch_size,
            )
            _load_collection_for_search(build_client, collection_name)
        finally:
            _close_milvus_client(build_client)

    evidence_by_id = {row["evidence_id"]: row for row in evidence_rows}
    results = []
    if not args.milvus_build_only:
        if bm25 is None:
            raise ValueError("BM25 retriever is required unless --milvus-build-only is set.")
        if object_bm25 is None and not args.disable_object_baseline:
            raise ValueError("ObjectBM25 retriever is required unless --disable-object-baseline or --milvus-build-only is set.")
        for case in cases:
            case_started = time.time()
            print(
                json.dumps(
                    {
                        "case_progress": "start",
                        "case_id": case.get("case_id"),
                        "category": case.get("category"),
                    },
                    ensure_ascii=False,
                ),
                file=sys.stderr,
                flush=True,
            )
            case_result = _run_case(
                case=case,
                bm25=bm25,
                object_bm25=object_bm25,
                milvus_client_cls=MilvusClient,
                milvus_db=milvus_db,
                collection_name=collection_name,
                model=model,
                evidence_by_id=evidence_by_id,
                top_k=args.top_k,
                bm25_top_k=args.bm25_top_k,
                object_top_k=args.object_top_k,
                milvus_top_k=args.milvus_top_k,
                query_expansion_enabled=query_expansion_enabled,
                object_baseline_enabled=not args.disable_object_baseline,
            )
            print(
                json.dumps(
                    {
                        "case_progress": "end",
                        "case_id": case.get("case_id"),
                        "gate_status": case_result.get("gate_status"),
                        "elapsed_ms": int((time.time() - case_started) * 1000),
                    },
                    ensure_ascii=False,
                ),
                file=sys.stderr,
                flush=True,
            )
            results.append(case_result)

    summary = _summarize(results)
    report = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "gate_status": "pass" if summary["failed_case_count"] == 0 else "fail",
        "diagnostic_only": True,
        "elapsed_ms": int((time.time() - started) * 1000),
        "inputs": {
            "evidence_path": str(args.evidence_path),
            "bm25_index_dir": str(args.bm25_index_dir),
            "object_bm25_index_dir": str(args.object_bm25_index_dir),
            "object_baseline_enabled": not args.disable_object_baseline,
            "cases_path": str(args.cases_path),
            "case_ids": [case.get("case_id") for case in cases],
            "milvus_db": str(milvus_db),
            "collection_name": collection_name,
            "embedding_model": str(args.embedding_model),
            "embedding_device": device,
            "collection_rows": int(args.reuse_milvus_collection_rows or 0) if reusing_milvus else len(vector_rows),
            "evidence_rows": len(evidence_rows),
            "object_vector_rows": len(object_vector_rows),
            "vector_kind_counts": _count_by(vector_rows, "vector_kind"),
            "object_vector_seed_path": str(args.object_vector_seed_path) if args.object_vector_seed_path else "",
            "milvus_build_only": bool(args.milvus_build_only),
            "reused_milvus_db": bool(reusing_milvus),
            "collection_tickers": tickers,
            "collection_years": years,
            "query_expansion_enabled": query_expansion_enabled,
            "use_all_evidence": bool(args.use_all_evidence),
            "case_scope_tickers": case_tickers,
            "case_scope_years": case_years,
        },
        "summary": summary,
        "cases": results,
    }
    json_path = run_dir / "milvus_retrieval_ab_summary.json"
    md_path = run_dir / "milvus_retrieval_ab_summary.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(json.dumps(_stdout_summary(report, json_path, md_path), ensure_ascii=False, indent=2))
    return 0 if report["gate_status"] == "pass" else 1


def _install_import_paths(milvus_deps_path: Path) -> None:
    for path in (REPO_ROOT / "src", milvus_deps_path):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


def _load_cases(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid retrieval case JSONL at {path}:{line_number}") from exc
            row["tickers"] = [str(item).upper() for item in row.get("tickers") or []]
            row["years"] = [int(item) for item in row.get("years") or []]
            rows.append(row)
    return rows


def _load_evidence_subset(
    path: Path,
    *,
    tickers: list[str],
    years: list[int],
    source_tiers: list[str],
    form_types: list[str],
    max_rows: int,
) -> list[dict[str, Any]]:
    ticker_set = set(tickers)
    year_set = set(years)
    source_tier_set = set(source_tiers)
    form_type_set = {_normalize_form_type(form) for form in form_types}
    rows_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            ticker = str(row.get("ticker") or "").upper()
            if ticker_set and ticker not in ticker_set:
                continue
            fiscal_year = _safe_int(row.get("fiscal_year"))
            if year_set and fiscal_year not in year_set:
                continue
            metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
            source_tier = str(row.get("source_tier") or metadata.get("source_tier") or "")
            if source_tier_set and source_tier not in source_tier_set:
                continue
            form_type = _normalize_form_type(metadata.get("form_type") or row.get("source_type"))
            if form_type_set and form_type not in form_type_set:
                continue
            rows_by_ticker[ticker].append(row)

    rows = [row for ticker in sorted(rows_by_ticker) for row in rows_by_ticker[ticker]]
    if max_rows <= 0 or len(rows) <= max_rows:
        return rows
    selected: list[dict[str, Any]] = []
    cursors = {ticker: 0 for ticker in rows_by_ticker}
    tickers_round_robin = sorted(rows_by_ticker)
    while len(selected) < max_rows and tickers_round_robin:
        next_tickers = []
        for ticker in tickers_round_robin:
            cursor = cursors[ticker]
            bucket = rows_by_ticker[ticker]
            if cursor < len(bucket):
                selected.append(bucket[cursor])
                cursors[ticker] += 1
                if len(selected) >= max_rows:
                    break
            if cursors[ticker] < len(bucket):
                next_tickers.append(ticker)
        tickers_round_robin = next_tickers
    return selected


def _collect_object_vector_seed_rows(
    *,
    cases: list[dict[str, Any]],
    object_bm25: Any,
    max_rows: int,
    top_k: int,
    query_expansion_enabled: bool,
) -> list[dict[str, Any]]:
    if max_rows <= 0:
        return []
    by_object_id: dict[str, dict[str, Any]] = {}
    per_query_top_k = max(5, min(int(top_k), max_rows))
    for case in cases:
        filters = _case_filters(case)
        object_types = case.get("object_types") or ["metric", "table", "claim"]
        queries = _expanded_queries(case, enabled=query_expansion_enabled)
        for query in queries:
            hits = object_bm25.search(
                query,
                top_k=per_query_top_k,
                filters={**filters, "object_type": object_types},
            )
            for hit in hits:
                record = hit.get("record") if isinstance(hit.get("record"), Mapping) else {}
                object_id = str(record.get("object_id") or hit.get("object_id") or "")
                source_evidence_id = str(record.get("source_evidence_id") or hit.get("source_evidence_id") or "")
                if not object_id or not source_evidence_id:
                    continue
                existing = by_object_id.get(object_id)
                score = float(hit.get("score") or 0.0)
                if existing is None or score > float(existing.get("_seed_score") or 0.0):
                    by_object_id[object_id] = {**record, "_seed_score": score}
    ranked = sorted(by_object_id.values(), key=lambda row: float(row.get("_seed_score") or 0.0), reverse=True)
    return _balanced_object_seed_rows(ranked, max_rows=max_rows)


def _load_object_vector_seed_rows(path: Path, *, max_rows: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid object vector seed JSONL at {path}:{line_number}") from exc
            if isinstance(row, Mapping):
                rows.append(dict(row))
    return _balanced_object_seed_rows(rows, max_rows=max_rows) if max_rows > 0 else rows


def _balanced_object_seed_rows(rows: list[dict[str, Any]], *, max_rows: int) -> list[dict[str, Any]]:
    if len(rows) <= max_rows:
        return rows
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[(str(row.get("ticker") or "").upper(), str(row.get("object_type") or ""))].append(row)
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    bucket_keys = sorted(buckets)
    while len(selected) < max_rows and bucket_keys:
        next_keys: list[tuple[str, str]] = []
        for key in bucket_keys:
            bucket = buckets[key]
            while bucket:
                row = bucket.pop(0)
                object_id = str(row.get("object_id") or "")
                if object_id and object_id not in seen:
                    selected.append(row)
                    seen.add(object_id)
                    break
            if len(selected) >= max_rows:
                break
            if bucket:
                next_keys.append(key)
        bucket_keys = next_keys
    return selected


def _build_vector_records(
    *,
    evidence_rows: list[dict[str, Any]],
    object_rows: list[dict[str, Any]],
    max_chars: int,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen_vector_ids: set[str] = set()
    for row in evidence_rows:
        evidence_id = str(row.get("evidence_id") or "")
        if not evidence_id:
            continue
        narrative = _evidence_vector_record(row, vector_kind="narrative_chunk", max_chars=max_chars)
        _append_unique_vector(records, seen_vector_ids, narrative)
        if _should_add_relationship_context(row):
            relationship = _evidence_vector_record(row, vector_kind="relationship_context", max_chars=max_chars)
            relationship["vector_id"] = f"{evidence_id}::relationship_context"
            relationship["semantic_scope"] = "relationship"
            relationship["vector_role"] = "economic_linkage_context"
            relationship["vector_text"] = _relationship_context_vector_text(row, max_chars=max_chars)
            _append_unique_vector(records, seen_vector_ids, relationship)
        if _should_add_paraphrase_context(row):
            paraphrase = _evidence_vector_record(row, vector_kind="paraphrase_context", max_chars=max_chars)
            paraphrase["vector_id"] = f"{evidence_id}::paraphrase_context"
            paraphrase["semantic_scope"] = "paraphrase"
            paraphrase["vector_role"] = "plain_language_context"
            paraphrase["vector_text"] = _paraphrase_context_vector_text(row, max_chars=max_chars)
            _append_unique_vector(records, seen_vector_ids, paraphrase)
        metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
        if bool(metadata.get("contains_table")):
            table = _evidence_vector_record(row, vector_kind="table_chunk", max_chars=max_chars)
            table["vector_id"] = f"{evidence_id}::table_chunk"
            table["object_type"] = "table"
            table["semantic_scope"] = "financial_table"
            table["vector_role"] = "tabular_fact_context"
            table["vector_text"] = _table_chunk_vector_text(row, max_chars=max_chars)
            _append_unique_vector(records, seen_vector_ids, table)
    for row in object_rows:
        record = _object_vector_record(row, max_chars=max_chars)
        _append_unique_vector(records, seen_vector_ids, record)
    return records


def _append_unique_vector(records: list[dict[str, Any]], seen: set[str], record: dict[str, Any]) -> None:
    vector_id = str(record.get("vector_id") or "")
    evidence_id = str(record.get("evidence_id") or "")
    if not vector_id or not evidence_id or vector_id in seen:
        return
    records.append(record)
    seen.add(vector_id)


def _evidence_vector_record(row: Mapping[str, Any], *, vector_kind: str, max_chars: int) -> dict[str, Any]:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
    evidence_id = str(row.get("evidence_id") or "")
    body = _truncate_text(str(row.get("text") or ""), max_chars)
    intent_tags = _intent_tags_for_evidence(row)
    return {
        "vector_id": evidence_id,
        "evidence_id": evidence_id,
        "vector_kind": vector_kind,
        "vector_role": _default_vector_role(vector_kind),
        "semantic_scope": _default_semantic_scope(vector_kind),
        "intent_tags": "|".join(intent_tags),
        "relationship_role": _relationship_role_for_row(row, intent_tags),
        "object_type": "",
        "ticker": str(row.get("ticker") or "").upper(),
        "company": str(row.get("company") or ""),
        "fiscal_year": int(row.get("fiscal_year") or 0),
        "form_type": _normalize_form_type(metadata.get("form_type") or row.get("source_type")),
        "source_type": _normalize_form_type(row.get("source_type") or metadata.get("form_type")),
        "source_tier": str(row.get("source_tier") or metadata.get("source_tier") or ""),
        "item_code": str(metadata.get("item_code") or ""),
        "category_slug": str(metadata.get("category_slug") or ""),
        "period_type": str(row.get("period_type") or metadata.get("period_type") or ""),
        "contains_table": bool(metadata.get("contains_table")),
        "preview": _preview(body, 600),
        "vector_text": _narrative_chunk_vector_text(row, max_chars=max_chars),
    }


def _object_vector_record(row: Mapping[str, Any], *, max_chars: int) -> dict[str, Any]:
    object_type = str(row.get("object_type") or "")
    source_evidence_id = str(row.get("source_evidence_id") or "")
    object_id = str(row.get("object_id") or "")
    kind = {
        "metric": "metric_row",
        "table": "table_row",
        "claim": "claim_object",
    }.get(object_type, "structured_object")
    metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
    intent_tags = _intent_tags_for_object(row)
    return {
        "vector_id": f"object::{object_id}",
        "evidence_id": source_evidence_id,
        "vector_kind": kind,
        "vector_role": _default_vector_role(kind),
        "semantic_scope": _default_semantic_scope(kind),
        "intent_tags": "|".join(intent_tags),
        "relationship_role": _relationship_role_for_row(row, intent_tags),
        "object_type": object_type,
        "ticker": str(row.get("ticker") or "").upper(),
        "company": "",
        "fiscal_year": int(row.get("fiscal_year") or 0),
        "form_type": _normalize_form_type(row.get("form_type") or row.get("source_type") or metadata.get("form_type")),
        "source_type": _normalize_form_type(row.get("source_type") or row.get("form_type") or metadata.get("form_type")),
        "source_tier": str(row.get("source_tier") or metadata.get("source_tier") or ""),
        "item_code": _item_code_from_section(row.get("section")),
        "category_slug": str(metadata.get("category_slug") or ""),
        "period_type": str(row.get("period_type") or metadata.get("period_type") or ""),
        "contains_table": object_type == "table",
        "preview": _preview(str(row.get("preview") or ""), 600),
        "vector_text": _object_vector_text(row, max_chars=max_chars),
    }


def _create_collection(client: Any, collection_name: str, dim: int, data_type: Any, milvus_client_cls: Any) -> None:
    schema = milvus_client_cls.create_schema(auto_id=False, enable_dynamic_field=True)
    schema.add_field(field_name="vector_id", datatype=data_type.VARCHAR, is_primary=True, max_length=512)
    schema.add_field(field_name="embedding", datatype=data_type.FLOAT_VECTOR, dim=dim)
    schema.add_field(field_name="evidence_id", datatype=data_type.VARCHAR, max_length=256)
    schema.add_field(field_name="ticker", datatype=data_type.VARCHAR, max_length=16)
    schema.add_field(field_name="fiscal_year", datatype=data_type.INT64)
    schema.add_field(field_name="form_type", datatype=data_type.VARCHAR, max_length=16)
    schema.add_field(field_name="source_tier", datatype=data_type.VARCHAR, max_length=80)
    schema.add_field(field_name="item_code", datatype=data_type.VARCHAR, max_length=16)
    schema.add_field(field_name="category_slug", datatype=data_type.VARCHAR, max_length=96)
    schema.add_field(field_name="period_type", datatype=data_type.VARCHAR, max_length=40)
    schema.add_field(field_name="contains_table", datatype=data_type.BOOL)
    schema.add_field(field_name="vector_kind", datatype=data_type.VARCHAR, max_length=32)
    schema.add_field(field_name="vector_role", datatype=data_type.VARCHAR, max_length=64)
    schema.add_field(field_name="semantic_scope", datatype=data_type.VARCHAR, max_length=64)
    schema.add_field(field_name="intent_tags", datatype=data_type.VARCHAR, max_length=512)
    schema.add_field(field_name="relationship_role", datatype=data_type.VARCHAR, max_length=64)
    schema.add_field(field_name="object_type", datatype=data_type.VARCHAR, max_length=32)
    schema.add_field(field_name="preview", datatype=data_type.VARCHAR, max_length=4096)
    index_params = milvus_client_cls.prepare_index_params()
    index_params.add_index(field_name="embedding", metric_type="COSINE", index_type="FLAT")
    client.create_collection(collection_name=collection_name, schema=schema, index_params=index_params)


def _load_collection_for_search(client: Any, collection_name: str) -> None:
    load = getattr(client, "load_collection", None)
    if not callable(load):
        return
    try:
        load(collection_name=collection_name)
    except TypeError:
        load(collection_name)


def _close_milvus_client(client: Any) -> None:
    for method_name in ("close", "disconnect"):
        method = getattr(client, method_name, None)
        if callable(method):
            try:
                method()
            except Exception:
                pass
            return


def _discover_milvus_collection_name(milvus_db: Path) -> str:
    collections_dir = Path(milvus_db) / "collections"
    names = sorted(path.name for path in collections_dir.glob("*") if path.is_dir())
    if len(names) != 1:
        raise ValueError(
            f"Expected exactly one collection under {collections_dir}; found {len(names)}. "
            "Pass --reuse-milvus-collection-name explicitly."
        )
    return names[0]


def _insert_vector_rows(
    *,
    client: Any,
    collection_name: str,
    model: Any,
    rows: list[dict[str, Any]],
    batch_size: int,
    insert_batch_size: int,
) -> None:
    pending: list[dict[str, Any]] = []
    for start in range(0, len(rows), max(1, int(batch_size))):
        batch = rows[start : start + max(1, int(batch_size))]
        if start == 0 or start % 512 == 0:
            print(
                json.dumps(
                    {"milvus_insert_progress": start, "total": len(rows)},
                    ensure_ascii=False,
                ),
                file=sys.stderr,
                flush=True,
            )
        texts = [str(row.get("vector_text") or "") for row in batch]
        embeddings = model.encode(
            texts,
            batch_size=max(1, int(batch_size)),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        for row, embedding in zip(batch, embeddings):
            pending.append(
                {
                    "vector_id": str(row.get("vector_id") or ""),
                    "evidence_id": str(row.get("evidence_id")),
                    "embedding": [float(item) for item in embedding.tolist()],
                    "ticker": str(row.get("ticker") or "").upper(),
                    "fiscal_year": int(row.get("fiscal_year") or 0),
                    "form_type": _normalize_form_type(row.get("form_type") or row.get("source_type")),
                    "source_tier": str(row.get("source_tier") or ""),
                    "item_code": str(row.get("item_code") or ""),
                    "category_slug": str(row.get("category_slug") or ""),
                    "period_type": str(row.get("period_type") or ""),
                    "contains_table": bool(row.get("contains_table")),
                    "vector_kind": str(row.get("vector_kind") or ""),
                    "vector_role": str(row.get("vector_role") or ""),
                    "semantic_scope": str(row.get("semantic_scope") or ""),
                    "intent_tags": _truncate_text(str(row.get("intent_tags") or ""), 500),
                    "relationship_role": str(row.get("relationship_role") or ""),
                    "object_type": str(row.get("object_type") or ""),
                    "preview": _truncate_text(str(row.get("preview") or ""), 4000),
                }
            )
        while len(pending) >= max(1, int(insert_batch_size)):
            client.insert(collection_name, pending[:insert_batch_size])
            del pending[:insert_batch_size]
    if pending:
        client.insert(collection_name, pending)


def _run_case(
    *,
    case: dict[str, Any],
    bm25: Any,
    object_bm25: Any,
    milvus_client_cls: Any,
    milvus_db: Path,
    collection_name: str,
    model: Any,
    evidence_by_id: dict[str, dict[str, Any]],
    top_k: int,
    bm25_top_k: int,
    object_top_k: int,
    milvus_top_k: int,
    query_expansion_enabled: bool,
    object_baseline_enabled: bool = True,
) -> dict[str, Any]:
    query = str(case.get("query") or "")
    filters = _case_filters(case)
    expanded_queries = _expanded_queries(case, enabled=query_expansion_enabled)
    milvus_client = milvus_client_cls(uri=str(milvus_db))
    try:
        _load_collection_for_search(milvus_client, collection_name)
        milvus_hits = _milvus_search_queries(
            client=milvus_client,
            collection_name=collection_name,
            model=model,
            queries=expanded_queries,
            case=case,
            top_k=milvus_top_k,
        )
    finally:
        _close_milvus_client(milvus_client)
    bm25_hits = _search_bm25_queries(
        bm25,
        queries=expanded_queries,
        top_k=bm25_top_k,
        filters=filters,
    )
    object_hits = []
    if object_baseline_enabled:
        object_hits = _search_object_bm25_queries(
            object_bm25,
            queries=expanded_queries,
            top_k=object_top_k,
            filters={**filters, "object_type": case.get("object_types") or ["metric", "table", "claim"]},
        )
    hybrid_hits = _hybrid_rrf(
        bm25_hits=bm25_hits,
        object_hits=object_hits,
        milvus_hits=milvus_hits,
        evidence_by_id=evidence_by_id,
        target_tickers=case.get("tickers") or [],
        top_k=max(top_k, min(bm25_top_k, milvus_top_k)),
        case=case,
    )

    variants = {
        "bm25": _evaluate_evidence_hits(bm25_hits, case, top_k=top_k),
        "object_bm25": {
            **_evaluate_object_hits(object_hits, case, top_k=top_k),
            "skipped": not object_baseline_enabled,
        },
        "milvus_semantic": _evaluate_milvus_hits(milvus_hits, evidence_by_id, case, top_k=top_k),
        "hybrid_rrf": _evaluate_hybrid_hits(hybrid_hits, case, top_k=top_k),
    }
    gates = _case_gates(case, variants)
    return {
        "case_id": case.get("case_id"),
        "category": case.get("category"),
        "query": query,
        "expanded_queries": expanded_queries,
        "filters": filters,
        "expected": {
            "tickers": case.get("tickers") or [],
            "terms_any": case.get("terms_any") or [],
            "metric_terms_any": case.get("metric_terms_any") or [],
        },
        "variants": variants,
        "gates": gates,
        "gate_status": "pass" if all(gates.values()) else "fail",
    }


def _case_filters(case: Mapping[str, Any]) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    if case.get("tickers"):
        filters["ticker"] = [str(item).upper() for item in case.get("tickers") or []]
    if case.get("years"):
        filters["fiscal_year"] = [int(item) for item in case.get("years") or []]
    if case.get("filing_types"):
        filters["form_type"] = [_normalize_form_type(item) for item in case.get("filing_types") or []]
    if case.get("source_tiers"):
        filters["source_tier"] = list(case.get("source_tiers") or [])
    return filters


def _search_bm25_queries(
    retriever: Any,
    *,
    queries: list[str],
    top_k: int,
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    hit_lists = [retriever.search(query, top_k=top_k, filters=filters) for query in queries]
    return _merge_ranked_hits(hit_lists, id_key="evidence_id", top_k=top_k)


def _search_object_bm25_queries(
    retriever: Any,
    *,
    queries: list[str],
    top_k: int,
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    hit_lists = [retriever.search(query, top_k=top_k, filters=filters) for query in queries]
    return _merge_ranked_hits(hit_lists, id_key="object_id", top_k=top_k)


def _merge_ranked_hits(hit_lists: list[list[dict[str, Any]]], *, id_key: str, top_k: int) -> list[dict[str, Any]]:
    scores: dict[str, float] = defaultdict(float)
    support: dict[str, dict[str, Any]] = {}
    for query_index, hits in enumerate(hit_lists):
        query_weight = 1.0 if query_index == 0 else 0.85
        for rank, hit in enumerate(hits, start=1):
            key = str(hit.get(id_key) or "")
            if not key:
                continue
            scores[key] += query_weight / (60.0 + rank)
            existing = support.get(key)
            if existing is None or rank < int(existing.get("rank") or 999999):
                support[key] = dict(hit)
            support[key].setdefault("matched_query_indices", [])
            support[key]["matched_query_indices"].append(query_index)
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[: max(1, int(top_k))]
    out: list[dict[str, Any]] = []
    for rank, (key, score) in enumerate(ranked, start=1):
        item = dict(support.get(key) or {})
        item["rank"] = rank
        item["score"] = score
        out.append(item)
    return out


def _milvus_search(
    *,
    client: Any,
    collection_name: str,
    model: Any,
    query: str,
    case: Mapping[str, Any],
    top_k: int,
) -> list[dict[str, Any]]:
    embedding = model.encode(
        [query],
        batch_size=1,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )[0]
    expr = _milvus_expr(case)
    base_output_fields = [
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
        "object_type",
        "preview",
    ]
    typed_output_fields = [
        "vector_role",
        "semantic_scope",
        "intent_tags",
        "relationship_role",
    ]
    try:
        results = client.search(
            collection_name=collection_name,
            data=[[float(item) for item in embedding.tolist()]],
            anns_field="embedding",
            limit=max(1, int(top_k)),
            filter=expr or "",
            output_fields=[*base_output_fields, *typed_output_fields],
        )
    except Exception as exc:
        if not any(field in str(exc) for field in typed_output_fields):
            raise
        results = client.search(
            collection_name=collection_name,
            data=[[float(item) for item in embedding.tolist()]],
            anns_field="embedding",
            limit=max(1, int(top_k)),
            filter=expr or "",
            output_fields=base_output_fields,
        )
    hits: list[dict[str, Any]] = []
    for rank, hit in enumerate(results[0] if results else [], start=1):
        entity = dict(hit.get("entity") or {})
        entity["rank"] = rank
        entity["score"] = float(hit.get("distance") or 0.0)
        hits.append(entity)
    return hits


def _milvus_search_queries(
    *,
    client: Any,
    collection_name: str,
    model: Any,
    queries: list[str],
    case: Mapping[str, Any],
    top_k: int,
) -> list[dict[str, Any]]:
    scores: dict[str, float] = defaultdict(float)
    support: dict[str, dict[str, Any]] = {}
    for query_index, query in enumerate(queries):
        query_weight = 1.0 if query_index == 0 else 0.85
        hits = _milvus_search(
            client=client,
            collection_name=collection_name,
            model=model,
            query=query,
            case=case,
            top_k=top_k,
        )
        for rank, hit in enumerate(hits, start=1):
            evidence_id = str(hit.get("evidence_id") or "")
            if not evidence_id:
                continue
            scores[evidence_id] += query_weight * _semantic_hit_weight(hit, case) / (60.0 + rank)
            existing = support.get(evidence_id)
            if existing is None or rank < int(existing.get("rank") or 999999):
                support[evidence_id] = dict(hit)
            _ensure_support_list_fields(
                support[evidence_id],
                [
                    "vector_kinds",
                    "vector_roles",
                    "semantic_scopes",
                    "intent_tags",
                    "relationship_roles",
                    "object_types",
                    "matched_query_indices",
                ],
            )
            support[evidence_id].setdefault("vector_kinds", [])
            support[evidence_id]["vector_kinds"].append(str(hit.get("vector_kind") or ""))
            support[evidence_id].setdefault("vector_roles", [])
            support[evidence_id]["vector_roles"].append(str(hit.get("vector_role") or ""))
            support[evidence_id].setdefault("semantic_scopes", [])
            support[evidence_id]["semantic_scopes"].append(str(hit.get("semantic_scope") or ""))
            support[evidence_id].setdefault("intent_tags", [])
            support[evidence_id]["intent_tags"].extend(_split_multi_value(hit.get("intent_tags")))
            support[evidence_id].setdefault("relationship_roles", [])
            support[evidence_id]["relationship_roles"].append(str(hit.get("relationship_role") or ""))
            support[evidence_id].setdefault("object_types", [])
            support[evidence_id]["object_types"].append(str(hit.get("object_type") or ""))
            support[evidence_id].setdefault("matched_query_indices", [])
            support[evidence_id]["matched_query_indices"].append(query_index)
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[: max(1, int(top_k))]
    out: list[dict[str, Any]] = []
    for rank, (evidence_id, score) in enumerate(ranked, start=1):
        item = dict(support.get(evidence_id) or {"evidence_id": evidence_id})
        item["rank"] = rank
        item["score"] = score
        item["vector_kinds"] = sorted({kind for kind in item.get("vector_kinds", []) if kind})
        item["vector_roles"] = sorted({kind for kind in item.get("vector_roles", []) if kind})
        item["semantic_scopes"] = sorted({kind for kind in item.get("semantic_scopes", []) if kind})
        item["intent_tags"] = sorted({kind for kind in item.get("intent_tags", []) if kind})
        item["relationship_roles"] = sorted({kind for kind in item.get("relationship_roles", []) if kind})
        item["object_types"] = sorted({kind for kind in item.get("object_types", []) if kind})
        out.append(item)
    return out


def _milvus_expr(case: Mapping[str, Any]) -> str:
    clauses = []
    if case.get("tickers"):
        clauses.append(_milvus_in_clause("ticker", [str(item).upper() for item in case.get("tickers") or []]))
    if case.get("years"):
        clauses.append("fiscal_year in [" + ", ".join(str(int(item)) for item in case.get("years") or []) + "]")
    if case.get("filing_types"):
        clauses.append(_milvus_in_clause("form_type", [_normalize_form_type(item) for item in case.get("filing_types") or []]))
    if case.get("source_tiers"):
        clauses.append(_milvus_in_clause("source_tier", [str(item) for item in case.get("source_tiers") or []]))
    return " and ".join(clause for clause in clauses if clause)


def _milvus_in_clause(field: str, values: Iterable[str]) -> str:
    quoted = ", ".join(json.dumps(str(value), ensure_ascii=False) for value in values)
    return f"{field} in [{quoted}]"


def _hybrid_rrf(
    *,
    bm25_hits: list[dict[str, Any]],
    object_hits: list[dict[str, Any]],
    milvus_hits: list[dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
    target_tickers: list[str],
    top_k: int,
    case: Mapping[str, Any],
) -> list[dict[str, Any]]:
    scores: dict[str, float] = defaultdict(float)
    support: dict[str, dict[str, Any]] = {}
    for source_name, hits, id_key in (
        ("bm25", bm25_hits, "evidence_id"),
        ("object_bm25", object_hits, "source_evidence_id"),
        ("milvus_semantic", milvus_hits, "evidence_id"),
    ):
        for rank, hit in enumerate(hits, start=1):
            evidence_id = str(hit.get(id_key) or "")
            if not evidence_id:
                continue
            scores[evidence_id] += 1.0 / (60.0 + rank)
            support.setdefault(evidence_id, {"sources": [], "evidence_id": evidence_id})
            support[evidence_id]["sources"].append(source_name)
            if evidence_id in evidence_by_id:
                support[evidence_id]["record"] = evidence_by_id[evidence_id]
            elif source_name == "bm25":
                support[evidence_id]["record"] = hit.get("record")
            support[evidence_id].setdefault("object_previews", [])
            if source_name == "object_bm25":
                support[evidence_id]["object_previews"].append(hit.get("preview") or "")
            if source_name == "milvus_semantic":
                support[evidence_id].setdefault("object_previews", [])
                support[evidence_id]["object_previews"].append(hit.get("preview") or "")
                support[evidence_id].setdefault("vector_kinds", [])
                support[evidence_id]["vector_kinds"].extend(hit.get("vector_kinds") or [hit.get("vector_kind") or ""])
                support[evidence_id].setdefault("vector_roles", [])
                support[evidence_id]["vector_roles"].extend(hit.get("vector_roles") or [hit.get("vector_role") or ""])
                support[evidence_id].setdefault("semantic_scopes", [])
                support[evidence_id]["semantic_scopes"].extend(hit.get("semantic_scopes") or [hit.get("semantic_scope") or ""])
                support[evidence_id].setdefault("intent_tags", [])
                support[evidence_id]["intent_tags"].extend(_split_multi_value(hit.get("intent_tags")))
                support[evidence_id].setdefault("relationship_roles", [])
                support[evidence_id]["relationship_roles"].extend(
                    hit.get("relationship_roles") or [hit.get("relationship_role") or ""]
                )
                support[evidence_id].setdefault("object_types", [])
                support[evidence_id]["object_types"].extend(hit.get("object_types") or [hit.get("object_type") or ""])
    ranked = _balanced_rrf_rank(scores, support, target_tickers=target_tickers, top_k=top_k, case=case)
    out = []
    for rank, (evidence_id, score) in enumerate(ranked, start=1):
        item = support.get(evidence_id, {"evidence_id": evidence_id})
        record = item.get("record") if isinstance(item.get("record"), Mapping) else {}
        out.append(
            {
                "rank": rank,
                "score": score,
                "evidence_id": evidence_id,
                "sources": sorted(set(item.get("sources") or [])),
                "ticker": record.get("ticker"),
                "fiscal_year": record.get("fiscal_year"),
                "text": _support_text(record, item),
                "text_preview": _preview(_support_text(record, item)),
                "contains_table": bool((record.get("metadata") or {}).get("contains_table")),
                "item_code": str((record.get("metadata") or {}).get("item_code") or ""),
                "source_tier": str(record.get("source_tier") or (record.get("metadata") or {}).get("source_tier") or ""),
                "vector_kinds": sorted({kind for kind in item.get("vector_kinds", []) if kind}),
                "vector_roles": sorted({kind for kind in item.get("vector_roles", []) if kind}),
                "semantic_scopes": sorted({kind for kind in item.get("semantic_scopes", []) if kind}),
                "intent_tags": sorted({kind for kind in item.get("intent_tags", []) if kind}),
                "relationship_roles": sorted({kind for kind in item.get("relationship_roles", []) if kind}),
                "object_types": sorted({kind for kind in item.get("object_types", []) if kind}),
            }
        )
    return out


def _balanced_rrf_rank(
    scores: Mapping[str, float],
    support: Mapping[str, Mapping[str, Any]],
    *,
    target_tickers: list[str],
    top_k: int,
    case: Mapping[str, Any],
) -> list[tuple[str, float]]:
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    if not target_tickers or top_k <= 1:
        return ranked[:top_k]

    target_order = [str(ticker).upper() for ticker in target_tickers]
    selected: list[tuple[str, float]] = []
    selected_ids: set[str] = set()
    category = str(case.get("category") or "")

    def add_best(bucket_key: tuple[str, ...]) -> None:
        if len(selected) >= top_k:
            return
        for evidence_id, score in ranked:
            if evidence_id in selected_ids:
                continue
            if _support_matches_bucket(support.get(evidence_id) or {}, key_type=bucket_key[0], expected=bucket_key[1:]):
                selected.append((evidence_id, score))
                selected_ids.add(evidence_id)
                return

    for ticker in target_order:
        add_best(("ticker", ticker))

    if category in {"sector_depth", "relationship", "paraphrase"}:
        for item_code in ("7", "8", "1", "1A", "exhibit_99_1"):
            add_best(("item_code", item_code))
        for source_tier in ("primary_sec_filing", "company_authored_unaudited_sec_filing"):
            add_best(("source_tier", source_tier))
        if category == "relationship":
            add_best(("semantic_scope", "relationship"))
            add_best(("vector_role", "economic_linkage_context"))
            for tag in _case_intent_tags(case)[:5]:
                add_best(("intent_tag", tag))
            vector_kind_priority = (
                "relationship_context",
                "claim_object",
                "narrative_chunk",
                "metric_row",
                "table_row",
                "table_chunk",
            )
        elif category == "paraphrase":
            add_best(("semantic_scope", "paraphrase"))
            add_best(("vector_role", "plain_language_context"))
            for tag in _case_intent_tags(case)[:5]:
                add_best(("intent_tag", tag))
            vector_kind_priority = (
                "paraphrase_context",
                "relationship_context",
                "narrative_chunk",
                "claim_object",
                "metric_row",
                "table_row",
                "table_chunk",
            )
        else:
            vector_kind_priority = (
                "metric_row",
                "table_row",
                "narrative_chunk",
                "relationship_context",
                "table_chunk",
                "claim_object",
            )
        for vector_kind in vector_kind_priority:
            add_best(("vector_kind", vector_kind))
    for evidence_id, score in ranked:
        if len(selected) >= top_k:
            break
        if evidence_id in selected_ids:
            continue
        selected.append((evidence_id, score))
        selected_ids.add(evidence_id)
    return selected


def _support_matches_bucket(item: Mapping[str, Any], *, key_type: str, expected: tuple[str, ...]) -> bool:
    record = item.get("record") if isinstance(item.get("record"), Mapping) else {}
    metadata = record.get("metadata") if isinstance(record.get("metadata"), Mapping) else {}
    if key_type == "ticker":
        return str(record.get("ticker") or "").upper() == (expected[0] if expected else "")
    if key_type == "item_code":
        item_code = str(metadata.get("item_code") or _item_code_from_section(record.get("section")) or "")
        return item_code == (expected[0] if expected else "")
    if key_type == "source_tier":
        return str(record.get("source_tier") or metadata.get("source_tier") or "") == (expected[0] if expected else "")
    if key_type == "vector_kind":
        kinds = {str(kind) for kind in item.get("vector_kinds", []) if kind}
        return (expected[0] if expected else "") in kinds
    if key_type == "vector_role":
        roles = {str(role) for role in item.get("vector_roles", []) if role}
        return (expected[0] if expected else "") in roles
    if key_type == "semantic_scope":
        scopes = {str(scope) for scope in item.get("semantic_scopes", []) if scope}
        return (expected[0] if expected else "") in scopes
    if key_type == "intent_tag":
        tags = {str(tag) for tag in item.get("intent_tags", []) if tag}
        return (expected[0] if expected else "") in tags
    if key_type == "relationship_role":
        roles = {str(role) for role in item.get("relationship_roles", []) if role}
        return (expected[0] if expected else "") in roles
    return False


def _evaluate_evidence_hits(hits: list[dict[str, Any]], case: Mapping[str, Any], *, top_k: int) -> dict[str, Any]:
    rows = []
    for hit in hits[:top_k]:
        record = hit.get("record") if isinstance(hit.get("record"), Mapping) else {}
        rows.append(
            {
                "rank": hit.get("rank"),
                "id": hit.get("evidence_id"),
                "ticker": hit.get("ticker"),
                "fiscal_year": hit.get("fiscal_year"),
                "text": record.get("text") or hit.get("text_preview") or "",
                "contains_table": bool(hit.get("contains_table")),
                "item_code": str((record.get("metadata") or {}).get("item_code") or ""),
                "source_tier": str(record.get("source_tier") or (record.get("metadata") or {}).get("source_tier") or ""),
                "vector_kind": "narrative_chunk",
                "vector_role": _default_vector_role("narrative_chunk"),
                "semantic_scope": _default_semantic_scope("narrative_chunk"),
                "intent_tags": "",
                "relationship_role": "",
            }
        )
    return _evaluate_rows(rows, case)


def _evaluate_object_hits(hits: list[dict[str, Any]], case: Mapping[str, Any], *, top_k: int) -> dict[str, Any]:
    rows = []
    for hit in hits[:top_k]:
        rows.append(
            {
                "rank": hit.get("rank"),
                "id": hit.get("source_evidence_id") or hit.get("object_id"),
                "object_id": hit.get("object_id"),
                "object_type": hit.get("object_type"),
                "ticker": hit.get("ticker"),
                "fiscal_year": hit.get("fiscal_year"),
                "text": hit.get("preview") or "",
                "contains_table": hit.get("object_type") == "table",
                "item_code": _item_code_from_section(hit.get("section")),
                "source_tier": str((hit.get("record") or {}).get("source_tier") or ""),
                "vector_kind": _vector_kind_for_object_type(hit.get("object_type")),
                "vector_role": _default_vector_role(_vector_kind_for_object_type(hit.get("object_type"))),
                "semantic_scope": _default_semantic_scope(_vector_kind_for_object_type(hit.get("object_type"))),
                "intent_tags": "",
                "relationship_role": "",
            }
        )
    return _evaluate_rows(rows, case, object_mode=True)


def _evaluate_milvus_hits(
    hits: list[dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
    case: Mapping[str, Any],
    *,
    top_k: int,
) -> dict[str, Any]:
    rows = []
    for hit in hits[:top_k]:
        record = evidence_by_id.get(str(hit.get("evidence_id") or ""), {})
        rows.append(
            {
                "rank": hit.get("rank"),
                "id": hit.get("evidence_id"),
                "ticker": hit.get("ticker"),
                "fiscal_year": hit.get("fiscal_year"),
                "text": " ".join(part for part in (str(hit.get("preview") or ""), str(record.get("text") or "")) if part),
                "contains_table": bool(hit.get("contains_table")),
                "item_code": str(hit.get("item_code") or (record.get("metadata") or {}).get("item_code") or ""),
                "source_tier": str(hit.get("source_tier") or record.get("source_tier") or ""),
                "vector_kind": ",".join(hit.get("vector_kinds") or [hit.get("vector_kind") or ""]),
                "vector_role": ",".join(hit.get("vector_roles") or [hit.get("vector_role") or ""]),
                "semantic_scope": ",".join(hit.get("semantic_scopes") or [hit.get("semantic_scope") or ""]),
                "intent_tags": ",".join(_split_multi_value(hit.get("intent_tags"))),
                "relationship_role": ",".join(hit.get("relationship_roles") or [hit.get("relationship_role") or ""]),
                "object_type": ",".join(hit.get("object_types") or [hit.get("object_type") or ""]),
            }
        )
    return _evaluate_rows(rows, case)


def _evaluate_hybrid_hits(hits: list[dict[str, Any]], case: Mapping[str, Any], *, top_k: int) -> dict[str, Any]:
    rows = []
    for hit in hits[:top_k]:
        rows.append(
            {
                "rank": hit.get("rank"),
                "id": hit.get("evidence_id"),
                "ticker": hit.get("ticker"),
                "fiscal_year": hit.get("fiscal_year"),
                "text": hit.get("text") or hit.get("text_preview") or "",
                "contains_table": bool(hit.get("contains_table")),
                "sources": hit.get("sources") or [],
                "item_code": str(hit.get("item_code") or ""),
                "source_tier": str(hit.get("source_tier") or ""),
                "vector_kind": ",".join(hit.get("vector_kinds") or []),
                "vector_role": ",".join(hit.get("vector_roles") or []),
                "semantic_scope": ",".join(hit.get("semantic_scopes") or []),
                "intent_tags": ",".join(hit.get("intent_tags") or []),
                "relationship_role": ",".join(hit.get("relationship_roles") or []),
                "object_type": ",".join(hit.get("object_types") or []),
            }
        )
    return _evaluate_rows(rows, case)


def _evaluate_rows(rows: list[dict[str, Any]], case: Mapping[str, Any], *, object_mode: bool = False) -> dict[str, Any]:
    terms = [str(item).lower() for item in case.get("terms_any") or []]
    metric_terms = [str(item).lower() for item in case.get("metric_terms_any") or []]
    tickers = {str(item).upper() for item in case.get("tickers") or []}
    usable = [row for row in rows if _row_has_any_term(row, terms)]
    metric_usable = [row for row in rows if _row_has_any_term(row, metric_terms)]
    ticker_coverage = sorted({str(row.get("ticker") or "").upper() for row in rows if str(row.get("ticker") or "").upper() in tickers})
    return {
        "row_count": len(rows),
        "usable_evidence_rows": len(usable),
        "metric_evidence_rows": len(metric_usable),
        "ticker_coverage": ticker_coverage,
        "ticker_coverage_count": len(ticker_coverage),
        "contains_table_count": sum(1 for row in rows if row.get("contains_table")),
        "vector_kind_counts": _count_by(rows, "vector_kind"),
        "vector_role_counts": _count_by(rows, "vector_role"),
        "semantic_scope_counts": _count_by(rows, "semantic_scope"),
        "intent_tag_counts": _count_by(rows, "intent_tags"),
        "relationship_role_counts": _count_by(rows, "relationship_role"),
        "object_type_counts": _count_by(rows, "object_type"),
        "item_code_counts": _count_by(rows, "item_code"),
        "source_tier_counts": _count_by(rows, "source_tier"),
        "top_ids": [row.get("id") for row in rows[:5]],
        "top_previews": [_preview(str(row.get("text") or ""), 180) for row in rows[:3]],
        "object_mode": object_mode,
    }


def _case_gates(case: Mapping[str, Any], variants: Mapping[str, Mapping[str, Any]]) -> dict[str, bool]:
    category = str(case.get("category") or "")
    min_usable = int(case.get("min_usable_evidence_rows") or 1)
    min_ticker_coverage = int(case.get("min_ticker_coverage") or min(1, len(case.get("tickers") or [])))
    bm25_usable = int(variants["bm25"].get("usable_evidence_rows") or 0)
    hybrid_usable = int(variants["hybrid_rrf"].get("usable_evidence_rows") or 0)
    bm25_ticker_coverage = int(variants["bm25"].get("ticker_coverage_count") or 0)
    hybrid_ticker_coverage = int(variants["hybrid_rrf"].get("ticker_coverage_count") or 0)
    object_metric = int(variants["object_bm25"].get("metric_evidence_rows") or 0)
    object_skipped = bool(variants["object_bm25"].get("skipped"))
    hybrid_metric = int(variants["hybrid_rrf"].get("metric_evidence_rows") or 0)
    gates = {
        "route_success_any": any(int(item.get("row_count") or 0) > 0 for item in variants.values()),
        "hybrid_usable_evidence_min": hybrid_usable >= min_usable,
        "hybrid_ticker_coverage_min": hybrid_ticker_coverage >= min_ticker_coverage,
    }
    if category in {"sector_depth", "relationship", "paraphrase"}:
        allowed_drop = int(case.get("allowed_usable_drop") or 1)
        gates["semantic_or_hybrid_not_worse_than_bm25"] = (
            hybrid_usable + allowed_drop >= bm25_usable
            and hybrid_ticker_coverage >= bm25_ticker_coverage
        )
    required_vector_kinds = [str(item) for item in case.get("required_semantic_vector_kinds") or [] if str(item)]
    if not required_vector_kinds and category == "relationship":
        required_vector_kinds = ["relationship_context"]
    if not required_vector_kinds and category == "paraphrase":
        required_vector_kinds = ["paraphrase_context"]
    if required_vector_kinds:
        gates["required_semantic_vector_kind_hit"] = _variant_has_any_count(
            [variants["milvus_semantic"], variants["hybrid_rrf"]],
            "vector_kind_counts",
            required_vector_kinds,
        )
    if category == "exact_lookup":
        if object_skipped:
            gates["exact_object_metric_hit"] = True
            gates["hybrid_exact_metric_not_dropped"] = hybrid_usable >= min_usable or bm25_usable >= min_usable
        else:
            gates["exact_object_metric_hit"] = object_metric > 0
            gates["hybrid_exact_metric_not_dropped"] = hybrid_metric >= object_metric or hybrid_usable >= min_usable
    return gates


def _row_has_any_term(row: Mapping[str, Any], terms: list[str]) -> bool:
    if not terms:
        return bool(str(row.get("text") or "").strip())
    text = str(row.get("text") or "").lower()
    return any(term in text for term in terms)


def _expanded_queries(case: Mapping[str, Any], *, enabled: bool) -> list[str]:
    base = str(case.get("query") or "").strip()
    if not enabled:
        return [base]
    terms = [str(item).strip() for item in case.get("terms_any") or [] if str(item).strip()]
    metric_terms = [str(item).strip() for item in case.get("metric_terms_any") or [] if str(item).strip()]
    category = str(case.get("category") or "")
    text = " ".join([base, *terms, *metric_terms]).lower()
    tickers = " ".join(str(item).upper() for item in case.get("tickers") or [])
    semantic_terms = _semantic_expansion_terms(text)

    if category == "relationship":
        queries = [
            base,
            " ".join(
                part
                for part in (
                    tickers,
                    "economic linkage demand transmission upstream downstream customer supplier supply chain",
                    " ".join(_dedupe_strings([*terms, *metric_terms, *semantic_terms])[:10]),
                )
                if part
            ),
            *_relationship_query_rewrites(case, semantic_terms=semantic_terms),
        ]
        return _dedupe_strings([query for query in queries if query])[:6] or [base]

    if category == "paraphrase":
        queries = [
            base,
            " ".join(
                part
                for part in (
                    tickers,
                    "plain language SEC filing evidence canonical financial terms",
                    " ".join(_dedupe_strings([*terms, *metric_terms, *semantic_terms])[:10]),
                )
                if part
            ),
            *_paraphrase_query_rewrites(case, semantic_terms=semantic_terms),
        ]
        return _dedupe_strings([query for query in queries if query])[:6] or [base]

    expansions: list[str] = []
    expansions.extend(terms[:8])
    expansions.extend(metric_terms[:8])
    expansions.extend(semantic_terms)
    max_expansion_terms = 10 if category == "exact_lookup" else 16
    deduped_terms = _dedupe_strings(expansions)[:max_expansion_terms]
    scoped_suffix = " ".join(part for part in (tickers, " ".join(deduped_terms)) if part).strip()
    queries = [base]
    if scoped_suffix:
        queries.append(f"{base} {scoped_suffix}".strip())
    if metric_terms:
        queries.append(" ".join(part for part in (tickers, " ".join(metric_terms[:8])) if part).strip())
    if category == "sector_depth" and deduped_terms:
        queries.append(" ".join(part for part in (tickers, " ".join(deduped_terms[:12])) if part).strip())
    return _dedupe_strings([query for query in queries if query])[:4] or [base]


def _semantic_expansion_terms(text: str) -> list[str]:
    synonym_groups = [
        (
            ("capex", "capital expenditure", "property and equipment"),
            ["capital expenditures", "additions to property and equipment", "purchases of property and equipment"],
        ),
        (
            ("credit", "borrower", "loan", "higher rates", "sour", "bank"),
            [
                "provision for credit losses",
                "allowance for credit losses",
                "net charge-offs",
                "nonperforming loans",
                "credit quality",
                "interest rates",
            ],
        ),
        (
            ("ai", "compute", "server", "cloud", "buildout", "data center", "infrastructure"),
            [
                "accelerated computing",
                "data center infrastructure",
                "cloud infrastructure",
                "server demand",
                "networking",
                "GPUs",
                "remaining performance obligations",
            ],
        ),
        (
            ("utility", "utilities", "electricity", "power", "load", "transmission", "regulated"),
            [
                "load growth",
                "power demand",
                "transmission investment",
                "distribution",
                "regulated rates",
                "capital investment",
            ],
        ),
        (
            ("healthcare", "drug", "procedure", "r&d", "research and development"),
            ["product revenue", "net sales", "research and development", "procedure volume", "demand"],
        ),
        (
            ("energy", "commodity", "natural gas", "production", "backlog"),
            ["production", "capital expenditures", "free cash flow", "commodity prices", "natural gas", "backlog"],
        ),
        (
            ("consumer", "traffic", "pricing", "inventory", "margin"),
            ["net sales", "traffic", "pricing", "gross margin", "inventory", "demand"],
        ),
        (
            ("supplier", "customer", "supply chain", "upstream", "downstream", "demand transmission"),
            ["customer supplier", "upstream downstream", "supply chain", "demand transmission", "economic linkage"],
        ),
    ]
    expansions: list[str] = []
    lowered = str(text or "").lower()
    for triggers, additions in synonym_groups:
        if any(trigger in lowered for trigger in triggers):
            expansions.extend(additions)
    return _dedupe_strings(expansions)


def _relationship_query_rewrites(case: Mapping[str, Any], *, semantic_terms: list[str]) -> list[str]:
    text = " ".join(
        [
            str(case.get("query") or ""),
            " ".join(str(item) for item in case.get("terms_any") or []),
            " ".join(str(item) for item in case.get("metric_terms_any") or []),
        ]
    ).lower()
    tickers = " ".join(str(item).upper() for item in case.get("tickers") or [])
    queries: list[str] = []
    if any(term in text for term in ("cloud", "hyperscaler", "ai", "server", "networking", "gpu", "data center")):
        queries.append(
            " ".join(
                part
                for part in (
                    tickers,
                    "cloud capex data center infrastructure AI supplier revenue demand backlog server networking GPUs",
                )
                if part
            )
        )
        queries.append(
            " ".join(
                part
                for part in (
                    tickers,
                    "hyperscaler capital expenditures remaining performance obligations supplier demand transmission",
                )
                if part
            )
        )
    if any(term in text for term in ("power", "electricity", "load", "transmission", "generation", "utilities")):
        queries.append(
            " ".join(
                part
                for part in (
                    tickers,
                    "data center electricity load growth power generation grid transmission utility capital investment",
                )
                if part
            )
        )
        queries.append(
            " ".join(
                part
                for part in (
                    tickers,
                    "regulated utility demand transmission generation capacity capital expenditures rates",
                )
                if part
            )
        )
    if any(term in text for term in ("credit", "deposit", "rate", "loan", "bank")):
        queries.append(
            " ".join(
                part
                for part in (
                    tickers,
                    "interest rates deposit beta loan demand credit losses provision capital market transmission",
                )
                if part
            )
        )
    if semantic_terms:
        queries.append(" ".join(part for part in (tickers, " ".join(semantic_terms[:10])) if part))
    return queries


def _paraphrase_query_rewrites(case: Mapping[str, Any], *, semantic_terms: list[str]) -> list[str]:
    text = " ".join(
        [
            str(case.get("query") or ""),
            " ".join(str(item) for item in case.get("terms_any") or []),
            " ".join(str(item) for item in case.get("metric_terms_any") or []),
        ]
    ).lower()
    tickers = " ".join(str(item).upper() for item in case.get("tickers") or [])
    queries: list[str] = []
    if any(term in text for term in ("borrower", "loan", "sour", "weaken", "credit", "higher rates")):
        queries.append(
            " ".join(
                part
                for part in (
                    tickers,
                    "borrowers weaken loans sour higher rates provision for credit losses allowance for credit losses net charge-offs nonperforming loans",
                )
                if part
            )
        )
        queries.append(
            " ".join(part for part in (tickers, "credit quality loan losses interest rates allowance net charge-offs") if part)
        )
    if any(term in text for term in ("compute", "server", "buildout", "ai", "cloud", "infrastructure", "chip")):
        queries.append(
            " ".join(
                part
                for part in (
                    tickers,
                    "accelerated compute buildout server demand cloud infrastructure spending data center capital expenditures GPUs networking",
                )
                if part
            )
        )
        queries.append(
            " ".join(
                part
                for part in (
                    tickers,
                    "AI infrastructure revenue demand backlog remaining performance obligations capital expenditures",
                )
                if part
            )
        )
    if semantic_terms:
        queries.append(" ".join(part for part in (tickers, " ".join(semantic_terms[:10])) if part))
    return queries


def _should_add_relationship_context(row: Mapping[str, Any]) -> bool:
    tags = set(_intent_tags_for_evidence(row))
    body = _row_body_text(row).lower()
    if {"supply_chain", "customer_supplier"} & tags and any(
        phrase in body for phrase in ("supplier", "customer", "supply chain", "upstream", "downstream")
    ):
        return True
    if "power_load" in tags and any(
        phrase in body for phrase in ("data center", "electricity", "load", "transmission", "generation", "power")
    ):
        return True
    if "ai_infrastructure" in tags and any(
        phrase in body for phrase in ("data center", "server", "networking", "gpu", "customer", "supplier", "demand", "backlog")
    ):
        return True
    if "capex" in tags and ("revenue" in tags or "demand" in tags or "backlog" in tags) and any(
        phrase in body for phrase in ("demand", "backlog", "customer", "supplier", "server", "networking", "data center")
    ):
        return True
    text = body
    return any(
        phrase in text
        for phrase in (
            "supplier",
            "customer",
            "supply chain",
            "upstream",
            "downstream",
            "data center",
            "transmission",
            "generation",
            "networking",
        )
    )


def _should_add_paraphrase_context(row: Mapping[str, Any]) -> bool:
    tags = set(_intent_tags_for_evidence(row))
    body = _row_body_text(row).lower()
    if "credit_cycle" in tags and any(phrase in body for phrase in ("credit", "loan", "allowance", "charge-off", "provision")):
        return True
    if "ai_infrastructure" in tags and any(
        phrase in body for phrase in ("ai", "artificial intelligence", "accelerated", "data center", "server", "networking", "gpu")
    ):
        return True
    if "power_load" in tags and any(phrase in body for phrase in ("power", "electricity", "load", "transmission", "generation")):
        return True
    if "healthcare_product" in tags and any(phrase in body for phrase in ("product", "procedure", "patient", "research and development", "r&d")):
        return True
    if "energy_commodity" in tags and any(phrase in body for phrase in ("commodity", "natural gas", "oil", "production", "lng")):
        return True
    if "consumer_demand" in tags and any(phrase in body for phrase in ("traffic", "pricing", "inventory", "consumer", "demand")):
        return True
    return False


def _intent_tags_for_evidence(row: Mapping[str, Any]) -> list[str]:
    return _intent_tags_from_text(_row_context_text(row))


def _intent_tags_for_object(row: Mapping[str, Any]) -> list[str]:
    fields = [
        str(row.get("object_type") or ""),
        str(row.get("metric_name") or ""),
        str(row.get("metric_family") or ""),
        str(row.get("title") or ""),
        str(row.get("row_label") or ""),
        str(row.get("column_label") or ""),
        str(row.get("preview") or ""),
        str(row.get("claim_text") or ""),
        str(row.get("section") or ""),
    ]
    tags = _intent_tags_from_text(" ".join(fields))
    object_type = str(row.get("object_type") or "")
    if object_type:
        tags.append(object_type)
    return _dedupe_strings(tags)


def _case_intent_tags(case: Mapping[str, Any]) -> list[str]:
    fields = [
        str(case.get("query") or ""),
        " ".join(str(item) for item in case.get("terms_any") or []),
        " ".join(str(item) for item in case.get("metric_terms_any") or []),
        str(case.get("category") or ""),
    ]
    return _intent_tags_from_text(" ".join(fields))


def _intent_tags_from_text(text: str) -> list[str]:
    lowered = str(text or "").lower()
    rules = [
        ("capex", ("capex", "capital expenditure", "capital expenditures", "property and equipment")),
        ("revenue", ("revenue", "net sales", "sales")),
        ("margin", ("margin", "gross margin", "operating margin")),
        ("backlog", ("backlog", "remaining performance obligations", "rpo")),
        ("cash_flow", ("cash flow", "free cash flow", "operating activities")),
        ("credit_cycle", ("credit loss", "credit losses", "allowance", "charge-off", "charge off", "nonperforming", "loan")),
        ("deposits_rates", ("deposit", "net interest income", "interest rate", "rate")),
        ("ai_infrastructure", ("ai", "artificial intelligence", "accelerated computing", "gpu", "data center", "server", "networking", "cloud")),
        ("power_load", ("power", "electricity", "load", "transmission", "generation", "regulated rates", "utility", "utilities")),
        ("healthcare_product", ("product revenue", "drug", "procedure", "patient", "research and development", "r&d")),
        ("energy_commodity", ("commodity", "natural gas", "oil", "production", "lng", "drilling")),
        ("consumer_demand", ("traffic", "pricing", "inventory", "consumer", "demand")),
        ("supply_chain", ("supply chain", "supplier", "supply", "inventory", "components")),
        ("customer_supplier", ("customer", "supplier", "partner", "channel")),
        ("demand", ("demand", "volume", "orders", "booking", "bookings")),
        ("risk", ("risk", "uncertainty", "litigation", "regulatory")),
    ]
    tags: list[str] = []
    for tag, triggers in rules:
        if any(trigger in lowered for trigger in triggers):
            tags.append(tag)
    return _dedupe_strings(tags)


def _default_vector_role(vector_kind: str) -> str:
    return {
        "narrative_chunk": "filing_narrative_context",
        "table_chunk": "tabular_fact_context",
        "metric_row": "metric_exact_value_context",
        "table_row": "table_exact_value_context",
        "claim_object": "structured_claim_context",
        "relationship_context": "economic_linkage_context",
        "paraphrase_context": "plain_language_context",
    }.get(str(vector_kind or ""), "structured_context")


def _default_semantic_scope(vector_kind: str) -> str:
    return {
        "narrative_chunk": "filing_narrative",
        "table_chunk": "financial_table",
        "metric_row": "metric",
        "table_row": "financial_table",
        "claim_object": "claim",
        "relationship_context": "relationship",
        "paraphrase_context": "paraphrase",
    }.get(str(vector_kind or ""), "general")


def _relationship_role_for_row(row: Mapping[str, Any], intent_tags: list[str]) -> str:
    tags = set(intent_tags)
    text = _row_context_text(row).lower()
    if "power_load" in tags:
        return "power_load_transmission"
    if "ai_infrastructure" in tags and "capex" in tags:
        return "capex_to_supplier_demand"
    if "customer_supplier" in tags or "supply_chain" in tags:
        return "customer_supplier"
    if "deposits_rates" in tags or "credit_cycle" in tags:
        return "rate_credit_cycle"
    if "healthcare_product" in tags:
        return "product_cycle"
    if "energy_commodity" in tags:
        return "commodity_cycle"
    if "consumer_demand" in tags:
        return "consumer_demand"
    if "upstream" in text or "downstream" in text:
        return "upstream_downstream"
    return ""


def _relationship_context_vector_text(row: Mapping[str, Any], *, max_chars: int) -> str:
    tags = _intent_tags_for_evidence(row)
    relationship_role = _relationship_role_for_row(row, tags)
    bridges = _semantic_bridges_for_tags(tags)
    body = _truncate_text(str(row.get("text") or ""), max_chars)
    metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
    parts = [
        "relationship evidence",
        "economic linkage",
        "demand transmission",
        "upstream downstream",
        "customer supplier",
        relationship_role,
        " ".join(tags),
        " ".join(bridges),
        str(row.get("ticker") or ""),
        str(row.get("company") or ""),
        str(row.get("fiscal_year") or ""),
        _normalize_form_type(metadata.get("form_type") or row.get("source_type")),
        str(row.get("section") or ""),
        str(row.get("subsection") or ""),
        body,
    ]
    return _truncate_text(" | ".join(part for part in parts if part), max_chars + 700)


def _paraphrase_context_vector_text(row: Mapping[str, Any], *, max_chars: int) -> str:
    tags = _intent_tags_for_evidence(row)
    bridges = _semantic_bridges_for_tags(tags)
    body = _truncate_text(str(row.get("text") or ""), max_chars)
    metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
    parts = [
        "plain language retrieval bridge",
        "SEC filing evidence",
        "canonical financial terms",
        " ".join(tags),
        " ".join(bridges),
        str(row.get("ticker") or ""),
        str(row.get("company") or ""),
        str(row.get("fiscal_year") or ""),
        _normalize_form_type(metadata.get("form_type") or row.get("source_type")),
        str(row.get("section") or ""),
        str(row.get("subsection") or ""),
        body,
    ]
    return _truncate_text(" | ".join(part for part in parts if part), max_chars + 700)


def _semantic_bridges_for_tags(tags: list[str]) -> list[str]:
    tag_set = set(tags)
    bridges: list[str] = []
    if "credit_cycle" in tag_set:
        bridges.extend(
            [
                "borrowers weaken",
                "loans sour",
                "higher rates",
                "provision for credit losses",
                "allowance for credit losses",
                "net charge-offs",
                "nonperforming loans",
            ]
        )
    if "ai_infrastructure" in tag_set:
        bridges.extend(
            [
                "accelerated compute buildout",
                "server demand",
                "cloud infrastructure spending",
                "data center infrastructure",
                "GPUs networking",
            ]
        )
    if "capex" in tag_set:
        bridges.extend(["capital expenditures", "property and equipment additions", "infrastructure investment"])
    if "power_load" in tag_set:
        bridges.extend(["data center electricity demand", "load growth", "generation transmission grid investment"])
    if "supply_chain" in tag_set or "customer_supplier" in tag_set:
        bridges.extend(["customer supplier relationship", "upstream downstream supply chain", "demand transmission"])
    if "healthcare_product" in tag_set:
        bridges.extend(["product cycle", "procedure volume", "R&D pipeline", "net sales demand"])
    if "energy_commodity" in tag_set:
        bridges.extend(["commodity cycle", "production", "natural gas demand", "free cash flow"])
    if "consumer_demand" in tag_set:
        bridges.extend(["consumer demand", "traffic pricing", "inventory margin pressure"])
    return _dedupe_strings(bridges)


def _semantic_hit_weight(hit: Mapping[str, Any], case: Mapping[str, Any]) -> float:
    category = str(case.get("category") or "")
    vector_kind = str(hit.get("vector_kind") or "")
    semantic_scope = str(hit.get("semantic_scope") or "")
    vector_role = str(hit.get("vector_role") or "")
    hit_tags = set(_split_multi_value(hit.get("intent_tags")))
    case_tags = set(_case_intent_tags(case))
    weight = 1.0
    if category == "relationship":
        if vector_kind == "relationship_context" or semantic_scope == "relationship":
            weight += 0.35
        if vector_role == "economic_linkage_context":
            weight += 0.15
    elif category == "paraphrase":
        if vector_kind == "paraphrase_context" or semantic_scope == "paraphrase":
            weight += 0.35
        if vector_role == "plain_language_context":
            weight += 0.15
    elif category == "exact_lookup" and vector_kind in {"metric_row", "table_row", "table_chunk"}:
        weight += 0.15
    if hit_tags & case_tags:
        weight += 0.1
    return weight


def _ensure_support_list_fields(item: dict[str, Any], keys: Iterable[str]) -> None:
    for key in keys:
        value = item.get(key)
        if value is None:
            item[key] = []
        elif isinstance(value, list):
            continue
        elif key == "matched_query_indices":
            item[key] = [value]
        else:
            item[key] = _split_multi_value(value)


def _variant_has_any_count(
    variants: Iterable[Mapping[str, Any]],
    count_key: str,
    expected_values: Iterable[str],
) -> bool:
    expected = {str(value) for value in expected_values if str(value)}
    if not expected:
        return True
    for variant in variants:
        counts = variant.get(count_key) if isinstance(variant.get(count_key), Mapping) else {}
        if any(int(counts.get(value) or 0) > 0 for value in expected):
            return True
    return False


def _row_context_text(row: Mapping[str, Any]) -> str:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
    fields = [
        str(row.get("ticker") or ""),
        str(row.get("company") or ""),
        str(row.get("section") or ""),
        str(row.get("subsection") or ""),
        str(row.get("evidence_type") or ""),
        str(row.get("text") or ""),
        str(metadata.get("category_slug") or ""),
        str(metadata.get("item_code") or ""),
    ]
    return " ".join(fields)


def _row_body_text(row: Mapping[str, Any]) -> str:
    fields = [
        str(row.get("section") or ""),
        str(row.get("subsection") or ""),
        str(row.get("evidence_type") or ""),
        str(row.get("text") or ""),
    ]
    return " ".join(fields)


def _narrative_chunk_vector_text(row: Mapping[str, Any], *, max_chars: int) -> str:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
    body = str(row.get("text") or "")
    if max_chars > 0 and len(body) > max_chars:
        body = body[:max_chars]
    parts = [
        str(row.get("ticker") or ""),
        str(row.get("company") or ""),
        str(row.get("fiscal_year") or ""),
        _normalize_form_type(metadata.get("form_type") or row.get("source_type")),
        str(row.get("section") or ""),
        str(row.get("subsection") or ""),
        str(row.get("evidence_type") or ""),
        str(metadata.get("item_code") or ""),
        body,
    ]
    return " | ".join(part for part in parts if part)


def _table_chunk_vector_text(row: Mapping[str, Any], *, max_chars: int) -> str:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
    body = _truncate_text(str(row.get("text") or ""), max_chars)
    parts = [
        "table evidence",
        str(row.get("ticker") or ""),
        str(row.get("company") or ""),
        str(row.get("fiscal_year") or ""),
        _normalize_form_type(metadata.get("form_type") or row.get("source_type")),
        str(row.get("section") or ""),
        str(row.get("subsection") or ""),
        str(metadata.get("item_code") or ""),
        body,
    ]
    return " | ".join(part for part in parts if part)


def _object_vector_text(row: Mapping[str, Any], *, max_chars: int) -> str:
    object_type = str(row.get("object_type") or "")
    prefix = {
        "metric": "structured metric row",
        "table": "structured table row",
        "claim": "structured narrative claim",
    }.get(object_type, "structured object")
    fields = [
        prefix,
        str(row.get("ticker") or ""),
        str(row.get("fiscal_year") or ""),
        _normalize_form_type(row.get("form_type") or row.get("source_type")),
        str(row.get("section") or ""),
        str(row.get("subsection") or ""),
        str(row.get("metric_name") or row.get("metric_family") or row.get("title") or ""),
        str(row.get("row_label") or ""),
        str(row.get("column_label") or ""),
        str(row.get("period") or row.get("period_end") or row.get("period_type") or ""),
        str(row.get("unit") or ""),
        str(row.get("preview") or row.get("claim_text") or ""),
    ]
    return _truncate_text(" | ".join(part for part in fields if part), max_chars)


def _support_text(record: Mapping[str, Any], item: Mapping[str, Any]) -> str:
    previews = [str(text) for text in item.get("object_previews", []) if str(text).strip()]
    base = str(record.get("text") or "")
    return " ".join([*previews, base]).strip()


def _dedupe_strings(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = " ".join(str(value or "").split())
        key = text.lower()
        if not text or key in seen:
            continue
        out.append(text)
        seen.add(key)
    return out


def _summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    failed = [case for case in results if case.get("gate_status") != "pass"]
    by_category: dict[str, dict[str, int]] = {}
    for case in results:
        category = str(case.get("category") or "")
        by_category.setdefault(category, {"cases": 0, "pass": 0, "fail": 0})
        by_category[category]["cases"] += 1
        by_category[category]["pass" if case.get("gate_status") == "pass" else "fail"] += 1
    return {
        "case_count": len(results),
        "passed_case_count": len(results) - len(failed),
        "failed_case_count": len(failed),
        "failed_case_ids": [case.get("case_id") for case in failed],
        "by_category": by_category,
        "mean_hybrid_usable_evidence_rows": _mean(
            int(case["variants"]["hybrid_rrf"].get("usable_evidence_rows") or 0) for case in results
        ),
        "mean_bm25_usable_evidence_rows": _mean(
            int(case["variants"]["bm25"].get("usable_evidence_rows") or 0) for case in results
        ),
        "mean_object_bm25_usable_evidence_rows": _mean(
            int(case["variants"]["object_bm25"].get("usable_evidence_rows") or 0) for case in results
        ),
        "mean_object_bm25_metric_evidence_rows": _mean(
            int(case["variants"]["object_bm25"].get("metric_evidence_rows") or 0) for case in results
        ),
        "mean_milvus_usable_evidence_rows": _mean(
            int(case["variants"]["milvus_semantic"].get("usable_evidence_rows") or 0) for case in results
        ),
        "object_bm25_enabled_case_count": sum(
            1 for case in results if not bool(case["variants"]["object_bm25"].get("skipped"))
        ),
        "exact_object_metric_hit_pass_count": sum(
            1 for case in results if bool((case.get("gates") or {}).get("exact_object_metric_hit"))
        ),
    }


def _render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary") or {}
    lines = [
        f"# Milvus Retrieval A/B: {report.get('run_id')}",
        "",
        f"- Gate: `{report.get('gate_status')}`",
        f"- Diagnostic only: `{str(report.get('diagnostic_only')).lower()}`",
        f"- Cases: `{summary.get('case_count')}`",
        f"- Passed: `{summary.get('passed_case_count')}`",
        f"- Failed: `{summary.get('failed_case_count')}`",
        f"- Collection rows: `{(report.get('inputs') or {}).get('collection_rows')}`",
        f"- Embedding: `{(report.get('inputs') or {}).get('embedding_model')}` on `{(report.get('inputs') or {}).get('embedding_device')}`",
        "",
        "## Case Results",
        "",
        "| Case | Category | Gate | BM25 usable | Object usable | Object metric | Milvus usable | Hybrid usable | Hybrid tickers | Gates |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for case in report.get("cases") or []:
        variants = case.get("variants") or {}
        gates = case.get("gates") or {}
        failed_gates = [name for name, value in gates.items() if not value]
        lines.append(
            "| {case_id} | {category} | `{gate}` | `{bm25}` | `{object_usable}` | `{object_metric}` | `{milvus}` | `{hybrid}` | `{tickers}` | {gates} |".format(
                case_id=case.get("case_id"),
                category=case.get("category"),
                gate=case.get("gate_status"),
                bm25=(variants.get("bm25") or {}).get("usable_evidence_rows"),
                object_usable=(variants.get("object_bm25") or {}).get("usable_evidence_rows"),
                object_metric=(variants.get("object_bm25") or {}).get("metric_evidence_rows"),
                milvus=(variants.get("milvus_semantic") or {}).get("usable_evidence_rows"),
                hybrid=(variants.get("hybrid_rrf") or {}).get("usable_evidence_rows"),
                tickers=(variants.get("hybrid_rrf") or {}).get("ticker_coverage_count"),
                gates=", ".join(failed_gates) if failed_gates else "pass",
            )
        )
    lines.extend(["", "## Notes", ""])
    lines.append("- This run is retrieval-only; it does not modify full-chain routing.")
    lines.append("- Promotion requires semantic/relationship/paraphrase evidence gains without exact lookup regression.")
    return "\n".join(lines).rstrip() + "\n"


def _stdout_summary(report: Mapping[str, Any], json_path: Path, md_path: Path) -> dict[str, Any]:
    return {
        "run_id": report.get("run_id"),
        "gate_status": report.get("gate_status"),
        "diagnostic_only": report.get("diagnostic_only"),
        "summary": report.get("summary"),
        "json_path": str(json_path),
        "md_path": str(md_path),
    }


def _default_run_id() -> str:
    return time.strftime("%Y%m%d_fin_agent_milvus_retrieval_ab_v0_3")


def _collection_name(run_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_]", "_", run_id)
    return f"fin_ab_{safe}_{int(time.time())}"[:250]


def _normalize_form_type(value: Any) -> str:
    return str(value or "").upper().strip().replace("10K", "10-K").replace("10Q", "10-Q")


def _item_code_from_section(value: Any) -> str:
    text = str(value or "")
    match = re.search(r"\bitem\s+(\d+[A-Z]?)\b", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).upper()
    lowered = text.lower()
    if "exhibit" in lowered and "99" in lowered:
        return "exhibit_99_1"
    return ""


def _vector_kind_for_object_type(value: Any) -> str:
    return {
        "metric": "metric_row",
        "table": "table_row",
        "claim": "claim_object",
    }.get(str(value or ""), "")


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _preview(text: str, max_chars: int = 280) -> str:
    normalized = " ".join(str(text or "").split())
    return normalized[:max_chars] + ("..." if len(normalized) > max_chars else "")


def _truncate_text(text: str, max_chars: int) -> str:
    text = str(text or "")
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars]


def _count_by(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for value in _split_multi_value(row.get(key)):
            text = str(value or "").strip()
            if not text:
                continue
            counts[text] = counts.get(text, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _split_multi_value(raw_value: Any) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, (list, tuple, set)):
        values: list[str] = []
        for item in raw_value:
            values.extend(_split_multi_value(item))
        return values
    return [
        value.strip()
        for value in re.split(r"[,|]", str(raw_value or ""))
        if value.strip()
    ]


def _mean(values: Iterable[int]) -> float:
    items = list(values)
    return round(sum(items) / len(items), 4) if items else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
