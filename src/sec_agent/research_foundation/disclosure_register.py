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
    from .disclosure_scope_reviews import for_entity
    reviews=for_entity(db,entity_id,as_of)
    sql=" FROM company_disclosures WHERE entity_id=? AND coalesce(published_at,json_extract(scope,'$.reviewed_at'))<=? AND (?='' OR category=? OR instr(lower(body),lower(?))>0)"
    args=(entity_id,as_of,query,query,query)
    rows=[dict(r) for r in db.execute('SELECT *'+sql+' ORDER BY category,published_at DESC',args)] if installed(db) else []
    if query in LABELS:rows=[r for r in rows if r['category']==query]
    grouped={}
    if installed(db,'counterparty_facts'):
        for r in db.execute('''SELECT f.*,s.title,s.published_at,
            CASE WHEN s.vintage IN ('known_as_of','current_revised')
              THEN coalesce(substr(json_extract(s.metadata,'$.known_at'),1,10),
                            substr(json_extract(s.metadata,'$.captured_at'),1,10),s.published_at)
              ELSE coalesce(s.published_at,substr(json_extract(s.metadata,'$.known_at'),1,10),
                            substr(json_extract(s.metadata,'$.captured_at'),1,10)) END AS known_as_of
            FROM counterparty_facts f JOIN sources s ON s.id=f.source_id
            WHERE f.entity_id=? AND s.access_state='readable' AND known_as_of<=?
            ORDER BY known_as_of DESC,f.id''',(entity_id,as_of)):
            f=json.loads(r['payload'])
            f.update(known_as_of=r['known_as_of'],date_basis='publication_date' if r['published_at']==r['known_as_of'] else 'known_as_of')
            if query and query not in LABELS and query.casefold() not in json.dumps(f,ensure_ascii=False).casefold():continue
            if query in LABELS and query!=r['category']:continue
            key=(r['source_id'],r['category'])
            grouped.setdefault(key,{'facts':[],'title':r['title'],'published_at':r['published_at'],'known_as_of':r['known_as_of']})['facts'].append(f)
    # Multiple locator windows for the same report must not duplicate facts.
    seen=set(); result=[]
    for row in rows:
        key=(row['source_id'],row['category'])
        if (key in grouped or key in reviews) and key in seen:continue
        seen.add(key)
        row['original_section_chars']=len(row.pop('body'))
        row['structured_facts']=grouped.get(key,{}).get('facts',[])
        row['known_as_of']=grouped.get(key,{}).get('known_as_of')
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
            'title':LABELS[category]+' · '+group['title'],'source_id':sid,'published_at':group['published_at'],'known_as_of':group['known_as_of'],
            'status':'reviewed_facts_available','extraction_status':'reviewed_facts_available',
            'extraction_note':'已核对的逐项记录；不代表完整前十名单。',
            'structured_facts':group['facts'],'readback':{'source_space':'library','operation':'read','document_id':sid}})
    present={(r['source_id'],r['category']) for r in result}
    for key,entry in reviews.items():
        if key in present:continue
        sid,category=key
        if query in LABELS and query!=category:continue
        if query and query not in LABELS and query.casefold() not in json.dumps(entry['review'],ensure_ascii=False).casefold():continue
        result.append({'id':'SCOPE::'+sid+'::'+category,'entity_id':entity_id,'category':category,
            'title':LABELS[category]+' · '+entry['title'],'source_id':sid,'published_at':entry['published_at'],
            'known_as_of':entry['known_as_of'],'status':'reviewed_scope','structured_facts':[],
            'readback':{'source_space':'library','operation':'read','document_id':sid}})
    for row in result:
        entry=reviews.get((row['source_id'],row['category']))
        if not entry:continue
        r=entry['review']
        row['scope_review']={k:v for k,v in r.items() if k!='evidence'}
        row['known_as_of']=entry['known_as_of']
        # New facts invalidate an earlier absence receipt. Do not hide them.
        if row['structured_facts']:
            row['extraction_status']='reviewed_facts_available'
            row['extraction_note']='已核对的逐项记录；核查范围：'+r['scope_note']
        else:
            row['extraction_status']='checked_no_explicit_fact' if r['result']=='checked_no_explicit_fact' else 'extraction_pending'
            row['extraction_note']=('已核查所列范围，未发现可逐项提取的明确披露；不代表公司在其他资料中未披露。核查范围：' if r['result']=='checked_no_explicit_fact' else '已复核的事实当前缺失，需要检查入库；核查范围：')+r['scope_note']
    for row in result:
        row['structured_facts'].sort(key=lambda f:(-(f.get('fiscal_year') or 0),f['counterparty_name'],f['role']))
    # Retire old source-less locator gaps only where reviewed facts now exist.
    known_categories={key[1] for key in grouped}
    result=[r for r in result if r['source_id'] or r['category'] not in known_categories]
    result.sort(key=lambda r:r.get('known_as_of') or r.get('published_at') or '',reverse=True)
    total=len(result); rows=result[offset:offset+limit]
    return {'items':rows,'total':total,'next_offset':offset+len(rows) if offset+len(rows)<total else None}


def fact_page(db,entity_id,query='',offset=0,limit=8,as_of='9999-12-31'):
    """Model contract: paginate facts, not arbitrarily long report collections."""
    reports=page(db,entity_id,query,0,10000,as_of)['items']
    rows=[]
    for report in reports:
        if not report['structured_facts']:
            row={k:report[k] for k in ('id','entity_id','category','source_id','extraction_status','extraction_note','readback')}
            if report.get('scope_review'):row['scope_review']=report['scope_review']
            rows.append(row)
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
