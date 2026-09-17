import asyncio
import pytest
from copy import deepcopy
from datetime import datetime, timezone

from langgraph.checkpoint.memory import InMemorySaver

from sec_agent.research_foundation.method_diagnostic_graph import compile_method_probe
from sec_agent.research_foundation.method_source_acquisition import MethodSourceAcquirer, SourceAcquisition
from test_method_diagnostic_graph import make_snapshot
from test_web_source_navigation import _reader, BRANCH
from test_external_sources import _run_scope


def request():
    return SourceAcquisition(acquisition_id='fetch-followup',query='company contract latest quarterly update',
        unresolved_question='Has delivery started?',why_existing_sources_insufficient='Only original contract available')


def test_acquisition_receipts_survive_failed_fetch_without_financial_evidence():
    reader,_,_=_reader(failure=True)
    acquire=MethodSourceAcquirer(reader=reader,branch_id=BRANCH,run_scope=_run_scope(BRANCH),record=lambda *a:None)
    result=asyncio.run(acquire(request(),_run_scope(BRANCH).research_as_of.date().isoformat()))
    assert result['reads']==[]
    assert [r['status'] for r in result['execution_receipts']]==['ok','tool_failure']
    assert all(not r['financial_evidence'] for r in result['execution_receipts'])


def test_search_date_cannot_admit_today_capture_to_historical_research():
    reader,_,_=_reader(published='2025-01-01')
    scope=_run_scope(BRANCH)
    acquire=MethodSourceAcquirer(reader=reader,branch_id=BRANCH,run_scope=scope,record=lambda *a:None)
    result=asyncio.run(acquire(request(),scope.research_as_of.date().isoformat()))
    row=result['reads'][0]
    assert row['source']['published_at']=='2025-01-01'
    assert row['source']['known_at']==datetime.now(timezone.utc).date().isoformat()
    assert row['status']=='ineligible_vintage_or_date' and not row['items']


def test_native_acquisition_checkpoint_resumes_into_worker_then_lead_without_refetch(tmp_path):
    calls=[]; acquisitions=[]
    captured={'status':'readable','source':{'id':'WEB::new','title':'Actual update','url':'https://example.com/update',
        'published_at':None,'known_at':'2025-06-01','vintage':'known_as_of','access_state':'readable','eligible':True},
        'items':[{'id':'PASSAGE::new','source_id':'WEB::new','body':'Delivery started.', 'digest':'b'*64,'locator':'chars0-17'}],
        'next_start':None,'coverage':{'complete_document':False,'unread_scope':'linked documents'}}
    async def acquire(req,as_of):
        acquisitions.append(req)
        return {'request':req.model_dump(),'reads':[deepcopy(captured)],'execution_receipts':[],'exclusions':[]}
    async def call(actor,payload,schema):
        calls.append(actor)
        if actor=='lead':
            if payload['results']:
                assert not payload['results'][0]['contract_errors']
                return dict(action='stop',public_basis='Used actual followup',synthesis='Delivery started, volume still unverified',open_issues=['volume'],tasks=[])
            if any(s['id']=='WEB::new' for s in payload['catalog']):
                return dict(action='delegate',public_basis='Read followup before updating',synthesis='',open_issues=[],tasks=[dict(
                    task_id='followup',question='Update contract stage',method_id='power_projects',steps=['P1'],expectation='factual',source_ids=['WEB::new'],search_terms=['Delivery'])])
            return dict(action='acquire',public_basis='Need update',synthesis='',open_issues=['delivery'],tasks=[],acquisitions=[request().model_dump()])
        assert 'finance' in payload['method_digests']
        assert not payload['read_results'][0]['coverage']['complete_document']
        return dict(obligation_id='followup',execution='completed',summary='Delivery started',steps=[dict(step_id='P1',status='completed',finding='delivery',source_ids=['PASSAGE::new'])],findings=[],unresolved=[],task_note=dict(changes=['updated stage'],blockers=[],next_action='lead'))
    snapshot=make_snapshot(tmp_path);saver=InMemorySaver();config={'configurable':{'thread_id':'resume'}}
    async def run():
        graph=compile_method_probe(snapshot=snapshot,call=call,record=lambda *a:None,checkpointer=saver,acquire=acquire,interrupt_after=['acquire'])
        state=await graph.ainvoke(dict(question='Contract update',as_of='2025-06-01',catalog_ids=['S1'],waves=0,results=[],decisions=[]),config)
        assert len(state['acquisitions'])==1 and len(acquisitions)==1
        graph=compile_method_probe(snapshot=snapshot,call=call,record=lambda *a:None,checkpointer=saver,acquire=acquire)
        final=await graph.ainvoke(None,config)
        assert final['terminal']=='bounded_stop' and len(acquisitions)==1
        assert 'WEB::new' not in {s['id'] for s in snapshot.catalog('2025-06-01')}
    asyncio.run(run())
    assert calls==['lead','lead','followup','lead']


