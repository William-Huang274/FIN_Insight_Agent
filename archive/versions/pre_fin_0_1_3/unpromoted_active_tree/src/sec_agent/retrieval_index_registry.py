from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


RETRIEVAL_INDEX_SNAPSHOT_SCHEMA_VERSION = "finsight_retrieval_index_snapshot_v0_1"
RETRIEVAL_INDEX_SOURCE_LINEAGE_SCHEMA_VERSION = "finsight_retrieval_index_source_lineage_v0_1"
RETRIEVAL_INDEX_REGISTRY_SUMMARY_SCHEMA_VERSION = "finsight_retrieval_index_registry_summary_v0_1"


INDEX_METADATA_PATTERNS: tuple[str, ...] = (
    "data/indexes/**/metadata.json",
    "data/indexes/**/index_metadata.json",
)

MILVUS_RUNTIME_CONFIGS: tuple[str, ...] = (
    "configs/runtime/milvus_runtime_603_local_v0_1.json",
)

TEMPORARY_PATH_TOKENS: tuple[str, ...] = (
    "/.tmp",
    "/_tmp_",
    "\\.tmp",
    "\\_tmp_",
)


def build_retrieval_index_registry(
    repo_root: str | Path,
    *,
    generated_at: str | None = None,
    milvus_config_paths: Sequence[str] = MILVUS_RUNTIME_CONFIGS,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    generated_at = generated_at or _utc_now()
    parser_artifact_index = _parser_artifact_index(root)
    snapshots: list[dict[str, Any]] = []
    lineages: list[dict[str, Any]] = []

    for metadata_path in discover_index_metadata_paths(root):
        metadata = _read_json(metadata_path)
        if not metadata:
            continue
        snapshot = _snapshot_from_index_metadata(root, metadata_path, metadata, generated_at=generated_at)
        snapshots.append(snapshot)
        lineages.extend(
            _lineages_for_index_snapshot(
                root,
                snapshot,
                metadata,
                parser_artifact_index=parser_artifact_index,
                generated_at=generated_at,
            )
        )

    for relative_path in milvus_config_paths:
        path = (root / relative_path).resolve()
        if not path.exists():
            continue
        config = _read_json(path)
        if not config:
            continue
        snapshot = _snapshot_from_milvus_config(root, path, config, generated_at=generated_at)
        snapshots.append(snapshot)
        lineages.extend(
            _lineages_for_milvus_config(root, snapshot, config, parser_artifact_index=parser_artifact_index, generated_at=generated_at)
        )

    summary = build_retrieval_index_registry_summary(
        snapshots=snapshots,
        lineages=lineages,
        generated_at=generated_at,
    )
    return {"snapshots": snapshots, "lineages": lineages, "summary": summary}


def discover_index_metadata_paths(repo_root: str | Path) -> list[Path]:
    root = Path(repo_root).resolve()
    paths: set[Path] = set()
    for pattern in INDEX_METADATA_PATTERNS:
        for path in root.glob(pattern):
            if path.is_file() and not _is_temporary_path(root, path):
                paths.add(path.resolve())
    return sorted(paths)


def build_retrieval_index_registry_summary(
    *,
    snapshots: Sequence[Mapping[str, Any]],
    lineages: Sequence[Mapping[str, Any]],
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or _utc_now()
    missing_sources = [row for row in lineages if row.get("source_artifact_status") == "missing_source_artifact"]
    missing_record_files = [row for row in snapshots if row.get("missing_record_file_count")]
    status = "pass" if not missing_sources and not missing_record_files else "action_required"
    return {
        "schema_version": RETRIEVAL_INDEX_REGISTRY_SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": status,
        "index_snapshot_count": len(snapshots),
        "source_lineage_count": len(lineages),
        "total_declared_records": sum(int(row.get("record_count") or 0) for row in snapshots),
        "missing_source_artifact_count": len(missing_sources),
        "missing_record_file_snapshot_count": len(missing_record_files),
        "by_index_type": dict(Counter(str(row.get("index_type") or "") for row in snapshots)),
        "by_index_family": dict(Counter(str(row.get("index_family") or "") for row in snapshots)),
        "source_artifact_status_counts": dict(Counter(str(row.get("source_artifact_status") or "") for row in lineages)),
        "parser_artifact_link_status_counts": dict(Counter(str(row.get("parser_artifact_link_status") or "") for row in lineages)),
        "record_snapshot_trace_status_counts": dict(Counter(str(row.get("record_snapshot_trace_status") or "") for row in lineages)),
        "missing_source_artifact_samples": [_compact_lineage(row) for row in missing_sources[:30]],
        "missing_record_file_samples": [_compact_snapshot(row) for row in missing_record_files[:30]],
        "policy": (
            "RD5 records retrieval index snapshots and source-artifact lineage. It does not promote retrieval hits into facts; "
            "BM25/ObjectBM25/SQLite/Dense/Milvus remain recall layers and must route back through parser/authority gates."
        ),
    }


def render_retrieval_index_registry_report(summary: Mapping[str, Any], *, output_paths: Mapping[str, str]) -> str:
    lines = [
        "# RD5 RAG Index Registry / Retrieval Parity",
        "",
        f"- Generated at: `{summary.get('generated_at', '')}`",
        f"- Status: `{summary.get('status', '')}`",
        f"- Index snapshots: `{summary.get('index_snapshot_count', 0)}`",
        f"- Source lineage rows: `{summary.get('source_lineage_count', 0)}`",
        f"- Total declared records: `{summary.get('total_declared_records', 0)}`",
        f"- Missing source artifacts: `{summary.get('missing_source_artifact_count', 0)}`",
        f"- Missing record-file snapshots: `{summary.get('missing_record_file_snapshot_count', 0)}`",
        "",
        "## Outputs",
        "",
    ]
    for key, path in output_paths.items():
        lines.append(f"- `{key}`: `{path}`")
    lines.extend(
        [
            "",
            "## Index Types",
            "",
            _markdown_counter_table(summary.get("by_index_type") or {}, "Index type", "Snapshots"),
            "",
            "## Source Artifact Status",
            "",
            _markdown_counter_table(summary.get("source_artifact_status_counts") or {}, "Status", "Lineage rows"),
            "",
            "## Parser Artifact Link",
            "",
            _markdown_counter_table(summary.get("parser_artifact_link_status_counts") or {}, "Status", "Lineage rows"),
            "",
            "## Record Snapshot Trace Status",
            "",
            _markdown_counter_table(summary.get("record_snapshot_trace_status_counts") or {}, "Status", "Lineage rows"),
            "",
            "## Boundary",
            "",
            "- RD5 只登记 retrieval index snapshot 与 source-artifact lineage，不把 retrieval hit 直接提权为 fact。",
            "- Milvus 仍是 semantic recall supplement，不承担 exact-value authority。",
            "- 旧云端绝对路径会重定位到当前 repo；若无法重定位则作为 missing source artifact 暴露。",
            "",
        ]
    )
    return "\n".join(lines)


def write_jsonl(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_retrieval_index_registry_sqlite(
    path: str | Path,
    *,
    snapshots: Sequence[Mapping[str, Any]],
    lineages: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(target)) as conn:
        conn.execute("drop table if exists retrieval_index_snapshots")
        conn.execute("drop table if exists retrieval_index_source_lineage")
        conn.execute(
            """
            create table retrieval_index_snapshots (
                retrieval_index_snapshot_id text primary key,
                schema_version text not null,
                generated_at text not null,
                index_family text not null,
                index_type text not null,
                index_path text not null,
                metadata_path text not null,
                record_count integer not null,
                record_files_json text not null,
                missing_record_file_count integer not null,
                source_path_hint text not null,
                embedding_model text not null,
                embedding_dim integer not null,
                claim_boundary text not null,
                metadata_json text not null
            )
            """
        )
        conn.execute(
            """
            create table retrieval_index_source_lineage (
                lineage_id text primary key,
                schema_version text not null,
                generated_at text not null,
                retrieval_index_snapshot_id text not null,
                index_path text not null,
                index_type text not null,
                source_hint_key text not null,
                source_path_hint text not null,
                resolved_source_path text not null,
                source_artifact_status text not null,
                parser_artifact_link_status text not null,
                parser_artifact_id text not null,
                parser_artifact_kind text not null,
                parser_run_ids_json text not null,
                record_snapshot_trace_status text not null,
                claim_boundary text not null
            )
            """
        )
        conn.executemany(
            """
            insert into retrieval_index_snapshots values (
                :retrieval_index_snapshot_id, :schema_version, :generated_at, :index_family, :index_type,
                :index_path, :metadata_path, :record_count, :record_files_json, :missing_record_file_count,
                :source_path_hint, :embedding_model, :embedding_dim, :claim_boundary, :metadata_json
            )
            """,
            [dict(row) for row in snapshots],
        )
        conn.executemany(
            """
            insert into retrieval_index_source_lineage values (
                :lineage_id, :schema_version, :generated_at, :retrieval_index_snapshot_id, :index_path, :index_type,
                :source_hint_key, :source_path_hint, :resolved_source_path, :source_artifact_status,
                :parser_artifact_link_status, :parser_artifact_id, :parser_artifact_kind, :parser_run_ids_json,
                :record_snapshot_trace_status, :claim_boundary
            )
            """,
            [dict(row) for row in lineages],
        )
        conn.execute("create index idx_retrieval_index_snapshots_family on retrieval_index_snapshots(index_family)")
        conn.execute("create index idx_retrieval_index_snapshots_type on retrieval_index_snapshots(index_type)")
        conn.execute("create index idx_retrieval_source_lineage_snapshot on retrieval_index_source_lineage(retrieval_index_snapshot_id)")
        conn.execute("create index idx_retrieval_source_lineage_status on retrieval_index_source_lineage(source_artifact_status)")
        conn.execute("create index idx_retrieval_source_lineage_parser_status on retrieval_index_source_lineage(parser_artifact_link_status)")
        snapshot_count = conn.execute("select count(*) from retrieval_index_snapshots").fetchone()[0]
        lineage_count = conn.execute("select count(*) from retrieval_index_source_lineage").fetchone()[0]
    return {"snapshot_count": int(snapshot_count), "lineage_count": int(lineage_count)}


def _snapshot_from_index_metadata(root: Path, metadata_path: Path, metadata: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    index_dir = metadata_path.parent
    record_files = _record_files(root, index_dir, metadata)
    missing_record_files = [row for row in record_files if not row["exists"]]
    return {
        "schema_version": RETRIEVAL_INDEX_SNAPSHOT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "retrieval_index_snapshot_id": _stable_id("rd5_index", _rel(index_dir, root), _summary_fingerprint(metadata)),
        "index_family": _index_family(index_dir),
        "index_type": str(metadata.get("index_type") or "unknown"),
        "index_path": _rel(index_dir, root),
        "metadata_path": _rel(metadata_path, root),
        "record_count": _int(metadata.get("records") or metadata.get("faiss_ntotal") or 0),
        "record_files_json": json.dumps(record_files, ensure_ascii=False, sort_keys=True),
        "missing_record_file_count": len(missing_record_files),
        "source_path_hint": _source_path_hint(metadata),
        "embedding_model": str(metadata.get("model_name") or ""),
        "embedding_dim": _int(metadata.get("embedding_dim")),
        "claim_boundary": _claim_boundary_for_index(metadata),
        "metadata_json": json.dumps(_compact_payload(metadata), ensure_ascii=False, sort_keys=True),
    }


def _snapshot_from_milvus_config(root: Path, path: Path, config: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    db_path = _resolve_path(root, str(config.get("db_path") or ""))
    lineage = config.get("lineage") if isinstance(config.get("lineage"), Mapping) else {}
    source_path_hint = str(
        config.get("source_parquet_path")
        or config.get("source_manifest_path")
        or lineage.get("parquet_export_dir")
        or lineage.get("summary_path")
        or ""
    )
    return {
        "schema_version": RETRIEVAL_INDEX_SNAPSHOT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "retrieval_index_snapshot_id": _stable_id("rd5_milvus", _rel(path, root), config.get("collection_name")),
        "index_family": "milvus_semantic",
        "index_type": "milvus_lite_vector_collection",
        "index_path": _rel(db_path, root) if db_path else "",
        "metadata_path": _rel(path, root),
        "record_count": _int(config.get("vector_count")),
        "record_files_json": json.dumps([{"path": _rel(db_path, root) if db_path else "", "exists": bool(db_path and db_path.exists())}], ensure_ascii=False),
        "missing_record_file_count": 0 if db_path and db_path.exists() else 1,
        "source_path_hint": source_path_hint,
        "embedding_model": str(config.get("embedding_model") or config.get("model_name") or ""),
        "embedding_dim": _int(config.get("embedding_dim")),
        "claim_boundary": str(config.get("claim_boundary") or "semantic_recall_supplement_not_exact_value_authority"),
        "metadata_json": json.dumps(_compact_payload(config), ensure_ascii=False, sort_keys=True),
    }


def _lineages_for_index_snapshot(
    root: Path,
    snapshot: Mapping[str, Any],
    metadata: Mapping[str, Any],
    *,
    parser_artifact_index: Mapping[str, Mapping[str, Any]],
    generated_at: str,
) -> list[dict[str, Any]]:
    hints = []
    for key in ("evidence_path", "structured_dir", "records_path", "corpus_path"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            hints.append((key, value))
    outputs = metadata.get("outputs")
    if isinstance(outputs, Mapping):
        for key, value in outputs.items():
            if isinstance(value, str) and value.strip():
                hints.append((f"outputs.{key}", value))
    if not hints:
        hints.append(("metadata_only", ""))
    return [
        _source_lineage_row(
            root,
            snapshot,
            source_path_hint=value,
            source_hint_key=key,
            parser_artifact_index=parser_artifact_index,
            generated_at=generated_at,
        )
        for key, value in hints
    ]


def _lineages_for_milvus_config(
    root: Path,
    snapshot: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    parser_artifact_index: Mapping[str, Mapping[str, Any]],
    generated_at: str,
) -> list[dict[str, Any]]:
    hints = []
    for key in ("source_parquet_path", "source_manifest_path", "evidence_path"):
        value = config.get(key)
        if isinstance(value, str) and value.strip():
            hints.append((key, value))
    lineage = config.get("lineage") if isinstance(config.get("lineage"), Mapping) else {}
    for key in ("parquet_export_dir", "summary_path"):
        value = lineage.get(key)
        if isinstance(value, str) and value.strip():
            hints.append((f"lineage.{key}", value))
    if not hints:
        hints.append(("config_only", ""))
    return [
        _source_lineage_row(
            root,
            snapshot,
            source_path_hint=value,
            source_hint_key=key,
            parser_artifact_index=parser_artifact_index,
            generated_at=generated_at,
        )
        for key, value in hints
    ]


def _source_lineage_row(
    root: Path,
    snapshot: Mapping[str, Any],
    *,
    source_path_hint: str,
    source_hint_key: str,
    parser_artifact_index: Mapping[str, Mapping[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    source_path = _resolve_path(root, source_path_hint) if source_path_hint else None
    source_rel = _rel(source_path, root) if source_path else ""
    source_exists = bool(source_path and source_path.exists())
    parser_artifact = parser_artifact_index.get(source_rel.lower()) if source_rel else None
    if not parser_artifact and source_path and source_path.is_dir():
        parser_artifact = _match_parser_artifact_under_dir(source_rel, parser_artifact_index)
    link_status = "matched_parser_artifact" if parser_artifact else ("metadata_only_no_source_hint" if not source_path_hint else "no_parser_artifact_match")
    source_status = "source_artifact_exists" if source_exists else ("metadata_only_no_source_hint" if not source_path_hint else "missing_source_artifact")
    record_trace_status = _record_snapshot_source_trace_status(root, snapshot)
    if source_status == "missing_source_artifact" and record_trace_status == "record_snapshot_has_raw_trace":
        source_status = "source_artifact_missing_but_record_snapshot_has_raw_trace"
    parser_run_ids = (parser_artifact or {}).get("linked_parser_run_ids") or []
    if not isinstance(parser_run_ids, list):
        parser_run_ids = []
    return {
        "schema_version": RETRIEVAL_INDEX_SOURCE_LINEAGE_SCHEMA_VERSION,
        "generated_at": generated_at,
        "lineage_id": _stable_id("rd5_index_lineage", snapshot.get("retrieval_index_snapshot_id"), source_hint_key, source_rel),
        "retrieval_index_snapshot_id": str(snapshot.get("retrieval_index_snapshot_id") or ""),
        "index_path": str(snapshot.get("index_path") or ""),
        "index_type": str(snapshot.get("index_type") or ""),
        "source_hint_key": source_hint_key,
        "source_path_hint": source_path_hint,
        "resolved_source_path": source_rel,
        "source_artifact_status": source_status,
        "parser_artifact_link_status": link_status,
        "parser_artifact_id": str((parser_artifact or {}).get("artifact_id") or ""),
        "parser_artifact_kind": str((parser_artifact or {}).get("artifact_kind") or ""),
        "parser_run_ids_json": json.dumps(parser_run_ids, ensure_ascii=False, sort_keys=True),
        "record_snapshot_trace_status": record_trace_status,
        "claim_boundary": str(snapshot.get("claim_boundary") or ""),
    }


def _parser_artifact_index(root: Path) -> dict[str, Mapping[str, Any]]:
    path = root / "data/manifests/parser_output_artifact_ledger_v0_1.jsonl"
    result: dict[str, Mapping[str, Any]] = {}
    if not path.exists():
        return result
    for row in _read_jsonl(path):
        artifact_path = str(row.get("artifact_path") or "")
        if artifact_path:
            result[artifact_path.lower()] = row
    return result


def _match_parser_artifact_under_dir(source_rel: str, parser_artifact_index: Mapping[str, Mapping[str, Any]]) -> Mapping[str, Any] | None:
    prefix = source_rel.rstrip("/").lower() + "/"
    for path, row in parser_artifact_index.items():
        if path.startswith(prefix):
            return row
    return None


def _record_snapshot_source_trace_status(root: Path, snapshot: Mapping[str, Any]) -> str:
    try:
        record_files = json.loads(str(snapshot.get("record_files_json") or "[]"))
    except json.JSONDecodeError:
        return "record_snapshot_trace_unknown"
    if not isinstance(record_files, list):
        return "record_snapshot_trace_unknown"
    candidate_paths: list[Path] = []
    for item in record_files:
        if not isinstance(item, Mapping):
            continue
        path = _resolve_path(root, str(item.get("path") or ""))
        if path and path.exists() and path.name == "records.jsonl":
            candidate_paths.append(path)
    if not candidate_paths:
        return "no_records_jsonl_snapshot"
    for path in candidate_paths:
        if _records_jsonl_has_raw_trace(root, path):
            return "record_snapshot_has_raw_trace"
    return "record_snapshot_without_verified_raw_trace"


def _records_jsonl_has_raw_trace(root: Path, path: Path, *, max_rows: int = 20) -> bool:
    checked = 0
    for row in _read_jsonl(path):
        checked += 1
        source_url = str(row.get("source_url") or "")
        local_path = str(row.get("local_path") or "")
        metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
        metadata_path = str(metadata.get("metadata_path") or "")
        raw_path = _resolve_path(root, local_path) if local_path else None
        meta_path = _resolve_path(root, metadata_path) if metadata_path else None
        if source_url and ((raw_path and raw_path.exists()) or (meta_path and meta_path.exists())):
            return True
        if checked >= max_rows:
            break
    return False


def _record_files(root: Path, index_dir: Path, metadata: Mapping[str, Any]) -> list[dict[str, Any]]:
    record_files = metadata.get("record_files")
    if not isinstance(record_files, list) or not record_files:
        record_files = []
        for name in (
            "records.pkl",
            "records.slim.pkl",
            "records.jsonl",
            "records.sqlite",
            "records.duckdb",
            "bm25.pkl",
            "faiss.index",
            "embeddings.npy",
        ):
            if (index_dir / name).exists():
                record_files.append(name)
    for key in ("faiss_index_path", "embeddings_path", "vectors_path", "records_path"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            record_files.append(value)
    deduped_record_files: list[str] = []
    seen: set[str] = set()
    for item in record_files:
        text = str(item)
        if text not in seen:
            seen.add(text)
            deduped_record_files.append(text)
    rows = []
    for item in deduped_record_files:
        path = _resolve_path(root, str(item))
        if path and not path.exists() and not Path(str(item)).is_absolute():
            path = (index_dir / str(item)).resolve()
        rows.append({"path": _rel(path, root) if path else str(item), "exists": bool(path and path.exists())})
    return rows


def _source_path_hint(metadata: Mapping[str, Any]) -> str:
    for key in ("evidence_path", "structured_dir", "records_path", "corpus_path"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _claim_boundary_for_index(metadata: Mapping[str, Any]) -> str:
    index_type = str(metadata.get("index_type") or "").lower()
    if "milvus" in index_type or "dense" in index_type:
        return "semantic_recall_supplement_not_exact_value_authority"
    if "sqlite" in index_type or "bm25" in index_type or "rank" in index_type:
        return "retrieval_candidate_only_must_return_to_parser_authority_gate"
    return "retrieval_index_metadata_only_no_fact_authority"


def _index_family(index_dir: Path) -> str:
    text = index_dir.as_posix().lower()
    if "/dense/" in text:
        return "dense_embedding"
    if "/sqlite_fts/" in text:
        return "sqlite_fts_object"
    if "/bm25/" in text and text.endswith("_objects"):
        return "object_bm25_or_fts"
    if "/bm25/" in text:
        return "bm25_lexical"
    return "retrieval_index"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, Mapping):
                yield dict(payload)


def _resolve_path(root: Path, value: str) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    path = Path(text)
    if not path.is_absolute():
        path = root / path
    resolved = path.resolve()
    if resolved.exists():
        return resolved
    parts = list(path.parts)
    lowered = [part.lower() for part in parts]
    if "fin_insight_agent" in lowered:
        index = lowered.index("fin_insight_agent")
        suffix = Path(*parts[index + 1 :]) if index + 1 < len(parts) else Path()
        relocated = (root / suffix).resolve()
        if relocated.exists():
            return relocated
        return relocated
    return resolved


def _is_temporary_path(root: Path, path: Path) -> bool:
    rel = f"/{_rel(path, root).lower()}"
    return any(token in rel for token in TEMPORARY_PATH_TOKENS)


def _summary_fingerprint(metadata: Mapping[str, Any]) -> str:
    compact = {
        key: metadata.get(key)
        for key in ("index_type", "records", "faiss_ntotal", "embedding_dim", "evidence_path", "structured_dir", "prefix")
        if key in metadata
    }
    return json.dumps(compact, ensure_ascii=False, sort_keys=True)


def _compact_payload(value: Any, *, max_items: int = 60) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _compact_payload(item, max_items=max_items) for key, item in list(value.items())[:max_items]}
    if isinstance(value, list):
        return [_compact_payload(item, max_items=max_items) for item in value[:max_items]]
    return value


def _compact_snapshot(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "index_path": row.get("index_path", ""),
        "index_type": row.get("index_type", ""),
        "missing_record_file_count": row.get("missing_record_file_count", 0),
    }


def _compact_lineage(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "index_path": row.get("index_path", ""),
        "index_type": row.get("index_type", ""),
        "source_hint_key": row.get("source_hint_key", ""),
        "source_path_hint": row.get("source_path_hint", ""),
        "resolved_source_path": row.get("resolved_source_path", ""),
        "source_artifact_status": row.get("source_artifact_status", ""),
        "record_snapshot_trace_status": row.get("record_snapshot_trace_status", ""),
    }


def _stable_id(*parts: Any) -> str:
    raw = "\x1f".join(str(part or "") for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rel(path: Path | None, root: Path) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _markdown_counter_table(counter: Mapping[str, Any], key_label: str, value_label: str) -> str:
    lines = [f"| {key_label} | {value_label} |", "| --- | ---: |"]
    for key, value in sorted(counter.items(), key=lambda item: str(item[0])):
        lines.append(f"| `{key}` | `{value}` |")
    return "\n".join(lines)
