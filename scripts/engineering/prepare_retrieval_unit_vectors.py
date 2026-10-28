"""Freeze and execute bounded original-unit embedding preparation; no Agent."""
import argparse
from contextlib import closing
from hashlib import file_digest,sha256
import json
import os
from pathlib import Path
import sqlite3
import zlib
import psutil
from retrieval.semantic_unit_catalog import iter_units
from retrieval.unit_embedding_preparation import UnitEmbeddingPreparation


def digest(path):
    with Path(path).open('rb') as stream:return file_digest(stream,'sha256').hexdigest()


def prepare(catalog,scope,output):
    catalog=catalog.resolve();scope=scope.resolve()
    selected=json.loads(scope.read_text(encoding='utf8'))
    allowed=set(selected['parent_node_ids'])
    if not allowed or len(selected['snapshot_digest'])!=64:raise ValueError('unit_vector_preparation_scope_invalid')
    output.mkdir(parents=True,exist_ok=False)
    count=size=batches=0;seen=set();batch=[];batch_bytes=0
    with (output/'jobs.jsonl').open('x',encoding='utf8') as jobs:
        for _,unit,_ in iter_units(catalog,require_new_vector=True):
            if unit['parent_node_id'] not in allowed or unit['embedding_input_sha256'] in seen:continue
            text=unit['embedding_context']+'\n'+unit['content'];length=len(text.encode())
            if length>16384:raise ValueError('unit_input_requires_replanning_no_truncation')
            if batch and (len(batch)==20 or batch_bytes+length>131072):
                jobs.write(json.dumps({'number':batches,'units':batch,'utf8_bytes':batch_bytes})+'\n')
                batches+=1;batch=[];batch_bytes=0
            batch.append({'id':unit['unit_id'],'input_sha256':unit['embedding_input_sha256']})
            batch_bytes+=length;count+=1;size+=length;seen.add(unit['embedding_input_sha256'])
        if batch:
            jobs.write(json.dumps({'number':batches,'units':batch,'utf8_bytes':batch_bytes})+'\n');batches+=1
    if not count:raise ValueError('unit_vector_preparation_has_no_new_inputs')
    from retrieval import semantic_units,unit_embedding_preparation,qwen_api
    code={str(Path(m.__file__).resolve()):digest(m.__file__) for m in (semantic_units,unit_embedding_preparation,qwen_api)}
    code[str(Path(__file__).resolve())]=digest(__file__)
    basis={'purpose':'Prepare exact original-span vectors for frozen retrieval repair validation',
        'input_scale':{'unique_new_vectors':count,'utf8_bytes':size,'parent_scope_size':len(allowed)},
        'required_output':'One 1024-dimensional vector per exact input, model identity and durable usage receipt',
        'quality_risk':'Exposed regression scope; smaller units may lose context; preparation is not retrieval-quality acceptance',
        'reasoning_profile':'qwen3.7-text-embedding only; no generation or Agent research',
        'limits':{'requests':batches,'batch_size':20,'max_input_bytes':16384,'max_batch_bytes':131072,
            'concurrency':1,'automatic_retries':0,'reported_token_stop_cap':size+128*batches},
        'stop_behavior':'Stop on first failed/unknown call, input drift, memory below 800 MiB or disk below 2 GiB; never resubmit or truncate'}
    plan={'format':'original-unit-embedding-plan.v1','catalog':str(catalog),'catalog_sha256':digest(catalog),
        'scope':str(scope),'scope_sha256':digest(scope),'snapshot_digest':selected['snapshot_digest'],
        'jobs_sha256':digest(output/'jobs.jsonl'),'code_sha256':code,'TokenBudgetBasis':basis}
    (output/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(basis,ensure_ascii=False),flush=True)
    return plan


def execute(output):
    from retrieval.qwen_api import QwenRetrieval
    import shutil
    plan=json.loads((output/'plan.json').read_text(encoding='utf8'));catalog=Path(plan['catalog'])
    for path,expected in [(catalog,plan['catalog_sha256']),(Path(plan['scope']),plan['scope_sha256']),
                           (output/'jobs.jsonl',plan['jobs_sha256']),*plan['code_sha256'].items()]:
        if digest(path)!=expected:raise ValueError('unit_vector_frozen_input_changed')
    stat=catalog.stat();signature=(stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)
    basis=plan['TokenBudgetBasis'];limits=basis['limits']
    summary={'status':'running','completed_batches':0,'provider_calls':0,'reported_new_tokens':0,
             'plan_sha256':digest(output/'plan.json'),'financial_research_calls':0}
    try:
        with (closing(QwenRetrieval(os.environ['QWEN_API_KEY'],embedding_model='qwen3.7-text-embedding')) as api,
              closing(sqlite3.connect(catalog.as_uri()+'?mode=ro',uri=True)) as db):
            client=UnitEmbeddingPreparation(output/'receipts',api,snapshot=plan['snapshot_digest'],budget=basis)
            with (output/'jobs.jsonl').open(encoding='utf8') as jobs:
                for line in jobs:
                    job=json.loads(line);current=catalog.stat()
                    if (current.st_size,current.st_mtime_ns,current.st_ctime_ns)!=signature:
                        raise ValueError('unit_catalog_changed_during_preparation')
                    if psutil.virtual_memory().available<800*2**20:raise RuntimeError('unit_preparation_memory_guard')
                    if shutil.disk_usage(output).free<2*2**30:raise RuntimeError('unit_preparation_disk_guard')
                    if summary['reported_new_tokens']>limits['reported_token_stop_cap']:
                        raise RuntimeError('unit_preparation_reported_usage_guard')
                    if summary['completed_batches']>=limits['requests']:raise ValueError('unit_preparation_request_budget')
                    texts=[]
                    for item in job['units']:
                        packed=db.execute('SELECT payload FROM units WHERE id=?',(item['id'],)).fetchone()
                        if packed is None:raise ValueError('unit_preparation_missing_unit')
                        unit=json.loads(zlib.decompress(packed[0]));text=unit['embedding_context']+'\n'+unit['content']
                        if sha256(text.encode()).hexdigest()!=item['input_sha256']:
                            raise ValueError('unit_preparation_input_digest_mismatch')
                        texts.append(text)
                    _,receipt=client.embed(texts)
                    summary['completed_batches']+=1;summary['provider_calls']+=receipt['provider_calls']
                    usage=receipt['newly_reported_usage']
                    summary['reported_new_tokens']+=usage.get('total_tokens',usage.get('input_tokens',0))
                    with (output/'batch-receipts.jsonl').open('a',encoding='utf8') as stream:
                        stream.write(json.dumps({'batch':job['number'],**receipt},ensure_ascii=False)+'\n')
                    (output/'result.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
                    print(json.dumps({'completed':summary['completed_batches'],'total':limits['requests'],
                        'provider_calls':summary['provider_calls'],'reported_new_tokens':summary['reported_new_tokens']}),flush=True)
            summary['status']='completed'
    except Exception as exc:
        summary.update(status='stopped',error_type=type(exc).__name__)
        raise
    finally:(output/'result.json').write_text(json.dumps(summary,indent=2),encoding='utf8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','execute'])
    parser.add_argument('--catalog',type=Path);parser.add_argument('--scope',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.action=='prepare':prepare(args.catalog,args.scope,args.output)
    else:execute(args.output)
