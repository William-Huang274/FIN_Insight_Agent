"""Precise local edits and recoverable runtime feedback, not financial qualification."""
from copy import deepcopy
import json

import pytest

from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256
from sec_agent.agent_runtime.specialist_graph import (
    ReviseWorkpaperAction, WorkpaperEditError, apply_workpaper_edits,
    SpecialistAgenticDependencies, build_specialist_agentic_state_graph,
)
from test_specialist_graph import _submission, _input, _ToolPorts, _evidence_action, _finance_action
from test_specialist_tool_batch import _batch, _handoff


def paper():
    value = _submission()({})
    value['context_digest'] = 'a' * 64
    value['narrative_markdown'] = '# Scope\n2025 Q1; USD million; source E:DELL:Q1\n\nExpense table absent.\n\n# Other\nKeep 12.50 and its period.'
    value['task_note'] = {'summary': 'Original assessment', 'coverage': [assessment('original')]}
    return value


def assessment(criterion):
    return {'criterion': criterion, 'status': 'completed', 'explanation': 'Inspected within stated scope.', 'fields': ['narrative_markdown'], 'claim_ids': []}


def text_edit(old='Expense table absent.', new='Expense table provided; detailed causal attribution remains open.', path='/narrative_markdown'):
    return {'op': 'str_replace', 'path': path, 'old_string': old, 'new_string': new}


def edit_action(original, edits, **kwargs):
    return ReviseWorkpaperAction.model_validate_json(json.dumps({'action': 'revise_workpaper', 'context_digest': 'b' * 64,
        'reason_summary': 'Correct selected content.', 'base_submission_digest': canonical_sha256(original), 'edits': edits, **kwargs}))


def test_precise_fragment_and_single_assessment_preserve_unrelated_content():
    original = paper(); saved = deepcopy(original)
    updated = apply_workpaper_edits(original, edit_action(original, [text_edit(), {'op': 'upsert_coverage', 'assessment': assessment('new check')}]))
    assert original == saved
    assert updated['narrative_markdown'] == original['narrative_markdown'].replace('Expense table absent.', text_edit()['new_string'])
    assert updated['claims'] == original['claims']
    assert updated['task_note']['coverage'] == [assessment('original'), assessment('new check')]
    changed = {**assessment('new check'), 'explanation': 'Rechecked with additional qualifiers.'}
    again = apply_workpaper_edits(updated, edit_action(updated, [{'op': 'upsert_coverage', 'assessment': changed}]))
    assert again['task_note']['coverage'] == [assessment('original'), changed]
    assert again['narrative_markdown'] == updated['narrative_markdown']


@pytest.mark.parametrize('body,fragment,count', [('same same', 'same', 2), ('aaaa', 'aa', 3), ('exact source', 'Exact source', 0)])
def test_ambiguous_or_missing_literal_never_guesses(body, fragment, count):
    original = paper(); original['narrative_markdown'] = body
    with pytest.raises(WorkpaperEditError) as caught:
        apply_workpaper_edits(original, edit_action(original, [text_edit(old=fragment)]))
    issue = caught.value.issues[0]
    assert issue['edit_index'] == 0 and issue['path'] == '/narrative_markdown'
    assert issue['match_count'] == count and 'adjacent text' in issue['remedy']
    assert original['narrative_markdown'] == body


def test_batch_returns_each_fault_location_without_applying_valid_edits():
    original = paper(); saved = deepcopy(original)
    with pytest.raises(WorkpaperEditError) as caught:
        apply_workpaper_edits(original, edit_action(original, [text_edit(),
            text_edit(old='missing', path='/thesis'), text_edit(path='/claims/99/statement'), text_edit(path='/claims')]))
    assert [i['edit_index'] for i in caught.value.issues] == [1, 2, 3]
    assert [i['code'] for i in caught.value.issues] == ['text_not_found', 'path_not_found', 'text_field_required']
    assert original == saved


def test_legacy_fragment_failure_explicitly_recommends_local_edit():
    original = paper()
    with pytest.raises(WorkpaperEditError) as caught:
        apply_workpaper_edits(original, edit_action(original, [{'path': '/narrative_markdown',
            'old_value': 'Expense table absent.', 'new_value': 'Provided.'}]))
    assert caught.value.issues[0]['code'] == 'old_value_mismatch'
    assert 'op=str_replace' in caught.value.issues[0]['remedy']


