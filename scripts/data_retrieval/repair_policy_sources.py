"""Recover Federal Register originals through its API and official GovInfo copy."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re

from scripts.data_retrieval.build_industry_foundation import Collector,dumps

CHALLENGE='Due to aggressive automated scraping of FederalRegister.gov'


def repair(worker):
    rows=worker.sql("SELECT DISTINCT s.* FROM sources s JOIN passages p ON p.source_id=s.id WHERE s.access_state='readable' AND instr(p.body,?)>0",(CHALLENGE,))
    def recover(row):
        meta=json.loads(row['metadata']);number=meta.get('document_number')
        if not number:
            match=re.search(r'/documents/\d{4}/\d{2}/\d{2}/(\d{4}-\d+)',row['url']);number=match[1] if match else None
        worker.sql("UPDATE sources SET access_state='blocked' WHERE id=?",(row['id'],))
        worker.gap('INSTITUTION::macro','policy_original:'+str(number),'tool_failure',
                   {'source_id':row['id'],'reason':'HTTP 200 challenge page, not policy text','public_information_gap':False})
        try:
            if not number:raise ValueError('policy_document_identity_missing')
            raw,_=worker.get(f'https://www.federalregister.gov/api/v1/documents/{number}.json')
            document=json.loads(raw);pdf=document['pdf_url']
            html=pdf.replace('/pdf/','/html/').removesuffix('.pdf')+'.htm'
            metadata={**meta,'original_source_id':row['id'],'original_filing_url':row['url'],'api_identity_url':document.get('json_url'),
                      'regulatory_type':document.get('type'),'effective_on':document.get('effective_on'),
                      'comments_close_on':document.get('comments_close_on'),'agencies':document.get('agencies',meta.get('agencies',[])),
                      'runtime_compatibility_parse':{'reason':'official GovInfo full text replaces misparsed access challenge','old_source_retained':True}}
            try:sid=worker.document('INSTITUTION::macro',html,'policy_regulation',title=row['title'],published=document['publication_date'],metadata=metadata)
            except Exception:sid=worker.document('INSTITUTION::macro',pdf,'policy_regulation',title=row['title'],published=document['publication_date'],metadata=metadata)
            # Preserve all existing publisher associations without changing IDs.
            for link in worker.sql('SELECT entity_id,category FROM entity_sources WHERE source_id=?',(row['id'],)):
                worker.sql('INSERT OR IGNORE INTO entity_sources VALUES(?,?,?)',(link['entity_id'],sid,link['category']))
            worker.gap('INSTITUTION::macro','policy_original:'+number,'available',{'recovered_source_id':sid,'failed_source_id':row['id'],'route':'Federal Register API -> official GovInfo original'})
            return {'document_number':number,'old_source_id':row['id'],'new_source_id':sid,'status':'recovered'}
        except Exception as exc:
            return {'document_number':number,'old_source_id':row['id'],'status':'tool_failure','error':type(exc).__name__}
    with ThreadPoolExecutor(max_workers=3) as pool:return list(pool.map(recover,rows))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    results=repair(Collector(a.db,json.loads(a.db.with_suffix('.plan.json').read_text(encoding='utf-8'))))
    a.output.write_text(dumps(results),encoding='utf-8');print(dumps({'recovered':sum(r['status']=='recovered' for r in results),'total':len(results)}))
