from hashlib import sha256
import asyncio

import pytest

from sec_agent.research_foundation.research_snapshot import build_snapshot, ResearchSnapshot
from sec_agent.research_foundation.method_diagnostic_graph import compile_method_probe


def make_snapshot(tmp_path):
    path=tmp_path/'evidence.sqlite'
    sources=[dict(id=k,title=k,url='https://example.org/'+k,published_at=d,
        vintage=v,access_state=a,digest=sha256(k.encode()).hexdigest()) for k,d,v,a in [
            ('S1','2025-01-01','dated_original','readable'),
            ('FUTURE','2026-01-01','dated_original','readable'),
            ('REVISED','2025-01-01','current_revised','readable'),
            ('FAILED','2025-01-01','dated_original','transport_failed')]]
    build_snapshot(path,sources,[dict(id=k+':p1',source_id=k,locator='p1',body='Revenue rose, operating profit fell.') for k in ['S1','FUTURE','REVISED']],
        entities=[dict(id='A',kind='company',name='A'),dict(id='B',kind='company',name='B')],
        edges=[dict(id='E1',subject='A',predicate='supplies',object='B',source_id='S1',locator='p1',published_at='2025-01-01',status='disclosed')])
    return ResearchSnapshot(path)


def test_snapshot_filters_future_and_revision_without_hiding_failure(tmp_path):
    snapshot=make_snapshot(tmp_path)
    assert [r['source_id'] for r in snapshot.search(['Revenue'],'2025-06-01')]==['S1']
    assert snapshot.read('FAILED','2025-06-01')['status']=='transport_failed'
    assert snapshot.read('REVISED','2025-06-01')['status']=='ineligible_vintage_or_date'
    assert snapshot.related('A','2024-12-31')==[]
    assert snapshot.related('A','2025-06-01')[0]['predicate']=='supplies'
    with pytest.raises(FileExistsError):build_snapshot(snapshot.path,[],[])


def test_scoped_full_originals_are_not_cut_to_top_k_when_within_budget(tmp_path):
    import sqlite3
    snapshot=make_snapshot(tmp_path)
    # Long enough to exceed the old26k cutoff; necessary tail does not match query.
    with sqlite3.connect(snapshot.path) as db:
        for i in range(9):
            body=('revenue ' if i<8 else 'necessary comparative segment table ')+'x'*3400
            db.execute('INSERT INTO passages VALUES(?,?,?,?,?)',(f'S1:p{i+2}','S1',f'p{i+2}',body,sha256(body.encode()).hexdigest()))
            db.execute('INSERT INTO passage_search VALUES(?,?,?)',(f'S1:p{i+2}','S1',body))
    async def call(actor,payload,schema):
        if actor=='lead':
            if payload['results']:
                return dict(action='stop',public_basis='done',synthesis='limited',open_issues=[],tasks=[])
            return dict(action='delegate',public_basis='compare',synthesis='',open_issues=[],tasks=[dict(task_id='t',question='compare',method_id='financial_quality',steps=['F2'],expectation='factual',source_ids=['S1'],search_terms=['revenue'])])
        assert payload['read_results'][0]['coverage']['complete_document']
        assert any('necessary comparative' in p['body'] for p in payload['read_results'][0]['items'])
        return dict(obligation_id='t',execution='completed',summary='checked',steps=[dict(step_id='F2',status='completed',finding='checked tail',source_ids=['S1:p10'])],findings=[],unresolved=[],task_note=dict(changes=['checked'],blockers=[],next_action='lead'))
    graph=compile_method_probe(snapshot=snapshot,call=call,record=lambda *a:None)
    asyncio.run(graph.ainvoke(dict(question='q',as_of='2025-06-01',catalog_ids=['S1'],waves=0,results=[],decisions=[])))


