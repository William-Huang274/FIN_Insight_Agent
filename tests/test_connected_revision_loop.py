"""Native identity, actual changes and independent version-bound closure."""
import asyncio
from copy import deepcopy
import json

import pytest
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

from sec_agent.agent_runtime.case_review_agent import CaseReview, case_review_scope_digest, validate_finding_confirmation
from sec_agent.agent_runtime.research_convergence import build_research_convergence_graph
from sec_agent.agent_runtime.workpaper_changes import workpaper_changes, confirmation_context
from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticDependencies, build_specialist_agentic_state_graph
from sec_agent.agent_runtime.workpaper_review_graph import validate_workpaper_state
from sec_agent.agent_runtime.task_outcome import task_outcome
from test_specialist_graph import _input, _ToolPorts, _evidence_action, _finance_action
from test_specialist_tool_batch import _batch
from test_workpaper_partial_edits import paper, edit_action, text_edit
from test_research_convergence import artifact_fixture


def submitted_original():
    ports = _ToolPorts()
    requests = []
    def turn(request):
        requests.append(request)
        return _batch(request, [_evidence_action()({}), _finance_action()({})] if len(requests) == 1 else [paper()])
    return build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=turn, evidence_tool=ports.evidence, finance_tool=ports.finance)).compile().invoke(_input())


def test_original_author_continues_and_records_actual_change_without_note_claim(tmp_path):
    original = submitted_original()
    assert original['phase'] == 'specialist_submission_accepted'
    saved = validate_workpaper_state(original)
    seen = []
    feedback = [{'finding_id': 'verifier:F1', 'diagnosis': 'Inspect the actual fixture body.'}]
    def turn(request):
        seen.append(request)
        assert request['task_context']['revision_feedback'] == feedback
        candidate = request['submission_to_repair']['candidate']
        answers = [{'finding_id': 'verifier:F1', 'disposition': 'corrected',
                    'explanation': 'Changed the precise fixture fragment; independent verification still required.'}]
        return _batch(request, [edit_action(candidate, [text_edit(),
            {'path': '/task_note/finding_responses', 'old_value': [], 'new_value': answers}]).model_dump(mode='json')])
    builder = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=turn, evidence_tool=_ToolPorts().evidence, finance_tool=_ToolPorts().finance,
        allow_workpaper_field_edits=True), recovery_state=saved, revision_feedback=feedback)
    async def resume():
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        async with AsyncSqliteSaver.from_conn_string(str(tmp_path / 'author.sqlite')) as saver:
            graph = builder.compile(checkpointer=saver)
            config = {'configurable': {'thread_id': 'original-author'}}
            result = await graph.ainvoke(_input(), config)
            assert (await graph.aget_state(config)).values['notebook'] == result['notebook']
            return result
    result = asyncio.run(resume())
    assert result['phase'] == 'specialist_submission_accepted' and len(seen) == 1
    assert result['agent_id'] == original['agent_id'] and result['task'] == original['task']
    assert result['notebook']['model_turn_records'][:-1] == original['notebook']['model_turn_records']
    assert result['notebook']['observations'] == original['notebook']['observations']
    assert result['final_submission']['task_note']['changes'] == original['final_submission']['task_note']['changes']
    change = task_outcome(result)['runtime_changes'][-1]
    assert '/narrative_markdown' in [r['path'] for r in change['locations']]
    assert change['semantic_status'] == 'not_independently_verified'
    assert original['final_submission']['narrative_markdown'] != result['final_submission']['narrative_markdown']


