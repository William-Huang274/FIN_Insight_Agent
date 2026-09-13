"""Source projection regression retained from the retired qualification runner."""
import copy
import hashlib
import pytest
from ingestion import retrieval_nodes as runner

def _text_sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _span_rows(*rows: tuple[str, list[str], str]) -> list[dict[str, object]]:
    return [
        {
            "span_index": index,
            "span_kind": kind,
            "source_block_ids": block_ids,
            "content_sha256": _text_sha(content),
            "content": content,
        }
        for index, (kind, block_ids, content) in enumerate(rows)
    ]


def test_mixed_table_chunk_retains_only_its_non_table_blocks_with_lineage() -> None:
    route_id = "micron_release"
    raw_sha = "a" * 64
    section_content = "Narrative about customer agreements\n\n| Metric | Value |"
    narrative = "Narrative about customer agreements"
    mixed_fragment = "about customer agreements"
    standalone = "Standalone prose"
    table = "| Metric | Value |\n| --- | --- |\n| Revenue | 10 |"
    authority = {
        "candidate_is_not_evidence": True,
        "numeric_authority": False,
        "citation_eligible": False,
    }
    common = {
        "parent_document_id": "DOC::1",
        "parent_section_id": "SECTION::1",
        "route_id": route_id,
        "raw_body_sha256": raw_sha,
        **authority,
    }
    corpus = {
        "documents": [
            {
                "document_id": "DOC::1",
                "route_id": route_id,
                "raw_body_sha256": raw_sha,
                "company": "Micron",
                "issuer_id": "MICRON",
                "ticker": "MU",
                "fiscal_period": "FY2026_Q3",
                "period_end": "2026-05-28",
                "publication_date": "2026-06-24",
                "source_role": "supplier_management_disclosure",
                "stable_url": "https://example.test/micron",
                "title": "Micron release",
                "document_kind": "html",
            }
        ],
        "sections": [
            {
                **{
                    key: value
                    for key, value in common.items()
                    if key != "parent_section_id"
                },
                "section_id": "SECTION::1",
                "section_path": ["Results"],
                "content": section_content,
                "content_sha256": _text_sha(section_content),
                "page_start": None,
                "page_end": None,
            }
        ],
        "blocks": [
            {
                **common,
                "block_id": "BLOCK::P1",
                "block_kind": "p",
                "block_index": 0,
                "content": narrative,
                "content_sha256": _text_sha(narrative),
            },
            {
                **common,
                "block_id": "BLOCK::T1",
                "block_kind": "table",
                "block_index": 1,
                "content": table,
                "content_sha256": _text_sha(table),
                "table_id": "TABLE::1",
                "table_row_count": 2,
                "table_column_count": 2,
            },
            {
                **common,
                "block_id": "BLOCK::P2",
                "block_kind": "p",
                "block_index": 2,
                "content": standalone,
                "content_sha256": _text_sha(standalone),
            },
        ],
        "chunks": [
            {
                **common,
                "chunk_id": "CHUNK::MIXED",
                "contains_table": True,
                "block_ids": ["BLOCK::P1", "BLOCK::T1"],
                "text": f"{mixed_fragment}\n\n{table}",
                "text_sha256": _text_sha(f"{mixed_fragment}\n\n{table}"),
                "retrieval_spans": (
                    mixed_spans := _span_rows(
                        ("p", ["BLOCK::P1"], mixed_fragment),
                        ("table", ["BLOCK::T1"], table),
                    )
                ),
                "retrieval_span_count": len(mixed_spans),
                "retrieval_spans_sha256": runner.canonical_digest(mixed_spans),
                "retrieval_span_text_sha256": _text_sha(
                    "\n".join(row["content"] for row in mixed_spans)
                ),
                "section_chunk_index": 0,
            },
            {
                **common,
                "chunk_id": "CHUNK::MIXED-OVERLAP",
                "contains_table": True,
                "block_ids": ["BLOCK::P1", "BLOCK::T1"],
                "text": f"{mixed_fragment}\n\n{table}",
                "text_sha256": _text_sha(f"{mixed_fragment}\n\n{table}"),
                "retrieval_spans": mixed_spans,
                "retrieval_span_count": len(mixed_spans),
                "retrieval_spans_sha256": runner.canonical_digest(mixed_spans),
                "retrieval_span_text_sha256": _text_sha(
                    "\n".join(row["content"] for row in mixed_spans)
                ),
                "section_chunk_index": 1,
            },
            {
                **common,
                "chunk_id": "CHUNK::PROSE",
                "contains_table": False,
                "block_ids": ["BLOCK::P2"],
                "text": standalone,
                "text_sha256": _text_sha(standalone),
                "retrieval_spans": (
                    prose_spans := _span_rows(
                        ("p", ["BLOCK::P2"], standalone),
                    )
                ),
                "retrieval_span_count": len(prose_spans),
                "retrieval_spans_sha256": runner.canonical_digest(prose_spans),
                "retrieval_span_text_sha256": _text_sha(standalone),
                "section_chunk_index": 2,
            },
        ],
    }

    first = runner.build_retrieval_nodes(corpus)
    second = runner.build_retrieval_nodes(corpus)
    mixed = next(row for row in first["prose"] if row["node_kind"] == "mixed_prose_span")

    assert mixed["node_id"].startswith("MIXEDPROSE::")
    assert mixed["node_id"] == next(
        row["node_id"]
        for row in second["prose"]
        if row["node_kind"] == "mixed_prose_span"
    )
    assert mixed["content"] == mixed_fragment
    assert narrative not in mixed["content"]
    assert table not in mixed["content"]
    assert mixed["source_chunk_id"] == "CHUNK::MIXED"
    assert mixed["source_chunk_ids"] == ["CHUNK::MIXED", "CHUNK::MIXED-OVERLAP"]
    assert mixed["source_block_ids"] == ["BLOCK::P1"]
    assert mixed["parent_document_id"] == "DOC::1"
    assert mixed["parent_section_id"] == "SECTION::1"
    assert first["parents"][0]["parent_section_id"] == "SECTION::1"
    assert first["parents"][0]["section_path"] == ["Results"]
    assert [row["node_id"] for row in first["tables"]] == ["BLOCK::T1"]
    assert [row["node_id"] for row in first["prose"] if row["node_kind"] == "chunk"] == [
        "CHUNK::PROSE"
    ]
    assert first["coverage"]["table_containing_chunk_count"] == 2
    assert first["coverage"]["mixed_prose_source_chunk_count"] == 2
    assert first["coverage"]["mixed_prose_leaf_count"] == 1
    assert first["coverage"]["mixed_prose_raw_span_run_count"] == 2
    assert first["coverage"]["mixed_prose_deduplicated_run_count"] == 1
    assert first["coverage"]["mixed_prose_raw_span_character_count"] == 2 * len(
        mixed_fragment
    )
    assert first["coverage"]["mixed_prose_candidate_character_count"] == len(
        mixed_fragment
    )
    assert first["coverage"]["table_or_image_only_chunk_count"] == 0
    assert first["coverage"]["mixed_non_table_unique_block_count"] == 1
    assert first["coverage"]["mixed_non_table_exclusive_block_count"] == 1
    assert first["coverage"]["mixed_non_table_exclusive_character_count"] == len(
        narrative
    )

    cross_lineage = copy.deepcopy(corpus)
    cross_lineage["blocks"][1]["parent_section_id"] = "SECTION::OTHER"
    with pytest.raises(runner.QualificationError, match="chunk_block_lineage_drift"):
        runner.build_retrieval_nodes(cross_lineage)

    flag_drift = copy.deepcopy(corpus)
    flag_drift["chunks"][0]["contains_table"] = False
    with pytest.raises(runner.QualificationError, match="chunk_contains_table_span_drift"):
        runner.build_retrieval_nodes(flag_drift)
