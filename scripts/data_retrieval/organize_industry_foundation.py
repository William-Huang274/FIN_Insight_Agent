"""Organize a copied build without changing existing evidence identities.

Entity roles and issuer metadata come from stored public records. Reviewed
relations require a containing source passage and an explicit review manifest;
co-occurrence is never promoted automatically.
"""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit

from scripts.data_retrieval.build_industry_foundation import dumps, identity

US_STATES = set('AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split())


def organize(path):
    with closing(sqlite3.connect(path)) as db, db:
        db.row_factory=sqlite3.Row
        for row in db.execute('SELECT c.*,e.name,e.kind FROM company_cards c JOIN entities e ON e.id=c.entity_id').fetchall():
            card=json.loads(row['payload']);eid=row['entity_id']
            manager=bool(db.execute('SELECT 1 FROM institution_positions WHERE manager_id=? LIMIT 1',(eid,)).fetchone())
            institution=row['sector']=='投资与金融'
            kind='agency' if eid.startswith('AGENCY::') else 'macro_collection' if eid=='INSTITUTION::macro' else 'fund' if card.get('profile_type')=='fund' else 'investment_institution' if institution else 'company'
            roles=[kind]+(['company'] if kind=='investment_institution' and row['kind']=='company' else [])+(['reporting_manager'] if manager else [])
            card.update(profile_type=kind,roles=roles,classification_status='navigation_roles_from_existing_sector_and_filings',
                        institution_type=(card.get('institution_type') or '投资与资产管理主体') if institution else '跨机构资料集合' if kind=='macro_collection' else card.get('institution_type'))
            country=row['country'];inc=card.get('incorporation_code')
            if inc in US_STATES:country='US';card['registration_country']='US'
            elif inc in {'A0','A1','A2','A3','A4','A5','A6','A7','A8','A9','B0','Z4'} and 'Canada' in card.get('registered_address',{}).get('stateOrCountryDescription',''):
                country='CA';card['registration_country']='CA'
            card['identity_basis']=card.get('sec_identity_url') or card.get('identity_basis') or card.get('profile_source_id')
            db.execute('UPDATE company_cards SET country=?,payload=? WHERE entity_id=?',(country,dumps(card),eid))
        # Federal Register records already identify their publishing agencies.
        rows=db.execute("SELECT s.* FROM sources s JOIN entity_sources es ON es.source_id=s.id WHERE es.entity_id='INSTITUTION::macro' AND s.access_state='readable'").fetchall()
        for row in rows:
            meta=json.loads(row['metadata']);agencies=meta.get('agencies',[])
            # These are distributor/publisher identities, never inferred policy
            # applicability. FRED is explicitly a distributor, not the originator.
            provider={'fred.stlouisfed.org':('FRED','Federal Reserve Bank of St. Louis · FRED','US','经济数据分发平台'),
                      'www.stats.gov.cn':('CN-NBS','国家统计局','CN','国家统计机构'),
                      'www.bis.gov':('US-BIS','Bureau of Industry and Security','US','出口管制机构')}.get(urlsplit(row['url']).hostname)
            if provider:
                key,name,country,kind=provider;eid='AGENCY::'+key
                db.execute('INSERT OR IGNORE INTO entities VALUES(?,?,?)',(eid,'institution',name))
                card={'profile_type':'agency','roles':['agency'],'institution_type':kind,'jurisdiction':country,'products':[],
                      'website':'https://'+urlsplit(row['url']).hostname,'legal_name':name,'listing_status':'not_applicable',
                      'selection_reason':'按官方来源域名归档。数据分发平台与原始统计发布者分别记录。',
                      'identity_basis':row['url'],'profile_source_id':row['id'],'classification_status':'official_source_domain'}
                db.execute('INSERT OR IGNORE INTO company_cards VALUES(?,?,?,?,?,?)',(eid,'发布与监管机构','',country,0,dumps(card)))
                db.execute('INSERT OR IGNORE INTO entity_sources VALUES(?,?,?)',(eid,row['id'],meta['category']))
            if meta.get('category')=='policy_regulation':
                meta.setdefault('relevance_review',{'status':'needs_review','reason':'Keyword discovery is not a relevance or applicability finding.'})
            for agency in agencies:
                if not agency.get('id') or not agency.get('name'):continue
                eid='AGENCY::US-FR-'+str(agency['id']);name=agency['name']
                db.execute('INSERT OR IGNORE INTO entities VALUES(?,?,?)',(eid,'institution',name))
                card={'profile_type':'agency','roles':['agency'],'institution_type':'美国联邦发布机构','jurisdiction':'US',
                      'legal_name':name,'products':[],'website':agency.get('url',''),'source_links':{'official_registry':agency.get('url')},
                      'selection_reason':'按已保存 Federal Register 文件的发布机构字段归类；适用公司需要另行核实。',
                      'listing_status':'not_applicable','profile_source_id':row['id'],'identity_basis':row['id'],'classification_status':'source_metadata',
                      'parent_agency_id':'AGENCY::US-FR-'+str(agency['parent_id']) if agency.get('parent_id') else None}
                db.execute('INSERT OR IGNORE INTO company_cards VALUES(?,?,?,?,?,?)',(eid,'发布与监管机构','','US',0,dumps(card)))
                db.execute('INSERT OR IGNORE INTO entity_sources VALUES(?,?,?)',(eid,row['id'],meta['category']))
            db.execute('UPDATE sources SET metadata=? WHERE id=?',(dumps(meta),row['id']))


def apply_reviews(path, reviews):
    with closing(sqlite3.connect(path)) as db, db:
        db.row_factory=sqlite3.Row
        for review in reviews.get('policies',[]):
            row=db.execute('SELECT metadata FROM sources WHERE id=?',(review['source_id'],)).fetchone()
            if not row:raise ValueError('review_source_not_found')
            meta=json.loads(row['metadata']);meta['relevance_review']={k:v for k,v in review.items() if k!='source_id'}
            db.execute('UPDATE sources SET metadata=? WHERE id=?',(dumps(meta),review['source_id']))
        for edge in reviews.get('relations',[]):
            source=db.execute("SELECT * FROM sources WHERE id=? AND access_state='readable'",(edge['source_id'],)).fetchone()
            if not source:raise ValueError('review_source_unreadable')
            passages=db.execute('SELECT * FROM passages WHERE source_id=?',(edge['source_id'],)).fetchall()
            # Whitespace normalization only; meaning is reviewed by the author.
            quote=' '.join(edge['evidence_quote'].split())
            matches=[p for p in passages if quote in ' '.join(p['body'].split())]
            if not quote or not matches:raise ValueError('review_quote_not_found:'+edge['predicate'])
            for key in ('subject','object'):
                if not db.execute('SELECT 1 FROM entities WHERE id=?',(edge[key],)).fetchone():raise ValueError('review_entity_not_found')
            p=matches[0]
            qualifiers={**edge.get('qualifiers',{}),'operator_reviewed_predicate':True,'source_passage_id':p['id'],
                        'evidence_quote':quote,'review_reason':edge['review_reason'],'reviewed_at':reviews['reviewed_at'],
                        'runtime_locator_binding':'exact_passage','announcement_is_not_fulfillment':True}
            db.execute('INSERT OR REPLACE INTO edges VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                ('EDGE::'+identity(edge['subject'],edge['object'],edge['predicate'],source['id'])[:32],edge['subject'],edge['predicate'],edge['object'],source['id'],p['locator'],
                 source['published_at'],edge.get('valid_from'),edge.get('valid_to'),edge['status'],dumps(qualifiers)))
            for eid in (edge['subject'],edge['object']):
                db.execute('INSERT OR IGNORE INTO entity_sources VALUES(?,?,?)',(eid,source['id'],edge.get('category','relationship_announcement')))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True);p.add_argument('--reviews',type=Path)
    a=p.parse_args();organize(a.db)
    if a.reviews:apply_reviews(a.db,json.loads(a.reviews.read_text(encoding='utf-8')))
