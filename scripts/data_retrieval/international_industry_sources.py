"""Official DART data and report-directory fallback for non-SEC companies."""
import argparse
import calendar
import json
from pathlib import Path
import re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from scripts.data_retrieval.build_industry_foundation import Collector,dumps,identity


def finmind_period(record,dataset):
    if dataset=='TaiwanStockMonthRevenue':
        year,month=int(record['revenue_year']),int(record['revenue_month'])
        return f'{year:04d}-{month:02d}-01',f'{year:04d}-{month:02d}-{calendar.monthrange(year,month)[1]:02d}'
    return None,record.get('date','')


def dart_point_rows(entity_id,source_id,account,year,report,as_of):
    """DART half-year IS/CIS current amount is 3 months; cumulative is separate.

    Applies to the December-year-end companies configured by this collector.
    Official field contract: DS003 / 2019020, thstrm_amount/thstrm_add_amount.
    """
    receipt=account.get('rcept_no','')
    filed=f'{receipt[:4]}-{receipt[4:6]}-{receipt[6:8]}' if len(receipt)>=8 else as_of
    if filed>as_of:return []
    annual=report=='11011';income=account.get('sj_div') in {'IS','CIS'}
    end=f'{year}-12-31' if annual else f'{year}-06-30'
    fields=['thstrm_amount']+(['thstrm_add_amount'] if not annual and income else [])
    rows=[]
    for field in fields:
        value=account.get(field,'').replace(',','')
        if not re.fullmatch(r'-?\d+(?:\.\d+)?',value):continue
        start=None if account.get('sj_div')=='BS' else f'{year}-01-01'
        fp='FY' if annual else 'H1'
        if not annual and income and field=='thstrm_amount':start=f'{year}-04-01';fp='Q2'
        payload={**account,'amount_field':field,'period_basis':'DART field contract; December fiscal year; current interim IS/CIS=3 months, add_amount=YTD','unit_source':'currency field','statement':account.get('sj_div'),
            'field_contract':'https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019020'}
        rid=identity(entity_id,source_id,account) if field=='thstrm_amount' else identity(entity_id,source_id,account,field)
        unit=account.get('currency') or 'unit_unconfirmed'
        if account.get('account_id') in {'ifrs-full_BasicEarningsLossPerShare','ifrs-full_DilutedEarningsLossPerShare'}:
            payload['original_currency_field']=unit
            payload['unit_source']='IFRS per-share concept and DART currency field'
            unit+='/shares'
        rows.append((rid,entity_id,'DART-IFRS',account.get('account_id','')+':'+account.get('sj_div',''),account.get('account_nm',''),value,unit,
            start,end,filed,year,fp,'DART-'+report,receipt,source_id,dumps(payload)))
    return rows


def dart(worker,company,corp_code):
    from scripts.deployment.research_workbench import configured_key
    key=configured_key('DART_API_KEY')
    e=company['entity_id']
    for year,report in [(2023,'11011'),(2024,'11011'),(2025,'11011'),(2026,'11012')]:
        public=f'https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json?corp_code={corp_code}&bsns_year={year}&reprt_code={report}&fs_div=CFS'
        try:
            response=requests.get('https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json',params={'crtfc_key':key,'corp_code':corp_code,'bsns_year':year,'reprt_code':report,'fs_div':'CFS'},timeout=35)
            response.raise_for_status();data=response.json()
            if data.get('status')!='000':raise ValueError('dart_'+str(data.get('status')))
            rows=data['list']
            if any(r.get('corp_code')!=corp_code for r in rows):raise ValueError('dart_entity_mismatch')
            sid=worker.source(e,public,company['name']+f' · DART {year} '+('年度' if report=='11011' else '半年度')+'合并报表','financial_api',dumps(data),metadata={'provider':'DART','report_code':report,'fiscal_year':year,'fs_div':'CFS','source_unit':'currency in each account','point_in_time':'current API capture; receipt number binds filing','original_filing_url':'https://dart.fss.or.kr/dsaf001/main.do?rcpNo='+rows[0]['rcept_no']})
            for r in rows:
                worker.sql('INSERT OR REPLACE INTO financial_points VALUES('+','.join('?'*16)+')',
                    dart_point_rows(e,sid,r,year,report,worker.as_of),many=True)
            worker.gap(e,'DART:'+str(year),'available',{'accounts':len(rows),'source_id':sid,'corp_code':corp_code})
        except Exception as exc:worker.gap(e,'DART:'+str(year),'tool_failure',{'error':type(exc).__name__,'public_information_gap':False})


