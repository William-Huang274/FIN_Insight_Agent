from copy import deepcopy

import pytest

from qualify_sec_sequence_alignment import compare


def document():
    return dict(source_containers=[dict(id='s', text='None.')], blocks=[dict(kind='text', text='None.',
                source_container_id='s', source_location_status='unique_complete_container',
                structural_role='unit_context', native_section_binding=dict(status='unique_native_membership', candidates=['item1']))])


def test_qualification_retains_existing_locations_roles_and_sections():
    old = document()
    assert compare(old, deepcopy(old)) == {'new_sections_with_blocks': 0}
    for field, value in [('text', 'different'), ('kind', 'heading'), ('structural_role', None), ('source_container_id', 'wrong')]:
        new = deepcopy(old); new['blocks'][0][field] = value
        with pytest.raises(ValueError):
            compare(old, new)
    new = deepcopy(old); new['blocks'][0]['native_section_binding']['candidates'] = ['item2']
    with pytest.raises(ValueError, match='previous_unique_section_lost'):
        compare(old, new)


def test_qualification_counts_only_actual_added_bindings():
    new = document(); old = deepcopy(new)
    old['blocks'][0].update(source_container_id=None, source_location_status='ambiguous', native_section_binding={})
    assert compare(old, new) == dict(new_unique_original_locations=1, new_unique_section_blocks=1, new_sections_with_blocks=1)


def test_previous_signature_proof_cannot_disappear():
    old = document(); old['source_scope_repairs'] = [dict(start_block=1, end_block_exclusive=5, heading_source_id='s', attestation_source_id='a')]
    with pytest.raises(ValueError, match='previous_signature_proof_lost'):
        compare(old, document())
