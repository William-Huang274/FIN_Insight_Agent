"""Company/source navigation over a published research library.

This is a thin SQL projection, shared by the runtime and asset workspace. Cards
are catalog metadata; financial observations and source claims keep their own
provenance. No company relationship is inferred from co-occurrence.
"""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from .industry_taxonomy import profile, listing_profile, source_navigation, financial_group_sql, financial_identity, FINANCIAL_GROUPS, METRIC_NAMES
from .material_presentation import material_preview
from . import financial_accounts, derived_financials, reporting_periods, disclosure_register


SCHEMA = """
CREATE TABLE IF NOT EXISTS company_cards(entity_id TEXT PRIMARY KEY REFERENCES entities(id),
 sector TEXT NOT NULL, ticker TEXT NOT NULL, country TEXT NOT NULL, expansion_depth INTEGER NOT NULL,
 payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS entity_sources(entity_id TEXT NOT NULL REFERENCES entities(id),
 source_id TEXT NOT NULL REFERENCES sources(id), category TEXT NOT NULL,
 PRIMARY KEY(entity_id,source_id,category));
CREATE TABLE IF NOT EXISTS data_gaps(entity_id TEXT NOT NULL, category TEXT NOT NULL,
 status TEXT NOT NULL, detail TEXT NOT NULL, updated_at TEXT NOT NULL,
 PRIMARY KEY(entity_id,category));
CREATE TABLE IF NOT EXISTS raw_captures(url TEXT PRIMARY KEY, captured_at TEXT NOT NULL,
 status INTEGER NOT NULL, content_type TEXT NOT NULL, digest TEXT NOT NULL, body_zlib BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS collection_attempts(id INTEGER PRIMARY KEY, url TEXT NOT NULL,
 captured_at TEXT NOT NULL, status TEXT NOT NULL, detail TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS filing_catalog(entity_id TEXT NOT NULL, accession TEXT NOT NULL,
 form TEXT NOT NULL, filed_at TEXT NOT NULL, period_end TEXT, primary_document TEXT,
 url TEXT NOT NULL, source_id TEXT, PRIMARY KEY(entity_id,accession));
CREATE TABLE IF NOT EXISTS financial_points(id TEXT PRIMARY KEY, entity_id TEXT NOT NULL,
 taxonomy TEXT NOT NULL, concept TEXT NOT NULL, label TEXT NOT NULL, value TEXT NOT NULL,
 unit TEXT NOT NULL, period_start TEXT, period_end TEXT NOT NULL, filed_at TEXT NOT NULL,
 fiscal_year INTEGER, fiscal_period TEXT, form TEXT NOT NULL, accession TEXT NOT NULL,
 source_id TEXT NOT NULL REFERENCES sources(id), payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS market_prices(entity_id TEXT NOT NULL, ticker TEXT NOT NULL,
 trade_date TEXT NOT NULL, open REAL, high REAL, low REAL, close REAL, adjusted_close REAL,
 volume REAL, currency TEXT, source_id TEXT NOT NULL REFERENCES sources(id),
 PRIMARY KEY(entity_id,trade_date,source_id));
CREATE TABLE IF NOT EXISTS institution_positions(id TEXT PRIMARY KEY, manager_id TEXT NOT NULL,
 issuer_name TEXT NOT NULL, cusip TEXT NOT NULL, security_class TEXT, value TEXT NOT NULL,
 value_unit TEXT NOT NULL, shares TEXT, shares_type TEXT, put_call TEXT,
 period_end TEXT NOT NULL, filed_at TEXT NOT NULL, source_id TEXT NOT NULL REFERENCES sources(id),
 payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS entity_sources_entity ON entity_sources(entity_id,category);
CREATE INDEX IF NOT EXISTS financial_points_entity ON financial_points(entity_id,period_end,concept);
CREATE INDEX IF NOT EXISTS institution_positions_issuer ON institution_positions(issuer_name);
CREATE TABLE IF NOT EXISTS position_issuers(position_id TEXT PRIMARY KEY REFERENCES institution_positions(id),
 entity_id TEXT NOT NULL REFERENCES entities(id), resolution_basis TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS position_issuers_entity ON position_issuers(entity_id);
"""


