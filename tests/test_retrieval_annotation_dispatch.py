from copy import deepcopy

import pytest

from scripts.engineering.retrieval_annotation_delta import validate_delta, partition_scope, digest
from scripts.engineering.retrieval_annotation_dispatch import prepare_dispatch, bind_dispatch, explicit_table_caption
from scripts.engineering.retrieval_annotation_reviews import reviewed_role
import scripts.engineering.retrieval_annotation_dispatch as dispatch


def fixture():
    p = {'schema': 'retrieval-annotation-packet.v3', 'packet_id': 'example',
         'source': {'source_digest': 'frozen-source', 'coordinate_space': 'document'},
         'elements': [{'id': 'A', 'kind': 'line', 'text': 'Amounts in millions', 'start': 0, 'end': 19},
                      {'id': 'B', 'kind': 'line', 'text': '(1)', 'start': 20, 'end': 23},
                      {'id': 'C', 'kind': 'line', 'text': ':', 'start': 24, 'end': 25},
                      {'id': 'T', 'kind': 'table', 'text': 'Cash | 42', 'start': 26, 'end': 35}],
         'tasks': [{'task_id': 'context', 'kind': 'context', 'scope_ids': ['A', 'B', 'C', 'T'],
                    'target_ids': ['T'], 'support_choices': [
                        {'id': 'S1', 'element_ids': ['A', 'B', 'C'], 'basis': 'Original complete caption with its inline note marker.'}]}]}
    budget = {k: 'qualification' for k in ('purpose', 'input_scale', 'required_output', 'quality_risk', 'reasoning_profile', 'limits', 'stop_behavior')}
    r = {'packets': [{'packet_id': 'example', 'decisions': [{'task_id': 'context', 'status': 'proposed',
             'links': [{'support_choice_ids': ['S1'], 'target_id': 'T'}]}]}]}
    return p, budget, r


def test_program_binds_hash_and_recovers_whole_caption_without_model_copying():
    p, b, r = fixture(); old = deepcopy((p, r))
    manifest = prepare_dispatch([p], trusted_roles={}, budget=b)
    out = bind_dispatch([p], manifest, r, trusted_roles={})
    assert out['packets'][0]['decisions'][0]['links'][0]['support_ids'] == ['A', 'B', 'C']
    assert (p, r) == old
    assert not out['semantic_accepted'] and not out['publication_allowed']
    assert validate_delta(p, out['packets'][0])['elements'] == p['elements']


@pytest.mark.parametrize('change', ['source', 'text', 'scope', 'choice', 'roles', 'manifest', 'extra_hash', 'duplicate', 'unknown', 'missing'])
def test_freeze_and_inventory_cannot_be_changed(change):
    p, b, r = fixture(); roles = {}; manifest = prepare_dispatch([p], trusted_roles=roles, budget=b)
    if change == 'source': p['source']['source_digest'] = 'changed'
    if change == 'text': p['elements'][0]['text'] = 'Amounts in billions'
    if change == 'scope': p['tasks'][0]['scope_ids'].remove('C')
    if change == 'choice': p['tasks'][0]['support_choices'][0]['element_ids'].pop()
    if change == 'roles': roles['forged'] = {}
    if change == 'manifest': manifest['dispatch_digest'] = 'changed'
    if change == 'extra_hash': r['packets'][0]['packet_digest'] = 'model-generated'
    if change == 'duplicate': r['packets'].append(deepcopy(r['packets'][0]))
    if change == 'unknown': r['packets'][0]['decisions'][0]['links'][0]['support_choice_ids'] = ['missing']
    if change == 'missing': r['packets'][0]['decisions'] = []
    with pytest.raises(ValueError): bind_dispatch([p], manifest, r, trusted_roles=roles)


@pytest.mark.parametrize('ids', [['A', 'C'], ['A', 'T'], ['T'], ['B', 'A']])
def test_choices_cannot_smuggle_noncontiguous_or_table_content(ids):
    p, b, _ = fixture(); p['tasks'][0]['support_choices'][0]['element_ids'] = ids
    with pytest.raises(ValueError): prepare_dispatch([p], trusted_roles={}, budget=b)


