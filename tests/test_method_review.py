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


def test_new_submission_exposes_required_review_fields_but_archives_stay_readable():
    from pydantic import ValidationError
    from sec_agent.research_foundation.method_review import SubmittedMethodReview
    schema=SubmittedMethodReview.model_json_schema()
    required=schema['$defs']['SubmittedMethodInspectionCheck']['required']
    fields=['source_checks','expressed_relationship','supported_relationship',
            'financial_verdict','clarity_verdict','clarity_reason','calculation_check']
    assert set(fields)<=set(required)
    valid=full_review(output()).model_dump(mode='json')
    SubmittedMethodReview.model_validate(valid)
    for field in fields:
        old=deepcopy(valid); del old['inspection_checks'][0][field]
        MethodReview.model_validate(old)
        with pytest.raises(ValidationError): SubmittedMethodReview.model_validate(old)


def test_unique_issue_link_is_audited_without_mutating_model_submission():
    row=output(); review=issue_review(row)
    review.inspection_checks[0].finding_ids=[]
    original=review.model_dump(mode='json')
    receipt=assess_method_review([row],review)
    assert receipt['errors']==[] and receipt['open_finding_ids']==['issue-1']
    assert not receipt['complete']
    assert review.model_dump(mode='json')==original
    record=receipt['runtime_parsing'][0]
    assert record['origin']=='runtime_compatibility_parse'
    assert record['normalized_result']==['issue-1'] and not record['financial_semantics_verified']
    assert receipt['state']['checks']['first:/summary']['finding_ids']==['issue-1']


@pytest.mark.parametrize('ambiguity',['finding','target','stale','explicit_wrong'])
def test_issue_link_does_not_guess_or_override_explicit_model_link(ambiguity):
    row=output(); review=issue_review(row); review.inspection_checks[0].finding_ids=[]
    if ambiguity=='finding':
        review.findings.append(review.findings[0].model_copy(update={'finding_id':'another'}))
    elif ambiguity=='target': row['result']['steps'][0]['finding']=row['result']['summary']
    elif ambiguity=='stale': review.inspection_checks[0].paper_digest='old'
    else: review.inspection_checks[0].finding_ids=['nonexistent']
    receipt=assess_method_review([row],review)
    assert receipt['errors'] and receipt['runtime_parsing']==[] and not receipt['complete']


@pytest.mark.parametrize('variant',['same','other_document','other_revision','unidentified','repeated','invented'])
def test_quote_locator_only_suggests_delivered_same_version_and_keeps_rejection(variant):
    row=output(); review=full_review(row)
    identity=dict(id='doc',digest='v1',published_at='2025-01-01',vintage='dated_original')
    row['review_evidence'][0]['source']=identity
    other=dict(id='S1:p2',body='Revenue rose. Future costs will rise.',digest='window2',source=deepcopy(identity))
    if variant=='other_document': other['source']['id']='different'
    elif variant=='other_revision': other['source']['digest']='v2'
    elif variant=='unidentified': row['review_evidence'][0]['source']={}
    elif variant=='repeated': other['body']+=' Future costs will rise.'
    elif variant=='invented': other['body']='No such quote exists.'
    row['review_evidence'].append(other)
    review.inspection_checks[0].source_checks[0].quote='Future costs will rise.'
    original=review.model_dump(mode='json')
    receipt=assess_method_review([row],review)
    assert any('quote_not_exact' in e for e in receipt['errors'])
    assert not receipt['complete'] and receipt['state']['checks']=={}
    assert review.model_dump(mode='json')==original
    recovery=receipt['source_quote_recovery'][0]
    assert not recovery['citation_rebound'] and not recovery['draft_changed']
    assert bool(recovery['candidates'])==(variant=='same')
    if variant=='same':
        candidate=recovery['candidates'][0]; span=candidate['quote_span']
        assert other['body'][span['start']:span['end']]==candidate['quote']


def test_two_matching_windows_remain_two_candidates_not_a_silent_selection():
    from sec_agent.research_foundation.method_review import quote_location_candidates
    identity=dict(id='doc',digest='v1')
    sources={str(i):dict(id=str(i),source=identity,digest=str(i),body='The same sentence.') for i in range(3)}
    candidates=quote_location_candidates(sources['0'],'The same sentence.',sources)
    assert [c['source_id'] for c in candidates]==['1','2']


