"""Issuer disclosure sections, distinct from manager-reported 13F holdings."""
import json

SCHEMA='''CREATE TABLE IF NOT EXISTS issuer_profiles(
 issuer_name TEXT PRIMARY KEY, legal_name TEXT, entity_id TEXT, industry TEXT,
 business TEXT, source_id TEXT REFERENCES sources(id), status TEXT NOT NULL, detail TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS company_disclosures(
 id TEXT PRIMARY KEY, entity_id TEXT REFERENCES entities(id), category TEXT NOT NULL,
 title TEXT NOT NULL, source_id TEXT REFERENCES sources(id), published_at TEXT,
 locator TEXT, body TEXT NOT NULL, status TEXT NOT NULL, scope TEXT NOT NULL);
 CREATE INDEX IF NOT EXISTS company_disclosure_entity ON company_disclosures(entity_id,category);'''
LABELS={'shareholders':'主要股东与实益所有权','customers':'主要客户与集中度','suppliers':'主要供应商与集中度'}

def installed(db,table='company_disclosures'):
    return bool(db.execute('SELECT 1 FROM sqlite_master WHERE name=?',(table,)).fetchone())

def page(db,entity_id,query='',offset=0,limit=30,as_of='9999-12-31'):
    if not installed(db):return {'items':[],'total':0,'next_offset':None}
    sql=" FROM company_disclosures WHERE entity_id=? AND coalesce(published_at,json_extract(scope,'$.reviewed_at'))<=? AND (?='' OR category=? OR instr(lower(body),lower(?))>0)"
    args=(entity_id,as_of,query,query,query)
    total=db.execute('SELECT count(*)'+sql,args).fetchone()[0]
    rows=[dict(r) for r in db.execute('SELECT *'+sql+' ORDER BY category,published_at DESC LIMIT ? OFFSET ?',(*args,limit,offset))]
    return {'items':rows,'total':total,'next_offset':offset+len(rows) if offset+len(rows)<total else None}

def annotate_positions(db,rows):
    if not installed(db,'issuer_profiles'):return
    for row in rows:
        profile=db.execute('SELECT * FROM issuer_profiles WHERE issuer_name=?',(row['issuer_name'],)).fetchone()
        row['issuer_profile']=dict(profile) if profile else {'status':'identity_needs_review','industry':None,'business':None}
