"""Resumable, API-first acquisition into a new SQL research-library release.

Raw provider bodies, failures and typed observations are retained in SQL. The
input is an operator-reviewed source plan, never model-generated trade advice.
No model calls. Publication is a separate, explicit operation after review.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import sqlite3
from threading import Lock
import time
from urllib.parse import quote, urljoin, urlsplit
import zlib

from bs4 import BeautifulSoup
import requests
import trafilatura
from pypdf import PdfReader

from sec_agent.research_foundation.industry_data import SCHEMA


def dumps(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,default=str)
def identity(*parts): return sha256(dumps(parts).encode()).hexdigest()
def now(): return datetime.now(timezone.utc).isoformat()


class Collector:
    def __init__(self,path,plan):
        self.path=Path(path); self.plan=plan; self.as_of=plan['as_of']; self.since=plan['recent_since']
        self.sql_lock=Lock(); self.sec_lock=Lock(); self.sec_last=0
        self.ua='FinSight-Public-Research/0.1.4 (+https://github.com/; public source research)'
        from scripts.deployment.research_workbench import configured_key
        contact=configured_key('FINSIGHT_SEC_CONTACT_EMAIL')
        if contact:
            from financial_facts.sec_snapshot import sec_user_agent_from_environment
            self.ua=sec_user_agent_from_environment({'FINSIGHT_SEC_CONTACT_EMAIL':contact})

    def sql(self,sql,args=(),many=False):
        with self.sql_lock,closing(sqlite3.connect(self.path,timeout=30)) as db,db:
            db.execute('PRAGMA foreign_keys=ON');db.row_factory=sqlite3.Row
            cur=db.executemany(sql,args) if many else db.execute(sql,args)
            return [dict(r) for r in cur.fetchall()] if cur.description else []

    def gap(self,e,category,status,detail):
        self.sql('INSERT OR REPLACE INTO data_gaps VALUES(?,?,?,?,?)',(e,category,status,dumps(detail),now()))

    def get(self,url):
        cached=self.sql('SELECT * FROM raw_captures WHERE url=?',(url,))
        if cached:
            r=cached[0]
            if r['status']!=200: raise ValueError('cached_http_'+str(r['status']))
            return zlib.decompress(r['body_zlib']),r['content_type']
        if urlsplit(url).hostname in {'data.sec.gov','www.sec.gov'}:
            with self.sec_lock:
                time.sleep(max(0,0.6-(time.monotonic()-self.sec_last)));self.sec_last=time.monotonic()
        try:
            r=requests.get(url,headers={'User-Agent':self.ua,'Accept-Encoding':'gzip, deflate'},timeout=(10,35))
            body=r.content
            if len(body)>48*1024*1024: raise ValueError('response_exceeds_48MiB')
            ct=r.headers.get('content-type','')
            self.sql('INSERT OR IGNORE INTO raw_captures VALUES(?,?,?,?,?,?)',(url,now(),r.status_code,ct,sha256(body).hexdigest(),zlib.compress(body)))
            self.sql('INSERT INTO collection_attempts(url,captured_at,status,detail) VALUES(?,?,?,?)',(url,now(),str(r.status_code),dumps({'bytes':len(body),'final_url':r.url})))
            r.raise_for_status(); return body,ct
        except Exception as exc:
            self.sql('INSERT INTO collection_attempts(url,captured_at,status,detail) VALUES(?,?,?,?)',(url,now(),'execution_failure',type(exc).__name__))
            raise

    def source(self,e,url,title,category,body,*,published=None,metadata=None,vintage=None):
        digest=sha256(body.encode()).hexdigest(); sid='SRC::'+identity(url,digest)[:32]
        meta={'category':category,'entity_id':e,'captured_at':now(),**(metadata or {})}
        if published:
            if published>self.as_of: raise ValueError('future_publication')
            v=vintage or 'dated_original'
            meta['window']='recent' if published>=self.since else 'historical_background'
        else:
            v=vintage or 'known_as_of';meta.update(known_at=self.as_of,window='current_capture_publication_unknown')
        self.sql('INSERT OR IGNORE INTO sources VALUES(?,?,?,?,?,?,?,?)',(sid,title,url,published,v,'readable',digest,dumps(meta)))
        self.sql('INSERT OR IGNORE INTO entity_sources VALUES(?,?,?)',(e,sid,category))
        # Keep complete ordered text; overlapping character windows are only
        # navigation segments, not independent factual assertions.
        with self.sql_lock,closing(sqlite3.connect(self.path,timeout=30)) as db,db:
            db.execute('PRAGMA foreign_keys=ON')
            existing={r[0] for r in db.execute('SELECT id FROM passages WHERE source_id=?',(sid,))}
            rows=[]
            for part,start in enumerate(range(0,len(body),5200)):
                text=body[max(0,start-250):start+5200]
                pid='PASSAGE::'+identity(sid,part)[:32];loc=f'text-part:{part}'
                if pid not in existing:rows.append((pid,sid,loc,text,sha256(text.encode()).hexdigest()))
            db.executemany('INSERT INTO passages VALUES(?,?,?,?,?)',rows)
            db.executemany('INSERT INTO passage_search VALUES(?,?,?)',[(r[0],r[1],r[3]) for r in rows])
        return sid

    def document(self,e,url,category,*,title=None,published=None,metadata=None):
        raw,ct=self.get(url)
        if raw.startswith(b'%PDF'):
            reader=PdfReader(BytesIO(raw)); pages=[p.extract_text() or '' for p in reader.pages]
            text='\n\n'.join(f'[PDF page {i+1}]\n{x}' for i,x in enumerate(pages))
            meta={'parser':'pypdf','pages':len(pages),'ocr_performed':False}
        else:
            soup=BeautifulSoup(raw,'lxml')
            inline_facts=soup.find_all(['ix:nonfraction','ix:nonnumeric','ix:fraction'])
            inline_count=len(inline_facts)
            page_title=soup.title.get_text(' ',strip=True) if soup.title else ''
            visible=soup.get_text(' ',strip=True)
            if 'Your request has been flagged as potentially automated' in visible or 'Due to aggressive automated scraping of FederalRegister.gov' in visible:
                raise ValueError('http_200_access_challenge_not_document')
            if re.search(r'bot manager|access denied|just a moment|request rejected|security verification',page_title,re.I):
                raise ValueError('http_200_access_challenge_not_document')
            title=title or (soup.title.get_text(' ',strip=True) if soup.title else url)
            if not published:
                for attrs in ({'property':'article:published_time'},{'name':'date'},{'name':'pubdate'},{'itemprop':'datePublished'}):
                    tag=soup.find('meta',attrs=attrs)
                    candidate=(tag.get('content','') if tag else '')[:10]
                    if re.fullmatch(r'\d{4}-\d{2}-\d{2}',candidate):published=candidate;break
            # Article cleaners drop unknown ix:* elements including their text.
            # Preserve visible inline XBRL values before calling the maintained
            # extractor. Hidden header facts are not displayed report content.
            if inline_count:
                for tag in list(soup.find_all('ix:header')):tag.decompose()
                for tag in list(soup.find_all(lambda t:t.name.startswith('ix:'))):tag.unwrap()
            # A financial filing is a whole report, not a news article. Article
            # selection can omit an entire financial-statement appendix even
            # after inline values are restored. Retain all report text/tables.
            text=None if inline_count else trafilatura.extract(raw,include_tables=True,include_comments=False, favor_recall=True)
            meta={'parser':'trafilatura','document_coverage':{'complete_document':False,'scope':'main text and tables extracted','unread_scope':'navigation, images and unparsed interactive content'}}
            if inline_count:
                meta['runtime_compatibility_parse']={'reason':'preserve displayed inline XBRL text and whole-report financial appendix','inline_xbrl_elements':inline_count,'inline_xbrl_unwrapped':True,'hidden_ix_header_removed':True,'raw_html_retained':True,'units_and_contexts_not_inferred_from_display_text':True}
            if not text or len(text.strip())<120:
                # SEC exhibit HTML can be rejected by article extraction despite
                # a valid body. Keep table rows/columns visible; do not call this
                # a missing disclosure or infer typed numbers from these cells.
                for tag in soup(['script','style','noscript']):tag.decompose()
                for table in reversed(soup.find_all('table')):
                    lines=[]
                    for tr in table.find_all('tr'):
                        cells=tr.find_all(['td','th'],recursive=False)
                        if cells:lines.append(' | '.join(cell.get_text(' ',strip=True) for cell in cells))
                    if lines:table.replace_with('\n[TABLE: original cell order; merged cells require original view]\n'+'\n'.join(lines)+'\n[/TABLE]\n')
                text=soup.get_text('\n',strip=True)
                if len(text)<120:raise ValueError('insufficient_parsed_text')
                meta['parser']='beautifulsoup_row_delimited_fallback'
                meta['runtime_compatibility_parse']={**meta.get('runtime_compatibility_parse',{}),'fallback_reason':'complete inline XBRL report required; article selection disabled' if inline_count else 'article extractor returned insufficient text','table_cells':'original order; rowspan/colspan not normalized','raw_html_retained':True}
                if inline_count:
                    meta['runtime_compatibility_parse']['full_visible_report']=True
                    meta['document_coverage']={'complete_document':False,'scope':'all parsed report text and ordered table cells; inline XBRL values retained','unread_scope':'images, CSS visual layout and merged-cell geometry; consult original for these'}
        return self.source(e,url,title or url,category,text,published=published,metadata={**meta,**(metadata or {})})

    def company(self,c):
        e=c['entity_id']; errors=[]
        try:
            sid=self.document(e,c['website'],'company_profile',title=c['name']+' · 官方业务入口')
            card=self.sql('SELECT payload FROM company_cards WHERE entity_id=?',(e,))[0]
            payload=json.loads(card['payload']); payload['profile_source_id']=sid
            self.sql('UPDATE company_cards SET payload=? WHERE entity_id=?',(dumps(payload),e))
            self.gap(e,'profile','available',{'source_id':sid,'tags':'operator classified; official original available'})
        except Exception as exc: self.gap(e,'profile','tool_failure',{'error':type(exc).__name__,'url':c['website'],'public_information_gap':False})
        if c.get('cik'):
            try:self.sec(c)
            except Exception as exc:errors.append('sec:'+type(exc).__name__);self.gap(e,'financial_reports','tool_failure',{'error':type(exc).__name__,'public_information_gap':False})
        else:self.gap(e,'financial_reports','alternative_source_required',{'reason':'No SEC registrant identity in source plan; use local exchange/official reporting; do not infer nondisclosure'})
        if c.get('ticker'):
            try:self.prices(c)
            except Exception as exc:errors.append('prices:'+type(exc).__name__);self.gap(e,'market_prices','tool_failure',{'error':type(exc).__name__,'public_information_gap':False})
        else:self.gap(e,'market_prices','listing_identity_unresolved',{'reason':'No verified tradable security identifier; private/unlisted status needs source confirmation'})
        self.gap(e,'relationships','review_pending',{'reason':'Source-bound edges require explicit evidence; co-occurrence is not a relationship'})
        self.gap(e,'financing','review_pending',{'reason':'Financing announcements, filings and positions need event-level extraction'})
        try:self.news(c)
        except Exception as exc:self.gap(e,'recent_news','tool_failure',{'error':type(exc).__name__,'public_information_gap':False})
        print(dumps({'company':c['slug'],'done':'api_and_profile','errors':errors}),flush=True)

    def sec(self,c):
        e=c['entity_id'];cik=str(int(c['cik'])).zfill(10)
        url=f'https://data.sec.gov/submissions/CIK{cik}.json';raw,_=self.get(url); sub=json.loads(raw)
        if str(sub.get('cik','')).lstrip('0')!=cik.lstrip('0'): raise ValueError('sec_cik_identity_mismatch')
        card=json.loads(self.sql('SELECT payload FROM company_cards WHERE entity_id=?',(e,))[0]['payload'])
        card.update(legal_name=sub['name'],sec_cik=cik,sec_tickers=sub.get('tickers',[]),exchanges=sub.get('exchanges',[]),
                    sic=sub.get('sic'),sic_description=sub.get('sicDescription'),sec_identity_url=url)
        if sub.get('tickers'):
            card['listing_status']='exchange_listed_per_SEC';
            if not c.get('ticker'): c['ticker']=sub['tickers'][0]
        self.sql('UPDATE company_cards SET payload=?,ticker=? WHERE entity_id=?',(dumps(card),c.get('ticker',''),e))
        self.source(e,url,sub['name']+' · SEC 注册与申报目录','sec_submissions',dumps({k:sub.get(k) for k in ['cik','name','tickers','exchanges','sic','sicDescription','businessDescription','formerNames']}))
        recent=sub['filings']['recent']; filings=[]
        def unpack(r):return [dict(zip(r.keys(),v)) for v in zip(*r.values())] if r else []
        filings.extend(unpack(recent))
        for hist in sub['filings'].get('files',[]):
            if hist.get('filingTo','')>=self.plan['filings_since']:
                h,_=self.get('https://data.sec.gov/submissions/'+hist['name']);filings.extend(unpack(json.loads(h)))
        eligible=[f for f in filings if self.plan['filings_since']<=f['filingDate']<=self.as_of]
        for f in eligible:
            if f['form'] not in {'10-K','10-K/A','10-Q','10-Q/A','8-K','8-K/A','20-F','20-F/A','40-F','40-F/A','6-K','13F-HR','13F-HR/A','S-1','S-1/A','424B4'}:continue
            u=f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{f['accessionNumber'].replace('-','')}/{f['primaryDocument']}"
            self.sql('INSERT OR IGNORE INTO filing_catalog VALUES(?,?,?,?,?,?,?,NULL)',(e,f['accessionNumber'],f['form'],f['filingDate'],f.get('reportDate'),f['primaryDocument'],u))
        manager=c['slug'] in {'vanguard','fidelity','blackrock','blackstone','brookfield'}
        if manager:
            self.gap(e,'institutional_positions','filing_read_pending',{'forms':sum(f['form'].startswith('13F') and f['filingDate']>=self.since for f in eligible)})
        if not manager or c.get('ticker'):
            try:self.facts(c)
            except Exception as exc:self.gap(e,'financial_data','tool_failure',{'error':type(exc).__name__,'public_information_gap':False})
        self.gap(e,'financial_reports','filing_read_pending',{'filings':len(eligible),'since':self.plan['filings_since'],'catalogue_is_not_full_text':True})

    def facts(self,c):
        url=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(c['cik']):010d}.json"
        raw,_=self.get(url);data=json.loads(raw); e=c['entity_id']
        if int(data['cik'])!=int(c['cik']):raise ValueError('companyfacts_identity_mismatch')
        sid=self.source(e,url,c['name']+' · SEC XBRL 财务数据','financial_api',dumps({'entityName':data['entityName'],'cik':data['cik'],'taxonomies':list(data.get('facts',{}))}),
            metadata={'data_table':'financial_points','coverage':'all concepts, all units, all filed vintages within window','known_at':self.as_of})
        rows=[]
        for tax,concepts in data.get('facts',{}).items():
            for concept,fact in concepts.items():
                for unit,values in fact.get('units',{}).items():
                    for v in values:
                        if not (self.plan['filings_since']<=v.get('end','')<=self.as_of and v.get('filed','')<=self.as_of):continue
                        rows.append((identity(e,tax,concept,unit,v),e,tax,concept,(fact.get('label') or '').strip() or f'{tax}:{concept}',str(v['val']),unit,
                          v.get('start'),v['end'],v['filed'],v.get('fy'),v.get('fp'),v.get('form',''),v.get('accn',''),sid,dumps(v)))
        self.sql('INSERT OR IGNORE INTO financial_points VALUES('+','.join('?'*16)+')',rows,many=True)
        self.gap(e,'financial_data','available',{'points':len(rows),'source_id':sid,'cutoff':self.as_of,'preserve_all_vintages':True})

    def prices(self,c):
        url=f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(c['ticker'])}?range=3mo&interval=1d&events=div%2Csplits"
        raw,_=self.get(url);data=json.loads(raw)['chart']['result'][0];e=c['entity_id'];meta=data['meta']
        sid=self.source(e,url,c['name']+' · 近三个月日行情','market_api',dumps(meta),metadata={'data_table':'market_prices','provider':'Yahoo unofficial public chart API','observation_window':[self.since,self.as_of]})
        values=data['indicators']['quote'][0];adj=data['indicators'].get('adjclose',[{}])[0].get('adjclose',[]); rows=[]
        from zoneinfo import ZoneInfo
        tz=ZoneInfo(meta.get('exchangeTimezoneName','UTC'))
        for i,t in enumerate(data.get('timestamp',[])):
            day=datetime.fromtimestamp(t,tz).date().isoformat()
            if not self.since<=day<=self.as_of:continue
            rows.append((e,c['ticker'],day,*[values.get(k,[None]*len(data['timestamp']))[i] for k in ('open','high','low','close')],adj[i] if i<len(adj) else None,values.get('volume',[])[i],meta.get('currency'),sid))
        self.sql('INSERT OR IGNORE INTO market_prices VALUES('+','.join('?'*11)+')',rows,many=True)
        self.gap(e,'market_prices','available' if rows else 'empty_window',{'rows':len(rows),'source_id':sid,'requested_window':[self.since,self.as_of],'last_trade_date':rows[-1][2] if rows else None})

    def news(self,c):
        # Discovery metadata only. A headline is never promoted to article text.
        from email.utils import parsedate_to_datetime
        from xml.etree import ElementTree as ET
        query=c['name'].split(' / ')[0]+f' after:{self.since} before:{self.as_of}'
        url='https://news.google.com/rss/search?q='+quote(query)+'&hl=en-US&gl=US&ceid=US:en'
        raw,_=self.get(url);root=ET.fromstring(raw);items=[]
        for item in root.findall('.//item'):
            try:day=parsedate_to_datetime(item.findtext('pubDate')).date().isoformat()
            except Exception:continue
            if self.since<=day<=self.as_of:items.append({'title':item.findtext('title'),'url':item.findtext('link'),'publisher':item.findtext('source'),'published_at':day,'article_body_available':False})
        if items:
            self.source(c['entity_id'],url,c['name']+' · 近期新闻发现目录','news_discovery',dumps(items),metadata={'coverage':'RSS metadata only; follow original publishers before making claims','items':len(items),'window_start':self.since})
        self.gap(c['entity_id'],'recent_news','discovery_only' if items else 'empty_window',{'items':len(items),'next':'Read original articles; metadata is not article evidence'})

    def filing_bodies(self,c):
        if not c.get('cik'):return
        e=c['entity_id'];rows=self.sql('SELECT * FROM filing_catalog WHERE entity_id=? ORDER BY filed_at DESC',(e,)); success=failed=0
        for f in rows:
            if f['source_id']:success+=1;continue
            # Annual documents are captured by the annual/source fallback phase.
            # Keep this phase focused on quarterlies and current disclosures.
            if f['form'] in {'10-K','10-K/A','20-F','20-F/A'}:continue
            if f['form'] not in {'10-K','10-K/A','10-Q','10-Q/A','20-F','20-F/A','S-1','424B4'} and f['filed_at']<self.since:continue
            try:
                sid=self.document(e,f['url'],'filing',title=c['name']+' '+f['form']+' '+f['filed_at'],published=f['filed_at'],metadata={'form':f['form'],'period_end':f['period_end'],'accession':f['accession']})
                self.sql('UPDATE filing_catalog SET source_id=? WHERE entity_id=? AND accession=?',(sid,e,f['accession'])); success+=1
                if f['form'].startswith('13F'):self.positions(c,f,sid)
            except Exception:failed+=1
        self.gap(e,'financial_reports','available' if success and not failed else 'partial' if success else 'tool_failure',{'full_texts':success,'failed_fetch_or_parse':failed,'catalogue_count':len(rows),'public_information_gap':False})
        print(dumps({'company':c['slug'],'full_filings':success,'failed':failed}),flush=True)

    def positions(self,c,f,sid):
        from xml.etree import ElementTree as ET
        base=f"https://www.sec.gov/Archives/edgar/data/{int(c['cik'])}/{f['accession'].replace('-','')}/"
        raw,_=self.get(base+'index.json');docs=json.loads(raw)['directory']['item']
        for d in docs:
            if not d['name'].endswith('.xml') or d['name']==f['primary_document']:continue
            u=base+d['name'];body,_=self.get(u)
            try:root=ET.fromstring(body)
            except ET.ParseError:continue
            records=[x for x in root.iter() if x.tag.split('}')[-1]=='infoTable']
            if not records:continue
            parsed=[]
            for item in records:
                values={x.tag.split('}')[-1]:(x.text or '').strip() for x in item.iter() if len(x)==0}
                parsed.append(values)
            ps=self.source(c['entity_id'],u,c['name']+' · 13F 持仓 '+f['period_end'],'institutional_positions',dumps({'rows':len(parsed),'period_end':f['period_end'],'filed_at':f['filed_at'],'data_table':'institution_positions'}),published=f['filed_at'])
            records=[(identity(ps,v),c['entity_id'],v.get('nameOfIssuer',''),v.get('cusip',''),v.get('titleOfClass',''),v.get('value',''),'USD',v.get('sshPrnamt'),v.get('sshPrnamtType'),v.get('putCall'),f['period_end'],f['filed_at'],ps,dumps(v)) for v in parsed]
            self.sql('INSERT OR IGNORE INTO institution_positions VALUES('+','.join('?'*14)+')',records,many=True)
            self.gap(c['entity_id'],'institutional_positions','available',{'positions':len(parsed),'period_end':f['period_end'],'filed_at':f['filed_at'],'value_unit':'USD per current 13F schema; no look-through of private holdings'})

    def holdings(self,c):
        if not c.get('cik'):return
        rows=self.sql("SELECT * FROM filing_catalog WHERE entity_id=? AND form IN ('13F-HR','13F-HR/A') AND filed_at>=? ORDER BY filed_at",(c['entity_id'],self.since))
        for row in rows:
            try:self.positions(c,row,row.get('source_id'))
            except Exception as exc:self.gap(c['entity_id'],'13F:'+row['accession'],'tool_failure',{'error':type(exc).__name__,'public_information_gap':False})
        print(dumps({'company':c['slug'],'13F_filings_attempted':len(rows)}),flush=True)

    def exhibits(self,c):
        """Capture disclosure attachments at SEC before attempting IR scraping."""
        if not c.get('cik'):return
        filings=self.sql("SELECT * FROM filing_catalog WHERE entity_id=? AND form IN ('8-K','6-K') AND filed_at>=? ORDER BY filed_at DESC",(c['entity_id'],self.since))
        saved=0;failures=[];candidates=0
        for f in filings:
            base=f"https://www.sec.gov/Archives/edgar/data/{int(c['cik'])}/{f['accession'].replace('-','')}/"
            try:
                # Most primary filings already contain direct exhibit links.
                # Reuse that captured HTML, avoiding an unnecessary archive call.
                raw,_=self.get(f['url']);soup=BeautifulSoup(raw,'html.parser')
                names={urljoin(f['url'],a['href']).removeprefix(base) for a in soup.select('a[href]') if urljoin(f['url'],a['href']).startswith(base)}
                items=[{'name':n} for n in names if re.search(r'(ex(?:hibit)?[-_]?99|ex[-_]?[0-9]*99|earnings|release|presentation)',n.lower())]
                if not items:
                    raw,_=self.get(base+'index.json');items=json.loads(raw)['directory']['item']
                for item in items:
                    name=item['name'];lower=name.lower()
                    if not lower.endswith(('.htm','.html','.pdf')) or not re.search(r'(ex(?:hibit)?[-_]?99|ex[-_]?[0-9]*99|earnings|release|presentation)',lower):continue
                    candidates+=1
                    try:
                        self.document(c['entity_id'],base+name,'filing_exhibit',title=c['name']+' '+f['filed_at']+' '+name,published=f['filed_at'],metadata={'parent_accession':f['accession'],'parent_form':f['form'],'exhibit_content_role':'read original: may include financial results, management remarks, transactions or presentations'})
                        saved+=1
                    except Exception as exc:failures.append({'url':base+name,'error':type(exc).__name__})
            except Exception as exc:failures.append({'url':base+'index.json','error':type(exc).__name__})
        self.gap(c['entity_id'],'recent_disclosure_exhibits','available' if saved and not failures else 'partial' if saved else 'discovery_gap',{'filings_checked':len(filings),'candidates':candidates,'saved':saved,'failures':failures,'filter':'ex99 or named earnings/release/presentation; other exhibits remain in filing index'})
        print(dumps({'company':c['slug'],'exhibits':saved,'failures':len(failures)}),flush=True)

    def community(self,c):
        e=c['entity_id']; statuses={}
        if c.get('github_org'):
            url=f"https://api.github.com/orgs/{c['github_org']}/repos?sort=updated&per_page=100"
            try:
                raw,_=self.get(url);repos=[r for r in json.loads(raw) if self.since<=r.get('pushed_at','')[:10]<=self.as_of]
                fields=['full_name','description','html_url','language','license','stargazers_count','forks_count','open_issues_count','created_at','updated_at','pushed_at','default_branch','archived']
                sid=self.source(e,url,c['name']+' · GitHub近期仓库','community_repository',dumps([{k:r.get(k) for k in fields} for r in repos]),metadata={'official_org_verification':'operator configured; verify link from official site','popularity_is_not_market_share':True})
                statuses['github']={'repos':len(repos),'source_id':sid}
                for r in repos[:3]:
                    u=f"https://api.github.com/repos/{r['full_name']}/readme"; b,_=self.get(u);v=json.loads(b)
                    import base64
                    text=base64.b64decode(v.get('content','')).decode('utf-8',errors='replace')
                    if text:self.source(e,v.get('html_url',u),r['full_name']+' README','repository_readme',text,metadata={'repository_updated_at':r['pushed_at'],'readme_published_at_unknown':True})
            except Exception as exc:statuses['github']={'error':type(exc).__name__}
        if c.get('hf_org'):
            url=f"https://huggingface.co/api/models?author={c['hf_org']}&sort=lastModified&direction=-1&limit=30&full=true"
            try:
                raw,_=self.get(url);models=[r for r in json.loads(raw) if self.since<=r.get('lastModified','')[:10]<=self.as_of]
                sid=self.source(e,url,c['name']+' · Hugging Face近期模型','model_catalogue',dumps(models),metadata={'downloads_are_platform_statistics_not_market_share':True})
                statuses['huggingface']={'models':len(models),'source_id':sid}
                for r in models[:4]:
                    u='https://huggingface.co/'+r['id']+'/raw/main/README.md'
                    b,_=self.get(u);self.source(e,u,r['id']+' model card','model_card',b.decode('utf-8',errors='replace'),metadata={'model_updated_at':r.get('lastModified'),'model_card_date_unknown':True})
            except Exception as exc:statuses['huggingface']={'error':type(exc).__name__}
        if c.get('x_handle'):statuses['x']={'handle':c['x_handle'],'state':'source_link_only_no_authenticated_timeline','url':'https://x.com/'+c['x_handle']}
        self.gap(e,'community_social','partial' if statuses else 'not_applicable',statuses or {'reason':'No designated model/repository account in this company scope'})


def initialize(path,base,plan):
    if path.exists():return
    path.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(Path(base).resolve().as_uri()+'?mode=ro',uri=True)) as src,closing(sqlite3.connect(path)) as dst:
        src.backup(dst);dst.executescript(SCHEMA)
        dst.execute("UPDATE snapshot_metadata SET value='building_public_library' WHERE key='state'")
        existing={row[2].casefold():row[0] for row in dst.execute('SELECT * FROM entities WHERE kind=\'company\'')}
        aliases={'nvidia':'NVIDIA','amazon':'Amazon','amd':'AMD','coreweave':'CoreWeave','oracle':'Oracle','talen':'Talen'}
        for c in plan['companies']:
            e=aliases.get(c['slug'],existing.get(c['name'].casefold(),'COMPANY::'+c['slug']));c['entity_id']=e
            dst.execute('INSERT OR IGNORE INTO entities VALUES(?,?,?)',(e,'company',c['name']))
            for a in {c['name'],c['slug'],c.get('ticker',''),*c['products']} - {''}:
                dst.execute('INSERT OR IGNORE INTO aliases VALUES(?,?)',(a,e))
            dst.execute('INSERT INTO company_cards VALUES(?,?,?,?,?,?)',(e,c['sector'],c.get('ticker',''),c.get('country',''),c['depth'],dumps(c)))
        dst.commit()
    path.with_suffix('.plan.json').write_text(dumps(plan),encoding='utf-8')


def main():
    p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True);p.add_argument('--base',type=Path,required=True);p.add_argument('--db',type=Path,required=True)
    p.add_argument('--phase',choices=['base','filings','community','holdings','exhibits'],default='base');p.add_argument('--companies',default='');p.add_argument('--workers',type=int,default=3)
    a=p.parse_args();plan=json.loads(a.plan.read_text(encoding='utf-8'));initialize(a.db,a.base,plan)
    plan=json.loads(a.db.with_suffix('.plan.json').read_text(encoding='utf-8'));worker=Collector(a.db,plan)
    companies=[c for c in plan['companies'] if not a.companies or c['slug'] in a.companies.split(',')]
    method={'base':worker.company,'filings':worker.filing_bodies,'community':worker.community,'holdings':worker.holdings,'exhibits':worker.exhibits}[a.phase]
    with ThreadPoolExecutor(max_workers=min(4,max(1,a.workers))) as pool:
        futures={pool.submit(method,c):c for c in companies}
        for future in as_completed(futures):
            try:future.result()
            except Exception as exc: print(dumps({'company':futures[future]['slug'],'phase':a.phase,'failure':type(exc).__name__}),flush=True)

if __name__=='__main__':main()
