"""Freeze every existing source binding before offline structural qualification."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sqlite3


def freeze(inventory,database,output):
    raw=inventory.read_bytes(); sources=[json.loads(line) for line in raw.splitlines() if line]
    if len({s['document_id'] for s in sources})!=len(sources):raise ValueError('duplicate_source_binding')
    with sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True) as db:
        captures={}
        for url,digest,mime,size in db.execute('SELECT url,digest,content_type,length(body_zlib) FROM raw_captures WHERE status=200'):
            captures.setdefault(url,{})[digest]={'sha256':digest,'content_type':mime,'compressed_bytes':size}
    rows=[];jobs={}
    for s in sources:
        versions=list(captures.get(s['url'],{}).values())
        status='unique_archived_capture' if len(versions)==1 else 'ambiguous_archived_versions' if versions else 'original_not_in_capture_store'
        row={**s,'original_resolution':status,'original_candidates':versions}
        rows.append(row)
        for version in versions:
            # Every observed original is checked; ambiguous binding stays open.
            key=version['sha256']
            jobs.setdefault(key,{'id':key,'capture':version,'url':s['url'],'title':s['title'],
                                 'domain':s['domain'],'form':s.get('form'),'bindings':[]})['bindings'].append(s['document_id'])
    result={'inventory_sha256':sha256(raw).hexdigest(),'database':str(database.resolve()),
            'source_bindings':len(rows),'unique_urls':len({s['url'] for s in sources}),
            'resolution':dict(Counter(s['original_resolution'] for s in rows)),
            'jobs':list(jobs.values()),'sources':rows,'provider_calls':0,
            'scope':'all frozen library bindings; availability and parse execution are not structural accuracy'}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False)
    print(json.dumps({k:v for k,v in result.items() if k not in {'jobs','sources'}},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['inventory','database','output']:p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();freeze(a.inventory,a.database,a.output)
