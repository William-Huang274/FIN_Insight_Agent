"""Validate reviewed disclosure packs and append traceable industry observations.

No model/network calls. Imports are atomic and idempotent. Existing source and
fact identities are preserved; publication remains a separate release operation.
"""
from contextlib import closing
from datetime import date
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

VERSION = 'industry-observation-v1'
NUMBER_WORDS = {'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10}
NUMBER_MAGNITUDES = {'hundred':100,'thousand':1000,'million':1000000,'billion':1000000000}
SCHEMA = """
CREATE TABLE IF NOT EXISTS industry_metric_definitions(
 metric TEXT NOT NULL, definition_hash TEXT NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(metric,definition_hash));
CREATE TABLE IF NOT EXISTS industry_metric_observations(
 id TEXT PRIMARY KEY, entity_id TEXT NOT NULL REFERENCES entities(id),
 metric TEXT NOT NULL, observation_date TEXT NOT NULL, period_start TEXT,
 period_end TEXT, fiscal_year INTEGER, fiscal_period TEXT, period_kind TEXT NOT NULL,
 value TEXT, unit TEXT NOT NULL, value_state TEXT NOT NULL, comparator TEXT NOT NULL,
 business_scope TEXT NOT NULL, source_id TEXT NOT NULL REFERENCES sources(id),
 available_at TEXT NOT NULL, payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS industry_metric_series ON industry_metric_observations(entity_id,metric,observation_date,available_at);
CREATE TABLE IF NOT EXISTS industry_metric_coverage(
 entity_id TEXT NOT NULL REFERENCES entities(id), as_of TEXT NOT NULL,
 payload TEXT NOT NULL, PRIMARY KEY(entity_id,as_of));
"""


def dumps(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))


def identity(*parts):
    return sha256(dumps(parts).encode()).hexdigest()


def _day(value):
    if value:date.fromisoformat(value)
    return value


def validate_pack(db, pack):
    """Reject unsupported values/quotes before any production rows are written."""
    cutoff=_day(pack['as_of'])
    companies=set(pack['companies'])
    if companies != {c['entity_id'] for c in pack['coverage']}:
        raise ValueError('coverage_must_include_every_assigned_company')
    for entity in companies:
        if not db.execute('SELECT 1 FROM company_cards WHERE entity_id=?',(entity,)).fetchone():
            raise ValueError('unknown_company:'+entity)
    sources={s['ref']:s for s in pack['sources']}
    if len(sources)!=len(pack['sources']):raise ValueError('duplicate_source_ref')
    definitions={d['metric']:d for d in pack['definitions']}
    bodies={}
    for ref,s in sources.items():
        published=_day(s.get('published_at'))
        if published and published>cutoff:raise ValueError('future_source:'+ref)
        sid=s.get('existing_source_id')
        if sid:
            row=db.execute('SELECT published_at FROM sources WHERE id=?',(sid,)).fetchone()
            if row is None:raise ValueError('source_not_found:'+sid)
            if row[0] and row[0]>cutoff:raise ValueError('future_existing_source:'+sid)
            bodies[ref]='\n'.join(r[0] for r in db.execute('SELECT body FROM passages WHERE source_id=? ORDER BY locator',(sid,)))
        else:
            if not s.get('body') or not s.get('url','').startswith(('https://','http://')):
                raise ValueError('new_source_requires_captured_body_and_url:'+ref)
            bodies[ref]=s['body']
    for o in pack['observations']:
        if o['entity_id'] not in companies or o['metric'] not in definitions:raise ValueError('observation_outside_scope')
        if o['period_kind'] not in {'quarter','ytd','annual','instant','event','ttm'}:raise ValueError('invalid_industry_period')
        if o['value_state'] not in {'actual','guidance','plan'}:raise ValueError('invalid_value_state')
        if o['comparator'] not in {'eq','gt','ge','lt','le','approx','text'}:raise ValueError('invalid_comparator')
        quote=o['evidence_quote']
        if not quote.strip() or quote not in bodies.get(o['source_ref'],''):
            raise ValueError('evidence_quote_not_in_source:'+o['entity_id']+':'+o['metric'])
        observed=_day(o['observation_date'])
        if not observed or observed>cutoff:raise ValueError('invalid_observation_date')
        start,end=_day(o.get('period_start')),_day(o.get('period_end'))
        if start and end and start>end:raise ValueError('reversed_financial_period')
        if o['value_state']=='actual' and end and end>cutoff:raise ValueError('future_actual_period')
        if o['value_state']=='actual' and o['period_kind']!='event' and end and observed!=end:
            raise ValueError('actual_observation_must_match_period_end')
        if not o.get('business_scope') or not o.get('evidence_locator'):raise ValueError('missing_scope_or_locator')
        if o.get('value') is not None:
            value=Decimal(str(o['value']))
            raw=o.get('value_in_source')
            if raw is None:raise ValueError('numeric_value_requires_source_token')
            token=str(raw).replace(',','').replace('%','').strip()
            if token.startswith('(') and token.endswith(')'):token='-'+token[1:-1]
            scale=Decimal(str(o.get('scale','1')))
            if o.get('source_number_basis')=='english_number_words_v1':
                words=token.lower().split()
                if len(words)!=2 or words[0] not in NUMBER_WORDS or words[1] not in NUMBER_MAGNITUDES:raise ValueError('unsupported_number_words')
                numeric=Decimal(NUMBER_WORDS[words[0]]*NUMBER_MAGNITUDES[words[1]])
            else:numeric=Decimal(token)
            expected=numeric*scale
            if scale<=0:raise ValueError('scale_must_be_positive')
            if o.get('sign')=='negative':
                if 'loss' not in quote.lower() or numeric<0:raise ValueError('negative_sign_requires_loss_evidence')
                expected=-expected
            elif o.get('sign') is not None:raise ValueError('invalid_source_sign')
            if not value.is_finite() or value!=expected:
                raise ValueError('numeric_scale_mismatch:'+o['metric'])
            # Quote must include the original token; tables retain row/column
            # context for reviewer verification of the selected period.
            if str(raw) not in quote and str(raw).replace('%','') not in quote:
                raise ValueError('source_token_not_in_quote:'+o['metric'])
        elif not o.get('text_value'):raise ValueError('null_value_requires_disclosure_text')
    return sources,definitions


