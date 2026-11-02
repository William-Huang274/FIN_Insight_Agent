import json
from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace

import pytest
from langchain_core.messages import ToolMessage

from sec_agent.agent_runtime.source_references import (
    reference_handle, reference_sources, resolve_reference, present_references,
    expand_references, render_answer_references,
)
from sec_agent.agent_runtime.source_search_scope import search_scope
from sec_agent.agent_runtime.public_source_restore import validated_public_source


def source():
    text = 'Revenue 100; contractual payment terms vary by customer.'
    digest = sha256(text.encode()).hexdigest()
    key = 'PASSAGE::WEB::document::0::' + digest[:16]
    row = dict(result_state='source_bound_passage', passage_id=key, passage=text,
        source_role='external_public_source_unverified', document_id='WEB::document',
        content_sha256=digest, source_url='https://example.com/disclosure', numeric_fact_authority=False, writer_citable=True,
        source_locator=dict(document_id='WEB::document', source_url='https://example.com/disclosure',
            character_start=0, character_end=len(text), content_sha256=digest, capture_receipt_digest='a'*64))
    return key, row


def state():
    key, row = source()
    data = {'operation': 'read', 'items': [row]}
    return key, {'messages': [ToolMessage(name='read_public_source', tool_call_id='read1',
                     content=json.dumps(data), artifact=data)]}


def test_short_reference_survives_restart_and_does_not_promote_candidates():
    key, current = state()
    old = deepcopy(current)
    sources, handles = reference_sources(current)
    handle = reference_handle(key)
    assert handles[handle] == key
    assert reference_sources(deepcopy(current)) == (sources, handles)
    body = {'request': {'operands': {'a': {'source_id': handle, 'literal': '100'}}},
            'report': {'narrative_markdown': '解释 [' + handle + ']'}}
    expanded = expand_references(body, current)
    assert expanded['request']['operands']['a']['source_id'] == key
    assert expanded['report']['narrative_markdown'] == '解释 [' + key + ']'
    assert current == old and body['request']['operands']['a']['source_id'] == handle
    with pytest.raises(ValueError, match='unobserved'):
        expand_references(body, {'messages': []})
    assert 'citation_handle' not in present_references({'result_state': 'retrieval_candidate', 'passage_id': key})
    assert present_references(sources[key])['citation_handle'] == handle


def test_unique_abbreviations_only_and_display_never_rewrites_conclusions():
    key, current = state(); sources, handles = reference_sources(current)
    short = 'PASSAGE::…' + key[-16:]
    assert resolve_reference(short, sources, handles) == key
    with pytest.raises(ValueError, match='ambiguous'):
        resolve_reference(short, {key: {}, 'PASSAGE::another::'+key[-16:]: {}}, {})
    text = 'This remains a hypothesis [' + reference_handle(key) + ']'
    rendered, bound, unknown = render_answer_references(text, current)
    assert rendered.startswith('This remains a hypothesis [REF-')
    assert 'https://example.com/disclosure' not in rendered
    assert bound[reference_handle(key)]['source']['source_url'] == 'https://example.com/disclosure'
    assert bound[reference_handle(key)]['source_id'] == key and unknown == []
    calc = 'CALC::' + 'a'*64
    assert resolve_reference(calc[:30], {calc: {}}, {}) == calc
    with pytest.raises(ValueError, match='ambiguous'):
        resolve_reference(calc[:30], {calc: {}, calc[:40]+'b'*24: {}}, {})


def test_typed_suffix_and_reader_projection_keep_identity_without_inventing_claim():
    from sec_agent.agent_runtime.source_references import answer_citations
    key, current = state()
    text = 'A hypothesis [passage::' + key.rsplit('::', 1)[-1] + ']'
    rendered, bound, unknown = render_answer_references(text, current)
    assert unknown == [] and rendered == 'A hypothesis [' + reference_handle(key) + ']'
    public = answer_citations(bound)[reference_handle(key)]
    assert public['claim']['kind'] == 'source_reference'
    assert public['sources'][0]['source_id'] == key
    assert public['sources'][0]['text'] == source()[1]['passage']
    calculation = {'expression': 'x / y', 'operands': {'x': {'source_id': key, 'literal': '2'}}, 'value_decimal': '2'}
    calc_view = answer_citations({'REF-test': {'source_id': 'CALC::test', 'source': calculation}})
    assert calc_view['REF-test']['sources'][0]['calculation'] == calculation
    sources, handles = reference_sources(current)
    ambiguous = {**sources, 'PASSAGE::other::' + key.rsplit('::', 1)[-1]: {}}
    with pytest.raises(ValueError, match='ambiguous'):
        resolve_reference('passage::' + key.rsplit('::', 1)[-1], ambiguous, handles)


def test_repeated_clean_replay_keeps_receipts_but_isolates_native_history_and_notes(tmp_path):
    from sec_agent.agent_runtime.organization_harness_session import receipt_replay_identity
    from uuid import uuid4
    original = receipt_replay_identity(tmp_path, 'task', 'a'*64, True)
    branch_id = str(uuid4())
    new = receipt_replay_identity(tmp_path, 'task', 'a'*64, True, branch_id)
    assert new != original and new[0].parent == original[0]
    assert new[0] == new[2] and new[1] != original[1]
    assert new == receipt_replay_identity(tmp_path, 'task', 'a'*64, True, branch_id)
    assert receipt_replay_identity(tmp_path, 'task', None, False) == (tmp_path, 'task', tmp_path)
    with pytest.raises(ValueError):
        receipt_replay_identity(tmp_path, 'task', 'a'*64, False, branch_id)


def test_search_scope_is_not_library_or_disclosure_absence():
    request = SimpleNamespace(operation='search', query='rare filing', document_id=None,
                              source_space='organization', offset=0, organization_filter=None)
    body = dict(items=[], total_matches=0, next_offset=None, source_snapshot_sha256='fixed')
    value = search_scope(body, request, public_web=True)['search_coverage']
    assert not value['issuer_non_disclosure_established'] and not value['unfiltered_catalog_returned_in_full']
    assert 'read_public_source' in value['available_followup_tools']
    assert 'read_public_source' not in search_scope(body, request)['search_coverage']['available_followup_tools']
    request.operation='catalog'; request.query=''
    assert search_scope(body, request)['search_coverage']['unfiltered_catalog_returned_in_full']
    request.offset=20
    assert not search_scope(body, request)['search_coverage']['unfiltered_catalog_returned_in_full']


def test_public_source_validation_preserves_original_and_rejects_tampering():
    _, row=source()
    assert validated_public_source(row)==row
    for field, value in [('passage','changed'),('numeric_fact_authority', True),('source_url','file:///private')]:
        with pytest.raises(ValueError):
            validated_public_source({**row,field:value})
