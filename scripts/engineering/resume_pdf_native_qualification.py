"""Resume an explicitly interrupted PDF run with exact worker/input identity."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import psutil


def save(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')


def verify_receipt(base, oid):
    r=json.loads((base/oid/'receipt.json').read_bytes())
    if not r.get('engineering_pass'):raise ValueError('failed_attempt_requires_diagnosis:'+oid)
    if r['source_sha256']!=oid or len(r['pages'])!=r['planned_pages']:raise ValueError('incomplete_pdf_receipt')
    if [p['page'] for p in r['pages']]!=list(range(1,r['planned_pages']+1)):raise ValueError('pdf_page_identity_mismatch')
    for page in r['pages']:
        if sha256((base/oid/'pages'/f"{page['page']:05d}.json.gz").read_bytes()).hexdigest()!=page['artifact_sha256']:
            raise ValueError('pdf_page_digest_changed')
    return r


def run(a):
    identity=json.loads((a.previous/'identity.json').read_bytes())
    if sha256(a.manifest.read_bytes()).hexdigest()!=identity['manifest_sha256'] or sha256(a.inventory.read_bytes()).hexdigest()!=identity['inventory_sha256']:
        raise ValueError('resume_input_identity_changed')
    for name,digest in identity['code'].items():
        if sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()!=digest:raise ValueError('resume_worker_changed:'+name)
    planned=[r for r in map(json.loads,a.inventory.read_text(encoding='utf8').splitlines()) if r['lane']=='pdf']
    a.output.mkdir(parents=True,exist_ok=True)
    own=dict(parent_identity=identity,resume_implementation_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
             prior_directory=str(a.previous),purpose='explicit_resource_interruption_continuation_same_parser')
    if (a.output/'identity.json').exists():
        if json.loads((a.output/'identity.json').read_bytes())!=own:raise ValueError('continuation_identity_changed')
    else:save(a.output/'identity.json',own)
    completed=[];counts=Counter();stopped=None
    for row in planned:
        oid=row['original_id'];directory=None
        for base in (a.output,a.previous):
            rp=base/oid/'receipt.json'
            if not rp.exists():continue
            r=verify_receipt(base,oid)
            directory=base;break
        if directory is None:
            if (a.output/oid).exists():raise ValueError('incomplete_continuation_attempt_requires_diagnosis:'+oid)
            available=psutil.virtual_memory().available//1024**2
            if available<a.minimum_available_mib or shutil.disk_usage(a.output).free<2*1024**3:
                stopped=dict(reason='resource_pause_before_next_document',available_mib=available,next_id=oid);break
            command=[sys.executable,str(Path(__file__).with_name('run_native_record_layout_qualification.py')),
                '--manifest',str(a.manifest),'--output',str(a.output),'--source-id',oid]
            try:
                p=subprocess.run(command,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=600)
                (a.output/(oid+'.log')).write_text(p.stdout+p.stderr,encoding='utf8')
                if p.returncode:stopped=dict(reason='child_failed',id=oid,exit_code=p.returncode);break
            except subprocess.TimeoutExpired as exc:
                out=exc.stdout or b'';err=exc.stderr or b''
                if isinstance(out,bytes):out=out.decode('utf8',errors='replace')
                if isinstance(err,bytes):err=err.decode('utf8',errors='replace')
                (a.output/(oid+'.log')).write_text(out+err,encoding='utf8')
                stopped=dict(reason='child_timeout',id=oid);break
            directory=a.output;r=verify_receipt(directory,oid)
        completed.append(dict(id=oid,receipt=str(directory/oid/'receipt.json'),same_worker_verified=True,reused=directory==a.previous))
        counts.update(r['counts']);counts['documents']+=1
        report=dict(planned=len(planned),processed=len(completed),counts=dict(counts),rows=completed,stop_reason=None,quality_pass=False)
        save(a.output/'summary.json',report)
        print(json.dumps(dict(processed=len(completed),pages=counts['pages'],reused=directory==a.previous)),flush=True)
    changed=[n for n,v in identity['code'].items() if sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()!=v]
    if sha256(Path(__file__).read_bytes()).hexdigest()!=own['resume_implementation_sha256']:changed.append(Path(__file__).name)
    report=dict(planned=len(planned),processed=len(completed),counts=dict(counts),rows=completed,stop_reason=stopped,code_changed=changed,
                engineering_pass=not stopped and not changed and len(completed)==len(planned) and not counts['page_errors'],quality_pass=False,provider_calls=0)
    save(a.output/'summary.json',report);save(a.output/'final-audit.json',{k:v for k,v in report.items() if k!='rows'})
    print(json.dumps({k:v for k,v in report.items() if k!='rows'}),flush=True)
    return 0 if report['engineering_pass'] else 3


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','inventory','previous','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--minimum-available-mib',type=int,default=1024)
    raise SystemExit(run(p.parse_args()))