def connect(path):
    db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    db.create_function('financial_account_path',2,financial_accounts.account_path,deterministic=True)
    return db


def installed(path):
    with closing(connect(path)) as db:
        return bool(db.execute("SELECT 1 FROM sqlite_master WHERE name='company_cards'").fetchone())


def companies(path, *, query='', sector='', offset=0, limit=100):
    if offset < 0 or not 1 <= limit <= 200:
        raise ValueError('invalid_company_window')
    with closing(connect(path)) as db:
        where = "(?='' OR c.sector=?) AND (?='' OR instr(lower(c.payload),lower(?))>0 OR instr(lower(e.name),lower(?))>0)"
        args = (sector,sector,query,query,query)
        total = db.execute('SELECT count(*) FROM company_cards c JOIN entities e ON e.id=c.entity_id WHERE '+where,args).fetchone()[0]
        rows = db.execute('SELECT c.*,e.name,e.kind FROM company_cards c JOIN entities e ON e.id=c.entity_id WHERE '+where+
                          ' ORDER BY c.expansion_depth,c.sector,e.name LIMIT ? OFFSET ?',(*args,limit,offset)).fetchall()
        items=[]
        for row in rows:
            item=dict(row); item['card']=json.loads(item.pop('payload'))
            item['profile']=profile(item,item['card'])
            item['listing']=listing_profile(item['card'])
            item['source_count']=db.execute("SELECT count(DISTINCT es.source_id) FROM entity_sources es JOIN sources s ON s.id=es.source_id WHERE es.entity_id=? AND s.access_state='readable'",(item['entity_id'],)).fetchone()[0]
            item['open_gaps']=db.execute("SELECT count(*) FROM data_gaps WHERE entity_id=? AND status NOT IN ('available','not_applicable')",(item['entity_id'],)).fetchone()[0]
            items.append(item)
        sectors=[r[0] for r in db.execute('SELECT DISTINCT sector FROM company_cards ORDER BY sector')]
    return {'items':items,'total':total,'sectors':sectors,'next_offset':offset+len(items) if offset+len(items)<total else None}


