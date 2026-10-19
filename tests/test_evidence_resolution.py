"""Deterministic source navigation/compatibility; no financial gold verdict."""
from copy import deepcopy
import asyncio
import json
import pytest
from langchain_core.messages import HumanMessage, ToolMessage
from sec_agent.agent_runtime.evidence_resolution import (
    resolve_quote, citation_inventory, confirmed_reference, delivery_reference_findings, read_source_span,
    review_reference_state)
from sec_agent.agent_runtime.evidence_resolution import (
    bind_source_quote, SourceQuoteSelectionRequired, quote_selection_feedback)
from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256
from sec_agent.agent_runtime.case_review_agent import (
    CaseReview, validate_case_review, validate_inspection_checks, build_case_reviewer, case_mcp_tools)
from sec_agent.agent_runtime.review_inspection import inspection_manifest
from test_research_convergence import artifact_fixture
from test_review_inspection_recovery import inspected, reads
from test_case_review_agent import review_fixture, ScriptedNativeChat, call
from test_research_mcp import _build_server
from mcp import Client


def sample():
    a=artifact_fixture()
    a._sources['P01:S002']={'result_state':'source_bound_passage','passage_id':'PASSAGE::CHUNK::docA:2:3::hashA',
        'document_id':'docA','node_id':'CHUNK::docA:2:3','content_sha256':'hashA',
        'passage':'Income |  | 10 |  | 20 |\nTax |  | (2) |  | (4) |\n'}
    a._papers['P01']['workpaper']['narrative_markdown']='Growth contribution requires checking. PASSAGE::...2:3'
    return a


def test_unique_quote_located_without_model_offsets_and_without_rewriting_text():
    body = 'Before\nRevenue 10\nAfter'
    quote, span, record = bind_source_quote(body, 'P01:S001', 'Revenue 10')
    assert quote == 'Revenue 10' and body[span['start']:span['end']] == quote
    assert record['original_input']['quote_span'] is None
    assert record['basis']['source_digest'] == canonical_sha256(body)
    assert not record['financial_semantics_verified']


def test_conflict_returns_both_choices_without_selecting_or_mutating_input():
    body = 'Revenue 10\nOther context'
    span = {'source_digest':canonical_sha256(body), 'start':3, 'end':len(body)}
    before = deepcopy(span)
    with pytest.raises(SourceQuoteSelectionRequired) as caught:
        bind_source_quote(body, 'P01:S001', 'Revenue 10', span)
    feedback = caught.value.feedback
    assert span == before and feedback['selected_match'] is None and not feedback['accepted']
    assert feedback['supplied_span_preview'] == body[3:]
    assert feedback['quote_candidates'][0]['quote_span']['start'] == 0
    assert feedback['original_input']['quote'] == 'Revenue 10'
    # A caller's explicit choice, not the host, resolves the conflict.
    assert bind_source_quote(body, 'P01:S001', 'Revenue 10')[0] == 'Revenue 10'
    assert bind_source_quote(body, 'P01:S001', '', span)[0] == body[3:]


def test_repeated_quote_requires_occurrence_selection_even_if_text_is_exact():
    body = 'Revenue 10\nRevenue 10'
    with pytest.raises(SourceQuoteSelectionRequired) as caught:
        bind_source_quote(body, 'P01:S001', 'Revenue 10')
    f = caught.value.feedback
    assert f['total_matches'] == 2 and f['selected_match'] is None
    selected = f['quote_candidates'][1]['quote_span']
    assert bind_source_quote(body, 'P01:S001', 'Revenue 10', selected)[1] == selected
    selected['source_digest'] = 'stale'
    with pytest.raises(ValueError, match='stale_digest'):
        bind_source_quote(body, 'P01:S001', 'Revenue 10', selected)


def test_selection_feedback_never_masks_a_sibling_tool_error():
    normal = {'errors':['source_quote_selection_required:F:source_checks/0']}
    assert quote_selection_feedback(ValueError(json.dumps(normal)))['accepted'] is False
    for other in ('unknown_source_id:F:P99', 'source_span_stale_digest', 'read_missing_papers_before_review'):
        assert quote_selection_feedback(ValueError(json.dumps({'errors':[*normal['errors'],other]}))) is None


