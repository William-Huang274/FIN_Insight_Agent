"""Explicit source-checked evaluation query embeddings; no Agent, no retries."""
import argparse
from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path

from scripts.engineering.organization_recall_evaluation import validate_questions
from scripts.engineering.retrieval_evaluation_freeze import validate_heldout_freeze
from tests.integration.source_intake_diagnostics import SourceBundles
from retrieval.qwen_api import QwenRetrieval
from retrieval.query_embeddings import QueryEmbeddingSource


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('dataset','intake','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--split',choices=['development','heldout'],required=True)
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    raw=args.dataset.read_bytes(); dataset=json.loads(raw)
    intake=json.loads((args.intake/'result.json').read_text(encoding='utf8'))
    if intake['status']!='verified' or intake['library_sha256']!=dataset['library_sha256']:
        raise ValueError('query_preparation_source_snapshot_mismatch')
    if args.split=='heldout' and dataset.get('freeze',{}).get('status')!='frozen':
        raise ValueError('heldout_requires_frozen_dataset_and_policy')
    validate_heldout_freeze(dataset, args.split)
    bundles=SourceBundles((r['source_id'],args.intake/r['directory']/'source.json') for r in intake['sources'])
    rows=[r for r in validate_questions(dataset,bundles) if r['split']==args.split]
    if not rows or len(rows)>200:raise ValueError('query_preparation_scope_outside_budget')
    model=intake['source_index']['embedding_model']; matrix=intake['source_index']['matrix_sha256']
    basis={'purpose':'New source-first organization retrieval development/evaluation query vectors',
        'dataset_sha256':sha256(raw).hexdigest(),'split':args.split,'model':model,'matrix_sha256':matrix,
        'input_scale':{'queries':len(rows),'utf8_bytes':sum(len(r['query'].encode()) for r in rows)},
        'required_output':'One 1024-dimensional vector and durable provider receipt per query',
        'quality_risk':'Known evidence labels only; pooled equivalence review may be pending; no financial answer generation',
        'reasoning_profile':'Embedding only, no reranking or generation',
        'limits':{'requests_max':len(rows),'concurrency':1,'sdk_retries':0,'timeout_seconds':45},
        'stop_behavior':'Stop at first failure; failed/unknown calls stay blocked after restart; never silently truncate'}
    args.output.mkdir(parents=True,exist_ok=True)
    path=args.output/'TokenBudgetBasis.json'
    if path.exists() and json.loads(path.read_text(encoding='utf8'))!=basis:
        raise ValueError('query_preparation_budget_changed')
    path.write_text(json.dumps(basis,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(basis,ensure_ascii=False),flush=True)
    if not args.execute:return
    report={'status':'running','samples':[],'dataset_sha256':basis['dataset_sha256'],'expected_queries':len(rows)}
    try:
        with closing(QwenRetrieval(os.environ['QWEN_API_KEY'],embedding_model=model)) as api:
            source=QueryEmbeddingSource(args.output/'query-cache',api,model=model)
            for row in rows:
                _,receipt=source.embed(row['query'],scope='public-recall-qualification',
                    index_digest=matrix,model=model,dimensions=1024)
                report['samples'].append({'id':row['id'],'receipt':receipt})
                (args.output/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        report['status']='completed'
    except Exception as error:
        report.update(status='failed',error_type=type(error).__name__)
        raise
    finally:
        (args.output/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'status':report['status'],'completed':len(report['samples']),
        'provider_calls':sum(s['receipt']['provider_calls'] for s in report['samples'])}))


if __name__=='__main__':main()
