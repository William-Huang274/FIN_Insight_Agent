"""Follow a 13F notice's named managers without attributing them to a fund."""
import argparse
from datetime import datetime
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from scripts.data_retrieval.build_industry_foundation import Collector, dumps, identity


def notice_managers(raw):
    root=ET.fromstring(raw)
    def text(tag):
        return next((e.text or '' for e in root.iter() if e.tag.split('}')[-1]==tag),'')
    if text('submissionType') not in {'13F-NT','13F-NT/A'}:raise ValueError('not_a_13f_notice')
    period=datetime.strptime(text('periodOfReport'),'%m-%d-%Y').date().isoformat()
    managers=[]
    for e in root.iter():
        if e.tag.split('}')[-1]!='otherManager':continue
        row={x.tag.split('}')[-1]:(x.text or '').strip() for x in e}
        if not row.get('cik','').isdigit() or not row.get('name'):raise ValueError('notice_manager_identity_missing')
        managers.append(row)
    return period,managers


def expand(worker, parent_id, notice_id):
    notice=worker.sql("SELECT * FROM sources WHERE id=? AND access_state='readable'",(notice_id,))[0]
    raw,_=worker.get(notice['url']);period,managers=notice_managers(raw)
    results=[]
    for manager in managers:
        cik=str(int(manager['cik'])).zfill(10);eid='INSTITUTION::SEC-'+cik
        existing=worker.sql("SELECT entity_id FROM company_cards WHERE CAST(json_extract(payload,'$.sec_cik') AS INTEGER)=?",(int(cik),))
        if existing:eid=existing[0]['entity_id']
        card={'legal_name':manager['name'],'name':manager['name'],'products':[],'profile_type':'investment_institution','roles':['investment_institution','reporting_manager'],
              'institution_type':'13F 持仓申报管理人','sec_cik':cik,'listing_status':'not_inferred_from_registration','website':'https://www.sec.gov/edgar/browse/?CIK='+cik,
              'identity_basis':notice_id,'profile_source_id':notice_id,'classification_status':'explicit_13F_notice',
              'selection_reason':'13F NOTICE 中列示的代为申报管理人；不代表单只基金，也不据此认定股权母子公司。'}
        worker.sql('INSERT OR IGNORE INTO entities VALUES(?,?,?)',(eid,'institution',manager['name']))
        worker.sql('INSERT OR IGNORE INTO company_cards VALUES(?,?,?,?,?,?)',(eid,'投资与金融','','to_verify',1,dumps(card)))
        worker.sql('INSERT OR IGNORE INTO entity_sources VALUES(?,?,?)',(eid,notice_id,'institutional_notice'))
        passage=worker.sql('SELECT id,locator FROM passages WHERE source_id=? ORDER BY rowid LIMIT 1',(notice_id,))[0]
        worker.sql('INSERT OR IGNORE INTO edges VALUES('+','.join('?'*11)+')',
            ('EDGE::'+identity(parent_id,eid,notice_id,'reports_via')[:32],parent_id,'reports_via',eid,notice_id,passage['locator'],notice['published_at'],None,None,'disclosed',
             dumps({'period_end':period,'manager_cik':cik,'relationship_scope':'reports securities on behalf of named notice filer; not ownership or a fund allocation','source_passage_id':passage['id'],'runtime_locator_binding':'exact_passage','extraction_method':'13F_XML_otherManager'})))
        result={'entity_id':eid,'cik':cik,'notice_period':period}
        try:
            url=f'https://data.sec.gov/submissions/CIK{cik}.json';body,_=worker.get(url);sub=json.loads(body)
            if int(sub['cik'])!=int(cik):raise ValueError('manager_cik_mismatch')
            current=json.loads(worker.sql('SELECT payload FROM company_cards WHERE entity_id=?',(eid,))[0]['payload'])
            current.update(legal_name=sub['name'],sec_identity_url=url,incorporation_code=sub.get('stateOfIncorporation'),registered_address=sub.get('addresses',{}).get('business',{}))
            worker.sql('UPDATE company_cards SET payload=? WHERE entity_id=?',(dumps(current),eid))
            worker.source(eid,url,sub['name']+' · SEC 注册与申报目录','sec_submissions',dumps({k:sub.get(k) for k in ['cik','name','addresses','stateOfIncorporation']}))
            recent=sub['filings']['recent'];filings=[dict(zip(recent,values)) for values in zip(*recent.values())]
            filings=[f for f in filings if f['form'] in {'13F-HR','13F-HR/A'} and worker.since<=f['filingDate']<=worker.as_of]
            attempts=[]
            for f in filings:
                u=f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{f['accessionNumber'].replace('-','')}/{f['primaryDocument']}"
                worker.sql('INSERT OR IGNORE INTO filing_catalog VALUES(?,?,?,?,?,?,?,NULL)',(eid,f['accessionNumber'],f['form'],f['filingDate'],f.get('reportDate'),f['primaryDocument'],u))
                try:
                    row=worker.sql('SELECT * FROM filing_catalog WHERE entity_id=? AND accession=?',(eid,f['accessionNumber']))[0]
                    worker.positions({'entity_id':eid,'cik':cik,'name':sub['name']},row,None)
                    attempts.append({'accession':f['accessionNumber'],'status':'processed'})
                except Exception as exc:attempts.append({'accession':f['accessionNumber'],'status':'tool_failure','error':type(exc).__name__})
            count=worker.sql('SELECT count(*) n FROM institution_positions WHERE manager_id=?',(eid,))[0]['n']
            status='partial' if any(a['status']=='tool_failure' for a in attempts) else 'available' if count else 'holdings_not_obtained'
            worker.gap(eid,'institutional_positions',status,{'rows':count,'filings':attempts,'not_fund_specific':True,'public_information_gap':False})
            result.update(status=status,rows=count,filings=len(attempts))
        except Exception as exc:
            result.update(status='tool_failure',error=type(exc).__name__)
            worker.gap(eid,'institutional_positions','tool_failure',{**result,'public_information_gap':False})
        results.append(result);print(dumps(result),flush=True)
    # Reuse only unique, already reviewed CUSIP mappings. Ambiguities stay unmapped.
    worker.sql('INSERT OR IGNORE INTO position_issuers SELECT p.id,m.entity_id,? FROM institution_positions p JOIN (SELECT p2.cusip,min(i.entity_id) entity_id FROM institution_positions p2 JOIN position_issuers i ON i.position_id=p2.id WHERE length(p2.cusip)=9 GROUP BY p2.cusip HAVING count(DISTINCT i.entity_id)=1) m ON m.cusip=p.cusip',('exact CUSIP match to existing reviewed issuer mapping; no parent/fund aggregation',))
    worker.gap(parent_id,'delegated_reporting_managers','available' if all(r['status']=='available' for r in results) else 'partial',{'notice_source_id':notice_id,'managers':results,'holdings_not_consolidated_or_attributed_to_funds':True})
    worker.gap(parent_id,'institutional_positions','not_applicable',{'reason':'This selected filing is a 13F NOTICE, not a direct holdings table. Read the named reporting managers; absence of parent rows is not absence of holdings.','notice_source_id':notice_id,'period_end':period,'reporting_manager_ids':[r['entity_id'] for r in results]})
    return results


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True);p.add_argument('--parent',required=True);p.add_argument('--notice',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=expand(Collector(a.db,json.loads(a.db.with_suffix('.plan.json').read_text(encoding='utf-8'))),a.parent,a.notice)
    a.output.write_text(dumps(result),encoding='utf-8')
