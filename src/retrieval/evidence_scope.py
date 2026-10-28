"""Source-coordinate scopes for candidate filtering, never inferred answer facts."""
from hashlib import sha256
import json
import re
from .catalog_company_identity import aliases_for, name_key

POLICY = 'original-evidence-scope.v1'
STATEMENT = re.compile(r'(?im)^[ \t]*(?:CONDENSED[ \t]+)?(?P<consolidated>CONSOLIDATED[ \t]+)?'
    r'(?:BALANCE[ \t]+SHEETS?|STATEMENTS?[ \t]+OF[ \t]+(?:CASH[ \t]+FLOWS?|INCOME|OPERATIONS|EARNINGS))[^\n]*$')
TABLE = re.compile(r'\[TABLE:[^\n]*\].*?\[/TABLE\]', re.S)
ITEM = re.compile(r'(?im)^[ \t]*Item[ \t]+(?P<number>\d+\.\d+)[. \t]+[^\n]+$')


def source_scopes(text):
    regions = []
    def add(start, end, attributes, basis):
        regions.append({'source_char_start':start,'source_char_end':end,
            'content_sha256':sha256(text[start:end].encode()).hexdigest(),
            'attributes':attributes,'basis':basis})
    # A statement title binds only its immediately following original table,
    # allowing unit/unaudited lines, not arbitrary intervening prose.
    for heading in STATEMENT.finditer(text):
        table = TABLE.search(text, heading.end())
        if table is None or table.start()-heading.end()>220:
            continue
        between = text[heading.end():table.start()]
        if any(s.strip(' \t\r\u200b\ufeff') and not (s.strip().startswith('(') and s.strip().endswith(')'))
               for s in between.splitlines()):
            continue
        title = heading.group().casefold()
        kind = 'balance_sheet' if 'balance' in title else 'cash_flow' if 'cash' in title else 'income_statement'
        attributes = {'statement_type':kind}
        if heading.group('consolidated'):
            attributes['consolidation'] = 'consolidated'
        previous = text[max(0,heading.start()-240):heading.start()].rstrip().split('\n')[-1].strip()
        owner = re.sub(r'\s+AND\s+SUBSIDIARIES\s*$', '', previous, flags=re.I)
        if (3 <= len(owner) <= 180 and not any(c in owner for c in '|[]<>')
                and re.search(r'\b(?:INC\.?|CORPORATION|CORP\.?|COMPANY|LIMITED|LTD\.?|PLC|LLC)\s*$',owner,re.I)):
            attributes['reporting_entity'] = owner
        add(heading.start(), table.end(), attributes, 'explicit_statement_heading_and_immediate_table')
    items = list(ITEM.finditer(text))
    for i, heading in enumerate(items):
        event = {'2.02':'earnings_release', '2.03':'financing'}.get(heading['number'])
        if event:
            add(heading.start(), items[i+1].start() if i+1<len(items) else len(text),
                {'event_type':event}, 'explicit_sec_item_'+heading['number'])
    return regions


def matching_state(scopes, wanted):
    """AND within one original region, never combine different table owners."""
    if not scopes:
        return 'unknown'
    states = []
    for scope in scopes:
        actual = scope['attributes']; checks = []
        for key, values in wanted.items():
            if key == 'unknown_policy':continue
            if not values:continue
            value = actual.get(key)
            if value is None:
                checks.append(None)
            elif key == 'reporting_entity':
                aliases = {name_key(n) for n in aliases_for({'company_name':value})}
                checks.append(any(name_key(n) in aliases for n in values))
            else:
                checks.append(value in values)
        states.append('mismatch' if False in checks else 'unknown' if None in checks else 'match')
    return 'match' if 'match' in states else 'unknown' if 'unknown' in states else 'mismatch'


def select_scoped(rows, wanted):
    counts = {'match':0,'unknown':0,'mismatch':0}; selected = []
    for row in rows:
        state = matching_state(row.get('evidence_scopes', []), wanted)
        # A mixed chunk may contain an unclassified paragraph beside a known
        # conflicting table. That table cannot classify the entire chunk.
        if state == 'mismatch' and not row.get('evidence_scope_complete', False):
            state = 'unknown'
        counts[state] += 1
        if state == 'match' or (state == 'unknown' and wanted.get('unknown_policy') == 'retain'):
            selected.append(row)
    return selected, {'policy':POLICY, 'constraints':wanted, 'counts':counts,
        'selected':len(selected), 'filtered_before_scoring':True,
        'unknown_is_not_source_absence':True}


