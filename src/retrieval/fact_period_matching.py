"""Conservative original-text period associations; no filing-year inference.

Evidence records name the clause/cell that supplies both concept and period.
Unrecognized syntax and ambiguous headers abstain; this is not answer validation.
"""
from datetime import date
import re
from .financial_query_needs import concepts

POLICY = 'explicit-fact-periods.v1'
MONTHS = {name.lower():i for i,name in enumerate(('January','February','March','April','May','June','July','August','September','October','November','December'),1)}
DATE = re.compile(r'\b(20\d{2})-(\d{2})-(\d{2})\b|(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日|\b('+'|'.join(MONTHS)+r')\s+(\d{1,2}),?\s+(20\d{2})\b',re.I)
FY = re.compile(r'\b(?:FY\s*|fiscal\s+(?:year\s+)?)(20\d{2})\b|(20\d{2})\s*财年',re.I)
TABLE = re.compile(r'\[TABLE:[^\n]*\].*?\[/TABLE\]',re.S)
NUMBER = re.compile(r'^\s*\(?\s*[$€£]?\s*-?\d[\d,]*(?:\.\d+)?\s*%?\s*\)?\s*$')
DURATION = re.compile(r'\b(?:years?|months?|weeks?|quarters?)\s+ended\b|\bthrough\b|\bto\b|季度|年度累计', re.I)
MONTH_DAY = re.compile(r'\b('+'|'.join(MONTHS)+r')\s+(\d{1,2})\b', re.I)
BALANCES = {'cash_equivalents','restricted_cash','repurchase_authorization'}


def balance_concepts(text):
    names={n for n,_,_ in concepts(text)} & BALANCES
    # Retrieval vocabulary deliberately includes spending as a useful route;
    # a period association must not call that spending an unused authority.
    if not re.search(r'\b(?:remaining|remained|unused|available)\b|剩余|尚可',text,re.I):
        names.discard('repurchase_authorization')
    if re.search(r'\b(?:beginning|increase|decrease|change)\b|期初|增加|减少|变动',text,re.I):
        names.difference_update({'cash_equivalents','restricted_cash'})
    return names


def dates(text):
    found=[]
    for m in DATE.finditer(text):
        values=m.groups()
        try:
            if values[0]:y,mo,d=map(int,values[:3])
            elif values[3]:y,mo,d=map(int,values[3:6])
            else:y,mo,d=int(values[8]),MONTHS[values[6].lower()],int(values[7])
            value=date(y,mo,d).isoformat()
        except ValueError:continue
        found.append((m.start(),m.end(),value))
    return found


def target_period(query):
    """One explicit temporal target. Comparisons remain unbound, never narrowed."""
    ds=dates(query);fys={a or b for a,b in FY.findall(query)}
    if len(ds)==1 and not fys:
        return {'kind':'date','value':ds[0][2]}
    if len(fys)==1 and not ds:
        return {'kind':'fiscal_year','value':next(iter(fys))}
    return {'kind':'unknown','reason':'multiple_or_unresolved_periods'}


def query_period(query):
    target=target_period(query)
    if target['kind']=='date':
        before=query[:dates(query)[0][0]]
        if not re.search(r'(?:\bas of|\bat|截至)\s*$',before,re.I):
            return {'kind':'unknown','reason':'date_role_not_explicit_balance_target'}
    if re.search(r'quarter|季度|\bQ[1-4]\b',query,re.I):
        return {'kind':'unknown','reason':'quarter_requires_explicit_duration'}
    return target


