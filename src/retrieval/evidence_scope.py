"""Source-coordinate scopes for candidate filtering, never inferred answer facts."""
from hashlib import sha256
import json
import re
from .catalog_company_identity import aliases_for, name_key

POLICY = 'original-evidence-scope.v1'
STATEMENT = re.compile(r'(?im)^[ \t]*(?:UNAUDITED\s+)?(?:CONDENSED\s+)?(?P<consolidated>CONSOLIDATED(?:\s+AND\s+COMBINED)?\s+)?(?:COMBINED\s+)?'
    r'(?:BALANCE\s+SHEETS?|STATEMENTS?\s+OF\s+FINANCIAL\s+POSITION|STATEMENTS?\s+OF\s+(?:CASH\s+FLOWS?|(?:COMPREHENSIVE\s+)?(?:INCOME|OPERATIONS|EARNINGS))'
    r'(?:\s+AND\s+COMPREHENSIVE\s+(?:INCOME|LOSS))?|STATEMENTS?\s+OF\s+(?:CHANGES\s+IN\s+)?(?:(?:STOCKHOLDERS|SHAREHOLDERS|PARTNERS)[\x27’]?\s+)?(?:EQUITY|CAPITAL))'
    r'(?P<tail>[^\n]*)$')
TABLE = re.compile(r'\[TABLE:[^\n]*\].*?\[/TABLE\]', re.S)
ITEM = re.compile(r'(?im)^[ \t]*I(?:[ \t]*\r?\n[ \t]*)?tem[ \t]+(?P<number>\d+\.\d+)[. \t]*(?:\r?\n[ \t]*)?[^\n]+$')


def source_scopes(text):
    regions = []
    from .fact_period_matching import markdown_tables
    tables=sorted([(m.start(),m.end()) for m in TABLE.finditer(text)]+
        [(t['source_char_start'],t['source_char_end']) for t in markdown_tables(text)])
    def add(start, end, attributes, basis):
        regions.append({'source_char_start':start,'source_char_end':end,
            'content_sha256':sha256(text[start:end].encode()).hexdigest(),
            'attributes':attributes,'basis':basis})
    # A statement title binds only its immediately following original table,
    # allowing unit/unaudited lines, not arbitrary intervening prose.
    for heading in STATEMENT.finditer(text):
        from .table_captions import is_table_caption
        tail=heading['tail'].strip(' \t:—–-*†‡')
        qualifiers=re.sub(r'\((?:UNAUDITED|AUDITED|CONTINUED|LOSS)\)', '',tail,flags=re.I).strip(' \t:—–-')
        supplemental=qualifiers.casefold() in {'data','detail','details','measures','highlights',
            'and supplemental information','and related financial highlights'}
        named_owner=re.fullmatch(r'of\s+(.{3,180}?(?:INC\.?|CORPORATION|CORP\.?|COMPANY|LIMITED|LTD\.?|PLC|LLC|N\.?V\.?))',qualifiers,re.I)
        if qualifiers and not supplemental and not named_owner and not is_table_caption(qualifiers):
            continue  # A prose mention of a statement is not its table title.
        table = next((t for t in tables if t[0]>=heading.end()),None)
        if table is None or table[0]-heading.end()>220:
            continue
        between = text[heading.end():table[0]]
        if any(not is_table_caption(s) for s in between.splitlines()):
            continue
        title = heading.group().casefold()
        kind = ('balance_sheet' if 'balance' in title or 'financial position' in title else 'cash_flow' if 'cash' in title else
                'equity_statement' if re.search(r'\b(?:equity|capital)\b',title) else 'income_statement')
        attributes = {'statement_type':kind,'statement_role':'supplemental' if supplemental else 'primary'}
        if heading.group('consolidated'):
            attributes['consolidation'] = 'consolidated'
        previous_lines=[re.sub(r'[\u200b\ufeff]','',s).strip() for s in text[max(0,heading.start()-240):heading.start()].splitlines()]
        previous=next((s for s in reversed(previous_lines) if s),'')
        owner = re.sub(r'\s+AND\s+(?:SUBSIDIARIES|SUBSIDIARY\s+COMPANIES)\s*$', '', previous, flags=re.I)
        if named_owner:
            attributes['reporting_entity']=named_owner[1]
        elif (3 <= len(owner) <= 180 and not any(c in owner for c in '|[]<>')
                and re.search(r'\b(?:INC\.?|CORPORATION|CORP\.?|COMPANY|LIMITED|LTD\.?|PLC|LLC|L\.?P\.?|N\.?V\.?)\s*$',owner,re.I)):
            attributes['reporting_entity'] = owner
        add(heading.start(), table[1], attributes, 'explicit_statement_heading_and_immediate_table')
    from .statement_headings import embedded_statement_regions
    for start,end,attributes,basis in embedded_statement_regions(text,tables):add(start,end,attributes,basis)
    items = list(ITEM.finditer(text))
    for i, heading in enumerate(items):
        event = {'2.02':'earnings_release', '2.03':'financing'}.get(heading['number'])
        if event:
            add(heading.start(), items[i+1].start() if i+1<len(items) else len(text),
                {'event_type':event}, 'explicit_sec_item_'+heading['number'])
    from .business_scope_attributes import table_attributes,exhibit_attributes,transaction_attributes,disclosure_attributes
    for start,end,attributes,basis in [*table_attributes(text,tables),
                                      *exhibit_attributes(text,tables),*transaction_attributes(text),*disclosure_attributes(text)]:
        add(start,end,attributes,basis)
    return regions


