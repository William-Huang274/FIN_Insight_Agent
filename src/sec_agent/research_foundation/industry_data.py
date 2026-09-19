"""Company/source navigation over a published research library.

This is a thin SQL projection, shared by the runtime and asset workspace. Cards
are catalog metadata; financial observations and source claims keep their own
provenance. No company relationship is inferred from co-occurrence.
"""
from contextlib import closing
import json
from pathlib import Path
import sqlite3


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
        result['sources']=[{**dict(s),'metadata':json.loads(s['metadata'])} for s in db.execute(
            'SELECT s.id,s.title,s.url,s.published_at,s.vintage,s.access_state,s.metadata,es.category FROM sources s JOIN entity_sources es ON es.source_id=s.id '
            'WHERE es.entity_id=? AND s.access_state=\'readable\' AND (s.published_at<=? OR s.published_at IS NULL) '
            'AND (s.vintage!=\'known_as_of\' OR substr(json_extract(s.metadata,\'$.known_at\'),1,10)<=?) '
            'ORDER BY s.published_at DESC,s.id',(entity_id,as_of,as_of))]
        result['gaps']=[dict(g) for g in db.execute('SELECT * FROM data_gaps WHERE entity_id=? ORDER BY category',(entity_id,))]
        result['data_counts']={table:db.execute('SELECT count(*) FROM '+table+' WHERE entity_id=?',(entity_id,)).fetchone()[0]
                               for table in ('filing_catalog','financial_points','market_prices')}
        result['positions_count']=db.execute('SELECT count(*) FROM institution_positions WHERE manager_id=?',(entity_id,)).fetchone()[0]
        result['card']['authority']='navigation_metadata_not_investment_judgment'
    return result


def data_page(path, entity_id, *, kind='financial', query='', offset=0, limit=30, as_of='9999-12-31'):
    if offset < 0 or not 1 <= limit <= 100: raise ValueError('invalid_data_window')
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
    with closing(connect(path)) as db:
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
    for row in rows:
        if 'payload' in row: row['payload']=json.loads(row['payload'])
    return {'items':rows,'total':total,'next_offset':offset+len(rows) if offset+len(rows)<total else None,
            'notice':'原始数据及披露版本；不自动合并期间、单位或修订。持仓日期与披露日不同，行情不是盈利事实。'}