def directory(worker,c,url):
    e=c['entity_id']
    try:
        raw,_=worker.get(url);soup=BeautifulSoup(raw,'html.parser');links=[]
        for a in soup.select('a[href]'):
            href=urljoin(url,a['href']);text=a.get_text(' ',strip=True);context=text+' '+href
            if '.pdf' not in href.lower():continue
            years=re.findall(r'20(?:23|24|25|26)',context)
            if not years:continue
            if not any(word in context.lower() for word in ['report','annual','financial','result','interim','年','季度','中期','ir/','finance']):continue
            if href not in [h for h,t in links]:links.append((href,text))
        ok=0;fails=[]
        for href,title in links[:16]:
            try:
                worker.document(e,href,'official_report',title=c['name']+' '+(title or href.rsplit('/',1)[-1]),metadata={'discovered_from':url,'publication_date':'requires document reading; not inferred from report year'})
                ok+=1
            except Exception as exc:fails.append({'url':href,'error':type(exc).__name__})
        worker.gap(e,'official_report_directory','available' if ok and not fails else 'partial' if ok else 'parser_or_discovery_gap',{'url':url,'pdf_candidates':len(links),'saved':ok,'failed':fails,'candidate_limit':16,'unread_candidates':max(0,len(links)-16)})
        print(dumps({'directory':c['slug'],'saved':ok,'candidates':len(links)}),flush=True)
    except Exception as exc:worker.gap(e,'official_report_directory','tool_failure',{'url':url,'error':type(exc).__name__})


def finmind(worker,company,stock_id):
    """Public provider fallback, retaining unconfirmed units explicitly.

    These are provider-normalized observations, not a replacement for audited
    statements. Missing release dates must never be backdated to period ends.
    """
    for dataset in ['TaiwanStockFinancialStatements','TaiwanStockBalanceSheet','TaiwanStockCashFlowsStatement','TaiwanStockMonthRevenue']:
        start=worker.since if dataset.endswith('MonthRevenue') else worker.plan['filings_since']
        url=f'https://api.finmindtrade.com/api/v4/data?dataset={dataset}&data_id={stock_id}&start_date={start}&end_date={worker.as_of}'
        try:
            raw,_=worker.get(url);data=json.loads(raw)
            if data.get('status')!=200:raise ValueError('finmind_non_success')
            records=data.get('data',[])
            if any(str(r.get('stock_id'))!=str(stock_id) for r in records):raise ValueError('finmind_entity_mismatch')
            sid=worker.source(company['entity_id'],url,company['name']+' · '+dataset,'financial_api',dumps(data),metadata={'provider':'FinMind','data_table':'financial_points','provider_normalized_not_audited_original':True,'unit_verification':'pending comparison with official statement; no implicit scale conversion','period_basis':'provider dates retained; release dates unavailable; capture date used as known-at','documentation':'https://finmind.github.io/tutor/TaiwanMarket/Fundamental/'})
            rows=[]
            for r in records:
                day=r.get('date','')
                if day>worker.as_of:continue
                value=r.get('value',r.get('revenue'))
                if value is None:continue
                concept=r.get('type','monthly_revenue');label=r.get('origin_name',concept)
                start,end=finmind_period(r,dataset)
                rows.append((identity(company['entity_id'],sid,r),company['entity_id'],'FinMind:'+dataset,concept,label,str(value),'provider_unit_unconfirmed',start,end,worker.as_of,int(end[:4]),None,dataset,'',sid,dumps({**r,'known_at':worker.as_of,'disclosure_date_unknown':True,'unit_scale_unverified':True,'period_basis':'revenue_year/revenue_month; provider date is not observation period' if start else 'provider date; flow period not verified'})))
            worker.sql('INSERT OR IGNORE INTO financial_points VALUES('+','.join('?'*16)+')',rows,many=True)
            worker.gap(company['entity_id'],dataset,'partial',{'records':len(rows),'source_id':sid,'remaining':'unit/scale and flow-period verification against primary reports; no financial calculations until resolved'})
            print(dumps({'company':company['slug'],'dataset':dataset,'rows':len(rows)}),flush=True)
        except Exception as exc:worker.gap(company['entity_id'],dataset,'tool_failure',{'error':type(exc).__name__,'public_information_gap':False})


def main():
    p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True);p.add_argument('--phase',choices=['dart','directories','finmind'],required=True);p.add_argument('--manifest',type=Path)
    a=p.parse_args();plan=json.loads(a.db.with_suffix('.plan.json').read_text(encoding='utf-8'));worker=Collector(a.db,plan);companies={c['slug']:c for c in plan['companies']}
    if a.phase=='dart':
        for slug,code in [('samsung','00126380'),('skhynix','00164779')]:dart(worker,companies[slug],code)
    elif a.phase=='finmind':
        for slug,code in [('foxconn','2317'),('quanta','2382'),('wistron','3231'),('wiwynn','6669')]:finmind(worker,companies[slug],code)
    else:
        for row in json.loads(a.manifest.read_text(encoding='utf-8')):directory(worker,companies[row['company']],row['url'])

if __name__=='__main__':main()