def query_period_requirements(query):
    """Typed explicit comparisons; never map a fiscal quarter to calendar dates."""
    from .query_requirements import positive_view
    text, _ = positive_view(query)
    observed = dates(text)
    quarters = re.findall(r'\b(?:FY\s*)?(20\d{2})\s*Q([1-4])\b|\bQ([1-4])\s*(?:FY\s*)?(20\d{2})\b', text, re.I)
    if quarters:
        targets = [{'kind':'fiscal_quarter','fiscal_year':a or d,'quarter':int(b or c)} for a,b,c,d in quarters]
        return {'targets':targets,'calendar_mapping':'unresolved_requires_original_fiscal_calendar'}
    if len(observed)==2 and re.search(r'\bfrom\b|自|从',text[:observed[0][0]],re.I):
        bridge=text[observed[0][1]:observed[1][0]]
        if re.fullmatch(r'\s*(?:to|through|至|到|–|—)\s*',bridge,re.I):
            start,end=observed[0][2],observed[1][2]
            if start<=end:
                return {'targets':[{'kind':'duration','start':start,'end':end}],'basis':'explicit_interval'}
    if observed and re.search(r'\bas of\b|\bat\b|截至',text[:observed[0][0]],re.I):
        # Every later date must be linked by an explicit comparison connector;
        # publication/authorization dates elsewhere are not balance targets.
        if all(re.fullmatch(r'\s*(?:and|versus|vs\.?|with|和|与|及|、|相比)\s*',
                           text[left[1]:right[0]],re.I) for left,right in zip(observed,observed[1:])):
            return {'targets':[{'kind':'date','value':v} for v in dict.fromkeys(d[2] for d in observed)],
                    'basis':'explicit_balance_dates'}
    fiscal = list(dict.fromkeys(a or b for a,b in FY.findall(text)))
    if fiscal and not observed and not re.search(r'quarter|季度|\bQ[1-4]\b',text,re.I):
        return {'targets':[{'kind':'fiscal_year','value':v} for v in fiscal],'basis':'explicit_fiscal_years'}
    return {'targets':[],'unresolved':'no_unambiguous_fact_period_requirement'}


def prose_periods(text):
    # Table contents cannot borrow a date from surrounding narrative.
    # A removed table is a clause boundary, not whitespace joining a heading
    # to an unrelated numeric footnote after the table. Preserve coordinates.
    masked=TABLE.sub(lambda m:'\x00'*len(m[0]),text)
    output=[]
    for match in re.finditer(r'[^。；;!?\x00]+',masked):
        # Split English sentences without splitting decimals or line wraps.
        for part in re.finditer(r'.+?(?:\.(?=\s+[A-Z])|$)',match[0],re.S):
            clause=part[0];offset=match.start()+part.start()
            # Markdown rows are handled by their own explicit columns.
            if '|' in clause:continue
            if re.search(r'\b(?:forecast|projected|expected|might|would|could)\b|预计|预测|可能',clause,re.I):continue
            names={n for n,_,_ in concepts(clause)}
            numeric_text=FY.sub('',DATE.sub('',clause))
            if not names or not re.search(r'\d',numeric_text):continue
            ds=dates(clause);fys={a or b for a,b in FY.findall(clause)}
            bindings=[]
            for lo,hi,value in ds:
                before=clause[max(0,lo-35):lo]
                after=clause[hi:hi+15]
                if re.search(r'(?:\bas\s+of|\bat|截至)\s*$',before,re.I):
                    role='balance_as_of'
                elif re.search(r'(?:expir\w*|matur\w*)\s+(?:on\s+)?$',before,re.I) or re.match(r'\s*(?:到期|届满)',after):
                    role='expiration'
                elif re.search(r'\bon\s*$',before,re.I) and re.search(r'authoriz|批准|授权',clause,re.I):
                    role='authorization_event'
                else:continue
                # Multiple dates can describe different events. A balance is
                # only bound when the clause has no competing date or FY.
                if role=='balance_as_of' and (len(ds)!=1 or fys or
                    re.search(r'\b(?:and|or|versus|vs\.?)\s+20\d{2}\b|(?:和|及|与)\s*20\d{2}年',clause,re.I)):continue
                allowed=balance_concepts(clause) if role=='balance_as_of' else names & {'authorization_expiration','debt_maturity'} if role=='expiration' else names & {'repurchase_authorization'}
                for name in sorted(allowed):
                    bindings.append({'concept':name,'role':role,'period':{'kind':'date','value':value}})
            if (len(fys)==1 and not ds and not re.search(r'quarter|季度|Q[1-4]',clause,re.I)
                    and not re.search(r'(?:fiscal\s+(?:year\s+)?20\d{2}|FY\s*20\d{2})\s+(?:annual\s+)?report|20\d{2}财年年报',clause,re.I)):
                for name in sorted(names):
                    bindings.append({'concept':name,'role':'fiscal_year','period':{'kind':'fiscal_year','value':next(iter(fys))}})
            for b in bindings:
                output.append({**b,'basis':'explicit_same_clause','source_char_start':offset,
                    'source_char_end':offset+len(clause),'quote':text[offset:offset+len(clause)]})
    return output


