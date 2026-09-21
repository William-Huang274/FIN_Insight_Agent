"""Deterministic, materialized financial calculations with operand provenance.

No LLM, FX guessing, annualising interim income or aggregation across revisions.
Valuation requires a reviewed security basis; annual P/E is explicitly NOT TTM.
"""
from collections import defaultdict
from contextlib import closing
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import sqlite3
import re

from .financial_metric_contracts import VERSION, CONCEPTS, FORMULAS
SCHEMA = '''CREATE TABLE IF NOT EXISTS derived_financials(
 id TEXT PRIMARY KEY, entity_id TEXT NOT NULL, metric TEXT NOT NULL,
 label TEXT NOT NULL, value TEXT, unit TEXT NOT NULL, status TEXT NOT NULL,
 period_start TEXT, period_end TEXT, valuation_date TEXT, available_at TEXT NOT NULL,
 formula TEXT NOT NULL, formula_version TEXT NOT NULL, inputs TEXT NOT NULL,
 detail TEXT NOT NULL);
 CREATE INDEX IF NOT EXISTS derived_financials_entity ON derived_financials(entity_id,metric,available_at);'''



def installed(db):
    return bool(db.execute("SELECT 1 FROM sqlite_master WHERE name='derived_financials'").fetchone())


def choose(rows, key):
    for concept in CONCEPTS[key]:
        matches=[r for r in rows if r.get('normalized_concept',r['concept'])==concept]
        if not matches:continue
        # Conflicting values in the same source/period/unit are not guessed away.
        values={Decimal(r['value']) for r in matches}
        if len(values)!=1:return None
        return sorted(matches,key=lambda r:r['id'])[0]
    return None


def operand(row, role):
    result={k:row.get(k) for k in ('id','source_id','taxonomy','concept','value','unit','period_start','period_end','filed_at','available_at','accession')}|{'role':role}
    if row.get('components'):result.update(components=row['components'],derivation=row['derivation'])
    if row.get('original_unit'):result.update(original_unit=row['original_unit'],unit_normalization=row['unit_normalization'])
    return result


def observation_period(row):
    if row.get('observation_period'):
        return row.get('observation_year'),row['observation_period']
    if not row.get('period_start'):return None,'instant'
    days=(date.fromisoformat(row['period_end'])-date.fromisoformat(row['period_start'])).days+1
    period='FY' if 330<=days<=380 else 'H1' if 150<=days<=200 else 'M9' if 240<=days<=290 else 'unknown'
    return None,period


def calculated_fact(base, concept, value, components, formula):
    signature=json.dumps([concept,[(r['id'],r['value']) for r in components],formula],sort_keys=True)
    return {**base,'id':'CALC::'+sha256(signature.encode()).hexdigest(),'concept':concept,'normalized_concept':concept,
            'value':str(value),'available_at':max(r.get('available_at',r['filed_at']) for r in components),
            'components':[operand(r,chr(97+i)) for i,r in enumerate(components)],'derivation':formula}


def latest_unambiguous(rows):
    if not rows:return None
    latest=max((r['period_end'],r['filed_at']) for r in rows)
    matches=[r for r in rows if (r['period_end'],r['filed_at'])==latest]
    return min(matches,key=lambda r:r['id']) if len({Decimal(r['value']) for r in matches})==1 else None


