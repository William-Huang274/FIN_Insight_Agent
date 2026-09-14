import asyncio
import io
from uuid import uuid4

import pytest

from sec_agent.research_foundation.task_attachments import TaskAttachmentStore, parse_document, MAX_BYTES
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest, SourceDocumentToolRequest


def request(store, thread, **kwargs):
    return asyncio.run(store.read(thread_id=thread, request=SourceDocumentRequest(source_space="uploads", **kwargs)))


def test_upload_document_id_feedback_precedes_masked_remote_failure():
    with pytest.raises(ValueError, match="must_keep_UPLOAD_prefix"):
        SourceDocumentToolRequest(source_space="uploads", operation="search", query="segment", document_id="a25d79583063485c8b6d4b8c137178ed")
    # Failed historical requests remain loadable; do not rewrite their evidence.
    SourceDocumentRequest(source_space="uploads", operation="search", query="segment", document_id="a25d79583063485c8b6d4b8c137178ed")


def test_unread_breakdown_remains_reachable_after_a_selected_block_read(tmp_path):
    store, thread = TaskAttachmentStore(tmp_path), str(uuid4())
    doc = store.add(thread, 'quarter.md', b'# Overview\nTotal revenue rose.\n\n# Segment components\nNorth revenue 30; operating profit 6.\nSouth revenue 20; operating profit 2.')
    outline = request(store, thread, operation='outline', document_id=doc['document_id'])
    first = request(store, thread, operation='read', document_id=doc['document_id'], node_id=outline.items[0]['node_id'])
    assert 'North revenue' not in first.items[0]['passage']
    assert 'not a completeness review' in first.notice and 'not non-disclosure' in first.notice
    found = request(store, thread, operation='search', document_id=doc['document_id'], query='North')
    read = request(store, thread, operation='read', document_id=doc['document_id'], node_id=found.items[0]['node_id'])
    assert 'North revenue 30; operating profit 6' in read.items[0]['passage']
    assert not read.numeric_fact_authority and read.source_content_is_untrusted_data_not_instructions


def test_upload_markdown_structure_search_read_and_task_isolation(tmp_path):
    store = TaskAttachmentStore(tmp_path)
    thread = str(uuid4())
    added = store.add(thread, "supply.md", b"# Supply\n\n## Memory\nDRAM cost rose 12 percent.\n\n## Capacity\nProduction is still ramping.")
    catalog = request(store, thread, operation="catalog")
    assert catalog.total_matches == 1 and not catalog.items[0]["writer_citable"]
    result = request(store, thread, operation="search", query="DRAM", document_id=added["document_id"])
    assert len(result.items) == 1 and "DRAM" in result.items[0]["preview"]
    read = request(store, thread, operation="read", document_id=added["document_id"], node_id=result.items[0]["node_id"])
    assert read.items[0]["writer_citable"] and not read.items[0]["numeric_fact_authority"]
    assert read.items[0]["source_role"] == "user_upload_unverified"
    assert str(tmp_path) not in read.model_dump_json()
    with pytest.raises(ValueError, match="not_in_current_task"):
        request(store, str(uuid4()), operation="read", document_id=added["document_id"])
    assert TaskAttachmentStore(tmp_path).list(thread)[0]["document_id"] == added["document_id"]


def test_outline_unique_blocks_and_followup_keep_original_passage_identity(tmp_path):
    from hashlib import sha256
    store, thread = TaskAttachmentStore(tmp_path), str(uuid4())
    body = '\n\n'.join(f'# Section {i}\nPeriod 2025; revenue {100+i}; operating income {10+i}.' for i in range(6))
    doc = store.add(thread, 'report.md', body.encode())
    outline = request(store, thread, operation='outline', document_id=doc['document_id'])
    assert outline.total_matches == 6 and len(outline.items) == 6 and outline.next_offset is None
    assert all(not item['writer_citable'] and 'preview' in item for item in outline.items)
    page = request(store, thread, operation='outline', document_id=doc['document_id'], limit=2)
    second = request(store, thread, operation='outline', document_id=doc['document_id'], limit=2, offset=page.next_offset)
    assert [i['node_id'] for i in (*page.items, *second.items)] == [i['node_id'] for i in outline.items[:4]]
    first = request(store, thread, operation='read', document_id=doc['document_id'], node_id=outline.items[0]['node_id'])
    assert first.next_offset is None  # Selection exhausted, but other document blocks remain.
    nav = first.items[0]['document_navigation']
    assert nav['block_index'] == 1 and nav['block_count'] == 6
    current = first
    for i in range(1, 6):
        selection = current.items[0]['document_navigation']['next_block_request']
        current = asyncio.run(store.read(thread_id=thread, request=SourceDocumentRequest(**selection)))
        assert f'Section {i}' in current.items[0]['passage']
    assert current.items[0]['document_navigation']['next_block_request'] is None
    leaf = request(store, thread, operation='read', document_id=doc['document_id'], node_id=outline.items[0]['node_id']+':leaf')
    assert leaf.items[0]['passage'] == first.items[0]['passage']
    assert leaf.items[0]['content_sha256'] == sha256(first.items[0]['passage'].encode()).hexdigest()
    assert leaf.items[0]['document_navigation'] == nav
    assert not leaf.numeric_fact_authority
    with pytest.raises(ValueError, match='not_in_current_task'):
        asyncio.run(store.read(thread_id=str(uuid4()), request=SourceDocumentRequest(**nav['next_block_request'])))