def test_missing_material_remains_unresolved():
    p, b, r = fixture()
    r['packets'][0]['decisions'] = [{'task_id': 'context', 'status': 'unresolved', 'reason': 'Referenced note body is not present'}]
    out = bind_dispatch([p], prepare_dispatch([p], trusted_roles={}, budget=b), r, trusted_roles={})
    assert validate_delta(p, out['packets'][0])['unresolved']


def test_validator_dependency_drift_invalidates_pending_dispatch(monkeypatch):
    p, b, r = fixture(); manifest = prepare_dispatch([p], trusted_roles={}, budget=b)
    monkeypatch.setattr(dispatch, 'implementation_digest', lambda: 'changed-validator')
    with pytest.raises(ValueError, match='drift'):
        bind_dispatch([p], manifest, r, trusted_roles={})


@pytest.mark.parametrize('change', ['none', 'plural', 'intervening', 'unreviewed', 'missing_attachment'])
def test_explicit_caption_rule_is_source_bound_not_nearest_text(change):
    p, _, _ = fixture()
    p['elements'][0]['text'] = 'The following table presents amounts in millions'
    # Rebuild geometry only for this synthetic test source.
    offset = 0
    for e in p['elements']:
        e['start'] = offset; e['end'] = offset+len(e['text']); offset = e['end']+1
    role = reviewed_role(p, 'T', 'data_table', reviewer='primary', reason='Cash observations in original rows')
    p['source_role_refs'] = {'T': role['review_id']}; roles = {role['review_id']: role}
    task = p['tasks'][0]; task['context_mode'] = 'table_caption'
    if change == 'plural': p['elements'][0]['text'] = 'The following tables present amounts in millions'
    if change == 'intervening': task['support_choices'][0]['element_ids'] = ['A', 'B']
    if change == 'unreviewed': p['source_role_refs'] = {}
    if change == 'missing_attachment': task['context_mode'] = 'referenced_note_body'
    out = explicit_table_caption(p, task, trusted_roles=roles)
    if change == 'none': assert out['links'][0]['support_ids'] == ['A', 'B', 'C']
    else: assert out is None


@pytest.mark.parametrize('text,exclude', [(' \u200b\ufeff ', True), ('0', False), ('—', False), ('(1)', False), ('million', False)])
def test_nonsemantic_spacer_retained_without_model_ownership(text, exclude):
    p = {'schema': 'retrieval-annotation-packet.v3', 'packet_id': 'spacer',
         'source': {'source_digest': 'original', 'coordinate_space': 'document'},
         'elements': [{'id': 'A', 'kind': 'line', 'text': 'First.', 'start': 0, 'end': 6},
                      {'id': 'S', 'kind': 'line', 'text': text, 'start': 7, 'end': 7+len(text)},
                      {'id': 'B', 'kind': 'line', 'text': 'Next.', 'start': 8+len(text), 'end': 13+len(text)}]}
    ids, retained = partition_scope(p['elements'], ['A', 'S', 'B'])
    assert retained == (['S'] if exclude else [])
    p['tasks'] = [{'task_id': 'P', 'kind': 'partition', 'scope_ids': ids, 'partition_source_ids': ['A', 'S', 'B']}]
    r = {'packet_id': 'spacer', 'packet_digest': digest(p), 'decisions': [{'task_id': 'P', 'status': 'proposed', 'groups': [[e] for e in ids]}]}
    out = validate_delta(p, r)
    assert out['elements'] == p['elements']
    assert out['coverage'][1]['state'] == ('retained_structure' if exclude else 'proposal_pending_review')
    if not exclude:
        p['tasks'][0]['scope_ids'] = ['A', 'B']; r['packet_digest'] = digest(p)
        r['decisions'][0]['groups'] = [['A'], ['B']]
        with pytest.raises(ValueError, match='omitted non-whitespace'): validate_delta(p, r)