def test_native_fanout_then_lead_consumes_actual_work_and_updates(tmp_path):
    snapshot=make_snapshot(tmp_path);calls=[];records=[]
    async def call(actor,payload,schema):
        calls.append((actor,payload))
        if actor=='lead':
            if not payload['results']:
                return dict(action='delegate',public_basis='Need scoped comparisons',synthesis='',open_issues=['profit'],tasks=[
                    dict(task_id=k,question=q,method_id='financial_quality',steps=['F2'],
                         expectation='conditional',source_ids=['S1'],search_terms=['Revenue'])
                    for k,q in [('revenue','Check revenue'),('profit','Check operating profit')]])
            assert len(payload['results'])==2
            assert all(not r['contract_errors'] for r in payload['results'])
            return dict(action='stop',public_basis='Consumed both results',synthesis='Growth without profit improvement',open_issues=['causal attribution'],tasks=[])
        assert payload['method_digests']['financial_quality']
        assert payload['read_results'][0]['coverage']['complete_document']
        return dict(obligation_id=actor,execution='partial',summary='Observed divergence',
            steps=[dict(step_id='F2',status='completed',finding='Revenue up profit down',source_ids=['S1:p1'])],
            findings=[dict(statement='Divergence',kind='factual',source_ids=['S1:p1'],public_basis='Original text',assumptions=[],alternative='Costs',would_change='Restatement')],
            unresolved=['causal attribution'],task_note=dict(changes=['compared'],blockers=[],next_action='Lead integrate'))
    graph=compile_method_probe(snapshot=snapshot,call=call,record=lambda k,v:records.append((k,v)))
    result=asyncio.run(graph.ainvoke(dict(question='Growth quality',as_of='2025-06-01',catalog_ids=['S1'],waves=0,results=[],decisions=[])))
    assert result['waves']==1 and result['terminal']=='bounded_stop'
    assert [x[0] for x in calls].count('lead')==2
    assert {r['obligation']['obligation_id'] for r in result['results']}=={'revenue','profit'}


def test_invalid_plan_stops_before_worker_payment(tmp_path):
    calls=[]
    async def call(actor,payload,schema):
        calls.append(actor)
        return dict(action='delegate',public_basis='bad source',synthesis='',open_issues=[],tasks=[dict(
            task_id='a',question='q',method_id='financial_quality',steps=['F2'],expectation='factual',source_ids=['invented'],search_terms=['a'])])
    graph=compile_method_probe(snapshot=make_snapshot(tmp_path),call=call,record=lambda *a:None)
    with pytest.raises(ValueError,match='plan_unknown_source'):
        asyncio.run(graph.ainvoke(dict(question='q',as_of='2025-06-01',catalog_ids=['S1'],waves=0,results=[],decisions=[])))
    assert calls==['lead']


def test_followup_uses_selected_dependency_and_enforces_wave_limit(tmp_path):
    snapshot=make_snapshot(tmp_path);workers=[]
    async def call(actor,payload,schema):
        if actor=='lead':
            wave=payload['waves_completed']
            task=dict(task_id=f't{wave}',question='resolve specific remaining comparison',method_id='financial_quality',
                steps=['F2'],expectation='conditional',source_ids=['S1'],search_terms=['Revenue'],
                dependency_ids=['t0'] if wave else [])
            return dict(action='delegate',public_basis='new observation requires targeted work',synthesis='',open_issues=['remaining'],tasks=[task])
        workers.append(actor)
        assert [r['obligation']['obligation_id'] for r in payload['prior_results']]==(['t0'] if actor=='t1' else [])
        return dict(obligation_id=actor,execution='partial',summary='specific result',steps=[dict(step_id='F2',status='completed',finding='compared',source_ids=['S1:p1'])],findings=[],unresolved=['remaining'],task_note=dict(changes=['comparison'],blockers=[],next_action='lead'))
    graph=compile_method_probe(snapshot=snapshot,call=call,record=lambda *a:None,max_waves=2)
    result=asyncio.run(graph.ainvoke(dict(question='q',as_of='2025-06-01',catalog_ids=['S1'],waves=0,results=[],decisions=[])))
    assert workers==['t0','t1']
    assert result['terminal']=='wave_limit_unresolved' and result['waves']==2


def test_no_paid_worker_when_all_source_inputs_are_unavailable(tmp_path):
    calls=[]
    async def call(actor,payload,schema):
        calls.append(actor)
        assert actor=='lead'
        if payload['results']:
            r=payload['results'][0]
            assert r['result_origin']=='runtime_execution_receipt_no_model_call'
            assert r['result']['execution']=='tool_failed' and not r['result']['findings']
            return dict(action='stop',public_basis='recover data',synthesis='',open_issues=['source failure'],tasks=[])
        return dict(action='delegate',public_basis='check',synthesis='',open_issues=[],tasks=[dict(task_id='t',question='q',method_id='financial_quality',steps=['F2'],expectation='factual',source_ids=['FAILED'],search_terms=['revenue'])])
    graph=compile_method_probe(snapshot=make_snapshot(tmp_path),call=call,record=lambda *a:None)
    result=asyncio.run(graph.ainvoke(dict(question='q',as_of='2025-06-01',catalog_ids=['FAILED'],waves=0,results=[],decisions=[])))
    assert calls==['lead','lead'] and result['terminal']=='bounded_stop'
