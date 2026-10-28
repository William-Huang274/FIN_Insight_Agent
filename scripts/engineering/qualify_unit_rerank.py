"""Freeze full service scoring inputs, then explicitly run bounded reranking.

Exposed regression diagnostic only. Reuses production candidate/context/final
selection functions; a frozen local source guard is not a current Java grant.
"""
import argparse
from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path
import time
from types import SimpleNamespace
import psutil


def digest(path):return sha256(Path(path).read_bytes()).hexdigest()


def prepare(index_path,overlay,contexts,metadata_path,queries_path,output):
    from scripts.engineering.frozen_retrieval_context import FrozenRetrievalContext
    from retrieval.semantic_unit_index import rank,validate
    from retrieval.published_lexical_index import PublishedLexicalStatistics
    from retrieval.organization_search_needs import compile_needs
    from retrieval.evidence_scope import resolve_scope,select_scoped
    from retrieval.organization_candidate_preparation import prepare_candidates
    from retrieval.scoped_reranking import scoring_documents
    from retrieval.graph_query_plan import graph_seeds
    from sec_agent.research_foundation.organization_query_plan import plan_query,select_planned
    from sec_agent.research_foundation.organization_index_release import canonical_digest
    from retrieval.relevance_instruction import configured_instruction
    from retrieval.relevance_boundary_runtime import configured_boundary,pipeline_identity
    model='qwen3.7-text-rerank';instruction=configured_instruction(model)
    boundary=configured_boundary('research.v2',SimpleNamespace(model=model,instruction=instruction),'bounded.v1')
    index=json.loads(index_path.read_bytes());publication=json.loads((overlay/'overlay.json').read_bytes())
    if canonical_digest(index)!=publication['snapshot_digest']:raise ValueError('unit_quality_snapshot_changed')
    allowed=set(publication['parent_scope']);records=[r for r in index['records'] if r['node_id'] in allowed]
    validate(overlay,publication['descriptor'],records,index['model'])
    metadata=json.loads(metadata_path.read_bytes());queries=json.loads(queries_path.read_bytes())['questions']
    output.mkdir(parents=True,exist_ok=False);jobs=[];total_bytes=0;total_candidates=0
    statistics=PublishedLexicalStatistics()
    with closing(FrozenRetrievalContext(index_path,contexts,index=index,
            retained_documents={r['document_id'] for r in records})) as adapter:
        metadata.update(adapter.source_metadata)
        for q in queries:
            import gc
            gc.collect()
            if psutil.virtual_memory().available<800*2**20:raise RuntimeError('unit_quality_memory_guard')
            documents,plan=select_planned(metadata,plan_query(q['query'],metadata,policy='conservative.v5'))
            required={r['node_id'] for r in index['records'] if r['document_id'] in documents}
            if required-allowed:raise ValueError('unit_quality_scope_not_fully_published')
            rows=[r for r in adapter.rows.values() if r['parent_document_id'] in documents]
            wanted=resolve_scope(q['query'],plan);scope_receipt=None
            if wanted:rows,scope_receipt=select_scoped(rows,wanted)
            needs=compile_needs(q['query'],plan)
            seeds,basis=graph_seeds(SimpleNamespace(entity_id=None,organization_query_planning='conservative.v5',query=q['query']),plan)
            if seeds:raise ValueError('unit_quality_relationship_query_requires_reviewed_graph_replay')
            def trace(need,route,samples):
                path=output/f'{q["id"]}.{need}.{route}.jsonl';h=sha256();count=0
                with path.open('xb') as stream:
                    for sample in samples:
                        raw=(json.dumps(sample,ensure_ascii=False)+'\n').encode();stream.write(raw);h.update(raw);count+=1
                return {'file':path.name,'sha256':h.hexdigest(),'count':count,'complete_population':True}
            entry,receipt=rank(overlay,rows,q['vector'],needs,metadata,wanted,policy='needs_units.v1',
                population_cache=statistics,capture_trace=True,trace_sink=trace)
            eligible=set(receipt.pop('_eligible_parent_ids'));rows=[r for r in rows if r['node_id'] in eligible]
            candidates,context_receipt=prepare_candidates(adapter,[adapter.rows[n] for n in entry['ordered']],rows,
                {'project_id':'offline-qualification'},needs=needs,wanted=wanted,document_context=True,table_context=True)
            texts=scoring_documents(candidates);total_bytes+=sum(len(t.encode()) for t in texts);total_candidates+=len(candidates)
            job={'id':q['id'],'query':q['query'],'candidates':candidates,'plan':plan,'needs':needs,
                'channels':entry,'retrieval_receipt':receipt,'context_receipt':context_receipt,
                'evidence_scope':scope_receipt,'provider_input_sha256':[sha256(t.encode()).hexdigest() for t in texts],
                'metadata':{d:metadata[d] for d in {r['parent_document_id'] for r in candidates}}}
            path=output/f'{q["id"]}.input.json';path.write_text(json.dumps(job,ensure_ascii=False),encoding='utf8')
            jobs.append({'id':q['id'],'input_sha256':digest(path)})
            print(json.dumps({'prepared':len(jobs),'total':len(queries),'id':q['id'],'candidates':len(candidates)}),flush=True)
    root=Path(__file__).resolve().parents[2]
    code={str(p):digest(p) for folder in ('src/retrieval','src/sec_agent/research_foundation') for p in (root/folder).glob('*.py')}
    for name in ('qualify_unit_rerank.py','frozen_retrieval_context.py'):
        path=root/'scripts/engineering'/name;code[str(path)]=digest(path)
    plan={'role':'exposed_regression_full_scoring_not_live_HTTP','jobs':jobs,'code_sha256':code,
        'instruction':instruction,'relevance_boundary':boundary.artifact if boundary else None,
        'pipeline':pipeline_identity('research.v2',model,instruction,'bounded.v1'),
        'inputs':{str(p):digest(p) for p in (index_path,overlay/'overlay.json',contexts/'context.json',metadata_path,queries_path)},
        'index_digest':canonical_digest(index),'TokenBudgetBasis':{
            'purpose':'Verify original-unit recall and complete production structural scoring before final page selection',
            'input_scale':{'queries':len(jobs),'candidate_occurrences':total_candidates,'utf8_bytes':total_bytes},
            'required_output':'Full ranks, scores, usage and final selected IDs for reviewed relevance evaluation',
            'quality_risk':'Exposed 44-query regression; no independent quality, live authorization or capacity claim',
            'reasoning_profile':'qwen3.7-text-rerank only; no Agent or financial answer generation',
            'limits':{'requests':len(jobs),'candidates_per_request':48,'concurrency':1,'automatic_retries':0},
            'stop_behavior':'Stop first failed/unknown paid response or memory below 800 MiB; persist receipts; never resubmit'}}
    (output/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf8')
    return plan['TokenBudgetBasis']


def run(output):
    from retrieval.scoped_reranking import ScopedReranker,scoring_documents
    from retrieval.qwen_api import QwenRetrieval
    from retrieval.organization_search_needs import select_coverage
    from retrieval.original_result_groups import collapse_original_duplicates
    plan=json.loads((output/'plan.json').read_bytes())
    for path,expected in plan['inputs'].items():
        if digest(path)!=expected:raise ValueError('unit_quality_frozen_input_changed')
    def check():
        if psutil.virtual_memory().available<800*2**20:raise RuntimeError('unit_quality_memory_guard')
        if any(digest(p)!=expected for p,expected in plan['code_sha256'].items()):raise RuntimeError('unit_quality_code_changed')
    check();result={'status':'running','plan_sha256':digest(output/'plan.json'),'samples':[],
                    'provider_calls':0,'live_authorization_tested':False,'independent_evaluation':False}
    path=output/'result.json'
    with path.open('x',encoding='utf8') as stream:json.dump(result,stream)
    with closing(QwenRetrieval(os.environ['QWEN_API_KEY'],rerank_model='qwen3.7-text-rerank')) as api:
        reranker=ScopedReranker(output/'receipts',api)
        from retrieval.relevance_boundary_runtime import ResultBoundary
        boundary=ResultBoundary(plan['relevance_boundary'],plan['pipeline']) if plan.get('relevance_boundary') else None
        for item in plan['jobs']:
            input_path=output/f'{item["id"]}.input.json'
            if digest(input_path)!=item['input_sha256']:raise ValueError('unit_quality_job_changed')
            job=json.loads(input_path.read_bytes());start=time.perf_counter()
            if [sha256(t.encode()).hexdigest() for t in scoring_documents(job['candidates'])]!=job['provider_input_sha256']:
                raise ValueError('unit_quality_provider_input_parity_failed')
            try:
                ranked,receipt=reranker.rank(job['query'],job['candidates'],scope='qualification:'+plan['index_digest'],
                    index_digest=plan['index_digest'],check_access=check,instruct=plan.get('instruction'))
                selected,coverage=select_coverage(ranked,job['needs'],job['retrieval_receipt']['lexical_needs'],job['metadata'])
                selected,groups=collapse_original_duplicates(selected)
                boundary_receipt=None
                if boundary:selected,boundary_receipt=boundary.apply(selected,receipt,limit=10)
            except Exception as error:
                result.update(status='stopped',failed_question=item['id'],error_type=type(error).__name__)
                path.write_text(json.dumps(result,indent=2),encoding='utf8');raise
            result['samples'].append({'id':item['id'],'ranked_ids':[r['node_id'] for r in ranked],
                'selected_ids':[r['node_id'] for r in selected],'receipt':receipt,'coverage':coverage,
                'original_result_groups':groups,'seconds':time.perf_counter()-start})
            result['samples'][-1]['relevance_boundary']=boundary_receipt
            result['provider_calls']+=receipt['provider_calls'];path.write_text(json.dumps(result,indent=2),encoding='utf8')
            print(json.dumps({'completed':len(result['samples']),'total':len(plan['jobs']),'id':item['id']}),flush=True)
    result['status']='completed';path.write_text(json.dumps(result,indent=2),encoding='utf8')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    create=sub.add_parser('prepare')
    for key in ('index','overlay','contexts','metadata','queries','output'):create.add_argument('--'+key,type=Path,required=True)
    execute=sub.add_parser('run');execute.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.action=='prepare':print(json.dumps(prepare(a.index,a.overlay,a.contexts,a.metadata,a.queries,a.output),ensure_ascii=False))
    else:run(a.output)
