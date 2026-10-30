"""Bounded, offline full-corpus structure qualification with immutable receipts.

Runs optional parsers in one recyclable child at a time. No model requests,
index publication or live database writes. Findings are diagnostics, not gold.
"""
import argparse
from collections import Counter
import gc
import gzip
from hashlib import sha256
from importlib.metadata import version, PackageNotFoundError
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time
import zlib

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))


def identity(manifest):
    files=['scripts/engineering/run_document_structure_audit.py',
           'scripts/engineering/document_structure_audit.py','scripts/engineering/probe_document_parsers.py',
           'scripts/engineering/restore_parser_paragraphs.py','src/retrieval/narrative_chunks.py',
           'scripts/engineering/structured_web_blocks.py',
           'scripts/engineering/source_structure_contract.py',
           'src/retrieval/object_view_compiler_v2.py']
    packages={}
    for name in ['edgartools','datamule','doc2dict','trafilatura','lxml','pypdf']:
        try:packages[name]=version(name)
        except PackageNotFoundError:packages[name]=None
    return {'manifest_sha256':sha256(manifest.read_bytes()).hexdigest(),
            'code':{f:sha256((ROOT/f).read_bytes()).hexdigest() for f in files},'packages':packages}


def save(path,obj):
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,default=str),encoding='utf8')
    tmp.replace(path)


def worker(args,manifest):
    from document_structure_audit import inspect
    from probe_document_parsers import deny_network,local_socket_only
    import psutil
    socket.socket.connect=local_socket_only(socket.socket.connect)
    socket.socket.connect_ex=local_socket_only(socket.socket.connect_ex)
    socket.create_connection=deny_network
    with sqlite3.connect(Path(manifest['database']).as_uri()+'?mode=ro',uri=True) as db:
        db.execute('PRAGMA cache_size=-2048')
        for job in manifest['jobs'][args.start:args.start+args.batch]:
            receipt=args.output/'receipts'/f"{job['id']}.json"
            if receipt.exists():continue
            started=time.perf_counter();result=None
            row={'id':job['id'],'bindings':job['bindings'],'provider_calls':0}
            try:
                capture=db.execute('SELECT body_zlib FROM raw_captures WHERE digest=? AND status=200 LIMIT 1',(job['id'],)).fetchone()
                if not capture:raise ValueError('frozen_original_missing')
                raw=zlib.decompress(capture[0]);del capture
                if sha256(raw).hexdigest()!=job['id']:raise ValueError('original_digest_mismatch')
                result=inspect(raw,job);del raw
                path=args.output/'documents'/f"{job['id']}.json.gz"
                with gzip.open(path,'wt',encoding='utf8',compresslevel=3) as out:
                    json.dump(result,out,ensure_ascii=False,default=str)
                row.update(status='inspected',route=result['route'],blocks=len(result['blocks']),
                           headings=len(result['outline']),pre_chunks=len(result['pre_chunks']),
                           tables=sum(b['kind']=='table' for b in result['blocks']),
                           paragraph_repairs=len(result.get('paragraph_repairs',[])),
                           issues=dict(Counter(i['kind'] for i in result['issues'])),
                           unmatched_explicit_headings=len(result.get('unmatched_explicit_headings',[])),
                           artifact_bytes=path.stat().st_size,artifact_sha256=sha256(path.read_bytes()).hexdigest())
            except Exception as exc:
                row.update(status='failed',error=type(exc).__name__,detail=str(exc)[:1000])
            row['elapsed_seconds']=time.perf_counter()-started
            mem=psutil.Process().memory_info()
            row['peak_working_set_bytes']=getattr(mem,'peak_wset',mem.rss)
            save(receipt,row)
            print(json.dumps({k:v for k,v in row.items() if k not in {'bindings','issues'}},ensure_ascii=False),flush=True)
            del result;gc.collect()
            if psutil.Process().memory_info().rss>600*1024**2:return


def summary(args,manifest):
    receipts={p.stem:json.loads(p.read_bytes()) for p in (args.output/'receipts').glob('*.json')}
    counts=Counter();issues=Counter();routes=Counter();bindings=Counter()
    for row in receipts.values():
        counts[row['status']]+=1;routes[row.get('route',row['status'])]+=1
        issues.update(row.get('issues',{}));bindings[row['status']]+=len(row['bindings'])
    report={'source_bindings':manifest['source_bindings'],'original_resolution':manifest['resolution'],
            'unique_originals':len(manifest['jobs']),'completed_originals':len(receipts),
            'execution_status':dict(counts),'binding_execution_status':dict(bindings),
            'routes':dict(routes),'issue_occurrences_not_confirmed_errors':dict(issues),
            'headings':sum(r.get('headings',0) for r in receipts.values()),
            'pre_chunks':sum(r.get('pre_chunks',0) for r in receipts.values()),
            'paragraph_repairs':sum(r.get('paragraph_repairs',0) for r in receipts.values()),
            'artifact_bytes':sum(r.get('artifact_bytes',0) for r in receipts.values()),
            'provider_calls':0,'structural_accuracy_claim':False}
    save(args.output/'summary.json',report);return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--worker',action='store_true');p.add_argument('--start',type=int,default=0)
    p.add_argument('--batch',type=int,default=12);p.add_argument('--limit',type=int)
    a=p.parse_args();manifest=json.loads(a.manifest.read_bytes())
    for sub in ['documents','receipts','logs']:(a.output/sub).mkdir(parents=True,exist_ok=True)
    frozen=identity(a.manifest);stamp=a.output/'execution-identity.json'
    if stamp.exists():
        if json.loads(stamp.read_bytes())!=frozen:raise ValueError('audit_code_or_input_changed_use_new_output')
    else:save(stamp,frozen)
    if a.worker:return worker(a,manifest)
    import psutil
    stop=min(len(manifest['jobs']),a.limit or len(manifest['jobs']))
    while True:
        pending=[i for i,j in enumerate(manifest['jobs'][:stop]) if not (a.output/'receipts'/f"{j['id']}.json").exists()]
        if not pending:break
        if psutil.virtual_memory().available<650*1024**2 or psutil.disk_usage(str(a.output)).free<600*1024**2:
            print('resource_pause_preserving_all_pending',flush=True);break
        start=pending[0];batch=min(a.batch,stop-start)
        log=a.output/'logs'/f'{start}-{time.time_ns()}.log'
        with log.open('w',encoding='utf8') as out:
            try:
                completed=subprocess.run([sys.executable,__file__,'--manifest',str(a.manifest),
                    '--output',str(a.output),'--worker','--start',str(start),'--batch',str(batch)],
                    stdout=out,stderr=subprocess.STDOUT,timeout=900)
            except subprocess.TimeoutExpired:
                print('batch_timeout_pending_preserved',flush=True);break
        report=summary(a,manifest)
        print(json.dumps(report,ensure_ascii=False),flush=True)
        if completed.returncode!=0:
            print('worker_failed_pending_preserved '+str(log),flush=True);break
    summary(a,manifest)


if __name__=='__main__':main()