def company_detail(path, entity_id, *, as_of='9999-12-31'):
    with closing(connect(path)) as db:
        r=db.execute('SELECT c.*,e.name,e.kind FROM company_cards c JOIN entities e ON e.id=c.entity_id WHERE entity_id=?',(entity_id,)).fetchone()
        if not r: raise KeyError(entity_id)
        result=dict(r); result['card']=json.loads(result.pop('payload'))
        result['profile']=profile(result,result['card'])
        result['listing']=listing_profile(result['card'])
        result['sources']=[{**dict(s),'metadata':json.loads(s['metadata'])} for s in db.execute(
            'SELECT s.id,s.title,s.url,s.published_at,s.vintage,s.access_state,s.metadata,es.category FROM sources s JOIN entity_sources es ON es.source_id=s.id '
            'WHERE es.entity_id=? AND s.access_state=\'readable\' AND (s.published_at<=? OR s.published_at IS NULL) '
            'AND (s.vintage!=\'known_as_of\' OR substr(json_extract(s.metadata,\'$.known_at\'),1,10)<=?) '
            'ORDER BY s.published_at DESC,s.id',(entity_id,as_of,as_of))]
        result['gaps']=[dict(g) for g in db.execute('SELECT * FROM data_gaps WHERE entity_id=? ORDER BY category',(entity_id,))]
        result['data_counts']={table:db.execute('SELECT count(*) FROM '+table+' WHERE entity_id=?',(entity_id,)).fetchone()[0]
                               for table in ('filing_catalog','financial_points','market_prices')}
        if entity_id.startswith('AGENCY::'):
            result['data_counts']['financial_points']=db.execute('SELECT count(*) FROM financial_points WHERE source_id IN (SELECT source_id FROM entity_sources WHERE entity_id=?)',(entity_id,)).fetchone()[0]
        result['positions_count']=db.execute('SELECT count(*) FROM institution_positions WHERE manager_id=?',(entity_id,)).fetchone()[0]
        result['card']['authority']='navigation_metadata_not_investment_judgment'
        unique={}
        for source in result['sources']:
            if source['id'] in unique:
                unique[source['id']]['categories'].append(source['category'])
                continue
            source['categories']=[source['category']]
            source['category']=source['metadata'].get('category',source['category'])
            source['link_role']='primary_catalogue' if source['metadata'].get('entity_id')==entity_id else 'related_material'
            unique[source['id']]=material_preview(db, source_navigation(source))
        result['sources']=list(unique.values())
        result['data_counts']['holders']=db.execute('SELECT count(*) FROM position_issuers WHERE entity_id=?',(entity_id,)).fetchone()[0]
        result['data_counts']['derived']=len(derived_financials.page(db,entity_id,limit=100,as_of=as_of)['items'])
        result['data_counts']['disclosures']=disclosure_register.page(db,entity_id,limit=100,as_of=as_of)['total']
        result['reporting_periods']=reporting_periods.menu(db,entity_id)
        from .relationship_extraction import coverage_page, assertion_page
        result['relationship_processing']=coverage_page(db,entity_id)
        result['data_counts']['relationships']=assertion_page(db,entity_id,limit=1,as_of=as_of)['total']
        result['account_tree']=financial_accounts.tree(db,entity_id) if result['profile']['type'] not in {'agency','macro_collection'} else []
        result['financial_groups']=[{'id':r[0],'label':FINANCIAL_GROUPS[r[0]],'count':r[1]} for r in db.execute(
            'SELECT '+financial_group_sql()+',count(*) FROM financial_points WHERE '+
            ('source_id IN (SELECT source_id FROM entity_sources WHERE entity_id=?)' if entity_id.startswith('AGENCY::') else 'entity_id=?')+
            ' GROUP BY 1',(entity_id,))]
        result['data_channels']=data_channels(result)
        result['macro_series']=[]
        if result['profile']['type'] in {'agency','macro_collection'}:
            scope='source_id IN (SELECT source_id FROM entity_sources WHERE entity_id=?)' if entity_id.startswith('AGENCY::') else 'entity_id=?'
            for r in db.execute('SELECT concept,label,unit,count(*) AS observations,max(period_end) AS latest_observation '
                'FROM financial_points WHERE '+scope+' GROUP BY concept,label,unit ORDER BY concept',(entity_id,)):
                result['macro_series'].append(dict(r))
    return result


def data_channels(detail):
    """Available data, not a fictitious universal company menu."""
    counts=detail['data_counts']; policy=detail['profile']['type'] in {'agency','macro_collection'}
    channels=[]
    if policy:
        if counts['financial_points']:channels.append({'kind':'financial','group':'','label':'经济指标与时间序列','count':counts['financial_points']})
        n=sum(s['category'].startswith('policy') for s in detail['sources'])
        if n:channels.append({'kind':'policies','group':'','label':'政策与规则登记','count':n})
    else:
        manager=detail['profile']['type'] in {'investment_institution','fund'}
        positions={'kind':'positions','group':'','label':'该管理人申报的证券持仓' if manager else '该主体申报的证券持仓','count':detail['positions_count']}
        if detail['positions_count'] and manager:channels.append(positions)
        if counts['financial_points']:channels.append({'kind':'financial','group':'','label':'财务指标','count':counts['financial_points']})
        if counts['market_prices']:channels.append({'kind':'prices','group':'','label':'市场日行情','count':counts['market_prices']})
        if counts.get('derived'):channels.append({'kind':'derived','group':'','label':'衍生指标与估值','count':counts['derived']})
        if detail['positions_count'] and not manager:channels.append(positions)
        if counts.get('disclosures'):channels.append({'kind':'disclosures','group':'','label':'主要股东、客户与供应商','count':counts['disclosures']})
        if counts.get('relationships'):channels.append({'kind':'relationships','group':'','label':'已提取的业务与资金关系','count':counts['relationships']})
        if counts.get('holders'):channels.append({'kind':'holders','group':'','label':'持有该证券的申报机构','count':counts['holders']})
        if counts['filing_catalog']:channels.append({'kind':'filings','group':'','label':'监管申报目录','count':counts['filing_catalog']})
    return channels