def materialize(path, as_of, *, entity_ids=None):
    """Append versioned calculations to a mutable build, never a published file."""
    generated=[]
    with closing(sqlite3.connect(path)) as db, db:
        db.row_factory=sqlite3.Row
        state=db.execute("SELECT value FROM snapshot_metadata WHERE key='state'").fetchone()
        if state and state[0]=='published_public_library.v1':raise ValueError('immutable_release_requires_build')
        db.executescript(SCHEMA)
        cards=db.execute('SELECT entity_id,payload FROM company_cards').fetchall()
        has_periods=bool(db.execute("SELECT 1 FROM sqlite_master WHERE name='financial_periods'").fetchone())
        for card in cards:
            eid=card['entity_id'];meta=json.loads(card['payload'])
            if entity_ids is not None and eid not in entity_ids:continue
            if meta.get('profile_type') in {'agency','macro_collection','fund'}:continue
            rows=[]
            period_columns=',p.fiscal_year AS observation_year,p.period AS observation_period' if has_periods else ''
            period_join=' LEFT JOIN financial_periods p ON p.fact_id=f.id' if has_periods else ''
            for r in db.execute("SELECT f.*,s.metadata AS source_metadata"+period_columns+" FROM financial_points f JOIN sources s ON s.id=f.source_id"+period_join+" WHERE f.entity_id=? AND f.filed_at<=? AND f.period_end<=? AND (f.taxonomy IN ('us-gaap','ifrs-full','issuer-reported','DART-IFRS') OR (f.taxonomy='dei' AND f.concept='EntityCommonStockSharesOutstanding')) AND s.access_state='readable'",(eid,as_of,as_of)):
                row=dict(r);sm=json.loads(row.pop('source_metadata'));payload=json.loads(row['payload'])
                row['normalized_concept']=row['concept']
                if row['taxonomy']=='DART-IFRS':
                    # Only main statement observations, never equity movements
                    # carrying the same XBRL concept in an SCE table.
                    match=re.fullmatch(r'(?:ifrs-full_|dart_)([^:]+):(BS|CIS|IS|CF)',row['concept'])
                    if not match:continue
                    row['normalized_concept']=match[1]
                    if match[1] in {'DilutedEarningsLossPerShare','BasicEarningsLossPerShare'} and row['unit']=='KRW':
                        row.update(original_unit='KRW',unit='KRW/shares',unit_normalization='DART IFRS per-share concept; source adapter supplied currency only')
                mapping=payload.get('derived_operand_review',payload.get('payload',{}).get('derived_operand_review',{}))
                if mapping.get('concept') and mapping.get('reviewed_at') and mapping.get('evidence_row'):
                    row['normalized_concept']=mapping['concept']
                    if mapping.get('sign_multiplier')==-1:
                        original=dict(row)
                        row=calculated_fact(row,mapping['concept'],-Decimal(row['value']),[original],'source_expense_presentation * -1')
                reviewed_publication=sm.get('publication_date_review',{}).get('published_at')
                # A dated SEC/DART fact carries its own filing publication.
                # Download time of the API envelope is not that filing date.
                known=reviewed_publication or ((sm.get('known_at') or sm.get('captured_at',''))[:10] if payload.get('date_basis')=='known_at_capture_not_publication' else row['filed_at'])
                if reviewed_publication and payload.get('date_basis')=='known_at_capture_not_publication':
                    row['filed_at']=reviewed_publication
                row['available_at']=max(row['filed_at'],known or row['filed_at'])
                if row['available_at']>as_of:continue
                reporting_currency=meta.get('derived_financial_profile',{}).get('currency') or meta.get('valuation_security_basis',{}).get('financial_currency')
                if reporting_currency and row['unit'] not in {reporting_currency,reporting_currency+'/shares','shares'}:continue
                try:
                    if not Decimal(row['value']).is_finite():continue
                except (InvalidOperation,TypeError):continue
                rows.append(row)
            cohorts=defaultdict(list)
            for r in rows:
                # Original taxonomy and source identity remain distinct.
                cohorts[(r['source_id'],r['accession'],r['taxonomy'],r['period_start'],r['period_end'],r['unit'])].append(r)
            outputs=[]
            def emit(metric,label,value,unit,status,inputs,formula,detail,period_start=None,period_end=None,valuation_date=None):
                available=max([x.get('available_at',x.get('filed_at','')) for x in inputs]+[valuation_date or '', detail.get('security_basis',{}).get('known_at','')])
                financial=next((x for x in inputs if 'concept' in x),None)
                if financial:
                    fy,fp=observation_period(financial)
                    detail={'fiscal_year':fy,'fiscal_period':fp,'calculation_currency':financial['unit'].split('/')[0],**detail}
                if valuation_date:
                    detail['calculation_currency']=next((x['unit'] for x in inputs if x.get('role')=='price'),'')
                normalized=[operand(x,chr(97+i)) if 'concept' in x else x for i,x in enumerate(inputs)]
                signature=json.dumps([VERSION,eid,metric,normalized,formula,status,detail],sort_keys=True,ensure_ascii=False)
                outputs.append((sha256(signature.encode()).hexdigest(),eid,metric,label,str(value) if value is not None else None,unit,status,
                    period_start,period_end,valuation_date,available or as_of,formula,VERSION,json.dumps(normalized,ensure_ascii=False),json.dumps(detail,ensure_ascii=False)))
            for cohort in cohorts.values():
                # Only exhaustive classified balance-sheet subtotals can be
                # added; never sum arbitrary account-directory descendants.
                if not cohort[0]['period_start']:
                    for role,current,noncurrent,concept in [('assets','current_assets','noncurrent_assets','TotalAssets'),('liabilities','current_liabilities','noncurrent_liabilities','TotalLiabilities')]:
                        a,b=choose(cohort,current),choose(cohort,noncurrent)
                        if not choose(cohort,role) and a and b:
                            combined=calculated_fact(a,concept,Decimal(a['value'])+Decimal(b['value']),[a,b],'current + noncurrent')
                            cohort.append(combined);rows.append(combined)
            for cohort in cohorts.values():
                revenue,cost=choose(cohort,'revenue'),choose(cohort,'cost')
                if not choose(cohort,'gross') and revenue and cost and Decimal(cost['value'])>=0:
                    cohort.append(calculated_fact(revenue,'GrossProfit',Decimal(revenue['value'])-Decimal(cost['value']),[revenue,cost],'revenue - cost_of_revenue'))
                for metric,label,left,right,formula,unit,rule in FORMULAS:
                    a,b=choose(cohort,left),choose(cohort,right)
                    if not a or not b:continue
                    if unit=='source_currency' and a['unit'] not in {'USD','CNY','JPY','EUR','KRW','TWD','HKD','GBP'}:continue
                    # Ratios only monetary values, never shares or percent facts.
                    if a['unit'] not in {'USD','CNY','JPY','EUR','KRW','TWD','HKD','GBP'}:continue
                    av,bv=Decimal(a['value']),Decimal(b['value'])
                    invalid=bv<0 if rule=='cash_capex' else bv<=0 or (rule=='nonnegative_numerator' and av<0)
                    val=None if invalid else av-bv if rule=='cash_capex' else av/bv*(100 if unit=='%' else 1)
                    emit(metric,label,val,a['unit'] if unit=='source_currency' else unit,'invalid_denominator_or_sign' if invalid else 'available',
                        [a,b],formula,{'basis':'same_source_accession_taxonomy_period_unit','cash_capex_excludes_non_cash_and_leases':rule=='cash_capex'},a['period_start'],a['period_end'])
                cfo,capex=choose(cohort,'cfo'),choose(cohort,'capex')
                if cfo and capex and revenue and Decimal(capex['value'])>=0 and Decimal(revenue['value'])>0:
                    emit('fcf_margin','自由现金流率（现金购建固定资产口径）',(Decimal(cfo['value'])-Decimal(capex['value']))/Decimal(revenue['value'])*100,'%', 'available',
                         [cfo,capex,revenue],'(a - b) / c * 100',{'basis':'same_source_accession_taxonomy_period_unit'},revenue['period_start'],revenue['period_end'])
                # Average balances and comparisons must belong to the same
                # report revision. Do not merge restated and superseded inputs.
                anchor=revenue or choose(cohort,'profit')
                if anchor and anchor['period_start']:
                    start=date.fromisoformat(anchor['period_start']);end=date.fromisoformat(anchor['period_end'])
                    days=(end-start).days+1
                    begin=(start-timedelta(days=1)).isoformat()
                    same=[r for r in rows if (r['source_id'],r['accession'],r['taxonomy'],r['unit'])==
                          (anchor['source_id'],anchor['accession'],anchor['taxonomy'],anchor['unit'])]
                    for metric,label,numerator,denominator,factor,unit in [
                        ('roa_period','总资产收益率（期间净利润／平均总资产）','profit','assets',100,'%'),
                        ('roe_period','归母净资产收益率（期间值）','parent_profit','equity',100,'%'),
                        ('asset_turnover','总资产周转率（期间值）','revenue','assets',1,'倍'),
                        ('receivable_days','应收账款周转天数','revenue','receivables',days,'天'),
                        ('inventory_days','存货周转天数','cost','inventory',days,'天')]:
                        n=choose(cohort,numerator)
                        opening=choose([r for r in same if not r['period_start'] and r['period_end']==begin],denominator)
                        end_balance=choose([r for r in same if not r['period_start'] and r['period_end']==anchor['period_end']],denominator)
                        if not (n and opening and end_balance):continue
                        avg=(Decimal(opening['value'])+Decimal(end_balance['value']))/2
                        nv=Decimal(n['value']);inverse=unit=='天'
                        valid=avg>0 and (nv>0 if inverse else True)
                        value=(avg/nv if inverse else nv/avg)*factor if valid else None
                        emit(metric,label,value,unit,'available' if valid else 'invalid_denominator_or_sign',[n,opening,end_balance],
                             '(b + c) / 2 / a * days' if inverse else 'a / ((b + c) / 2)'+(' * 100' if factor==100 else ''),
                             {'basis':'same_report_revision_average_opening_closing_balance','period_days':days,'annualized':False},anchor['period_start'],anchor['period_end'])
                    for role,label in [('revenue','收入同比增长率'),('operating','经营利润同比增长率'),('profit','期间净利润同比增长率'),('cfo','经营现金流同比增长率')]:
                        current=choose(cohort,role)
                        if not current:continue
                        prior=[r for r in same if r['period_start'] and 350<=(end-date.fromisoformat(r['period_end'])).days<=380
                               and abs((date.fromisoformat(r['period_end'])-date.fromisoformat(r['period_start'])).days+1-days)<=7]
                        previous=choose(prior,role)
                        if not previous:continue
                        den=Decimal(previous['value']);valid=den>0
                        emit(role+'_growth_yoy',label,(Decimal(current['value'])/den-1)*100 if valid else None,'%',
                             'available' if valid else 'nonpositive_comparison_base',[current,previous],'(a / b - 1) * 100',
                             {'basis':'same_report_revision_comparable_duration','prior_period_end':previous['period_end']},current['period_start'],current['period_end'])
            from .valuation_history import calculate
            calculate(db,eid,rows,meta.get('valuation_security_basis',{}),as_of,emit,latest_unambiguous)
            # All reproducible versions remain in SQL. Browsing selects latest
            # period/version per metric unless a historical as_of is requested.
            db.executemany('INSERT OR IGNORE INTO derived_financials VALUES('+','.join('?'*15)+')',outputs)
            generated.extend(outputs)
    return {'formula_version':VERSION,'generated_rows':len(generated),'entities':len({r[1] for r in generated})}


