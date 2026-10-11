"""Focused review and local recovery; no synthetic financial acceptance."""
import asyncio
from copy import deepcopy
import json
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from mcp import Client
from sec_agent.agent_runtime.case_review_agent import CaseReview, ReviewHandoff, validate_case_review, build_case_reviewer, case_mcp_tools
from sec_agent.agent_runtime.review_inspection import read_location
from sec_agent.agent_runtime.review_context import working_messages
from test_case_review_agent import review_fixture, ScriptedNativeChat, call
from test_research_convergence import artifact_fixture
from test_review_inspection_recovery import reads
from test_research_mcp import _build_server


def test_resume_keeps_current_instruction_and_does_not_serialize_host_stop_as_model_answer():
    a=artifact_fixture()
    rows=[HumanMessage(content=json.dumps({'question':'Original question'})),
        HumanMessage(content='review_handoff_contract_v2: first migration'),
        AIMessage(content='Model call limits exceeded: run limit (24/24)'),
        HumanMessage(id='resume',content='review_handoff_contract_v2: continue the pending task')]
    projected=working_messages({'messages':rows},a)
    assert projected[-1]==rows[-1]
    assert not any(isinstance(m,AIMessage) for m in projected)
    assert len(rows)==4  # Original host receipt remains archived.


def test_parent_resumes_latest_confirmation_then_passes_revisions_to_lead():
    from langgraph.checkpoint.memory import InMemorySaver
    from langchain_core.runnables import RunnableLambda
    from sec_agent.agent_runtime.research_session import build_research_session_graph
    from sec_agent.agent_runtime.case_review_agent import case_review_scope_digest
    from sec_agent.agent_runtime.workpaper_changes import paper_versions
    from test_research_session import _phases
    async def exercise():
        a=artifact_fixture(); revision={'P01':{'status':'revision_submitted','workpaper':deepcopy(a.read_paper('P01')),'finding_responses':[]}}
        revision['P01']['workpaper']['thesis']+=' Current accepted author revision.'
        current=a.with_revisions(revision); question='Same synthetic question'
        context={'paper_version_digests':paper_versions(current),'findings_to_confirm':{'P01':[]}}
        latest={'phase':'case_review_incomplete','scope_digest':case_review_scope_digest(current,question),'marker':'LATEST'}
        history=[{'actor':'independent_workpaper_confirmation','output':{'context':context,'review':latest}}]
        state={'question':question,'case_papers':list(a._author_states.values()),'revisions':revision,
            'phase':'research_needs_attention','research_stop_reason':'independent_confirmation_incomplete',
            'case_review':{'marker':'OLD'},'convergence_history':history,'research_handoff':{},
            'continue_remaining_research':True,'review_repair_decision':{'action':'repair'}}
        phases,_,_=_phases();seen=[]
        async def review(s,config):
            seen.append('review');assert s['previous_review']['marker']=='LATEST'
            assert s['revisions']==revision and s['review_confirmation']==context
            return {'phase':'case_review_ready_for_convergence',**{r:{'status':'review_submitted','review':review_fixture(current)} for r in ('counter','verifier')}}
        async def converge(s,config):
            seen.append('lead');assert s['revisions']==revision and not s['review_repair_decision']
            return {'phase':'research_convergence_needs_attention','stop_reason':'synthetic_end','revisions':revision,'artifact_history':[]}
        phases.update(review=RunnableLambda(review),converge=RunnableLambda(converge))
        graph=build_research_session_graph(**phases).compile(checkpointer=InMemorySaver())
        config={'configurable':{'thread_id':'resume-focused'},'recursion_limit':60}
        await graph.aupdate_state(config,state,as_node='research_attention')
        result=await graph.ainvoke(None,config)
        assert seen==['review','lead'] and result['revisions']==revision
        assert result['convergence_history']==history
    asyncio.run(exercise())


def finding(identity, quote):
    return dict(finding_id=identity, paper_id='P01', severity='advisory', problematic_quote=quote,
        diagnosis='Synthetic local wording finding, not a financial judgment.', requested_change='Clarify this exact current wording only.')


def test_lead_receives_findings_without_legacy_paragraph_forms():
    from sec_agent.agent_runtime.review_recovery import public_review, public_confirmation
    saved={'summary':'Current findings','findings':[{'finding_id':'F'}],'inspection_checks':[{'result':'OLD_FORM'}]}
    projected=public_review(saved)
    assert projected=={'summary':'Current findings','findings':[{'finding_id':'F'}]}
    assert saved['inspection_checks']
    assert 'OLD_FORM' not in json.dumps(public_confirmation({'review':{'counter':{'review':saved}}}))


