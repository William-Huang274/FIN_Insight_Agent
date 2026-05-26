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
