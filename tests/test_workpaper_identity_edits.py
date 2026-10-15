"""Version/identity-bound updates without copying old claims; no model calls."""
from copy import deepcopy
import json

import pytest
from pydantic import ValidationError

from sec_agent.agent_runtime.specialist_graph import (
    ReviseWorkpaperAction, WorkpaperEditError, apply_workpaper_edits,
    save_workpaper_revision, resolve_workpaper_revision,
    SpecialistAgenticDependencies, build_specialist_agentic_state_graph,
)
from sec_agent.agent_runtime.deepseek_structured_agents import _native_function_schema, _NATIVE_SPECIALIST_SYSTEM_PROMPT
from sec_agent.agent_runtime.research_context_view import working_view
from test_workpaper_partial_edits import paper, edit_action, text_edit
from test_specialist_graph import _input, _ToolPorts, _evidence_action, _finance_action
from test_specialist_tool_batch import _batch, _handoff
from test_research_context_view import fixture


def change(original, **fields):
    return {'op': 'update_claim', 'claim_id': original['claims'][0]['claim_id'], 'changes': fields}


def test_identity_edit_retains_unmentioned_sources_fields_and_order_after_serialization():
    original = paper(); saved = deepcopy(original)
    edit = change(original, statement='Updated interpretation of the same observed material.')
    action = edit_action(original, [edit])
    assert action.model_dump(mode='json')['edits'] == [edit]
    pending = save_workpaper_revision(action)
    assert pending['edits'] == [edit]
    updated = apply_workpaper_edits(original, action)
    expected = deepcopy(original['claims']); expected[0]['statement'] = edit['changes']['statement']
    assert updated['claims'] == expected
    assert original == saved
    assert updated['narrative_markdown'] == original['narrative_markdown']


def test_identity_resolves_current_position_and_version_is_still_mandatory():
    original = paper(); selected = original['claims'][0]['claim_id']
    original['claims'].reverse()
    edit = {'op': 'update_claim', 'claim_id': selected, 'changes': {'statement': 'Updated.'}}
    updated = apply_workpaper_edits(original, edit_action(original, [edit]))
    assert next(c for c in updated['claims'] if c['claim_id'] == selected)['statement'] == 'Updated.'
    with pytest.raises(WorkpaperEditError, match='base_mismatch'):
        apply_workpaper_edits(original, edit_action(original, [edit], base_submission_digest='0'*64))


@pytest.mark.parametrize('fields', [{}, {'statement': None}, {'evidence_ids': None}, {'kind': None}, {'claim_id': 'renamed'}, {'unsupported': 1}])
def test_empty_null_or_identity_mutation_cannot_silently_clear_claim(fields):
    original = paper()
    with pytest.raises(ValidationError):
        edit_action(original, [change(original, **fields)])


def test_explicit_clear_is_distinct_from_omitted_field():
    original = paper()
    updated = apply_workpaper_edits(original, edit_action(original, [change(original,
        reasoning_summary=None, evidence_ids=[], citation_quotes={})]))
    assert updated['claims'][0]['reasoning_summary'] is None
    assert updated['claims'][0]['evidence_ids'] == []
    assert updated['claims'][0]['citation_quotes'] == {}
    assert updated['claims'][0]['statement'] == original['claims'][0]['statement']


def test_unknown_or_duplicate_identity_rejects_without_guessing():
    original = paper(); saved = deepcopy(original)
    with pytest.raises(WorkpaperEditError) as err:
        apply_workpaper_edits(original, edit_action(original, [
            {'op': 'update_claim', 'claim_id': 'missing', 'changes': {'statement': 'Wrong target.'}}]))
    assert err.value.issues[0]['code'] == 'claim_id_not_found_or_not_unique'
    assert original == saved
    original['claims'].append(deepcopy(original['claims'][0]))
    with pytest.raises(WorkpaperEditError):
        apply_workpaper_edits(original, edit_action(original, [change(original, statement='Ambiguous.')]))


def test_version_bound_setter_and_fragment_can_update_related_prose_without_full_paper():
    original = paper()
    updated = apply_workpaper_edits(original, edit_action(original, [
        change(original, statement='Related judgment updated.'), text_edit(),
        {'op': 'set_field', 'path': '/task_note/summary', 'value': 'Updated source status.'}]))
    assert updated['task_note']['coverage'] == original['task_note']['coverage']
    assert text_edit()['new_string'] in updated['narrative_markdown']
    assert 'Keep 12.50 and its period.' in updated['narrative_markdown']
    for path in ('/claims/0', '/context_digest', '/citation_quotes'):
        with pytest.raises(WorkpaperEditError):
            apply_workpaper_edits(original, edit_action(original, [{'op': 'set_field', 'path': path, 'value': {}}]))


