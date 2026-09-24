"""Feedback provenance, isolation and nonblocking execution; no financial gold claims."""
import asyncio
from copy import deepcopy
import json

import pytest
from langchain_core.runnables import RunnableLambda
from sec_agent.agent_runtime.research_feedback import ReportResearchIssuesAction, FeedbackChoice, ResearchFeedbackStore, bind_issues
from sec_agent.agent_runtime.research_session import build_research_session_graph
from test_research_orientation import make_graph, call, read_result, submission


def action(**changes):
    issue = dict(issue_id='scope1', kind='relation_scope', summary='The transaction scope may be narrower.',
                 read_refs=['O1'], edge_ids=['EDGE::one'], impact='independent_search', next_check='Read the original announcement.')
    issue.update(changes)
    return ReportResearchIssuesAction(context_digest='a'*64, issues=[issue])


def observations():
    return [dict(read_ref='O1', selection={'operation':'related'}, result={'status':'success',
        'items':[{'edge_id':'EDGE::one', 'predicate':'procures', 'title':'Announcement'}]})]


def test_feedback_unread_original_is_a_question_not_disproof():
    result = bind_issues(action(), observations(), run_id='run1', snapshot_id='snap', library_sha256='f'*64)[0]
    assert result['status']=='pending_review' and not result['changes_published_graph']
    assert result['evidence']['O1']['original_read'] is False
    assert result['evidence']['O1']['preview'][0]['predicate']=='procures'
    assert result['library_sha256']=='f'*64
    with pytest.raises(ValueError, match='observed_read_refs'):
        bind_issues(action(read_refs=['O9']), observations(), run_id='r', snapshot_id='s')
    with pytest.raises(ValueError, match='edge_not_in'):
        bind_issues(action(edge_ids=['EDGE::invented']), observations(), run_id='r', snapshot_id='s')


def test_orientation_projection_keeps_evidence_but_not_repeated_transport_details():
    from sec_agent.agent_runtime.research_orientation import orientation_source_view, finding_read_refs, bind_orientation
    from sec_agent.agent_runtime.research_orientation import SubmitResearchOrientationAction
    result=read_result();result['items'][0]['mcp_receipt_chain']=[{'call_id':'receipt','request_digest':'a'*64}]
    original=deepcopy(result)
    projected=orientation_source_view(result)
    assert result==original and 'mcp_receipt_chain' not in projected['items'][0]
    assert projected['items'][0]['passage']==result['items'][0]['passage']
    obs=[{'read_ref':'O2','selection':{'operation':'read'},'result':result}]
    assert list(finding_read_refs(obs))==['O2']
    with pytest.raises(ValueError,match="finding=F1; invalid=.*O1.*available=.*O2"):
        bind_orientation(SubmitResearchOrientationAction.model_validate({'context_digest':'a'*64,**submission()}),obs)


def test_navigation_normalization_preserves_conflicts_dates_units_and_readbacks():
    from sec_agent.agent_runtime.research_orientation import orientation_source_view
    telemetry = {'mode': 'hybrid', 'graph_window_truncated': True, 'candidate_chunks': 30}
    metadata = {'period_end': '2026-06-30', 'unit': 'MW', 'revision': 'r2',
        'routing_metadata_v1': json.dumps({'period_end': '2026-06-30', 'unit': 'GW', 'old_id': 'v1'})}
    original = {'status': 'success', 'items': [
        {'metadata': json.dumps(metadata), 'retrieval': telemetry, 'next_offset': 10},
        {'retrieval': telemetry, 'source_known_at': None, 'publication_date': '2026-08-01'},
        {'passage': '{"metadata": "Do not rewrite this source"}', 'passage_id': 'p',
         'source_locator': {'revision': 'r2', 'page': 7},
         'context_readbacks': [{'node_id': 'next', 'operation': 'read'}]},
        {'metadata': 'unparsed metadata', 'failure': {'reason': 'read unavailable'}}]}
    saved = deepcopy(original)
    view = orientation_source_view(original)
    assert original == saved
    assert view['items'][0]['metadata']['routing_metadata_v1'] == {'unit': 'GW', 'old_id': 'v1'}
    assert view['items'][0]['metadata']['period_end'] == '2026-06-30'
    assert view['items'][0]['next_offset'] == 10
    for index in (0, 1):
        ref = view['items'][index]['retrieval']['same_receipt_ref']
        assert view['retrieval_contexts'][ref] == telemetry
    assert view['items'][1]['source_known_at'] is None
    assert view['items'][2:] == saved['items'][2:]
    assert orientation_source_view(view) == view


