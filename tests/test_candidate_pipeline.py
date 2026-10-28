import pytest
from retrieval.candidate_pipeline import fuse_channels, expand_population


def test_union_and_spare_neighbors_preserve_independent_candidates_and_scope():
    rows=[{'node_id':str(i),'parent_document_id':'document'} for i in range(80)]
    scores=[1/(i+1) for i in range(80)]
    entry, order, limits=fuse_channels(rows,scores,[str(i) for i in range(12,40)],
        policy='needs_window.v4',lexical_policy='organization-financial-needs.v2')
    assert limits=={'dense':24,'lexical':24,'graph':0}
    assert set(entry['ordered'])=={str(i) for i in range(36)}
    expanded,receipt=expand_population(entry['ordered'],entry['dense'],rows,
        {'0':['70','foreign']},policy='needs_window.v4')
    assert expanded==entry['ordered']+['70']
    assert receipt['displaced_node_ids']==[]
    with pytest.raises(ValueError,match='outside_scope'):
        fuse_channels(rows,scores,['foreign'],policy='needs_window.v4')


def test_ties_are_stable_and_nonfinite_scores_rejected():
    rows=[{'node_id':n} for n in ['z','a']]
    entry,order,_=fuse_channels(rows,[.5,.5],[],policy='balanced.v1')
    assert entry['dense']==['a','z'] and order==[1,0]
    with pytest.raises(ValueError,match='nonfinite'):
        fuse_channels(rows,[float('nan'),.5],[],policy='balanced.v1')
