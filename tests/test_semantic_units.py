from copy import deepcopy
from hashlib import sha256
import pytest
from retrieval.semantic_units import split_original,validate_partition
from retrieval.structural_surface import structural_only


def row(body,scopes=(),tables=(),space=None):
    origin={'source_digest':'s'*64,'source_char_start':100,'source_char_end':100+len(body)}
    structure={'status':'verified_original_coordinates','tables':tables,'evidence_scopes':scopes}
    if space:
        origin={'source_digest':'s'*64,'char_start':100,'char_end':100+len(body),'original_node_id':space}
        structure.update(status='verified_original_node_coordinates',coordinate_space={'original_node_id':space})
    return {'node_id':'parent','parent_document_id':'doc','title':'original context','content':body,'original_source':origin,
        'source_structure':structure,'content_sha256':sha256(body.encode()).hexdigest(),
        'embedding_context':'original context','embedding_input_sha256':sha256(('original context\n'+body).encode()).hexdigest()}


def test_mixed_table_separation_preserves_every_character_and_vector_inputs():
    body='Main\n[TABLE:1]\nCash | 20\n[/TABLE]\nPension\n[TABLE:2]\nCash | 3\n[/TABLE]\nTail'
    a=100+body.index('[TABLE:2]');b=100+body.index('[/TABLE]',body.index('[TABLE:2]'))+8
    source=row(body,[{'source_char_start':a,'source_char_end':b,'attributes':{'asset_scope':'pension_plan'}}])
    units=split_original(source)
    assert ''.join(u['content'] for u in units)==body
    assert all(not ('20' in u['content'] and '3' in u['content']) for u in units)
    assert not any(u['reusable_parent_vector'] for u in units)
    pension=[u for u in units if u['evidence_scopes']]
    assert len(pension)==1 and '3' in pension[0]['content'] and pension[0]['role']=='table'
    # The unknown trailing prose no longer shares the table's semantic vector.
    assert units[-1]['content']=='\nTail' and units[-1]['evidence_scopes']==[]


def test_single_unchanged_unit_can_reuse_only_the_exact_embedding_input():
    source=row('A complete paragraph.')
    unit=split_original(source)[0]
    assert unit['reusable_parent_vector']
    source['embedding_input_sha256']='x'*64
    assert not split_original(source)[0]['reusable_parent_vector']


def test_node_local_frames_never_merge_and_tampering_is_rejected():
    a=row('Same text',space='node-a');b=row('Same text',space='node-b')
    aa,bb=split_original(a),split_original(b)
    assert aa[0]['unit_id']!=bb[0]['unit_id']
    with pytest.raises(ValueError,match='identity_mismatch'):validate_partition(a,bb)
    bad=deepcopy(aa);bad[0]['content']='changed'
    with pytest.raises(ValueError,match='content_mismatch'):validate_partition(a,bad)


def test_split_table_fragment_keeps_global_table_identity_and_prose_never_truncates():
    source=row('a'*7000,tables=[{'source_char_start':50,'source_char_end':9000}])
    units=split_original(source)
    assert len(units)==1 and units[0]['table_intervals']==[(50,9000)]
    assert len(units[0]['content'])==7000
    assert split_original(row('a'*7000))[0]['content']=='a'*7000


@pytest.mark.parametrize('text', ['[/TABLE]', '\n[TABLE: original cell order]\n[/TABLE]\n', ' \n',
    '[TABLE: original cell order]\n | | | \n', ' | | \n[/TABLE]'])
def test_parser_only_units_are_preserved_but_not_searchable(text):
    original=row(text)
    units=split_original(original)
    assert ''.join(u['content'] for u in units)==text
    assert all(not u['retrievable'] for u in units)
    validate_partition(original,units)


@pytest.mark.parametrize('text', ['Cash | 20', '(in millions)', '(1) Includes restricted cash.',
    '2024 | 2023', '[TABLE:1] Cash | 20 [/TABLE]', 'CONSOLIDATED BALANCE SHEETS',
    '[Unknown marker]', 'Table of Contents', '| - |', '| $ |', '| 0 |'])
def test_short_facts_units_footnotes_and_navigation_are_not_blanket_discarded(text):
    assert not structural_only(text)
    assert any(u['retrievable'] for u in split_original(row(text)))
