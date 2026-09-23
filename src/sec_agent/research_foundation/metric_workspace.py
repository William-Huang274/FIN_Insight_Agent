"""Shared metric catalog, observation cards and comparison projection.

Read-only over immutable releases. Dates describe observations; financial inputs
retain their own periods. No interpolation, implicit FX or front-end arithmetic.
"""
from collections import defaultdict
from contextlib import closing
from datetime import date
import json
import sqlite3

from . import derived_financials
from .industry_data import connect
from .metric_reviews import read_reviews, qualify_rows
from .financial_metric_contracts import CONCEPTS

CONCEPT_LABELS={'revenue':'营业收入','cost':'营业成本','gross':'毛利','operating':'营业利润','profit':'期间净利润','parent_profit':'归母净利润','assets':'总资产','liabilities':'总负债','equity':'归母权益','current_assets':'流动资产','current_liabilities':'流动负债','cash':'现金及现金等价物','cfo':'经营活动现金流量净额','capex':'现金购建固定资产','capex_extended':'固定资产等购买及预付款','eps':'稀释每股收益','shares':'普通股股数','inventory':'存货','receivables':'应收账款','total_equity':'权益合计'}


def _operand_labels(inputs):
    result=[]
    for x in inputs:
        concept=x.get('concept','')
        label=next((CONCEPT_LABELS[k] for k,values in CONCEPTS.items() if concept in values and k in CONCEPT_LABELS),None)
        label=label or {'price':'证券价格','fx':'汇率','shares':'股数'}.get(x.get('role')) or concept or x.get('role','输入')
        result.append({**x,'display_label':label,'components':_operand_labels(x.get('components',[]))} if x.get('components') else {**x,'display_label':label})
    return result

GROUPS = {
    'profitability': ('盈利能力', {'gross_margin','operating_margin','net_margin','parent_net_margin'}),
    'cashflow': ('现金流与投入', {'operating_cash_margin','capex_to_revenue','cash_conversion','fcf_cash_ppe','fcf_extended_property'}),
    'solvency': ('偿债能力', {'current_ratio','cash_ratio','liabilities_to_assets','liabilities_to_equity'}),
    'efficiency': ('回报与效率', {'roa_period','roe_period','inventory_turnover','inventory_days','receivables_turnover','receivables_days'}),
    'valuation': ('估值', {'pe_fy_diluted','ps_fy','pb','market_cap_reported_shares'}),
}
PERIOD_NAMES = {'annual':'全年','quarter':'单季','ytd':'累计','instant':'期末时点','unknown':'期间待核','ttm':'滚动十二个月'}


def _table(db, name):
    return bool(db.execute('SELECT 1 FROM sqlite_master WHERE name=?',(name,)).fetchone())


def _anchors(db, entity_id):
    """Reuse reviewed observation periods, never calendar-month quarter guesses."""
    result=defaultdict(set)
    if not _table(db,'financial_periods'):return result
    for r in db.execute('SELECT DISTINCT f.period_end,p.fiscal_year,p.period,p.basis FROM financial_points f JOIN financial_periods p ON p.fact_id=f.id WHERE f.entity_id=?',(entity_id,)):
        quarter={'H1':'Q2','M9':'Q3','FY':'FY'}.get(r['period'],r['period'])
        if quarter in {'Q1','Q2','Q3','Q4','FY'} and r['fiscal_year'] is not None:
            result[r['period_end']].add((r['fiscal_year'],quarter,r['basis']))
    return result


def _period(row, anchors):
    start,end=row.get('period_start'),row.get('period_end')
    detail=row.get('detail') or {}
    period=detail.get('fiscal_period') or row.get('fiscal_period')
    year=detail.get('fiscal_year') or row.get('fiscal_year')
    basis='unverified';quarter=None
    candidates=anchors.get(end,set())
    # Different filing versions may use different basis descriptions. Only
    # identical year/quarter identities can be resolved, not arbitrary firsts.
    identities={(y,q) for y,q,_ in candidates}
    if len(identities)==1:
        year,quarter=next(iter(identities));basis=';'.join(sorted({b for _,_,b in candidates}))
    if not start:
        kind='instant'
    elif period=='FY':kind='annual'
    elif period in {'H1','M9'}:kind='ytd'
    elif period in {'Q1','Q2','Q3','Q4'}:kind='quarter';quarter=period
    else:
        days=(date.fromisoformat(end)-date.fromisoformat(start)).days+1 if end else 0
        kind='annual' if 330<=days<=380 else 'ytd' if 150<=days<=200 or 240<=days<=290 else 'quarter' if 70<=days<=110 and quarter else 'unknown'
    if kind=='annual':quarter='FY'
    verified=bool(year and any(b in basis for b in ('observed_end_matched_current_filing_period','dart_explicit_current_business_year','issuer_fiscal_calendar','issuer_reported_fiscal_period')))
    prefix=f'FY{year}' if verified else f'截至年份 {end[:4]}' if end else '期间待核'
    suffix=('年末' if quarter=='FY' else f'{quarter} 期末' if quarter else '时点') if kind=='instant' else ('全年' if kind=='annual' else f'{quarter or ""} {PERIOD_NAMES[kind]}').strip()
    return {'fiscal_year':year if verified else None,'fiscal_period':quarter if verified else None,'period_kind':kind,'start':start,'end':end,'label':f'{prefix} · {suffix}','identity_basis':basis,'verified_fiscal_identity':verified}