def covers_interval(scopes, start, end):
    position=start
    for scope in sorted(scopes,key=lambda s:s['source_char_start']):
        lo,hi=scope['source_char_start'],scope['source_char_end']
        if lo>position:break
        position=max(position,hi)
    return position>=end


def plan_scope(query, query_plan=None):
    """Only unambiguous positive requests; negations/comparisons stay broad."""
    if re.search(r'不是|并非|而非|而不是|\b(?:not|rather than|instead of|versus|vs)\b',query,re.I):
        return None
    events = []
    if re.search(r'业绩(?:发布|公告)|财报发布|\bearnings (?:release|announcement|8-k)\b',query,re.I):
        events.append('earnings_release')
    if re.search(r'融资(?:发布|公告)|\bfinancing (?:release|announcement)\b',query,re.I):
        events.append('financing')
    wanted = {'unknown_policy':'retain'}
    if len(events) == 1:wanted['event_type']=events
    statements = []
    for kind, pattern in [('balance_sheet',r'资产负债表|\bbalance sheets?\b'),
                          ('cash_flow',r'现金流量表|\bstatements? of cash flows?\b'),
                          ('income_statement',r'利润表|损益表|\b(?:income statements?|statements? of (?:income|operations|earnings))\b')]:
        if re.search(pattern,query,re.I):statements.append(kind)
    if len(statements)==1:
        wanted['statement_type']=statements
        if re.search(r'合并|\bconsolidated\b',query,re.I):
            wanted['consolidation']=['consolidated']
            constraint=(query_plan or {}).get('constraint',{})
            if constraint.get('issuer_id') and constraint.get('company_names'):
                wanted['reporting_entity']=constraint['company_names']
    return wanted if len(wanted)>1 else None


def resolve_scope(query, query_plan, explicit=None):
    """Reconcile explicit business fields with safely understood query fields."""
    inferred=plan_scope(query, query_plan)
    if explicit is None:
        return inferred
    for key, values in (inferred or {}).items():
        if key=='unknown_policy' or not explicit.get(key):
            continue
        if key=='reporting_entity':
            expected={name_key(a) for v in values for a in aliases_for({'company_name':v})}
            supplied={name_key(a) for v in explicit[key] for a in aliases_for({'company_name':v})}
        else:
            expected,supplied=set(values),set(explicit[key])
        if not expected & supplied:
            raise ValueError('organization_evidence_filter_conflicts_with_query:'+key)
    # Typed fields are intentional constraints. Inferred fields only fill
    # absent fields; caller controls whether unclassified evidence is retained.
    return {**(inferred or {}), **explicit, 'unknown_policy':explicit.get('unknown_policy','exclude')}


def scoring_scope_text(row):
    """Expose verified table/event ownership when a chunk starts mid-table."""
    structure=row.get('source_structure',{})
    if structure.get('status')!='verified_original_coordinates':
        return ''
    origin=row.get('original_source',{})
    start,end=origin.get('source_char_start'),origin.get('source_char_end')
    regions=structure.get('evidence_scopes',[])
    result=[]
    for region in regions:
        lo,hi=region['source_char_start'],region['source_char_end']
        digest=region.get('content_sha256','')
        if (any(type(v) is not int for v in (start,end,lo,hi)) or not 0<=start<end
                or not 0<=lo<hi or not lo<end or not start<hi
                or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest)):
            raise ValueError('rerank_unverified_evidence_scope')
        attributes=region['attributes']
        allowed={'reporting_entity':None,'statement_type':{'balance_sheet','cash_flow','income_statement'},
                 'consolidation':{'consolidated'},'event_type':{'earnings_release','financing'}}
        if not attributes or any(k not in allowed or not isinstance(v,str) or not v.strip() or len(v)>180
                or (allowed[k] is not None and v not in allowed[k]) for k,v in attributes.items()):
            raise ValueError('rerank_invalid_evidence_attributes')
        result.append({'attributes':attributes,'source_char_start':lo,'source_char_end':hi})
    if not result:return ''
    text=json.dumps({'excerpt_start':start,'excerpt_end':end,'regions':result},ensure_ascii=False,sort_keys=True)
    if len(text.encode())>8192:raise ValueError('rerank_evidence_scope_outside_budget')
    return ('Verified original table/event regions overlapping this excerpt. '
        'Each attribution applies ONLY to its own original interval, not all facts in the document. '
        'These are source context, not an answer or relevance judgment:\n'+text)
