"""Lossless reviewer projection and explicit completion, not financial verdicts."""
from copy import deepcopy
import json

import pytest
from langchain_core.messages import ToolMessage
from pydantic import ValidationError

from sec_agent.agent_runtime.review_context import paper_quote_view, confirmation_navigation, handoff_page
from sec_agent.agent_runtime.case_review_agent import ReviewHandoff


def test_legacy_read_window_projection_does_not_modify_receipt_or_text():
    from sec_agent.agent_runtime.review_context import source_window_view
    value={'status':'multiple_anchor_matches','source_id':'P08:S011','candidates':[
        {'match_start':183,'match_end':197,'text':'the exact original window',
         'quote_span':{'source_digest':'original','start':63,'end':663}}]}
    original=ToolMessage(content=json.dumps(value),artifact=deepcopy(value),
        name='read_review_source_span',tool_call_id='read1')
    before=original.model_dump()
    view=source_window_view(original); decoded=json.loads(view.content)
    assert 'quote_span' not in decoded['candidates'][0]
    assert decoded['candidates'][0]['window_span']==value['candidates'][0]['quote_span']
    assert decoded['candidates'][0]['text']==value['candidates'][0]['text']
    assert original.model_dump()==before and view.artifact==original.artifact
    assert source_window_view(view)==view


def expand_quotes(value):
    result = deepcopy(value)
    table = result.pop('citation_quote_table', None)
    if table is None:
        return result
    result.pop('quote_view_notice')
    claims = result['content']['claims'] if result['section'] == 'workpaper' else result['content']
    for claim in claims:
        if 'citation_quote_refs' not in claim:
            continue
        refs = claim.pop('citation_quote_refs')
        claim['citation_quotes'] = {}
        for source, ids in refs.items():
            scalar = isinstance(ids, str)
            if scalar:ids = [ids]
            assert all(table[i]['source_id'] == source for i in ids)
            claim['citation_quotes'][source] = [table[i]['quote'] for i in ids]
            if scalar:claim['citation_quotes'][source] = claim['citation_quotes'][source][0]
    return result


def test_repeated_quotes_keep_exact_source_bindings_prose_and_native_receipt():
    quote = 'Literal with period, unit and restrictions. ' * 45
    content = {'paper_id':'P01', 'section':'workpaper', 'content':{
        'narrative_markdown':'Full current prose', 'task_note':{'status':'author claims done'},
        'claims':[{'claim_id':str(i), 'statement':str(i), 'source_ids':['S1','S2'],
                   'citation_quotes':{'S1':[quote, quote], 'S2':quote}} for i in range(6)]}}
    m = ToolMessage(name='read_research_artifact', tool_call_id='read',
        content=json.dumps(content), artifact=deepcopy(content))
    original = m.model_dump()
    projected = paper_quote_view(m)
    assert len(projected.content) < len(m.content)/2
    assert expand_quotes(json.loads(projected.content)) == content
    assert len(json.loads(projected.content)['citation_quote_table']) == 2
    assert projected.artifact == content and projected.tool_call_id == 'read'
    assert m.model_dump() == original
    assert paper_quote_view(projected).content == projected.content
    error = m.model_copy(update={'status':'error'})
    assert paper_quote_view(error) is error


def test_diff_coordinates_are_paginated_without_changing_confirmation():
    class Artifacts:
        _papers = {'P01':{}}
        def catalog(self):return {'papers':[{'paper_id':'P01'}]}
    confirmation = {'changes':{'P01':{'current_digest':'current', 'changed_claim_ids':['C1'],
        'locations':[{'path':'/thesis', 'spans':[{'before':[i,i+1],'after':[i,i+2]} for i in range(500)]}]}},
        'findings_to_confirm':{'P01':[{'id':'F1','request':'Review this'}]}}
    original = deepcopy(confirmation)
    nav = confirmation_navigation(confirmation)
    assert nav['findings_to_confirm'] == confirmation['findings_to_confirm']
    assert nav['changes']['P01']['locations'][0] == {'path':'/thesis','span_count':500}
    args=nav['changes']['P01']['exact_changes_read']['arguments']
    text=''
    while True:
        page=handoff_page(Artifacts(), confirmation, **args)
        text+=page['text']
        if page['next_offset'] is None:break
        args['offset']=page['next_offset']
    assert json.loads(text)['changes'] == original['changes']['P01']
    assert confirmation == original


def test_active_schema_explains_required_classification_without_doing_it():
    properties=ReviewHandoff.model_json_schema()['properties']
    for key in ('completion','unresolved_data_requests','research_limitations'):
        assert len(properties[key]['description']) > 80
    proposal={'completion':'complete','summary':'Sufficient length synthetic review summary.',
        'assessments':[{'paper_id':'P01','assessment':'Synthetic assessment only.'}],
        'unresolved_data_requests':['Author supplied ambiguous outstanding work.']}
    original=deepcopy(proposal)
    with pytest.raises(ValidationError, match='completion_must_match'):
        ReviewHandoff.model_validate(proposal)
    assert proposal == original
    assert ReviewHandoff.model_validate({**proposal,'completion':'incomplete'}).unresolved_data_requests
    limits={**proposal,'unresolved_data_requests':[], 'research_limitations':['Known scope limit.']}
    assert ReviewHandoff.model_validate(limits).completion == 'complete'


def test_native_tool_schema_and_handoff_read_are_available_before_submission():
    import asyncio
    from langchain_core.messages import HumanMessage
    from langchain_core.utils.function_calling import convert_to_openai_tool
    from mcp import Client
    from sec_agent.agent_runtime.case_review_agent import build_case_reviewer, case_mcp_tools
    from test_case_review_agent import ScriptedNativeChat, call, review_fixture
    from test_research_convergence import artifact_fixture
    from test_research_mcp import _build_server

    async def exercise():
        artifacts = artifact_fixture()
        class Probe(ScriptedNativeChat):
            def bind_tools(self, tools, **kwargs):
                submit = next(t for t in tools if t.name=='submit_case_review')
                fields = convert_to_openai_tool(submit)['function']['parameters']['properties']['review']['properties']
                assert 'incomplete' in fields['completion']['description']
                assert 'current claims' in fields['research_limitations']['description']
                return super().bind_tools(tools, **kwargs)
        replies = [[call('read_review_handoff',{'section':'revision_confirmation','paper_id':'P01'},'handoff'),
            call('read_review_handoff',{'section':'revision_confirmation','paper_id':'missing'},'bad-handoff')],
            [call('read_research_artifact',{'paper_id':p['paper_id']},p['paper_id']) for p in artifacts.catalog()['papers']],
            [call('submit_case_review',{'review':{**review_fixture(artifacts),'completion':'complete'}},'submit')]]
        async with Client(_build_server(case_artifacts=artifacts)) as client:
            agent=build_case_reviewer(role='counter',model=Probe(marker='test',replies=replies),
                tools=await case_mcp_tools(client),artifacts=artifacts,require_inspection=True,
                max_model_calls=3, confirmation=None)
            # The empty handoff is a valid exact read; it must not invent context.
            result=await agent.ainvoke({'messages':[HumanMessage(content='Synthetic review only.')]})
        receipt=next(m for m in result['messages'] if isinstance(m,ToolMessage) and m.tool_call_id=='handoff')
        assert receipt.status=='success' and json.loads(receipt.content)['text']=='null'
        error=next(m for m in result['messages'] if isinstance(m,ToolMessage) and m.tool_call_id=='bad-handoff')
        assert error.status=='error' and 'unknown_paper_id' in error.content
        assert result['review']['completion']=='complete'
    asyncio.run(exercise())
