from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_build_evidence_store_streams_chunk_jsonl(tmp_path: Path) -> None:
    chunks_path = tmp_path / "chunks.jsonl"
    output_path = tmp_path / "evidence.jsonl"
    chunk = {
        "chunk_id": "AAA_2024_10K_ITEM1_BLOCK_0001_CHUNK_0001",
        "ticker": "AAA",
        "company": "AAA Corp",
        "fiscal_year": 2024,
        "category": "Technology",
        "category_slug": "technology",
        "source_type": "10-K",
        "form_type": "10-K",
        "source_tier": "primary_sec_filing",
        "period_end": "2024-12-31",
        "period_type": "annual",
        "duration_months": 12,
        "fiscal_period": "FY",
        "section": "Item 1. Business",
        "item_code": "1",
        "chunk_index": 1,
        "block_id": "AAA_2024_10K_ITEM1_BLOCK_0001",
        "block_index": 1,
        "block_heading": "Business",
        "block_type": "paragraph",
        "block_char_start": 0,
        "block_char_end": 32,
        "block_part_index": 1,
        "block_part_count": 1,
        "contains_table": False,
        "text": "AAA provides business services.",
        "char_start": 0,
        "char_end": 32,
        "source_url": "https://www.sec.gov/example",
        "local_path": "data/raw_private/sec/AAA/10-K.html",
        "metadata": {"filing_date": "2025-02-01"},
    }
    chunks_path.write_text(json.dumps(chunk, ensure_ascii=False) + "\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "data_retrieval" / "build_evidence_store.py"),
            "--chunks",
            str(chunks_path),
            "--output",
            str(output_path),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    summary = json.loads(result.stdout)
    evidence = json.loads(output_path.read_text(encoding="utf-8").strip())

    assert summary["streaming"] is True
    assert summary["input_chunks"] == 1
    assert summary["evidence_objects"] == 1
    assert evidence["evidence_id"] == chunk["chunk_id"]
    assert evidence["source_tier"] == "primary_sec_filing"