def _group(metric):
    for key,(_,members) in GROUPS.items():
        if metric in members:return key
    return 'growth' if 'growth' in metric else 'efficiency'


def _project(row, anchors, company_name):
    financial=_period(row,anchors)
    valuation=bool(row.get('valuation_date'))
    inputs=_operand_labels(row.get('inputs',[]))
    return {**row,'inputs':inputs,'company_name':company_name,'record_type':'calculated','observation_kind':'valuation' if valuation else 'financial',
            'observation_date':row.get('valuation_date') or row.get('period_end'),
            'financial_basis':financial,'period_kind':'daily' if valuation else financial['period_kind'],
            'period_label':row.get('valuation_date') if valuation else financial['label'],
            'group':_group(row['metric']),'value_state':'actual','comparison_key':row['metric'],
            'comparison_status':'definition_aligned_scope_review_required',
            'comparison_note':'公式一致；仍需核对会计、业务范围及财务期间。' if not valuation else '保留证券、盈利期间、股数与汇率依据；完整财年PE不是TTM。'}


def materialize_contract(path):
    """Persist queryable date semantics without changing underlying fact IDs."""
    with closing(sqlite3.connect(path)) as db,db:
        db.row_factory=sqlite3.Row
        state=db.execute("SELECT value FROM snapshot_metadata WHERE key='state'").fetchone()
        if state and state[0]=='published_public_library.v1':raise ValueError('immutable_release_requires_build')
        db.executescript('''CREATE TABLE IF NOT EXISTS metric_observation_index(
         record_id TEXT PRIMARY KEY, entity_id TEXT NOT NULL, metric_id TEXT NOT NULL,
         record_type TEXT NOT NULL, observation_kind TEXT NOT NULL, observation_date TEXT,
         financial_start TEXT, financial_end TEXT, fiscal_year INTEGER, fiscal_period TEXT,
         period_kind TEXT NOT NULL, unit TEXT NOT NULL, value_state TEXT NOT NULL,
         available_at TEXT NOT NULL, contract_version TEXT NOT NULL, payload TEXT NOT NULL);
         CREATE INDEX IF NOT EXISTS metric_observation_lookup ON metric_observation_index(entity_id,metric_id,observation_date,available_at);''')
        count=0
        for entity in db.execute('SELECT id,name FROM entities WHERE id IN (SELECT entity_id FROM company_cards)').fetchall():
            anchors=_anchors(db,entity['id'])
            rows=[]
            if derived_financials.installed(db):
                for raw in db.execute('SELECT * FROM derived_financials WHERE entity_id=?',(entity['id'],)):
                    r=dict(raw);r['detail']=json.loads(r['detail']);r['inputs']=json.loads(r['inputs'])
                    rows.append(_project(r,anchors,entity['name']))
            if _table(db,'industry_metric_observations'):
                rows.extend({**json.loads(r[0]),'company_name':entity['name']} for r in db.execute('SELECT payload FROM industry_metric_observations WHERE entity_id=?',(entity['id'],)))
            for r in rows:
                f=r.get('financial_basis',{})
                db.execute('INSERT OR REPLACE INTO metric_observation_index VALUES('+','.join('?'*16)+')',(r['id'],r['entity_id'],r['metric'],r['record_type'],r['observation_kind'],r['observation_date'],f.get('start'),f.get('end'),f.get('fiscal_year'),f.get('fiscal_period'),r['period_kind'],r['unit'],r['value_state'],r['available_at'],'metric-observation.v1',json.dumps(r,ensure_ascii=False)))
                count+=1
        return count


