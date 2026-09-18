import asyncio

from sec_agent.research_foundation.method_execution import ResearchObligation, method_payload
from sec_agent.research_foundation.method_worker import compile_method_worker


def test_public_observation_method_reaches_native_worker_with_required_steps():
    obligation=ResearchObligation(obligation_id='survey-probe',parent_question='What can user observations support?',
        question='Check original results and reporting; develop testable hypotheses',business_scope='Software users',
        as_of='2026-09-18',method_ids=['public_observations'],required_steps=['O1','O2','O3','O4','O5'],
        expectation='exploratory',materiality='core',source_requirements=['Original question and method'])
    payload={**method_payload(obligation),'read_results':[]}
    async def call(actor,task,schema):
        assert set(task['method_digests'])=={'finance','public_observations'}
        method=next(m for m in task['methods'] if m['method_id']=='public_observations')
        assert all(f'步骤 O{i}：' in method['content'] for i in range(1,6))
        assert '总样本不自动是每题分母' in method['content']
        assert '余数' in method['content'] and '同一调查' in method['content']
        assert task['remaining_calculation_rounds']==1
        return {'action':'finish','result':{'obligation_id':'survey-probe','execution':'partial','summary':'No source supplied in fixture',
            'steps':[{'step_id':s,'status':'blocked','finding':'Need original material','source_ids':[]} for s in obligation.required_steps],
            'findings':[],'unresolved':['Await sources'],'task_note':{'changes':[],'blockers':['Await sources'],'next_action':'Read originals'}}}
    graph=compile_method_worker(call=call,actor='observer',payload=payload,record=lambda *args:None,max_tool_rounds=1,runtime_submissions=True)
    result=asyncio.run(graph.ainvoke({'observations':[],'tool_rounds':0}))
    assert result['action']['result']['execution']=='partial'
