"""Source-plan enrichment and official macro series for the industry SQL release."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import json
from pathlib import Path
import re
from urllib.parse import quote,urljoin
from bs4 import BeautifulSoup

from scripts.data_retrieval.build_industry_foundation import Collector,dumps,identity


def add_sources(worker, sources):
    companies={c['slug']:c for c in worker.plan['companies']}
    for entry in sources:
        c=companies[entry['company']];e=c['entity_id']
        try:
            sid=worker.document(e,entry['url'],entry['category'],published=entry.get('published_at'))
            passages=worker.sql('SELECT id,locator,body FROM passages WHERE source_id=? ORDER BY rowid',(sid,))
            s=worker.sql('SELECT * FROM sources WHERE id=?',(sid,))[0]
            for edge in entry.get('edges',[]):
                target=companies[edge['object']];subject=companies[edge['subject']]
                labels=[target['slug'],target['name'].split(' / ')[0]]
                # The operator specified the predicate. This check binds it to
                # an actual containing passage; it does not infer a predicate.
                matches=[p for p in passages if any(label.casefold() in p['body'].casefold() for label in labels)]
                if not matches:
                    worker.gap(e,'edge:'+entry['key']+':'+target['slug'],'locator_review_required',{'source_id':sid,'target':target['name']});continue
                p=matches[0];date=s['published_at'] or worker.as_of
                qualifiers={'assertion_kind':'company_announcement','relationship_scope':entry['category'],
                    'announcement_is_not_fulfillment':True,'source_publication_known':bool(s['published_at']),
                    'runtime_locator_binding':'exact_passage','source_passage_id':p['id'],'operator_reviewed_predicate':True}
                worker.sql('INSERT OR IGNORE INTO edges VALUES('+','.join('?'*11)+')',
                    ('EDGE::'+identity(subject['entity_id'],target['entity_id'],edge['predicate'],sid)[:32],subject['entity_id'],edge['predicate'],target['entity_id'],sid,p['locator'],date,None,None,edge['status'],dumps(qualifiers)))
                for participant in {subject['entity_id'],target['entity_id']}:
                    worker.sql('INSERT OR IGNORE INTO entity_sources VALUES(?,?,?)',(participant,sid,entry['category']))
            print(dumps({'source':entry['key'],'status':'saved','source_id':sid}),flush=True)
        except Exception as exc:
            worker.gap(e,'source:'+entry['key'],'tool_failure',{'url':entry['url'],'error':type(exc).__name__,'public_information_gap':False})
            print(dumps({'source':entry['key'],'status':type(exc).__name__}),flush=True)


def annual_mirrors(worker,c):
    """Publisher-independent reproduction only after the official archive fails.

    Fallback copies remain labelled third-party mirrors and point at the original
    filing; primary archive successes retain their primary-source status.
    """
    if not c.get('ticker') or '.' in c['ticker']:return
    rows=worker.sql("SELECT * FROM filing_catalog WHERE entity_id=? AND form IN ('10-K','20-F','40-F') ORDER BY period_end DESC",(c['entity_id'],))
    years=set();ok=0;failed=0;mirrors=0
    for f in rows:
        if not f.get('period_end'):continue
        year=f['period_end'][:4]
        if year in years:continue
        years.add(year)
        if f['source_id']:ok+=1;continue
        try:
            sid=worker.document(c['entity_id'],f['url'],'filing',title=c['name']+' '+f['form']+' '+year,published=f['filed_at'],metadata={'accession':f['accession'],'period_end':f['period_end']})
            worker.sql('UPDATE filing_catalog SET source_id=? WHERE entity_id=? AND accession=?',(sid,c['entity_id'],f['accession']));ok+=1;continue
        except Exception:pass
        card=json.loads(worker.sql('SELECT payload FROM company_cards WHERE entity_id=?',(c['entity_id'],))[0]['payload'])
        exchange='NASDAQ' if any('Nasdaq' in str(x) for x in card.get('exchanges',[])) else 'NYSE'
        ticker=c['ticker'].replace('.','-')
        url=f'https://www.annualreports.com/HostedData/AnnualReportArchive/{ticker[0].lower()}/{exchange}_{ticker}_{year}.pdf'
        try:
            sid=worker.document(c['entity_id'],url,'annual_report_mirror',title=c['name']+' '+year+' 年报镜像',published=f['filed_at'],
                metadata={'original_filing_url':f['url'],'accession':f['accession'],'mirror_identity_verification':'pending_original_comparison','period_end':f['period_end'],'source_strength':'third_party_reproduction'})
            worker.sql('UPDATE filing_catalog SET source_id=? WHERE entity_id=? AND accession=?',(sid,c['entity_id'],f['accession']));ok+=1;mirrors+=1
        except Exception:failed+=1
    worker.gap(c['entity_id'],'annual_full_text',('available_with_mirror_qualification' if mirrors else 'available') if ok and not failed else 'partial' if ok else 'tool_failure',{'years':sorted(years),'full_texts':ok,'mirrors':mirrors,'failed':failed,'quarterlies_and_8k_tracked_separately':True})
    print(dumps({'company':c['slug'],'annual_full_texts':ok,'failed':failed}),flush=True)


def macro(worker):
    from scripts.deployment.research_workbench import configured_key
    e='INSTITUTION::macro';worker.sql('INSERT OR IGNORE INTO entities VALUES(?,?,?)',(e,'institution','宏观与监管资料'))
    # FRED values are current vintages, never backdated as real-time releases.
    series={'DFF':'美国有效联邦基金利率','DGS10':'美国10年期国债收益率','CPIAUCSL':'美国CPI','PPIACO':'美国PPI',
            'PAYEMS':'美国非农就业','UNRATE':'美国失业率','INDPRO':'美国工业生产','BOPGSTB':'美国商品服务贸易差额','DEXCHUS':'美元人民币汇率'}
    key=configured_key('FRED_API_KEY')
    import requests
    for code,label in series.items():
        try:
            public='https://fred.stlouisfed.org/series/'+code
            if key:
                # Credentials only in the transport parameters, never persisted
                # to a source URL, exception detail or request ledger.
                r=requests.get('https://api.stlouisfed.org/fred/series/observations',params={'api_key':key,'series_id':code,'file_type':'json','observation_start':worker.since,'observation_end':worker.as_of},timeout=35)
                r.raise_for_status();data=r.json();values=data.get('observations',[])
                mr=requests.get('https://api.stlouisfed.org/fred/series',params={'api_key':key,'series_id':code,'file_type':'json'},timeout=35);mr.raise_for_status();meta=mr.json()['seriess'][0]
            else:raise ValueError('fred_key_unavailable')
            sid=worker.source(e,public,label,'macro_series',dumps({'metadata':meta,'observations':values}),vintage='known_as_of',metadata={'known_at':worker.as_of,'current_revised':True,'historical_vintage':False,'units':meta.get('units'),'frequency':meta.get('frequency')})
            for v in values:
                worker.sql('INSERT OR IGNORE INTO observations VALUES(?,?,?,?,?,?,?)',('OBS::'+identity(code,v,worker.as_of)[:32],'macro_current_vintage',sid,e,v['date'],meta.get('units',''),dumps({'series_id':code,'label':label,**v,'known_at':worker.as_of,'current_vintage':True})))
            worker.gap(e,code,'available',{'observations':len(values),'current_revised':True})
        except Exception as exc:worker.gap(e,code,'tool_failure',{'error':type(exc).__name__,'public_information_gap':False})
    # Official regulation discovery with dates. Body ingestion follows the API's
    # html_url; proposals and final rules retain the API type and effective date.
    for term in ['artificial intelligence','advanced computing','data centers','semiconductor']:
        url='https://www.federalregister.gov/api/v1/documents.json?'+f'conditions[term]={quote(term)}&conditions[publication_date][gte]={worker.since}&conditions[publication_date][lte]={worker.as_of}&per_page=100&order=newest'
        try:
            raw,_=worker.get(url);data=json.loads(raw)
            for item in data.get('results',[]):
                try:worker.document(e,item['html_url'],'policy_regulation',published=item['publication_date'],title=item['title'],metadata={'jurisdiction':'US','regulatory_type':item.get('type'),'document_number':item.get('document_number'),'agencies':item.get('agencies'),'abstract':item.get('abstract')})
                except Exception as exc:worker.gap(e,'regulation:'+item['document_number'],'tool_failure',{'url':item['html_url'],'error':type(exc).__name__})
            worker.gap(e,'regulation_search:'+term,'partial' if data.get('total_pages',1)>1 else 'available',{'matches':data.get('count'),'pages':data.get('total_pages'),'captured_first_page':len(data.get('results',[])),'scope':'first result page; search hits require relevance screening'})
        except Exception as exc:worker.gap(e,'regulation_search:'+term,'tool_failure',{'error':type(exc).__name__})


def main():
    p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True);p.add_argument('--sources',type=Path);p.add_argument('--phase',choices=['sources','annuals','macro'],required=True);p.add_argument('--companies',default='')
    a=p.parse_args();plan=json.loads(a.db.with_suffix('.plan.json').read_text(encoding='utf-8'));worker=Collector(a.db,plan)
    if a.phase=='sources':add_sources(worker,json.loads(a.sources.read_text(encoding='utf-8')))
    elif a.phase=='macro':macro(worker)
    else:
        companies=[c for c in plan['companies'] if not a.companies or c['slug'] in a.companies.split(',')]
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures=[pool.submit(annual_mirrors,worker,c) for c in companies]
            for future in as_completed(futures):future.result()

if __name__=='__main__':main()