def test_stale_base_claim_identity_and_duplicate_coverage_remain_guarded():
    original = paper()
    with pytest.raises(WorkpaperEditError, match='base_mismatch'):
        apply_workpaper_edits(original, edit_action(original, [text_edit()], base_submission_digest='0' * 64))
    with pytest.raises(WorkpaperEditError, match='claim_identity'):
        apply_workpaper_edits(original, edit_action(original, [text_edit(old=original['claims'][0]['claim_id'], new='replacement', path='/claims/0/claim_id')]))
    original['task_note']['coverage'].append(assessment('original'))
    with pytest.raises(WorkpaperEditError) as caught:
        apply_workpaper_edits(original, edit_action(original, [{'op': 'upsert_coverage', 'assessment': assessment('original')}]))
    assert caught.value.issues[0]['code'] == 'coverage_criterion_not_unique'


def test_native_feedback_keeps_unmodified_body_visible_after_other_field_repair():
    ports, requests = _ToolPorts(), []
    def model(request):
        requests.append(request); n = len(requests)
        if n == 1:
            return _batch(request, [_evidence_action()({}), _finance_action()({})])
        if n == 2:
            value = paper(); value['claims'][0]['evidence_ids'] = ['E:unobserved']
            return _batch(request, [value])
        target = request['submission_to_repair']; candidate = target['candidate']
        if n == 3:
            edits = [{'path': '/counterevidence/0', 'old_value': candidate['counterevidence'][0], 'new_value': 'Corrected limit.'},
                {'path': '/narrative_markdown', 'old_value': 'Expense table absent.', 'new_value': 'Provided.'}]
        elif n == 4:
            details = json.loads(request['tool_results'][0]['content'])['edit_result']
            assert details['candidate_unchanged'] and not details['batch_applied']
            assert details['issues'][0]['edit_index'] == 1
            assert details['issues'][0]['path'] == '/narrative_markdown'
            edits = [{'path': '/counterevidence/0', 'old_value': candidate['counterevidence'][0], 'new_value': 'Corrected limit.'}]
        elif n == 5:
            progress = {r['path']: r['status'] for r in target['edit_progress']}
            assert progress['/narrative_markdown'] == 'unchanged_since_revision_requested'
            assert progress['/counterevidence/0'] == 'changed_not_semantically_verified'
            result = json.loads(request['tool_results'][0]['content'])
            assert result['edit_result']['batch_applied'] and not result['accepted']
            edits = [text_edit(), {'path': '/claims/0/evidence_ids', 'old_value': ['E:unobserved'], 'new_value': ['E:DELL:Q1']},
                {'op': 'upsert_coverage', 'assessment': assessment('additional check')}]
        else:
            return _handoff(request)
        action = edit_action(candidate, edits).model_dump(mode='json')
        return _batch(request, [action])
    graph = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(model_turn=model,
        evidence_tool=ports.evidence, finance_tool=ports.finance, allow_workpaper_field_edits=True)).compile()
    result = graph.invoke(_input(), {'recursion_limit': 60})
    assert result['phase'] == 'specialist_submission_accepted'
    assert len(requests) == 5
    assert 'Expense table absent.' not in result['final_submission']['narrative_markdown']
    assert result['final_submission']['claims'][0]['evidence_ids'] == ['E:DELL:Q1']


def test_schema_invalid_edit_batch_preserves_prior_candidate_and_locations():
    ports, requests = _ToolPorts(), []
    def model(request):
        requests.append(request)
        if len(requests) == 1: return _batch(request, [_evidence_action()({}), _finance_action()({})])
        if len(requests) == 2:
            value = paper(); value['claims'][0]['evidence_ids'] = ['E:unobserved']
            return _batch(request, [value])
        if len(requests) == 3:
            original = request['submission_to_repair']['candidate']
            return _batch(request, [edit_action(original, [text_edit(),
                {'path': '/terminal_state', 'old_value': original['terminal_state'], 'new_value': 'invented'}]).model_dump(mode='json')])
        result = json.loads(request['tool_results'][0]['content'])['edit_result']
        assert result['candidate_unchanged'] and result['issues'][0]['location'] == ['terminal_state']
        assert request['submission_to_repair']['candidate'] == requests[2]['submission_to_repair']['candidate']
        return _handoff(request)
    graph = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(model_turn=model,
        evidence_tool=ports.evidence, finance_tool=ports.finance, allow_workpaper_field_edits=True)).compile()
    result = graph.invoke(_input(), {'recursion_limit': 50})
    assert result['final_submission'] is None
