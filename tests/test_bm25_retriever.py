from __future__ import annotations

import json
import pickle
from pathlib import Path

from retrieval.bm25_retriever import BM25Retriever
from retrieval.object_bm25_retriever import ObjectBM25Retriever


class _FakeBM25:
    def __init__(self) -> None:
        self.full_calls = 0
        self.batch_calls = 0

    def get_scores(self, _tokens: list[str]) -> list[float]:
        self.full_calls += 1
        return [1.0, 9.0, 5.0]

    def get_batch_scores(self, _tokens: list[str], indices: list[int]) -> list[float]:
        self.batch_calls += 1
        scores = {0: 1.0, 1: 9.0, 2: 5.0}
        return [scores[idx] for idx in indices]


def _write_index(path: Path) -> None:
    path.mkdir(exist_ok=True)
    with (path / "bm25.pkl").open("wb") as f:
        pickle.dump(_FakeBM25(), f)
    records = [
        {
            "evidence_id": "a1",
            "ticker": "AAA",
            "fiscal_year": 2025,
            "section": "Item 1",
            "text": "alpha cloud revenue",
            "metadata": {"form_type": "10-K", "source_tier": "primary_sec_filing"},
        },
        {
            "evidence_id": "b1",
            "ticker": "BBB",
            "fiscal_year": 2025,
            "section": "Item 1",
            "text": "beta cloud revenue",
            "metadata": {"form_type": "10-K", "source_tier": "primary_sec_filing"},
        },
        {
            "evidence_id": "a2",
            "ticker": "AAA",
            "fiscal_year": 2026,
            "section": "Item 2",
            "text": "alpha quarterly revenue",
            "metadata": {"form_type": "10-Q", "source_tier": "primary_sec_filing"},
        },
    ]
    (path / "records.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in records) + "\n",
        encoding="utf-8",
    )


def test_bm25_filtered_search_uses_batch_scores_and_filter_cache(tmp_path: Path) -> None:
    _write_index(tmp_path)
    retriever = BM25Retriever(tmp_path)

    first = retriever.search(
        "cloud revenue",
        top_k=2,
        filters={"ticker": "AAA", "source_tier": "primary_sec_filing"},
    )
    second = retriever.search(
        "cloud revenue",
        top_k=2,
        filters={"ticker": "AAA", "source_tier": "primary_sec_filing"},
    )

    assert [row["evidence_id"] for row in first] == ["a2", "a1"]
    assert [row["evidence_id"] for row in second] == ["a2", "a1"]
    assert retriever.bm25.full_calls == 0
    assert retriever.bm25.batch_calls == 2
    assert len(retriever._filter_cache) == 1


def test_bm25_unfiltered_search_keeps_full_scores_path(tmp_path: Path) -> None:
    _write_index(tmp_path)
    retriever = BM25Retriever(tmp_path)

    hits = retriever.search("cloud revenue", top_k=2)

    assert [row["evidence_id"] for row in hits] == ["b1", "a2"]
    assert retriever.bm25.full_calls == 1
    assert retriever.bm25.batch_calls == 0


def _write_object_index(path: Path) -> None:
    path.mkdir(exist_ok=True)
    with (path / "bm25.pkl").open("wb") as f:
        pickle.dump(_FakeBM25(), f)
    records = [
        {
            "object_id": "obj_a1",
            "object_type": "metric",
            "ticker": "AAA",
            "fiscal_year": "2025",
            "period": "2025",
            "metric_name": "cloud revenue",
            "raw_value": "$1",
            "metadata": {"form_type": "10-K", "source_tier": "primary_sec_filing"},
        },
        {
            "object_id": "obj_b1",
            "object_type": "metric",
            "ticker": "BBB",
            "fiscal_year": 2025,
            "period": "2025",
            "metric_name": "cloud revenue",
            "raw_value": "$2",
            "metadata": {"form_type": "10-K", "source_tier": "primary_sec_filing"},
        },
        {
            "object_id": "obj_a2",
            "object_type": "table",
            "ticker": "AAA",
            "fiscal_year": 2026,
            "period": "2026",
            "title": "revenue table",
            "cells": [{"period": "2026", "raw_value": "$3", "unit": "usd_millions"}],
            "metadata": {"form_type": "10-Q", "source_tier": "primary_sec_filing"},
        },
    ]
    (path / "records.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in records) + "\n",
        encoding="utf-8",
    )


