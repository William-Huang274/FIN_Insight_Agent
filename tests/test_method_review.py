"""Mechanical review contracts with declared fixtures, not a model finance eval."""
import asyncio
from copy import deepcopy

import pytest

from sec_agent.research_foundation.method_review import (
    MethodReview, assess_method_review, review_targets,
)
from sec_agent.research_foundation.method_diagnostic_graph import compile_method_probe
from test_method_diagnostic_graph import make_snapshot


def output(paper_id='first'):
    return dict(obligation={'obligation_id': paper_id}, contract_errors=[], calculations={},
        result=dict(obligation_id=paper_id, execution='completed', summary='Profit fell.',
            steps=[dict(step_id='F2', status='completed', finding='Revenue rose.', source_ids=['S1:p1'])],
            findings=[], unresolved=[], task_note=dict(changes=[], blockers=[], next_action='Lead review')),
        review_evidence=[dict(id='S1:p1', body='Revenue rose, operating profit fell.', digest='original')])


def check(target, **overrides):
    return dict(paper_id=target['paper_id'], paper_digest=target['paper_digest'],
        dimension='prose_consistency', field_path=target['field_path'], target_quote=target['text'],
        status='checked', result='Compared with the supplied original.',
        expressed_relationship=target['text'], supported_relationship='Revenue rose, operating profit fell.',
        financial_verdict='supported', clarity_verdict='clear', clarity_reason='Period and entity preserved.',
        calculation_check='none_added', source_checks=[dict(source_id='S1:p1', quote='operating profit fell.')],
        **overrides)


def full_review(row):
    return MethodReview(inspection_checks=[check(t) for t in review_targets(row)])


def issue_review(row):
    review = full_review(row)
    first = review.inspection_checks[0]
    first.status = 'issue'; first.financial_verdict = 'contradicted'; first.finding_ids = ['issue-1']
    body = review.model_dump(mode='json')
    body['findings'] = [dict(finding_id='issue-1', paper_id=row['obligation']['obligation_id'],
        severity='material', finding_type='financial_error', problematic_quote=row['result']['summary'],
        diagnosis='Declared test issue, not a machine-derived financial diagnosis.',
        requested_change='Recheck the affected statement and its related explanation.',
        source_checks=[dict(source_id='S1:p1', quote='operating profit fell.')])]
    return MethodReview.model_validate(body)


def test_omission_is_pending_not_acceptance_and_does_not_destroy_old_checks():
    row=output()
    missing=assess_method_review([row], MethodReview())
    assert not missing['complete'] and len(missing['pending_targets'])==2
    partial=MethodReview(inspection_checks=[check(review_targets(row)[0])])
    saved=assess_method_review([row], partial)
    omitted=assess_method_review([row], MethodReview(), saved['state'])
    assert omitted['state']==saved['state'] and len(omitted['pending_targets'])==1
    assert not omitted['financial_semantics_checked_by_runtime']


@pytest.mark.parametrize('mutation,error', [
    ('stale', 'version_or_target'), ('source', 'source_not_delivered'), ('quote', 'source_quote_not_exact'),
    ('skip', 'cannot_skip'), ('verdict', 'verdict_mismatch'), ('duplicate', 'duplicate_target'),
    ('target', 'target_quote_not_exact'), ('relationship', 'explicit_semantic_comparison'),
])
def test_invalid_review_cannot_promote_or_replace_prior_state(mutation,error):
    row=output(); review=full_review(row); c=review.inspection_checks[0]
    if mutation=='stale': c.paper_digest='stale'
    elif mutation=='source': c.source_checks[0].source_id='not-delivered'
    elif mutation=='quote': c.source_checks[0].quote='profit doubled'
    elif mutation=='skip': c.status='not_applicable'
    elif mutation=='verdict': c.financial_verdict='contradicted'
    elif mutation=='target': c.target_quote='invented target'
    elif mutation=='relationship': c.supported_relationship=''
    else: review.inspection_checks.append(c.model_copy(deep=True))
    result=assess_method_review([row],review)
    assert any(error in e for e in result['errors']) and not result['complete']
    assert result['state']=={'checks':{},'findings':{},'closures':{}}


def test_changed_candidate_invalidates_old_review_without_rewriting_history():
    row=output(); saved=assess_method_review([row],full_review(row))
    assert saved['complete']
    changed=deepcopy(row); changed['result']['summary']='A different current judgment.'
    current=assess_method_review([changed],MethodReview(),saved['state'])
    assert len(current['pending_targets'])==2 and not current['complete']
    assert current['state']==saved['state']


