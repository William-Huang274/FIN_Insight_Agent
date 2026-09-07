from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.data_retrieval.materialize_dell_knowledge_reader_bridge import (
    KnowledgeReaderBridgeError,
    materialize_bridge,
)


def _write_chunks(path: Path, *, prefix: str = "CHUNK") -> str:
    rows = []
    for index in range(2):
        rows.append({
            "chunk_id": f"{prefix}-{index}",
            "route_id": f"route-{prefix.lower()}",
            "chunk_index": index,
            "page": None,
            "parser": "fixture_parser_1_0",
            "splitter": "fixture_splitter_1_0",
            "stable_url": f"https://official.example/source-{index}",
            "text": f"Official primary source narrative {index}",
            "text_sha256": hashlib.sha256(
                f"Official primary source narrative {index}".encode("utf-8")
            ).hexdigest(),
            "publication_date": "2026-08-01",
            "source_role": "issuer_management_disclosure",
            "title": "Official Release",
            "publisher": "Official Publisher",
            "branches": ["Q1_ISSUER_TRUTH"],
            "raw_body_sha256": str(index) * 64,
            "numeric_authority": False,
        })
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_bridge_is_mechanical_and_candidate_only(tmp_path: Path) -> None:
    chunks = tmp_path / "chunks.jsonl"
    digest = _write_chunks(chunks)
    result = materialize_bridge(
        input_chunks=chunks, expected_input_sha256=digest,
        expected_input_count=2, output_root=tmp_path / "out", attempt_id="A01",
    )
    rows = [
        json.loads(line) for line in
        Path(result["output"]["records_path"]).read_text().splitlines()
    ]
    assert result["input"]["observed_sha256"] == digest
    assert result["inputs"] == [result["input"]]
    assert result["output"]["record_count"] == 2
    assert rows[0]["evidence_id"] == "CHUNK-0"
    assert rows[0]["route_id"] == "route-chunk"
    assert rows[0]["chunk_index"] == 0
    assert rows[0]["page"] is None
    assert rows[0]["parser"] == "fixture_parser_1_0"
    assert rows[0]["splitter"] == "fixture_splitter_1_0"
    assert rows[0]["text_sha256"] == hashlib.sha256(
        b"Official primary source narrative 0"
    ).hexdigest()
    assert rows[0]["parent_document_id"].startswith("DOC::")
    assert rows[0]["source_url"] == "https://official.example/source-0"
    assert rows[0]["source_type"] == "issuer_management_disclosure"
    assert rows[0]["source_tier"] == "official_primary_qualification_candidate"
    assert rows[0]["section"] == "Official Release"
    assert rows[0]["ticker"] == rows[0]["period_end"] == ""
    assert rows[0]["candidate_is_not_evidence"] is True
    assert rows[0]["citation_eligible"] is False
    assert rows[0]["evidence_admission_performed"] is False
    assert result["provenance_fields_preserved"] is True
    assert result["text_sha256_recomputed"] is True
    assert result["parent_content_materialized"] is False
    assert result["parent_child_retrieval_performed"] is False


def test_bridge_rejects_digest_before_creating_attempt(tmp_path: Path) -> None:
    chunks = tmp_path / "chunks.jsonl"
    _write_chunks(chunks)
    output_root = tmp_path / "out"
    with pytest.raises(KnowledgeReaderBridgeError, match="bridge_input_sha256_drift"):
        materialize_bridge(
            input_chunks=chunks, expected_input_sha256="0" * 64,
            expected_input_count=2, output_root=output_root, attempt_id="A01",
        )
    assert not (output_root / "A01").exists()


def test_bridge_rejects_count_before_creating_attempt(tmp_path: Path) -> None:
    chunks = tmp_path / "chunks.jsonl"
    digest = _write_chunks(chunks)
    output_root = tmp_path / "out"
    with pytest.raises(KnowledgeReaderBridgeError, match="bridge_input_count_drift"):
        materialize_bridge(
            input_chunks=chunks, expected_input_sha256=digest,
            expected_input_count=3, output_root=output_root, attempt_id="A01",
        )
    assert not (output_root / "A01").exists()


def test_bridge_rejects_row_text_digest_mismatch_before_attempt(
    tmp_path: Path,
) -> None:
    chunks = tmp_path / "chunks.jsonl"
    _write_chunks(chunks)
    rows = [json.loads(line) for line in chunks.read_text().splitlines()]
    rows[0]["text"] = "Mutated text with a stale digest"
    chunks.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    digest = hashlib.sha256(chunks.read_bytes()).hexdigest()
    output_root = tmp_path / "out"

    with pytest.raises(
        KnowledgeReaderBridgeError,
        match="bridge_text_sha256_mismatch:1",
    ):
        materialize_bridge(
            input_chunks=chunks,
            expected_input_sha256=digest,
            expected_input_count=2,
            output_root=output_root,
            attempt_id="A01",
        )
    assert not (output_root / "A01").exists()


def test_bridge_combines_two_frozen_chunk_sets_in_declared_order(
    tmp_path: Path,
) -> None:
    first = tmp_path / "a02-chunks.jsonl"
    second = tmp_path / "e0-chunks.jsonl"
    first_digest = _write_chunks(first, prefix="A02")
    second_digest = _write_chunks(second, prefix="E0")

    result = materialize_bridge(
        input_chunks=[first, second],
        expected_input_sha256=[first_digest, second_digest],
        expected_input_count=[2, 2],
        output_root=tmp_path / "out",
        attempt_id="A02-E0",
    )
    rows = [
        json.loads(line) for line in
        Path(result["output"]["records_path"]).read_text().splitlines()
    ]

    assert result["input"] == {
        "input_set_count": 2,
        "expected_count": 4,
        "observed_count": 4,
    }
    assert [row["observed_sha256"] for row in result["inputs"]] == [
        first_digest,
        second_digest,
    ]
    assert [row["evidence_id"] for row in rows] == [
        "A02-0", "A02-1", "E0-0", "E0-1",
    ]
    assert all(row["candidate_is_not_evidence"] is True for row in rows)
    assert all(row["citation_eligible"] is False for row in rows)
    assert all(row["evidence_admission_performed"] is False for row in rows)


def test_bridge_rejects_duplicate_id_across_input_sets_before_attempt(
    tmp_path: Path,
) -> None:
    first = tmp_path / "a02-chunks.jsonl"
    second = tmp_path / "e0-chunks.jsonl"
    first_digest = _write_chunks(first)
    second_digest = _write_chunks(second)
    output_root = tmp_path / "out"

    with pytest.raises(
        KnowledgeReaderBridgeError,
        match="bridge_evidence_id_duplicate:2:1",
    ):
        materialize_bridge(
            input_chunks=[first, second],
            expected_input_sha256=[first_digest, second_digest],
            expected_input_count=[2, 2],
            output_root=output_root,
            attempt_id="A02-E0",
        )
    assert not (output_root / "A02-E0").exists()