def test_table_compatibility_restores_only_unique_identical_nonempty_cells():
    body='Income |  | 10 |  | 20 |\nTax |  | (2) |  | (4) |\n'
    request='Income | 10 | 20 |\nTax | (2) | (4) |'
    exact, record=resolve_quote(body,request)
    assert exact==body.rstrip() and record['origin']=='runtime_compatibility_parse'
    assert record['original_input']==request and record['normalized_result']==exact
    assert not record['financial_semantics_verified']
    for wrong in (request.replace('(4)','4'),request.replace('20','21'),request.replace('Tax','Revenue')):
        assert resolve_quote(body,wrong)==(wrong,None)
    assert resolve_quote(body+body,request)==(request,None)


def test_candidate_confirmation_requires_read_and_never_repairs_draft_silently():
    a=sample(); row=citation_inventory(a,'P01')[0]
    assert row['status']=='candidate_requires_confirmation'
    assert row['candidates'][0]['source_id']=='P01:S002'
    assert row['runtime_parsing']['normalized_result'] is None
    with pytest.raises(ValueError,match='requires_actual_current_source_read'):
        confirmed_reference(a,'P01',row['reference_id'],'P01:S002','Actual source identity and content checked.',[])
    messages=[ToolMessage(name='read_research_source',tool_call_id='read',content='source',artifact=a.read_source('P01:S002'))]
    confirmed=confirmed_reference(a,'P01',row['reference_id'],'P01:S002','Actual source identity and content checked.',messages)
    assert confirmed['delivery_reference_needs_repair'] and confirmed['read_tool_call_ids']==['read']
    messages.append(ToolMessage(name='confirm_review_reference',tool_call_id='confirm',content='confirmed',artifact=confirmed))
    findings,records=delivery_reference_findings(a,messages,complete=True)
    assert len(findings)==1 and records[0]['origin']=='runtime_compatibility_parse'
    assert findings[0]['finding_type'] == 'traceability'
    assert 'PASSAGE::...2:3' in a.read_paper('P01')['narrative_markdown']
    a._papers['P01']['workpaper']['narrative_markdown']+=' Revision.'
    with pytest.raises(ValueError,match='unconfirmed_references'):
        delivery_reference_findings(a,messages,complete=True)


def test_same_suffix_in_distinct_documents_is_ambiguous_and_cannot_autoconfirm():
    a=sample();a._sources['P01:S003']=dict(a._sources['P01:S002'],passage_id='PASSAGE::CHUNK::docB:2:3::hashB',
        document_id='docB',node_id='CHUNK::docB:2:3',content_sha256='hashB')
    a._papers['P01']['sources']['P01:S003']={}
    row=citation_inventory(a,'P01')[0]
    assert row['status']=='ambiguous' and len(row['candidates'])==2
    with pytest.raises(ValueError,match='unconfirmed_references'):
        delivery_reference_findings(a,[],complete=True)
    a._papers['P01']['workpaper']['narrative_markdown']='PASSAGE::CHUNK::docA:2:3::hashA'
    assert citation_inventory(a,'P01')[0]['status']=='exact'


def test_complete_cross_paper_alias_matches_authorized_owner_without_confirmation():
    a=sample()
    source=deepcopy(a._sources['P01:S002'])
    a._sources['P02:S025']=source
    a._papers['P02']['sources']['P02:S025']={}
    a._papers['P01']['workpaper']['narrative_markdown']='Existing source P02:S025.'
    original=deepcopy(a._papers)
    row=citation_inventory(a,'P01')[0]
    assert row['status']=='exact' and row['candidates'][0]['source_id']=='P02:S025'
    assert a.source_item('P02:S025')==source
    assert not row['runtime_parsing']['financial_semantics_verified']
    assert delivery_reference_findings(a,[],complete=True)==([],[])
    assert a._papers==original
    # A prefix is never an instruction to look outside this case, and fuzzy
    # matching cannot silently select another paper's similarly named source.
    for ref in ['P02:S999','P99:S025','P02:S0…25']:
        a._papers['P01']['workpaper']['narrative_markdown']=ref
        assert citation_inventory(a,'P01')[0]['status']=='unresolved'
        with pytest.raises(ValueError,match='unconfirmed_references'):
            delivery_reference_findings(a,[],complete=True)


