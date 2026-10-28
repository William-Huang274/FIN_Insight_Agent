from copy import deepcopy
from test_semantic_units import row
from retrieval.original_result_groups import collapse_original_duplicates


def original(identifier='first'):
    r=row('Cash | 40');r['node_id']=identifier
    r['original_source'].update(source_id='source',library_sha256='library')
    return r


def test_duplicate_original_projection_backfills_without_losing_alternate_identity():
    a=original();b=original('duplicate');c=original('other')
    c['original_source']['source_digest']='revised'
    result,receipt=collapse_original_duplicates([a,b,c])
    assert [r['node_id'] for r in result]==['first','other']
    assert receipt['removed_rank_slots']==1
    assert receipt['aliases'][0]['alternate_node_id']=='duplicate'


def test_equal_body_different_table_position_version_or_period_is_not_merged():
    a=original();variants=[]
    for field,value in [('source_id','other'),('source_digest','revised'),('library_sha256','other-library')]:
        b=deepcopy(a);b['node_id']=field;b['original_source'][field]=value;variants.append(b)
    b=original('different-row');b['original_source']['source_char_start']+=10
    b['original_source']['source_char_end']+=10;variants.append(b)
    b=original('different-period');b['source_structure']['period_evidence']=[{'period':{'kind':'date','value':'2025-01-01'}}]
    variants.append(b)
    assert len(collapse_original_duplicates([a,*variants])[0])==6
