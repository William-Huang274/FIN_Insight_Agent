"""Isolated serial source-location repair with immutable per-document receipts."""
import argparse
from collections import Counter
import gc
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import struct
import sys
import time

from audit_source_binding_lineage import digest


def save(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')


def memory_requirement(job):
    path=Path(job['artifact']['path']);source_bytes=job['source'].get('bytes')
    if source_bytes is None or path.suffix!='.gz':return 800*2**20
    with path.open('rb') as stream:
        stream.seek(-4,2);document_bytes=struct.unpack('<I',stream.read(4))[0]
    # A conservative input-size budget, plus fixed interpreter/DOM allowance
    # and 192 MiB left free. Large inputs retain a larger startup requirement.
    return max(320*2**20,8*document_bytes+20*source_bytes+288*2**20)


def worker(input_path,output):
    from qualify_embedded_section_titles import original
    from source_location_alignment import repair,verify
    from validate_source_structure_audit import validate
    row=json.loads(Path(input_path).read_bytes());a=row['artifact'];out=Path(output);out.mkdir(parents=True,exist_ok=False)
    payload=Path(a['path']).read_bytes()
    if digest(payload)!=a['sha256']:raise ValueError('parent_changed')
    old=json.loads(gzip.decompress(payload));raw=original(row['source']);new,proofs=repair(old,raw)
    verify(new,raw)
    if validate(new):raise ValueError('structure_contract_failed')
    for field in ('source_sha256','chapter_tree','outline','source_scope_repairs','source_heading_units','source_heading_scope_deferrals','source_role_repairs'):
        if old.get(field)!=new.get(field):raise ValueError('prior_structure_changed:'+field)
    if len(old['blocks'])!=len(new['blocks']):raise ValueError('physical_block_count_changed')
    allowed={'source_container_id','source_container_candidates','source_location_status','source_alignment_basis','source_alignment_proof','source_alignment_alternatives'}
    for before,after in zip(old['blocks'],new['blocks']):
        if {k:v for k,v in before.items() if k not in allowed}!={k:v for k,v in after.items() if k not in allowed}:
            raise ValueError('physical_block_or_role_changed')
    if len(old['pre_chunks'])!=len(new['pre_chunks']):raise ValueError('prechunk_count_changed')
    for before,after in zip(old['pre_chunks'],new['pre_chunks']):
        if {k:v for k,v in before.items() if k!='source_container_id'}!={k:v for k,v in after.items() if k!='source_container_id'}:
            raise ValueError('prechunk_content_or_scope_changed')
    selected=a
    if new!=old:
        target=out/'document.json.gz';target.write_bytes(gzip.compress(json.dumps(new,ensure_ascii=False).encode(),compresslevel=6,mtime=0))
        selected=dict(a,path=str(target),sha256=digest(target.read_bytes()),version=out.parent.name)
        from finalize_structure_prechunks import classify
        chunks=classify(new);chunk_path=out/'prechunks.json.gz';chunk_path.write_bytes(gzip.compress(json.dumps(chunks,ensure_ascii=False).encode(),compresslevel=6,mtime=0))
        selected['prechunks']=dict(path=str(chunk_path),sha256=digest(chunk_path.read_bytes()))
    metrics={}
    for label,d in [('before',old),('after',new)]:
        metrics[label]=dict(Counter(b.get('source_location_status','not_recorded') for b in d['blocks'] if b.get('text','').strip()))
    hidden_ids={p['source_id'] for p in new.get('source_visibility_repairs',[])}
    bound_hidden=[i for i,b in enumerate(new['blocks']) if b.get('source_container_id') in hidden_ids]
    import psutil
    memory=psutil.Process().memory_info()
    receipt=dict(status='qualified',source_sha256=old['source_sha256'],parent=a,artifact=selected,
        repaired_locations=len(proofs),verified_alternatives=len(new.get('source_equivalent_occurrence_proofs',[])),visibility_updates=len(new.get('source_visibility_repairs',[])),
        retained_hidden_bindings=bound_hidden,metrics=metrics,peak_rss_mib=getattr(memory,'peak_wset',memory.rss)/2**20,provider_calls=0)
    save(out/'receipt.json',receipt)


def run(ledger,output,limit=None,prior=None):
    import psutil
    targets={}
    with Path(ledger).open(encoding='utf8') as stream:
        for line in stream:
            row=json.loads(line);a=row.get('current_parser_artifact') or {}
            if a.get('lane') in {'sec','web'}:targets.setdefault(a['path'],dict(artifact=a,source=row['current_source']))
    del row,line;gc.collect()
    jobs=list(targets.values())
    if limit is None:jobs.sort(key=lambda job:(memory_requirement(job),job['artifact']['path']))
    if limit is not None:jobs=jobs[:limit]
    out=Path(output);out.mkdir(parents=True,exist_ok=False);(out/'inputs').mkdir()
    names=('qualify_source_locations.py','source_location_alignment.py','source_visibility.py','source_heading_units.py',
           'source_structure_contract.py','validate_source_structure_audit.py','qualify_embedded_section_titles.py','audit_source_binding_lineage.py','finalize_structure_prechunks.py')
    identity=dict(ledger_sha256=digest(Path(ledger).read_bytes()),code={n:digest(Path(__file__).with_name(n).read_bytes()) for n in names},
                  planned=len(jobs),full_scope=limit is None,memory_policy='input_size_bound_plus_192_mib_reserve')
    reused={}
    if prior:
        previous=json.loads((Path(prior)/'identity.json').read_bytes())
        if previous!=identity:raise ValueError('prior_input_or_implementation_changed')
        previous_summary=json.loads((Path(prior)/'summary.json').read_bytes())
        reused={r['parent']['path']:r for r in previous_summary['rows'] if r['status']=='qualified'}
    save(out/'identity.json',identity);results=[];selected={};pause=None
    def summary(status):
        save(out/'summary.json',dict(status=status,planned=len(jobs),processed=len(results),full_scope=limit is None,rows=results,
            statuses=dict(Counter(r['status'] for r in results)),provider_calls=0,quality_pass=False))
    for index,job in enumerate(jobs):
        a=job['artifact'];existing=reused.get(a['path'])
        if existing:
            if existing['parent']!=a or digest(Path(existing['artifact']['path']).read_bytes())!=existing['artifact']['sha256']:
                raise ValueError('prior_artifact_changed')
            result=existing
        else:
            required=memory_requirement(job)
            deadline=time.monotonic()+60
            while psutil.virtual_memory().available<required and time.monotonic()<deadline:time.sleep(5)
            if psutil.virtual_memory().available<required or shutil.disk_usage(out).free<650*2**20:
                pause='resource_pause';break
            print(json.dumps(dict(launch=index,available_mib=psutil.virtual_memory().available//2**20,required_mib=required//2**20)),flush=True)
            input_path=out/'inputs'/f'{index:04d}.json';save(input_path,job);folder=out/f'{index:04d}'
            started=time.monotonic()
            try:
                child=subprocess.run([sys.executable,__file__,'--worker',str(input_path),'--output',str(folder)],
                    capture_output=True,text=True,encoding='utf8',errors='replace',timeout=600)
                (out/f'{index:04d}.log').write_text(child.stdout+child.stderr,encoding='utf8')
                if child.returncode:raise RuntimeError('child_exit_'+str(child.returncode))
                result=json.loads((folder/'receipt.json').read_bytes());result['receipt']=str(folder/'receipt.json')
            except Exception as exc:
                result=dict(status='failed',parent=a,error=repr(exc),output=str(folder))
            result['elapsed_seconds']=time.monotonic()-started
        results.append(result)
        if result['status']=='qualified':selected[a['path']]=result['artifact']
        summary('running')
        print(json.dumps(dict(processed=len(results),planned=len(jobs),status=result['status'],repaired=result.get('repaired_locations',0))),flush=True)
    assert identity['ledger_sha256']==digest(Path(ledger).read_bytes())
    assert all(digest(Path(__file__).with_name(n).read_bytes())==h for n,h in identity['code'].items())
    state=pause or ('failed' if any(r['status']=='failed' for r in results) else 'completed')
    summary(state)
    if state=='completed' and limit is None:
        seen=set()
        with Path(ledger).open(encoding='utf8') as source,(out/'library-bindings.jsonl').open('w',encoding='utf8') as destination:
            for line in source:
                row=json.loads(line);a=row.get('current_parser_artifact') or {}
                if row['document_id'] in seen:raise ValueError('duplicate_binding')
                seen.add(row['document_id'])
                if a.get('path') in selected:
                    row['current_parser_artifact']=selected[a['path']];row['processing']['current_parser_artifact']=selected[a['path']]
                destination.write(json.dumps(row,ensure_ascii=False)+'\n')
        assert len(seen)==1742
    return 0 if state=='completed' else 75 if pause else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ledger');p.add_argument('--output',required=True)
    p.add_argument('--limit',type=int);p.add_argument('--prior');p.add_argument('--worker')
    a=p.parse_args()
    if a.worker:worker(a.worker,a.output)
    else:raise SystemExit(run(a.ledger,a.output,a.limit,a.prior))
