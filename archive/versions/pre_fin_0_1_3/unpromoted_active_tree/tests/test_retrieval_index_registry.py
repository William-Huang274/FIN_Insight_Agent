from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from sec_agent.retrieval_index_registry import (
    build_retrieval_index_registry,
    write_retrieval_index_registry_sqlite,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_rd5_relocates_old_cloud_source_path_and_links_parser_artifact(tmp_path: Path) -> None:
    repo = tmp_path
    source = repo / "data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text('{"ticker":"NVDA"}\n', encoding="utf-8")
    index_dir = repo / "data/indexes/bm25/sec_tech_10k"
    index_dir.mkdir(parents=True, exist_ok=True)
    (index_dir / "records.jsonl").write_text('{"id":"r1"}\n', encoding="utf-8")
    (index_dir / "bm25.pkl").write_bytes(b"bm25")
    _write_json(
        index_dir / "metadata.json",
        {
            "index_type": "rank_bm25",
            "records": 1,
            "evidence_path": "/root/autodl-tmp/FIN_Insight_Agent/data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl",
        },
    )
    _write_jsonl(
        repo / "data/manifests/parser_output_artifact_ledger_v0_1.jsonl",
        [
            {
                "artifact_id": "artifact:sec10k",
                "artifact_kind": "jsonl_rows",
                "artifact_path": "data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl",
                "linked_parser_run_ids": ["run:sec10k"],
            }
        ],
    )

    result = build_retrieval_index_registry(repo, generated_at="2026-06-27T00:00:00+00:00")

    assert result["summary"]["status"] == "pass"
    assert result["summary"]["index_snapshot_count"] == 1
    assert result["snapshots"][0]["missing_record_file_count"] == 0
    lineage = result["lineages"][0]
    assert lineage["resolved_source_path"] == "data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl"
    assert lineage["source_artifact_status"] == "source_artifact_exists"
    assert lineage["parser_artifact_link_status"] == "matched_parser_artifact"
    assert json.loads(lineage["parser_run_ids_json"]) == ["run:sec10k"]


def test_rd5_missing_source_artifact_is_action_required(tmp_path: Path) -> None:
    repo = tmp_path
    index_dir = repo / "data/indexes/bm25/missing_source"
    index_dir.mkdir(parents=True, exist_ok=True)
    (index_dir / "records.jsonl").write_text('{"id":"r1"}\n', encoding="utf-8")
    _write_json(
        index_dir / "metadata.json",
        {
            "index_type": "rank_bm25",
            "records": 1,
            "evidence_path": "data/processed_private/evidence_objects/missing.jsonl",
        },
    )

    result = build_retrieval_index_registry(repo, generated_at="2026-06-27T00:00:00+00:00")

    assert result["summary"]["status"] == "action_required"
    assert result["summary"]["missing_source_artifact_count"] == 1
    assert result["lineages"][0]["source_artifact_status"] == "missing_source_artifact"


def test_rd5_missing_source_artifact_can_pass_only_when_records_have_raw_trace(tmp_path: Path) -> None:
    repo = tmp_path
    raw_file = repo / "data/raw_private/sec/2023/NVDA/10-K.html"
    raw_file.parent.mkdir(parents=True, exist_ok=True)
    raw_file.write_text("<html>filing</html>", encoding="utf-8")
    index_dir = repo / "data/indexes/bm25/legacy_cloud"
    index_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        index_dir / "metadata.json",
        {
            "index_type": "rank_bm25",
            "records": 1,
            "evidence_path": "/root/autodl-tmp/FIN_Insight_Agent/data/processed_private/evidence_objects/legacy_missing.jsonl",
        },
    )
    _write_jsonl(
        index_dir / "records.jsonl",
        [
            {
                "evidence_id": "NVDA_2025_10K_ITEM1",
                "source_url": "https://www.sec.gov/Archives/edgar/data/1045810/example.htm",
                "local_path": "data/raw_private/sec/2023/NVDA/10-K.html",
            }
        ],
    )

    result = build_retrieval_index_registry(repo, generated_at="2026-06-27T00:00:00+00:00")

    assert result["summary"]["status"] == "pass"
    assert result["summary"]["missing_source_artifact_count"] == 0
    assert result["lineages"][0]["source_artifact_status"] == "source_artifact_missing_but_record_snapshot_has_raw_trace"
    assert result["lineages"][0]["record_snapshot_trace_status"] == "record_snapshot_has_raw_trace"


def test_rd5_milvus_config_records_vector_collection_and_lineage(tmp_path: Path) -> None:
    repo = tmp_path
    db_path = repo / "data/indexes/milvus_lite.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_bytes(b"sqlite")
    parquet_dir = repo / "data/milvus_exports/run1/data"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        repo / "configs/runtime/milvus_runtime_603_local_v0_1.json",
        {
            "schema_version": "finsight_milvus_runtime_config_v0_1",
            "db_path": "data/indexes/milvus_lite.db",
            "collection_name": "fin_test",
            "embedding_model": "bge-m3",
            "embedding_dim": 1024,
            "vector_count": 2,
            "claim_boundary": "semantic_recall_supplement_not_exact_value_authority",
            "lineage": {"parquet_export_dir": "data/milvus_exports/run1/data"},
        },
    )

    result = build_retrieval_index_registry(repo, generated_at="2026-06-27T00:00:00+00:00")

    snapshot = result["snapshots"][0]
    assert snapshot["index_family"] == "milvus_semantic"
    assert snapshot["record_count"] == 2
    assert snapshot["missing_record_file_count"] == 0
    assert result["lineages"][0]["source_hint_key"] == "lineage.parquet_export_dir"
    assert result["lineages"][0]["source_artifact_status"] == "source_artifact_exists"


def test_rd5_sqlite_counts_match_registry_rows(tmp_path: Path) -> None:
    repo = tmp_path
    index_dir = repo / "data/indexes/bm25/sec"
    index_dir.mkdir(parents=True, exist_ok=True)
    (index_dir / "records.jsonl").write_text('{"id":"r1"}\n', encoding="utf-8")
    source = repo / "data/processed_private/evidence_objects/sec.jsonl"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text('{"ticker":"MSFT"}\n', encoding="utf-8")
    _write_json(index_dir / "metadata.json", {"index_type": "rank_bm25", "records": 1, "evidence_path": str(source)})
    result = build_retrieval_index_registry(repo, generated_at="2026-06-27T00:00:00+00:00")
    sqlite_path = repo / "data/workbench_private/research_data/registry.sqlite"
    counts = write_retrieval_index_registry_sqlite(sqlite_path, snapshots=result["snapshots"], lineages=result["lineages"])

    with sqlite3.connect(str(sqlite_path)) as conn:
        index_type = conn.execute("select index_type from retrieval_index_snapshots").fetchone()[0]
        source_status = conn.execute("select source_artifact_status from retrieval_index_source_lineage").fetchone()[0]

    assert counts == {"snapshot_count": 1, "lineage_count": 1}
    assert index_type == "rank_bm25"
    assert source_status == "source_artifact_exists"
