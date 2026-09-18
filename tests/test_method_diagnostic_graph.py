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


def test_retrospective_policy_is_explicit_and_shared_by_read_search_and_contract(tmp_path):
    import sqlite3, json
    from datetime import date
    from test_method_execution import fixture
    from sec_agent.research_foundation.method_execution import assess_result_contract
    original=make_snapshot(tmp_path)
    with sqlite3.connect(original.path) as db:
        db.execute("UPDATE sources SET published_at=NULL, metadata=? WHERE id='REVISED'",(json.dumps({'known_at':'2026-09-18'}),))
    assert original.read('REVISED','2025-06-01')['status']=='ineligible_vintage_or_date'
    retrospective=ResearchSnapshot(original.path,time_mode='retrospective',knowledge_as_of='2026-09-18')
    assert retrospective.read('REVISED','2025-06-01')['status']=='readable'
    assert any(s['id']=='REVISED' and s['eligible'] for s in retrospective.catalog('2025-06-01'))
    with pytest.raises(ValueError,match='knowledge_date_precedes'):
        retrospective.catalog('2027-01-01')
    task,source,result=fixture()
    task.time_mode='retrospective';task.knowledge_as_of=date(2026,9,18)
    source.vintage='current_revised';source.published_at=None;source.known_at=date(2026,9,18)
    assert assess_result_contract(task,result,{'S1':source})==[]
    task.time_mode='strict_as_of'
    assert assess_result_contract(task,result,{'S1':source})


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
            assert {m['method_id'] for m in payload['industry_methods']} == {
                'semiconductor_systems','model_compute_demand','manufacturing_capacity',
                'software_platforms','financial_quality','cloud_infrastructure',
                'power_projects','financing_ownership','macro_valuation'}
            if not payload['results']:
                return dict(action='delegate',public_basis='Need scoped comparisons',synthesis='',open_issues=['profit'],tasks=[
                    dict(task_id=k,question=q,method_id='financial_quality',steps=['F2'],
                         expectation='conditional',source_ids=['S1'],search_terms=['Revenue'])
                    for k,q in [('revenue','Check revenue'),('profit','Check operating profit')]])
            assert len(payload['results'])==2
            assert all(not r['contract_errors'] for r in payload['results'])
            assert len(payload['review_evidence'])==1
            assert payload['review_evidence'][0]['id']=='S1:p1'
            assert payload['review_evidence'][0]['body']=='Revenue rose, operating profit fell.'
            assert all('review_evidence' not in r for r in payload['results'])
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


def test_same_wave_dependencies_use_native_order_and_original_sources(tmp_path):
    calls=[]
    async def call(actor,payload,schema):
        calls.append(actor)
        if actor=='lead':
            if payload['results']:
                return dict(action='stop',public_basis='used dependencies',synthesis='limited',open_issues=[],tasks=[])
            return dict(action='delegate',public_basis='sequential checks',synthesis='',open_issues=[],tasks=[dict(
                task_id=name,question='compare',method_id='financial_quality',steps=['F2'],expectation='factual',
                source_ids=['S1'],search_terms=['Revenue'],dependency_ids=['first'] if name=='second' else [])
                for name in ['second','first']])
        assert [r['obligation']['obligation_id'] for r in payload['prior_results']]==(['first'] if actor=='second' else [])
        return dict(obligation_id=actor,execution='completed',summary='checked',steps=[dict(step_id='F2',status='completed',finding='checked',source_ids=['S1:p1'])],findings=[],unresolved=[],task_note=dict(changes=['checked'],blockers=[],next_action='lead'))
    graph=compile_method_probe(snapshot=make_snapshot(tmp_path),call=call,record=lambda *a:None,max_waves=1)
    result=asyncio.run(graph.ainvoke(dict(question='q',as_of='2025-06-01',catalog_ids=['S1'],waves=0,results=[],decisions=[])))
    assert calls==['lead','first','second','lead'] and result['waves']==1


def test_cyclic_same_wave_plan_is_rejected_before_workers(tmp_path):
    calls=[]
    async def call(actor,payload,schema):
        calls.append(actor)
        return dict(action='delegate',public_basis='bad cycle',synthesis='',open_issues=[],tasks=[dict(
            task_id=name,question='compare',method_id='financial_quality',steps=['F2'],expectation='factual',
            source_ids=['S1'],search_terms=['Revenue'],dependency_ids=[other]) for name,other in [('a','b'),('b','a')]])
    graph=compile_method_probe(snapshot=make_snapshot(tmp_path),call=call,record=lambda *a:None)
    with pytest.raises(ValueError,match='cyclic_task_dependency'):
        asyncio.run(graph.ainvoke(dict(question='q',as_of='2025-06-01',catalog_ids=['S1'],waves=0,results=[],decisions=[])))
    assert calls==['lead']


def test_paginated_neighbour_does_not_clip_complete_document_within_scope_budget(tmp_path):
    import sqlite3
    snapshot=make_snapshot(tmp_path)
    with sqlite3.connect(snapshot.path) as db:
        db.execute("UPDATE sources SET published_at='2025-01-01' WHERE id='FUTURE'")
        for sid,count,body in [('S1',9,'x'*3400),('FUTURE',44,'revenue details')]:
            for i in range(count):
                text=('necessary tail comparison ' if sid=='S1' and i==8 else 'revenue ')+body
                pid=f'{sid}:p{i+2}'
                db.execute('INSERT INTO passages VALUES(?,?,?,?,?)',(pid,sid,f'p{i+2}',text,sha256(text.encode()).hexdigest()))
                db.execute('INSERT INTO passage_search VALUES(?,?,?)',(pid,sid,text))
    async def call(actor,payload,schema):
        if actor=='lead':
            if payload['results']:
                return dict(action='stop',public_basis='done',synthesis='limited',open_issues=[],tasks=[])
            return dict(action='delegate',public_basis='check both originals',synthesis='',open_issues=[],tasks=[dict(
                task_id='t',question='compare',method_id='financial_quality',steps=['F2'],expectation='factual',
                source_ids=['S1','FUTURE'],search_terms=['revenue'])])
        reads={r['source']['id']:r for r in payload['read_results']}
        assert reads['S1']['coverage']['complete_document']
        assert any('necessary tail' in p['body'] for p in reads['S1']['items'])
        assert not reads['FUTURE']['coverage']['complete_document']
        return dict(obligation_id='t',execution='partial',summary='more reading needed',
            steps=[dict(step_id='F2',status='completed',finding='tail preserved',source_ids=['S1:p10'])],
            findings=[],unresolved=['remaining neighbour pages'],task_note=dict(changes=[],blockers=[],next_action='read more'))
    graph=compile_method_probe(snapshot=snapshot,call=call,record=lambda *a:None)
    asyncio.run(graph.ainvoke(dict(question='q',as_of='2025-06-01',catalog_ids=['S1','FUTURE'],results=[],waves=0)))
