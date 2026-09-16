"""One read-only query implementation for browsing and pinning financial rows."""
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from pydantic import BaseModel, ConfigDict, Field

METRIC_LABELS = {'revenue':'营业收入','operating_cash_flow':'经营现金流 CFO','capital_expenditures':'资本开支 Capex',
    'net_income':'净利润','operating_income':'营业利润','gross_profit':'毛利润','cash_and_equivalents':'现金及现金等价物',
    'accounts_payable':'应付账款','accounts_receivable':'应收账款','inventory':'存货','diluted_eps':'稀释每股收益 EPS','shares_outstanding':'流通股数'}


def content_digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class FinancialQuery(BaseModel):
    model_config = ConfigDict(extra='forbid')
    ticker: str = Field(default='', max_length=30)
    query: str = Field(default='', max_length=200)
    fiscal_year: int | None = None
    period: str = Field(default='', max_length=30)
    metric: str = Field(default='', max_length=100)
    as_of: str = Field(default='9999-12-31', pattern=r'^\d{4}-\d{2}-\d{2}$')
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=24, ge=1, le=100)


def financial_page(path, selection: FinancialQuery):
    if not path or not Path(path).is_file():
        raise FileNotFoundError('财务数据库尚未接入')
    q = selection.model_dump()
    where, args = ['filed_at <= ?'], [q['as_of']]
    for column, value in [('ticker',q['ticker'].upper()),('fiscal_year',q['fiscal_year']),('fiscal_period',q['period']),('metric_id',q['metric'])]:
        if value not in ('', None):
            where.append(column+' = ?'); args.append(value)
    if q['query']:
        matched = [key for key,label in METRIC_LABELS.items() if q['query'].casefold() in label.casefold()]
        where.append('(instr(lower(metric_id),lower(?))>0 OR instr(lower(legal_name),lower(?))>0 OR instr(lower(ticker),lower(?))>0 OR instr(lower(concept),lower(?))>0'+ (' OR metric_id IN ('+','.join('?' for _ in matched)+')' if matched else '') + ')')
        args.extend([q['query']]*4); args.extend(matched)
    condition = ' AND '.join(where)
    # Explicit columns: original capture filesystem locations are not public data.
    fields = ('observation_id ticker cik legal_name metric_id unit_family taxonomy concept concept_priority value_decimal unit '
              'period_start period_end duration_days period_role fiscal_year fiscal_period reported_fiscal_year reported_fiscal_period '
              'form accession_number filed_at accepted_at frame primary_document citation_url companyfacts_sha256 submissions_sha256 '
              'captured_at superseded_by_observation_id').split()
    with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN')  # count, rows and facets share one read snapshot
        available = {r['name'] for r in db.execute('PRAGMA table_info(company_fact_observations)')}
        projection = ','.join(f for f in fields if f in available)
        total = db.execute('SELECT count(*) FROM company_fact_observations WHERE '+condition,args).fetchone()[0]
        # rowid breaks ties in older marts that predate observation_id.
        tie = 'observation_id' if 'observation_id' in available else 'rowid'
        rows = [dict(r) for r in db.execute('SELECT '+projection+' FROM company_fact_observations WHERE '+condition+
            ' ORDER BY ticker,fiscal_year DESC,period_end DESC,metric_id,filed_at DESC,'+tie+' LIMIT ? OFFSET ?', [*args,q['limit'],q['offset']])]
        facets = {key:[r[0] for r in db.execute('SELECT DISTINCT '+column+' FROM company_fact_observations ORDER BY '+column)]
                  for key,column in [('tickers','ticker'),('years','fiscal_year'),('metrics','metric_id'),('periods','fiscal_period')]}
    items = [{**r, 'selection_id': content_digest([q['offset']+i, r])} for i,r in enumerate(rows)]
    return {'items':items,'total':total,**facets,'metric_labels':METRIC_LABELS,'selection_query':q,
            'snapshot':content_digest({'query':q,'items':items,'total':total}),
            'notice':'保留各披露版本；同一期间可能有多行。数值为来源单位，正式计算由 Agent 标准指标工具按时点选择。'}
