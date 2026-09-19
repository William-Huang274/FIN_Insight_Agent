import asyncio
from copy import deepcopy
import pytest
from sec_agent.research_foundation.method_worker import (compile_method_worker,
    normalize_worker_receipts, WorkerAction)


def test_worker_consumes_actual_calculator_result_before_finishing():
    calls=[];events=[]
    async def call(actor,payload,schema):
        calls.append(actor)
        if not payload['tool_observations']:
            return dict(action='calculate',result=None,calculations=[dict(expression='a-b',operands={
                'a':dict(source_id='P1',literal='120',quote='Current 120 prior 100'),
                'b':dict(source_id='P1',literal='100',quote='Current 120 prior 100')},
                result_unit='USD million',rationale='Matched periods, current minus prior')])
        row=payload['tool_observations'][0]
        assert row['result']['value_decimal']=='20' and not row['result']['financial_semantics_verified']
        return dict(action='finish',calculations=[],result=dict(obligation_id='task',execution='completed',summary='Computed difference',
            steps=[dict(step_id='F2',status='completed',finding='read and compared',source_ids=['P1'])],
            findings=[dict(statement='Difference 20',kind='factual',source_ids=['P1'],calculation_refs=[row['result']['calculation_id']],
                public_basis='Actual calculation',assumptions=[],alternative='None needed for subtraction',would_change='Restatement')],
            unresolved=[],task_note=dict(changes=['compared'],blockers=[],next_action='lead')))
    payload=dict(instructions='Method',read_results=[dict(status='readable',source=dict(url='https://example.com'),items=[
        dict(id='P1',body='Current 120 prior 100',digest='a'*64,locator='paragraph1')])])
    graph=compile_method_worker(call=call,actor='task',payload=payload,record=lambda event,row:events.append((event,row)))
    result=asyncio.run(graph.ainvoke(dict(tool_rounds=0,observations=[])))
    assert result['tool_rounds']==1 and len(calls)==2 and len(events)==1


def finished():
    return WorkerAction.model_validate(dict(action='finish',result=dict(obligation_id='t',
        execution='completed',summary='Same analysis',steps=[dict(step_id='S2',status='completed',
        finding='Difference',source_ids=['P1'],execution_receipt_refs=['CALC::known','UNKNOWN'])],
        findings=[],unresolved=[],task_note=dict(changes=[],blockers=[],next_action='Review',
        execution_receipt_refs=['CALC::known','CALC::unbound','CALC::rejected','ACCESS::ok']))))


def test_receipt_compatibility_requires_actual_success_and_preserves_unknown_unbound():
    action=finished(); original=action.model_dump()
    observations=[{'status':'ok','result':{'calculation_id':ref}}
                  for ref in ['CALC::known','CALC::unbound']]
    observations.append({'status':'rejected','result':{'calculation_id':'CALC::rejected'}})
    normalized,records=normalize_worker_receipts(action,observations)
    assert action.model_dump()==original
    assert normalized.result.steps[0].calculation_refs==['CALC::known']
    assert normalized.result.steps[0].execution_receipt_refs==['UNKNOWN']
    assert normalized.result.task_note.execution_receipt_refs==['CALC::unbound','CALC::rejected','ACCESS::ok']
    assert normalized.result.summary==action.result.summary
    assert len(records)==1 and records[0]['basis']['financial_acceptance'] is False
    assert normalize_worker_receipts(normalized,observations)[1]==[]


@pytest.mark.parametrize('overrun',[False,True])
def test_completion_calculation_is_available_once_without_resetting_limit(overrun):
    budgets=[];events=[]
    async def call(actor,payload,schema):
        budgets.append(deepcopy(payload['calculation_budget']))
        if len(budgets)<=2 or overrun:
            return dict(action='calculate',calculations=[dict(expression='a-b',operands={
                'a':dict(source_id='P1',literal='120',quote='Current 120 prior 100'),
                'b':dict(source_id='P1',literal='100',quote='Current 120 prior 100')},
                result_unit='units',rationale='Comparable difference')])
        result=finished().model_dump()
        ref=payload['tool_observations'][-1]['result']['calculation_id']
        result['result']['steps'][0]['execution_receipt_refs']=[ref]
        result['result']['task_note']['execution_receipt_refs']=[ref]
        return result
    graph=compile_method_worker(call=call,actor='s',record=lambda e,v:events.append((e,v)),
        max_tool_rounds=1,completion_tool_rounds=1,runtime_submissions=True,
        payload={'instructions':'Self-check','read_results':[{'status':'readable','source':{'url':'https://example.test'},
        'items':[{'id':'P1','body':'Current 120 prior 100','digest':'a'*64,'locator':'p1'}]}]})
    if overrun:
        with pytest.raises(ValueError,match='worker_calculation_limit_unresolved'):
            asyncio.run(graph.ainvoke({'tool_rounds':0,'observations':[]}))
    else:
        state=asyncio.run(graph.ainvoke({'tool_rounds':0,'observations':[]}))
        assert state['tool_rounds']==2 and len(state['observations'])==2
        assert state['action']['result']['task_note']['execution_receipt_refs']==[]
        assert len(state['runtime_parsing'])==1
        assert any(e=='worker_runtime_compatibility_parse' for e,v in events)
    assert [b['used_rounds'] for b in budgets]==[0,1,2]
    assert [b['phase'] for b in budgets]==['analysis','completion','completion']
    assert all(b['total_round_limit']==2 for b in budgets)
