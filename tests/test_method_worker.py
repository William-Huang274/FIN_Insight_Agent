import asyncio
from sec_agent.research_foundation.method_worker import compile_method_worker


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
