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


def test_empty_graph_does_not_take_dense_capacity():
    rows=[{'node_id':str(i)} for i in range(80)]
    scores=list(range(80))
    baseline,_,a=fuse_channels(rows,scores,[],policy='needs_window.v4')
    empty,_,b=fuse_channels(rows,scores,[],policy='needs_window.v4',graph=[])
    assert a==b and empty['dense']==baseline['dense']
    assert empty['graph']==[] and b['graph']==0


def test_unit_policy_backfills_independent_rankings_before_any_neighbors():
    rows=[{'node_id':str(i)} for i in range(100)]
    scores=[1/(i+1) for i in range(100)]
    lexical=[str(i) for i in [*range(24),*range(70,94)]]
    entry,_,limits=fuse_channels(rows,scores,lexical,policy='needs_units.v1',
        lexical_policy='organization-financial-needs.v2')
    assert len(entry['ordered'])==48 and len(set(entry['ordered']))==48
    assert entry['dense']==entry['lexical']==[str(i) for i in range(24)]
    assert len(entry['independent_backfill']['dense'])==12
    assert len(entry['independent_backfill']['lexical'])==12
    assert entry['independent_backfill']['adjacent_only_candidates']==[]
