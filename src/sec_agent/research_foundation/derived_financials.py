"""Deterministic, materialized financial calculations with operand provenance.

No LLM, FX guessing, annualising interim income or aggregation across revisions.
Valuation requires a reviewed security basis; annual P/E is explicitly NOT TTM.
"""
from collections import defaultdict
from contextlib import closing
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import sqlite3

VERSION = 'derived_financials.v1'
SCHEMA = '''CREATE TABLE IF NOT EXISTS derived_financials(
 id TEXT PRIMARY KEY, entity_id TEXT NOT NULL, metric TEXT NOT NULL,
 label TEXT NOT NULL, value TEXT, unit TEXT NOT NULL, status TEXT NOT NULL,
 period_start TEXT, period_end TEXT, valuation_date TEXT, available_at TEXT NOT NULL,
 formula TEXT NOT NULL, formula_version TEXT NOT NULL, inputs TEXT NOT NULL,
 detail TEXT NOT NULL);
 CREATE INDEX IF NOT EXISTS derived_financials_entity ON derived_financials(entity_id,metric,available_at);'''
CONCEPTS = {
 'revenue': ('RevenueFromContractWithCustomerExcludingAssessedTax','Revenues','Revenue','NetSales'),
 'gross': ('GrossProfit',), 'operating': ('OperatingIncomeLoss','OperatingProfit','ProfitLossFromOperatingActivities'),
 'profit': ('NetIncomeLoss','ProfitForPeriod','ProfitLoss'),
 'current_assets': ('AssetsCurrent','CurrentAssets'), 'current_liabilities': ('LiabilitiesCurrent','CurrentLiabilities'),
 'assets': ('Assets','TotalAssets'), 'liabilities': ('Liabilities','TotalLiabilities'),
 'cfo': ('NetCashProvidedByUsedInOperatingActivities','CashFlowsFromUsedInOperatingActivities'),
 'capex': ('PaymentsToAcquirePropertyPlantAndEquipment','PurchaseOfPropertyPlantAndEquipment'),
 'eps': ('EarningsPerShareDiluted',), 'shares': ('CommonStockSharesOutstanding',),
}
FORMULAS = [
 ('gross_margin','毛利率','gross','revenue','a / b * 100','%', 'positive_denominator'),
 ('operating_margin','经营利润率','operating','revenue','a / b * 100','%', 'positive_denominator'),
 ('net_margin','净利率（期间净利润口径）','profit','revenue','a / b * 100','%', 'positive_denominator'),
 ('current_ratio','流动比率','current_assets','current_liabilities','a / b','倍', 'positive_denominator'),
 ('liabilities_to_assets','资产负债率','liabilities','assets','a / b * 100','%', 'positive_denominator'),
 ('fcf_cash_ppe','自由现金流（经营现金流减现金购建固定资产）','cfo','capex','a - b','source_currency', 'cash_capex'),
]


def installed(db):
    return bool(db.execute("SELECT 1 FROM sqlite_master WHERE name='derived_financials'").fetchone())


def choose(rows, key):
    for concept in CONCEPTS[key]:
        matches=[r for r in rows if r['concept']==concept]
        if not matches:continue
        # Conflicting values in the same source/period/unit are not guessed away.
        values={Decimal(r['value']) for r in matches}
        if len(values)!=1:return None
        return sorted(matches,key=lambda r:r['id'])[0]
    return None


def operand(row, role):
    return {k:row.get(k) for k in ('id','source_id','taxonomy','concept','value','unit','period_start','period_end','filed_at','available_at','accession')}|{'role':role}


def latest_unambiguous(rows):
    if not rows:return None
    latest=max((r['period_end'],r['filed_at']) for r in rows)
    matches=[r for r in rows if (r['period_end'],r['filed_at'])==latest]
    return min(matches,key=lambda r:r['id']) if len({Decimal(r['value']) for r in matches})==1 else None


