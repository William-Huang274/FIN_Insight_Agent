from hashlib import sha256
import json
import sqlite3
import zlib
import pytest
from scripts.engineering.review_retrieval_rankings import review


def test_source_verified_review_never_treats_missing_judgments_as_negatives(tmp_path):
    records=[]
    with sqlite3.connect(tmp_path/'navigation.sqlite') as db:
        db.execute('CREATE TABLE nodes(node_id TEXT PRIMARY KEY,payload BLOB)')
        for n,body in [('a','Cash is 10 million.'),('b','Signature.')]:
            digest=sha256(body.encode()).hexdigest()
            row={'node_id':n,'content':body,'original_source':{'id':n},'title':'Report'}
            raw=json.dumps(row).encode()
            records.append({'node_id':n,'content_sha256':digest,'navigation_sha256':sha256(raw).hexdigest()})
            db.execute('INSERT INTO nodes VALUES(?,?)',(n,zlib.compress(raw)))
    inputs={'index':{'records':records},'dataset':{'questions':[{'id':'q','query':'cash amount'}]},
            'result':{'samples':[{'id':'q','rankings':{'selected':['a','b']},'gold':['a']}]}}
    for name,value in inputs.items():(tmp_path/(name+'.json')).write_text(json.dumps(value))
    args=[tmp_path/(n+'.json') for n in ('result','dataset','index')]
    first=review(*args,tmp_path/'first')
    assert first['precision_at_10'] is None and first['pooled_ndcg_at_10'] is None
    assert first['samples'][0]['known_evidence_all_at_10'] is True
    judgments=[{'question_id':'q','node_id':r['node_id'],'content_sha256':r['content_sha256'],
                'query_sha256':sha256(b'cash amount').hexdigest(),'grade':3 if i==0 else 0,
                'reason':'Answer fact' if i==0 else 'Signature has no requested fact'} for i,r in enumerate(records)]
    path=tmp_path/'judgments.json';path.write_text(json.dumps(judgments))
    second=review(*args,tmp_path/'second',path)
    assert second['precision_at_10']==.1 and second['pooled_ndcg_at_10']==1
    assert second['equivalent_evidence_recall'] is None
    judgments[0]['query_sha256']='b'*64;path.write_text(json.dumps(judgments))
    with pytest.raises(ValueError,match='changed_question'):review(*args,tmp_path/'third',path)