def test_reentry_exposes_exact_rejection_and_submission_schema_without_dispatch(tmp_path):
    from sec_agent.research_foundation.method_diagnostic_graph import SubmittedProbeDecision
    calls=[]
    async def call(actor,payload,schema):
        calls.append(actor)
        assert schema is SubmittedProbeDecision
        assert payload['judgment_policy']['may_revise_upstream_judgment']
        assert not payload['judgment_policy']['freeze_before_required_reading']
        assert payload['previous_review_feedback']['errors']==['review_checked_requires_original:first:/summary']
        assert payload['results'][0]['result']==output()['result']
        return decision('stop')
    graph=compile_method_probe(snapshot=make_snapshot(tmp_path),call=call,record=lambda *a:None)
    state=asyncio.run(graph.ainvoke(dict(question='q',as_of='2025-06-01',catalog_ids=['S1'],
        results=[output()],waves=1,review_receipt={'errors':['review_checked_requires_original:first:/summary']})))
    assert calls==['lead'] and state['terminal']=='bounded_stop'
    assert not state['review_receipt']['complete']


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


def test_revision_comparison_preserves_entire_added_meaning_and_fallible_advice():
    from sec_agent.research_foundation.method_review import revision_comparisons
    first,repair,_,_=repair_fixture()
    repair['result']['summary']='Profit fell. Public disclosure is required before recognition.'
    before=deepcopy([first,repair])
    comparison=revision_comparisons([first,repair])[0]
    assert comparison['comparison_status']=='current_versions_compared'
    delta=next(x for x in comparison['changes'] if x['field_path']=='/summary')
    assert delta['before']==first['result']['summary'] and delta['after']==repair['result']['summary']
    assert 'Public disclosure' in delta['paragraph_edits'][0]['introduced_text']
    assert comparison['repair_advice'][0]['authority']=='fallible_reviewer_opinion_not_source'
    assert [first,repair]==before and not comparison['financial_semantics_checked_by_runtime']


def test_revision_comparison_aligns_reordered_steps_by_id_and_records_removals():
    from sec_agent.research_foundation.method_review import revision_comparisons
    from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256
    first,repair,_,_=repair_fixture()
    first['result']['steps'] += [dict(step_id='F3',status='completed',finding='Old F3.',source_ids=['S1:p1']),
                                 dict(step_id='F4',status='completed',finding='Deleted step.',source_ids=['S1:p1'])]
    first['result']['findings']=[dict(statement='Old claim.')]
    repair['repair_targets'][0]['paper_digest']=canonical_sha256(first['result'])
    repair['result']['steps']=[dict(step_id='F3',status='completed',finding='New F3.',source_ids=['S1:p1']),repair['result']['steps'][0]]
    repair['result']['findings']=[dict(statement='New claim.')]
    rows=revision_comparisons([first,repair])[0]['changes']
    step=next(r for r in rows if r['field_path']=='/steps/0/finding')
    assert step['original_field_path']=='/steps/1/finding' and step['before']=='Old F3.'
    assert any(r['before']=='Deleted step.' and r['field_path'] is None for r in rows)
    assert any(r['after']=='New claim.' and r['original_field_path'] is None for r in rows)
    assert any(r['before']=='Old claim.' and r['field_path'] is None for r in rows)


def test_revision_comparison_refuses_stale_original_instead_of_guessing_diff():
    from sec_agent.research_foundation.method_review import revision_comparisons
    first,repair,_,_=repair_fixture()
    first['result']['summary']='A changed original.'
    row=revision_comparisons([first,repair])[0]
    assert row['comparison_status']=='original_missing_or_changed' and row['changes']==[]


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
            comparisons=payload['review_context']['revision_comparisons']
            assert comparisons[0]['paper_id']=='repair'
            assert comparisons[0]['changes'][0]['before']=='Profit rose.'
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


def test_contract_errors_remain_until_exact_element_repair_is_confirmed():
    first,repair,review,state=repair_fixture()
    first['contract_errors']=[dict(code='unknown_source',location='/steps/0/source_ids',detail='missing')]
    # The existing issue targets /summary, not the broken step. Cannot waive it.
    blocked=assess_method_review([first,repair],review,state)
    assert not blocked['complete'] and len(blocked['outstanding_contract_errors'])==1
    state['findings']['issue-1']['field_paths'].append('/steps/0/finding')
    fixed=assess_method_review([first,repair],review,state)
    assert fixed['complete'] and fixed['outstanding_contract_errors']==[]
    first['contract_errors'].append(dict(code='missing_required_steps',location='/steps',detail=['F3']))
    assert not assess_method_review([first,repair],review,state)['complete']


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
