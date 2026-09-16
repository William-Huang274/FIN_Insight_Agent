"""Native review/Lead recovery contracts, not synthetic financial acceptance."""
import asyncio
from copy import deepcopy
import json

import pytest
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.memory import InMemorySaver
from mcp import Client

from sec_agent.agent_runtime.case_review_agent import (
    CaseReview, CaseReviewFinding, build_case_reviewer, case_mcp_tools,
    validate_case_review, validate_inspection_checks, case_review_scope_digest,
)
from sec_agent.agent_runtime.review_inspection import inspection_manifest, quote_recovery, read_location
from sec_agent.agent_runtime.review_recovery import review_recovery_handoff
from sec_agent.agent_runtime.lead_issue_decision import LeadIssueDecision, decision_errors
from sec_agent.agent_runtime.research_session import build_research_session_graph, current_task_artifacts
from test_case_review_agent import ScriptedNativeChat, call, review_fixture
from test_research_convergence import artifact_fixture
from test_research_mcp import _build_server
from test_research_session import _phases


def reads(artifacts):
    return [ToolMessage(name='read_research_artifact', content='Full native paper read', tool_call_id=p['paper_id'],
        artifact={'paper_id':p['paper_id'], 'section':'workpaper', 'content':artifacts.read_paper(p['paper_id'])})
        for p in artifacts.catalog()['papers']]


def inspected(artifacts):
    review = review_fixture(artifacts)
    review['completion'] = 'complete'
    review['inspection_checks'] = []
    for pid, manifest in inspection_manifest(artifacts).items():
        for dimension in manifest['required_dimensions']:
            review['inspection_checks'].append({'paper_id':pid,'paper_digest':manifest['paper_digest'],
                'dimension':dimension,'claim_ids':manifest['material_claim_ids'] if dimension=='claim_support' else [],
                'field_path':'/narrative_markdown','target_quote':artifacts.read_paper(pid)['narrative_markdown'],
                'status':'checked','result':'Synthetic contract inspection only; not a verified economic conclusion.',
                'source_checks':[{'source_id':pid+':S002','quote':'29800'}]})
    return review


def test_full_read_does_not_allow_uncovered_or_stale_clean_inspection():
    artifacts = artifact_fixture()
    with pytest.raises(ValueError, match='inspection_incomplete'):
        validate_inspection_checks(CaseReview.model_validate(review_fixture(artifacts)), artifacts, reads(artifacts), complete=True)
    good = inspected(artifacts)
    validate_inspection_checks(CaseReview.model_validate(good), artifacts, reads(artifacts), complete=True)
    bad = deepcopy(good)
    bad['inspection_checks'][0]['paper_digest'] = 'superseded'
    with pytest.raises(ValueError, match='stale_paper'):
        validate_inspection_checks(CaseReview.model_validate(bad), artifacts, reads(artifacts), complete=True)
    bad = deepcopy(good)
    bad['inspection_checks'][0]['claim_ids'] = []
    with pytest.raises(ValueError, match='inspection_incomplete'):
        validate_inspection_checks(CaseReview.model_validate(bad), artifacts, reads(artifacts), complete=True)


@pytest.mark.parametrize('mutation,error', [
    ({'status':'unresolved'}, 'unresolved_requires_incomplete'),
    ({'status':'issue','finding_ids':['missing']}, 'requires_current_finding'),
    ({'status':'not_applicable'}, 'cannot_be_skipped'),
    ({'source_checks':[]}, 'requires_source_basis'),
    ({'field_path':'/reason_summary'}, 'requires_actual_prose_field'),
])
def test_inspection_cannot_hide_unchecked_work_or_use_author_note(mutation, error):
    artifacts = artifact_fixture()
    review = inspected(artifacts)
    review['inspection_checks'][1].update(mutation)
    with pytest.raises(ValueError, match=error):
        validate_inspection_checks(CaseReview.model_validate(review), artifacts, reads(artifacts), complete=True)


