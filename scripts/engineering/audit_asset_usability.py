"""Inventory every entity's usable views; counts do not imply research quality."""
import argparse
import json
from pathlib import Path
from sec_agent.research_foundation.industry_data import companies, company_detail, connect
from sec_agent.research_foundation.material_presentation import DIRECTORIES, directory_records


def audit(path):
    cards=companies(path,limit=200)
    if cards['next_offset'] is not None:raise ValueError('audit_requires_catalogue_pagination')
    results=[]; errors=[]; seen=set(); records=0
    with connect(path) as db:
        for item in cards['items']:
            d=company_detail(path,item['entity_id'])
            results.append({'entity_id':d['entity_id'],'name':d['name'],'type':d['profile']['type'],
                'data_counts':d['data_counts'],'positions':d['positions_count'],'channels':d['data_channels'],
                'source_count':len(d['sources']),'no_structured_financials':not d['data_counts']['financial_points']})
            for s in d['sources']:
                if s['id'] in seen:continue
                seen.add(s['id'])
                if not s['display_title'].strip():errors.append({'source_id':s['id'],'error':'empty_title'})
                if s['category'] in DIRECTORIES:
                    try:
                        rows=directory_records(db,s);records+=len(rows)
                        if any(not r['title'].strip() for r in rows):raise ValueError('empty_record_title')
                    except ValueError as exc:errors.append({'source_id':s['id'],'error':str(exc)})
        labels=[dict(r) for r in db.execute("SELECT taxonomy,count(*) AS rows FROM financial_points WHERE trim(label)='' GROUP BY taxonomy")]
    return {'entities':results,'unique_sources':len(seen),'directory_records':records,'errors':errors,
        'blank_original_labels_by_taxonomy':labels,'scope':'Full catalogue projection and structured-directory readability; not financial interpretation acceptance.'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--library',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    result=audit(a.library);Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'entities':len(result['entities']),'unique_sources':result['unique_sources'],'directory_records':result['directory_records'],'errors':result['errors']}))