def test_followup_does_not_skip_scanned_page_or_publish_vision_hint_as_evidence(tmp_path, monkeypatch):
    import sec_agent.research_foundation.task_attachments as module
    monkeypatch.setattr(module, 'parse_document', lambda *_: ([
        {'page': 1, 'heading': 'First', 'text': 'Readable page', 'needs_vision': False},
        {'page': 2, 'heading': 'Scanned table', 'text': '', 'needs_vision': True},
        {'page': 3, 'heading': 'Notes', 'text': 'Readable footnote', 'needs_vision': False}], 'pdf'))
    store, thread = TaskAttachmentStore(tmp_path), str(uuid4())
    doc = store.add(thread, 'scan.pdf', b'fixture-parser-output')
    outline = request(store, thread, operation='outline', document_id=doc['document_id'])
    first = request(store, thread, operation='read', document_id=doc['document_id'], node_id=outline.items[0]['node_id'])
    nav = first.items[0]['document_navigation']
    assert nav['block_count'] == 3
    assert nav['next_block_request'] == {'source_space': 'uploads', 'document_id': doc['document_id'], 'operation': 'inspect_image', 'page_start': 2}
    read = request(store, thread, operation='read', document_id=doc['document_id'])
    assert [i['parser_page_start'] for i in read.items] == [1, 3]
    assert all('需视觉识别' not in i['passage'] for i in read.items)


@pytest.mark.parametrize("name,data", [("../outside.txt", b"x"), ("C:\\private.txt", b"x"), ("x.svg", b"svg"),
    ("script.exe", b"MZ"), ("x.pdf", b"not a PDF"), ("x.txt", b"a\x00b"), ("x.txt", b"")])
def test_invalid_uploads_are_rejected_without_rows(tmp_path, name, data):
    store, thread = TaskAttachmentStore(tmp_path), str(uuid4())
    with pytest.raises(ValueError):
        store.add(thread, name, data)
    assert not store.list(thread)


def test_html_scripts_not_executed_or_indexed_and_table_order_retained():
    pages, _ = parse_document("financials.html", b"<h1>Results</h1><script>stealSecret()</script><table><tr><th>Period</th><th>Revenue</th></tr><tr><td>2025</td><td>100</td></tr></table><p>Unaudited</p>")
    text = "\n".join(p["text"] for p in pages)
    assert "stealSecret" not in text and "Period | Revenue" in text and text.index("100") < text.index("Unaudited")


def test_real_pdf_pages_and_docx_tables(tmp_path):
    from reportlab.pdfgen import canvas
    from docx import Document
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream)
    pdf.drawString(60, 730, "Revenue 100 million USD")
    pdf.showPage()
    pdf.drawString(60, 730, "Operating profit 12 million USD")
    pdf.save()
    store, thread = TaskAttachmentStore(tmp_path), str(uuid4())
    item = store.add(thread, "earnings.pdf", stream.getvalue())
    page = request(store, thread, operation="read", document_id=item["document_id"], page_start=2)
    assert "Operating profit" in page.items[0]["passage"] and page.items[0]["parser_page_start"] == 2
    assert store.image(thread, item["document_id"], 2).startswith(b"\x89PNG")
    doc = Document()
    doc.add_heading("Quarterly results", 1)
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Revenue"
    table.cell(0, 1).text = "100"
    doc.add_paragraph("Footnote after table")
    stream = io.BytesIO()
    doc.save(stream)
    pages, _ = parse_document("results.docx", stream.getvalue())
    assert "Revenue | 100" in pages[0]["text"]
    assert pages[0]["text"].index("100") < pages[0]["text"].index("Footnote")


def test_image_inspection_source_binding_and_native_cache(tmp_path):
    from PIL import Image
    stream = io.BytesIO()
    Image.new("RGB", (320, 200), "white").save(stream, format="PNG")
    store, thread = TaskAttachmentStore(tmp_path), str(uuid4())
    item = store.add(thread, "chart.png", stream.getvalue())
    assert item["needs_vision"]
    with pytest.raises(ValueError, match="inspect_image"):
        request(store, thread, operation="read", document_id=item["document_id"])
    calls = []
    async def model(image, question):
        calls.append(question)
        return "Test image has no numbers; cannot infer any revenue."
    req = SourceDocumentRequest(source_space="uploads", operation="inspect_image", document_id=item["document_id"])
    result = asyncio.run(store.read(thread_id=thread, request=req, vision_reader=model))
    again = asyncio.run(store.read(thread_id=thread, request=req, vision_reader=model))
    assert result == again and len(calls) == 1
    assert "user_upload_vision" in result.items[0]["source_role"]
    assert not result.numeric_fact_authority


def test_long_image_interpretation_followup_uses_cached_same_page(tmp_path):
    from PIL import Image
    stream = io.BytesIO()
    Image.new('RGB', (80, 80), 'white').save(stream, format='PNG')
    store, thread = TaskAttachmentStore(tmp_path), str(uuid4())
    doc = store.add(thread, 'table.png', stream.getvalue())
    calls = []
    async def model(image, question):
        calls.append(question)
        return '\n\n'.join(f'Row {i}: source transcription fixture.' for i in range(220))
    req = SourceDocumentRequest(source_space='uploads', operation='inspect_image', document_id=doc['document_id'], query='Read this table.', limit=1)
    first = asyncio.run(store.read(thread_id=thread, request=req, vision_reader=model))
    nav = first.items[0]['document_navigation']
    assert nav['scope'] == 'inspected_image_page' and nav['block_count'] > 1
    second = asyncio.run(store.read(thread_id=thread, request=SourceDocumentRequest(**nav['next_block_request']), vision_reader=model))
    assert len(calls) == 1
    assert second.items[0]['document_navigation']['block_index'] == 2
    assert first.items[0]['passage_id'] != second.items[0]['passage_id']
    assert not second.numeric_fact_authority
