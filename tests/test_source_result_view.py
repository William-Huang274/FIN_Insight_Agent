"""Source selection and evidence survive request projection; no quality score."""
from copy import deepcopy
import json

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import SecretStr

from sec_agent.agent_runtime.source_result_view import source_result_view, source_message_views
from sec_agent.agent_runtime.deepseek_structured_agents import ReasoningPreservingChatDeepSeek, _agentic_semantic_value
from sec_agent.agent_runtime.research_orientation import orientation_source_view


def candidate():
    metadata = {"entity_id": "ACME", "period_end": "2026-06-30", "form": "10-Q",
        "publication_date": "2026-08-01", "origin_url": "https://example.org/report",
        "document_coverage": {"complete_document": False, "unread_scope": "images"},
        "parse_revision": {"supersedes": "SRC::old", "reason": "full table repaired"},
        "runtime_compatibility_parse": {"table_cells": "merged geometry not normalized"},
        "new_unknown_field": {"unit": "USD million", "is_guidance": True},
        "parser": "internal-parser", "material_card_version": "internal-v2"}
    return {"result_state": "retrieval_candidate", "document_id": "SRC::one", "title": "ACME Q2 report",
        "published_at": metadata["publication_date"], "url": metadata["origin_url"],
        "eligible": True, "known_at": "2026-08-02", "document_coverage": metadata["document_coverage"],
        "metadata": json.dumps({**metadata, "routing_metadata_v1": json.dumps(metadata)}),
        "mcp_receipt_chain": [{"receipt_id": "private"}],
        "readback": {"source_space": "library", "operation": "read", "document_id": "SRC::one"}}


def test_directory_preserves_selection_scope_revision_and_all_candidates():
    rows = [{**candidate(), "document_id": f"SRC::{i}"} for i in range(20)]
    before = deepcopy(rows)
    view = source_result_view(rows)
    assert rows == before and len(view) == 20
    assert source_result_view(view) == view
    for original, projected in zip(rows, view):
        for key in ("title", "document_id", "published_at", "url", "eligible", "known_at", "document_coverage", "readback"):
            assert projected[key] == original[key]
        meta = projected['metadata']
        assert meta['period_end'] == '2026-06-30'
        assert meta['parse_revision']['supersedes'] == 'SRC::old'
        assert meta['runtime_compatibility_parse']['table_cells'] == 'merged geometry not normalized'
        assert meta['new_unknown_field']['is_guidance'] is True
        assert not {'routing_metadata_v1', 'parser', 'material_card_version', 'publication_date', 'origin_url', 'document_coverage'} & meta.keys()
    assert len(json.dumps(view)) < len(json.dumps(rows)) * .65


def test_company_sources_are_file_cards_not_full_company_profiles():
    source = {'id': 'SRC::one', 'title': 'Issuer report', 'published_at': '2026-08-01',
        'access_state': 'readable', 'preview': 'Short selection excerpt',
        'metadata': {'period_end': '2026-06-30', 'unit': 'USD million',
            'parse_revision': {'supersedes': 'SRC::old'}, 'document_coverage': {'complete_document': False},
            'runtime_compatibility_parse': {'diagnostic': 'Long parser details '*200}}}
    menu = {'result_state': 'retrieval_candidate', 'company_section': 'sources', 'entity_id': 'COMPANY::A',
        'card': {'registered_address': 'address '*500}, 'sources': [source]*20,
        'section_total': 32, 'sources_total': 32, 'next_offset': 20, 'unknown_scope': 'preserve'}
    original = deepcopy(menu)
    view = source_result_view(menu)
    assert 'card' not in view and len(view['sources']) == 20
    assert view['section_total'] == 32 and view['next_offset'] == 20 and view['unknown_scope'] == 'preserve'
    for row in view['sources']:
        assert row['document_id'] == 'SRC::one' and row['readback']['operation'] == 'outline'
        for key in ('period_end', 'unit', 'parse_revision'):
            assert row['metadata'][key] == source['metadata'][key]
        assert view['shared_document_coverage'] == source['metadata']['document_coverage']
    assert source_result_view(view) == view and menu == original
    assert len(json.dumps(view)) < len(json.dumps(menu))*.25