def test_failed_batch_and_saved_correction_preserve_other_claim_changes():
    original = paper(); saved = deepcopy(original)
    first = edit_action(original, [change(original, statement='Changed once.'), text_edit(old='not present')])
    with pytest.raises(WorkpaperEditError): apply_workpaper_edits(original, first)
    assert original == saved
    pending = json.loads(json.dumps(save_workpaper_revision(first)))
    correction = edit_action(original, [], pending_revision_digest=pending['digest'],
        edit_corrections=[{'edit_index': 1, 'edit': text_edit()}])
    updated = apply_workpaper_edits(original, resolve_workpaper_revision(correction, pending))
    assert updated['claims'][0]['statement'] == 'Changed once.'
    assert text_edit()['new_string'] in updated['narrative_markdown']


def test_new_wire_retires_old_value_variant_but_archived_actions_still_parse():
    wire = _native_function_schema(ReviseWorkpaperAction, runtime_context_binding=True)
    encoded = json.dumps(wire)
    assert '"old_value"' not in encoded and '"new_value"' not in encoded
    for op in ('update_claim', 'set_field', 'str_replace', 'upsert_coverage'):
        assert f'"const": "{op}"' in encoded
    variant, = [v for v in wire['parameters']['properties']['edits']['items']['anyOf']
                if v['properties']['op'].get('const') == 'update_claim']
    changes = variant['properties']['changes']
    assert not changes.get('required')
    assert changes['properties']['statement']['type'] == 'string'
    assert '"type": "null"' not in json.dumps(changes['properties']['evidence_ids'])
    assert '"type": "null"' in json.dumps(changes['properties']['reasoning_summary'])
    assert 'Shared citation_quotes may' not in _NATIVE_SPECIALIST_SYSTEM_PROMPT
    assert 'Do not duplicate source quotes' not in _NATIVE_SPECIALIST_SYSTEM_PROMPT
    original = paper()
    legacy = edit_action(original, [{'path': '/thesis', 'old_value': original['thesis'], 'new_value': 'Legacy still readable.'}])
    assert apply_workpaper_edits(original, legacy)['thesis'] == 'Legacy still readable.'


def test_calc_channel_explanation_preserves_exact_original_bindings_and_history():
    rows = fixture(); body = json.loads(rows[4].content)
    ref = {'ref_id': 'NEW', 'authority_state': 'non_authoritative_metric', 'writer_citable': False, 'numeric_fact_authority': False}
    body['result']['observations'][0]['references'] = [ref]
    rows[4].content = json.dumps(body); saved = deepcopy(rows)
    result = working_view(rows); view = json.loads(result[0].content)
    assert view['current_material_bindings'][0]['references'] == [ref]
    assert view['current_reference_usage']['NEW']['field'] == 'fact_ids'
    assert 'writer_citable=false only forbids evidence_ids' in view['current_reference_usage']['NEW']['requirement']
    assert rows == saved and working_view(result) == result


def test_native_revision_validates_new_bindings_then_finishes_with_identity_patch():
    ports, requests = _ToolPorts(), []
    def model(request):
        requests.append(request); n = len(requests)
        if n == 1: return _batch(request, [_evidence_action()({}), _finance_action()({})])
        if n == 2:
            value = paper(); value['claims'][0]['evidence_ids'] = ['E:unobserved']
            return _batch(request, [value])
        candidate = request['submission_to_repair']['candidate']
        if n == 3:
            assert 'update_claim' in request['submission_to_repair']['submission_contract']['claim_changes']
            return _batch(request, [edit_action(candidate, [change(candidate, evidence_ids=['E:still-unobserved'])]).model_dump(mode='json')])
        if n == 4:
            assert candidate['claims'][0]['evidence_ids'] == ['E:still-unobserved']
            assert not json.loads(request['tool_results'][0]['content'])['accepted']
            return _batch(request, [edit_action(candidate, [change(candidate, evidence_ids=['E:DELL:Q1']),
                text_edit(), {'op':'set_field','path':'/task_note/summary','value':'Fixture updated.'}]).model_dump(mode='json')])
        return _handoff(request)
    result = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=model, evidence_tool=ports.evidence, finance_tool=ports.finance,
        allow_workpaper_field_edits=True)).compile().invoke(_input(), {'recursion_limit': 60})
    assert len(requests) == 4
    assert result['phase'] == 'specialist_submission_accepted'
    assert result['final_submission']['claims'][0]['evidence_ids'] == ['E:DELL:Q1']
    assert result['final_submission']['task_note']['summary'] == 'Fixture updated.'
