"""Rebuild a local Milvus Lite collection from exported Milvus parquet shards.

Milvus Lite directories built on Linux are not always safe to open directly on
Windows. This tool treats the collection data parquet files as the portable
artifact and creates a fresh local Milvus Lite collection without re-embedding.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MILVUS_DEPS_PATH = Path("Z:/FIN_Insight_Agent_artifacts/python_deps/milvus_lite")
DEFAULT_MILVUS_DIR = Path("Z:/FIN_Insight_Agent_artifacts/milvus")
DEFAULT_OUTPUT_DIR = REPO_ROOT / "eval" / "sec_cases" / "outputs" / "milvus_retrieval_ab"
SCHEMA_VERSION = "fin_agent_milvus_lite_parquet_rebuild_v0.1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild Milvus Lite from exported parquet shards.")
    parser.add_argument("--parquet-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--milvus-deps-path", type=Path, default=DEFAULT_MILVUS_DEPS_PATH)
    parser.add_argument("--milvus-dir", type=Path, default=DEFAULT_MILVUS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--insert-batch-size", type=int, default=4096)
    parser.add_argument("--parquet-batch-size", type=int, default=4096)
    parser.add_argument("--progress-interval", type=int, default=65536)
    parser.add_argument("--defer-index-build", action="store_true", default=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.time()
    _install_import_paths(args.milvus_deps_path)
    _patch_windows_milvus_lite_manifest_replace()

    import pyarrow.parquet as pq
    from pymilvus import DataType, MilvusClient

    from eval_milvus_retrieval_ab import (  # noqa: PLC0415
        _close_milvus_client,
        _collection_name,
        _create_collection,
        _create_embedding_index,
    )

    parquet_files = sorted(args.parquet_dir.glob("*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(f"No parquet shards found under {args.parquet_dir}")

    dim = _infer_embedding_dim(parquet_files[0], pq)
    run_dir = args.output_dir / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    milvus_db = args.milvus_dir / args.run_id / "milvus_lite.db"
    milvus_db.parent.mkdir(parents=True, exist_ok=True)
    collection_name = _collection_name(args.run_id)
    client = MilvusClient(uri=str(milvus_db))

    counters: Counter[str] = Counter()
    vector_kind_counts: Counter[str] = Counter()
    form_counts: Counter[str] = Counter()
    source_tier_counts: Counter[str] = Counter()
    fiscal_year_counts: Counter[str] = Counter()
    tickers: set[str] = set()
    pending: list[dict[str, Any]] = []

    try:
        _create_collection(
            client,
            collection_name,
            dim,
            DataType,
            MilvusClient,
            defer_index_build=bool(args.defer_index_build),
        )
        for parquet_path in parquet_files:
            parquet_file = pq.ParquetFile(parquet_path)
            for record_batch in parquet_file.iter_batches(batch_size=max(1, int(args.parquet_batch_size))):
                rows = record_batch.to_pylist()
                for row in rows:
                    record = _milvus_insert_record(row)
                    pending.append(record)
                    counters["rows_seen"] += 1
                    ticker = str(record.get("ticker") or "").upper()
                    if ticker:
                        tickers.add(ticker)
                    vector_kind_counts[str(record.get("vector_kind") or "")] += 1
                    form_counts[str(record.get("form_type") or "")] += 1
                    source_tier_counts[str(record.get("source_tier") or "")] += 1
                    fiscal_year_counts[str(record.get("fiscal_year") or "")] += 1
                    if len(pending) >= max(1, int(args.insert_batch_size)):
                        client.insert(collection_name, pending)
                        counters["rows_inserted"] += len(pending)
                        pending.clear()
                _print_progress(counters, args.progress_interval, started, batch_len=len(rows))
        if pending:
            client.insert(collection_name, pending)
            counters["rows_inserted"] += len(pending)
            pending.clear()
        if args.defer_index_build:
            index_started = time.time()
            _create_embedding_index(client, collection_name, MilvusClient)
            counters["index_build_elapsed_ms"] = int((time.time() - index_started) * 1000)
        stats: dict[str, Any] = {}
        try:
            stats = client.get_collection_stats(collection_name=collection_name)
        except TypeError:
            stats = client.get_collection_stats(collection_name)
    finally:
        _close_milvus_client(client)

    report = {
        "schema_version": SCHEMA_VERSION,
        "run_id": args.run_id,
        "gate_status": "pass",
        "diagnostic_only": True,
        "elapsed_ms": int((time.time() - started) * 1000),
        "inputs": {
            "parquet_dir": str(args.parquet_dir),
            "parquet_file_count": len(parquet_files),
            "milvus_db": str(milvus_db),
            "collection_name": collection_name,
            "insert_batch_size": int(args.insert_batch_size),
            "parquet_batch_size": int(args.parquet_batch_size),
            "defer_index_build": bool(args.defer_index_build),
            "embedding_dim": int(dim),
        },
        "outputs": {
            "rows_seen": int(counters["rows_seen"]),
            "rows_inserted": int(counters["rows_inserted"]),
            "collection_stats": stats,
            "unique_tickers": len(tickers),
            "vector_kind_counts": dict(sorted(vector_kind_counts.items())),
            "form_counts": dict(sorted(form_counts.items())),
            "source_tier_counts": dict(sorted(source_tier_counts.items())),
            "fiscal_year_counts": dict(sorted(fiscal_year_counts.items())),
            "index_build_elapsed_ms": int(counters["index_build_elapsed_ms"]),
        },
    }
    json_path = run_dir / "milvus_parquet_rebuild_summary.json"
    md_path = run_dir / "milvus_parquet_rebuild_summary.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(json.dumps({"run_id": args.run_id, "gate_status": "pass", "json_path": str(json_path)}, ensure_ascii=False))
    return 0


def _install_import_paths(milvus_deps_path: Path) -> None:
    for path in (REPO_ROOT / "scripts" / "eval_retrieval", REPO_ROOT / "src", milvus_deps_path):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


def _patch_windows_milvus_lite_manifest_replace() -> None:
    if os.name != "nt":
        return
    try:
        import milvus_lite.storage.manifest as manifest_module

        manifest_module.os.rename = manifest_module.os.replace
    except Exception:
        return


def _infer_embedding_dim(parquet_path: Path, pq_module: Any) -> int:
    table = pq_module.read_table(parquet_path, columns=["embedding"])
    if table.num_rows <= 0:
        raise ValueError(f"First parquet shard has no rows: {parquet_path}")
    embedding = table.slice(0, 1).to_pylist()[0]["embedding"]
    return len(embedding)


def _milvus_insert_record(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "vector_id": str(row.get("vector_id") or ""),
        "evidence_id": str(row.get("evidence_id") or ""),
        "embedding": row.get("embedding") or [],
        "ticker": str(row.get("ticker") or "").upper(),
        "fiscal_year": int(row.get("fiscal_year") or 0),
        "form_type": str(row.get("form_type") or ""),
        "source_tier": str(row.get("source_tier") or ""),
        "item_code": str(row.get("item_code") or ""),
        "category_slug": str(row.get("category_slug") or ""),
        "period_type": str(row.get("period_type") or ""),
        "contains_table": bool(row.get("contains_table")),
        "vector_kind": str(row.get("vector_kind") or ""),
        "vector_role": str(row.get("vector_role") or ""),
        "semantic_scope": str(row.get("semantic_scope") or ""),
        "intent_tags": str(row.get("intent_tags") or "")[:500],
        "relationship_role": str(row.get("relationship_role") or ""),
        "object_type": str(row.get("object_type") or ""),
        "preview": str(row.get("preview") or "")[:4000],
    }


def _print_progress(counters: Counter[str], progress_interval: int, started: float, *, batch_len: int) -> None:
    progress_interval = max(1, int(progress_interval or 1))
    rows_seen = int(counters["rows_seen"])
    if rows_seen and rows_seen % progress_interval < max(1, int(batch_len)):
        elapsed = max(0.001, time.time() - started)
        print(
            json.dumps(
                {
                    "milvus_parquet_rebuild_progress": {
                        "rows_seen": rows_seen,
                        "rows_inserted": int(counters["rows_inserted"]),
                        "elapsed_sec": round(elapsed, 3),
                        "rows_per_sec": round(float(rows_seen) / elapsed, 3),
                    }
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
            flush=True,
        )


def _render_markdown(report: dict[str, Any]) -> str:
    inputs = report.get("inputs") or {}
    outputs = report.get("outputs") or {}
    lines = [
        f"# Milvus Parquet Rebuild: {report.get('run_id')}",
        "",
        f"- Gate: `{report.get('gate_status')}`",
        f"- Elapsed ms: `{report.get('elapsed_ms')}`",
        f"- Parquet files: `{inputs.get('parquet_file_count')}`",
        f"- Rows seen: `{outputs.get('rows_seen')}`",
        f"- Rows inserted: `{outputs.get('rows_inserted')}`",
        f"- Collection stats: `{outputs.get('collection_stats')}`",
        f"- Milvus DB: `{inputs.get('milvus_db')}`",
        f"- Collection: `{inputs.get('collection_name')}`",
        f"- Index build elapsed ms: `{outputs.get('index_build_elapsed_ms')}`",
        "",
        "## Vector Kinds",
        "",
    ]
    for key, value in (outputs.get("vector_kind_counts") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