def test_quote_error_returns_exact_current_windows_without_accepting_normalized_quote():
    artifacts = artifact_fixture()
    original = artifacts.read_paper('P01')
    changed = deepcopy(original)
    changed['narrative_markdown'] = '**Bridge caveat**:\n1. Expense increase offsets earnings growth.'
    artifacts = artifacts.with_revisions({'P01':{'status':'revision_submitted','workpaper':changed,'finding_responses':[]}})
    finding = CaseReviewFinding(finding_id='location',paper_id='P01',severity='material',
        problematic_quote='Bridge caveat:\n1. Expense increase offsets earnings growth.',
        diagnosis='Synthetic formatting mismatch; no financial verdict.',requested_change='Inspect only the current bridge explanation.')
    review = CaseReview.model_validate(review_fixture(artifacts)).model_copy(update={'findings':[finding]})
    with pytest.raises(ValueError) as failure:
        validate_case_review(review, artifacts, reads(artifacts))
    feedback = json.loads(str(failure.value))['quote_recovery'][0]
    assert not feedback['accepted']
    location = next(x for x in feedback['locations'] if x['field_path']=='/narrative_markdown')
    assert location['text'] == changed['narrative_markdown']
    assert read_location(artifacts, 'P01', location['field_path'], location['offset'], 800) == location
    assert original['narrative_markdown'] != changed['narrative_markdown']


def test_strict_native_reviewer_consumes_manifest_and_can_submit_truthful_incomplete():
    async def exercise():
        artifacts = artifact_fixture()
        submitted = inspected(artifacts)
        submitted['completion'] = 'incomplete'
        submitted['unresolved_data_requests'] = ['A required original-source relation remains unverified.']
        submitted['inspection_checks'] = [submitted['inspection_checks'][0]]
        submitted['inspection_checks'][0].update(status='unresolved', source_checks=[])
        class InspectedChat(ScriptedNativeChat):
            def _generate(self, messages, stop=None, run_manager=None, **kwargs):
                assert 'inspection_manifest=' in messages[0].content
                return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
        model = InspectedChat(marker='inspection', replies=[
            [call('read_research_artifact',{'paper_id':p['paper_id']},p['paper_id']) for p in artifacts.catalog()['papers']],
            [call('read_review_location',{'paper_id':'P01','field_path':'/missing'},'bad-location')],
            [call('submit_case_review',{'review':submitted},'submit')]])
        async with Client(_build_server(case_artifacts=artifacts),raise_exceptions=False) as client:
            agent = build_case_reviewer(role='verifier', model=model, tools=await case_mcp_tools(client), artifacts=artifacts,
                max_model_calls=3, require_inspection=True)
            result = await agent.ainvoke({'messages':[HumanMessage(content='Inspect the synthetic current papers.')]})
        assert result['review']['completion']=='incomplete'
        assert result['review']['unresolved_data_requests']
        assert any(isinstance(m,ToolMessage) and m.status=='error' and 'unknown_review_field' in m.content for m in result['messages'])
    asyncio.run(exercise())


def incomplete_review(artifacts, question):
    return {'phase':'case_review_incomplete', 'scope_digest':case_review_scope_digest(artifacts,question),
        'verifier':{'status':'review_submitted','review':review_fixture(artifacts)},
        'counter':{'status':'incomplete_no_submission','review':None,'recorded_findings':{},
            'recovery_state':{'messages':['PRIVATE_HISTORY_SENTINEL']}, 'incomplete_output':['PRIVATE_REASONING_SENTINEL'],
            'tool_feedback':['problematic_quote_not_exact:location'],'model_calls':10}}


def recovery_decision():
    return {'summary':'Resume only the missing independent review; no financial approval.', 'action':'resume_review',
        'review_assignments':[{'reviewer':'counter','objective':'Recover the exact current prose location and complete outstanding scope checks.',
            'expected_progress':'Submit the preserved findings and remaining uncertainties using the current candidate.',
            'stop_condition':'Stop if the same location error recurs or necessary evidence remains unavailable.'}]}