def table_periods(text,tables):
    """Only verified column geometry and a unique explicit header above data."""
    output=[]
    for table in tables:
        if table.get('status')!='original_geometry_verified':continue
        cells=table['cells'];groups={}
        for cell in cells:groups.setdefault(cell['row'],[]).append(cell)
        data_rows=[]
        for row,values in groups.items():
            labels=[c for c in values if c['text'].strip() and not NUMBER.fullmatch(c['text']) and not dates(c['text']) and not FY.search(c['text'])]
            if labels and any(NUMBER.fullmatch(c['text']) and not re.fullmatch(r'20\d{2}',c['text'].strip()) for c in values):data_rows.append(row)
        if not data_rows:continue
        header=[c for c in cells if c['row']<min(data_rows)]
        for row in data_rows:
            values=groups[row]
            label=next((c for c in values if c['text'].strip()),None)
            if not label:continue
            # A displayed end date is not enough to identify a flow's start.
            # Only known stock measures participate in exact-date matching.
            names=balance_concepts(label['text'])
            for c in values:
                if c.get('facts') or not NUMBER.fullmatch(c['text']):continue
                headers=[h for h in header if h['column']<=c['column'] and c['column']+c['colspan']<=h['column']+h['colspan']]
                # A year-ended flow is not a balance at the ending date.
                # Keep unrecognized durations unbound until start/end can be
                # established; never borrow the filing's year or fiscal end.
                if any(DURATION.search(h['text']) for h in headers):continue
                bindings=[(h,target_period(h['text'])) for h in headers]
                bindings=[(h,p) for h,p in bindings if p['kind']!='unknown']
                # Common ordinary HTML: a month/day spans two columns and
                # the next header row supplies each column's explicit year.
                # Only unique components on the same verified column path.
                years={h['text'].strip() for h in headers if re.fullmatch(r'20\d{2}',h['text'].strip())}
                month_days={(m[1].lower(),int(m[2])) for h in headers if not dates(h['text']) for m in MONTH_DAY.finditer(h['text'])}
                if len(years)==1 and len(month_days)==1:
                    month,day=next(iter(month_days))
                    try: value=date(int(next(iter(years))),MONTHS[month],day).isoformat()
                    except ValueError: value=None
                    if value:bindings.append((headers[-1],{'kind':'date','value':value}))
                identities={(p['kind'],p['value']) for _,p in bindings}
                if len(identities)!=1:continue
                h,p=bindings[-1]
                for name in sorted(names):
                    output.append({'concept':name,'role':'table_header','period':p,
                        'basis':'verified_column_header','source_char_start':c['source_char_start'],
                        'source_char_end':c['source_char_end'],'quote':c['text'],
                        'label':label['text'],'header':h['text'],'header_source_char_start':h['source_char_start'],
                        'header_components':[{'quote':v['text'],'source_char_start':v['source_char_start'],
                            'source_char_end':v['source_char_end']} for v in headers]})
    return output


def markdown_tables(text):
    """Rectangular explicit pipe tables only; flattened HTML is not Markdown."""
    result=[];blocked=[(m.start(),m.end()) for m in TABLE.finditer(text)]
    for block in re.finditer(r'(?m)^\|[^\n]+\|[ \t]*(?:\n\|[^\n]+\|[ \t]*)+',text):
        if any(a<block.end() and b>block.start() for a,b in blocked) or '\\|' in block[0]:continue
        lines=block[0].splitlines()
        rows=[line.strip().strip('|').split('|') for line in lines]
        if len(rows)<3 or len({len(r) for r in rows})!=1:continue
        if not all(re.fullmatch(r'\s*:?-{3,}:?\s*',v) for v in rows[1]):continue
        cells=[];offset=block.start()
        for y,line in enumerate(lines):
            bounds=[m.start() for m in re.finditer(r'\|',line)]
            if y!=1:
                for x,(a,b) in enumerate(zip(bounds,bounds[1:])):
                    value=line[a+1:b];trim=len(value)-len(value.lstrip());body=value.strip()
                    cells.append({'row':y,'column':x,'rowspan':1,'colspan':1,'text':body,'facts':[],
                        'source_char_start':offset+a+1+trim,'source_char_end':offset+a+1+trim+len(body)})
            offset+=len(line)+1
        from hashlib import sha256
        result.append({'status':'original_geometry_verified','cells':cells,
            'source_char_start':block.start(),'source_char_end':block.end(),
            'content_sha256':sha256(block[0].encode()).hexdigest(),
            'geometry_basis':'explicit_rectangular_markdown'})
    return result


