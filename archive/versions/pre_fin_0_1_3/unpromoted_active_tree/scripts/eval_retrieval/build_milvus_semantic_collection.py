"""Build a Milvus Lite semantic collection from evidence JSONL in streaming mode.

This is the full-scale build path for audited evidence collections. It reuses
the retrieval A/B vector text contract, but avoids materializing every evidence
row and typed vector before embedding starts.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MILVUS_DEPS_PATH = Path("Z:/FIN_Insight_Agent_artifacts/python_deps/milvus_lite")
DEFAULT_MILVUS_DIR = Path("Z:/FIN_Insight_Agent_artifacts/milvus")
DEFAULT_OUTPUT_DIR = REPO_ROOT / "eval" / "sec_cases" / "outputs" / "milvus_retrieval_ab"
DEFAULT_EMBEDDING_MODEL = Path(
    "D:/hf_cache/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181"
)
SCHEMA_VERSION = "fin_agent_milvus_streaming_build_v0.1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Streaming Milvus semantic collection builder.")
    parser.add_argument("--evidence-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--milvus-deps-path", type=Path, default=DEFAULT_MILVUS_DEPS_PATH)
    parser.add_argument("--milvus-dir", type=Path, default=DEFAULT_MILVUS_DIR)
    parser.add_argument("--embedding-model", type=Path, default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--device", default=os.environ.get("MILVUS_AB_EMBED_DEVICE", "cuda"))
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument("--defer-index-build", action="store_true")
    parser.add_argument("--collection-max-rows", type=int, default=0)
    parser.add_argument("--embedding-batch-size", type=int, default=256)
    parser.add_argument("--embedding-max-seq-length", type=int, default=512)
    parser.add_argument("--vector-text-max-chars", type=int, default=1800)
    parser.add_argument("--insert-batch-size", type=int, default=4096)
    parser.add_argument("--progress-interval", type=int, default=8192)
    parser.add_argument("--load-after-build", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.time()
    run_dir = args.output_dir / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    args.milvus_dir.mkdir(parents=True, exist_ok=True)

    _install_import_paths(args.milvus_deps_path)
    from pymilvus import DataType, MilvusClient
    from sentence_transformers import SentenceTransformer
    import torch

    if hasattr(torch, "set_float32_matmul_precision"):
        try:
            torch.set_float32_matmul_precision("high")
        except Exception:
            pass

    device = str(args.device or "cuda")
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"
    model = SentenceTransformer(str(args.embedding_model), device=device)
    embedding_fp16_enabled = False
    if args.fp16 and device == "cuda":
        embedding_fp16_enabled = _enable_model_fp16(model)
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
    pending_vectors: list[dict[str, Any]] = []
    pending_insert: list[dict[str, Any]] = []

    try:
        _create_collection(
            client,
            collection_name,
            dim,
            DataType,
            MilvusClient,
            defer_index_build=bool(args.defer_index_build),
        )
        for row in _iter_evidence_rows(args.evidence_path):
            counters["evidence_rows_seen"] += 1
            evidence_id = str(row.get("evidence_id") or "")
            if not evidence_id:
                counters["evidence_rows_without_id"] += 1
                continue
            ticker = str(row.get("ticker") or "").upper()
            if ticker:
                tickers.add(ticker)
            form_counts[_normalize_form_type(row.get("form_type") or row.get("source_type"))] += 1
            source_tier_counts[str(row.get("source_tier") or "")] += 1
            fiscal_year_counts[str(row.get("fiscal_year") or "")] += 1

            vector_rows = _build_vector_records(evidence_rows=[row], object_rows=[], max_chars=args.vector_text_max_chars)
            for vector_row in vector_rows:
                pending_vectors.append(vector_row)
                vector_kind_counts[str(vector_row.get("vector_kind") or "")] += 1
            counters["vector_rows_built"] += len(vector_rows)

            if len(pending_vectors) >= max(1, int(args.embedding_batch_size)):
                _encode_and_stage(
                    client=client,
                    collection_name=collection_name,
                    model=model,
                    pending_vectors=pending_vectors,
                    pending_insert=pending_insert,
                    counters=counters,
                    insert_batch_size=args.insert_batch_size,
                    progress_interval=args.progress_interval,
                    started=started,
                )
            if int(args.collection_max_rows or 0) > 0 and counters["evidence_rows_seen"] >= int(args.collection_max_rows):
                break

        _encode_and_stage(
            client=client,
            collection_name=collection_name,
            model=model,
            pending_vectors=pending_vectors,
            pending_insert=pending_insert,
            counters=counters,
            insert_batch_size=args.insert_batch_size,
            progress_interval=args.progress_interval,
            started=started,
            force=True,
        )
        if pending_insert:
            client.insert(collection_name, pending_insert)
            counters["vectors_inserted"] += len(pending_insert)
            pending_insert.clear()
        if args.defer_index_build:
            index_started = time.time()
            _create_embedding_index(client, collection_name, MilvusClient)
            counters["index_build_elapsed_ms"] = int((time.time() - index_started) * 1000)
        if args.load_after_build:
            _load_collection_for_search(client, collection_name)
    finally:
        _close_milvus_client(client)

    report = {
        "schema_version": SCHEMA_VERSION,
        "run_id": args.run_id,
        "gate_status": "pass",
        "diagnostic_only": True,
        "elapsed_ms": int((time.time() - started) * 1000),
        "inputs": {
            "evidence_path": str(args.evidence_path),
            "milvus_db": str(milvus_db),
            "collection_name": collection_name,
            "embedding_model": str(args.embedding_model),
            "embedding_device": device,
            "embedding_fp16_enabled": embedding_fp16_enabled,
            "defer_index_build": bool(args.defer_index_build),
            "collection_max_rows": int(args.collection_max_rows),
            "embedding_batch_size": int(args.embedding_batch_size),
            "insert_batch_size": int(args.insert_batch_size),
            "progress_interval": int(args.progress_interval),
            "vector_text_max_chars": int(args.vector_text_max_chars),
            "embedding_max_seq_length": int(args.embedding_max_seq_length),
        },
        "outputs": {
            "evidence_rows_seen": int(counters["evidence_rows_seen"]),
            "evidence_rows_without_id": int(counters["evidence_rows_without_id"]),
            "vector_rows_built": int(counters["vector_rows_built"]),
            "vectors_encoded": int(counters["vectors_encoded"]),
            "vectors_inserted": int(counters["vectors_inserted"]),
            "unique_tickers": len(tickers),
            "vector_kind_counts": dict(sorted(vector_kind_counts.items())),
            "form_counts": dict(sorted(form_counts.items())),
            "source_tier_counts": dict(sorted(source_tier_counts.items())),
            "fiscal_year_counts": dict(sorted(fiscal_year_counts.items())),
            "index_build_elapsed_ms": int(counters["index_build_elapsed_ms"]),
            "cuda_peak_memory_allocated_mb": _cuda_peak_memory_mb(torch, device, "allocated"),
            "cuda_peak_memory_reserved_mb": _cuda_peak_memory_mb(torch, device, "reserved"),
        },
    }
    json_path = run_dir / "milvus_streaming_build_summary.json"
    md_path = run_dir / "milvus_streaming_build_summary.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    print(json.dumps({"run_id": args.run_id, "gate_status": "pass", "json_path": str(json_path)}, ensure_ascii=False))
    return 0


def _install_import_paths(milvus_deps_path: Path) -> None:
    for path in (REPO_ROOT / "src", REPO_ROOT / "scripts" / "eval_retrieval", milvus_deps_path):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


from eval_milvus_retrieval_ab import (  # noqa: E402
    _build_vector_records,
    _close_milvus_client,
    _collection_name,
    _create_collection,
    _create_embedding_index,
    _enable_model_fp16,
    _load_collection_for_search,
    _normalize_form_type,
)


def _iter_evidence_rows(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid evidence JSONL at {path}:{line_number}") from exc
            if isinstance(row, dict):
                yield row


def _encode_and_stage(
    *,
    client: Any,
    collection_name: str,
    model: Any,
    pending_vectors: list[dict[str, Any]],
    pending_insert: list[dict[str, Any]],
    counters: Counter[str],
    insert_batch_size: int,
    progress_interval: int,
    started: float,
    force: bool = False,
) -> None:
    if not force and not pending_vectors:
        return
    batch = pending_vectors[:]
    if not batch:
        return
    pending_vectors.clear()
    texts = [str(row.get("vector_text") or "") for row in batch]
    embeddings = model.encode(
        texts,
        batch_size=len(batch),
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    for row, embedding in zip(batch, embeddings):
        pending_insert.append(_milvus_insert_record(row, embedding.tolist()))
    counters["vectors_encoded"] += len(batch)
    while len(pending_insert) >= max(1, int(insert_batch_size)):
        client.insert(collection_name, pending_insert[:insert_batch_size])
        counters["vectors_inserted"] += int(insert_batch_size)
        del pending_insert[:insert_batch_size]
    progress_interval = max(1, int(progress_interval or 1))
    if counters["vectors_encoded"] == len(batch) or counters["vectors_encoded"] % progress_interval < len(batch):
        elapsed = max(0.001, time.time() - started)
        print(
            json.dumps(
                {
                    "milvus_stream_progress": {
                        "vectors_encoded": int(counters["vectors_encoded"]),
                        "vectors_inserted": int(counters["vectors_inserted"]),
                        "evidence_rows_seen": int(counters["evidence_rows_seen"]),
                        "elapsed_sec": round(elapsed, 3),
                        "vectors_per_sec": round(float(counters["vectors_encoded"]) / elapsed, 3),
                    }
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
            flush=True,
        )


def _milvus_insert_record(row: dict[str, Any], embedding: list[float]) -> dict[str, Any]:
    return {
        "vector_id": str(row.get("vector_id") or ""),
        "evidence_id": str(row.get("evidence_id")),
        "embedding": embedding,
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
        "intent_tags": str(row.get("intent_tags") or "")[:500],
        "relationship_role": str(row.get("relationship_role") or ""),
        "object_type": str(row.get("object_type") or ""),
        "preview": str(row.get("preview") or "")[:4000],
    }


def _render_markdown(report: dict[str, Any]) -> str:
    inputs = report.get("inputs") or {}
    outputs = report.get("outputs") or {}
    lines = [
        f"# Milvus Streaming Build: {report.get('run_id')}",
        "",
        f"- Gate: `{report.get('gate_status')}`",
        f"- Elapsed ms: `{report.get('elapsed_ms')}`",
        f"- Evidence rows: `{outputs.get('evidence_rows_seen')}`",
        f"- Vector rows: `{outputs.get('vector_rows_built')}`",
        f"- Vectors inserted: `{outputs.get('vectors_inserted')}`",
        f"- Unique tickers: `{outputs.get('unique_tickers')}`",
        f"- Milvus DB: `{inputs.get('milvus_db')}`",
        f"- Collection: `{inputs.get('collection_name')}`",
        f"- Embedding: `{inputs.get('embedding_model')}` on `{inputs.get('embedding_device')}`, fp16=`{inputs.get('embedding_fp16_enabled')}`",
        f"- Batch: embedding `{inputs.get('embedding_batch_size')}`, insert `{inputs.get('insert_batch_size')}`",
        f"- Defer index build: `{inputs.get('defer_index_build')}`",
        f"- CUDA peak allocated MB: `{outputs.get('cuda_peak_memory_allocated_mb')}`",
        f"- CUDA peak reserved MB: `{outputs.get('cuda_peak_memory_reserved_mb')}`",
        "",
        "## Vector Kinds",
        "",
    ]
    for key, value in (outputs.get("vector_kind_counts") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    return "\n".join(lines)


def _cuda_peak_memory_mb(torch_module: Any, device: str, kind: str) -> int:
    if device != "cuda":
        return 0
    cuda = getattr(torch_module, "cuda", None)
    if cuda is None:
        return 0
    try:
        if kind == "reserved":
            return int(cuda.max_memory_reserved() / (1024 * 1024))
        return int(cuda.max_memory_allocated() / (1024 * 1024))
    except Exception:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
