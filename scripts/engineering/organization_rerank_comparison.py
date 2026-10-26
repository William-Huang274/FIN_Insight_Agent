"""Development-only fixed-candidate Qwen comparison; plan first, no retry.

This reads a frozen PUBLIC qualification release, not live organization data.
Service authorization, independent evaluation and latency gates remain separate.
"""
import argparse
from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import time
import zlib

from retrieval.scoped_reranking import ScopedReranker
from scripts.engineering.organization_ranking_ablation import compare
from scripts.engineering.qualify_retrieval_recall import ranking_metrics


def prepare(result_path,dataset_path,index_path,navigation_path=None):
    raw=result_path.read_bytes(); saved=json.loads(raw)
    index_raw=index_path.read_bytes(); index=json.loads(index_raw)
    if sha256(index_raw).hexdigest()!=saved['index_sha256']:
        raise ValueError('rerank_original_candidate_index_mismatch')
    compare(saved,index)  # Complete samples, exact baseline RRF, development-only.
    if saved.get('split')!='development':
        raise ValueError('rerank_requires_development_split')
    dataset_raw=dataset_path.read_bytes(); dataset=json.loads(dataset_raw)
    if sha256(dataset_raw).hexdigest()!=saved['dataset_sha256']:
        raise ValueError('rerank_original_query_dataset_mismatch')
    questions={r['id']:r for r in dataset['questions'] if r['split']=='development'}
    records={r['node_id']:r for r in index['records']}
    jobs=[]
    navigation_path=navigation_path or index_path.parent/'navigation.sqlite'
    uri=navigation_path.resolve().as_uri()+'?mode=ro'
    with closing(sqlite3.connect(uri,uri=True)) as db:
        for sample in saved['samples']:
            question=questions[sample['id']]
            for channel in ('fused_candidates','graph_fused_candidates'):
                if channel not in sample['rankings']:continue
                ids=sample['rankings'][channel]
                if not 1<=len(ids)<=48:raise ValueError('rerank_candidate_budget')
                candidates=[]
                for node in ids:
                    row=db.execute('SELECT payload FROM nodes WHERE node_id=?',(node,)).fetchone()
                    if row is None:raise ValueError('rerank_missing_candidate')
                    payload=zlib.decompress(row[0])
                    if sha256(payload).hexdigest()!=records[node]['navigation_sha256']:
                        raise ValueError('rerank_navigation_hash_mismatch')
                    candidate=json.loads(payload)
                    if candidate['node_id']!=node:raise ValueError('rerank_candidate_identity_mismatch')
                    candidates.append(candidate)
                job={'id':sample['id'],'family':sample['family'],'query':question['query'],
                     'channel':channel,'gold':sample['gold'],'candidates':candidates}
                if 'search_needs' in sample:
                    job['search_needs']=sample['search_needs']
                jobs.append(job)
    plan={'purpose':'Development fixed-candidate comparison: equal RRF versus Qwen3 rerank',
        'result_sha256':sha256(raw).hexdigest(),'dataset_sha256':sha256(dataset_raw).hexdigest(),
        'index_sha256':sha256(index_raw).hexdigest(),'jobs':len(jobs),
        'navigation_path':str(navigation_path),'navigation_validation':'each decompressed payload matched original index SHA256',
        'TokenBudgetBasis':{'purpose':'Measure whether reranking recovers known evidence already in the candidate union',
            'input_scale':{'requests_max':len(jobs),'candidates':sum(len(j['candidates']) for j in jobs),
                           'utf8_bytes':sum(len((c.get('embedding_context','')+'\n'+c['content']).encode()) for j in jobs for c in j['candidates'])},
            'required_output':'Complete candidate rank and provider usage per request',
            'quality_risk':'Development only; not blind recall, full relevance judgments or financial quality',
            'reasoning_profile':'qwen3-rerank only; no generative model',
            'limits':{'requests':len(jobs),'candidates_per_request':48},
            'stop_behavior':'Stop at first error; keep failed/unknown receipts; never resubmit'},
        'samples':[{'id':j['id'],'channel':j['channel'],'query_sha256':sha256(j['query'].encode()).hexdigest(),
                    'candidate_ids':[c['node_id'] for c in j['candidates']]} for j in jobs]}
    if any('search_needs' in job for job in jobs):
        from retrieval import organization_search_needs
        metadata_raw=(result_path.parent/'source-metadata.json').read_bytes()
        metadata=json.loads(metadata_raw)['resolved']
        for job in jobs:job['source_metadata']=metadata
        plan['selection_contract']={'policy':organization_search_needs.POLICY,
            'implementation_sha256':sha256(Path(organization_search_needs.__file__).read_bytes()).hexdigest(),
            'metadata_sha256':sha256(metadata_raw).hexdigest(),
            'scope':'query-derived candidate coverage, not answer sufficiency'}
    return jobs,plan


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('result','dataset','index','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--navigation',type=Path)
    parser.add_argument('--env-file',type=Path)
    parser.add_argument('--receipt-cache',type=Path,help='Reuse exact successful public development receipts; failed/unknown requests remain blocked')
    args=parser.parse_args()
    jobs,plan=prepare(args.result,args.dataset,args.index,args.navigation)
    args.output.mkdir(parents=True,exist_ok=True)
    planned=args.output/'plan.json'
    if planned.exists() and json.loads(planned.read_text(encoding='utf8'))!=plan:
        raise ValueError('rerank_plan_changed_new_review_required')
    planned.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf8')
    if not args.execute:
        print(json.dumps(plan['TokenBudgetBasis'],ensure_ascii=False)); return
    if args.env_file:
        from dotenv import dotenv_values
        key=dotenv_values(args.env_file).get('QWEN_API_KEY')
    else:key=os.environ.get('QWEN_API_KEY')
    if not key:raise ValueError('configured_qwen_key_unavailable')
    from retrieval.qwen_api import QwenRetrieval
    api=QwenRetrieval(key,embedding_model='qwen3.7-text-embedding')
    receipt_cache=args.receipt_cache or args.output/'provider-records'
    source=ScopedReranker(receipt_cache,api)
    report={'status':'running','S2_passed':False,'evaluation_role':'development_fixed_candidates',
            'expected_jobs':len(jobs),'samples':[],'plan_sha256':sha256(planned.read_bytes()).hexdigest(),
            'receipt_cache':str(receipt_cache)}
    try:
        for job in jobs:
            start=time.perf_counter()
            # Sources are already frozen public qualification inputs. This
            # callback deliberately does NOT claim current organization ACL.
            ranked,receipt=source.rank(job['query'],job['candidates'],scope='qualification:development-rerank',
                index_digest=plan['index_sha256'],check_access=lambda:None)
            report['samples'].append({k:job[k] for k in ('id','family','channel','gold')})
            report['samples'][-1].update(seconds=time.perf_counter()-start,receipt=receipt,
                candidate_count=len(ranked),ranked_ids=[r['node_id'] for r in ranked],
                baseline=ranking_metrics([r['node_id'] for r in job['candidates']],job['gold']),
                reranked=ranking_metrics([r['node_id'] for r in ranked],job['gold']))
            if 'search_needs' in job:
                from retrieval.organization_search_needs import select_coverage
                needs=job['search_needs']
                selected,coverage=select_coverage(ranked,needs['search_needs'],needs['lexical_needs'],job['source_metadata'])
                report['samples'][-1].update(selected_ids=[r['node_id'] for r in selected],
                    need_coverage=coverage,selected=ranking_metrics([r['node_id'] for r in selected],job['gold']))
            (args.output/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
            if len(report['samples'])%10==0:
                print(json.dumps({'completed':len(report['samples']),'expected':len(jobs)}),flush=True)
        report['status']='completed'
    except Exception as error:
        report.update(status='failed',error_type=type(error).__name__,error=str(error))
        raise
    finally:
        api.close()
        (args.output/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'status':report['status'],'jobs':len(report['samples']),
        'provider_calls':sum(s['receipt']['provider_calls'] for s in report['samples']),
        'baseline_hit10':sum(s['baseline']['known_hit@10'] for s in report['samples']),
        'rerank_hit10':sum(s['reranked']['known_hit@10'] for s in report['samples'])}))


if __name__=='__main__':main()
