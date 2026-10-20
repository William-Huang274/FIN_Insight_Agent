"""Literal paper navigation, not automatic findings or financial acceptance."""
import asyncio
from copy import deepcopy

import pytest
from langchain_core.messages import HumanMessage, ToolMessage
from mcp import Client
from sec_agent.agent_runtime.case_review_agent import build_case_reviewer, case_mcp_tools
from sec_agent.agent_runtime.review_inspection import read_quoted_location, read_location, bind_location
from test_research_convergence import artifact_fixture
from test_case_review_agent import ScriptedNativeChat, call
from test_research_mcp import _build_server


def sample(text):
    a = artifact_fixture()
    paper = deepcopy(a.read_paper('P01'))
    paper['claims'][0]['statement'] = text
    return a.with_revisions({'P01': {'status': 'revision_submitted', 'workpaper': paper}})


def test_exact_unicode_quote_binds_only_selected_text_and_current_version():
    a = sample('前言🙂。金额 **5,988**；后文。')
    cid = a.read_paper('P01')['claims'][0]['claim_id']
    quote = '金额 **5,988**'
    v = read_quoted_location(a, 'P01', '/claims/'+cid+'/statement', quote)
    assert v['text'] == quote and v['offset'] == 4
    assert v['match_end'] == 4 + len(quote)
    m = ToolMessage(content='', artifact=v, name='read_review_location', tool_call_id='q')
    assert bind_location(a, [m], 'P01', v['location_id']) == quote
    with pytest.raises(ValueError, match='stale'):
        bind_location(sample('新版'+quote), [m], 'P01', v['location_id'])
    # Literal matching never removes markup or changes numbers.
    missing = read_quoted_location(a, 'P01', '/claims/0/statement', '金额 5,988')
    assert missing['status'] == 'quote_not_found' and 'location_id' not in missing


def test_multiple_matches_return_choices_not_accepted_locations():
    a = sample('甲 金额5,988 说明一；乙 金额5,988 说明二。')
    v = read_quoted_location(a, 'P01', '/claims/0/statement', '金额5,988')
    assert v['total_matches'] == 2 and v['selected_match'] is None
    assert 'text' not in v and 'location_id' not in v
    assert all('location_id' not in c for c in v['candidates'])
    args = v['candidates'][1]['readback']['arguments']
    chosen = read_quoted_location(a, args['paper_id'], args['field_path'], args['quote'],
        match_index=args['match_index'], paper_digest=args['paper_digest'])
    assert chosen['offset'] == v['candidates'][1]['match_start']
    assert chosen['text'] == '金额5,988'
    with pytest.raises(ValueError, match='stale'):
        read_quoted_location(sample('新版'), args['paper_id'], args['field_path'], args['quote'],
            match_index=args['match_index'], paper_digest=args['paper_digest'])
    with pytest.raises(ValueError, match='requires_candidate'):
        read_quoted_location(a, 'P01', '/claims/0/statement', '金额5,988', match_index=0)


def test_overlapping_matches_and_pagination_are_bounded():
    a = sample('a'*10000)
    v = read_quoted_location(a, 'P01', '/claims/0/statement', 'aa')
    assert v['total_matches'] == 9999 and len(v['candidates']) == 6
    assert sum(len(c['context']) for c in v['candidates']) <= 6000
    args = v['next_page']['arguments']
    page = read_quoted_location(a, args['paper_id'], args['field_path'], args['quote'],
        match_offset=args['match_offset'], paper_digest=args['paper_digest'])
    assert page['candidates'][0]['match_index'] == 6


@pytest.mark.parametrize('quote,kwargs', [('', {}), (' '*2, {}), ('x'*6001, {}),
    ('a', {'match_offset': -1}), ('a', {'max_characters': 0}),
    ('a', {'match_index': 20, 'paper_digest': 'stale'})])
def test_invalid_selections_fail_without_rewriting(quote, kwargs):
    with pytest.raises(ValueError):
        read_quoted_location(sample('aaa'), 'P01', '/claims/0/statement', quote, **kwargs)


def test_native_tool_quote_conflicting_offset_and_legacy_read():
    async def run():
        a = sample('前文 selected exact 后文')
        proposal = [call('read_review_location', {'paper_id':'P01', 'field_path':'/claims/0/statement',
            'quote':'selected exact'}, 'quote'),
            call('read_review_location', {'paper_id':'P01', 'field_path':'/claims/0/statement',
                'quote':'selected exact', 'offset':0}, 'conflict'),
            call('read_review_location', {'paper_id':'P01', 'field_path':'/claims/0/statement',
                'offset':0, 'max_characters':2}, 'legacy')]
        model = ScriptedNativeChat(marker='synthetic', replies=[proposal])
        async with Client(_build_server(case_artifacts=a)) as client:
            agent = build_case_reviewer(role='counter', model=model, artifacts=a, tools=await case_mcp_tools(client),
                require_inspection=True, max_model_calls=1)
            result = await agent.ainvoke({'messages':[HumanMessage(content='Offline navigation only.')]})
        receipts = {m.tool_call_id:m for m in result['messages'] if isinstance(m, ToolMessage)}
        assert receipts['quote'].artifact['text'] == 'selected exact'
        assert receipts['conflict'].status == 'error'
        assert receipts['legacy'].artifact == read_location(a,'P01','/claims/0/statement',0,2)
        assert not result.get('recorded_findings') and not result.get('review')
    asyncio.run(run())