def materialize(path, as_of):
    """Append versioned calculations to a mutable build, never a published file."""
    generated=[]
    with closing(sqlite3.connect(path)) as db, db:
        db.row_factory=sqlite3.Row
        state=db.execute("SELECT value FROM snapshot_metadata WHERE key='state'").fetchone()
        if state and state[0]=='published_public_library.v1':raise ValueError('immutable_release_requires_build')
        db.executescript(SCHEMA)
        cards=db.execute('SELECT entity_id,payload FROM company_cards').fetchall()
        for card in cards:
            eid=card['entity_id'];meta=json.loads(card['payload'])
            if meta.get('profile_type') in {'agency','macro_collection','fund'}:continue
            rows=[]
            for r in db.execute("SELECT f.*,s.metadata AS source_metadata FROM financial_points f JOIN sources s ON s.id=f.source_id WHERE f.entity_id=? AND f.filed_at<=? AND f.period_end<=? AND (f.taxonomy IN ('us-gaap','ifrs-full','issuer-reported') OR (f.taxonomy='dei' AND f.concept='EntityCommonStockSharesOutstanding')) AND s.access_state='readable'",(eid,as_of,as_of)):
                row=dict(r);sm=json.loads(row.pop('source_metadata'));payload=json.loads(row['payload'])
                known=(sm.get('known_at') or sm.get('captured_at',''))[:10] if sm.get('known_at') or payload.get('date_basis')=='known_at_capture_not_publication' else row['filed_at']
                row['available_at']=max(row['filed_at'],known or row['filed_at'])
                if row['available_at']>as_of:continue
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
                normalized=[operand(x,chr(97+i)) if 'concept' in x else x for i,x in enumerate(inputs)]
                signature=json.dumps([VERSION,eid,metric,normalized,formula,status,detail],sort_keys=True,ensure_ascii=False)
                outputs.append((sha256(signature.encode()).hexdigest(),eid,metric,label,str(value) if value is not None else None,unit,status,
                    period_start,period_end,valuation_date,available or as_of,formula,VERSION,json.dumps(normalized,ensure_ascii=False),json.dumps(detail,ensure_ascii=False)))
            for cohort in cohorts.values():
                for metric,label,left,right,formula,unit,rule in FORMULAS:
                    a,b=choose(cohort,left),choose(cohort,right)
                    if not a or not b:continue
                    if unit=='source_currency' and a['unit'] not in {'USD','CNY','JPY','EUR','KRW','TWD','HKD','GBP'}:continue
                    # Ratios only monetary values, never shares or percent facts.
                    if a['unit'] not in {'USD','CNY','JPY','EUR','KRW','TWD','HKD','GBP'}:continue
                    av,bv=Decimal(a['value']),Decimal(b['value'])
                    invalid=bv<0 if rule=='cash_capex' else bv<=0
                    val=None if invalid else av-bv if rule=='cash_capex' else av/bv*(100 if unit=='%' else 1)
                    emit(metric,label,val,a['unit'] if unit=='source_currency' else unit,'invalid_denominator_or_sign' if invalid else 'available',
                        [a,b],formula,{'basis':'same_source_accession_taxonomy_period_unit','cash_capex_excludes_non_cash_and_leases':rule=='cash_capex'},a['period_start'],a['period_end'])
            security=meta.get('valuation_security_basis',{})
            prices=[dict(r) for r in db.execute('SELECT p.*,s.metadata AS source_metadata FROM market_prices p JOIN sources s ON s.id=p.source_id WHERE p.entity_id=? AND p.trade_date<=? AND s.access_state=\'readable\' ORDER BY trade_date DESC',(eid,as_of))]
            # Current snapshot only. Each operand retains both trade date and
            # capture-known date; historical prices are not historical forecasts.
            if prices:
                price=prices[0];pm=json.loads(price.pop('source_metadata'));price['available_at']=max(price['trade_date'],(pm.get('known_at') or pm.get('captured_at') or price['trade_date'])[:10])
                px={'role':'price','source_id':price['source_id'],'trade_date':price['trade_date'],'value':str(price['close']),'unit':price['currency'],'price_basis':'unadjusted_close','available_at':price['available_at']}
                basis_source=db.execute("SELECT 1 FROM sources WHERE id=? AND access_state='readable'",(security.get('source_id',''),)).fetchone()
                basis_ok=security.get('status')=='reviewed_single_common_share' and bool(basis_source) and security.get('ticker')==price['ticker'] and price['available_at']<=as_of and (security.get('known_at') or as_of)<=as_of
                try:price_valid=Decimal(str(price['close'])).is_finite() and Decimal(str(price['close']))>0
                except (InvalidOperation,TypeError):price_valid=False
                basis_ok=basis_ok and price_valid
                eps=[r for r in rows if r['concept']=='EarningsPerShareDiluted' and r['form'] in {'10-K','20-F'} and r['filed_at']<=price['trade_date'] and r['period_start'] and 330<=(date.fromisoformat(r['period_end'])-date.fromisoformat(r['period_start'])).days<=380 and r['unit']==(price['currency'] or '')+'/shares']
                ep=latest_unambiguous(eps)
                # Split/reverse-split coverage is explicitly reviewed through
                # price date; raw close must be on the EPS share basis.
                basis_ok=basis_ok and security.get('price_basis_reviewed_through','')>=price['trade_date']
                if basis_ok and ep:
                    den=Decimal(ep['value']);stale=(date.fromisoformat(price['trade_date'])-date.fromisoformat(ep['period_end'])).days>550
                    status='stale_earnings' if stale else 'not_meaningful_nonpositive_earnings' if den<=0 else 'available'
                    value=Decimal(str(price['close']))/den if status=='available' else None
                    emit('pe_fy_diluted','市盈率（最近完整财年稀释EPS，非TTM）',value,'倍',status,[px,ep],'unadjusted_close / annual_diluted_eps',{'security_basis':security,'earnings_basis':'last_full_fiscal_year_not_ttm_or_forward'},ep['period_start'],ep['period_end'],price['trade_date'])
                else:
                    emit('pe_fy_diluted','市盈率（最近完整财年稀释EPS，非TTM）',None,'倍','missing_inputs',[px],'unadjusted_close / annual_diluted_eps',{'missing':['reviewed_security_and_split_basis'] if not basis_ok else ['same_currency_annual_diluted_eps']},valuation_date=price['trade_date'])
                shares=[r for r in rows if r['concept'] in {'CommonStockSharesOutstanding','EntityCommonStockSharesOutstanding'} and r['filed_at']<=price['trade_date'] and not r['period_start'] and r['unit']=='shares' and r['period_end']<=price['trade_date']]
                sh=latest_unambiguous(shares)
                if basis_ok and sh:
                    age=(date.fromisoformat(price['trade_date'])-date.fromisoformat(sh['period_end'])).days
                    status='available' if 0<=age<=120 and Decimal(sh['value'])>0 else 'stale_or_invalid_share_count'
                    value=Decimal(str(price['close']))*Decimal(sh['value']) if status=='available' else None
                    emit('market_cap_reported_shares','参考市值（最新披露股数）',value,price['currency'],status,[px,sh],'unadjusted_close * reported_common_shares',{'security_basis':security,'share_count_age_days':age,'not_live_share_count':True},period_end=sh['period_end'],valuation_date=price['trade_date'])
                else:
                    emit('market_cap_reported_shares','参考市值（最新披露股数）',None,price['currency'] or '', 'missing_inputs',[px],'unadjusted_close * reported_common_shares',{'missing':['reviewed_security_and_split_basis'] if not basis_ok else ['reported_common_shares']},valuation_date=price['trade_date'])
            # All reproducible versions remain in SQL. Browsing selects latest
            # period/version per metric unless a historical as_of is requested.
            db.executemany('INSERT OR IGNORE INTO derived_financials VALUES('+','.join('?'*15)+')',outputs)
            generated.extend(outputs)
    return {'formula_version':VERSION,'generated_rows':len(generated),'entities':len({r[1] for r in generated})}


def page(db,entity_id,query='',offset=0,limit=30,as_of='9999-12-31'):
    if not installed(db):return {'items':[],'total':0,'next_offset':None,'notice':'derived_metrics_not_materialized'}
    rows=[dict(r) for r in db.execute("SELECT * FROM derived_financials WHERE entity_id=? AND available_at<=? ORDER BY COALESCE(valuation_date,period_end) DESC,available_at DESC,COALESCE(period_start,'') DESC,rowid DESC",(entity_id,as_of))]
    selected={}
    for r in rows:
        if query and query.casefold() not in (r['metric']+' '+r['label']).casefold():continue
        selected.setdefault(r['metric'],r)
    rows=list(selected.values())
    for r in rows:
        r['inputs']=json.loads(r['inputs']);r['detail']=json.loads(r['detail'])
        r['source_id']=next((x['source_id'] for x in r['inputs'] if x.get('source_id')),None)
    return {'items':rows[offset:offset+limit],'total':len(rows),'next_offset':offset+limit if offset+limit<len(rows) else None,'notice':'Deterministic stored calculations; retained original operands and versions, not model estimates.'}
