import asyncio
from copy import deepcopy
from uuid import uuid4
import pytest
from langgraph.types import Command
from sec_agent.agent_runtime.manual_review import ManualReview, apply_manual_review
from test_dell_report_session import setup_session
from test_dell_case_review_agent import artifacts


def test_manual_completion_retains_checkpoint_roles_and_accepts_next_question(artifacts):
    async def run():
        graph, models, initial, ref = setup_session(artifacts)
        config = {'configurable': {'thread_id': str(uuid4())}}
        opened = await graph.ainvoke({'open': True}, config)
        baseline = await graph.aget_state(config)
        decision = {'base_version': 1, 'report_markdown': opened['report']['narrative_markdown']+' Only an observation.',
            'paper_edits': [{'paper_id': 'P01', 'body': 'Human corrected working paper; not new source evidence.'}],
            'reason': 'Remove unsupported causal wording', 'confirmed': True}
        result = await graph.ainvoke(Command(resume={'action':'manual_complete','manual_review':decision}), config)
        assert result['phase'] == 'human_completed' and result['report_version'] == 2
        assert result['__interrupt__'] and not any(m.contexts for m in models.values())
        assert result['human_edits'][0]['papers'][0]['actor'] == artifacts.catalog()['papers'][0]['branch_id']
        assert (await graph.aget_state(baseline.config)).values['report'] == initial['report']
        assert result['report_review'] == initial['report_review']
        decision.update(base_version=2,report_markdown=decision['report_markdown']+' Revised scope.')
        result = await graph.ainvoke(Command(resume={'action':'manual_complete','manual_review':decision}), config)
        assert len(result['human_edits']) == 2 and result['human_edits'][1]['papers'] == []
    asyncio.run(run())


@pytest.mark.parametrize('failure',['stale','unknown_source','data_problem','no_confirmation','unknown_paper'])
def test_manual_completion_does_not_bypass_source_or_data_failures(artifacts,failure):
    _,_,initial,_=setup_session(artifacts)
    state={**deepcopy(initial),'report_version':1}
    payload={'base_version':1,'report_markdown':state['report']['narrative_markdown']+' Correction.',
        'reason':'Test reason','confirmed':True}
    if failure=='stale': payload['base_version']=2
    if failure=='unknown_source': payload['report_markdown']='Invented [P01:UNKNOWN]'
    if failure=='data_problem': state['report_review']['unresolved_data_requests']=['Missing receipt']
    if failure=='no_confirmation': payload['confirmed']=False
    if failure=='unknown_paper': payload['paper_edits']=[{'paper_id':'P99','body':'Other case'}]
    with pytest.raises(ValueError):apply_manual_review(state,ManualReview(**payload),artifacts)
    assert state['report']==initial['report']