def test_repeated_search_is_stopped_without_second_provider_call(tmp_path):
    requests=[]
    async def acquire(req,as_of):
        requests.append(req)
        return dict(request=req.model_dump(),reads=[],execution_receipts=[],exclusions=[])
    async def call(actor,payload,schema):
        return dict(action='acquire',public_basis='retry same search',synthesis='',open_issues=['source'],tasks=[],acquisitions=[request().model_dump()])
    graph=compile_method_probe(snapshot=make_snapshot(tmp_path),call=call,record=lambda *a:None,acquire=acquire)
    result=asyncio.run(graph.ainvoke(dict(question='q',as_of='2025-06-01',catalog_ids=['S1'],waves=0,results=[],decisions=[])))
    assert len(requests)==1 and result['terminal']=='repeated_acquisition_no_progress'


def test_section_search_reaches_original_after_opening_prefix_without_refetch():
    text='Opening material. '*3000+'\nImportantRevenueNote: actual contract delivery began April.\n'+'Other material. '*1500
    reader,fetcher,_=_reader(text=text)
    scope=_run_scope(BRANCH);events=[]
    acquire=MethodSourceAcquirer(reader=reader,branch_id=BRANCH,run_scope=scope,record=lambda event,value:events.append((event,value)))
    req=request().model_copy(update={'section_queries':['ImportantRevenueNote']})
    asyncio.run(acquire(req,scope.research_as_of.date().isoformat()))
    searches=[r for event,r in events if event=='source_result' and r['operation']=='search' and any(p.get('result_state')=='source_bound_passage' for p in r['items'])]
    assert searches and any('actual contract delivery began April' in p['passage'] for p in searches[0]['items'])
    assert searches[0]['execution_receipt']['operation']=='search'
    assert len(fetcher.calls)==1


@pytest.mark.parametrize('status,expected_calls',[('zero_results',2),('tool_failure',1)])
def test_date_filter_relaxation_is_recorded_but_transport_failure_is_not_retried(status,expected_calls):
    from sec_agent.research_foundation.source_document_navigation import SourceDocumentResult,SourceExecutionReceipt
    calls=[]
    async def reader(*,request,**kwargs):
        calls.append(request)
        return SourceDocumentResult(operation='search',items=(),next_offset=None,total_matches=0,
            notice='fixture',source_snapshot_sha256='a'*64,execution_receipt=SourceExecutionReceipt(
                receipt_id='EXEC::'+str(len(calls))*64,operation='search',status=status,provider_receipt_digest='a'*64))
    scope=_run_scope(BRANCH)
    acquire=MethodSourceAcquirer(reader=reader,branch_id=BRANCH,run_scope=scope,record=lambda *a:None)
    req=SourceAcquisition.model_validate({**request().model_dump(),'start_published_date':'2025-01-01','include_domains':['example.com']})
    result=asyncio.run(acquire(req,scope.research_as_of.date().isoformat()))
    assert len(calls)==expected_calls
    if status=='zero_results':
        assert calls[1].start_published_date is None and calls[1].include_domains==('example.com',)
        assert result['runtime_adjustments'][0]['origin']=='runtime_retrieval_adjustment'
        assert not result['runtime_adjustments'][0]['historical_evidence_policy_relaxed']
    else:
        assert not result['runtime_adjustments']