def test_feedback_store_isolation_idempotency_and_no_graph_write(tmp_path):
    store=ResearchFeedbackStore(tmp_path/'feedback.sqlite')
    records=bind_issues(action(),observations(),run_id='r',snapshot_id='s')
    record=records[0]
    store.save('alice','t',records); store.save('alice','t',records)
    assert len(store.list('alice','t','r'))==1
    assert store.list('bob','t')==[] and store.list('alice','other')==[] and store.list('alice','t','other')==[]
    changed=deepcopy(records); changed[0]['summary']='Different'
    with pytest.raises(ValueError,match='already_used'): store.save('alice','t',changed)
    choice=FeedbackChoice(submission_id='attempt-123',content_digest=record['content_digest'],choice='request_check')
    first=store.choose('alice','t',record['record_id'],choice)
    assert first==store.choose('alice','t',record['record_id'],choice)
    assert first['execution_status']=='recorded_not_executed'
    with pytest.raises(KeyError): store.choose('bob','t',record['record_id'],choice)
    with pytest.raises(ValueError,match='version_mismatch'):
        store.choose('alice','t',record['record_id'],choice.model_copy(update={'content_digest':'0'*64}))
    with pytest.raises(ValueError,match='submission_id_conflict'):
        store.choose('alice','t',record['record_id'],choice.model_copy(update={'choice':'avoid_inference'}))


def test_lead_feedback_does_not_block_submission_or_enable_children(tmp_path):
    store=ResearchFeedbackStore(tmp_path/'f.sqlite')
    def model(req):
        turn=req['progress']['turn_index']
        if turn==1: return call(req,'RequestSourceAction',dict(action='request_source', reason_summary='Read the evidence.',selection={'source_space':'library','operation':'read','document_id':'DOC::test'}))
        if turn==2: return call(req,'ReportResearchIssuesAction', {'issues':[action(edge_ids=[]).issues[0].model_dump(mode='json')]})
        assert req['orientation_context']['feedback_updates'][0]['run_id']=='native-run'
        return call(req,'SubmitResearchOrientationAction',submission())
    graph,value=make_graph(model,feedback_run_id='native-run',feedback_sink=lambda rows:store.save('u','t',rows),feedback_reader=lambda:store.list('u','t'))
    result=graph.invoke(value.model_dump(mode='json'))
    assert result['phase']=='research_orientation_submitted'
    assert len(result['research_feedback'])==1 and len(store.list('u','t'))==1


@pytest.mark.parametrize('phase', ['research_orientation_submitted','research_needs_attention'])
def test_parent_orientation_stops_before_experts_reviews_and_writer(phase):
    def research(request):
        assert request['research_stage']=='orientation'
        return {'phase':phase, 'research_orientation':{'overview':'Test planning only'}, 'research_feedback':[], 'planning_observations':[]}
    def forbidden(_): pytest.fail('orientation must not execute downstream phases')
    r=RunnableLambda(forbidden)
    graph=build_research_session_graph(research=RunnableLambda(research),review=r,converge=r,writer=r,verifier=r,quick_writer=r).compile()
    result=asyncio.run(graph.ainvoke({'question':'Test the source-bound research planning only.','research_stage':'orientation'}, {'configurable':{'run_id':'native-run'}}))
    assert result['phase']==phase and result['orientation_run_id']=='native-run'
    assert result['research_tasks']==[] and result['initialized']
