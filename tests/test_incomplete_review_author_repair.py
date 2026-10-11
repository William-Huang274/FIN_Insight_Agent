"""Author repair may precede review completion; it never certifies the case."""
import asyncio
from copy import deepcopy

import pytest
from langchain_core.messages import HumanMessage, messages_to_dict
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.memory import InMemorySaver

from sec_agent.agent_runtime.lead_issue_decision import LeadIssueDecision, decision_errors
from sec_agent.agent_runtime.research_session import build_research_session_graph, current_task_artifacts
from sec_agent.agent_runtime.review_recovery import review_after_author_changes, review_recovery_handoff
from sec_agent.agent_runtime.review_check_store import merge_checks, restore_checks, restore_findings
from sec_agent.agent_runtime.workpaper_changes import confirmation_context
from test_review_inspection_recovery import artifact_fixture, inspected, incomplete_review
from test_research_session import _phases


def partial(artifacts, question):
    record = incomplete_review(artifacts, question)
    for role in ('counter', 'verifier'):
        record[role] = {'status': 'incomplete_no_submission', 'review': None, 'model_calls': 24,
            'recorded_findings': {'local': {'paper_id': 'P01', 'finding_id': 'local', 'severity': 'material',
                'problematic_quote': artifacts.read_paper('P01')['thesis'],
                'diagnosis': 'Synthetic local problem needing author attention.',
                'requested_change': 'Inspect the original source and correct the local statement.'}},
            'recovery_state': {'messages': messages_to_dict([HumanMessage(content='Saved private source reads.')]),
                'recorded_inspections': merge_checks({}, inspected(artifacts)['inspection_checks'])}}
        record[role]['recovery_state']['recorded_findings'] = deepcopy(record[role]['recorded_findings'])
    return record


def repair_decision(feedback):
    return {'action': 'repair', 'summary': 'Repair confirmed local issues before completing independent case review.',
        'dispositions': [{'paper_id': pid, 'finding_id': f['finding_id'], 'disposition': 'repair',
            'rationale': 'This source-bound synthetic local issue needs an author revision.',
            'requested_change': 'Correct the local claim after inspecting the original source.',
            'expected_progress': 'Submit a revised source-bound statement for independent confirmation.'}
            for pid, rows in feedback.items() for f in rows]}


def test_author_revision_invalidates_changed_checks_but_preserves_other_work_and_usage():
    before = artifact_fixture()
    previous = partial(before, 'Same original question')
    original = deepcopy(previous)
    paper = deepcopy(before.read_paper('P01'))
    paper['thesis'] += ' Revised synthetic explanation.'
    revisions = {'P01': {'status': 'revision_submitted', 'workpaper': paper, 'finding_responses': []}}
    current = before.with_revisions(revisions)
    feedback = review_recovery_handoff(previous, before, 'Same original question')['feedback']
    context = confirmation_context(before, revisions, feedback)
    resumed = review_after_author_changes(previous, before, current, 'Same original question', context)
    assert previous == original
    assert resumed['scope_digest'] != previous['scope_digest']
    for role in ('counter', 'verifier'):
        row = resumed[role]
        assert row['model_calls'] == 24 and row['status'] == 'incomplete_no_submission'
        saved = row['recovery_state']
        assert {c['paper_id'] for c in restore_checks(saved).values()} == {'P02'}
        assert not restore_findings(saved, {})
        assert 'Saved private source reads.' in str(saved['messages'])
        assert 'findings_to_confirm' in str(saved['messages'][-1])
    with pytest.raises(ValueError, match='original_incomplete_scope'):
        review_after_author_changes(previous, before, current, 'Changed question', context)


def test_native_parent_routes_explicit_repair_without_accepting_incomplete_review():
    async def exercise():
        phases, _, _ = _phases()
        seen = []
        async def review(state, config):
            seen.append('review')
            return partial(current_task_artifacts(state), state['question'])
        async def triage(state, config):
            seen.append('lead')
            handoff = review_recovery_handoff(state['case_review'], current_task_artifacts(state), state['question'])
            decision = repair_decision(handoff['feedback'])
            assert not decision_errors(LeadIssueDecision.model_validate(decision), handoff['feedback'],
                {'P01', 'P02'}, incomplete_reviewers=['counter', 'verifier'])
            return decision
        async def converge(state, config):
            seen.append('authors_then_review')
            assert state['review_repair_decision']['action'] == 'repair'
            assert state['case_review']['phase'] == 'case_review_incomplete'
            assert state['feedback']['P01']
            return {'phase': 'research_convergence_needs_attention', 'stop_reason': 'fixture_stops_before_acceptance'}
        phases.update(review=RunnableLambda(review), triage_review=RunnableLambda(triage), converge=RunnableLambda(converge))
        app = build_research_session_graph(**phases).compile(checkpointer=InMemorySaver())
        result = await app.ainvoke({'question': 'Inspect and repair this original synthetic research question.'},
            {'configurable': {'thread_id': 'partial-author-repair'}, 'recursion_limit': 100})
        assert seen == ['review', 'lead', 'authors_then_review']
        assert not result.get('report')
        assert result['case_review']['phase'] == 'case_review_incomplete'
    asyncio.run(exercise())


def test_saved_lead_repair_executes_only_owner_then_requires_independent_review():
    from sec_agent.agent_runtime.research_convergence import build_research_convergence_graph
    async def exercise():
        artifacts = artifact_fixture()
        record = partial(artifacts, 'Same original question')
        feedback = review_recovery_handoff(record, artifacts, 'Same original question')['feedback']
        seen = []
        async def author(pid, state, config):
            seen.append(pid)
            revised = deepcopy(artifacts.read_paper(pid))
            revised['thesis'] += ' Revised by the original author.'
            return {'status': 'revision_submitted', 'workpaper': revised,
                'finding_responses': [{'finding_id': f['finding_id'], 'disposition': 'corrected',
                    'explanation': 'Author claims correction; independent verification still required.'}
                    for f in state['pending_feedback'][pid]]}
        async def confirm(current, context, config):
            seen.append('independent_review')
            assert set(context['findings_to_confirm']) == {'P01'}
            assert current.read_paper('P01') != artifacts.read_paper('P01')
            return {'phase': 'case_review_incomplete',
                'scope_digest': __import__('sec_agent.agent_runtime.case_review_agent', fromlist=['case_review_scope_digest']).case_review_scope_digest(current, 'Same original question')}
        def forbidden(*args, **kwargs):
            raise AssertionError('No repeated Lead or premature synthesis is permitted')
        graph = build_research_convergence_graph(artifacts=artifacts, question='Same original question',
            feedback=feedback, research_review_context={}, make_agent=forbidden, hierarchical=True,
            run_author=author, review_revisions=confirm, initial_lead_decision=repair_decision(feedback)).compile()
        result = await graph.ainvoke({})
        assert seen == ['P01', 'independent_review']
        assert result['stop_reason'] == 'independent_confirmation_incomplete'
        assert not result.get('report')
    asyncio.run(exercise())