def review_result(artifacts, feedback, *, stale=False, open_issue=False):
    records = {}
    for role in ('counter', 'verifier'):
        findings = [{'finding_id': 'again', 'paper_id': 'P01', 'severity': 'material',
            'problematic_quote': artifacts.read_paper('P01')['thesis'],
            'diagnosis': 'Remaining fixture inconsistency requires correction.',
            'requested_change': 'Correct the still inconsistent fixture prose.'}] if open_issue else []
        records[role] = {'status': 'review_submitted', 'review': {
            'summary': 'Synthetic version confirmation, not financial quality qualification.',
            'assessments': [{'paper_id': p['paper_id'], 'assessment': 'Inspected current fixture with its source bindings.'} for p in artifacts.catalog()['papers']],
            'findings': findings, 'unresolved_data_requests': [],
            'finding_checks': [{'finding_id': f['finding_id'], 'status': 'still_open' if open_issue else 'resolved',
                'reason': 'Inspected actual updated fixture and related source context.',
                'related_finding_ids': ['again'] if open_issue else []}
                for rows in feedback.values() for f in rows]}}
    return {**records, 'phase': 'case_review_ready_for_convergence',
        'scope_digest': 'stale' if stale else case_review_scope_digest(artifacts, 'fixture question')}


@pytest.mark.parametrize('failure', ['missing_check', 'missing_current_finding', 'unresolved_hidden'])
def test_confirmation_cannot_silently_omit_remaining_work(failure):
    artifacts = artifact_fixture()
    feedback = {'P01': [{'finding_id': 'verifier:F1'}]}
    context = confirmation_context(artifacts, {}, feedback)
    value = review_result(artifacts, feedback)['verifier']['review']
    if failure == 'missing_check': value['finding_checks'] = []
    elif failure == 'missing_current_finding': value['finding_checks'][0]['status'] = 'still_open'
    else: value['finding_checks'][0]['status'] = 'unresolved'
    with pytest.raises(ValueError):
        validate_finding_confirmation(CaseReview.model_validate(value), context, artifacts)


@pytest.mark.parametrize('stale,repeat', [(False, False), (True, False), (False, True)])
def test_connected_graph_confirms_before_lead_and_stops_repeated_failure(stale, repeat):
    artifacts, sequence, inputs = artifact_fixture(), [], []
    class Child(TypedDict, total=False):
        messages: list
        output: dict
    def make_agent(role, current, **kwargs):
        def execute(state):
            sequence.append(role)
            inputs.append((role, json.loads(state['messages'][-1].content)))
            if role == 'lead_decision':
                dispositions = [{'finding_id': f['finding_id'], 'paper_id': pid, 'disposition': 'repair',
                    'rationale': 'Fixture Lead assigns a bounded correction.', 'requested_change': 'Correct fixture.', 'expected_progress': 'Updated fixture.'}
                    for pid, rows in (kwargs['feedback'] or {}).items() for f in rows]
                output = {'action': 'repair' if dispositions else 'synthesize', 'dispositions': dispositions}
            elif role.endswith('verifier'):
                output = {'summary': 'Fixture stage review after workpaper confirmation.', 'findings': [], 'unresolved_data_requests': []}
            else: output = {'title': 'Fixture', 'narrative_markdown': 'Fixture synthesis', 'citations': {}, 'charts': []}
            return {'output': output}
        graph = StateGraph(Child); graph.add_node('model', execute); graph.add_edge(START, 'model'); graph.add_edge('model', END)
        return graph.compile()
    async def author(pid, state, config):
        sequence.append('original_author')
        current = artifacts.with_revisions(state.get('revisions', {}))
        value = current.read_paper(pid); value['narrative_markdown'] += '\nActual amendment.'
        return {'status': 'revision_submitted', 'workpaper': value, 'sources': {},
            'finding_responses': [{'finding_id': f['finding_id'], 'disposition': 'corrected', 'explanation': 'A fixture assertion requiring independent review.'}
                for f in state['pending_feedback'][pid]]}
    async def confirm(current, context, config):
        sequence.append('independent_confirmation')
        assert context['changes']['P01']['locations']
        return review_result(current, context['findings_to_confirm'], stale=stale, open_issue=repeat)
    from langgraph.checkpoint.memory import InMemorySaver
    graph = build_research_convergence_graph(artifacts=artifacts, question='fixture question',
        feedback={'P01': [{'finding_id': 'verifier:F1'}]}, research_review_context={}, make_agent=make_agent,
        run_author=author, review_revisions=confirm, hierarchical=True, max_correction_rounds=1).compile(checkpointer=InMemorySaver())
    result = asyncio.run(graph.ainvoke({}, {'recursion_limit': 100, 'configurable': {'thread_id': 'connected-loop'}}))
    assert sequence[:3] == ['lead_decision', 'original_author', 'independent_confirmation']
    if stale:
        assert result['stop_reason'] == 'independent_confirmation_stale_version' and 'synthesis' not in sequence
    elif repeat:
        assert result['stop_reason'] == 'material_findings_remain_after_targeted_correction'
        assert sequence.count('original_author') == 2 and 'synthesis' not in sequence
    else:
        assert sequence[3:5] == ['lead_decision', 'synthesis']
        assert result['phase'] == 'case_report_ready_for_human_review'
        assert inputs[1][1]['independent_current_workpaper_confirmation']['context']['author_responses']