@pytest.mark.parametrize('metadata', ['{bad json', 'null', '[1,2]', 17, 0, None, False, ''])
def test_unrecognized_metadata_and_prose_are_never_parsed_or_dropped(metadata):
    row = {**candidate(), 'metadata': metadata, 'passage': '{"parser":"source text"}'}
    view = source_result_view(row)
    assert view['metadata'] == metadata
    assert view['passage'] == row['passage']


def test_conflicting_period_and_coverage_remain_visible():
    row = candidate()
    meta = json.loads(row['metadata'])
    meta['routing_metadata_v1'] = json.dumps({'period_end': '2025-06-30', 'form': '10-Q'})
    meta['document_coverage'] = {'complete_document': True}
    row['metadata'] = json.dumps(meta)
    view = source_result_view(row)
    assert view['metadata']['routing_metadata_v1'] == {'period_end': '2025-06-30'}
    assert view['metadata']['document_coverage'] != view['document_coverage']
    assert source_result_view(view) == view


def test_reader_keeps_exact_evidence_and_failure_with_same_view_across_roles():
    passage = {**candidate(), 'result_state': 'source_bound_passage', 'passage_id': 'PASSAGE::one',
        'passage': 'Actual 12.5 USD million; FY2026 guidance 20.\n| footnote | cancellable |',
        'content_sha256': 'a'*64, 'source_char_start': 40, 'source_char_end': 120,
        'writer_citable': True, 'numeric_fact_authority': False,
        'truncated': True, 'next_readback': {'character_offset': 120}, 'unit': 'USD million'}
    failure = {'result_state': 'typed_gap', 'reason': 'unread_pages', 'public_information_gap_proved': False}
    original = {'items': [passage, failure]}
    view = source_result_view(original)
    for k, v in passage.items():
        if k not in {'metadata', 'mcp_receipt_chain'}:
            assert view['items'][0][k] == v
    assert view['items'][1] == failure
    assert orientation_source_view(original)['items'][0]['metadata'] == view['items'][0]['metadata']
    assert _agentic_semantic_value(passage)['metadata'] == view['items'][0]['metadata']


def test_native_sdk_fresh_and_restored_history_projects_before_transport():
    stored = {'result': {'observations': [{'content': [candidate()]}]}}
    rows = [HumanMessage(content='Original task'),
        AIMessage(content='', tool_calls=[{'id': 'read-1', 'name': 'RequestSourceAction', 'args': {}}],
                  additional_kwargs={'reasoning_content': 'provider round-trip fixture'}),
        ToolMessage(name='RequestSourceAction', tool_call_id='read-1', content=json.dumps(stored))]
    before = deepcopy(rows)
    payloads = []
    def transport(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json={'id': 'mock', 'object': 'chat.completion', 'created': 0,
            'model': 'deepseek-v4-flash', 'choices': [{'index': 0, 'finish_reason': 'stop',
            'message': {'role': 'assistant', 'content': 'fixture response'}}],
            'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}})
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        chat = ReasoningPreservingChatDeepSeek(model='deepseek-v4-flash', api_key=SecretStr('offline'),
            http_client=client, max_retries=0, use_responses_api=False, tool_context_policy='task_boundary')
        chat.invoke(rows)
        chat.invoke(source_message_views(rows))
    assert rows == before
    assert payloads[0]['messages'] == payloads[1]['messages']
    last = payloads[0]['messages'][-1]
    assert last['tool_call_id'] == 'read-1'
    item = json.loads(last['content'])['result']['observations'][0]['content'][0]
    assert item['readback'] == candidate()['readback']
    assert isinstance(item['metadata'], dict) and 'routing_metadata_v1' not in item['metadata']
    assert 'mcp_receipt_chain' not in last['content']