def test_repeated_resume_preserves_current_work_and_deduplicates_identical_reads():
    a=artifact_fixture(); messages=[HumanMessage(content='review_handoff_contract_v2')]
    for i in range(5):
        messages.extend([AIMessage(content='Current public judgment '+str(i),tool_calls=[call('read_review_location',{'paper_id':'P01','field_path':'/thesis'},str(i))]),
            ToolMessage(name='read_review_location',tool_call_id=str(i),content='IDENTICAL_SOURCE')])
    messages.append(HumanMessage(content='review_handoff_contract_v2: resume same unfinished review'))
    view=working_messages({'messages':messages},a)
    assert sum(isinstance(m,AIMessage) for m in view)==5
    assert sum(m.content=='IDENTICAL_SOURCE' for m in view)==1
    assert 'duplicate_of_tool_call_id' in view[2].content
    assert sum(m.content=='IDENTICAL_SOURCE' for m in messages)==5


def test_location_identity_binds_current_read_quote_and_rejects_stale_or_unread():
    a=artifact_fixture(); location=read_location(a,'P01','/thesis')
    row=finding('F','');row['location_id']=location['location_id']
    review=CaseReview.model_validate({**review_fixture(a),'findings':[row]})
    journal=[*reads(a),ToolMessage(name='read_review_location',tool_call_id='loc',content=json.dumps(location),artifact=location)]
    validate_case_review(review,a,journal)
    assert review.findings[0].problematic_quote==location['text']
    with pytest.raises(ValueError,match='location'):
        validate_case_review(CaseReview.model_validate({**review_fixture(a),'findings':[row]}),a,reads(a))
    stale=deepcopy(journal);stale[-1].artifact['paper_digest']='stale'
    with pytest.raises(ValueError,match='location'):
        validate_case_review(CaseReview.model_validate({**review_fixture(a),'findings':[row]}),a,stale)


def test_handoff_has_no_paragraph_form_and_still_requires_honest_completion():
    schema=ReviewHandoff.model_json_schema()
    assert 'inspection_checks' not in schema['properties']
    assert 'completion' in schema['required']
    with pytest.raises(ValueError,match='completion_must_match'):
        ReviewHandoff.model_validate({**review_fixture(artifact_fixture()),'completion':'complete','unresolved_data_requests':['Critical original not read']})


def test_contract_transition_preserves_task_and_user_correction_without_old_queue():
    a=artifact_fixture()
    state={'messages':[HumanMessage(content=json.dumps({'question':'The original question','inspection_manifest':'OLD_QUEUE'})),
        HumanMessage(content='Authors revised the current candidate. Historical paper text OLD_QUEUE'),
        HumanMessage(content='Continue this same review using saved reads, findings and version-bound checks. OLD_QUEUE'),
        HumanMessage(content=json.dumps({'notice':'Current review working state, not financial evidence.','inspection_progress':'OLD_QUEUE'})),
        HumanMessage(content='Preserve the agreed research cutoff.'),
        *reads(a),HumanMessage(content='review_handoff_contract_v2') ]}
    view=working_messages(state,a)
    text=' '.join(str(m.content) for m in view)
    assert 'The original question' in text and 'Preserve the agreed research cutoff.' in text
    assert 'OLD_QUEUE' not in text and 'missing_semantic_target_ids' not in text
    assert json.loads(view[-1].content)['current_full_paper_reads']==['P01','P02']
    assert len(state['messages'])==8


def test_invalid_finding_does_not_discard_valid_sibling_or_accept_review():
    async def exercise():
        a=artifact_fixture(); good=finding('good',a.read_paper('P01')['thesis']); bad=finding('bad','NOT_IN_PAPER')
        submitted={**review_fixture(a),'completion':'complete','findings':[good,bad]}
        model=ScriptedNativeChat(marker='partial',replies=[
            [call('read_research_artifact',{'paper_id':p['paper_id']},p['paper_id']) for p in a.catalog()['papers']],
            [call('submit_case_review',{'review':submitted},'invalid')],
            [call('submit_case_review',{'review':{**review_fixture(a),'completion':'complete'}},'fixed')]])
        async with Client(_build_server(case_artifacts=a)) as client:
            graph=build_case_reviewer(role='verifier',model=model,tools=await case_mcp_tools(client),artifacts=a,require_inspection=True,max_model_calls=3)
            result=await graph.ainvoke({'messages':[HumanMessage(content='Check the synthetic papers.')]})
        assert list(result['recorded_findings'])==['good']
        assert [f['finding_id'] for f in result['review']['findings']]==['good']
        error=next(m for m in result['messages'] if isinstance(m,ToolMessage) and m.tool_call_id=='invalid')
        assert error.status=='error' and 'Saved valid findings: good' in error.content
    asyncio.run(exercise())
