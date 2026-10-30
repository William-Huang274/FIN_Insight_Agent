"""Read-only source coverage inventory, not automatic query/fact verification.

Inputs are a private parser manifest and its source foundation database. No
network/model calls, SQL writes, numeric inference or deployment changes.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlparse


def filing_identity(url):
    match=re.fullmatch(r'/Archives/edgar/data/(\d+)/(\d{18})/[^/]+',urlparse(url).path)
    if not match or urlparse(url).hostname != 'www.sec.gov':
        return None
    cik, acc=match.groups()
    return {'cik':cik.zfill(10),'accession':acc[:10]+'-'+acc[10:12]+'-'+acc[12:]}


def audit(manifest, database, output):
    spec=json.loads(manifest.read_bytes())
    rows=[]
    with sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True) as db:
        db.execute('PRAGMA query_only=ON'); db.execute('BEGIN')
        accessions=sorted({identity['accession'] for s in spec['samples']
                           if (identity:=filing_identity(s['url']))})
        grouped={}
        if accessions:
            placeholders=','.join('?' for _ in accessions)
            for acc,a,b,c,n in db.execute(
                'SELECT accession,taxonomy,concept,unit,count(*) FROM financial_points '
                f'WHERE accession IN ({placeholders}) GROUP BY accession,taxonomy,concept,unit',accessions):
                grouped.setdefault(acc,[]).append({'taxonomy':a,'concept':b,'unit':c,'rows':n})
        for sample in spec['samples']:
            raw=Path(sample['path']).read_bytes()
            if sha256(raw).hexdigest()!=sample['raw_sha256']:
                raise ValueError('original_capture_changed')
            parsed_path=Path(sample['path']).parent.parent/'parsed'/(sample['id']+'.json')
            parsed=json.loads(parsed_path.read_bytes())
            if parsed['raw_sha256']!=sample['raw_sha256'] or parsed['status']!='parsed':
                raise ValueError('parsed_original_binding_changed')
            identity=filing_identity(sample['url'])
            facts=parsed['output'].get('xbrl_facts',[])
            if not isinstance(facts,list):raise ValueError('unexpected_parser_fact_shape')
            counts=grouped.get(identity['accession'],[]) if identity else []
            concepts=sorted({str(f.get('concept')) for f in facts if f.get('concept')})
            rows.append({'document_id':sample['document_id'],'title':sample['title'],
                         'url':sample['url'],'raw_sha256':sample['raw_sha256'],
                         'parsed_sha256':sha256(parsed_path.read_bytes()).hexdigest(),
                         'questions':sample.get('questions',[]),'filing':identity,
                         'same_accession_sql_rows':sum(x['rows'] for x in counts),
                         'sql_concepts':counts,'original_xbrl_fact_count':len(facts),
                         'original_numeric_financial_facts':sum(bool(f.get('is_numeric') and f.get('unit') and not str(f.get('concept','')).startswith('dei:')) for f in facts),
                         'original_xbrl_concepts':concepts,
                         'table_count':sum(x['kind']=='table' for x in parsed['output']['blocks']),
                         'query_fact_coverage':'requires_reviewed_concept_period_dimension_requirements',
                         'route':('inspect_existing_sql' if counts else 'inspect_original_xbrl' if facts else 'ordinary_table_or_prose_review')})
    result={'scope':'34-source coverage inventory; source presence is not question answer coverage',
            'manifest_sha256':sha256(manifest.read_bytes()).hexdigest(),
            'database':str(database.resolve()),'read_only':True,'provider_calls':0,
            'documents':len(rows),'with_same_accession_sql':sum(bool(r['same_accession_sql_rows']) for r in rows),
            'with_original_xbrl':sum(bool(r['original_xbrl_fact_count']) for r in rows),'sources':rows}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='sources'}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','database','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();audit(args.manifest,args.database,args.output)