def import_pack(path, pack):
    path=Path(path)
    if 'published' in path.parts:raise ValueError('immutable_published_library')
    with closing(sqlite3.connect(path)) as db:
        db.execute('PRAGMA foreign_keys=ON')
        state=db.execute("SELECT value FROM snapshot_metadata WHERE key='state'").fetchone()
        if state and state[0]=='published_public_library.v1':raise ValueError('immutable_published_library')
        sources,definitions=validate_pack(db,pack)
        db.executescript(SCHEMA)
        with db:
            resolved={}
            for ref,s in sources.items():
                sid=s.get('existing_source_id')
                if not sid:
                    body=s['body'];digest=sha256(body.encode()).hexdigest()
                    sid='SRC::'+identity(s['url'],digest)[:32]
                    published=s.get('published_at')
                    meta={'category':'industry_operating_metrics','known_at':pack['as_of'],'capture_scope':s.get('scope'),'import_version':VERSION}
                    db.execute('INSERT OR IGNORE INTO sources VALUES(?,?,?,?,?,?,?,?)',(sid,s['title'],s['url'],published,'dated_original' if published else 'known_as_of','readable',digest,dumps(meta)))
                    for part,start in enumerate(range(0,len(body),5200)):
                        text=body[max(0,start-250):start+5200];pid='PASSAGE::'+identity(sid,part)[:32]
                        inserted=db.execute('INSERT OR IGNORE INTO passages VALUES(?,?,?,?,?)',(pid,sid,f'text-part:{part}',text,sha256(text.encode()).hexdigest())).rowcount
                        if inserted:db.execute('INSERT INTO passage_search VALUES(?,?,?)',(pid,sid,text))
                resolved[ref]=sid
            for definition in definitions.values():
                db.execute('INSERT OR IGNORE INTO industry_metric_definitions VALUES(?,?,?)',(definition['metric'],identity(definition),dumps(definition)))
            for o in pack['observations']:
                sid=resolved[o['source_ref']]
                db.execute('INSERT OR IGNORE INTO entity_sources VALUES(?,?,?)',(o['entity_id'],sid,'industry_operating_metrics'))
                published=db.execute('SELECT published_at FROM sources WHERE id=?',(sid,)).fetchone()[0]
                available=published or pack['as_of']
                fy,fp=o.get('fiscal_year'),o.get('fiscal_period')
                labels={'quarter':'单季','ytd':'累计','annual':'全年','instant':'期末时点','event':'事件快照','ttm':'滚动十二个月'}
                label=(f'FY{fy} · {fp or ""} {labels[o["period_kind"]]}').strip() if fy else o['observation_date']+' · '+labels[o['period_kind']]
                record_id='INDUSTRY::'+identity(o['entity_id'],o['metric'],sid,o)[:40]
                payload={**o,'id':record_id,'source_id':sid,'record_type':'reported','status':'reported','group':'industry',
                    'observation_kind':'industry','period_label':label,'available_at':available,'published_at':published,
                    'available_at_basis':'publication_date' if published else 'capture_date_publication_unknown',
                    'financial_basis':{'fiscal_year':fy,'fiscal_period':fp,'period_kind':o['period_kind'],'start':o.get('period_start'),'end':o.get('period_end'),'label':label,'identity_basis':'issuer_reported_fiscal_period' if fy else 'date_only','verified_fiscal_identity':bool(fy)},
                    'formula_version':VERSION,'definition':definitions[o['metric']],
                    'comparison_status':'scope_review_required','comparison_note':'公司披露口径：'+o['business_scope']+'；跨公司比较须核对定义，约数及上下限不作为精确点。'}
                # Exact unit aliases only; never infer a currency or perform FX.
                canonical_unit={'percent':'%','PERCENT':'%','RMB':'CNY'}.get(o['unit'],o['unit'])
                if canonical_unit!=o['unit']:
                    payload.update(original_unit=o['unit'],unit=canonical_unit,unit_normalization='exact_unit_alias_v1')
                db.execute('INSERT OR IGNORE INTO industry_metric_observations VALUES('+','.join('?'*17)+')',
                    (record_id,o['entity_id'],o['metric'],o['observation_date'],o.get('period_start'),o.get('period_end'),fy,fp,o['period_kind'],o.get('value'),canonical_unit,o['value_state'],o['comparator'],o['business_scope'],sid,available,dumps(payload)))
            for c in pack['coverage']:
                db.execute('INSERT OR REPLACE INTO industry_metric_coverage VALUES(?,?,?)',(c['entity_id'],pack['as_of'],dumps(c)))
                detail={**c,'as_of':pack['as_of'],'observation_count':sum(o['entity_id']==c['entity_id'] for o in pack['observations'])}
                db.execute('INSERT OR REPLACE INTO data_gaps VALUES(?,?,?,?,?)',(c['entity_id'],'industry_metrics','partial' if c['gaps'] else 'available',dumps(detail),pack['as_of']))
    return {'companies':len(pack['companies']),'observations':len(pack['observations']),'sources':len(sources),'version':VERSION}