def page(db,entity_id,query='',offset=0,limit=30,as_of='9999-12-31',*,view='latest',fiscal_year=None,fiscal_period='',date_start='',date_end=''):
    if not installed(db):return {'items':[],'total':0,'next_offset':None,'notice':'derived_metrics_not_materialized'}
    if view not in {'latest','history'}:raise ValueError('invalid_derived_view')
    for value in (date_start,date_end):
        if value:date.fromisoformat(value)
    if date_start and date_end and date_start>date_end:raise ValueError('invalid_derived_date_range')
    rows=[dict(r) for r in db.execute("SELECT * FROM derived_financials WHERE entity_id=? AND available_at<=? ORDER BY COALESCE(valuation_date,period_end) DESC,available_at DESC,COALESCE(period_start,'') DESC,rowid DESC",(entity_id,as_of))]
    # A v2 build recomputes all eligible periods for its scoped issuers. Keep v1
    # in storage, but do not mix its convenience-currency snapshots into v2.
    if any(r['formula_version']==VERSION for r in rows):rows=[r for r in rows if r['formula_version']==VERSION]
    selected={};periods=set();catalog={}
    for r in rows:
        r['detail']=json.loads(r['detail']);r['inputs']=json.loads(r['inputs'])
        d=r['detail'];fy=d.get('fiscal_year');fp=d.get('fiscal_period')
        if fp is None:
            _,fp=observation_period(r)
        legacy_currency=next((x['unit'].split('/')[0] for x in r['inputs'] if x.get('concept') and x.get('unit') not in {None,'shares','pure'}),'')
        if r['valuation_date']:legacy_currency=next((x.get('unit','') for x in r['inputs'] if x.get('role')=='price'),'')
        r.update(fiscal_year=fy,fiscal_period=fp,calculation_currency=legacy_currency if r['valuation_date'] else d.get('calculation_currency',legacy_currency))
        periods.add((fy,fp));catalog[r['metric']]=r['label']
        if query.startswith('metric:'):
            if r['metric']!=query[7:]:continue
        elif query and query.casefold() not in (r['metric']+' '+r['label']).casefold():continue
        if fiscal_year is not None and fiscal_year!=fy:continue
        if fiscal_period and fiscal_period!=fp:continue
        observed=r['valuation_date'] or r['period_end'] or ''
        if date_start and observed<date_start or date_end and observed>date_end:continue
        key=(r['metric'],r['unit'],r['calculation_currency'])
        if view=='history':key+=(r['period_start'],r['period_end'],r['valuation_date'])
        selected.setdefault(key,r)
    rows=list(selected.values())
    for r in rows:
        r['source_id']=next((x['source_id'] for x in r['inputs'] if x.get('source_id')),None)
    return {'items':rows[offset:offset+limit],'total':len(rows),'next_offset':offset+limit if offset+limit<len(rows) else None,
            'view':view,'as_of':as_of,'metric_catalog':[{'id':k,'label':v} for k,v in sorted(catalog.items())],
            'reporting_periods':[{'fiscal_year':fy,'period':fp} for fy,fp in sorted(periods,key=lambda p:(p[0] or 0,p[1]),reverse=True)],
            'notice':'Stored calculations with original operands. History selects the latest available revision for each period at as_of; valuation inputs must have been public by the trade date. Period returns are not annualized.'}
