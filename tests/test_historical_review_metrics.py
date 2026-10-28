import json
from hashlib import sha256
import pytest
from scripts.engineering.score_retrieval_review_pool import score, ordering_diagnostics, candidate_diagnostics


def fixture(tmp_path):
    pools=tmp_path/'pools';batch=pools/'historical';batch.mkdir(parents=True)
    judgments=tmp_path/'judgments';judgments.mkdir()
    rows=[{'node_id':n,'content':n,'content_sha256':sha256(n.encode()).hexdigest(),
           'ranks':{'selected':i}} for i,n in enumerate(('a','b'),1)]
    for q in ('reviewed','unreviewed'):
        (batch/(q+'.json')).write_text(json.dumps({'question':{'id':q,'query':q},'candidates':rows}))
    (judgments/'reviewed.json').write_text(json.dumps([
        {'question_id':'reviewed','query_sha256':sha256(b'reviewed').hexdigest(),
         'node_id':r['node_id'],'content_sha256':r['content_sha256'],'grade':3 if i==0 else 0,
         'reason':'Explicit synthetic review'} for i,r in enumerate(rows)]))
    return pools,judgments,batch


def test_unreviewed_queries_prevent_full_batch_precision_and_zero_label_substitution(tmp_path):
    pools,judgments,_=fixture(tmp_path)
    batch=score(pools,judgments)['batches'][0]
    summary=batch['stages']['selected']
    assert summary['precision_at_10_macro'] is None
    assert summary['fully_reviewed_queries']==1 and summary['unjudged_top10']==2
    known=next(s for s in batch['samples'] if s['id']=='reviewed')['stages']['selected']
    assert known['precision']==.1 and known['returned_precision']==.5
    assert known['irrelevant_results']==1 and known['pooled_graded_ndcg']==1


def test_changed_query_does_not_inherit_identical_body_judgments(tmp_path):
    pools,judgments,batch=fixture(tmp_path);path=batch/'reviewed.json'
    data=json.loads(path.read_text());data['question']['query']='different period'
    path.write_text(json.dumps(data))
    summary=score(pools,judgments)['batches'][0]['stages']['selected']
    assert summary['fully_reviewed_queries']==0 and summary['unjudged_top10']==4


def test_changed_body_or_missing_display_position_fails_closed(tmp_path):
    pools,judgments,batch=fixture(tmp_path);path=batch/'reviewed.json';data=json.loads(path.read_text())
    data['candidates'][0]['content']='edited'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='content_changed'):score(pools,judgments)
    data['candidates'][0]['content']='a';data['candidates'][0]['ranks']['selected']=3
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='missing_top10_rank'):score(pools,judgments)


def test_unreviewed_pool_tail_does_not_inflate_ndcg_or_recall(tmp_path):
    pools,judgments,batch=fixture(tmp_path)
    (batch/'unreviewed.json').unlink()
    path=batch/'reviewed.json';data=json.loads(path.read_text())
    # This candidate was recalled by another channel but not displayed. Its
    # relevance can change IDCG and recall even though Precision is unaffected.
    data['candidates'].append({'node_id':'outside','content':'outside',
        'content_sha256':sha256(b'outside').hexdigest(),'ranks':{'selected':None}})
    path.write_text(json.dumps(data))
    output=score(pools,judgments)['batches'][0]
    result=output['samples'][0]['stages']['selected']
    assert result['precision']==.1 and result['unjudged']==0
    assert result['pooled_graded_ndcg'] is None and result['pooled_recall'] is None
    summary=output['stages']['selected']
    assert summary['all_queries_top10_reviewed'] and not summary['all_query_pools_reviewed']
    assert summary['precision_at_10_macro']==.1
    assert summary['pooled_graded_ndcg_at_10_macro'] is None
    labelpath=judgments/'reviewed.json';labels=json.loads(labelpath.read_text())
    labels.append({'question_id':'reviewed','query_sha256':sha256(b'reviewed').hexdigest(),
        'node_id':'outside','content_sha256':sha256(b'outside').hexdigest(),
        'grade':3,'reason':'A relevant alternative in another channel'})
    labelpath.write_text(json.dumps(labels))
    completed=score(pools,judgments)['batches'][0]['samples'][0]['stages']['selected']
    assert 0<completed['pooled_graded_ndcg']<1
    assert completed['pooled_recall']==.5


def test_channel_scores_are_original_not_rank_proxies_and_unknown_is_not_negative():
    candidates=[{'node_id':'bad','content_sha256':'digest','ranks':{'dense_candidates':1},
        'raw_bm25_score':31.2,'dense_score':-.03,'historical_rerank_score':.91},
        {'node_id':'unknown','content_sha256':'other','ranks':{'reranked':2}}]
    rows=candidate_diagnostics(candidates,{'bad':0},{'bad':{'reason':'Wrong period'}})
    assert rows[0]['scores']==dict(raw_bm25_score=31.2,dense_score=-.03,historical_rerank_score=.91)
    assert rows[1]['grade'] is None and rows[1]['reason'] is None
    assert all(value is None for value in rows[1]['scores'].values())
    assert len(rows[1]['missing_score_channels'])==3


@pytest.mark.parametrize('value',[True,float('nan'),float('inf'),'0.9'])
def test_non_numeric_or_nonfinite_scores_cannot_enter_diagnostics(value):
    with pytest.raises(ValueError,match='invalid_channel_score'):
        candidate_diagnostics([{'node_id':'a','content_sha256':'x','ranks':{},'dense_score':value}],{}, {})


def test_ordering_audit_counts_only_wrong_above_direct_with_tail_and_absence_separate():
    ranks={1:'unknown',2:'wrong',3:'context',4:'answer',11:'tail',12:'wrong_tail'}
    grades={'wrong':0,'context':1,'answer':3,'tail':2,'wrong_tail':0,'absent':2}
    result=ordering_diagnostics(ranks,grades)
    assert result['reviewed_irrelevant_top10_above_direct_evidence_pairs']==2
    assert result['reviewed_irrelevant_top10_above_direct_evidence_nodes']==['wrong']
    assert result['reviewed_direct_evidence_absent_from_stage']==['absent']
