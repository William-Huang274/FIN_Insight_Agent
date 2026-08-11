from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from sec_agent.raw_disclosure_data_inventory import (
    RAG_INDEX_INVENTORY_SCHEMA_VERSION,
    RAW_DISCLOSURE_DATA_INVENTORY_SCHEMA_VERSION,
    RUNTIME_DATABASE_INVENTORY_SCHEMA_VERSION,
    build_inventory_summary,
    build_rag_index_inventory,
    build_raw_disclosure_data_inventory,
    build_runtime_database_inventory,
)


def test_raw_disclosure_inventory_reads_summary_and_jsonl_rows(tmp_path: Path) -> None:
    repo = tmp_path
    raw_root = repo / "data" / "raw_private" / "structured_financial_facts"
    raw_root.mkdir(parents=True)
    (raw_root / "sample.json").write_text("{}", encoding="utf-8")
    manifest_dir = repo / "data" / "manifests"
    manifest_dir.mkdir(parents=True)
    rows_path = manifest_dir / "sec_financial_statement_metric_runtime_rows_v0_1.jsonl"
    rows_path.write_text(
        "\n".join(
            [
                json.dumps({"ticker": "NVDA", "metric_family": "revenue"}),
                json.dumps({"ticker": "MSFT", "metric_family": "assets"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (manifest_dir / "sec_financial_statement_metric_runtime_summary_v0_1.json").write_text(
        json.dumps(
            {
                "schema_version": "fixture_summary",
                "status": "pass",
                "runtime_row_count": 2,
                "runtime_ticker_count": 2,
                "metric_family_counts": {"revenue": 1, "assets": 1},
            }
        ),
        encoding="utf-8",
    )

    rows = build_raw_disclosure_data_inventory(repo, generated_at="2026-06-27T00:00:00+00:00")

    by_name = {row["artifact_name"]: row for row in rows}
    assert by_name["sec_structured_financial_facts_raw_root"]["schema_version"] == RAW_DISCLOSURE_DATA_INVENTORY_SCHEMA_VERSION
    assert by_name["sec_structured_financial_facts_raw_root"]["path_exists"] is True
    statement_rows = by_name["sec_financial_statement_metric_runtime_rows"]
    assert statement_rows["row_count"] == 2
    assert statement_rows["summary_metrics"]["runtime_row_count"] == 2
    assert statement_rows["lineage_status"] == "summary_linked"


def test_rag_index_inventory_reads_bm25_metadata_and_milvus_config(tmp_path: Path) -> None:
    repo = tmp_path
    index_dir = repo / "data" / "indexes" / "bm25" / "sector_depth_full238_us_v0_3_mixed_with_8k_fy2023_2027"
    index_dir.mkdir(parents=True)
    (index_dir / "metadata.json").write_text(
        json.dumps(
            {
                "index_type": "rank_bm25",
                "records": 12,
                "evidence_path": "data/processed_private/evidence_objects/example.jsonl",
            }
        ),
        encoding="utf-8",
    )
    (index_dir / "records.jsonl").write_text("{}\n", encoding="utf-8")
    milvus_db = repo / "artifacts" / "milvus_lite.db"
    milvus_db.parent.mkdir(parents=True)
    milvus_db.write_text("placeholder", encoding="utf-8")
    milvus_config = repo / "configs" / "runtime" / "milvus_runtime_603_local_v0_1.json"
    milvus_config.parent.mkdir(parents=True)
    milvus_config.write_text(
        json.dumps(
            {
                "status": "available",
                "db_path": str(milvus_db),
                "collection_name": "fixture_collection",
                "embedding_dim": 1024,
                "vector_count": 42,
                "ticker_count_indexed": 3,
                "company_count_declared": 4,
                "claim_boundary": "semantic_recall_supplement_not_exact_value_authority",
            }
        ),
        encoding="utf-8",
    )

    rows = build_rag_index_inventory(repo, generated_at="2026-06-27T00:00:00+00:00")

    by_type = {row["index_type"]: row for row in rows}
    assert by_type["rank_bm25"]["schema_version"] == RAG_INDEX_INVENTORY_SCHEMA_VERSION
    assert by_type["rank_bm25"]["records"] == 12
    assert by_type["rank_bm25"]["retriever_role"] == "lexical_recall"
    milvus = by_type["milvus_lite_vector_collection"]
    assert milvus["records"] == 42
    assert milvus["collection_name"] == "fixture_collection"
    assert milvus["claim_boundary"] == "semantic_recall_supplement_not_exact_value_authority"


def test_runtime_database_inventory_introspects_sqlite_and_summary_counts(tmp_path: Path) -> None:
    repo = tmp_path
    db_path = repo / "data" / "workbench_private" / "runtime_bridge" / "eval_store.sqlite"
    db_path.parent.mkdir(parents=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("create table eval_case_result(case_id text)")
        conn.executemany("insert into eval_case_result(case_id) values (?)", [("a",), ("b",)])

    database_rows = build_runtime_database_inventory(repo, generated_at="2026-06-27T00:00:00+00:00")
    eval_store = next(row for row in database_rows if row["artifact_name"] == "runtime_bridge_eval_store")

    assert eval_store["schema_version"] == RUNTIME_DATABASE_INVENTORY_SCHEMA_VERSION
    assert eval_store["path_exists"] is True
    assert eval_store["sqlite_schema_status"] == "sqlite_introspection_pass"
    assert eval_store["sqlite_row_counts"]["eval_case_result"] == 2

    summary = build_inventory_summary(raw_rows=[], rag_rows=[], database_rows=database_rows)
    assert summary["runtime_database_inventory_rows"] == len(database_rows)
    assert summary["database_path_exists_count"] >= 1
