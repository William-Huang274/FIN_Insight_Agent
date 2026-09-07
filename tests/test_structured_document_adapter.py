from __future__ import annotations

from hashlib import sha256
from types import SimpleNamespace
from xml.etree import ElementTree

import pytest

from ingestion.structured_document_adapter import (
    StructuredDocumentError,
    StructuredSourceDescriptor,
    _deduplicate_sec_chunk_blocks,
    _footnote_markers,
    _generic_sections_from_html,
    _markdown_page_blocks,
    _markdown_table_rows,
    _ordered_chunk_block_indices,
    _overlapping_block_indices,
    _strip_sec_repeating_navigation,
    _table_footnote_candidates,
    _xml_table_markdown,
)


def _source_mapping() -> dict[str, object]:
    return {
        "route_id": "dell_test_route",
        "title": "Dell test source",
        "publisher": "Dell Technologies",
        "issuer_id": "DELL",
        "ticker": "dell",
        "company": "Dell Technologies Inc.",
        "publication_date": "2026-09-01",
        "fiscal_period": "FY2027_Q2",
        "period_end": "2026-07-31",
        "source_role": "issuer_management_disclosure",
        "document_kind": "html",
        "stable_url": "https://example.test/dell",
        "branches": ["Q1_ISSUER_TRUTH"],
    }


def test_structured_source_descriptor_normalizes_ticker_and_digest() -> None:
    body = b"<html><body>Dell</body></html>"

    source = StructuredSourceDescriptor.from_mapping(
        _source_mapping(),
        raw_body_sha256=sha256(body).hexdigest().upper(),
    )

    assert source.ticker == "DELL"
    assert source.raw_body_sha256 == sha256(body).hexdigest()
    assert source.branches == ("Q1_ISSUER_TRUTH",)


@pytest.mark.parametrize(
    "mutation",
    [
        {"stable_url": "http://example.test/dell"},
        {"document_kind": "docx"},
        {"branches": []},
        {"branches": ["Q1_ISSUER_TRUTH", "Q1_ISSUER_TRUTH"]},
    ],
)
def test_structured_source_descriptor_rejects_invalid_contract(
    mutation: dict[str, object],
) -> None:
    value = {**_source_mapping(), **mutation}

    with pytest.raises(
        StructuredDocumentError,
        match="structured_source_descriptor_invalid",
    ):
        StructuredSourceDescriptor.from_mapping(
            value,
            raw_body_sha256="a" * 64,
        )


def test_footnote_markers_do_not_treat_accounting_negatives_as_footnotes() -> None:
    text = (
        "Change in cash from operating activities (13)% and losses $(66); "
        "other accounting negatives include (95), (47), and (2); "
        "see markers (a), (b), and a cross-reference to Note 13."
    )

    assert _footnote_markers(text) == ["a", "b"]


def test_sec_chunk_deduplication_is_exact_and_preserves_real_fragments() -> None:
    blocks = (
        SimpleNamespace(
            block_type="Text",
            element_ids=["element-a"],
            content="Capital Return\nDell returned capital.",
        ),
        SimpleNamespace(
            block_type="Text",
            element_ids=["element-a"],
            content="Capital Return Dell returned capital.",
        ),
        SimpleNamespace(
            block_type="Text",
            element_ids=["element-a"],
            content="A different retained fragment from the same element.",
        ),
    )

    deduplicated = _deduplicate_sec_chunk_blocks(blocks)

    assert deduplicated == (blocks[0], blocks[2])


def test_sec_chunk_deduplication_keeps_identical_text_without_element_lineage() -> None:
    blocks = (
        SimpleNamespace(block_type="Text", element_ids=[], content="Repeated disclosure."),
        SimpleNamespace(block_type="Text", element_ids=[], content="Repeated disclosure."),
    )

    assert _deduplicate_sec_chunk_blocks(blocks) == blocks


