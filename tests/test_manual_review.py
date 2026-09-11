import asyncio
import json
from copy import deepcopy
from uuid import uuid4
import pytest
from langgraph.types import Command
from sec_agent.agent_runtime.manual_review import ManualReview, apply_manual_review
from test_dell_report_session import setup_session
from test_dell_case_review_agent import artifacts


def test_followup_tool_reads_human_corrected_paper_not_original(artifacts):
    from test_dell_case_review_agent import call
    async def run():
        graph, models, initial, ref = setup_session(artifacts, quick=True)
        config = {'configurable': {'thread_id': str(uuid4())}}
        await graph.ainvoke({'open': True}, config)
        correction = 'Current human correction: retain observation, withdraw causal attribution.'
        await graph.ainvoke(Command(resume={'action': 'manual_complete', 'manual_review': {
            'base_version': 1, 'report_markdown': initial['report']['narrative_markdown'] + correction,
            'paper_edits': [{'paper_id': 'P01', 'body': correction}],
            'reason': 'User withdrew causal attribution', 'confirmed': True}}), config)
        models['quick_writer'].replies = [
            [call('read_current_workpaper', {'paper_id': 'P01'}, 'read-current')],
            [call('submit_case_answer', {'answer_markdown': f'Observation only. [{ref}]'}, 'answer-current')]]
        await graph.ainvoke(Command(resume={'action': 'ask', 'answer_mode': 'quick',
            'message': 'Read the current working paper before answering.'}), config)
        messages = models['quick_writer'].contexts[-1]
        tool_message = next(m for m in messages if getattr(m, 'tool_call_id', None) == 'read-current')
        result = json.loads(tool_message.content)
        assert result['narrative_markdown'] == correction
        assert result['human_editorial_revision']['number'] == 1
        assert artifacts.read_paper('P01')['narrative_markdown'] != correction
    asyncio.run(run())


def test_two_roles_in_one_branch_keep_distinct_manual_edit_ownership():
    from sec_agent.agent_runtime.manual_review import paper_owner_role
    state = {'case_papers': [{'agent_id': 'a', 'task': {'task_id': 'cash'}},
                            {'agent_id': 'b', 'task': {'task_id': 'merger'}}],
             'research_tasks': [{'task_id': 'cash', 'owner_role': 'financial-analyst'},
                                {'task_id': 'merger', 'owner_role': 'merger-analyst'}]}
    assert paper_owner_role(state, {'author': 'a', 'branch_id': 'Q1'}) == 'financial-analyst'
    assert paper_owner_role(state, {'author': 'b', 'branch_id': 'Q1'}) == 'merger-analyst'


def test_caption_only_edit_preserves_financial_chart_and_records_history(artifacts):
    _, _, initial, _ = setup_session(artifacts)
    state = {**deepcopy(initial), 'report_version': 1}
    state['report']['charts'] = [{'title': 'Cash flows', 'interpretation': 'All original facts.',
        'unit': 'USD', 'scale_divisor': 1000000, 'points': [{'value': 71611000000, 'source_id': 'saved'}]}]
    baseline = deepcopy(state)
    decision = ManualReview(base_version=1, report_markdown=state['report']['narrative_markdown'],
        reason='Distinguish calculated FCF from direct operating cash flow.', confirmed=True,
        chart_edits=[{'chart_index': 0, 'interpretation': 'FCF is calculated as CFO less capital expenditure.'}])
    result = apply_manual_review(state, decision, artifacts)
    assert result['phase'] == 'human_completed' and result['report_version'] == 2
    assert result['human_edits'][-1]['charts'][0]['before'] == 'All original facts.'
    assert result['human_edits'][-1]['papers'] == []
    for key in ('unit', 'scale_divisor', 'points'):
        assert result['report']['charts'][0][key] == baseline['report']['charts'][0][key]
    assert state == baseline
    with pytest.raises(ValueError):
        apply_manual_review(state, decision.model_copy(update={'chart_edits': [
            decision.chart_edits[0].model_copy(update={'chart_index': 1})]}), artifacts)
    with pytest.raises(ValueError):
        ManualReview(**{**decision.model_dump(), 'chart_edits': [
            {'chart_index': 0, 'interpretation': 'Overwrite', 'points': []}]})


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


@pytest.mark.parametrize('failure',['stale','unknown_source','data_problem','no_confirmation','unknown_paper','unknown_paper_source'])
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
    if failure=='unknown_paper_source': payload['paper_edits']=[{'paper_id':'P01','body':'Unsupported [P01:UNKNOWN]'}]
    with pytest.raises(ValueError):apply_manual_review(state,ManualReview(**payload),artifacts)
    assert state['report']==initial['report']


def test_human_view_preserves_sources_and_later_consuming_revision(artifacts):
    original = artifacts.read_paper('P01')
    history = [{'number': 1, 'reason': 'Withdraw attribution', 'papers': [
        {'paper_id': 'P01', 'after': 'Observation only.'}]}]
    view = artifacts.with_human_edits(history)
    assert view.read_paper('P01')['claims'] == original['claims']
    assert view.read_paper('P01', 'sources') == artifacts.read_paper('P01', 'sources')
    author_revision = view.read_paper('P01')
    author_revision['narrative_markdown'] = 'Observation only. Added source-bound detail.'
    revised = view.with_revisions({'P01': {'status': 'revision_submitted', 'workpaper': author_revision}})
    assert revised.with_human_edits(history).read_paper('P01') == author_revision
    history.append({'number': 2, 'reason': 'New user scope', 'papers': [
        {'paper_id': 'P01', 'after': 'Only the latest user scope.'}]})
    assert revised.with_human_edits(history).read_paper('P01')['narrative_markdown'] == 'Only the latest user scope.'
    assert artifacts.read_paper('P01') == original