def repair_fixture():
    first=output(); first['result']['summary']='Profit rose.'
    saved=assess_method_review([first],issue_review(first))
    repair=output('repair')
    repair['repair_targets']=[saved['state']['findings']['issue-1']]
    review=full_review(repair).model_dump(mode='json')
    review['finding_checks']=[dict(finding_id='issue-1',status='resolved',
        reason='Explicitly reviewed the current repair and source; test-authored verdict.',
        paper_id='repair',paper_digest=review_targets(repair)[0]['paper_digest'],
        current_quote='Profit fell.',clarity_verdict='clear',
        source_checks=[dict(source_id='S1:p1',quote='operating profit fell.')])]
    return first,repair,MethodReview.model_validate(review),saved['state']


def test_new_author_completion_does_not_close_issue_explicit_review_does():
    first,repair,review,state=repair_fixture()
    before=assess_method_review([first,repair],full_review(repair),state)
    assert before['open_finding_ids']==['issue-1'] and not before['complete']
    after=assess_method_review([first,repair],review,state)
    assert after['errors']==[] and after['complete']
    assert after['state']['closures']['issue-1']['paper_id']=='repair'
    assert after['state']['findings']['issue-1']['paper_id']=='first'


@pytest.mark.parametrize('mutation,error', [('lineage','exact_repair_lineage'),('digest','exact_repair_lineage'),
    ('unreviewed','checked_current_repair'),('current_quote','current_quote'),('source','requires_original')])
def test_closure_cannot_be_faked_by_stale_or_unreviewed_revision(mutation,error):
    first,repair,review,state=repair_fixture()
    if mutation=='lineage': repair['repair_targets']=[]
    elif mutation=='digest': review.finding_checks[0].paper_digest='old'
    elif mutation=='unreviewed': review.inspection_checks=[]
    elif mutation=='current_quote': review.finding_checks[0].current_quote='new but absent'
    else: review.finding_checks[0].source_checks=[]
    outcome=assess_method_review([first,repair],review,state)
    assert any(error in e for e in outcome['errors']) and not outcome['complete']
    assert 'issue-1' not in outcome['state']['closures']


def task(name, **extra):
    return dict(task_id=name,question='Check the comparison',method_id='financial_quality',steps=['F2'],
        expectation='factual',source_ids=['S1'],search_terms=['Revenue'],**extra)


def decision(action, tasks=(), review=None):
    return dict(action=action,public_basis='Bounded test plan',synthesis='Test synthesis',open_issues=[],
        tasks=list(tasks),review=(review or MethodReview()).model_dump(mode='json'))


@pytest.mark.parametrize('resume', [False, True])
def test_native_graph_dispatches_issue_and_confirms_exact_repair(tmp_path, resume):
    calls=[]; observed=[]
    async def call(actor,payload,schema):
        calls.append(actor)
        if actor=='lead':
            if not payload['results']: return decision('delegate',[task('first')])
            if len(payload['results'])==1:
                review=issue_review(payload['results'][0])
                return decision('delegate',[task('repair',dependency_ids=['first'],repair_finding_ids=['issue-1'])],review)
            row=payload['results'][-1]; review=full_review(row).model_dump(mode='json')
            review['finding_checks']=repair_fixture()[2].model_dump(mode='json')['finding_checks']
            review['finding_checks'][0]['paper_digest']=review_targets(row)[0]['paper_digest']
            assert payload['review_context']['open_findings'][0]['finding_id']=='issue-1'
            return decision('stop',review=MethodReview.model_validate(review))
        if actor=='repair':
            assert payload['repair_targets'][0]['paper_id']=='first'
            assert payload['prior_results'][0]['obligation']['obligation_id']=='first'
        result=output(actor)['result']
        if actor=='first': result['summary']='Profit rose.'
        return result
    from langgraph.checkpoint.memory import InMemorySaver
    snapshot=make_snapshot(tmp_path); saver=InMemorySaver() if resume else None
    def compile_graph():
        return compile_method_probe(snapshot=snapshot,call=call,record=lambda k,v:observed.append((k,v)),
            checkpointer=saver,interrupt_after=['wave_done'] if resume else None)
    graph=compile_graph(); config={'configurable':{'thread_id':'review-resume-test'}}
    state=asyncio.run(graph.ainvoke(dict(question='q',as_of='2025-06-01',catalog_ids=['S1'],results=[],waves=0),config))
    if resume:
        graph=compile_graph()
        state=asyncio.run(graph.ainvoke(None,config))
        assert state['review_state']['findings']['issue-1']['field_paths']==['/summary']
        assert not state['review_state']['closures']
        graph=compile_graph()
        state=asyncio.run(graph.ainvoke(None,config))
    assert calls==['lead','first','lead','repair','lead']
    assert state['review_receipt']['complete'] and state['terminal']=='probe_closed_not_report_acceptance'
    assert state['results'][1]['repair_targets'][0]['finding_id']=='issue-1'
    assert any(k=='lead_review_receipt' for k,_ in observed)


