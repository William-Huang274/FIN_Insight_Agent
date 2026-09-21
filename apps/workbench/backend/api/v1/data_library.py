"""Public document coverage and parameterized, read-only financial data browsing."""
from contextlib import closing
from pathlib import Path
import sqlite3
import json

from fastapi import APIRouter, HTTPException, Query, Request
from ...authentication import current_owner
from sec_agent.research_foundation.public_library import library_nodes, document_catalog

from sec_agent.research_foundation.financial_library import FinancialQuery, financial_page


def build_data_library_router(attachments_root, fact_mart=None, research_library=None):
    router = APIRouter(prefix='/data-library')

    def foundation():
        path=research_library or Path(attachments_root)/'public-library'/'research-library.sqlite'
        if not Path(path).is_file(): raise HTTPException(503,'公司数据基座尚未接入')
        from sec_agent.research_foundation.industry_data import installed
        from sec_agent.research_foundation.research_library import open_library
        open_library(path)  # Refuse a corrupt or unpublished release on every route.
        if not installed(path): raise HTTPException(503,'当前资料版本尚无公司资料卡')
        return path

    @router.get('/companies')
    def company_catalog(request:Request,query:str=Query('',max_length=200),sector:str=Query('',max_length=100),offset:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=200)):
        current_owner(request)
        from sec_agent.research_foundation.industry_data import companies
        return companies(foundation(),query=query,sector=sector,offset=offset,limit=limit)

    @router.get('/companies/{entity_id}')
    def company_card(request:Request,entity_id:str):
        current_owner(request)
        from sec_agent.research_foundation.industry_data import company_detail
        try:return company_detail(foundation(),entity_id)
        except KeyError:raise HTTPException(404,'未找到这家公司') from None

    @router.get('/companies/{entity_id}/data')
    def company_data(request:Request,entity_id:str,kind:str=Query('financial',pattern='^(financial|prices|positions|holders|filings|derived|disclosures|relationships)$'),query:str=Query('',max_length=200),offset:int=Query(0,ge=0),limit:int=Query(30,ge=1,le=100),group:str=Query('',pattern='^(|operating|offering|compensation|macro|other)$'),account:str=Query('',max_length=100),fiscal_year:int|None=Query(None,ge=1900,le=2200),fiscal_period:str=Query('',pattern='^(|FY|Q1|Q2|Q3|Q4|H1|M9|instant|other|unknown)$'),derived_view:str=Query('latest',pattern='^(latest|history)$'),date_start:str=Query('',max_length=10),date_end:str=Query('',max_length=10),as_of:str=Query('9999-12-31',pattern=r'^\d{4}-\d{2}-\d{2}$')):
        current_owner(request)
        from sec_agent.research_foundation.industry_data import data_page
        try:return data_page(foundation(),entity_id,kind=kind,query=query,offset=offset,limit=limit,group=group,account=account,fiscal_year=fiscal_year,fiscal_period=fiscal_period,derived_view=derived_view,date_start=date_start,date_end=date_end,as_of=as_of)
        except ValueError as exc:raise HTTPException(422,str(exc)) from None

    @router.get('/companies/{entity_id}/network')
    def company_network(request:Request,entity_id:str,depth:int=Query(1,ge=1,le=2)):
        current_owner(request)
        from sec_agent.research_foundation.research_library import open_library
        library=open_library(foundation())
        # UI category filtering happens after readback. Give it a larger bounded
        # window than model context so holder rows cannot hide business links.
        result=library.graph_search(entity_id,'9999-12-31',depth=depth,max_edges=1000)
        ids={entity_id}|{e[k] for e in result['edges'] for k in ('subject','object')}
        result['nodes']=[e for e in library.entities() if e['id'] in ids]
        return result

    @router.get('/research-sources/{document_id}')
    def research_source(request:Request,document_id:str,offset:int=Query(0,ge=0),limit:int=Query(5,ge=1,le=20),passage_id:str|None=Query(None,max_length=200)):
        current_owner(request)
        from sec_agent.research_foundation.research_library import open_library
        library=open_library(foundation())
        if passage_id:
            anchor=library._query('SELECT rowid FROM passages WHERE id=? AND source_id=?',(passage_id,document_id))
            if not anchor:raise HTTPException(404,'这条依据不属于所选原文')
            offset=library._query('SELECT count(*) AS n FROM passages WHERE source_id=? AND rowid<?',(document_id,anchor[0]['rowid']))[0]['n']
        result=library.read(document_id,'9999-12-31',start=offset,limit=limit)
        result['offset']=offset
        if result.get('source') and isinstance(result['source'].get('metadata'),str):
            result['source']['metadata']=json.loads(result['source']['metadata'])
        result['total']=library._query('SELECT count(*) AS n FROM passages WHERE source_id=?',(document_id,))[0]['n']
        return result

    @router.get('/research-sources/{document_id}/presentation')
    def research_source_presentation(request:Request,document_id:str,offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=100)):
        current_owner(request)
        from sec_agent.research_foundation.industry_data import connect
        from sec_agent.research_foundation.material_presentation import material_view
        from sec_agent.research_foundation.research_library import open_library
        path=foundation()
        result=open_library(path).read(document_id,'9999-12-31',limit=1)
        if result['status']!='readable':raise HTTPException(404,'当前来源没有可读材料')
        with closing(connect(path)) as db:
            try:return material_view(db,result['source'],offset=offset,limit=limit) or {'kind':'text'}
            except ValueError as exc:raise HTTPException(422,str(exc)) from None

    @router.get('/market-prices')
    def market_prices(request: Request, ticker: str = Query('',max_length=30),
                      as_of: str = Query('9999-12-31',pattern=r'^\d{4}-\d{2}-\d{2}$'),
                      limit: int = Query(30,ge=1,le=100)):
        current_owner(request)
        path = Path(attachments_root)/'public-library'/'market-prices.sqlite'
        if not path.is_file(): raise HTTPException(503,'行情数据库尚未接入')
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
            db.row_factory=sqlite3.Row
            items=[dict(r) for r in db.execute(
                'SELECT * FROM market_prices WHERE trade_date<=? AND (?=\'\' OR ticker=?) ORDER BY trade_date DESC LIMIT ?',
                (as_of,ticker.upper(),ticker.upper(),limit))]
        return {'items':items,'notice':'行情供应商日线观察，原价与复权收盘价分列；抓取时间不代表历史可获得时点，非发行人财务事实或盈利预测。'}

    @router.get('/sources')
    def sources(request: Request, ticker: str = '', query: str = Query('',max_length=200),
                year: str = '', kind: str = '', as_of: str = Query('9999-12-31',pattern=r'^\d{4}-\d{2}-\d{2}$'),
                offset: int = Query(0,ge=0), limit: int = Query(24,ge=1,le=100)):
        current_owner(request)
        rows, digest = library_nodes(attachments_root, as_of)
        docs = document_catalog(rows)
        filtered = [d for d in docs if (not ticker or d['ticker'] == ticker.upper())
                    and (not year or str(d.get('period_end') or d.get('fiscal_period') or '').startswith(year))
                    and (not kind or d['source_role'] == kind)
                    and (not query or query.casefold() in ' '.join(str(d.get(k) or '') for k in ('ticker','company','title','fiscal_period')).casefold())]
        return {'items': filtered[offset:offset+limit], 'total': len(filtered), 'snapshot':digest,
                'tickers':sorted({str(d['ticker']) for d in docs if d['ticker']}),
                'years':sorted({str(d.get('period_end') or d.get('fiscal_period') or '')[:4] for d in docs if str(d.get('period_end') or d.get('fiscal_period') or '')[:4].isdigit()},reverse=True),
                'kinds':sorted({str(d['source_role']) for d in docs if d['source_role']}),
                'notice':'公共原文可检索，不等于已核验事实；当前目录来自已保存快照。年份筛选为报告期结束年份。'}

    @router.get('/sources/{document_id}')
    def document(request: Request, document_id: str, offset: int = Query(0,ge=0), limit: int = Query(5,ge=1,le=20)):
        current_owner(request)
        rows, digest = library_nodes(attachments_root)
        selected = [r for r in rows if r['parent_document_id'] == document_id and r['node_kind'] == 'section']
        if not selected: raise HTTPException(404, '目录中没有这份公共资料')
        # Full sections, rendered as text/Markdown by the client, never raw HTML.
        return {'sections':[{'title':' / '.join(r.get('section_path') or []), 'text':r.get('content',''), 'selection_id':r['node_id']} for r in selected[offset:offset+limit]],
                'total':len(selected),'snapshot':digest, 'document':next(d for d in document_catalog(rows) if d['document_id']==document_id)}

    @router.get('/financials')
    def financials(request: Request, ticker: str = Query('',max_length=30), query: str = Query('',max_length=200),
                   fiscal_year: int | None = None, period: str = Query('',max_length=30), metric: str = Query('',max_length=100),
                   as_of: str = Query('9999-12-31',pattern=r'^\d{4}-\d{2}-\d{2}$'),
                   offset: int = Query(0,ge=0), limit: int = Query(30,ge=1,le=100)):
        current_owner(request)
        try:
            return financial_page(fact_mart, FinancialQuery(ticker=ticker, query=query, fiscal_year=fiscal_year,
                period=period, metric=metric, as_of=as_of, offset=offset, limit=limit))
        except FileNotFoundError:
            raise HTTPException(503, '财务数据库尚未接入') from None

    return router
