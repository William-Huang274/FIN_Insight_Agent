"""Replay selected PDF pages through the existing candidate adapter, offline.

This is a parser comparison, not product ingestion or financial acceptance.
Publication metadata not supplied by the frozen manifest remains explicitly
unknown. OCR is not silently enabled when the selected page lacks native text.
"""
import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import socket
import sqlite3
import sys
import time
import zlib

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))


def denied(*args,**kwargs):raise RuntimeError('offline_probe_network_or_ocr_denied')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--prior-probes',type=Path,nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    socket.socket.connect=denied;socket.socket.connect_ex=denied;socket.create_connection=denied
    from ingestion.pdf_layout import parse_captured_pdf_layout
    import psutil
    m=json.loads(a.manifest.read_bytes());jobs={j['id']:j for j in m['jobs']};selections={}
    for folder in a.prior_probes:
        identity=json.loads((folder/'identity.json').read_bytes())
        if identity['manifest_sha256']!=sha256(a.manifest.read_bytes()).hexdigest():raise ValueError('scope_mismatch')
        scope=identity['TokenBudgetBasis']['input_scale']
        selections.setdefault(scope['document_id'],set()).update(i+1 for i in scope['zero_based_pages'])
    plan={'manifest_sha256':sha256(a.manifest.read_bytes()).hexdigest(),
          'implementation_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
          'adapter_sha256':sha256((ROOT/'src/ingestion/pdf_layout.py').read_bytes()).hexdigest(),
          'structure_adapter_sha256':sha256((ROOT/'src/ingestion/pdf_structure_candidates.py').read_bytes()).hexdigest(),
          'packages':{n:version(n) for n in ['pdfplumber','pdfminer.six','pypdf']},
          'pages_one_based':{k:sorted(v) for k,v in selections.items()},'ocr':'disabled_not_installed_or_called',
          'publication_metadata':'unknown_not_evaluated','provider_calls':0,'production_enabled':False}
    (a.output/'identity.json').write_text(json.dumps(plan,indent=2),encoding='utf8')
    rows=[]
    with sqlite3.connect(Path(m['database']).as_uri()+'?mode=ro',uri=True) as db:
        for sid,pages in selections.items():
            job=jobs[sid];raw=zlib.decompress(db.execute('SELECT body_zlib FROM raw_captures WHERE digest=? AND status=200 LIMIT 1',(sid,)).fetchone()[0])
            if sha256(raw).hexdigest()!=sid:raise ValueError('original_changed')
            rawpath=a.output/(sid+'.pdf');rawpath.write_bytes(raw)
            capture={'document_path':rawpath.name,'sha256':sid,'byte_count':len(raw),
                     'title':job['title'],'source_url':job['url'],'publication_date':'unknown'}
            del raw
            for page in sorted(pages):
                start=time.perf_counter();row={'id':sid,'page':page,'title':job['title']}
                try:
                    result=parse_captured_pdf_layout(capture,repository_root=a.output,
                           selected_page_numbers=[page],ocr_engine_factory=denied)
                    path=a.output/f'{sid}-page-{page}.json'
                    path.write_text(json.dumps(result,ensure_ascii=False),encoding='utf8')
                    pg=result['pages'][0]
                    row.update(status='executed_not_quality_qualified',artifact=path.name,
                        artifact_sha256=sha256(path.read_bytes()).hexdigest(),
                        tables=pg['table_region_count'],text_blocks=len(pg['text_blocks']),
                        words=pg['word_count'],extraction_mode=pg['extraction_mode'])
                except Exception as exc:row.update(status='failed_or_requires_ocr',error=type(exc).__name__,detail=str(exc)[:500])
                mem=psutil.Process().memory_info()
                row.update(elapsed_seconds=time.perf_counter()-start,peak_working_set_bytes=getattr(mem,'peak_wset',mem.rss))
                with (a.output/'results.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
                rows.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
    (a.output/'summary.json').write_text(json.dumps({'pages':len(rows),'executed':sum(r['status']=='executed_not_quality_qualified' for r in rows),'provider_calls':0},indent=2),encoding='utf8')


if __name__=='__main__':main()
