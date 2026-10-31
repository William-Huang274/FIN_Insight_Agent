"""Apply a bounded HTML context repair across a frozen original library.

Reuses prior parser/heading repairs. Only changed documents are materialized;
each receipt binds the original and parent artifact. No models or publication.
"""
import argparse
from collections import Counter
import gc
import gzip
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import sys
import time
import zlib

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from source_structure_contract import source_containers
from refine_document_chapters import refine
from validate_source_structure_audit import validate


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['manifest','baseline','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();m=json.loads(a.manifest.read_bytes())
    a.output.mkdir(parents=True,exist_ok=True)
    for sub in ['receipts','documents']:(a.output/sub).mkdir(exist_ok=True)
    identity={'manifest_sha256':sha256(a.manifest.read_bytes()).hexdigest(),
              'baseline_identity_sha256':sha256((a.baseline/'execution-identity.json').read_bytes()).hexdigest(),
              'code':{name:sha256((ROOT/name).read_bytes()).hexdigest() for name in [
                  'scripts/engineering/repair_library_blank_heading_context.py',
                  'scripts/engineering/source_structure_contract.py',
                  'scripts/engineering/refine_document_chapters.py',
                  'scripts/engineering/validate_source_structure_audit.py']},'provider_calls':0}
    stamp=a.output/'identity.json'
    if stamp.exists() and json.loads(stamp.read_bytes())!=identity:raise ValueError('resume_identity_changed')
    stamp.write_text(json.dumps(identity),encoding='utf8')
    counts=Counter()
    with sqlite3.connect(Path(m['database']).as_uri()+'?mode=ro',uri=True) as db:
        db.execute('PRAGMA cache_size=-2048')
        for job in m['jobs']:
            sid=job['id'];receipt_path=a.output/'receipts'/f'{sid}.json'
            parent=json.loads((a.baseline/'receipts'/f'{sid}.json').read_bytes())
            if receipt_path.exists():
                row=json.loads(receipt_path.read_bytes())
                if row['parent_artifact_sha256']!=parent['artifact_sha256']:raise ValueError('parent_changed')
                if row['status']=='repaired_structure_checked':
                    artifact=a.output/'documents'/f'{sid}.json.gz'
                    if sha256(artifact.read_bytes()).hexdigest()!=row['artifact_sha256']:
                        raise ValueError('resumed_artifact_changed')
                counts[row['status']]+=1
                continue
            started=time.perf_counter();row={'id':sid,'route':parent['route'],
                'parent_artifact_sha256':parent['artifact_sha256'],'parent_directory':str(a.baseline),
                'bindings':job['bindings'],'promoted_headings':[]}
            try:
                if parent['route'] not in {'edgartools','trafilatura_xml'}:
                    row['status']='not_applicable_parent_retained'
                else:
                    compressed=db.execute('SELECT body_zlib FROM raw_captures WHERE digest=? AND status=200 LIMIT 1',(sid,)).fetchone()
                    if not compressed:raise ValueError('original_missing')
                    raw=zlib.decompress(compressed[0]);del compressed
                    if sha256(raw).hexdigest()!=sid:raise ValueError('original_changed')
                    sources=source_containers(raw);del raw
                    relevant={r['id']:r for r in sources if r.get('blank_layout_context',{}).get('followed_by_prose')
                              and r.get('heading_eligible') and not r.get('excluded_navigation') and not r.get('table_id')}
                    row['context_candidates']=len(relevant)
                    row['status']='html_checked_parent_retained'
                    if relevant:
                        packed=(a.baseline/'documents'/f'{sid}.json.gz').read_bytes()
                        if sha256(packed).hexdigest()!=parent['artifact_sha256']:raise ValueError('parent_artifact_changed')
                        d=json.loads(gzip.decompress(packed));del packed
                        old_sources={r['id']:r for r in d['source_containers']}
                        delta={k:v for k,v in relevant.items() if k in old_sources and not old_sources[k].get('heading_eligible')}
                        old_texts=[b['text'] for b in d['blocks']]
                        old_tables=[b for b in d['blocks'] if b['kind']=='table']
                        old_table_content=json.dumps([{k:b.get(k) for k in ['text','headers','rows','footer']} for b in old_tables],sort_keys=True)
                        for b in d['blocks']:
                            source=delta.get(b.get('source_container_id'))
                            if source and parent['route']=='edgartools' and b['kind']=='text' and b.get('source_location_status')=='unique_complete_container':
                                old_sources[source['id']].update(source)
                                b.update(kind='heading',level=3,parser_level=3,heading_basis=source['role_basis'])
                                row['promoted_headings'].append({'source_container_id':source['id'],'text':source['text'],
                                                               'context':source['blank_layout_context']})
                        if row['promoted_headings']:
                            d=refine(d)
                            if d['outline']:d['issues']=[i for i in d['issues'] if i['kind']!='long_document_without_recognized_heading']
                            if old_texts!=[b['text'] for b in d['blocks']]:raise ValueError('unexpected_block_text_change')
                            tables=[{k:b.get(k) for k in ['text','headers','rows','footer']} for b in d['blocks'] if b['kind']=='table']
                            if old_table_content!=json.dumps(tables,sort_keys=True):raise ValueError('table_content_changed')
                            errors=validate(d)
                            if errors:raise ValueError('structure_validation:'+str(errors[:5]))
                            path=a.output/'documents'/f'{sid}.json.gz'
                            with gzip.open(path,'wt',encoding='utf8',compresslevel=3) as f:json.dump(d,f,ensure_ascii=False)
                            row.update(status='repaired_structure_checked',artifact_sha256=sha256(path.read_bytes()).hexdigest(),
                                       headings=len(d['outline']),issues=dict(Counter(i['kind'] for i in d['issues'])),
                                       block_text_and_table_content_preserved=True)
                        del d
                    del sources,relevant
            except Exception as exc:row.update(status='failed',error=type(exc).__name__,detail=str(exc)[:600])
            row['elapsed_seconds']=time.perf_counter()-started
            receipt_path.write_text(json.dumps(row,ensure_ascii=False),encoding='utf8')
            counts[row['status']]+=1;gc.collect()
            if sum(counts.values())%50==0:print(json.dumps(dict(counts)),flush=True)
    (a.output/'summary.json').write_text(json.dumps(dict(counts),indent=2),encoding='utf8')
    print(json.dumps(dict(counts)),flush=True)


if __name__=='__main__':main()
