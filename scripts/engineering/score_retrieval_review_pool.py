"""Score frozen historical pools against explicitly reviewed query/body pairs.

Unreviewed passages are never negatives. A fully reviewed subset must not be
reported as a complete batch. This command makes no model or service calls.
"""
from hashlib import sha256
import argparse
import json
from pathlib import Path
from statistics import mean

from retrieval.relevance_metrics import ranking_metrics


def score(pools, judgments):
    labels={};provenance=[]
    for path in sorted(Path(judgments).glob('*.json')):
        raw=path.read_bytes();rows=json.loads(raw)
        provenance.append({'file':path.name,'sha256':sha256(raw).hexdigest()})
        for row in rows:
            key=(row['question_id'],row['query_sha256'],row['node_id'],row['content_sha256'])
            if type(row['grade']) is not int or not 0<=row['grade']<=3 or not row.get('reason'):
                raise ValueError('review_requires_explicit_grade_and_reason')
            if key in labels and labels[key]['grade']!=row['grade']:
                raise ValueError('review_conflicting_judgments')
            labels[key]=row
    batches=[]
    for batch in sorted(Path(pools).iterdir()):
        if not batch.is_dir():continue
        samples=[]
        for path in sorted(batch.glob('*.json')):
            raw=path.read_bytes();pool=json.loads(raw)
            if 'question' not in pool or 'candidates' not in pool:continue
            question=pool['question'];qhash=sha256(question['query'].encode()).hexdigest()
            qrels={};seen=set();rankings={};bodies={}
            for row in pool['candidates']:
                node=row['node_id'];bodyhash=sha256(row['content'].encode()).hexdigest()
                if bodyhash!=row['content_sha256']:raise ValueError('review_pool_content_changed')
                if node in seen:raise ValueError('review_pool_duplicate_node')
                seen.add(node);bodies[node]=bodyhash
                label=labels.get((question['id'],qhash,node,bodyhash))
                if label is not None:qrels[node]=label['grade']
                for stage,rank in row['ranks'].items():
                    if rank is None:continue
                    if type(rank) is not int or rank<1:raise ValueError('review_invalid_rank')
                    if rank in rankings.setdefault(stage,{}):raise ValueError('review_duplicate_rank')
                    rankings[stage][rank]=node
            stages={}
            for stage,ranks in rankings.items():
                # Pool preparation must retain every displayed position. A gap
                # cannot silently move rank 11 into the top ten.
                expected=set(range(1,min(10,max(ranks))+1))
                if not expected<=ranks.keys():raise ValueError('review_missing_top10_rank')
                page=[ranks[i] for i in sorted(expected)]
                metrics=ranking_metrics(page,qrels)
                relevant=sum(qrels.get(n,-1)>=2 for n in page)
                metrics.update(returned_precision=(relevant/len(page) if page and not metrics['unjudged'] else None),
                    irrelevant_results=sum(qrels.get(n)==0 for n in page),
                    context_only_results=sum(qrels.get(n)==1 for n in page),
                    unique_returned_bodies=len({bodies[n] for n in page}))
                stages[stage]=metrics
            samples.append({'id':question['id'],'pool_file_sha256':sha256(raw).hexdigest(),
                'query_sha256':qhash,'pool_count':len(seen),'judged_pool_count':len(qrels),'stages':stages})
        summaries={}
        for stage in sorted({s for item in samples for s in item['stages']}):
            values=[item['stages'].get(stage) for item in samples]
            full=len(values)>0 and all(v is not None and not v['unjudged'] for v in values)
            known=[v for v in values if v is not None and not v['unjudged']]
            def average(field):
                nums=[v[field] for v in values if v is not None and v[field] is not None]
                return mean(nums) if full and len(nums)==len(values) else None
            summaries[stage]={'all_queries_top10_reviewed':full,'fully_reviewed_queries':len(known),
                'precision_at_10_macro':average('precision'),
                'returned_precision_macro':average('returned_precision'),
                'pooled_graded_ndcg_at_10_macro':average('pooled_graded_ndcg'),
                'pooled_recall_at_10_macro':average('pooled_recall'),
                'unjudged_top10':sum(v['unjudged'] for v in values if v is not None)}
        batches.append({'batch':batch.name,'questions':len(samples),'stages':summaries,'samples':samples})
    return {'role':'historical_review_coverage_and_metrics_not_current_acceptance',
        'provider_calls':0,'judgment_files':provenance,'batches':batches,
        'precision_denominator':10,'returned_precision_denominator':'actual_displayed_results; empty is undefined',
        'ndcg_ideal':'all_explicitly_judged_pool_candidates; not_exhaustive_corpus',
        'all_equivalent_evidence_recall':None,'unreviewed_are_not_negatives':True}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('pools','judgments','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();result=score(args.pools,args.judgments)
    with args.output.open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({'batches':len(result['batches']),'review_files':len(result['judgment_files'])}))