def position_relations(path, entity_id, as_of):
    """Project only explicitly resolved issuer identities, without summing exposure."""
    with closing(connect(path)) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='position_issuers'").fetchone():return []
        rows=db.execute('SELECT p.manager_id,i.entity_id,p.source_id,p.period_end,p.filed_at,count(*) AS position_rows '
            'FROM institution_positions p JOIN position_issuers i ON i.position_id=p.id '
            'JOIN sources s ON s.id=p.source_id WHERE (p.manager_id=? OR i.entity_id=?) AND p.filed_at<=? '
            "AND s.access_state='readable' AND (s.vintage NOT IN ('known_as_of','current_revised') OR substr(json_extract(s.metadata,'$.known_at'),1,10)<=?) "
            'GROUP BY p.manager_id,i.entity_id,p.source_id,p.period_end,p.filed_at ORDER BY p.filed_at DESC',
            (entity_id,entity_id,as_of,as_of)).fetchall()
        from hashlib import sha256
        return [{'id':'POSITION_EDGE::'+sha256('|'.join(str(r[k]) for k in ('manager_id','entity_id','source_id','period_end')).encode()).hexdigest()[:24],
            'subject':r['manager_id'],'object':r['entity_id'],'predicate':'reported_security_position','status':'reported_as_of',
            'source_id':r['source_id'],'published_at':r['filed_at'],'locator':'structured institution_positions',
            'qualifiers':{'period_end':r['period_end'],'position_rows':r['position_rows'],
                'identity_basis':'existing_reviewed_position_issuers_mapping','no_netting':True},
            'candidate_only':False,'evidence':[],
            'readback':{'source_space':'library','operation':'data','entity_id':r['manager_id'],'data_kind':'positions'}} for r in rows]


