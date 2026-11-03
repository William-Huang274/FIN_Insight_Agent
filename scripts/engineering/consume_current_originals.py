"""Serial isolated native parsing of the current-source backlog, no model/network."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.parse import urlsplit
import zlib

from audit_source_binding_lineage import digest, read_lines, readonly


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')


def worker(row,out):
    def deny(*args,**kwargs):raise RuntimeError('offline_parser_network_disabled')
    socket.create_connection=deny;socket.socket.connect=deny
    c=row['current_source']
    if c.get('path'):raw=Path(c['path']).read_bytes()
    else:
        with readonly(c['database']) as db:
            data=db.execute('SELECT body_zlib FROM raw_captures WHERE url=? AND digest=?',(c['url'],c['current_sha256'])).fetchone()
        if not data:raise ValueError('current_source_missing')
        raw=zlib.decompress(data[0])
    assert digest(raw)==c['current_sha256']
    out.mkdir(parents=True,exist_ok=False)
    job=dict(id=digest(raw),title=row['title'],url=row['url'],domain=urlsplit(row['url']).netloc,
             form=row.get('metadata',{}).get('form',''),capture={'content_type':''})
    receipt=dict(document_id=row['document_id'],source_sha256=job['id'],quality_pass=False,provider_calls=0)
    def pack(name,value):
        path=out/(name+'.json.gz');data=gzip.compress(json.dumps(value,ensure_ascii=False).encode(),compresslevel=3,mtime=0)
        path.write_bytes(data);return dict(path=str(path),sha256=digest(data))
    if raw.lstrip().startswith(b'%PDF'):
        import pymupdf
        from pdf_native_structure import describe_page
        document=pymupdf.open(stream=raw,filetype='pdf');pages=[];counts=Counter()
        for page in document:
            data=describe_page(page)
            if data['errors']:raise ValueError('pdf_page_errors:'+str(data['errors']))
            artifact=pack(f'page-{page.number+1:05d}',data)
            pages.append(dict(page=page.number+1,**artifact));counts['tables']+=len(data['tables']);counts['panels']+=len(data['panels']['panels'])
        receipt.update(lane='pdf',pages=pages,page_count=len(document),counts=dict(counts),native_bookmarks=document.get_toc())
    else:
        from document_structure_audit import inspect
        from refine_document_chapters import refine
        from structured_source_contract import describe
        from native_document_capture import capture_native
        from native_document_adaptation import adapt
        from native_web_adaptation import adapt_web
        from document_structure_repairs import repair_sec_signatures,repair_markdown_html
        from document_role_repairs import repair_context_roles
        from source_heading_units import repair as repair_headings
        from source_part_hierarchy import repair as repair_parts
        from finalize_structure_prechunks import classify
        from validate_source_structure_audit import validate
        document=refine(inspect(raw,job))
        route=document['route']
        if route in ('structured_json','structured_xml'):
            document['source_sha256']=job['id']
            contract=describe(document)
            if contract.get('column_lengths_consistent') is False:raise ValueError('parallel_columns_mismatch')
            receipt.update(lane='structured',records=pack('records',contract),record_kind=contract['kind'])
        else:
            native_route={'edgartools':'edgartools','trafilatura_xml':'trafilatura','markdown_or_plain_text':'markdown'}[route]
            native=capture_native(raw,native_route,title=job['title'],form=job['form'])
            receipt['native']=pack('native',native)
            if native_route=='trafilatura':document=adapt_web(native,document);lane='web'
            elif native_route=='markdown':document=repair_markdown_html(adapt(native));lane='markdown'
            else:
                document=repair_context_roles(repair_sec_signatures(adapt(native,document)))
                document=repair_headings(document,native)
                if document.get('native_toc_identity_aliases'):
                    document['native_toc_alias_capture']=receipt['native']
                document,_=repair_parts(document)
                from embedded_section_titles import repair as repair_embedded_titles
                document,_,_=repair_embedded_titles(document,raw)
                from equivalent_section_titles import repair as repair_equivalent_titles
                document,_=repair_equivalent_titles(document,raw)
                from source_section_title_links import repair as repair_source_titles
                document,_,_=repair_source_titles(document,raw)
                lane='sec'
            if lane in {'sec','web'}:
                from source_location_alignment import repair as repair_source_locations
                document,_=repair_source_locations(document,raw)
            errors=validate(document)
            if errors:raise ValueError('structure_contract:'+str(errors))
            receipt.update(lane=lane,prechunks=pack('prechunks',classify(document)),blocks=len(document['blocks']),chapters=len(document['chapter_tree']))
        receipt['document']=pack('document',document)
    receipt['status']='engineering_checked_quality_pending'
    save(out/'receipt.json',receipt)


def run(args):
    rows=[r for r in read_lines(args.ledger) if r['processing']['stage']=='parse_current_original']
    # Fail before starting a mixed-format batch when a required lane is absent.
    from importlib.util import find_spec
    from importlib.metadata import version
    if find_spec('pymupdf') is None:raise RuntimeError('pymupdf_dependency_unavailable')
    prior={}
    if args.prior:
        root=Path(args.prior)
        identity=json.loads((root/'identity.json').read_bytes())
        if identity['ledger_sha256']!=digest(Path(args.ledger).read_bytes()):
            raise ValueError('prior_ledger_changed')
        previous=json.loads((root/'summary.json').read_bytes())
        prior={r['document_id']:r for r in previous['rows']}
        if not set(prior)<= {r['document_id'] for r in rows}:raise ValueError('prior_scope_mismatch')
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    save(out/'identity.json',dict(ledger_sha256=digest(Path(args.ledger).read_bytes()),
        code={p.name:digest(p.read_bytes()) for p in Path(__file__).parent.glob('*.py')},planned=len(rows),
        prior=args.prior,pymupdf_version=version('pymupdf'),python=sys.executable))
    results=[]
    for index,row in enumerate(rows):
        previous=prior.get(row['document_id'])
        if previous and previous['status']!='failed':
            receipt=json.loads(Path(previous['receipt']).read_bytes())
            if receipt['source_sha256']!=row['current_source']['current_sha256']:raise ValueError('prior_source_changed')
            for name in ('document','native','records','prechunks'):
                if name in receipt and digest(Path(receipt[name]['path']).read_bytes())!=receipt[name]['sha256']:
                    raise ValueError('prior_artifact_changed:'+name)
            for page in receipt.get('pages',[]):
                if digest(Path(page['path']).read_bytes())!=page['sha256']:raise ValueError('prior_page_changed')
            record=dict(previous,qualification_version=previous.get('qualification_version',Path(args.prior).name),reused_from=args.prior)
            results.append(record)
            continue
        import psutil
        wait_until=time.monotonic()+300
        while psutil.virtual_memory().available<800*2**20 and time.monotonic()<wait_until:
            save(out/'summary.json',dict(planned=len(rows),processed=len(results),status='waiting_for_memory',rows=results,quality_pass=False))
            time.sleep(10)
        if psutil.virtual_memory().available<800*2**20 or shutil.disk_usage(out).free<600*2**20:
            save(out/'summary.json',dict(planned=len(rows),processed=len(results),status='resource_pause',rows=results,quality_pass=False));return 75
        rowpath=out/'inputs'/f'{index:04d}.json';save(rowpath,row)
        folder=out/f'{index:04d}'
        started=time.monotonic()
        try:
            result=subprocess.run([sys.executable,__file__,'--worker',str(rowpath),'--output',str(folder)],capture_output=True,text=True,encoding='utf8',errors='replace',timeout=600)
            (out/f'{index:04d}.log').write_text(result.stdout+result.stderr,encoding='utf8')
            if result.returncode:raise ValueError('worker_exit_'+str(result.returncode))
            record=json.loads((folder/'receipt.json').read_bytes())
        except Exception as exc:
            record=dict(document_id=row['document_id'],status='failed',error=repr(exc))
            save(out/f'{index:04d}.failure.json',record)
        record.update(elapsed_seconds=round(time.monotonic()-started,2),receipt=str(folder/'receipt.json'))
        record['qualification_version']=out.name
        if previous:record['prior_failure']=previous
        results.append(record)
        summary=dict(planned=len(rows),processed=len(results),statuses=dict(Counter(r['status'] for r in results)),rows=results,quality_pass=False,provider_calls=0)
        save(out/'summary.json',summary)
        print(json.dumps(dict(processed=index+1,planned=len(rows),statuses=summary['statuses']),ensure_ascii=False),flush=True)
    return 0


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ledger');p.add_argument('--worker');p.add_argument('--output',required=True)
    p.add_argument('--prior',help='Explicitly retain successful receipts and retry failed/unprocessed rows into a new output')
    args=p.parse_args()
    if args.worker:worker(json.loads(Path(args.worker).read_bytes()),Path(args.output))
    else:raise SystemExit(run(args))