def test_sec_chunk_deduplication_keeps_identical_text_from_distinct_elements() -> None:
    blocks = (
        SimpleNamespace(
            block_type="Text", element_ids=["element-a"], content="Same disclosure."
        ),
        SimpleNamespace(
            block_type="Text", element_ids=["element-b"], content="Same disclosure."
        ),
    )

    assert _deduplicate_sec_chunk_blocks(blocks) == blocks


def test_table_numeric_footnotes_require_explanatory_definition_rows() -> None:
    references = (
        "| Online stores (1) | $70,432 |\n"
        "| Foreign exchange | (95) |\n"
        "| Losses | $(66) |"
    )
    definitions = (
        "| (1) | Includes product sales and digital media content. |\n"
        "| --- | --- |"
    )

    assert _table_footnote_candidates(references) == ({"1"}, set())
    assert _table_footnote_candidates(definitions) == (set(), {"1"})


def test_raw_splitter_span_includes_next_table_before_text_cleanup() -> None:
    offsets = [(0, 100), (102, 220)]
    raw_chunk = "x" * 103

    assert _overlapping_block_indices(offsets, start=0, raw_length=len(raw_chunk)) == [0, 1]


def test_xml_table_projection_preserves_rows_and_declared_colspan() -> None:
    table = ElementTree.fromstring(
        """
        <table>
          <row><cell colspan="2"><p>Guidance</p></cell></row>
          <row><cell><p>Revenue</p></cell><cell><p>$192 billion</p></cell></row>
        </table>
        """
    )

    markdown = _xml_table_markdown(table)

    assert _markdown_table_rows(markdown) == [
        ["Guidance", ""],
        ["Revenue", "$192 billion"],
    ]


def test_markdown_table_round_trip_keeps_escaped_pipe_inside_one_cell() -> None:
    table = ElementTree.fromstring(
        "<table><row><cell>A | B</cell><cell>Value</cell></row></table>"
    )

    assert _markdown_table_rows(_xml_table_markdown(table)) == [
        ["A | B", "Value"]
    ]


def test_repeating_sec_navigation_filter_is_exact() -> None:
    assert _strip_sec_repeating_navigation(
        "Table of Contents\nRisk discussion\nTable of Contents analysis"
    ) == "Risk discussion\nTable of Contents analysis"


def test_section_owned_markdown_page_retains_table_boundary() -> None:
    blocks = _markdown_page_blocks(
        "ITEM 1A — RISK FACTORS\n\n| Metric | Value |\n| --- | --- |\n"
        "| Backlog | $95 billion |\n\nFollowing text.",
        17,
    )

    assert [block.kind for block in blocks] == ["text", "table", "text"]
    assert _markdown_table_rows(blocks[1].content) == [
        ["Metric", "Value"],
        ["Backlog", "$95 billion"],
    ]
    assert all(block.page_start == block.page_end == 17 for block in blocks)


def test_trafilatura_projection_keeps_anchor_text_and_table_rows() -> None:
    pytest.importorskip("trafilatura")
    body = b"""
    <html><body><article>
      <h2>Story Highlights</h2>
      <p>Dell selected <a href="https://example.test/factory">Dell AI Factory</a>
      solutions for a new cluster.</p>
      <table>
        <tr><th>Metric</th><th>Value</th></tr>
        <tr><td>GPU count</td><td>4,000</td></tr>
      </table>
    </article></body></html>
    """

    sections = _generic_sections_from_html(body, "Dell test source")
    blocks = [block for section in sections for block in section.blocks]

    combined = "\n".join(block.content for block in blocks)
    assert "Dell selected Dell AI Factory solutions for a new cluster." in combined
    table_blocks = [block for block in blocks if block.kind == "table"]
    assert len(table_blocks) == 1
    assert _markdown_table_rows(table_blocks[0].content) == [
        ["Metric", "Value"],
        ["GPU count", "4,000"],
    ]
