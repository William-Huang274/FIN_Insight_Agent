"""The updated financial method must reach the actual qualification worker."""
import asyncio

from sec_agent.research_foundation.method_execution import ResearchObligation, method_payload
from sec_agent.research_foundation.method_worker import compile_method_worker


def test_financial_quality_delivery_obligations_reach_worker_without_case_answers():
    obligation = ResearchObligation(
        obligation_id='financial-boundaries', parent_question='Assess financial disclosure',
        question='Interpret dated status and monetary reconciliation', business_scope='Financial disclosure',
        as_of='2026-09-19', method_ids=['financial_quality'], required_steps=['F1', 'F4', 'F6'],
        expectation='conditional', materiality='core', source_requirements=['Issuer original'],
    )
    payload = {**method_payload(obligation), 'read_results': []}

    async def call(actor, task, schema):
        method = next(m for m in task['methods'] if m['method_id'] == 'financial_quality')
        assert '状态一直持续到研究截止日' in method['content']
        assert '起点金额、每项调整金额、终点金额' in method['content']
        assert '某一组成项' in method['content']
        assert all(name not in method['content'] for name in ('AMD', 'Talen', 'Stack Overflow'))
        assert set(task['method_digests']) == {'finance', 'financial_quality'}
        return {'action': 'finish', 'result': {
            'obligation_id': obligation.obligation_id, 'execution': 'partial',
            'summary': 'Fixture intentionally supplies no issuer source.',
            'steps': [{'step_id': s, 'status': 'blocked', 'finding': 'Await source', 'source_ids': []}
                      for s in obligation.required_steps],
            'findings': [], 'unresolved': ['No source in fixture'],
            'task_note': {'changes': [], 'blockers': ['Await source'], 'next_action': 'Read issuer original'},
        }}

    worker = compile_method_worker(call=call, actor='analyst', payload=payload,
                                   record=lambda *args: None, runtime_submissions=True)
    result = asyncio.run(worker.ainvoke({'observations': [], 'tool_rounds': 0}))
    assert result['action']['result']['execution'] == 'partial'
