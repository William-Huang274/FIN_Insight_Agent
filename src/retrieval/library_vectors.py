"""Persistent exact cosine index for immutable library child chunks.

SQLite owns embedding deduplication/transactions and request accounting; NumPy
owns float32 matrix storage and cosine ranking. No corpus API calls on reads.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from contextlib import closing
from functools import lru_cache
from hashlib import sha256
import json
from math import ceil
from pathlib import Path
import sqlite3
import time

import numpy as np

from retrieval.library_chunks import VERSION
from retrieval.qwen_api import QwenRetrieval

MODEL='text-embedding-v4'
DIM=1024


def digest(path):
    with Path(path).open('rb') as f:
        from hashlib import file_digest
        return file_digest(f,'sha256').hexdigest()


def inputs(library):
    return library._query('SELECT id,source_id,context || char(10) || body AS text FROM retrieval_chunks ORDER BY id')


def vector_key(text):
    return sha256((MODEL+'\0'+str(DIM)+'\0'+text).encode()).hexdigest()


def open_cache(root):
    Path(root).mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(Path(root)/'chunk-embeddings.sqlite',timeout=60)
    db.executescript('''
    CREATE TABLE IF NOT EXISTS vectors(key TEXT PRIMARY KEY,vector BLOB NOT NULL);
    CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY,status TEXT NOT NULL,payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS request_items(request_id TEXT,key TEXT,PRIMARY KEY(request_id,key));
    ''')
    return db


def plan(library,root):
    rows=inputs(library)
    unique={vector_key(r['text']):r['text'] for r in rows}
    with closing(open_cache(root)) as db:
        present={r[0] for r in db.execute('SELECT key FROM vectors')}
        blocked={r[0] for r in db.execute("SELECT i.key FROM request_items i JOIN requests r ON r.id=i.request_id WHERE r.status!='completed'")}
    missing={k:t for k,t in unique.items() if k not in present}
    return rows,missing,{'purpose':'Embed every readable child chunk for source-bound retrieval; no generative financial reasoning',
      'input_scale':{'chunks':len(rows),'unique_texts':len(unique),'missing_vectors':len(missing),
                     'missing_characters':sum(map(len,missing.values()))},
      'required_output':f'{DIM}-dimension finite nonzero vectors; immutable searchable matrix and SQL request ledger',
      'quality_risk':'Semantic retrieval is candidate navigation; cited original and financial period/unit checks remain necessary',
      'reasoning_profile':'non-generative embedding',
      'limits':{'batch_size':10,'max_requests':ceil(len(missing)/10),'max_workers':4,'attempts_per_request':1,'request_timeout_seconds':90,'minimum_dispatch_interval_seconds':0.6},
      'stop_behavior':'Withhold each failed/unknown batch without retry; stop new dispatch after 3 consecutive or 10 total failed batches; retain in-flight outcomes and refuse incomplete publication',
      'blocked_keys':len(blocked.intersection(missing)),
      'model':MODEL,'dimensions':DIM,'library_sha256':library.manifest['sha256'],
      'provider_contract':'https://www.alibabacloud.com/help/en/model-studio/text-embedding-synchronous-api',
      'contract_checked_at':'2026-09-22','pricing_note':'Actual provider token usage retained; no fixed total cost promised; regional billing applies'}


def prepare(library,root,api_key,audit,*,execute=False,skip_blocked=False,retry_request_ids=()):
    root=Path(root);audit=Path(audit);audit.mkdir(parents=True,exist_ok=True)
    rows,missing,basis=plan(library,root)
    (audit/'TokenBudgetBasis.json').write_text(json.dumps(basis,indent=2),encoding='utf8')
    if not execute:return basis
    if (root/'chunk-vector-manifest.json').is_file():
        manifest,_,_=ready_index(root,library.manifest['sha256'])
        if missing:raise ValueError('published_vector_cache_incomplete')
        (audit/'embedding-result.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
        return manifest
    with closing(open_cache(root)) as db:
        blocked={r[0] for r in db.execute("SELECT i.key FROM request_items i JOIN requests r ON r.id=i.request_id WHERE r.status!='completed'")}
        approved=set()
        for rid in retry_request_ids:
            if not db.execute("SELECT 1 FROM requests WHERE id=? AND status!='completed'",(rid,)).fetchone():raise ValueError('retry_requires_existing_failed_or_unknown_request')
            approved.update(r[0] for r in db.execute('SELECT key FROM request_items WHERE request_id=?',(rid,)))
    withheld=set(missing)&(blocked-approved)
    if withheld and not skip_blocked:raise RuntimeError('previous_failed_or_unknown_embedding_keys_require_review')
    missing={k:t for k,t in missing.items() if k not in withheld}
    basis.update(withheld_keys=len(withheld),explicitly_approved_retry_request_ids=list(retry_request_ids),
                 dispatched_texts=len(missing))
    (audit/'TokenBudgetBasis.json').write_text(json.dumps(basis,indent=2),encoding='utf8')
    if not rows:raise ValueError('no_readable_chunks_to_embed')
    pending=list(missing.items())
    batches=[pending[i:i+10] for i in range(0,len(pending),10)]

    # One SDK connection pool is shared by bounded threads; avoid reconnecting
    # and rebuilding TLS clients for every batch. Provider retries remain zero.
    with closing(open_cache(root)) as db,closing(QwenRetrieval(api_key,embedding_model=MODEL,timeout=90)) as api,ThreadPoolExecutor(max_workers=4) as pool:
        active={};next_batch=0;completed=0;failure=None;failed_count=0;consecutive_failures=0;stop=False;began=time.monotonic();last_dispatch=0.
        while active or (next_batch<len(batches) and not stop):
            while not stop and len(active)<4 and next_batch<len(batches):
                # A corpus-wide rate ceiling also bounds token throughput;
                # sleeping here never repeats a request or changes its identity.
                time.sleep(max(0.,0.6-(time.monotonic()-last_dispatch)))
                batch=batches[next_batch];next_batch+=1
                rid=sha256(json.dumps([k for k,_ in batch]).encode()).hexdigest()
                if any(k in approved for k,_ in batch):
                    rid=sha256((rid+json.dumps(sorted(retry_request_ids))).encode()).hexdigest()
                if db.execute('SELECT 1 FROM requests WHERE id=?',(rid,)).fetchone():
                    raise RuntimeError('request_already_recorded_no_automatic_retry')
                with db:
                    db.execute('INSERT INTO requests VALUES(?,?,?)',(rid,'started',json.dumps({'basis':basis,'batch_characters':sum(len(t) for _,t in batch),'batch_count':len(batch)})))
                    db.executemany('INSERT INTO request_items VALUES(?,?)',[(rid,k) for k,_ in batch])
                active[pool.submit(api.embed,[text for _,text in batch],dimensions=DIM)]=(rid,batch)
                last_dispatch=time.monotonic()
            done,_=wait(active,return_when=FIRST_COMPLETED)
            for future in done:
                rid,batch=active.pop(future)
                try:
                    result=future.result();vectors=np.asarray(result.values,dtype=np.float32)
                    if vectors.shape!=(len(batch),DIM) or not np.isfinite(vectors).all() or np.any(np.linalg.norm(vectors,axis=1)==0):
                        raise ValueError('invalid_vector_response')
                    receipt={'request_id':result.request_id,'model':result.model,'usage':result.usage,'count':len(batch)}
                    with db:
                        db.executemany('INSERT INTO vectors VALUES(?,?)',[(k,v.tobytes()) for (k,_),v in zip(batch,vectors)])
                        db.execute('UPDATE requests SET status=?,payload=? WHERE id=?',('completed',json.dumps(receipt),rid))
                    completed+=1
                    consecutive_failures=0
                except Exception as exc:
                    # Do not persist provider error body, which may contain inputs.
                    receipt={'error_type':type(exc).__name__,'status_code':getattr(exc,'status_code',None),
                             'provider_request_id':getattr(exc,'request_id',None),'code':getattr(exc,'code',None)}
                    with db:db.execute('UPDATE requests SET status=?,payload=? WHERE id=?',('failed_usage_unknown',json.dumps(receipt),rid))
                    failure=exc;failed_count+=1;consecutive_failures+=1
                    stop=consecutive_failures>=3 or failed_count>=10
                if completed%50==0 or stop:
                    print(json.dumps({'completed_batches':completed,'total_batches':len(batches),'elapsed_seconds':round(time.monotonic()-began),'failed_batches':failed_count,'stopped':stop}),flush=True)
        if failure:raise RuntimeError('embedding_failed_usage_retained_no_automatic_retry') from failure
        if withheld:
            report={'status':'partial_blocked_requests_retained','withheld_keys':len(withheld),
                    'new_completed_batches':completed,'published_index':False}
            (audit/'embedding-result.json').write_text(json.dumps(report,indent=2),encoding='utf8')
            return report
        keys=list(dict.fromkeys(vector_key(r['text']) for r in rows));key_index={k:i for i,k in enumerate(keys)}
        matrix=np.lib.format.open_memmap(root/'chunk-vectors.npy',mode='w+',dtype=np.float32,shape=(len(keys),DIM))
        for i,k in enumerate(keys):
            saved=db.execute('SELECT vector FROM vectors WHERE key=?',(k,)).fetchone()
            if not saved:raise ValueError('missing_vector_at_publication')
            v=np.frombuffer(saved[0],dtype=np.float32)
            if v.shape!=(DIM,) or not np.isfinite(v).all() or np.linalg.norm(v)==0:raise ValueError('invalid_cached_vector')
            matrix[i]=v/np.linalg.norm(v)
        matrix.flush();del matrix
        mapping=[{'id':r['id'],'source_id':r['source_id'],'vector_index':key_index[vector_key(r['text'])]} for r in rows]
        (root/'chunk-vector-map.json').write_text(json.dumps(mapping,separators=(',',':')),encoding='utf8')
        usage={}
        for status,payload in db.execute('SELECT status,payload FROM requests'):
            if status=='completed':
                for k,v in json.loads(payload).get('usage',{}).items():
                    if isinstance(v,(int,float)):usage[k]=usage.get(k,0)+v
        manifest={'version':VERSION,'library_sha256':library.manifest['sha256'],'embedding_model':MODEL,
           'dimensions':DIM,'chunks':len(rows),'unique_vectors':len(keys),'scope':'all readable child chunks; original parents preserved',
           'matrix_sha256':digest(root/'chunk-vectors.npy'),'mapping_sha256':digest(root/'chunk-vector-map.json'),
           'usage':usage,'semantic_accuracy_evaluated':False}
        (root/'chunk-vector-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
        (audit/'embedding-result.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
        return manifest


@lru_cache(maxsize=2)
def _load(root,manifest_stamp):
    root=Path(root);manifest=json.loads((root/'chunk-vector-manifest.json').read_text(encoding='utf8'))
    if manifest.get('version')!=VERSION or manifest.get('embedding_model')!=MODEL or manifest.get('dimensions')!=DIM:
        raise ValueError('chunk_vector_model_contract_mismatch')
    if digest(root/'chunk-vectors.npy')!=manifest['matrix_sha256'] or digest(root/'chunk-vector-map.json')!=manifest['mapping_sha256']:
        raise ValueError('chunk_vector_index_digest_mismatch')
    matrix=np.load(root/'chunk-vectors.npy',mmap_mode='r',allow_pickle=False)
    mapping=json.loads((root/'chunk-vector-map.json').read_text(encoding='utf8'))
    if matrix.shape!=(manifest['unique_vectors'],DIM) or len(mapping)!=manifest['chunks']:
        raise ValueError('chunk_vector_index_shape_mismatch')
    return manifest,matrix,mapping


def dense_search(root,library_sha,query_vector,eligible,k=24):
    manifest,matrix,mapping=ready_index(root,library_sha)
    v=np.asarray(query_vector,dtype=np.float32)
    if v.shape!=(DIM,) or not np.isfinite(v).all() or np.linalg.norm(v)==0:raise ValueError('invalid_query_vector')
    scores=matrix @ (v/np.linalg.norm(v))
    matches=[(float(scores[r['vector_index']]),r['id']) for r in mapping if r['source_id'] in eligible]
    return [cid for _,cid in sorted(matches,reverse=True)[:k]]


def ready_index(root,library_sha):
    path=Path(root)/'chunk-vector-manifest.json'
    if not path.is_file():raise RuntimeError('chunk_vector_index_not_prepared')
    manifest,matrix,mapping=_load(str(Path(root).resolve()),path.stat().st_mtime_ns)
    if manifest['library_sha256']!=library_sha:raise ValueError('chunk_vector_library_version_mismatch')
    return manifest,matrix,mapping
