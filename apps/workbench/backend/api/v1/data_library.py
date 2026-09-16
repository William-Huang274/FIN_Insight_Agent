"""Public document coverage and parameterized, read-only financial data browsing."""
from contextlib import closing
from pathlib import Path
import sqlite3

from fastapi import APIRouter, HTTPException, Query, Request
from ...authentication import current_owner
from sec_agent.research_foundation.public_library import library_nodes, document_catalog

from sec_agent.research_foundation.financial_library import FinancialQuery, financial_page


def build_data_library_router(attachments_root, fact_mart=None):
    router = APIRouter(prefix='/data-library')

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