def test_object_bm25_filtered_search_uses_indexed_filters_and_batch_scores(tmp_path: Path) -> None:
    _write_object_index(tmp_path)
    retriever = ObjectBM25Retriever(tmp_path)

    hits = retriever.search(
        "cloud revenue 2026",
        top_k=3,
        filters={
            "ticker": ["AAA"],
            "fiscal_year": 2026,
            "object_type": ["metric", "table"],
            "form_type": ["10-Q"],
            "source_tier": ["primary_sec_filing"],
        },
    )

    assert [row["object_id"] for row in hits] == ["obj_a2"]
    assert retriever.bm25.full_calls == 0
    assert retriever.bm25.batch_calls == 1
    assert len(retriever._filter_cache) == 1


def test_object_bm25_prefers_slim_records_when_present(tmp_path: Path) -> None:
    _write_object_index(tmp_path)
    slim_records = [
        {
            "object_id": "obj_a1",
            "object_type": "metric",
            "ticker": "AAA",
            "fiscal_year": "2025",
            "period": "2025",
            "preview": "slim cloud revenue",
            "search_text": "slim cloud revenue",
            "metadata": {"form_type": "10-K", "source_tier": "primary_sec_filing"},
        },
        {
            "object_id": "obj_b1",
            "object_type": "metric",
            "ticker": "BBB",
            "fiscal_year": 2025,
            "period": "2025",
            "preview": "slim cloud revenue",
            "search_text": "slim cloud revenue",
            "metadata": {"form_type": "10-K", "source_tier": "primary_sec_filing"},
        },
        {
            "object_id": "obj_a2",
            "object_type": "table",
            "ticker": "AAA",
            "fiscal_year": 2026,
            "periods": ["2026"],
            "preview": "slim revenue table",
            "search_text": "slim revenue table 2026",
            "metadata": {"form_type": "10-Q", "source_tier": "primary_sec_filing"},
        },
    ]
    (tmp_path / "records.slim.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in slim_records) + "\n",
        encoding="utf-8",
    )

    retriever = ObjectBM25Retriever(tmp_path)
    hits = retriever.search(
        "cloud revenue 2026",
        top_k=3,
        filters={
            "ticker": ["AAA"],
            "fiscal_year": 2026,
            "object_type": ["metric", "table"],
            "form_type": ["10-Q"],
            "source_tier": ["primary_sec_filing"],
        },
    )

    assert retriever.records_path.name == "records.slim.jsonl"
    assert hits[0]["object_id"] == "obj_a2"
    assert hits[0]["preview"] == "slim revenue table"