def calculate_ratio(path, *, numerator_id, denominator_id, metric, label, reviewed_scope):
    """Persist an explicitly reviewed pair. No name-based operand selection."""
    if not reviewed_scope.strip():raise ValueError('ratio_requires_scope_review')
    with closing(sqlite3.connect(path)) as db,db:
        db.row_factory=sqlite3.Row
        state=db.execute("SELECT value FROM snapshot_metadata WHERE key='state'").fetchone()
        if state and state[0]=='published_public_library.v1':raise ValueError('immutable_published_library')
        operands=[]
        for rid in (numerator_id,denominator_id):
            raw=db.execute('SELECT payload FROM industry_metric_observations WHERE id=?',(rid,)).fetchone()
            if raw is None:raise ValueError('ratio_input_not_found')
            operands.append(json.loads(raw[0]))
        a,b=operands
        if any(a.get(k)!=b.get(k) for k in ('entity_id','period_start','period_end','period_kind','unit')):
            raise ValueError('ratio_period_entity_unit_mismatch')
        if a['period_kind'] not in {'quarter','ytd','annual','ttm'}:raise ValueError('ratio_requires_flow_period')
        if any(x.get('value') is None or x['comparator']!='eq' or x['value_state']!='actual' for x in operands):
            raise ValueError('ratio_requires_exact_actual_inputs')
        if Decimal(b['value'])<=0:raise ValueError('ratio_denominator_not_positive')
        version='industry-ratio.v1';rid='INDUSTRY::'+identity(version,numerator_id,denominator_id,metric,reviewed_scope)[:40]
        inputs=[{k:x.get(k) for k in ('id','source_id','value','unit','period_start','period_end','available_at')}|{'role':role,'display_label':x['label'],'concept':x['metric']} for role,x in zip(('a','b'),operands)]
        result={**a,'id':rid,'metric':metric,'label':label,'value':str(Decimal(a['value'])/Decimal(b['value'])*100),'unit':'%',
                'record_type':'calculated','status':'available','inputs':inputs,'formula':'a / b * 100','formula_version':version,
                'available_at':max(x['available_at'] for x in operands),'business_scope':reviewed_scope,
                'comparison_note':reviewed_scope+'；按已核输入计算，不自动视为跨公司可比。',
                'definition':{'metric':metric,'label':label,'unit':'%','business_definition':reviewed_scope},
                'qualifiers':list(dict.fromkeys(q for x in operands for q in x.get('qualifiers',[])))}
        for k in ('evidence_quote','evidence_locator','value_in_source','scale','original_unit','unit_normalization'):result.pop(k,None)
        db.execute('INSERT OR IGNORE INTO industry_metric_observations VALUES('+','.join('?'*17)+')',
                   (rid,result['entity_id'],metric,result['observation_date'],result.get('period_start'),result.get('period_end'),result.get('fiscal_year'),result.get('fiscal_period'),result['period_kind'],result['value'],'%','actual','eq',reviewed_scope,result['source_id'],result['available_at'],dumps(result)))
        return result
