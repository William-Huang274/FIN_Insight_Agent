from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256

import pytest

from sec_agent.research_foundation.saved_web_navigation import read_saved_web_window
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest


def original(start=20000, text='Original disclosed text. ' * 100):
    digest = sha256(text.encode()).hexdigest()
    return dict(result_state='source_bound_passage', document_id='WEB::doc',
        passage_id=f'PASSAGE::WEB::doc::{start}::{digest[:16]}', passage=text,
        content_sha256=digest, writer_citable=True, numeric_fact_authority=False,
        publication_date='2026-08-01', source_url='https://example.com/results',
        source_document_completeness_verified=False, truncated=True,
        source_locator=dict(document_id='WEB::doc', character_start=start,
            character_end=start+len(text), content_sha256=digest, capture_receipt_digest='a'*64))


def read(rows, offset=20000, size=8000, **kw):
    return read_saved_web_window(SourceDocumentRequest(source_space='web', operation='read',
        document_id='WEB::doc', offset=offset, max_characters=size), rows,
        research_as_of=kw.get('as_of', datetime(2026, 9, 24, tzinfo=timezone.utc)))


def test_saved_window_preserves_original_and_reports_bounded_coverage():
    row = original(); before = deepcopy(row)
    result = read([row, deepcopy(row)])
    assert result.items == (row,) and row == before
    assert result.execution_receipt.status == 'ok' and result.next_offset is None
    assert not result.numeric_fact_authority and not result.evidence_admission_performed
    boundary = read([row], offset=0)
    assert boundary.execution_receipt.status == 'coverage_boundary'
    assert boundary.items[0]['readback']['offset'] == 20000
    assert not boundary.items[0]['writer_citable'] and 'passage' not in boundary.items[0]


def test_saved_subwindow_retains_capture_and_has_exact_hash_identity():
    row = original()
    result = read([row], offset=20004, size=2000)
    part = result.items[0]
    assert part['passage'] == row['passage'][4:2004]
    assert part['source_locator']['character_start'] == 20004
    assert part['saved_parent_passage_id'] == row['passage_id']
    assert part['source_locator']['capture_receipt_digest'] == 'a'*64
    assert part['content_sha256'] == sha256(part['passage'].encode()).hexdigest()
    assert result.next_offset == 22004


def test_unknown_or_candidate_documents_are_not_promoted():
    row = original(); row['result_state'] = 'retrieval_candidate'
    assert read([row]) is None and read([]) is None
    row = original(); row['document_id'] = 'WEB::another'
    assert read([row]) is None


def test_source_integrity_capture_conflicts_and_cutoff_are_not_bypassed():
    row = original(); row['passage'] += 'bad'
    with pytest.raises(ValueError, match='locator_invalid'): read([row])
    row = original(); row['content_sha256'] = 'b'*64
    with pytest.raises(ValueError, match='identity_invalid'): read([row])
    row = original(30000); row['source_locator']['capture_receipt_digest'] = 'b'*64
    with pytest.raises(ValueError, match='multiple_captures'): read([original(), row])
    row = original(); row['source_url'] = 'https://example.com/conflict'
    with pytest.raises(ValueError, match='identity_conflict'): read([original(), row])
    with pytest.raises(ValueError, match='publication_after'): read([original()],
        as_of=datetime(2026, 7, 1, tzinfo=timezone.utc))


def test_mcp_saved_route_uses_scoped_sources_and_registers_exact_read():
    import asyncio
    from mcp import Client
    from test_research_mcp import _build_server, _method_arguments
    from sec_agent.research_foundation.source_bound_calculator import ObservedSourceRegistry
    from sec_agent.research_foundation.mcp_server import GET_RESEARCH_METHOD_TOOL
    row = original(); registry = ObservedSourceRegistry(); live_calls = []
    def live(**kw):
        live_calls.append(kw['request'].document_id)
        raise ValueError('web_document_not_discovered_in_this_scope_search_first')
    async def exercise():
        server = _build_server(source_document_reader=live, source_registry=registry)
        registry.remember('read_source_document', {'operation': 'read', 'items': [row]})
        async with Client(server) as client:
            method = await client.call_tool(GET_RESEARCH_METHOD_TOOL, _method_arguments(['Q1_ISSUER_TRUTH']))
            args = {'branch_id': 'Q1_ISSUER_TRUTH', 'run_scope': method.structured_content['run_scope'],
                'request': {'source_space': 'web', 'operation': 'read', 'document_id': 'WEB::doc',
                            'offset': 20000, 'max_characters': 8000}}
            result = await client.call_tool('read_source_document', args)
            assert not result.is_error and result.structured_content['items'] == [row]
            assert not live_calls and registry.get(row['passage_id']) == row
            invalid = await client.call_tool('read_source_document', {**args, 'branch_id': 'Q2_DEMAND_QUALITY'})
            assert invalid.is_error and not live_calls
            unknown = await client.call_tool('read_source_document', {**args,
                'request': {**args['request'], 'document_id': 'WEB::unknown'}})
            assert unknown.is_error and live_calls == ['WEB::unknown']
    asyncio.run(exercise())