def test_change_navigation_preserves_offsets_without_copying_source_or_claiming_closure():
    before = {'claims': [], 'narrative_markdown': 'Alpha unchanged. Old. Omega unchanged.'}
    after = {**before, 'narrative_markdown': 'Alpha unchanged. New explanation. Omega unchanged.'}
    result = workpaper_changes(before, after)
    assert result['baseline_digest'] != result['current_digest']
    assert result['locations'][0]['path'] == '/narrative_markdown'
    assert 'Alpha unchanged' not in json.dumps(result)


def test_private_history_restore_requires_exact_original_actor_and_receipt(tmp_path):
    from types import SimpleNamespace
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
    from sec_agent.agent_runtime.author_revision import restore_author_history
    state = {'agent_id': 'original', 'notebook': {'model_turn_records': [{
        'runtime_receipt': {'actor': 'original', 'request_digest': 'bound'},
        'action': {'tool_calls': [{'id': 'last-call', 'name': 'SubmitWorkpaperAction', 'args': {}}]}}]}}
    messages = [SystemMessage(content='original instructions'), HumanMessage(content='original task')]
    raw = AIMessage(content='', tool_calls=[{'id': 'last-call', 'name': 'SubmitWorkpaperAction', 'args': {}}])
    event = {'actor': 'other', 'request_digest': 'bound', 'messages': [m.model_dump(mode='json') for m in messages],
        'raw_response': raw.model_dump(mode='json')}
    path = tmp_path / 'private.jsonl'; path.write_text(json.dumps(event)+'\n', encoding='utf-8')
    adapter = SimpleNamespace(_agentic_history={})
    with pytest.raises(ValueError, match='private_history_unavailable'):
        restore_author_history(adapter, state, [path])
    assert adapter._agentic_history == {}
    event['actor'] = 'original'
    path.write_text(json.dumps(event)+'\n', encoding='utf-8')
    restore_author_history(adapter, state, [path])
    assert adapter._agentic_history['original'] == [*messages, raw]


def test_native_author_bridge_keeps_second_paper_aliases_and_source_identity():
    from sec_agent.agent_runtime.author_revision import native_revision_view, current_author_state, author_feedback
    artifacts = artifact_fixture()
    saved = current_author_state(artifacts, 'P02', {})
    ref = next(iter(artifacts.read_paper('P02', 'sources')))
    feedback = [{'finding_id': 'verifier:F1', 'source_checks': [{'source_id': ref, 'quote': 'fixture'}]}]
    mapped = author_feedback(feedback, artifacts)
    assert mapped[0]['source_checks'][0]['source_id'] != ref
    assert feedback[0]['source_checks'][0]['source_id'] == ref
    saved['final_submission']['task_note'] = {'summary': 'Synthetic response, not a quality assertion.', 'coverage': [], 'issues': [], 'changes': '',
        'finding_responses': [{'finding_id': 'verifier:F1', 'disposition': 'disagreed_with_sources',
            'explanation': 'No fixture content modification is justified by these synthetic observations.'}]}
    revision = native_revision_view(saved, artifacts, 'P02', mapped)
    assert revision['workpaper']['claims'] == artifacts.read_paper('P02')['claims']
    assert revision['sources'] == {} and revision['author_identity']['agent_id'] == saved['agent_id']
    assert artifacts.with_revisions({'P02': revision}).source_item(ref) == artifacts.source_item(ref)
