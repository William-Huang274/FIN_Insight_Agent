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


def test_explicit_replace_matches_legacy_and_preserves_atomic_old_value_guard():
    from pydantic import ValidationError
    original = paper()
    edit = {'path': '/claims/0/evidence_ids', 'old_value': original['claims'][0]['evidence_ids'], 'new_value': []}
    legacy = edit_action(original, [edit])
    explicit = edit_action(original, [{**edit, 'op': 'replace'}])
    assert apply_workpaper_edits(original, legacy) == apply_workpaper_edits(original, explicit)
    with pytest.raises(WorkpaperEditError, match='old_value_or_path_mismatch'):
        apply_workpaper_edits(original, edit_action(original, [{**edit, 'op': 'replace', 'old_value': ['wrong']}]))
    with pytest.raises(ValidationError):
        edit_action(original, [{**edit, 'op': 'remove'}])


def test_mismatch_exposes_exact_small_field_and_large_field_locator_without_applying():
    original = paper()
    original['narrative_markdown'] = 'Long current document ' * 1000
    saved = deepcopy(original)
    with pytest.raises(WorkpaperEditError) as caught:
        apply_workpaper_edits(original, edit_action(original, [
            {'path': '/claims/0/evidence_ids', 'old_value': ['missing'], 'new_value': []},
            {'path': '/narrative_markdown', 'old_value': 'fragment', 'new_value': 'replacement'}]))
    small, large = caught.value.issues
    assert small['current_value'] == original['claims'][0]['evidence_ids']
    assert small['current_value_digest'] == canonical_sha256(small['current_value'])
    assert large['current_value_at'] == 'submission_to_repair.candidate/narrative_markdown'
    assert 'current_value' not in large and original == saved
    # The exact field returned by the runtime supports the next atomic repair.
    updated = apply_workpaper_edits(original, edit_action(original, [
        {'path': small['path'], 'old_value': small['current_value'], 'new_value': []}]))
    assert updated['claims'][0]['evidence_ids'] == []
    assert updated['narrative_markdown'] == original['narrative_markdown']


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


@pytest.mark.parametrize('restore', [False, True])
def test_native_failed_batch_repairs_only_bad_edit_and_retains_all_other_changes(restore):
    ports, requests = _ToolPorts(), []
    def model(request):
        requests.append(request)
        n = len(requests)
        if n == 1: return _batch(request, [_evidence_action()({}), _finance_action()({})])
        if n == 2:
            value = paper(); value['claims'][0]['evidence_ids'] = ['E:unobserved']
            return _batch(request, [value])
        candidate = request['submission_to_repair']['candidate']
        if n == 3:
            return _batch(request, [edit_action(candidate, [
                text_edit(old='①Expense table absent.'),
                {'path': '/claims/0/evidence_ids', 'old_value': ['E:unobserved'], 'new_value': ['E:DELL:Q1']},
                {'path': '/counterevidence/0', 'old_value': candidate['counterevidence'][0], 'new_value': 'Corrected limit.'}
            ]).model_dump(mode='json')])
        assert n == 4
        detail = json.loads(request['tool_results'][0]['content'])['edit_result']
        assert detail['saved_edit_count'] == 3 and detail['candidate_unchanged']
        assert candidate == requests[2]['submission_to_repair']['candidate']
        return _batch(request, [edit_action(candidate, [],
            pending_revision_digest=detail['pending_revision_digest'],
            edit_corrections=[{'edit_index': 0, 'edit': text_edit()}]).model_dump(mode='json')])
    dependencies = SpecialistAgenticDependencies(model_turn=model,
        evidence_tool=ports.evidence, finance_tool=ports.finance, allow_workpaper_field_edits=True)
    graph = build_specialist_agentic_state_graph(dependencies=dependencies).compile()
    initial = {**_input(), 'max_model_turns': 3} if restore else _input()
    result = graph.invoke(initial, {'recursion_limit': 60})
    if restore:
        assert len(result['pending_workpaper_revision']['edits']) == 3
        saved = deepcopy(result)
        result = build_specialist_agentic_state_graph(dependencies=dependencies,
            recovery_state=result).compile().invoke({**_input(), 'run_invocation_id': 'resume-edit-batch'}, {'recursion_limit': 60})
        assert len(saved['pending_workpaper_revision']['edits']) == 3
    assert result['phase'] == 'specialist_submission_accepted'
    assert result['pending_workpaper_revision'] is None
    assert result['final_submission']['counterevidence'][0] == 'Corrected limit.'
    assert result['final_submission']['claims'][0]['evidence_ids'] == ['E:DELL:Q1']
    assert text_edit()['new_string'] in result['final_submission']['narrative_markdown']


def test_saved_revision_is_serializable_and_stale_or_ambiguous_corrections_are_rejected():
    from sec_agent.agent_runtime.specialist_graph import save_workpaper_revision, resolve_workpaper_revision
    original = paper()
    legacy = {'action':'revise_workpaper','context_digest':'b'*64,'reason_summary':'Legacy action',
        'base_submission_digest':canonical_sha256(original),'edits':[text_edit()]}
    assert ReviseWorkpaperAction.model_validate_json(json.dumps(legacy)).model_dump(mode='json') == legacy
    draft = save_workpaper_revision(edit_action(original, [text_edit(old='wrong')]))
    restored = json.loads(json.dumps(draft))
    repair = edit_action(original, [], pending_revision_digest=draft['digest'],
        edit_corrections=[{'edit_index': 0, 'edit': text_edit()}])
    fixed = resolve_workpaper_revision(repair, restored)
    assert text_edit()['new_string'] in apply_workpaper_edits(original, fixed)['narrative_markdown']
    with pytest.raises(ValueError, match='digest_mismatch'):
        resolve_workpaper_revision(repair.model_copy(update={'pending_revision_digest': '0' * 64}), restored)
    with pytest.raises(ValueError, match='index_invalid_or_repeated'):
        resolve_workpaper_revision(repair.model_copy(update={'edit_corrections': repair.edit_corrections * 2}), restored)
    with pytest.raises(WorkpaperEditError, match='base_mismatch'):
        apply_workpaper_edits({**original, 'narrative_markdown': 'Changed meanwhile'}, fixed)
