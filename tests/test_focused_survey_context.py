import asyncio

from sec_agent.research_foundation.method_execution import ResearchObligation, method_payload
from sec_agent.research_foundation.method_worker import compile_method_worker


def obligation():
    return ResearchObligation(obligation_id='survey', parent_question='Adoption evidence',
        question='Assess this survey', business_scope='Survey analysis', as_of='2026-09-19',
        method_ids=['survey_analysis'], required_steps=['S1','S2','S3','S4'],
        expectation='conditional', materiality='core', source_requirements=['Original survey'])


def test_clean_worker_receives_only_selected_method_and_actual_tools():
    task=method_payload(obligation(),shared_method_ids=())
    task.update(read_results=[],capabilities=['source_bound_calculator'])
    async def call(actor,payload,schema):
        assert set(payload['method_digests'])=={'survey_analysis'}
        assert '现金流' not in payload['methods'][0]['content']
        assert 'remaining_calculation_rounds' in payload
        assert 'original_workpaper' not in payload and 'review_issues' not in payload
        return {'action':'finish','result':{'obligation_id':'survey','execution':'partial',
            'summary':'No sources supplied in fixture','steps':[{'step_id':'S1','status':'blocked',
            'finding':'Await material','source_ids':[]}], 'findings':[], 'unresolved':['No sources'],
            'task_note':{'changes':[],'blockers':['No sources'],'next_action':'Obtain material'}}}
    state=asyncio.run(compile_method_worker(call=call,actor='survey',payload=task,
        record=lambda *args:None,runtime_submissions=True).ainvoke({'observations':[],'tool_rounds':0}))
    assert state['action']['result']['execution']=='partial'


def test_legacy_method_selection_keeps_finance_and_explicit_selection_hashes_content():
    assert set(method_payload(obligation())['method_digests'])=={'finance','survey_analysis'}
    assert set(method_payload(obligation(),shared_method_ids=())['method_digests'])=={'survey_analysis'}