def test_object_bm25_prefers_pickle_slim_records_over_jsonl(tmp_path: Path) -> None:
    _write_object_index(tmp_path)
    jsonl_record = {
        "object_id": "obj_a1",
        "object_type": "metric",
        "ticker": "AAA",
        "fiscal_year": "2025",
        "period": "2025",
        "preview": "jsonl record",
        "metadata": {"form_type": "10-K", "source_tier": "primary_sec_filing"},
    }
    pickle_record = {
        "object_id": "obj_a1",
        "object_type": "metric",
        "ticker": "AAA",
        "fiscal_year": "2025",
        "period": "2025",
        "preview": "pickle record",
        "metadata": {"form_type": "10-K", "source_tier": "primary_sec_filing"},
    }
    (tmp_path / "records.slim.jsonl").write_text(
        json.dumps(jsonl_record, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with (tmp_path / "records.slim.pkl").open("wb") as handle:
        pickle.dump(pickle_record, handle)

    retriever = ObjectBM25Retriever(tmp_path)
    hits = retriever.search("cloud revenue 2025", top_k=1, filters={"ticker": "AAA"})

    assert retriever.records_path.name == "records.slim.pkl"
    assert hits[0]["preview"] == "pickle record"


def test_object_bm25_uses_duckdb_record_store_without_loading_records(tmp_path: Path) -> None:
    _write_object_index(tmp_path)
    import duckdb

    con = duckdb.connect(str(tmp_path / "records.duckdb"))
    try:
        con.execute(
            """
            CREATE TABLE object_records (
                idx INTEGER,
                object_id VARCHAR,
                object_type VARCHAR,
                source_evidence_id VARCHAR,
                ticker VARCHAR,
                fiscal_year INTEGER,
                form_type VARCHAR,
                source_type VARCHAR,
                source_tier VARCHAR,
                section VARCHAR,
                subsection VARCHAR,
                period VARCHAR,
                period_end VARCHAR,
                period_type VARCHAR,
                duration_months INTEGER,
                fiscal_period VARCHAR,
                preview VARCHAR,
                periods_json VARCHAR,
                metric_family VARCHAR
            )
            """
        )
        con.execute(
            "INSERT INTO object_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                2,
                "obj_a2",
                "table",
                "AAA_2026_10Q_ITEM2",
                "AAA",
                2026,
                "10-Q",
                "10-Q",
                "primary_sec_filing",
                "Item 2",
                "",
                "",
                "2026-03-31",
                "quarter",
                3,
                "Q1",
                "duckdb revenue table",
                json.dumps(["2026"]),
                "",
            ],
        )
        con.execute(
            "CREATE TABLE object_record_store_metadata AS SELECT ? AS payload_json",
            [json.dumps({"record_count": 3})],
        )
    finally:
        con.close()

    retriever = ObjectBM25Retriever(tmp_path)
    hits = retriever.search(
        "cloud revenue 2026",
        top_k=3,
        filters={
            "ticker": ["AAA"],
            "fiscal_year": 2026,
            "object_type": ["metric", "table"],
            "form_type": ["10-Q"],
            "source_tier": ["primary_sec_filing"],
        },
    )

    assert retriever.record_store_path.exists()
    assert retriever.records == []
    assert hits[0]["object_id"] == "obj_a2"
    assert hits[0]["preview"] == "duckdb revenue table"


def test_object_bm25_uses_sqlite_fts_without_rank_bm25_pickle(tmp_path: Path) -> None:
    import sqlite3

    con = sqlite3.connect(str(tmp_path / "records.sqlite"))
    try:
        con.executescript(
            """
            CREATE TABLE object_records (
                idx INTEGER PRIMARY KEY,
                object_id TEXT,
                object_type TEXT,
                source_evidence_id TEXT,
                ticker TEXT,
                fiscal_year INTEGER,
                form_type TEXT,
                source_type TEXT,
                source_tier TEXT,
                section TEXT,
                subsection TEXT,
                period TEXT,
                period_end TEXT,
                period_type TEXT,
                duration_months INTEGER,
                fiscal_period TEXT,
                preview TEXT,
                periods_json TEXT,
                metric_family TEXT,
                record_json TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE object_records_fts USING fts5(
                search_text,
                content='object_records',
                content_rowid='idx'
            );
            CREATE TABLE object_index_metadata(payload_json TEXT NOT NULL);
            """
        )
        records = [
            {
                "object_id": "obj_a1",
                "object_type": "metric",
                "ticker": "AAA",
                "fiscal_year": 2025,
                "period": "2025",
                "metric_name": "cloud revenue",
                "preview": "AAA cloud revenue",
                "metadata": {"form_type": "10-K", "source_tier": "primary_sec_filing"},
            },
            {
                "object_id": "obj_a2",
                "object_type": "table",
                "ticker": "AAA",
                "fiscal_year": 2026,
                "periods": ["2026"],
                "preview": "AAA quarterly revenue table",
                "metadata": {"form_type": "10-Q", "source_tier": "primary_sec_filing"},
            },
        ]
        for idx, record in enumerate(records, start=1):
            con.execute(
                "INSERT INTO object_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    idx,
                    record["object_id"],
                    record["object_type"],
                    "",
                    record["ticker"],
                    record["fiscal_year"],
                    record["metadata"]["form_type"],
                    record["metadata"]["form_type"],
                    record["metadata"]["source_tier"],
                    "",
                    "",
                    record.get("period", ""),
                    "",
                    "",
                    None,
                    "",
                    record["preview"],
                    json.dumps(record.get("periods") or []),
                    "",
                    json.dumps(record),
                ],
            )
            con.execute("INSERT INTO object_records_fts(rowid, search_text) VALUES (?, ?)", [idx, record["preview"]])
        con.execute(
            "INSERT INTO object_index_metadata VALUES (?)",
            [json.dumps({"schema_version": "sec_agent_object_sqlite_fts_v0.1", "records": 2})],
        )
        con.commit()
    finally:
        con.close()

    retriever = ObjectBM25Retriever(tmp_path)
    hits = retriever.search(
        "quarterly revenue 2026",
        top_k=3,
        filters={"ticker": "AAA", "fiscal_year": 2026, "form_type": "10-Q"},
    )

    assert retriever.sqlite_fts_path.exists()
    assert retriever.bm25 is None
    assert retriever.records == []
    assert [row["object_id"] for row in hits] == ["obj_a2"]
