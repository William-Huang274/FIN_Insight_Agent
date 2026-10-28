from copy import deepcopy
import pytest
from retrieval.table_completion import complete_tables
from retrieval.rerank_structure_context import structure_context_text
from test_table_completion import fixture


def test_verified_structural_completion_reaches_each_scoring_document():
    rows,load,_=fixture()
    enriched,_=complete_tables(rows,load,independent_candidates=True)
    row=enriched[1];row['rerank_table_completion']=row.pop('table_completion')
    text=structure_context_text(row)
    assert 'USD millions' in text and '2025' in text
    assert 'context, not independent evidence' in text
    assert row['content']==rows[1]['content']
    altered=deepcopy(row);altered['rerank_table_completion']['contexts'][0]['text']+='!'
    with pytest.raises(ValueError,match='identity_mismatch'):structure_context_text(altered)


def test_rerank_request_key_binds_structural_context_and_preserves_current_checks(tmp_path):
    from test_scoped_reranking import fixture as scorer_fixture
    scorer,_,calls=scorer_fixture(tmp_path)
    rows,load,_=fixture()
    kwargs=dict(scope='organization:test',index_digest='a'*64,check_access=lambda:None)
    legacy=scorer.rank('Cash',rows,**kwargs)[1]
    rows,_=complete_tables(rows,load,independent_candidates=True)
    for row in rows:row['rerank_table_completion']=row.pop('table_completion')
    fresh=scorer.rank('Cash',rows,**kwargs)[1]
    assert fresh['request_key']!=legacy['request_key']
    assert 'unit_statement' in calls[1][1][1]
    assert scorer.rank('Cash',rows,**kwargs)[1]['cache_hit']
    def deny():raise PermissionError('revoked')
    with pytest.raises(PermissionError):scorer.rank('Cash',rows,**{**kwargs,'check_access':deny})