def tagged_periods(tables):
    output=[]
    for table in tables:
        for cell in table['cells']:
            for fact in cell.get('facts',[]):
                context=fact['period'];observed=context.get('dates',{});instant=observed.get('instant')
                if context.get('status')!='explicit_xbrl_period':continue
                # A dimensional/member value is not silently promoted to the
                # issuer-wide metric requested by an unqualified question.
                if context.get('dimensions'):continue
                label=re.sub(r'(?<=[a-z])(?=[A-Z])',' ',fact.get('concept') or '')
                period=({'kind':'date','value':instant} if instant else
                        {'kind':'duration','start':observed['startdate'],'end':observed['enddate']})
                names=balance_concepts(label) if instant else {n for n,_,_ in concepts(label)} - BALANCES
                for name in sorted(names):
                    output.append({'concept':name,'role':'balance_as_of' if instant else 'flow_duration','period':period,
                        'basis':'original_contextref','source_char_start':cell['source_char_start'],
                        'source_char_end':cell['source_char_end'],'quote':cell['text'],
                        'context_ref':fact['context_ref'],'entity':context['entity'],
                        'entity_scheme':context.get('entity_scheme')})
    return output


def match_period(row,need,target):
    if target['kind']=='unknown':return 'unknown'
    if need.get('concept') in {'authorization_expiration','debt_maturity'}:return 'unknown'
    # This is a relative candidate preference, never an access or exclusion rule.
    evidence=row.get('source_structure',{}).get('period_evidence')
    if evidence is None:evidence=prose_periods(row['content'])+table_periods(row['content'],markdown_tables(row['content']))
    matching=[e for e in evidence if e['concept']==need.get('concept') and fact_entity_matches(e,need,row)]
    if need.get('concept')=='repurchase_authorization':
        matching=[e for e in matching if e['role']!='authorization_event']
    comparable=[e for e in matching if e['period']['kind']==target['kind']]
    if any(e['period']==target for e in comparable):return 'match'
    # A fragment is not an exhaustive source. An observed other period is a
    # mismatch for that fact, not proof that the document lacks a target fact.
    return 'other_observed_period' if comparable else 'unknown'


def fact_entity_matches(evidence, need, row):
    """A dated subsidiary value cannot prove the requested issuer's fact date.

    Unknown entity bindings do not supply a positive period preference. They
    remain retrieval candidates and may be read; this is not an access rule.
    """
    owner = need.get('owner') or {}
    if row.get('scoring_view'):
        lo,hi=evidence.get('source_char_start'),evidence.get('source_char_end')
        if type(lo) is not int or type(hi) is not int or not any(
                s['source_char_start']<=lo and s['source_char_end']>=hi for s in row['scoring_view']['spans']):
            return False
    if evidence.get('entity') is not None:
        expected = owner.get('fact_entity_identifiers', [])
        if not expected:
            return False
        def key(entity, scheme):
            if not isinstance(entity,str) or not isinstance(scheme,str):return None
            scheme=scheme.rstrip('/').casefold()
            if scheme in {'http://www.sec.gov/cik','https://www.sec.gov/cik'} and entity.isdigit():
                return ('sec-cik',str(int(entity)))
            return (scheme,entity)
        actual=key(evidence['entity'],evidence.get('entity_scheme'))
        return actual is not None and any(actual==key(e.get('identifier'),e.get('scheme')) for e in expected)
    names=owner.get('company_names') or []
    if names:
        from .evidence_scope import matching_state
        start,end=evidence.get('source_char_start'),evidence.get('source_char_end')
        regions=[s for s in row.get('source_structure',{}).get('evidence_scopes',[])
                 if type(start) is int and type(end) is int
                 and s['source_char_start']<=start and s['source_char_end']>=end]
        if regions and matching_state(regions,{'reporting_entity':names})=='mismatch':
            return False
    return True
