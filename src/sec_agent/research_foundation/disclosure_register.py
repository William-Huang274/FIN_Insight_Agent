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
    sql=" FROM company_disclosures WHERE entity_id=? AND coalesce(published_at,json_extract(scope,'$.reviewed_at'))<=? AND (?='' OR category=? OR instr(lower(body),lower(?))>0)"
    args=(entity_id,as_of,query,query,query)
    rows=[dict(r) for r in db.execute('SELECT *'+sql+' ORDER BY category,published_at DESC',args)] if installed(db) else []
    grouped={}
    if installed(db,'counterparty_facts'):
        for r in db.execute('''SELECT f.*,s.title,s.published_at FROM counterparty_facts f
            JOIN sources s ON s.id=f.source_id WHERE f.entity_id=? AND s.published_at<=?
            ORDER BY s.published_at DESC,f.id''',(entity_id,as_of)):
            f=json.loads(r['payload'])
            if query and query not in LABELS and query.casefold() not in json.dumps(f,ensure_ascii=False).casefold():continue
            if query in LABELS and query!=r['category']:continue
            key=(r['source_id'],r['category'])
            grouped.setdefault(key,{'facts':[],'title':r['title'],'published_at':r['published_at']})['facts'].append(f)
    # Multiple locator windows for the same report must not duplicate facts.
    seen=set(); result=[]
    for row in rows:
        key=(row['source_id'],row['category'])
        if key in grouped and key in seen:continue
        seen.add(key)
        row['original_section_chars']=len(row.pop('body'))
        row['structured_facts']=grouped.get(key,{}).get('facts',[])
        row['extraction_status']='reviewed_facts_available' if row['structured_facts'] else 'extraction_pending'
        row['extraction_note']='已核对的逐项记录；不代表完整前十名单。' if row['structured_facts'] else '尚未完成逐项结构化提取，这是数据处理缺口，不等于公司未披露。'
        # Source availability checks remain distinguishable from extraction.
        if row['status']=='report_acquisition_required':
            row['extraction_status']='report_acquisition_required'
            row['extraction_note']='报告尚未获取，需要先完成来源获取。'
        row['readback']={'source_space':'library','operation':'read','document_id':row['source_id']}
        result.append(row)
    for key,group in grouped.items():
        if key in seen:continue
        sid,category=key
        result.append({'id':'STRUCTURED::'+sid+'::'+category,'entity_id':entity_id,'category':category,
            'title':LABELS[category]+' · '+group['title'],'source_id':sid,'published_at':group['published_at'],
            'status':'reviewed_facts_available','extraction_status':'reviewed_facts_available',
            'extraction_note':'已核对的逐项记录；不代表完整前十名单。',
            'structured_facts':group['facts'],'readback':{'source_space':'library','operation':'read','document_id':sid}})
    for row in result:
        row['structured_facts'].sort(key=lambda f:(-(f.get('fiscal_year') or 0),f['counterparty_name'],f['role']))
    # Retire old source-less locator gaps only where reviewed facts now exist.
    known_categories={key[1] for key in grouped}
    result=[r for r in result if r['source_id'] or r['category'] not in known_categories]
    result.sort(key=lambda r:r.get('published_at') or '',reverse=True)
    total=len(result); rows=result[offset:offset+limit]
    return {'items':rows,'total':total,'next_offset':offset+len(rows) if offset+len(rows)<total else None}


def fact_page(db,entity_id,query='',offset=0,limit=8,as_of='9999-12-31'):
    """Model contract: paginate facts, not arbitrarily long report collections."""
    reports=page(db,entity_id,query,0,10000,as_of)['items']
    rows=[]
    for report in reports:
        if not report['structured_facts']:
            rows.append({k:report[k] for k in ('id','entity_id','category','source_id','extraction_status','extraction_note','readback')})
            continue
        for fact in report['structured_facts']:
            row={k:v for k,v in fact.items() if k not in ('evidence','review_note')}
            row['evidence']=[{'passage_id':a['passage_id'],'start':a['start'],'end':a['end'],
                             'readback':{'source_space':'library','operation':'read','document_id':fact['source_id'],'node_id':a['passage_id']}}
                             for a in fact['evidence']]
            rows.append(row)
    total=len(rows); result=rows[offset:offset+limit]
    return {'items':result,'total':total,'next_offset':offset+len(result) if offset+len(result)<total else None}

def annotate_positions(db,rows):
    if not installed(db,'issuer_profiles'):return
    for row in rows:
        profile=db.execute('SELECT * FROM issuer_profiles WHERE issuer_name=?',(row['issuer_name'],)).fetchone()
        row['issuer_profile']=dict(profile) if profile else {'status':'identity_needs_review','industry':None,'business':None}
