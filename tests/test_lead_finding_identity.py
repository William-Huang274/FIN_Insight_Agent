import asyncio
from copy import deepcopy
import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from sec_agent.agent_runtime.lead_issue_decision import (
    LeadIssueDecision, decision_errors, resolve_disposition_ids,
)
from sec_agent.agent_runtime.report_synthesis_agent import build_case_output_agent
from test_case_review_agent import artifacts, call
from test_report_synthesis_agent import NativeFixtureModel


def feedback(role='verifier', round_index=0, original='F1', paper='P01'):
    return {paper: [{'finding_id': f'confirmation:{round_index}:{role}:{original}',
        'original_finding_id': original, 'reviewer': role, 'severity': 'material'}]}


def proposal(identifier='F1'):
    return LeadIssueDecision(summary='Preserve the research and correct the specific current issue.', action='repair',
        dispositions=[dict(paper_id='P01', finding_id=identifier, disposition='repair',
            rationale='This synthetic finding concerns the current table period label.',
            requested_change='Correct only the affected period label using its original source.',
            expected_progress='Table period and source period agree after author review.')])


@pytest.mark.parametrize('identifier', ['F1', 'verifier:F1', 'confirmation:0:verifier:F1'])
def test_only_identity_changes_and_proposal_metadata_are_preserved(identifier):
    original = proposal(identifier); before = original.model_dump(); supplied = feedback(); saved = deepcopy(supplied)
    resolved, receipts, errors = resolve_disposition_ids(original, supplied)
    assert not errors and not decision_errors(resolved, supplied, {'P01'})
    expected = deepcopy(before); expected['dispositions'][0]['finding_id'] = 'confirmation:0:verifier:F1'
    assert resolved.model_dump() == expected
    assert original.model_dump() == before and supplied == saved
    assert bool(receipts) == (identifier != expected['dispositions'][0]['finding_id'])


@pytest.mark.parametrize('identifier', ['F', 'counter:F1', 'confirmation:9:verifier:F1', 'other:F1'])
def test_no_suffix_fuzzy_or_stale_round_matching(identifier):
    original = proposal(identifier)
    resolved, receipts, errors = resolve_disposition_ids(original, feedback())
    assert not receipts and not errors and resolved == original
    assert decision_errors(resolved, feedback(), {'P01'})


def test_alias_requires_explicit_identity_metadata_and_same_paper():
    supplied = feedback(); del supplied['P01'][0]['original_finding_id']
    assert not resolve_disposition_ids(proposal(), supplied)[1]
    assert not resolve_disposition_ids(proposal(), feedback(paper='P02'))[1]


@pytest.mark.parametrize('second', [feedback('counter'), feedback(round_index=1),
    {'P01': [{'finding_id': 'F1', 'severity': 'material'}]}])
def test_colliding_roles_rounds_or_exact_id_never_choose(second):
    supplied = feedback(); supplied['P01'].extend(second['P01'])
    original = proposal(); resolved, receipts, errors = resolve_disposition_ids(original, supplied)
    assert resolved == original and not receipts
    assert 'ambiguous_finding_id' in errors[0] and 'candidate_ids' in errors[0]


def test_duplicate_disposition_is_rejected_after_resolution():
    original = proposal()
    original.dispositions.append(proposal('confirmation:0:verifier:F1').dispositions[0])
    resolved, receipts, errors = resolve_disposition_ids(original, feedback())
    assert receipts and not errors
    assert 'exactly one' in str(decision_errors(resolved, feedback(), {'P01'}))


@pytest.mark.parametrize('variant', ['valid', 'duplicate', 'material_as_advisory', 'bad_source', 'ambiguous'])
def test_native_submit_resolves_before_full_validation_without_rewriting_proposal(artifacts, variant):
    async def run():
        decision = proposal().model_dump(); supplied = feedback()
        if variant == 'duplicate':
            decision['dispositions'].append(deepcopy(decision['dispositions'][0]))
        elif variant == 'material_as_advisory':
            decision['action'] = 'synthesize'
            decision['dispositions'][0].update(disposition='carry_advisory',
                report_handling='Carry the exact limitation beside the resulting research claim.')
        elif variant == 'bad_source':
            decision['dispositions'][0]['citation_ids'] = ['P01:DOES_NOT_EXIST']
        elif variant == 'ambiguous':
            supplied['P01'].extend(feedback('counter')['P01'])
        submitted = deepcopy(decision)
        model = NativeFixtureModel(marker='identity', replies=[[
            call('submit_lead_issue_decision', {'decision': decision}, 'submit')]])
        agent = build_case_output_agent(role='decision', model=model, tools=[], artifacts=artifacts,
            feedback=supplied, limits={'model_calls': 1, 'tool_calls': 2})
        async for state in agent.astream({'messages': [{'role': 'user', 'content': 'Decide supplied issues.'}], 'revisions': {}}, stream_mode='values'):
            if any(isinstance(m, ToolMessage) for m in state['messages']):
                break  # Inspect the actual rejected receipt, never request a second response.
        raw = next(m for m in state['messages'] if isinstance(m, AIMessage))
        assert raw.tool_calls[0]['args']['decision'] == submitted
        receipt = next(m for m in state['messages'] if isinstance(m, ToolMessage))
        assert bool(state.get('output')) == (variant == 'valid')
        assert receipt.status == ('success' if variant == 'valid' else 'error')
        if variant == 'valid':
            saved = state['output']
            assert saved['dispositions'][0]['finding_id'] == 'confirmation:0:verifier:F1'
            assert saved['finding_id_resolutions'][0]['submitted_id'] == 'F1'
            assert json.loads(receipt.content.split('\n')[-1])['submission_saved'] is True
            for key, value in submitted['dispositions'][0].items():
                if key != 'finding_id': assert saved['dispositions'][0][key] == value
    asyncio.run(run())
