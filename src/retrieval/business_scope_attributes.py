"""Original table introductions and exhibit descriptions, with bounded scope.

These are navigation attributes, not financial equivalences or truth labels.
Never infer the reporting entity from an issuer name elsewhere in the filing.
"""
import re

ASSET_PATTERNS={
    'pension_plan':r'\bpension (?:plan )?(?:assets?|trusts?|funds?)\b|养老金(?:计划)?资产',
    'postretirement_plan':r'\b(?:other )?postretirement (?:benefit )?(?:plan )?assets?\b|退休后福利资产',
    'nuclear_decommissioning_trust':r'\bnuclear decommissioning trust(?: funds?)?\b|核退役信托',
    'investment_fund':r'\b(?:investment|mutual) fund assets?\b|投资基金资产',
}
TABLE_TOPICS={
    'fair_value_measurements':r'\bfair value (?:measurements?|hierarchy)\b|公允价值(?:计量|层级)',
    'asset_allocation':r'\b(?:target )?asset allocations?\b|资产配置',
}
EXHIBIT_PATTERNS={
    'press_release':r'\bpress release\b|新闻稿',
    'certification':r'\bcertification of (?:the )?(?:principal|chief)\b|高管认证',
    'interactive_data':r'\b(?:interactive data file|XBRL (?:instance|taxonomy))\b',
    'debt_agreement':r'\b(?:credit agreement|indenture|note purchase agreement)\b',
    'acquisition_agreement':r'\b(?:agreement and plan of merger|asset purchase agreement)\b',
}


def announced_event(subject):
    """Classify the explicitly announced object, not incidental finance words.

    Both event kinds in one announcement remain ambiguous. A generic press
    release, exhibit number or mention of liquidity proves neither event.
    """
    patterns={
        'earnings_release':r'\b(?:financial results|results of operations|earnings(?: results)?)\b',
        'financing':r'\b(?:(?:senior |convertible |secured |unsecured )*(?:notes?|bonds?|debt|equity|shares?|securities) (?:offering|issuance)|(?:offering|issuance) of (?:its |the )?(?:(?:senior|convertible|secured|unsecured) )*(?:notes?|bonds?|debt|equity|shares?|securities)|credit (?:facility|agreement)|term loan)\b',
    }
    return _unique(subject,patterns)


def _unique(text,patterns):
    values=[name for name,pattern in patterns.items() if re.search(pattern,text,re.I)]
    return values[0] if len(values)==1 else None


def table_attributes(text,tables):
    """Bind only the immediate caption or explicit introduction to one table."""
    result=[]
    for start,end in tables:
        prefix=text[:start].rstrip()
        line=prefix.rsplit('\n',1)[-1] if prefix else ''
        lo=len(prefix)-len(line)
        # A bounded line ending in ':' announces the following table. A
        # standalone caption may have a note number, but cannot be a sentence
        # merely mentioning someone else's assets or containing table cells.
        title=re.sub(r'^(?:\d+[.)]\s+|#{1,6}\s+)','',line).strip()
        standalone=(len(title)<=100 and not re.search(r'[|<>\[\]]',title)
            and not re.search(r'\b(?:is|was|were|include|includes|reported|held|discussed)\b',title,re.I))
        introduction=(len(title)<=600 and title.endswith(':')
            and bool(re.search(r'\b(?:following|classifications|allocations|summari[sz](?:es|ed)|presented below)\b',title,re.I)))
        if not (standalone or introduction):continue
        attrs={}
        if asset:=_unique(title,ASSET_PATTERNS):attrs['asset_scope']=asset
        if topic:=_unique(title,TABLE_TOPICS):attrs['table_topic']=topic
        if attrs:
            attrs['statement_role']='supplemental'
            result.append((lo,end,attrs,'explicit_immediate_table_subject'))
    return result


def exhibit_attributes(text,tables):
    """Bind each exact exhibit row; a shared 99.1 number is not a business role."""
    result=[]
    for start,end in tables:
        body=text[start:end]
        for line in re.finditer(r'(?m)^[ \t|]*(?:\d{1,3}(?:\.\d+|\.[A-Z]+)?)[ \t|]+[^\n]+$',body):
            if '|' not in line[0]:continue
            role=_unique(line[0],EXHIBIT_PATTERNS)
            if not role:continue
            attrs={'exhibit_role':role}
            if role=='press_release' and (event:=announced_event(line[0])):
                attrs['event_type']=event
            result.append((start+line.start(),start+line.end(),attrs,'explicit_exhibit_row_description'))
    return result


def transaction_attributes(text):
    """Copy explicitly labeled security identifiers; never join coupon/year guesses."""
    result=[]
    for match in re.finditer(r'(?im)^[^\n]{0,180}\b(?P<kind>ISIN|CUSIP)\s*[:#]?\s*(?P<id>[A-Z0-9]{9,12})\b[^\n]{0,180}$',text):
        kind,value=match['kind'].upper(),match['id'].upper()
        if len(value)!=(12 if kind=='ISIN' else 9):continue
        result.append((match.start(),match.end(),{'transaction_id':kind+':'+value},'explicit_security_identifier'))
    return result


def disclosure_attributes(text):
    """A filing's explicit release announcement, not mere exhibit boilerplate.

    Bind the original announcement line only. It supplies the role and event
    together, without joining a different exhibit row or another SEC item.
    """
    result=[]
    for line in re.finditer(r'(?m)^[^\n]+$',text):
        if '|' in line[0] or len(line[0])>4000:continue
        announcement=re.search(r'\b(?:issued|published)\s+(?:a|the)\s+press release\s+announcing\b',line[0],re.I)
        if not announcement:continue
        attrs={'exhibit_role':'press_release'}
        # Only the announced subject before the next sentence; descriptions
        # of a different release later in the paragraph cannot change it.
        subject=re.split(r'(?<=[.!?])\s+(?=[A-Z])',line[0][announcement.end():],maxsplit=1)[0]
        if event:=announced_event(subject):attrs['event_type']=event
        result.append((line.start(),line.start()+announcement.end()+len(subject),attrs,'explicit_original_release_announcement'))
    return result


def query_attributes(query):
    attrs={}
    if asset:=_unique(query,ASSET_PATTERNS):attrs['asset_scope']=[asset]
    if topic:=_unique(query,TABLE_TOPICS):attrs['table_topic']=[topic]
    if role:=_unique(query,EXHIBIT_PATTERNS):attrs['exhibit_role']=[role]
    identifiers=[a['transaction_id'] for _,_,a,_ in transaction_attributes(query)]
    if identifiers:attrs['transaction_id']=list(dict.fromkeys(identifiers))
    return attrs
