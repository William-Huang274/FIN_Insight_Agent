"""Persistent exact cosine index for immutable library child chunks.

SQLite owns embedding deduplication/transactions and request accounting; NumPy
owns float32 matrix storage and cosine ranking. No corpus API calls on reads.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from contextlib import closing
from functools import lru_cache
from heapq import nlargest
from hashlib import sha256
import json
from math import ceil
from pathlib import Path
import sqlite3
import time
from threading import RLock

import numpy as np

from retrieval.library_chunks import VERSION
from retrieval.qwen_api import QwenRetrieval

MODEL='text-embedding-v4'
SUPPORTED_MODELS={MODEL, 'qwen3.7-text-embedding'}
DIM=1024


class EmbeddingPacer:
    """Reserve a rolling token estimate and smooth dispatch; never retry calls.

    UTF-8 byte estimates are deliberately conservative, then raised when actual
    usage requires it. They are scheduling estimates, not billed token counts.
    Provider limits are account-wide: other clients can still cause a 429.
    """
    def __init__(self, tokens_per_minute=600_000, minimum_interval=.6):
        self.limit=tokens_per_minute;self.minimum_interval=minimum_interval
        self.ratio=.5;self.reservations={};self.next_dispatch=0.

    def reserve(self,rid,texts,stop_file=None):
        byte_count=sum(len(t.encode('utf8')) for t in texts)
        estimate=ceil(byte_count*self.ratio)
        if estimate>self.limit:raise ValueError('embedding_batch_exceeds_local_token_window')
        while True:
            if stop_file and Path(stop_file).exists():return False
            now=time.monotonic()
            self.reservations={k:r for k,r in self.reservations.items() if now-r[0]<60}
            if now>=self.next_dispatch and sum(r[1] for r in self.reservations.values())+estimate<=self.limit:
                self.reservations[rid]=(now,estimate,byte_count)
                self.next_dispatch=now+max(self.minimum_interval,60*estimate/self.limit)
                return True
            time.sleep(.25)

    def observe(self,rid,total_tokens):
        if rid not in self.reservations or not isinstance(total_tokens,(int,float)):return
        stamp,estimate,byte_count=self.reservations[rid]
        self.reservations[rid]=(stamp,max(estimate,total_tokens),byte_count)
        self.ratio=max(self.ratio,1.2*total_tokens/max(1,byte_count))


def digest(path):
    with Path(path).open('rb') as f:
        from hashlib import file_digest
        return file_digest(f,'sha256').hexdigest()


def inputs(library):
    return library._query('SELECT id,source_id,context || char(10) || body AS text FROM retrieval_chunks ORDER BY id')


def vector_key(text,model=MODEL):
    return sha256((model+'\0'+str(DIM)+'\0'+text).encode()).hexdigest()


def open_cache(root):
    Path(root).mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(Path(root)/'chunk-embeddings.sqlite',timeout=60)
    db.executescript('''
    CREATE TABLE IF NOT EXISTS vectors(key TEXT PRIMARY KEY,vector BLOB NOT NULL);
    CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY,status TEXT NOT NULL,payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS request_items(request_id TEXT,key TEXT,PRIMARY KEY(request_id,key));
    ''')
    return db


def plan(library,root,*,model=MODEL):
    if model not in SUPPORTED_MODELS:raise ValueError('unsupported_corpus_embedding_model')
    rows=inputs(library)
    unique={vector_key(r['text'],model):r['text'] for r in rows}
    batch_size=20 if model=='qwen3.7-text-embedding' else 10
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
      'limits':{'batch_size':batch_size,'max_requests':ceil(len(missing)/batch_size),'max_workers':4,'attempts_per_request':1,'request_timeout_seconds':90,'minimum_dispatch_interval_seconds':0.6,'estimated_tokens_per_rolling_minute':600000,'token_estimate':'UTF8 bytes times adaptive ratio, initially0.5, raised to1.2times observed token/byte ratio; not billing usage'},
      'stop_behavior':'Withhold each failed/unknown batch without retry; stop dispatch immediately on429/account errors, or after3 consecutive/10 total other failures; drain in-flight outcomes and refuse incomplete publication',
      'blocked_keys':len(blocked.intersection(missing)),
      'model':model,'dimensions':DIM,'library_sha256':library.manifest['sha256'],
      'provider_contract':'https://www.alibabacloud.com/help/en/model-studio/text-embedding-synchronous-api',
      'contract_checked_at':'2026-09-22','pricing_note':'Actual provider token usage retained; no fixed total cost promised; regional billing applies'}


def prepare(library,root,api_key,audit,*,execute=False,skip_blocked=False,retry_request_ids=(),model=MODEL,stop_file=None):
    root=Path(root);audit=Path(audit);audit.mkdir(parents=True,exist_ok=True)
    rows,missing,basis=plan(library,root,model=model)
    basis['stop_file']=str(stop_file) if stop_file else None
    (audit/'TokenBudgetBasis.json').write_text(json.dumps(basis,indent=2),encoding='utf8')
    if not execute:return basis
    if (root/'chunk-vector-manifest.json').is_file():
        manifest,_,_=ready_index(root,library.manifest['sha256'])
        if manifest['embedding_model']!=model:raise ValueError('published_embedding_model_mismatch')
        if missing:raise ValueError('published_vector_cache_incomplete')
        (audit/'embedding-result.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
        return manifest
    with closing(open_cache(root)) as db:
        blocked={r[0] for r in db.execute("SELECT i.key FROM request_items i JOIN requests r ON r.id=i.request_id WHERE r.status!='completed'")}
        approved=set()
        for rid in retry_request_ids:
            if not db.execute("SELECT 1 FROM requests WHERE id=? AND status!='completed'",(rid,)).fetchone():raise ValueError('retry_requires_existing_failed_or_unknown_request')
            approved.update(r[0] for r in db.execute('SELECT key FROM request_items WHERE request_id=?',(rid,)))
        # An earlier approval must not authorize a second attempt after its own
        # retry failed, even if remaining texts now form different batches.
        for rid,key in db.execute("SELECT i.request_id,i.key FROM request_items i JOIN requests r ON r.id=i.request_id WHERE r.status!='completed'"):
            if rid not in retry_request_ids:approved.discard(key)
    withheld=set(missing)&(blocked-approved)
    if withheld and not skip_blocked:raise RuntimeError('previous_failed_or_unknown_embedding_keys_require_review')
    missing={k:t for k,t in missing.items() if k not in withheld}
    basis.update(withheld_keys=len(withheld),explicitly_approved_retry_request_ids=list(retry_request_ids),
                 dispatched_texts=len(missing))
    (audit/'TokenBudgetBasis.json').write_text(json.dumps(basis,indent=2),encoding='utf8')
    if not rows:raise ValueError('no_readable_chunks_to_embed')
    pending=list(missing.items())
    batch_size=basis['limits']['batch_size']
    batches=[pending[i:i+batch_size] for i in range(0,len(pending),batch_size)]

    # One SDK connection pool is shared by bounded threads; avoid reconnecting
    # and rebuilding TLS clients for every batch. Provider retries remain zero.
    with closing(open_cache(root)) as db,closing(QwenRetrieval(api_key,embedding_model=model,timeout=90)) as api,ThreadPoolExecutor(max_workers=4) as pool:
        active={};next_batch=0;completed=0;failure=None;failed_count=0;consecutive_failures=0;stop=False;began=time.monotonic()
        pacer=EmbeddingPacer()
        paused=False
        while active or (next_batch<len(batches) and not stop):
            while not stop and len(active)<4 and next_batch<len(batches):
                if stop_file and Path(stop_file).exists():
                    paused=stop=True
                    break
                batch=batches[next_batch]
                rid=sha256(json.dumps([k for k,_ in batch]).encode()).hexdigest()
                if any(k in approved for k,_ in batch):
                    rid=sha256((rid+json.dumps(sorted(retry_request_ids))).encode()).hexdigest()
                if db.execute('SELECT 1 FROM requests WHERE id=?',(rid,)).fetchone():
                    raise RuntimeError('request_already_recorded_no_automatic_retry')
                if not pacer.reserve(rid,[t for _,t in batch],stop_file):
                    paused=stop=True
                    break
                next_batch+=1
                with db:
                    db.execute('INSERT INTO requests VALUES(?,?,?)',(rid,'started',json.dumps({'basis':basis,'batch_characters':sum(len(t) for _,t in batch),'batch_count':len(batch)})))
                    db.executemany('INSERT INTO request_items VALUES(?,?)',[(rid,k) for k,_ in batch])
                active[pool.submit(api.embed,[text for _,text in batch],dimensions=DIM)]=(rid,batch)
            if not active:break
            done,_=wait(active,return_when=FIRST_COMPLETED)
            for future in done:
                rid,batch=active.pop(future)
                try:
                    result=future.result();vectors=np.asarray(result.values,dtype=np.float32)
                    if result.model!=model or vectors.shape!=(len(batch),DIM) or not np.isfinite(vectors).all() or np.any(np.linalg.norm(vectors,axis=1)==0):
                        raise ValueError('invalid_vector_response')
                    receipt={'request_id':result.request_id,'model':result.model,'usage':result.usage,'count':len(batch)}
                    with db:
                        db.executemany('INSERT INTO vectors VALUES(?,?)',[(k,v.tobytes()) for (k,_),v in zip(batch,vectors)])
                        db.execute('UPDATE requests SET status=?,payload=? WHERE id=?',('completed',json.dumps(receipt),rid))
                    completed+=1
                    pacer.observe(rid,result.usage.get('total_tokens'))
                    consecutive_failures=0
                except Exception as exc:
                    # Do not persist provider error body, which may contain inputs.
                    receipt={'error_type':type(exc).__name__,'status_code':getattr(exc,'status_code',None),
                             'provider_request_id':getattr(exc,'request_id',None),'code':getattr(exc,'code',None)}
                    with db:db.execute('UPDATE requests SET status=?,payload=? WHERE id=?',('failed_usage_unknown',json.dumps(receipt),rid))
                    failure=exc;failed_count+=1;consecutive_failures+=1
                    stop=stop or getattr(exc,'status_code',None)==429 or getattr(exc,'code',None) in {'Arrearage','BudgetLimitExceeded','insufficient_quota'} or consecutive_failures>=3 or failed_count>=10
                if completed%50==0 or stop:
                    print(json.dumps({'completed_batches':completed,'total_batches':len(batches),'elapsed_seconds':round(time.monotonic()-began),'failed_batches':failed_count,'stopped':stop}),flush=True)
        if failure:raise RuntimeError('embedding_failed_usage_retained_no_automatic_retry') from failure
        if paused:
            report={'status':'paused_after_inflight_drained','new_completed_batches':completed,'published_index':False}
            (audit/'embedding-result.json').write_text(json.dumps(report,indent=2),encoding='utf8')
            return report
        if withheld:
            report={'status':'partial_blocked_requests_retained','withheld_keys':len(withheld),
                    'new_completed_batches':completed,'published_index':False}
            (audit/'embedding-result.json').write_text(json.dumps(report,indent=2),encoding='utf8')
            return report
        keys=list(dict.fromkeys(vector_key(r['text'],model) for r in rows));key_index={k:i for i,k in enumerate(keys)}
        matrix=np.lib.format.open_memmap(root/'chunk-vectors.npy',mode='w+',dtype=np.float32,shape=(len(keys),DIM))
        for i,k in enumerate(keys):
            saved=db.execute('SELECT vector FROM vectors WHERE key=?',(k,)).fetchone()
            if not saved:raise ValueError('missing_vector_at_publication')
            v=np.frombuffer(saved[0],dtype=np.float32)
            if v.shape!=(DIM,) or not np.isfinite(v).all() or np.linalg.norm(v)==0:raise ValueError('invalid_cached_vector')
            matrix[i]=v/np.linalg.norm(v)
        matrix.flush();del matrix
        mapping=[{'id':r['id'],'source_id':r['source_id'],'vector_index':key_index[vector_key(r['text'],model)]} for r in rows]
        (root/'chunk-vector-map.json').write_text(json.dumps(mapping,separators=(',',':')),encoding='utf8')
        usage={}
        for status,payload in db.execute('SELECT status,payload FROM requests'):
            if status=='completed':
                for k,v in json.loads(payload).get('usage',{}).items():
                    if isinstance(v,(int,float)):usage[k]=usage.get(k,0)+v
        manifest={'version':VERSION,'library_sha256':library.manifest['sha256'],'embedding_model':model,
           'dimensions':DIM,'chunks':len(rows),'unique_vectors':len(keys),'scope':'all readable child chunks; original parents preserved',
           'matrix_sha256':digest(root/'chunk-vectors.npy'),'mapping_sha256':digest(root/'chunk-vector-map.json'),
           'usage':usage,'semantic_accuracy_evaluated':False}
        (root/'chunk-vector-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
        (audit/'embedding-result.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
        return manifest


def _index_identity(root):
    return tuple((s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
                 for s in ((Path(root)/name).stat() for name in
                           ('chunk-vector-manifest.json','chunk-vectors.npy','chunk-vector-map.json')))


_index_lock=RLock()


@lru_cache(maxsize=2)
def _load(root,identity):
    root=Path(root);manifest=json.loads((root/'chunk-vector-manifest.json').read_text(encoding='utf8'))
    if manifest.get('version')!=VERSION or manifest.get('embedding_model') not in SUPPORTED_MODELS or manifest.get('dimensions')!=DIM:
        raise ValueError('chunk_vector_model_contract_mismatch')
    if digest(root/'chunk-vectors.npy')!=manifest['matrix_sha256'] or digest(root/'chunk-vector-map.json')!=manifest['mapping_sha256']:
        raise ValueError('chunk_vector_index_digest_mismatch')
    matrix=np.load(root/'chunk-vectors.npy',mmap_mode='r',allow_pickle=False)
    mapping=json.loads((root/'chunk-vector-map.json').read_text(encoding='utf8'))
    if matrix.shape!=(manifest['unique_vectors'],DIM) or len(mapping)!=manifest['chunks']:
        raise ValueError('chunk_vector_index_shape_mismatch')
    if _index_identity(root)!=identity:
        raise ValueError('chunk_vector_index_changed_during_load')
    return manifest,matrix,mapping


def dense_search(root,library_sha,query_vector,eligible,k=24):
    manifest,matrix,mapping=ready_index(root,library_sha)
    v=np.asarray(query_vector,dtype=np.float32)
    if v.shape!=(DIM,) or not np.isfinite(v).all() or np.linalg.norm(v)==0:raise ValueError('invalid_query_vector')
    scores=matrix @ (v/np.linalg.norm(v))
    matches=((float(scores[r['vector_index']]),r['id']) for r in mapping if r['source_id'] in eligible)
    return [cid for _,cid in nlargest(k,matches)]


def ready_index(root,library_sha):
    path=Path(root)/'chunk-vector-manifest.json'
    if not path.is_file():raise RuntimeError('chunk_vector_index_not_prepared')
    resolved=str(Path(root).resolve())
    with _index_lock:
        manifest,matrix,mapping=_load(resolved,_index_identity(resolved))
    if manifest['library_sha256']!=library_sha:raise ValueError('chunk_vector_library_version_mismatch')
    return manifest,matrix,mapping
