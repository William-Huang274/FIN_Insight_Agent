from copy import deepcopy
import pytest
from retrieval.source_structure import source_structure
from retrieval.source_coordinates import verified_bounds
from retrieval.table_completion import read_span


def test_imported_nodes_get_verified_local_structure_without_invented_document_order(tmp_path):
    from test_library_node_recovery import ready
    *_,bundle=ready(tmp_path)
    structures=source_structure(bundle)
    assert len(structures)==len(bundle['chunks'])
    original_by_parent={p['id']:p for p in bundle['parents']}
    for chunk in bundle['chunks']:
        s=structures[chunk['id']]
        assert s['status']=='verified_original_node_coordinates'
        assert s['coordinate_space']['complete_original_document'] is False
        assert s['coordinate_space']['original_node_sha256']==original_by_parent[chunk['parent_id']]['digest']
        origin={'original_node_id':s['coordinate_space']['original_node_id'],
                'char_start':chunk['char_start'],'char_end':chunk['char_end']}
        assert verified_bounds({'source_structure':s,'original_source':origin})[1:]==(chunk['char_start'],chunk['char_end'])
        changed=deepcopy(origin);changed['original_node_id']='another-node'
        with pytest.raises(ValueError,match='node_identity'):
            verified_bounds({'source_structure':s,'original_source':changed})


def test_identical_local_offsets_in_another_node_cannot_supply_table_context():
    anchor={'parent_document_id':'document','original_source':{'source_id':'source','source_digest':'a'*64,
        'original_node_id':'table-a','char_start':4,'char_end':8}}
    header={'parent_document_id':'document','content':'unit',
        'original_source':{'source_digest':'a'*64,'original_node_id':'table-b','char_start':0,'char_end':4}}
    with pytest.raises(ValueError,match='identity_mismatch'):
        read_span(anchor,{'source_char_start':0,'source_char_end':4},[(0,4,'header')],lambda _:header)


def test_identical_supplemental_text_in_two_nodes_keeps_each_node_identity():
    from hashlib import sha256
    from retrieval.table_completion import complete_tables
    span={'source_char_start':0,'source_char_end':4,'content_sha256':sha256(b'unit').hexdigest(),
          'role':'header_band'}
    rows=[{'node_id':space,'parent_document_id':'document',
        'original_source':{'source_digest':'a'*64,'original_node_id':space,'char_start':4,'char_end':8},
        'source_structure':{'status':'verified_original_node_coordinates',
            'table_dependencies':[{'table':{},'required':[span],'unresolved':[]}]}} for space in ('a','b')]
    calls=[]
    def load(anchor,span):
        space=anchor['original_source']['original_node_id'];calls.append(space)
        return {**span,'text':'unit','document_id':'document','source_digest':'a'*64,'original_node_id':space}
    result,receipt=complete_tables(rows,load,independent_candidates=True)
    assert calls==['a','b'] and receipt['unique_supplemental_spans']==2
    assert [r['table_completion']['contexts'][0]['original_node_id'] for r in result]==['a','b']