def matching_state(scopes, wanted):
    """AND within one original region, never combine different table owners."""
    if not scopes:
        return 'unknown'
    states = []
    for scope in scopes:
        actual = scope['attributes']; checks = []
        for key, values in wanted.items():
            if key in {'unknown_policy','fact_periods'}:continue
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


def interval_matching_state(scopes, wanted):
    """Combine only at a proven common interval, never across adjacent tables.

    A broad SEC event can supply event_type while the nested table supplies its
    owner. An unknown broad region cannot override a known conflicting owner.
    Contradictory original bindings remain unresolved rather than choosing one.
    """
    checks=[]
    for key,values in wanted.items():
        if key in {'unknown_policy','fact_periods'} or not values:continue
        actual=[s['attributes'][key] for s in scopes if key in s['attributes']]
        if not actual:
            checks.append(None);continue
        states=[matching_state([{'attributes':{key:v}}],{key:values}) for v in actual]
        checks.append(False if all(s=='mismatch' for s in states) else
                      True if all(s=='match' for s in states) else None)
    return 'mismatch' if False in checks else 'unknown' if None in checks else 'match'


def select_scoped(rows, wanted):
    counts = {'match':0,'unknown':0,'mismatch':0}; selected = []
    for row in rows:
        business={k:v for k,v in wanted.items() if k not in {'unknown_policy','fact_periods'} and v}
        state = matching_state(row.get('evidence_scopes', []), wanted) if business else 'match'
        # A mixed chunk may contain an unclassified paragraph beside a known
        # conflicting table. That table cannot classify the entire chunk.
        if state == 'mismatch' and not row.get('evidence_scope_complete', False):
            state = 'unknown'
        if row.get('source_interval'):
            intervals=scope_intervals(*row['source_interval'],row.get('evidence_scopes',[]),wanted)
            states=[s['state'] for s in intervals]
            state='match' if 'match' in states else 'unknown' if 'unknown' in states else 'mismatch'
        if wanted.get('fact_periods') and state!='mismatch':
            from .fact_scope import fact_state
            state=fact_state(row,wanted)
        counts[state] += 1
        if state == 'match' or (state == 'unknown' and wanted.get('unknown_policy') == 'retain'):
            selected.append(row)
    return selected, {'policy':POLICY, 'constraints':wanted, 'counts':counts,
        'selected':len(selected), 'filtered_before_scoring':True,
        'unknown_is_not_source_absence':True}


def scope_intervals(start,end,regions,wanted):
    """Classify a single original coordinate frame, shared by recall and scoring."""
    if type(start) is not int or type(end) is not int or not 0<=start<end:
        raise ValueError('evidence_scope_invalid_source_interval')
    active=[s for s in regions if s['source_char_start']<end and s['source_char_end']>start]
    boundaries=sorted({start,end,*(max(start,s['source_char_start']) for s in active),
                       *(min(end,s['source_char_end']) for s in active)})
    return [{'source_char_start':lo,'source_char_end':hi,'state':interval_matching_state(
        [s for s in active if s['source_char_start']<=lo and s['source_char_end']>=hi],wanted)}
        for lo,hi in zip(boundaries,boundaries[1:])]


def covers_interval(scopes, start, end):
    position=start
    for scope in sorted(scopes,key=lambda s:s['source_char_start']):
        lo,hi=scope['source_char_start'],scope['source_char_end']
        if lo>position:break
        position=max(position,hi)
    return position>=end


def plan_scope(query, query_plan=None):
    """Extract positive requirements while retaining exclusions separately."""
    from .query_requirements import positive_view
    query, _ = positive_view(query)
    from .announcement_query import event_requirements
    events = event_requirements(query)
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
            if not re.search(r'附注|明细|调节|摘要|\b(?:notes?|detail|highlights?|reconciliation|supplemental)\b',query,re.I):
                wanted['statement_role']=['primary']
            constraint=(query_plan or {}).get('constraint',{})
            if constraint.get('issuer_id') and constraint.get('company_names'):
                wanted['reporting_entity']=constraint['company_names']
    from .business_scope_attributes import query_attributes
    wanted.update(query_attributes(query))
    from .fact_scope import inferred_fact_requirements
    facts=inferred_fact_requirements(query)
    if facts:wanted['fact_periods']=facts
    return wanted if len(wanted)>1 else None


def resolve_scope(query, query_plan, explicit=None):
    """Reconcile explicit business fields with safely understood query fields."""
    inferred=plan_scope(query, query_plan)
    if explicit is None:
        return inferred
    for key, values in (inferred or {}).items():
        if key=='unknown_policy' or not explicit.get(key):
            continue
        if key=='fact_periods':
            normalize=lambda rows:{json.dumps({k:v for k,v in r.items() if v is not None},sort_keys=True) for r in rows}
            expected,supplied=normalize(values),normalize(explicit[key])
        elif key=='reporting_entity':
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
    from .source_coordinates import VERIFIED, verified_bounds
    if structure.get('status') not in VERIFIED:
        return ''
    _,start,end=verified_bounds(row)
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
        allowed={'reporting_entity':None,'statement_type':{'balance_sheet','cash_flow','income_statement','equity_statement'},
                 'statement_role':{'primary','supplemental','reconciliation'},
                 'consolidation':{'consolidated'},'event_type':{'earnings_release','financing'},
                 'asset_scope':{'pension_plan','postretirement_plan','nuclear_decommissioning_trust','investment_fund'},
                 'table_topic':{'fair_value_measurements','asset_allocation'},
                 'exhibit_role':{'press_release','certification','interactive_data','debt_agreement','acquisition_agreement'},
                 'transaction_id':None}
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
