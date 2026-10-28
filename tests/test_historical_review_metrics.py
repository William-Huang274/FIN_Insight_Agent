import json
from hashlib import sha256
import pytest
from scripts.engineering.score_retrieval_review_pool import score


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