def test_lead_recovery_is_scoped_and_does_not_receive_private_history():
    artifacts = artifact_fixture()
    review = incomplete_review(artifacts,'Current question')
    handoff = review_recovery_handoff(review,artifacts,'Current question')
    assert 'PRIVATE_' not in json.dumps(handoff)
    assert handoff['incomplete_reviewers']==['counter']
    decision = LeadIssueDecision.model_validate(recovery_decision())
    assert not decision_errors(decision,{}, {'P01','P02'},incomplete_reviewers=['counter'])
    assert decision_errors(decision,{}, {'P01','P02'})
    assert decision_errors(decision.model_copy(update={'action':'synthesize'}),{}, {'P01','P02'},incomplete_reviewers=['counter'])
    with pytest.raises(ValueError,match='current_incomplete_scope'):
        review_recovery_handoff(review,artifacts,'Changed research question')


def test_native_lead_tool_rejects_synthesis_during_incomplete_review_triage():
    from sec_agent.agent_runtime.report_synthesis_agent import build_case_output_agent
    from test_report_synthesis_agent import NativeFixtureModel
    async def exercise():
        decision = recovery_decision()
        model = NativeFixtureModel(marker='triage', replies=[
            [call('submit_lead_issue_decision', {'decision':{**decision,'action':'synthesize'}}, 'reject')],
            [call('submit_lead_issue_decision', {'decision':decision}, 'resume')]])
        agent = build_case_output_agent(role='decision',model=model,tools=[],artifacts=artifact_fixture(),
            limits={'model_calls':2,'tool_calls':4}, incomplete_reviewers=['counter'])
        result = await agent.ainvoke({'messages':[HumanMessage(content='Triage the outstanding saved review only.')], 'revisions':{}})
        assert result['output']['action']=='resume_review'
        assert any(isinstance(m,ToolMessage) and m.status=='error' and 'only resume_review or stop' in m.content for m in result['messages'])
        assert 'incomplete-review triage' in model.contexts[0][0].content
    asyncio.run(exercise())


def test_new_inspection_cannot_silently_reuse_legacy_clean_review():
    from sec_agent.agent_runtime.case_review_agent import build_case_review_graph
    artifacts=artifact_fixture()
    prior=incomplete_review(artifacts,'Same question')
    with pytest.raises(ValueError,match='legacy_complete_review_requires_new_inspection'):
        build_case_review_graph(reviewers={'counter':RunnableLambda(lambda x:x),'verifier':RunnableLambda(lambda x:x)},
            artifacts=artifacts,question='Same question',run_id='same',run_invocation_id='next',
            previous_review=prior,require_inspection=True)


@pytest.mark.parametrize('still_incomplete',[False,True])
def test_native_parent_lead_resumes_only_saved_review_once_then_converges_or_stops(still_incomplete):
    async def exercise():
        phases, _, _ = _phases()
        seen=[]
        async def review(state, config):
            seen.append('review')
            artifacts=current_task_artifacts(state)
            if seen.count('review')==1:
                return incomplete_review(artifacts,state['question'])
            assert state['previous_review']['counter']['recovery_state']['messages']==['PRIVATE_HISTORY_SENTINEL']
            assert state['review_recovery_instructions']['counter']['objective']
            result=incomplete_review(artifacts,state['question'])
            if not still_incomplete:
                result.update(phase='case_review_ready_for_convergence', counter={'status':'review_submitted','review':review_fixture(artifacts)})
            return result
        async def triage(state, config):
            seen.append('lead')
            return recovery_decision()
        async def converge(state, config):
            seen.append('converge')
            return {'phase':'research_convergence_needs_attention','stop_reason':'fixture_stops_before_any_financial_acceptance'}
        phases.update(review=RunnableLambda(review),triage_review=RunnableLambda(triage),converge=RunnableLambda(converge))
        app=build_research_session_graph(**phases).compile(checkpointer=InMemorySaver())
        result=await app.ainvoke({'question':'Inspect this synthetic question with source-bound review recovery.'},
            {'configurable':{'thread_id':'inspection-recovery'},'recursion_limit':100})
        assert seen==['review','lead','review']+([] if still_incomplete else ['converge'])
        assert result['review_triage_count']==1 and not result.get('report')
        assert 'PRIVATE_' not in json.dumps(result['review_triage_history'])
        assert len(result['research_review_history'])==2
    asyncio.run(exercise())
