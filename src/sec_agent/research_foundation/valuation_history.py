"""Historical reference valuations; quote, security and currency bases are explicit."""
from datetime import date
from decimal import Decimal, InvalidOperation
import json

from .financial_metric_contracts import CONCEPTS

FX_SCHEMA='''CREATE TABLE IF NOT EXISTS valuation_fx(
 source_id TEXT NOT NULL, trade_date TEXT NOT NULL, base_currency TEXT NOT NULL,
 quote_currency TEXT NOT NULL, rate TEXT NOT NULL, available_at TEXT NOT NULL,
 PRIMARY KEY(source_id,trade_date,base_currency,quote_currency));'''


def calculate(db,eid,rows,security,as_of,emit,latest):
    prices=db.execute("SELECT p.*,s.metadata AS source_metadata FROM market_prices p JOIN sources s ON s.id=p.source_id WHERE p.entity_id=? AND p.trade_date<=? AND s.access_state='readable' ORDER BY trade_date DESC",(eid,as_of)).fetchall()
    has_fx=bool(db.execute("SELECT 1 FROM sqlite_master WHERE name='valuation_fx'").fetchone())
    def fx_rate(currency,day):
        if currency=='USD':return Decimal(1),[]
        if not has_fx:return None,[]
        r=db.execute("SELECT f.* FROM valuation_fx f JOIN sources s ON s.id=f.source_id WHERE f.base_currency='USD' AND f.quote_currency=? AND f.trade_date<=? AND f.available_at<=? AND s.access_state='readable' ORDER BY f.trade_date DESC LIMIT 1",(currency,day,as_of)).fetchone()
        if not r or (date.fromisoformat(day)-date.fromisoformat(r['trade_date'])).days>4:return None,[]
        rate=Decimal(r['rate'])
        return (rate,[{'role':'fx','source_id':r['source_id'],'trade_date':r['trade_date'],'value':r['rate'],'unit':currency+'/USD','available_at':r['available_at']}]) if rate>0 else (None,[])
    def convert(value,base,quote,day):
        if base==quote:return value,[]
        a,ai=fx_rate(base,day);b,bi=fx_rate(quote,day)
        return (value/a*b,ai+bi) if a and b else (None,[])
    def split_factor(start,end):
        factor=Decimal(1)
        for event in security.get('split_events',[]):
            if start<event['date']<=end:factor*=Decimal(str(event['numerator']))/Decimal(str(event['denominator']))
        return factor
    basis_source=db.execute("SELECT 1 FROM sources WHERE id=? AND access_state='readable'",(security.get('source_id',''),)).fetchone()
    for raw in prices:
        p=dict(raw);pm=json.loads(p.pop('source_metadata'));day=p['trade_date']
        known=max(day,(pm.get('known_at') or pm.get('captured_at') or day)[:10])
        px={'role':'price','source_id':p['source_id'],'trade_date':day,'value':str(p['close']),'unit':p['currency'],'price_basis':'unadjusted_close','available_at':known}
        try:price=Decimal(str(p['close']));valid=price.is_finite() and price>0
        except (InvalidOperation,TypeError):valid=False;price=Decimal(0)
        ok=valid and bool(basis_source) and security.get('status') in {'reviewed_single_common_share','reviewed_ordinary_equivalent'} and security.get('ticker')==p['ticker'] and known<=as_of and (security.get('known_at') or as_of)<=as_of and security.get('price_basis_reviewed_through','')>=day
        ratio=Decimal(str(security.get('ordinary_shares_per_security',1)))
        ok=ok and ratio>0
        public=[r for r in rows if r['available_at']<=day and r['period_end']<=day]
        annual=[r for r in public if r['period_start'] and 330<=(date.fromisoformat(r['period_end'])-date.fromisoformat(r['period_start'])).days<=380]
        if security.get('financial_currency'):
            annual=[r for r in annual if r['unit'].split('/')[0]==security['financial_currency']]
        eps=latest([r for r in annual if r.get('normalized_concept',r['concept']) in CONCEPTS['eps'] and r['unit'].endswith('/shares')])
        # Reviewed mappings identify the actual per-share instrument. Generic
        # USD EPS on an ADR issuer is not presumed to be ordinary-share EPS.
        if security.get('eps_fact_ids'):
            eps=latest([r for r in annual if r['id'] in security['eps_fact_ids']])
        details={'security_basis':security,'earnings_basis':'last_full_fiscal_year_not_ttm_or_forward'}
        eligible=ok and eps and (not security.get('price_basis_reviewed_from') or security['price_basis_reviewed_from']<=eps['filed_at'])
        if eligible:
            factor=split_factor(eps['filed_at'],day)
            eps_ratio=Decimal(str(security.get('ordinary_shares_per_eps_unit',1)))
            den,fx=convert(Decimal(eps['value'])*ratio/eps_ratio/factor,eps['unit'].split('/')[0],p['currency'],day)
            status='missing_fx' if den is None else 'stale_earnings' if (date.fromisoformat(day)-date.fromisoformat(eps['period_end'])).days>550 else 'not_meaningful_nonpositive_earnings' if den<=0 else 'available'
            emit('pe_fy_diluted','市盈率（最近完整财年稀释EPS，非TTM）',price/den if status=='available' else None,'倍',status,[px,eps,*fx],
                 'close / (annual_diluted_eps * ordinary_shares_per_security / ordinary_shares_per_eps_unit / subsequent_split_factor * currency_conversion)',
                 {**details,'split_factor':str(factor),'ordinary_shares_per_security':str(ratio),'ordinary_shares_per_eps_unit':str(eps_ratio)},eps['period_start'],eps['period_end'],day)
        else:
            emit('pe_fy_diluted','市盈率（最近完整财年稀释EPS，非TTM）',None,'倍','missing_inputs',[px],'close / annual_diluted_eps',{'missing':['reviewed_security_and_split_basis'] if not ok else ['annual_diluted_eps_on_reviewed_security_basis']},valuation_date=day)
        candidates=[r for r in public if r.get('normalized_concept',r['concept']) in CONCEPTS['shares'] and not r['period_start'] and r['unit']=='shares']
        if security.get('share_fact_ids'):candidates=[r for r in candidates if r['id'] in security['share_fact_ids']]
        if security.get('share_groups'):
            from .derived_financials import calculated_fact
            candidates=[]
            for group in security['share_groups']:
                components=[r for r in public if r['id'] in group['fact_ids']]
                if len(components)!=len(group['fact_ids']) or len({(r['source_id'],r['period_end'],r['unit']) for r in components})!=1:continue
                candidates.append(calculated_fact(components[0],'OrdinarySharesOutstanding',sum(Decimal(r['value']) for r in components),components,'sum_of_explicit_economically_equivalent_issued_classes'))
        sh=latest(candidates)
        def missing_cap_ratios(status,inputs):
            for metric,label in [('ps_fy','市销率（最近完整财年收入）'),('pb','市净率（最新披露归母权益）')]:
                emit(metric,label,None,'倍',status,inputs,'reference_market_cap / financial_value_in_quote_currency',
                     {'missing':['usable_reference_market_cap'],'security_basis':security},valuation_date=day)
        if not ok or not sh:
            emit('market_cap_reported_shares','参考市值（最新披露股数）',None,p['currency'] or '','missing_inputs',[px],'close * actual_ordinary_shares / ordinary_shares_per_security',{'missing':['reviewed_security_and_split_basis'] if not ok else ['reported_common_shares']},valuation_date=day)
            missing_cap_ratios('missing_inputs',[px])
            continue
        age=(date.fromisoformat(day)-date.fromisoformat(sh['period_end'])).days
        status='available' if 0<=age<=120 and Decimal(sh['value'])>0 else 'stale_or_invalid_share_count'
        factor=split_factor(sh['period_end'],day)
        cap=price*Decimal(sh['value'])*factor/ratio if status=='available' else None
        label='参考市值（经济等价股类合计，按上市股价格）' if security.get('multiple_economic_classes') else '参考市值（最新披露股数）'
        if security.get('share_count_label'):label=security['share_count_label']
        emit('market_cap_reported_shares',label,cap,p['currency'],status,[px,sh],'close * reported_ordinary_shares * subsequent_split_factor / ordinary_shares_per_security',
             {'security_basis':security,'share_count_age_days':age,'not_live_share_count':True,'split_factor':str(factor),'ordinary_shares_per_security':str(ratio),'calculation_currency':p['currency']},period_end=sh['period_end'],valuation_date=day)
        if cap is None:
            missing_cap_ratios(status,[px,sh])
            continue
        for metric,label,role,group in [('ps_fy','市销率（最近完整财年收入）','revenue',annual),('pb','市净率（最新披露归母权益）','equity',[r for r in public if not r['period_start']])]:
            if security.get('financial_currency'):group=[r for r in group if r['unit']==security['financial_currency']]
            matches=[r for r in group if r.get('normalized_concept',r['concept']) in CONCEPTS[role] and r['unit'] in {'USD','CNY','TWD','KRW','HKD','EUR','JPY','GBP'}]
            denrow=None
            if matches:
                from .derived_financials import choose
                newest=max((r['period_end'],r['filed_at']) for r in matches)
                denrow=choose([r for r in matches if (r['period_end'],r['filed_at'])==newest],role)
            if not denrow:
                emit(metric,label,None,'倍','missing_inputs',[px,sh],'reference_market_cap / financial_value_in_quote_currency',
                     {'missing':[role],'security_basis':security},valuation_date=day)
                continue
            den,fx=convert(Decimal(denrow['value']),denrow['unit'],p['currency'],day)
            stale=(date.fromisoformat(day)-date.fromisoformat(denrow['period_end'])).days>(550 if role=='revenue' else 240)
            status='missing_fx' if den is None else 'stale_financial_input' if stale else 'not_meaningful_nonpositive_base' if den<=0 else 'available'
            emit(metric,label,cap/den if status=='available' else None,'倍',status,[px,sh,denrow,*fx],
                 'close * reported_ordinary_shares * subsequent_split_factor / ordinary_shares_per_security / financial_value_in_quote_currency',
                 {'security_basis':security,'basis':'reported_share_count_reference_not_live_market_cap','calculation_currency':p['currency'],'split_factor':str(factor),'ordinary_shares_per_security':str(ratio),
                  'fiscal_year':denrow.get('observation_year'),'fiscal_period':denrow.get('observation_period')},denrow['period_start'],denrow['period_end'],day)