def test_pending_reference_state_is_current_bounded_and_does_not_confirm():
    a=sample(); original=deepcopy(a._papers)
    pending=review_reference_state(a,[])
    row=pending['items'][0]
    assert row['reference_id']==citation_inventory(a,'P01')[0]['reference_id']
    assert row['candidate_source_ids']==['P01:S002']
    assert pending['pending_count']==1 and a._papers==original
    assert review_reference_state(a,[],limit=0)['remaining_count']==1
    messages=[ToolMessage(name='read_research_source',tool_call_id='read',content='source',artifact=a.read_source('P01:S002'))]
    assert review_reference_state(a,messages)['pending_count']==1  # Reading alone is not confirmation.
    confirmed=confirmed_reference(a,'P01',row['reference_id'],'P01:S002','Identity checked against the actual source.',messages)
    messages.append(ToolMessage(name='confirm_review_reference',tool_call_id='confirm',content='confirmed',artifact=confirmed))
    assert review_reference_state(a,messages)['pending_count']==0
    a._papers['P01']['workpaper']['narrative_markdown']+=' New version.'
    assert review_reference_state(a,messages)['pending_count']==1


def test_reference_state_is_in_request_before_submission_without_changing_history():
    from langchain.agents.middleware.types import ModelRequest
    from sec_agent.agent_runtime.case_review_agent import ReviewReferenceState
    a=sample(); messages=[HumanMessage(content='Review supplied papers.')]
    model=ScriptedNativeChat(marker='synthetic',replies=[])
    request=ModelRequest(model=model,messages=messages,state={'messages':messages},tools=[])
    projected=ReviewReferenceState(a).project(request)
    pending=json.loads(projected.messages[-1].content)
    assert pending['items'][0]['reference_id']==citation_inventory(a,'P01')[0]['reference_id']
    assert request.messages==messages and len(messages)==1
    assert 'model_confirmed' not in projected.messages[-1].content


@pytest.mark.parametrize('audited',[False,True])
def test_native_request_exposes_pending_reference_before_first_model_action(audited):
    class Capture(ScriptedNativeChat):
        seen: list=[]
        def _generate(self,messages,stop=None,run_manager=None,**kwargs):
            self.seen.append(list(messages))
            return super()._generate(messages,stop=stop,run_manager=run_manager,**kwargs)
    async def run():
        a=sample(); audit=None
        if audited:
            from sec_agent.agent_runtime.case_review_agent import CaseModelAudit
            from sec_agent.agent_runtime.research_session_runtime import load_research_runtime_profile
            from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekModelProfile, TokenBudgetBasis
            profile,_=load_research_runtime_profile('.')
            node=profile['nodes']['counter']
            audit=CaseModelAudit(actor='counter',profile=DeepSeekModelProfile.model_validate(node['profile']),
                basis=TokenBudgetBasis.model_validate_json(json.dumps(node['budget'])),
                public_sink=lambda e:None,private_sink=lambda e:None)
        model=Capture(marker='synthetic',replies=[[call('read_review_references',{'paper_id':'P01'},'refs')]])
        async with Client(_build_server(case_artifacts=a)) as client:
            agent=build_case_reviewer(role='counter',model=model,tools=await case_mcp_tools(client),
                artifacts=a,require_inspection=True,audit=audit,max_model_calls=1)
            result=await agent.ainvoke({'messages':[HumanMessage(content='Inspect provided research.')]})
        assert len(model.seen)==1
        blocks=[m.content for m in model.seen[0] if isinstance(m,HumanMessage) and 'runtime_reference_state' in m.content]
        assert len(blocks)==1
        assert citation_inventory(a,'P01')[0]['reference_id'] in blocks[0]
        assert not any('runtime_reference_state' in m.content for m in result['messages'] if isinstance(m,HumanMessage))
    asyncio.run(run())


