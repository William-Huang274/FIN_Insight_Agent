"""Reconcile coverage and attach discoverable, explicitly unverified links.

Counterparty mentions remain candidates, distinct from reviewed relationship
predicates. This script never infers a supply contract, shipment or investment.
"""
import argparse
import json
from pathlib import Path
import re
from scripts.data_retrieval.build_industry_foundation import Collector,dumps,identity


def reconcile(worker):
    companies=worker.plan['companies']; by_id={c['entity_id']:c for c in companies}
    # Exact brand spellings are discovery anchors, not name/entity verification.
    aliases={'alphabet':['Google','Alphabet'],'meta':['Meta Platforms'],'bytedance':['ByteDance'],'alibaba':['Alibaba'],
        'tencent':['Tencent'],'zhipu':['Zhipu'],'moonshot':['Moonshot'],'skhynix':['SK hynix','SK Hynix'],
        'tsmc':['TSMC','Taiwan Semiconductor'],'samsung':['Samsung'],'huawei':['Huawei'],'foxconn':['Foxconn','Hon Hai'],
        'quanta':['Quanta Computer'],'ase':['ASE Technology','Siliconware'],'applied':['Applied Materials'],
        'lam':['Lam Research'],'kla':['KLA'],'arm':['Arm Holdings'],'quantaservices':['Quanta Services'],
        'gevernova':['GE Vernova'],'siemensenergy':['Siemens Energy'],'constellation':['Constellation'],
        'nextera':['NextEra'],'sbenergy':['SB Energy'],'digitalrealty':['Digital Realty'],'blackrock':['BlackRock'],
        'spacex':['SpaceX'],'minimax':['MiniMax'],'xai':['xAI'],'mistral':['Mistral']}
    patterns={c['entity_id']:re.compile(r'(?<![A-Za-z])(?:'+'|'.join(re.escape(x) for x in aliases.get(c['slug'],[c['name'].split(' / ')[0]]))+r')(?![A-Za-z])',re.I)
              for c in companies}
    literal_aliases={c['entity_id']:[a.casefold() for a in aliases.get(c['slug'],[c['name'].split(' / ')[0]])] for c in companies}
    verbs=re.compile(r'\b(supplier|customer|partner|invest(?:ment|ed|or)|purchase|supply|agreement|contract|manufactur|capacity|financ|acqui)',re.I)
    for c in companies:
        e=c['entity_id'];card=json.loads(worker.sql('SELECT payload FROM company_cards WHERE entity_id=?',(e,))[0]['payload'])
        filings=worker.sql('SELECT f.*,s.metadata FROM filing_catalog f LEFT JOIN sources s ON f.source_id=s.id WHERE f.entity_id=?',(e,))
        available=[f for f in filings if f['source_id']]
        annual=[f for f in filings if f['form'] in {'10-K','20-F','40-F'}]
        if annual:
            years={f['period_end'][:4] for f in annual if f.get('period_end')}
            read_years={f['period_end'][:4] for f in annual if f.get('period_end') and f['source_id']}
            mirrors=sum('mirror_identity_verification' in (f.get('metadata') or '') for f in annual if f['source_id'])
            worker.gap(e,'annual_full_text','available' if years==read_years and len(read_years)>=3 and not mirrors else 'partial',{'years_in_catalogue':sorted(years),'readable_years':sorted(read_years),'mirror_copies':mirrors,'three_year_minimum_met':len(read_years)>=3,'short_listing_history_not_assumed_complete':len(read_years)<3})
        if available:
            worker.gap(e,'financial_reports','partial' if len(available)<len(filings) else 'available',{'filing_catalogue':len(filings),'readable_full_texts':len(available),'unread_full_texts':len(filings)-len(available),'recent_8k_and_quarterlies_required':True,'original_catalogue_retains_unread_links':True})
        elif not c.get('cik'):
            official=worker.sql("SELECT source_id FROM entity_sources WHERE entity_id=? AND category IN ('official_report','annual_report','earnings_release')",(e,))
            worker.gap(e,'financial_reports','partial' if official else 'alternative_source_required',{'non_SEC_materials':len(official),'three_year_completeness':'must be reviewed per report; no false nondisclosure assertion'})
        if not card.get('profile_source_id') and available:
            card['profile_source_id']=available[0]['source_id'];card['profile_binding']='SEC disclosure identity and business description; homepage access failed separately'
            worker.gap(e,'profile','available',{'source_id':available[0]['source_id'],'route':'SEC disclosure fallback','homepage_attempts_retained':True})
        if c.get('cik'):
            url=f"https://data.sec.gov/submissions/CIK{int(c['cik']):010d}.json"
            try:
                raw,_=worker.get(url);sub=json.loads(raw);card['registered_address']=sub.get('addresses',{}).get('business',{})
                card['incorporation_code']=sub.get('stateOfIncorporation');card['entity_type']=sub.get('entityType')
                card['sec_tickers']=sub.get('tickers',[])
                card['classification_basis']={'business_tags':'operator navigation categories; inspect linked original for scope','issuer_identity':url,'registration_address_not_operating_footprint':True}
            except Exception:pass
        # Existing publications are retained and indexed. Bind exact legacy
        # ticker metadata when present; don't reassign from prose co-occurrence.
        card['card_version']='company_card.v1';card['as_of']=worker.as_of
        card['source_links']={'official_website':c['website'],'sec_submissions':card.get('sec_identity_url'),
            'github':'https://github.com/'+c['github_org'] if c.get('github_org') else None,
            'huggingface':'https://huggingface.co/'+c['hf_org'] if c.get('hf_org') else None,
            'official_social_candidate':'https://x.com/'+c['x_handle'] if c.get('x_handle') else None}
        worker.sql('UPDATE company_cards SET payload=? WHERE entity_id=?',(dumps(card),e))
        # At most two evidence passages per target and company keep the graph
        # usable. All source text remains searchable beyond this navigation cap.
        passages=worker.sql("SELECT p.*,s.published_at,s.metadata FROM passages p JOIN sources s ON p.source_id=s.id JOIN entity_sources es ON es.source_id=s.id WHERE es.entity_id=? AND s.access_state='readable' AND es.category IN ('filing','annual_report','official_report','company_profile') ORDER BY s.published_at DESC",(e,))
        seen={}; candidates=0
        for p in passages:
            folded=p['body'].casefold()
            for target,pattern in patterns.items():
                if target==e or seen.get(target,0)>=2:continue
                if not any(alias in folded for alias in literal_aliases[target]):continue
                match=pattern.search(p['body'])
                if not match:continue
                excerpt=p['body'][max(0,match.start()-240):match.end()+360]
                if not verbs.search(excerpt):continue
                worker.sql('INSERT OR IGNORE INTO edges VALUES('+','.join('?'*11)+')',
                    ('EDGE::'+identity(e,target,p['id'],'counterparty_mention')[:32],e,'counterparty_mention',target,p['source_id'],p['locator'],p['published_at'] or worker.as_of,None,None,'needs_semantic_review',
                     dumps({'candidate_only':True,'not_a_confirmed_supply_or_investment_relation':True,'excerpt':excerpt,'source_passage_id':p['id'],'runtime_locator_binding':'exact_passage','extraction_method':'literal_name_and_relation_vocabulary_candidate','identity_resolution':'candidate_brand_match'})))
                seen[target]=seen.get(target,0)+1;candidates+=1
        edges=worker.sql('SELECT predicate,count(*) AS n FROM edges WHERE subject=? OR object=? GROUP BY predicate',(e,e))
        confirmed=sum(x['n'] for x in edges if x['predicate']!='counterparty_mention')
        worker.gap(e,'relationships','partial' if edges else 'research_needed',{'reviewed_announcement_edges':confirmed,'counterparty_mentions':sum(x['n'] for x in edges if x['predicate']=='counterparty_mention'),'candidate_mentions_are_not_verified_relationships':True})
        finance=worker.sql("SELECT source_id FROM entity_sources WHERE entity_id=? AND category='financing_announcement'",(e,))
        worker.gap(e,'financing','partial' if finance or available else 'research_needed',{'explicit_financing_announcements':len(finance),'filing_footnotes_available':bool(available),'transaction_extraction_and_cash_settlement_not_assumed':True})
    # Captured current macro vintages are usable on/after the capture date only.
    for row in worker.sql("SELECT id,metadata FROM sources WHERE vintage='current_revised'"):
        meta=json.loads(row['metadata'])
        if meta.get('category')=='macro_series' and meta.get('known_at')==worker.as_of:
            meta['current_revised']=True
            worker.sql("UPDATE sources SET vintage='known_as_of',metadata=? WHERE id=?",(dumps(meta),row['id']))
    # Material cards are machine-readable projections, never compressed facts.
    for row in worker.sql('SELECT id,url,published_at,vintage,metadata FROM sources'):
        original_metadata=row['metadata'];meta=json.loads(original_metadata);cat=meta.get('category','legacy_material')
        # Projection/card annotations must not force paid re-embedding of an
        # unchanged original routing representation. Identity corrections before
        # this stage remain in the routing metadata and do invalidate the cache.
        meta.setdefault('routing_metadata_v1',original_metadata)
        dimension=('D1_company_disclosure' if cat in {'filing','filing_exhibit','official_report','annual_report','annual_report_mirror','sec_submissions','company_profile','earnings_release'} else
            'D2_financial_market' if cat in {'financial_api','market_api','institutional_positions'} else
            'D3_product_technology' if cat in {'model_product','product_platform','model_card'} else
            'D4_relationships' if cat in {'relationship_announcement','financing_announcement','power_contract','infrastructure_project','industry_ecosystem'} else
            'D6_macro_policy' if cat in {'macro_series','macro_release','policy_regulation','policy_current_rule'} else 'D5_news_community')
        meta['material_card_version']='material_card.v1';meta['research_dimension']=dimension
        meta['origin_url']=row['url'];meta['publication_date']=row['published_at'];meta['data_tables']=([meta['data_table']] if meta.get('data_table') else [])
        meta['evidence_role']=('discovery_metadata_only' if cat=='news_discovery' else 'community_or_repository_claim' if cat in {'model_card','repository_readme','community_repository','model_catalogue'} else 'structured_provider_observation' if cat in {'financial_api','market_api','macro_series','institutional_positions'} else 'original_document_requires_reading')
        if row['published_at'] and row['published_at']<worker.since:meta['window']='historical_background'
        worker.sql('UPDATE sources SET metadata=? WHERE id=?',(dumps(meta),row['id']))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True);a=p.parse_args()
    plan=json.loads(a.db.with_suffix('.plan.json').read_text(encoding='utf-8'));reconcile(Collector(a.db,plan))
