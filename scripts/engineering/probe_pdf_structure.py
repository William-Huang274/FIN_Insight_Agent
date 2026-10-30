"""Optional, offline PDF inventory and bounded page-layout qualification.

Install candidate parsers outside the service environment. This probe never
publishes its output or substitutes font/geometry evidence for financial facts.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import socket
import sqlite3
import time
import zlib


def deny_network(*args, **kwargs):
    raise RuntimeError('offline_pdf_probe_network_denied')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--document-id')
    p.add_argument('--audit-directory',type=Path,help='Frozen format-sniffed receipts; required for complete PDF inventory')
    p.add_argument('--pages',type=int,nargs='+',default=[0,2])
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    socket.socket.connect=deny_network;socket.socket.connect_ex=deny_network;socket.create_connection=deny_network
    import pymupdf
    import psutil
    manifest=json.loads(a.manifest.read_bytes()); rows=[]
    identity={'manifest_sha256':sha256(a.manifest.read_bytes()).hexdigest(),
              'implementation_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
              'pymupdf_version':pymupdf.__version__, 'remote_calls':0,'production_enabled':False,
              'purpose':'PDF source inventory and bounded layout/tool qualification',
              'TokenBudgetBasis':{'purpose':'local page layout recognition, no language generation',
               'input_scale':{'document_id':a.document_id,'zero_based_pages':a.pages} if a.document_id else 'all captured PDFs; no layout inference',
               'required_output':'page grounded structure and original render for review',
               'quality_risk':'layout predictions are not independently verified heading hierarchy or financial meaning',
               'reasoning_profile':'local specialized layout model only in selected-page mode',
               'limits':'one document at a time; no OCR, no remote calls, no embedding',
               'stop_behavior':'record failure; no automatic retry or model substitution'}}
    (a.output/'identity.json').write_text(json.dumps(identity,ensure_ascii=False,indent=2),encoding='utf8')
    if not a.document_id and not a.audit_directory:raise ValueError('inventory_requires_format_sniffed_receipts')
    jobs=[j for j in manifest['jobs'] if (j['id']==a.document_id if a.document_id else
          json.loads((a.audit_directory/'receipts'/(j['id']+'.json')).read_bytes()).get('route')=='pypdf_text_diagnostic')]
    if a.document_id and not jobs:raise ValueError('unknown_frozen_document')
    with sqlite3.connect(Path(manifest['database']).as_uri()+'?mode=ro',uri=True) as db:
        db.execute('PRAGMA cache_size=-2048')
        for j in jobs:
            started=time.perf_counter();row={'id':j['id'],'title':j['title'],'url':j['url']}
            try:
                compressed=db.execute('SELECT body_zlib FROM raw_captures WHERE digest=? AND status=200 LIMIT 1',(j['id'],)).fetchone()
                if not compressed:raise ValueError('missing_capture')
                raw=zlib.decompress(compressed[0]);del compressed
                if sha256(raw).hexdigest()!=j['id']:raise ValueError('source_digest_mismatch')
                if not raw.lstrip().startswith(b'%PDF'):raise ValueError('capture_not_pdf')
                with pymupdf.open(stream=raw,filetype='pdf') as doc:
                    row.update(pages=len(doc),bookmarks=doc.get_toc(),page_profiles=[])
                    pages=sorted(set(a.pages)) if a.document_id else range(len(doc))
                    if any(i<0 or i>=len(doc) for i in pages):raise ValueError('page_out_of_range')
                    for i in pages:
                        page=doc[i]; text=page.get_text('dict',flags=pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES)
                        spans=[s for b in text['blocks'] if b['type']==0 for l in b['lines'] for s in l['spans']]
                        row['page_profiles'].append({'page':i+1,'chars':sum(len(s['text']) for s in spans),
                            'images':len(page.get_images()),'font_sizes':dict(Counter(round(s['size'],1) for s in spans)),
                            'width':page.rect.width,'height':page.rect.height})
                    if a.document_id:
                        import pymupdf4llm
                        data=pymupdf4llm.to_json(doc,pages=list(pages),use_ocr=False,show_progress=False)
                        (a.output/'layout.json').write_text(data if isinstance(data,str) else json.dumps(data),encoding='utf8')
                        for i in pages:doc[i].get_pixmap(matrix=pymupdf.Matrix(1,1)).save(str(a.output/f'page-{i+1}.png'))
                        row['layout_artifact_sha256']=sha256((a.output/'layout.json').read_bytes()).hexdigest()
                    row['status']='executed_not_quality_qualified'
            except Exception as exc:row.update(status='failed',error=type(exc).__name__,detail=str(exc)[:600])
            row['elapsed_seconds']=time.perf_counter()-started
            mem=psutil.Process().memory_info();row['peak_working_set_bytes']=getattr(mem,'peak_wset',mem.rss)
            rows.append(row)
            with (a.output/'results.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
            print(json.dumps({k:v for k,v in row.items() if k not in {'bookmarks','page_profiles','url'}},ensure_ascii=False),flush=True)
    (a.output/'summary.json').write_text(json.dumps({'documents':len(rows),'status':dict(Counter(r['status'] for r in rows)),
            'pages_inventoried':sum(len(r.get('page_profiles',[])) for r in rows),'remote_calls':0},indent=2),encoding='utf8')


if __name__=='__main__':main()