def test_digest_bound_quote_selection_and_compatibility_receipts():
    a=sample();body=a._sources['P01:S002']['passage']; selected=read_source_span(a,'P01:S002',0,len(body)-1)
    review=CaseReview.model_validate(review_fixture(a))
    finding={'finding_id':'F','paper_id':'P01','severity':'advisory','problematic_quote':'Growth contribution',
        'diagnosis':'Synthetic source operation test only.','requested_change':'Inspect the actual selected source span.',
        'source_checks':[{'source_id':'P01:S002','quote_span':selected['window_span']}]}
    review=review.model_copy(update={'findings':CaseReview.model_validate({**review.model_dump(),'findings':[finding]}).findings})
    receipts=[];validate_case_review(review,a,reads(a),parsing_records=receipts)
    assert review.findings[0].source_checks[0].quote==body.rstrip()
    assert receipts[0]['source_check_index']==0 and receipts[0]['origin']=='runtime_compatibility_parse'
    review.findings[0].source_checks[0].quote_span.source_digest='stale'
    with pytest.raises(ValueError,match='stale_digest'):
        validate_case_review(review,a,reads(a))


def test_literal_anchor_selection_returns_contexts_without_selecting_ambiguous_match():
    a=sample()
    selected=read_source_span(a,'P01:S002',anchor='Tax',max_characters=100)
    assert selected['text']=='Tax |  | (2) |  | (4) |\n'
    assert selected['window_span']['start']==len('Income |  | 10 |  | 20 |\n')
    assert selected['runtime_parsing']['method']=='exact_source_anchor_v1'
    body=a._sources['P01:S002']['passage']
    result=read_source_span(a,'P01:S002',anchor='|')
    assert result['status']=='multiple_anchor_matches' and result['selected_match'] is None
    assert 'text' not in result and 'quote_span' not in result
    assert len(result['candidates'])==6 and result['next_page']
    for item in result['candidates']:
        span=item['window_span']
        assert item['text']==body[span['start']:span['end']]
        assert body[item['match_start']:item['match_end']]=='|'
        assert read_source_span(a,**item['readback']['arguments'])['text']
    next_page=read_source_span(a,**result['next_page']['arguments'])
    assert next_page['candidates'][0]['match_index']==6
    assert next_page['selected_match'] is None


def test_anchor_navigation_is_bounded_and_missing_anchor_is_not_missing_source():
    a=sample();a._sources['P01:S002']['passage']=('before Tax after '*1000)
    result=read_source_span(a,'P01:S002',anchor='Tax',max_characters=6000)
    assert result['total_matches']==1000
    assert sum(len(c['text']) for c in result['candidates'])<=6000
    absent=read_source_span(a,'P01:S002',anchor='Absent')
    assert absent['status']=='anchor_not_found' and absent['candidates']==[]
    assert absent['selected_match'] is None and absent['readback']
    for kwargs in ({'anchor':'Tax','start':1},{'match_offset':1},{'anchor':'Tax','match_offset':-1},
                   {'anchor':'Tax','match_offset':1000}):
        with pytest.raises(ValueError):read_source_span(a,'P01:S002',**kwargs)


def test_overall_equation_cannot_cover_other_paragraphs_or_ambiguous_wording():
    a=artifact_fixture();good=CaseReview.model_validate(inspected(a))
    validate_inspection_checks(good,a,reads(a),complete=True)
    checks=[c for c in good.inspection_checks if c.dimension=='prose_consistency']
    good.inspection_checks.remove(checks[-1])
    # Legacy record completeness is not a submission gate. An explicit
    # contradictory check is still invalid independently of record count.
    validate_inspection_checks(good,a,reads(a),complete=True)
    good=CaseReview.model_validate(inspected(a));check=next(c for c in good.inspection_checks if c.dimension=='prose_consistency')
    check.financial_verdict='contradicted'
    with pytest.raises(ValueError,match='semantic_verdict_status_mismatch'):
        validate_inspection_checks(good,a,reads(a),complete=True)