def test_legacy_lead_stop_preserves_unreviewed_targets(tmp_path):
    async def call(actor,payload,schema):
        if actor=='lead': return decision('stop') if payload['results'] else decision('delegate',[task('first')])
        return output()['result']
    graph=compile_method_probe(snapshot=make_snapshot(tmp_path),call=call,record=lambda *a:None)
    state=asyncio.run(graph.ainvoke(dict(question='q',as_of='2025-06-01',catalog_ids=['S1'],results=[],waves=0)))
    assert state['terminal']=='bounded_stop' and len(state['review_receipt']['pending_targets'])==2


def test_changed_repair_reopens_historical_closure():
    first,repair,review,state=repair_fixture()
    closed=assess_method_review([first,repair],review,state)
    repair['result']['summary']='Current replacement judgment.'
    reopened=assess_method_review([first,repair],full_review(repair),closed['state'])
    assert reopened['invalidated_closures']==['issue-1']
    assert reopened['open_finding_ids']==['issue-1'] and not reopened['complete']


def test_well_formed_but_wrong_model_verdict_is_not_machine_financial_acceptance():
    row=output(); row['result']['summary']='Profit rose.'
    # Deliberately lie in the model verdict despite the supplied contrary text.
    # This adapter checks references and coverage; it cannot prove entailment.
    outcome=assess_method_review([row],full_review(row))
    assert outcome['complete'] and not outcome['financial_semantics_checked_by_runtime']


def test_existing_quote_span_contract_is_accepted_without_recopying_original():
    row=output(); review=full_review(row)
    from sec_agent.agent_runtime.case_review_agent import ReviewSourceCheck
    review.inspection_checks[0].source_checks=[ReviewSourceCheck(source_id='S1:p1',
        quote_span=dict(source_digest='original',start=0,end=12))]
    assert assess_method_review([row],review)['complete']
    review.inspection_checks[0].source_checks[0].quote_span.end=1000
    assert any('span_mismatch' in e for e in assess_method_review([row],review)['errors'])


@pytest.mark.parametrize('kind,error', [('unknown','current_open_finding'),('missing_dependency','original_dependency'),
    ('duplicate','duplicate_repair_assignment')])
def test_invalid_repair_plan_cannot_dispatch_workers(tmp_path,kind,error):
    calls=[]
    async def call(actor,payload,schema):
        calls.append(actor)
        if actor=='lead':
            if not payload['results']: return decision('delegate',[task('first')])
            plan=task('repair',dependency_ids=[] if kind=='missing_dependency' else ['first'],
                repair_finding_ids=['unknown'] if kind=='unknown' else ['issue-1'])
            tasks=[plan]
            if kind=='duplicate': tasks.append({**plan,'task_id':'repair-duplicate'})
            return decision('delegate',tasks,issue_review(payload['results'][0]))
        return output()['result']
    graph=compile_method_probe(snapshot=make_snapshot(tmp_path),call=call,record=lambda *a:None)
    with pytest.raises(ValueError,match=error):
        asyncio.run(graph.ainvoke(dict(question='q',as_of='2025-06-01',catalog_ids=['S1'],results=[],waves=0)))
    assert calls==['lead','first','lead']


def test_bad_review_stops_graph_before_dispatching_repair(tmp_path):
    calls=[]
    async def call(actor,payload,schema):
        calls.append(actor)
        if actor=='lead':
            if not payload['results']: return decision('delegate',[task('first')])
            review=issue_review(payload['results'][0]); review.inspection_checks[0].paper_digest='stale'
            return decision('delegate',[task('repair',dependency_ids=['first'],repair_finding_ids=['issue-1'])],review)
        return output()['result']
    graph=compile_method_probe(snapshot=make_snapshot(tmp_path),call=call,record=lambda *a:None)
    state=asyncio.run(graph.ainvoke(dict(question='q',as_of='2025-06-01',catalog_ids=['S1'],results=[],waves=0)))
    assert calls==['lead','first','lead'] and state['terminal']=='review_contract_unresolved'
    assert state['review_receipt']['errors'] and not state['review_state']['findings']


def test_offline_replay_records_original_hash_and_missing_checks(tmp_path):
    import json
    from hashlib import sha256
    from scripts.engineering.replay_method_review import replay
    state_path=tmp_path/'state.json'; decision_path=tmp_path/'decision.json'
    state_path.write_text(json.dumps({'results':[output()],'terminal':'probe_closed_not_report_acceptance'}),encoding='utf-8')
    decision_path.write_text(json.dumps({'action':'stop'}),encoding='utf-8')
    state_before=state_path.read_bytes(); decision_before=decision_path.read_bytes()
    result=replay(state_path,decision_path)
    assert result['input_digests']['state']==sha256(state_before).hexdigest()
    assert result['provider_calls']==0 and not result['receipt']['complete']
    assert state_path.read_bytes()==state_before and decision_path.read_bytes()==decision_before