def _company_name(db, entity_id):
    company=db.execute('SELECT payload FROM company_cards WHERE entity_id=?',(entity_id,)).fetchone()
    if not company:raise ValueError('metric_company_not_found')
    payload=json.loads(company['payload'])
    entity=db.execute('SELECT name FROM entities WHERE id=?',(entity_id,)).fetchone()
    return entity['name'] if entity else payload.get('name') or entity_id


def _rows(db, entity_id, as_of):
    name=_company_name(db, entity_id)
    anchors=_anchors(db,entity_id)
    rows=derived_financials.page(db,entity_id,limit=100000,view='history',as_of=as_of)['items'] if derived_financials.installed(db) else []
    output=[_project(r,anchors,name) for r in rows]
    if _table(db,'industry_metric_observations'):
        for r in db.execute('SELECT payload FROM industry_metric_observations WHERE entity_id=? AND available_at<=?',(entity_id,as_of)):
            item=json.loads(r['payload']);item['company_name']=name;output.append(item)
    return output


def _read_card(db, entity_ids, record_id, as_of):
    # Validate company scope before resolving the globally unique record ID.
    names = {eid:_company_name(db,eid) for eid in entity_ids}
    raw = db.execute('SELECT * FROM derived_financials WHERE id=? AND available_at<=?',
                     (record_id,as_of)).fetchone() if derived_financials.installed(db) else None
    if raw and raw['entity_id'] in names:
        row = dict(raw)
        row['detail'] = json.loads(row['detail']); row['inputs'] = json.loads(row['inputs'])
        return _project(row,_anchors(db,row['entity_id']),names[row['entity_id']])
    if _table(db,'industry_metric_observations'):
        raw = db.execute('SELECT entity_id,payload FROM industry_metric_observations WHERE id=? AND available_at<=?',
                         (record_id,as_of)).fetchone()
        if raw and raw['entity_id'] in names:
            return {**json.loads(raw['payload']),'company_name':names[raw['entity_id']]}
    raise ValueError('metric_record_not_found_at_cutoff')


def _sample(rows, frequency):
    if frequency=='native':return rows
    buckets={}
    for r in sorted(rows,key=lambda x:x['observation_date'] or ''):
        if r['observation_kind']!='valuation':
            buckets[r['id']]=r;continue
        day=date.fromisoformat(r['observation_date'])
        bucket=day.strftime('%Y-%m') if frequency=='month_end' else str(day.isocalendar()[:2])
        key=(r['entity_id'],r['metric'],r['unit'],bucket)
        # Include missing/not meaningful observations, never silently carry an
        # earlier valid value to the last day of a bucket.
        buckets[key]={**r,'display_sampling':frequency,'sampling_note':'所选范围内该周/月最后一个有记录的交易日；保留该日缺项状态。'}
    return list(buckets.values())


