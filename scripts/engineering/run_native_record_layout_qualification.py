"""Serial full-scope native PDF geometry / structured record qualification."""
import argparse
from collections import Counter
import gzip
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import zlib

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')


def original(db,oid):
    row=db.execute('SELECT body_zlib FROM raw_captures WHERE digest=? AND status=200 LIMIT 1',(oid,)).fetchone()
    if row is None:raise ValueError('original_missing')
    raw=zlib.decompress(row[0])
    if sha256(raw).hexdigest()!=oid:raise ValueError('original_digest_mismatch')
    return raw


def pdf_worker(args,manifest):
    import pymupdf
    from pdf_native_structure import describe_page
    with sqlite3.connect(Path(manifest['database']).as_uri()+'?mode=ro',uri=True) as db:
        db.execute('PRAGMA cache_size=-2048');raw=original(db,args.source_id)
    document=pymupdf.open(stream=raw,filetype='pdf');counts=Counter();rows=[]
    for page in document:
        started=time.monotonic();data=describe_page(page)
        path=args.output/args.source_id/'pages'/f'{page.number+1:05d}.json.gz';path.parent.mkdir(parents=True,exist_ok=True)
        packed=gzip.compress(json.dumps(data,ensure_ascii=False).encode(),mtime=0);path.write_bytes(packed)
        counts['pages']+=1;counts['table_candidates']+=len(data['tables']);counts['panel_candidates']+=len(data['panels']['panels'])
        counts['words']+=len(data['panels']['words']);counts['page_errors']+=bool(data['errors'])
        counts['pages_with_rotated_lines']+=any(k!='0' and v for k,v in data['line_direction_character_counts'].items())
        rows.append(dict(page=page.number+1,artifact_sha256=sha256(packed).hexdigest(),elapsed_seconds=round(time.monotonic()-started,3),errors=data['errors']))
        if (page.number+1)%25==0:print(json.dumps(dict(source=args.source_id,page=page.number+1,total=document.page_count)),flush=True)
    report=dict(source_sha256=args.source_id,planned_pages=document.page_count,counts=dict(counts),pages=rows,
        native_bookmarks=document.get_toc(),parser='pymupdf',parser_version=pymupdf.__version__,
        engineering_pass=not counts['page_errors'] and counts['pages']==document.page_count,quality_pass=False,provider_calls=0)
    save(args.output/args.source_id/'receipt.json',report)
    return 0 if report['engineering_pass'] else 1


def main(args):
    manifest=json.loads(args.manifest.read_bytes())
    if args.source_id:return pdf_worker(args,manifest)
    args.output.mkdir(parents=True,exist_ok=False)
    rows=[json.loads(s) for s in args.inventory.read_text(encoding='utf8').splitlines()]
    selected=[r for r in rows if r['lane']==args.lane];result=[];counts=Counter()
    names=['pdf_native_structure.py','structured_source_contract.py',Path(__file__).name]
    identity=dict(manifest_sha256=sha256(args.manifest.read_bytes()).hexdigest(),inventory_sha256=sha256(args.inventory.read_bytes()).hexdigest(),
        code={n:sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in names},planned=len(selected),provider_calls=0)
    save(args.output/'identity.json',identity)
    if args.lane=='structured':
        from lxml import etree
        from structured_source_contract import describe
        with sqlite3.connect(Path(manifest['database']).as_uri()+'?mode=ro',uri=True) as db:
            db.execute('PRAGMA cache_size=-2048')
            for row in selected:
                oid=row['original_id'];r=dict(id=oid,title=row['title'])
                try:
                    parent=Path(row['existing_baseline']).read_bytes()
                    if sha256(parent).hexdigest()!=row['existing_baseline_sha256']:raise ValueError('parent_digest_mismatch')
                    d=json.loads(gzip.decompress(parent));raw=original(db,oid)
                    if d['route']=='structured_json':
                        if json.loads(raw.decode('utf-8-sig'))!=d['structured_object']:raise ValueError('json_original_object_changed')
                    else:
                        parser=etree.XMLParser(resolve_entities=False,no_network=True)
                        left=etree.tostring(etree.fromstring(raw,parser),method='c14n')
                        right=etree.tostring(etree.fromstring(d['structured_xml'].encode(),parser),method='c14n')
                        if left!=right:raise ValueError('xml_original_tree_changed')
                    contract=describe(d);contract.update(source_sha256=oid,parent_sha256=sha256(parent).hexdigest(),source_object_conserved=True)
                    save(args.output/oid/'records.json',contract)
                    r.update(status='checked',kind=contract['kind'],records=contract.get('record_count',len(contract.get('records',[]))))
                    counts[contract['kind']]+=1
                    if contract.get('column_lengths_consistent') is False:r['status']='failed';r['error']='parallel_columns_mismatch'
                except Exception as exc:r.update(status='failed',error=type(exc).__name__,detail=str(exc))
                result.append(r);counts[r['status']]+=1
                save(args.output/'summary.json',dict(planned=len(selected),processed=len(result),counts=dict(counts),rows=result,quality_pass=False))
    else:
        for row in selected:
            oid=row['original_id'];r=dict(id=oid,title=row['title'])
            import psutil,shutil
            available=psutil.virtual_memory().available//1024**2
            if available<args.minimum_available_mib or shutil.disk_usage(args.output).free<2*1024**3:
                pause=dict(reason='resource_pause_before_next_document',available_mib=available,next_id=oid)
                save(args.output/'resource-pause.json',pause)
                counts['resource_pauses']+=1
                break
            command=[sys.executable,__file__,'--manifest',str(args.manifest),'--output',str(args.output),'--source-id',oid]
            try:
                proc=subprocess.run(command,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=600)
                (args.output/(oid+'.log')).write_text(proc.stdout+proc.stderr,encoding='utf8')
                r.update(status='checked' if proc.returncode==0 else 'failed',exit_code=proc.returncode)
                if (args.output/oid/'receipt.json').exists():
                    receipt=json.loads((args.output/oid/'receipt.json').read_bytes());counts.update(receipt['counts']);r['counts']=receipt['counts']
            except subprocess.TimeoutExpired as exc:
                r.update(status='timeout',error='document_600_seconds');save(args.output/(oid+'.timeout.json'),r)
                (args.output/(oid+'.log')).write_text((exc.stdout or b'').decode('utf8',errors='replace') if isinstance(exc.stdout,bytes) else exc.stdout or '',encoding='utf8')
            result.append(r);counts[r['status']]+=1
            save(args.output/'summary.json',dict(planned=len(selected),processed=len(result),counts=dict(counts),rows=result,quality_pass=False))
            print(json.dumps(dict(processed=len(result),planned=len(selected),counts=dict(counts))),flush=True)
    changed=[n for n,v in identity['code'].items() if sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()!=v]
    report=dict(planned=len(selected),processed=len(result),counts=dict(counts),code_changed=changed,
        engineering_pass=len(result)==len(selected) and not (counts['failed'] or counts['timeout'] or changed),quality_pass=False,provider_calls=0)
    save(args.output/'final-audit.json',report);print(json.dumps(report),flush=True)
    return 0 if report['engineering_pass'] else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--inventory',type=Path)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--lane',choices=['structured','pdf']);p.add_argument('--source-id')
    p.add_argument('--minimum-available-mib',type=int,default=1024)
    raise SystemExit(main(p.parse_args()))
