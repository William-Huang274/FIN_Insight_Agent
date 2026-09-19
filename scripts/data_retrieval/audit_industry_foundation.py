"""Audit an immutable industry library; keep generated coverage outside Git."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import csv
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from sec_agent.research_foundation.industry_data import companies, company_detail, data_page
from sec_agent.research_foundation.research_library import open_library


def audit(library_path, previous, output, restore_target=None):
    library=open_library(library_path)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    rows=companies(library_path,limit=200)['items'];coverage=[];gaps=[]
    for row in rows:
        detail=company_detail(library_path,row['entity_id'])
        annual=next((json.loads(g['detail']) for g in detail['gaps'] if g['category']=='annual_full_text'),{})
        coverage.append({'entity_id':row['entity_id'],'name':row['name'],'sector':row['sector'],'depth':row['expansion_depth'],
            'readable_materials':len({s['id'] for s in detail['sources']}),**detail['data_counts'],
            'institution_positions':detail['positions_count'],'annual_readable_years':','.join(annual.get('readable_years',[])),
            'annual_three_years_verified':annual.get('three_year_minimum_met',False),
            'open_gap_categories':';'.join(g['category'] for g in detail['gaps'] if g['status'] not in {'available','not_applicable'})})
        gaps.extend({'name':row['name'],**g} for g in detail['gaps'])
    for name,items in [('company-coverage',coverage),('company-gaps',gaps)]:
        (output/(name+'.json')).write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
        with (output/(name+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(items[0]));writer.writeheader();writer.writerows(items)
    with closing(sqlite3.connect(library_path)) as db:
        db.row_factory=sqlite3.Row
        counts={t:db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in
            ['sources','passages','entities','edges','company_cards','financial_points','market_prices','institution_positions','position_issuers','filing_catalog','raw_captures','collection_attempts']}
        integrity=db.execute('PRAGMA integrity_check').fetchone()[0]
        foreign_errors=[tuple(r) for r in db.execute('PRAGMA foreign_key_check')]
        invalid_passages=[r['id'] for r in db.execute('SELECT id,body,digest FROM passages') if sha256(r['body'].encode()).hexdigest()!=r['digest']]
        old=sqlite3.connect(Path(previous).resolve().as_uri()+'?mode=ro',uri=True)
        old_sources=old.execute('SELECT id,digest,url FROM sources').fetchall()
        preserved=all(tuple(db.execute('SELECT id,digest,url FROM sources WHERE id=?',(r[0],)).fetchone() or ())==r for r in old_sources)
        old.close()
        summary={'library_sha256':library.manifest['sha256'],'counts':counts,'integrity':integrity,'foreign_key_errors':foreign_errors,
            'readable_passages':db.execute("SELECT count(*) FROM passages p JOIN sources s ON s.id=p.source_id WHERE s.access_state='readable'").fetchone()[0],
            'invalid_passage_hashes':invalid_passages,'previous_source_count':len(old_sources),'previous_source_identity_digest_url_preserved':preserved,
            'company_count':sum(r.get('kind')=='company' for r in rows),
            'companies_with_three_year_annuals_verified':sum(r['annual_three_years_verified'] for r in coverage),
            'source_access':[dict(r) for r in db.execute('SELECT access_state,count(*) AS count FROM sources GROUP BY access_state')],
            'dimensions':[dict(r) for r in db.execute("SELECT json_extract(metadata,'$.research_dimension') AS dimension,count(*) AS count FROM sources WHERE access_state='readable' GROUP BY dimension")],
            'price_coverage':[dict(r) for r in db.execute('SELECT count(distinct entity_id) companies,min(trade_date) since,max(trade_date) latest FROM market_prices')],
            'financial_coverage':[dict(r) for r in db.execute('SELECT taxonomy,count(distinct entity_id) entities,count(*) rows FROM financial_points GROUP BY taxonomy')],
            'macro_latest':[dict(r) for r in db.execute("SELECT concept,min(period_end) since,max(period_end) latest,count(*) observations FROM financial_points WHERE taxonomy='FRED' GROUP BY concept")],
            'edge_types':[dict(r) for r in db.execute('SELECT predicate,status,count(*) count FROM edges GROUP BY predicate,status')],
            'acceptance':'engineering checks and coverage inventory; not blanket research-quality acceptance'}
        if restore_target:
            target=Path(restore_target)
            if target.exists():raise FileExistsError(target)
            target.parent.mkdir(parents=True,exist_ok=True)
            with closing(sqlite3.connect(target)) as restored:
                db.backup(restored)
                summary['restore_test']={'target':str(target),'integrity':restored.execute('PRAGMA integrity_check').fetchone()[0],
                    'same_source_count':restored.execute('SELECT count(*) FROM sources').fetchone()[0]==counts['sources'],
                    'same_table_counts':all(restored.execute('SELECT count(*) FROM '+table).fetchone()[0]==count for table,count in counts.items())}
    def read_one(row):
        c=company_detail(library_path,row['entity_id'])
        d=data_page(library_path,row['entity_id'],limit=2)
        return bool(c['entity_id']==row['entity_id'] and d['total']>=0)
    with ThreadPoolExecutor(max_workers=6) as pool:summary['concurrent_read_all_cards']=all(pool.map(read_one,rows))
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    if integrity!='ok' or foreign_errors or invalid_passages or not preserved or not summary['concurrent_read_all_cards']:
        raise ValueError('foundation_integrity_or_compatibility_failed')
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--previous',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--restore-target',type=Path)
    a=p.parse_args();print(json.dumps(audit(a.library,a.previous,a.output,a.restore_target),ensure_ascii=False))
