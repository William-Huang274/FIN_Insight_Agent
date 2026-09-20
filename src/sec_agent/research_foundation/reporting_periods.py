"""Observation periods, kept separate from the fiscal year of the filing."""
from collections import defaultdict
from datetime import date
import json

SCHEMA='''CREATE TABLE IF NOT EXISTS financial_periods(
 fact_id TEXT PRIMARY KEY REFERENCES financial_points(id), fiscal_year INTEGER,
 period TEXT NOT NULL, label TEXT NOT NULL, basis TEXT NOT NULL);
 CREATE INDEX IF NOT EXISTS financial_period_filter ON financial_periods(fiscal_year,period);'''
LABELS={'FY':'全年','Q1':'第一季度','Q2':'第二季度','Q3':'第三季度','Q4':'第四季度',
 'H1':'上半年累计','M9':'前三季度累计','instant':'期末余额','other':'其他期间','unknown':'期间待核'}

def installed(db):
    return bool(db.execute("SELECT 1 FROM sqlite_master WHERE name='financial_periods'").fetchone())

def rebuild(db):
    state=db.execute("SELECT value FROM snapshot_metadata WHERE key='state'").fetchone()
    if state and state[0]=='published_public_library.v1':raise ValueError('immutable_release_requires_build')
    db.executescript(SCHEMA)
    rows=[dict(r) for r in db.execute('SELECT * FROM financial_points')]
    filings=defaultdict(list); anchors=defaultdict(set)
    for r in rows:
        if r['fiscal_year'] and r['form'] in {'10-K','10-K/A','10-Q','10-Q/A','20-F','20-F/A'} and r['period_start']:
            filings[(r['entity_id'],r['accession'],r['fiscal_year'],r['fiscal_period'])].append(r)
    for (eid,_,fy,fp),facts in filings.items():
        if fp not in {'FY','Q1','Q2','Q3','Q4'}:continue
        end=max(r['period_end'] for r in facts)
        anchors[(eid,end)].add((fy,'Q4' if fp=='FY' else fp))
    output=[]
    for r in rows:
        payload=json.loads(r['payload']); year=None; period='unknown'; basis='unresolved'
        candidates=anchors.get((r['entity_id'],r['period_end']),set())
        if len(candidates)==1:
            year,quarter=next(iter(candidates));basis='observed_end_matched_current_filing_period'
        else:quarter=None
        explicit=payload.get('reporting_period')
        if explicit:
            year=explicit['fiscal_year'];period=explicit['period'];basis=explicit['basis']
        elif r['period_start']:
            days=(date.fromisoformat(r['period_end'])-date.fromisoformat(r['period_start'])).days+1
            if 330<=days<=380:period='FY'
            elif 150<=days<=200:period='H1'
            elif 240<=days<=290:period='M9'
            elif 70<=days<=110:period=quarter or 'unknown'
            else:period='other'
            if year is None and r['taxonomy']=='issuer-reported' and payload.get('period_basis') in {'FY','H1','Q1','Q2','Q3','Q4'}:
                year=int(r['period_end'][:4]);period=payload['period_basis'];basis='reviewed_period_end_year_not_issuer_fy_label'
        else:period='instant'
        if r['taxonomy']=='DART-IFRS' and payload.get('bsns_year') and 'DART field contract' in payload.get('period_basis',''):
            year=int(payload['bsns_year']);basis='dart_explicit_current_business_year'
            if period=='unknown' and r['fiscal_period'] in {'Q1','Q2','Q3','Q4'}:period=r['fiscal_period']
        elif r['taxonomy'].startswith('FinMind:'):
            year=int(r['period_end'][:4]);basis='provider_observation_calendar_year_period_unverified'
            period='instant' if r['taxonomy'].endswith('BalanceSheet') else 'unknown'
        if year is None and r['taxonomy']=='issuer-reported' and payload.get('period_basis')=='instant':
            year=int(r['period_end'][:4]);basis='reviewed_period_end_year_not_issuer_fy_label'
        label=(f'FY{year}' if basis in {'observed_end_matched_current_filing_period','dart_explicit_current_business_year'} else f'年结 {year}') if year else '财年待核'
        label+=' · '+LABELS[period]
        output.append((r['id'],year,period,label,basis))
    db.executemany('INSERT OR REPLACE INTO financial_periods VALUES(?,?,?,?,?)',output)
    return len(output)

def menu(db,entity_id):
    if not installed(db):return []
    return [dict(r) for r in db.execute('SELECT p.fiscal_year,p.period,p.label,count(*) AS count '
        'FROM financial_periods p JOIN financial_points f ON f.id=p.fact_id WHERE f.entity_id=? '
        'GROUP BY p.fiscal_year,p.period,p.label ORDER BY p.fiscal_year DESC,p.period',(entity_id,))]


if __name__=='__main__':
    import argparse
    import sqlite3
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',required=True)
    args=parser.parse_args()
    with sqlite3.connect(args.build) as connection:
        connection.row_factory=sqlite3.Row
        print(json.dumps({'observations':rebuild(connection)}))