def test_native_record_tool_persists_runtime_origin_separately_from_raw_model_call():
    async def run():
        a=sample()
        finding={'finding_id':'F','paper_id':'P01','severity':'advisory','problematic_quote':'Growth contribution',
            'diagnosis':'Synthetic compatibility operation only.','requested_change':'Inspect original table headings and periods.',
            'source_checks':[{'source_id':'P01:S002','quote':'Income | 10 | 20 |'}]}
        model=ScriptedNativeChat(marker='synthetic',replies=[
            [call('read_research_artifact',{'paper_id':'P01','section':'workpaper'},'read')],
            [call('record_case_finding',{'finding':finding},'record')]])
        async with Client(_build_server(case_artifacts=a)) as client:
            agent=build_case_reviewer(role='counter',model=model,tools=await case_mcp_tools(client),artifacts=a,max_model_calls=2)
            result=await agent.ainvoke({'messages':[HumanMessage(content='Synthetic proof, not a financial verdict.')]})
        actual=result['recorded_findings']['F']['source_checks'][0]['quote']
        assert actual=='Income |  | 10 |  | 20 |'
        saved=next(m for m in result['messages'] if isinstance(m,ToolMessage) and m.name=='record_case_finding')
        assert saved.artifact['runtime_parsing'][0]['origin']=='runtime_compatibility_parse'
        assert finding['source_checks'][0]['quote']=='Income | 10 | 20 |'
    asyncio.run(run())


def test_concise_semantic_result_keeps_evidence_and_relationship_checks():
    a=artifact_fixture();payload=inspected(a)
    for check in payload['inspection_checks']:
        check['result']='一致'
    review=CaseReview.model_validate(payload)
    validate_inspection_checks(review,a,reads(a),complete=True)
    payload['inspection_checks'][0]['result']='  '
    with pytest.raises(ValueError,match='must_not_be_blank'):
        CaseReview.model_validate(payload)
    prose=next(c for c in review.inspection_checks if c.dimension=='prose_consistency')
    prose.supported_relationship=''
    with pytest.raises(ValueError,match='semantic_relationship_comparison_required'):
        validate_inspection_checks(review,a,reads(a),complete=True)


def test_native_schema_feedback_keeps_paths_without_echoing_full_model_arguments():
    async def run():
        a=sample()
        finding={'finding_id':'F','paper_id':'P01','severity':'invalid-severity',
            'problematic_quote':'Growth contribution','diagnosis':'UNIQUE_RAW_PAYLOAD_'+('x'*20000),
            'requested_change':'Inspect original source only.'}
        model=ScriptedNativeChat(marker='synthetic',replies=[
            [call('read_research_artifact',{'paper_id':'P01','section':'workpaper'},'read')],
            [call('record_case_finding',{'finding':finding},'bad')]])
        async with Client(_build_server(case_artifacts=a)) as client:
            agent=build_case_reviewer(role='counter',model=model,tools=await case_mcp_tools(client),artifacts=a,max_model_calls=2)
            result=await agent.ainvoke({'messages':[HumanMessage(content='Synthetic schema failure only.')]})
        feedback=next(m for m in result['messages'] if isinstance(m,ToolMessage) and m.tool_call_id=='bad')
        assert feedback.status=='error' and len(feedback.content)<2000
        assert 'finding.severity' in feedback.content and 'finding.diagnosis' in feedback.content
        assert 'UNIQUE_RAW_PAYLOAD_' not in feedback.content
        assert feedback.artifact['runtime_parsing'][0]['origin']=='runtime_compatibility_parse'
        assert not result.get('recorded_findings') and not result.get('review')
        original=next(m for m in result['messages'] if getattr(m,'tool_calls',[]) and m.tool_calls[0]['id']=='bad')
        assert original.tool_calls[0]['args']['finding']==finding
    asyncio.run(run())