def query_metrics(path, entity_ids, *, section='overview', metric='', record_id='', as_of='9999-12-31', fiscal_year=None, period_kind='', date_start='', date_end='', frequency='native', alignment='date', offset=0, limit=100, include_inputs=False):
    if not 1<=len(entity_ids)<=12 or len(set(entity_ids))!=len(entity_ids):raise ValueError('metric_company_limit_1_to_12_unique')
    if section not in {'overview','catalog','history','valuation','compare','card'}:raise ValueError('invalid_metric_section')
    if frequency not in {'native','week_end','month_end'} or alignment not in {'date','fiscal'}:raise ValueError('invalid_metric_axis')
    if period_kind not in {'','instant','quarter','ytd','annual','ttm','unknown','event','daily'}:raise ValueError('invalid_metric_period_kind')
    for d in (as_of,date_start,date_end):
        if d:date.fromisoformat(d)
    if date_start and date_end and date_start>date_end:raise ValueError('invalid_metric_date_range')
    if offset<0 or not 1<=limit<=2000:raise ValueError('invalid_metric_page')
    if section=='compare' and not metric:raise ValueError('comparison_requires_metric')
    with closing(connect(path)) as db:
        reviews=read_reviews(db,entity_ids,as_of,metric)
        if section=='card':
            card=_read_card(db,entity_ids,record_id,as_of)
            qualify_rows([card],reviews)
            def input_sources(inputs):
                return {x.get('source_id') for x in inputs} | {s for x in inputs for s in input_sources(x.get('components',[]))}
            source_ids=input_sources(card.get('inputs',[]))|{card.get('source_id')}
            card['sources']=[dict(s) for sid in sorted(s for s in source_ids if s) for s in db.execute('SELECT id,title,url,published_at FROM sources WHERE id=?',(sid,))]
            return {'items':[card],'total':1,'next_offset':None,'as_of':as_of,'section':'card',
                    'industry_reviews':[r for r in reviews if r['id'] in card.get('review_ids',[])]}
        rows=[r for eid in entity_ids for r in _rows(db,eid,as_of)]
        qualify_rows(rows,reviews)
    catalog={}
    for r in rows:
        item=catalog.setdefault(r['metric'],{'id':r['metric'],'label':r.get('definition',{}).get('label',r['label']),'group':r['group'],'units':set(),'companies':set(),'period_kinds':set(),'record_type':r['record_type']})
        item['units'].add(r['unit']);item['companies'].add(r['entity_id']);item['period_kinds'].add(r['period_kind'])
    catalog=[{k:sorted(v) if isinstance(v,set) else v for k,v in item.items()} for item in catalog.values()]
    years=sorted({r['financial_basis']['fiscal_year'] for r in rows if r.get('financial_basis',{}).get('fiscal_year') and r['observation_kind']!='valuation'},reverse=True)
    if section=='catalog':return {'items':catalog,'total':len(catalog),'fiscal_years':years,'as_of':as_of,'industry_reviews':reviews}
    rows=[r for r in rows if (not metric or r['metric']==metric) and (not period_kind or r['period_kind']==period_kind)]
    if section=='history':rows=[r for r in rows if r['observation_kind']!='valuation']
    if section=='valuation':rows=[r for r in rows if r['observation_kind']=='valuation']
    if fiscal_year is not None:
        if section=='valuation':raise ValueError('valuation_uses_trade_dates_not_fiscal_year')
        rows=[r for r in rows if r['observation_kind']!='valuation' and r.get('financial_basis',{}).get('fiscal_year')==fiscal_year]
    rows=[r for r in rows if (not date_start or (r['observation_date'] or '')>=date_start) and (not date_end or (r['observation_date'] or '')<=date_end)]
    rows.sort(key=lambda r:(r['observation_date'] or '',r['available_at'],r['id']),reverse=True)
    if section=='overview':
        latest={}
        for r in rows:latest.setdefault((r['entity_id'],r['metric'],r['period_kind'],r['unit'],r['value_state'],r.get('series_scope',r.get('business_scope','')),r.get('comparator','eq')),r)
        rows=list(latest.values())
    rows=_sample(rows,frequency)
    rows.sort(key=lambda r:(r['observation_date'] or '',r['metric']),reverse=True)
    for r in rows:
        if alignment=='fiscal':
            f=r.get('financial_basis',{})
            r['axis_key']=f"FY{f['fiscal_year']} {f['fiscal_period']} {r['period_kind']}" if f.get('fiscal_year') and f.get('fiscal_period') and r['observation_kind']!='valuation' else None
        else:r['axis_key']=r['observation_date']
    coverage=[{'entity_id':eid,'count':sum(r['entity_id']==eid for r in rows),'state':'available' if any(r['entity_id']==eid for r in rows) else 'no_matching_observations'} for eid in entity_ids]
    units=sorted({r['unit'] for r in rows});kinds=sorted({r['period_kind'] for r in rows});states=sorted({r['value_state'] for r in rows})
    comparison={'state':'scope_review_required','notes':['同一指标定义；业务范围、会计及证券口径仍须核对。'],'units':units,'period_kinds':kinds,'value_states':states}
    if len(units)>1 or len(kinds)>1 or len(states)>1:
        comparison['state']='separate_series_required';comparison['notes']=['单位、期间或实际/计划状态不同，分组展示，不混成同一序列。']
    if not include_inputs:
        rows=[{k:v for k,v in r.items() if k not in {'inputs','detail','formula'}} for r in rows]
    if any(r.get('comparison_rules') for r in rows):
        comparison['state']='separate_series_required'
        comparison['notes'].extend(dict.fromkeys(rule['reason'] for r in rows for rule in r.get('comparison_rules',[])))
    return {'items':rows[offset:offset+limit],'total':len(rows),'next_offset':offset+limit if offset+limit<len(rows) else None,'metric_catalog':catalog,'fiscal_years':years,'coverage':coverage,'comparison':comparison,'industry_reviews':reviews,'as_of':as_of,'section':section,'frequency':frequency,'alignment':alignment,'history_policy':'latest_revision_at_cutoff; valuation_financial_inputs_public_by_trade_date','value_precision':'decimal_strings; no_interpolation_or_implicit_fx'}