def data_page(path, entity_id, *, kind='financial', query='', offset=0, limit=30, as_of='9999-12-31', group='', account='', fiscal_year=None, fiscal_period=''):
    if offset < 0 or not 1 <= limit <= 100: raise ValueError('invalid_data_window')
    if group and (kind!='financial' or group not in FINANCIAL_GROUPS):
        raise ValueError('invalid_financial_group')
    if account and (kind!='financial' or account not in financial_accounts.LABELS):raise ValueError('invalid_account_path')
    if (fiscal_year is not None or fiscal_period) and kind!='financial':raise ValueError('period_requires_financial')
    if fiscal_period and fiscal_period not in reporting_periods.LABELS:raise ValueError('invalid_fiscal_period')
    if kind=='disclosures':
        with closing(connect(path)) as db:return disclosure_register.page(db,entity_id,query,offset,limit,as_of)
    if kind=='relationships':
        from .relationship_extraction import assertion_page
        with closing(connect(path)) as db:return assertion_page(db,entity_id,query=query,offset=offset,limit=limit,as_of=as_of)
    if kind=='derived':
        with closing(connect(path)) as db:return derived_financials.page(db,entity_id,query,offset,limit,as_of)
    if kind=='holders':
        with closing(connect(path)) as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='position_issuers'").fetchone():
                return {'items':[],'total':0,'next_offset':None,'notice':'This older release has no issuer/position crosswalk; no zero-holdings conclusion.'}
            scope=" FROM institution_positions p JOIN position_issuers i ON i.position_id=p.id JOIN entities e ON e.id=p.manager_id WHERE i.entity_id=? AND p.filed_at<=? AND (?='' OR instr(lower(e.name),lower(?))>0)"
            args=(entity_id,as_of,query,query)
            total=db.execute('SELECT count(*)'+scope,args).fetchone()[0]
            rows=[dict(r) for r in db.execute('SELECT p.*,e.name AS manager_name,i.resolution_basis'+scope+' ORDER BY p.filed_at DESC,e.name LIMIT ? OFFSET ?',(*args,limit,offset))]
        for row in rows:row['payload']=json.loads(row['payload'])
        return {'items':rows,'total':total,'next_offset':offset+len(rows) if offset+len(rows)<total else None,'notice':'13F issuer-name crosswalk; separate share classes, puts/calls, managers and report dates. Not current holdings or net exposure.'}
    contracts={'financial':('financial_points','entity_id','filed_at','concept'),
               'prices':('market_prices','entity_id','trade_date','ticker'),
               'positions':('institution_positions','manager_id','filed_at','issuer_name'),
               'filings':('filing_catalog','entity_id','filed_at','form')}
    if kind not in contracts: raise ValueError('unknown_data_kind')
    table,entity,date,search=contracts[kind]
    where=f"{entity}=? AND {date}<=? AND (?='' OR instr(lower({search}),lower(?))>0)"
    args=(entity_id,as_of,query,query)
    if kind=='financial' and entity_id.startswith('AGENCY::'):
        where=f"source_id IN (SELECT source_id FROM entity_sources WHERE entity_id=?) AND {date}<=? AND (?='' OR instr(lower({search}),lower(?))>0)"
    if kind=='financial':
        mapped=[key.split(':',1)[1] for key,value in METRIC_NAMES.items() if query and query.casefold() in value.casefold()]
        terms="(?='' OR instr(lower(concept),lower(?))>0 OR instr(lower(label),lower(?))>0"
        if mapped:terms+=' OR concept IN ('+','.join('?' for _ in mapped)+')'
        terms+=')'
        where=where[:where.index("(?=''")]+terms
        args=(entity_id,as_of,query,query,query,*mapped)
    base_where,base_args=where,args
    if group:
        where += ' AND ('+financial_group_sql()+')=?'
        args += (group,)
    if account:
        where+=" AND (coalesce(json_extract(payload,'$.account_path'),financial_account_path(taxonomy,concept))=? OR coalesce(json_extract(payload,'$.account_path'),financial_account_path(taxonomy,concept)) LIKE ?)"
        args+=(account,account+'/%')
    with closing(connect(path)) as db:
        if kind=='financial' and (fiscal_year is not None or fiscal_period):
            if reporting_periods.installed(db):
                where+=" AND id IN (SELECT fact_id FROM financial_periods WHERE (? IS NULL OR fiscal_year=?) AND (?='' OR period=?))"
                args+=(fiscal_year,fiscal_year,fiscal_period,fiscal_period)
            else:where+=' AND 0'
        groups=[{'id':r[0],'label':FINANCIAL_GROUPS[r[0]],'count':r[1]} for r in db.execute(
            'SELECT '+financial_group_sql()+' AS g,count(*) FROM financial_points WHERE '+base_where+' GROUP BY g',base_args)] if kind=='financial' else []
        total=db.execute('SELECT count(*) FROM '+table+' WHERE '+where,args).fetchone()[0]
        # Capture/filing dates often tie (e.g. one FRED response contains three
        # months). Show latest observation periods first, without discarding
        # historical revisions or silently selecting a preferred financial fact.
        ordering = f'{date} DESC'
        if kind in {'financial','positions','filings'}:
            ordering += ', period_end DESC'
        if kind == 'financial': ordering += ', concept, id'
        elif kind == 'positions': ordering += ', issuer_name, id'
        elif kind == 'filings': ordering += ', accession'
        rows=[dict(r) for r in db.execute('SELECT * FROM '+table+' WHERE '+where+f' ORDER BY {ordering} LIMIT ? OFFSET ?',(*args,limit,offset))]
        if kind=='positions':disclosure_register.annotate_positions(db,rows)
        if kind=='financial':
            metadata={sid:json.loads(db.execute('SELECT metadata FROM sources WHERE id=?',(sid,)).fetchone()[0]) for sid in {r['source_id'] for r in rows}}
            for row in rows:
                if reporting_periods.installed(db):
                    period=db.execute('SELECT * FROM financial_periods WHERE fact_id=?',(row['id'],)).fetchone()
                    row['reporting_period']=dict(period) if period else None
                row['frequency']=metadata[row['source_id']].get('frequency')
                row['revision_basis']='current_revised' if metadata[row['source_id']].get('current_revised') else 'source_disclosure'
    for row in rows:
        if 'payload' in row: row['payload']=json.loads(row['payload'])
        if kind=='financial':financial_accounts.annotate(financial_identity(row))
    return {'items':rows,'total':total,'next_offset':offset+len(rows) if offset+len(rows)<total else None,
            'groups':groups,'selected_group':group,
            'notice':'原始数据及披露版本；不自动合并期间、单位或修订。持仓日期与披露日不同，行情不是盈利事实。'}
