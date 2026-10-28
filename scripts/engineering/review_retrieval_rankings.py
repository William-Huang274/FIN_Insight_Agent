"""Build a source-verified relevance review pool for a frozen retrieval run.

Known evidence coverage and graded relevance are separate. Unjudged candidates
remain unknown; they are never implicitly counted as irrelevant. No API calls.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import zlib
from retrieval.relevance_metrics import ranking_metrics


def review(result_path, dataset_path, index_path, output, judgments_path=None):
    result=json.loads(result_path.read_bytes())
    dataset=json.loads(dataset_path.read_bytes())
    index=json.loads(index_path.read_bytes())
    questions={q['id']:q for q in dataset['questions']}
    records={r['node_id']:r for r in index['records']}
    judgments=json.loads(judgments_path.read_bytes()) if judgments_path else []
    grades={};reasons={}
    for j in judgments:
        key=(j['question_id'],j['node_id'])
        if key in grades:raise ValueError('review_duplicate_judgment')
        if j['content_sha256']!=records[j['node_id']]['content_sha256']:
            raise ValueError('review_judgment_changed_original')
        if j['query_sha256']!=sha256(questions[j['question_id']]['query'].encode()).hexdigest():
            raise ValueError('review_judgment_changed_question')
        if not j.get('reason'):raise ValueError('review_judgment_requires_reason')
        grades[key]=j['grade']
        reasons[key]=j['reason']
    output.mkdir(parents=True,exist_ok=False)
    metrics=[]
    db=sqlite3.connect(index_path.parent.joinpath('navigation.sqlite').as_uri()+'?mode=ro',uri=True)
    try:
        for sample in result['samples']:
            q=questions[sample['id']]
            if not q['id'] or any(c in q['id'] for c in '/\\:') or q['id'] in {'.','..'}:
                raise ValueError('review_invalid_question_id')
            rankings=sample.get('rankings') or {'reranked':sample['ranked_ids'],'selected':sample['selected_ids']}
            selected=rankings['selected']
            pool=list(dict.fromkeys([n for ranked in rankings.values() for n in ranked[:10]]+sample.get('gold',[])))
            receipt=sample.get('rerank_receipt') or sample.get('receipt') or {}
            scores=dict(receipt.get('scores',[])); rows=[]
            for n in pool:
                record=records[n]
                value=db.execute('SELECT payload FROM nodes WHERE node_id=?',(n,)).fetchone()
                if not value:raise ValueError('review_missing_original')
                raw=zlib.decompress(value[0])
                if sha256(raw).hexdigest()!=record['navigation_sha256']:
                    raise ValueError('review_changed_navigation')
                row=json.loads(raw)
                if row['node_id']!=n or sha256(row['content'].encode()).hexdigest()!=record['content_sha256']:
                    raise ValueError('review_changed_body')
                rows.append({'question_id':q['id'],'query_sha256':sha256(q['query'].encode()).hexdigest(),
                    'node_id':n,'content_sha256':record['content_sha256'],'title':row.get('title'),
                    'original_source':row['original_source'],'content':row['content'],
                    'ranks':{channel:(ranked.index(n)+1 if n in ranked else None) for channel,ranked in rankings.items()},
                    'historical_rerank_score':scores.get(n),'raw_bm25_score':None,'dense_score':None,
                    'numeric_score_scope':'only_saved_provider_rerank_scores_no_invented_channel_scores',
                    'grade':grades.get((q['id'],n)), 'reason':reasons.get((q['id'],n))})
            qrels={n:g for (question,n),g in grades.items() if question==q['id']}
            scored=ranking_metrics(selected,qrels)
            gold=set(sample.get('gold',[]))
            metrics.append({'id':q['id'],'kind':q.get('question_kind',sample.get('kind')),
                **scored,'known_evidence_hit_at_10':bool(gold & set(selected[:10])) if gold else None,
                'known_evidence_all_at_10':gold <= set(selected[:10]) if gold else None,
                'review_pool_size':len(pool)})
            (output/(q['id']+'.json')).write_text(json.dumps({'question':q,'candidates':rows},ensure_ascii=False),encoding='utf8')
    finally:db.close()
    complete=all(m['unjudged']==0 for m in metrics)
    summary={'role':'historical_exposed_regression_not_new_holdout','provider_calls':0,
        'input_sha256':{str(p):sha256(p.read_bytes()).hexdigest() for p in (result_path,dataset_path,index_path)},
        'questions':len(metrics),'all_top10_judged':complete,
        'precision_at_10':sum(m['precision'] for m in metrics)/len(metrics) if complete and metrics else None,
        'pooled_ndcg_at_10':sum(m['pooled_graded_ndcg'] for m in metrics)/len(metrics)
            if metrics and all(m['pooled_graded_ndcg'] is not None for m in metrics) else None,
        'equivalent_evidence_recall':None,'pool_scope':'union_channel_top10_plus_known_evidence_not_exhaustive',
        'samples':metrics}
    (output/'metrics.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('result','dataset','index','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--judgments',type=Path)
    a=p.parse_args();r=review(a.result,a.dataset,a.index,a.output,a.judgments)
    print(json.dumps({k:r[k] for k in ('questions','all_top10_judged','precision_at_10','pooled_ndcg_at_10')}))
