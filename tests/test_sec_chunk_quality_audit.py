from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "eval_retrieval" / "audit_sec_chunk_quality.py"


def test_chunk_quality_audit_passes_clean_chunks(tmp_path: Path) -> None:
    module = _load_script()
    chunks_path = tmp_path / "chunks.jsonl"
    evidence_path = tmp_path / "evidence.jsonl"
    bm25_dir = tmp_path / "bm25"
    object_dir = tmp_path / "objects"
    bm25_dir.mkdir()
    object_dir.mkdir()
    rows = [
        _chunk("MSFT_2026_10Q_ITEM1_BLOCK_0001_CHUNK_0001", item="1", text_words=120),
        _chunk("MSFT_2026_10Q_ITEM2_BLOCK_0001_PART_01_OF_02", item="2", block="MSFT_2026_10Q_ITEM2_BLOCK_0001", part=1, parts=2, text="alpha " * 120 + "shared overlap words " * 20),
        _chunk("MSFT_2026_10Q_ITEM2_BLOCK_0001_PART_02_OF_02", item="2", block="MSFT_2026_10Q_ITEM2_BLOCK_0001", part=2, parts=2, text="shared overlap words " * 20 + "beta " * 120, char_start=600),
    ]
    _write_jsonl(chunks_path, rows)
    _write_jsonl(evidence_path, [{"evidence_id": row["chunk_id"]} for row in rows])
    (bm25_dir / "metadata.json").write_text(json.dumps({"records": len(rows), "index_type": "rank_bm25"}), encoding="utf-8")
    (object_dir / "metadata.json").write_text(json.dumps({"records": 10, "index_type": "sqlite_fts5"}), encoding="utf-8")

    audit = module.audit_chunk_quality(
        chunks_path=chunks_path,
        evidence_path=evidence_path,
        bm25_index_dir=bm25_dir,
        object_bm25_index_dir=object_dir,
        run_id="unit_clean",
    )

    assert audit["gate_status"] == "pass"
    assert audit["checks"]["split_overlap_present"] is True
    assert audit["checks"]["primary_core_item_coverage_bounded"] is True


def test_chunk_quality_audit_fails_duplicate_and_unbalanced_table(tmp_path: Path) -> None:
    module = _load_script()
    chunks_path = tmp_path / "chunks.jsonl"
    duplicate_id = "AAPL_2026_10Q_ITEM1_BLOCK_0001_CHUNK_0001"
    rows = [
        _chunk(duplicate_id, item="1", text="[TABLE_START id=1 rows=1]\nRevenue | 1\n" + "word " * 100),
        _chunk(duplicate_id, item="2", text_words=100),
    ]
    _write_jsonl(chunks_path, rows)

    audit = module.audit_chunk_quality(
        chunks_path=chunks_path,
        evidence_path=None,
        bm25_index_dir=None,
        object_bm25_index_dir=None,
        run_id="unit_fail",
    )

    assert audit["gate_status"] == "fail"
    assert audit["checks"]["duplicate_chunk_ids_absent"] is False
    assert audit["checks"]["table_markers_balanced"] is False
    assert "暂不进入 Milvus retrieval-only 实验" in audit["milvus_insertion_experiment"]["decision"]


def test_chunk_quality_audit_detects_evidence_and_bm25_mismatch(tmp_path: Path) -> None:
    module = _load_script()
    chunks_path = tmp_path / "chunks.jsonl"
    evidence_path = tmp_path / "evidence.jsonl"
    bm25_dir = tmp_path / "bm25"
    object_dir = tmp_path / "objects"
    bm25_dir.mkdir()
    object_dir.mkdir()
    rows = [
        _chunk("JPM_2026_10K_ITEM1_BLOCK_0001_CHUNK_0001", form="10-K", item="1", text_words=100),
        _chunk("JPM_2026_10K_ITEM1A_BLOCK_0001_CHUNK_0001", form="10-K", item="1A", text_words=100),
        _chunk("JPM_2026_10K_ITEM7_BLOCK_0001_CHUNK_0001", form="10-K", item="7", text_words=100),
        _chunk("JPM_2026_10K_ITEM8_BLOCK_0001_CHUNK_0001", form="10-K", item="8", text_words=100),
    ]
    _write_jsonl(chunks_path, rows)
    _write_jsonl(evidence_path, [{"evidence_id": rows[0]["chunk_id"]}])
    (bm25_dir / "metadata.json").write_text(json.dumps({"records": 1, "index_type": "rank_bm25"}), encoding="utf-8")
    (object_dir / "metadata.json").write_text(json.dumps({"records": 1, "index_type": "sqlite_fts5"}), encoding="utf-8")

    audit = module.audit_chunk_quality(
        chunks_path=chunks_path,
        evidence_path=evidence_path,
        bm25_index_dir=bm25_dir,
        object_bm25_index_dir=object_dir,
        run_id="unit_mismatch",
    )

    assert audit["gate_status"] == "fail"
    assert audit["checks"]["evidence_rows_match_chunks"] is False
    assert audit["evidence_parity"]["missing_evidence_count"] == 3
    assert "evidence_rows_match_chunks" in audit["milvus_insertion_experiment"]["decision"]


def _chunk(
    chunk_id: str,
    *,
    form: str = "10-Q",
    item: str = "1",
    block: str | None = None,
    part: int = 1,
    parts: int = 1,
    text: str | None = None,
    text_words: int = 100,
    char_start: int = 0,
) -> dict:
    body = text if text is not None else " ".join(f"word{i}" for i in range(text_words))
    block_id = block or chunk_id.rsplit("_CHUNK_", 1)[0].rsplit("_PART_", 1)[0]
    char_end = char_start + len(body)
    return {
        "chunk_id": chunk_id,
        "ticker": "MSFT",
        "company": "Microsoft Corporation",
        "fiscal_year": 2026,
        "source_type": form,
        "form_type": form,
        "source_tier": "primary_sec_filing",
        "section": f"Item {item}",
        "item_code": item,
        "chunk_index": part,
        "block_id": block_id,
        "block_index": 1,
        "block_heading": f"Item {item}",
        "block_type": "management_discussion",
        "block_char_start": 0,
        "block_char_end": 5000,
        "block_part_index": part,
        "block_part_count": parts,
        "contains_table": "[TABLE_START" in body,
        "text": body,
        "char_start": char_start,
        "char_end": char_end,
        "source_url": "https://www.sec.gov/example",
        "local_path": "D:/tmp/example.html",
        "metadata": {
            "accession_number": "0000000000-26-000001",
            "filing_date": "2026-01-01",
            "period_end": "2026-01-01",
            "form_type": form,
            "source_tier": "primary_sec_filing",
        },
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _load_script():
    spec = importlib.util.spec_from_file_location("audit_sec_chunk_quality_under_test", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
