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


def financing_definitions(text):
    """Resolve an instrument's quoted defined name within this original only.

    A bare 'Facility' can mean a factory. Only an immediately preceding credit,
    loan or securities description supports a financial alias. Reused names
    with conflicting/unknown definitions are deliberately not resolved.
    """
    meanings={}
    pattern=r'\(\s*(?:the\s+)?[“\"](?P<alias>[^”\"\n]{2,100})[”\"]\s*\)'
    for match in re.finditer(pattern,text,re.I):
        label=re.split(r'[\n()]',text[max(0,match.start()-240):match.start()])[-1].strip()
        # Definition attaches to the final noun phrase, not an earlier loan
        # mentioned elsewhere in the same sentence.
        financial=bool(re.search(r'\b(?:credit agreement|(?:(?:delayed draw|revolving|senior|secured|unsecured)\s+)*'
            r'(?:term )?loan(?: facility)?|credit facility|(?:notes?|bonds?|securities) offering)\s*$',label,re.I))
        meanings.setdefault(match['alias'].casefold(),set()).add(financial)
    return tuple(alias for alias,states in meanings.items() if states=={True})


def announced_event(subject,definitions=()):
    """Classify the explicitly announced object, not incidental finance words.

    Both event kinds in one announcement remain ambiguous. A generic press
    release, exhibit number or mention of liquidity proves neither event.
    """
    patterns={
        'earnings_release':r'\b(?:financial results|results of operations|earnings(?: results)?)\b',
        'financing':r'\b(?:(?:senior |convertible |secured |unsecured )*(?:notes?|bonds?|debt|equity|shares?|securities) (?:offering|issuance)|(?:offering|issuance) of (?:its |the )?(?:(?:senior|convertible|secured|unsecured) )*(?:notes?|bonds?|debt|equity|shares?|securities)|credit (?:facility|agreement)|term loan)\b',
    }
    values={name for name,pattern in patterns.items() if re.search(pattern,subject,re.I)}
    if any(re.search(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',subject,re.I) for alias in definitions):
        values.add('financing')
    return next(iter(values)) if len(values)==1 else None


def _unique(text,patterns):
    values=[name for name,pattern in patterns.items() if re.search(pattern,text,re.I)]
    return values[0] if len(values)==1 else None


def table_attributes(text,tables):
    """Bind only the immediate caption or explicit introduction to one table."""
    result=[]
    for start,end in tables:
        prefix=text[:start].rstrip()
        # Original filings can insert a page number, navigation label and
        # repeated notes header between an explicit introduction and its table.
        # Remove only that complete page-furniture shape, never free prose or
        # another table, and retain original coordinates for the proof region.
        furniture=re.search(r'\n\s*\d{1,4}\s*\nTable of Contents?\s*\n'
            r'[A-Z][A-Z0-9 &.,()\x27’-]{2,180}\s*\n'
            r'NOTES TO (?:CONDENSED )?CONSOLIDATED FINANCIAL STATEMENTS(?: \(Continued\))?\s*$',prefix)
        if furniture:prefix=prefix[:furniture.start()].rstrip()
        line=prefix.rsplit('\n',1)[-1] if prefix else ''
        lo=len(prefix)-len(line)
        # A bounded line ending in ':' announces the following table. A
        # standalone caption may have a note number, but cannot be a sentence
        # merely mentioning someone else's assets or containing table cells.
        title=re.sub(r'^(?:\d+[.)]\s+|#{1,6}\s+)','',line).strip()
        standalone=(len(title)<=100 and not re.search(r'[|<>\[\]]',title)
            and not re.search(r'\b(?:is|was|were|include|includes|reported|held|discussed)\b',title,re.I))
        introduction=(len(title)<=600 and title.endswith(':')
            and bool(re.search(r'\b(?:following|as follows|classifications|allocations|summari[sz](?:es|ed)|presented below)\b',title,re.I)))
        if not (standalone or introduction):continue
        if introduction and not _unique(title,TABLE_TOPICS):
            # A standalone subject immediately followed by an em dash and the
            # table's introduction may carry the topic; do not scan a section
            # for any convenient earlier mention.
            preceding=prefix[:lo].rstrip()
            caption=re.search(r'(?:^|\n)([^\n|\[\]]{1,100})\n[ \t]*[–—-]\s*$',preceding)
            if caption:
                title=caption[1]+' '+title;lo=caption.start(1)
        attrs={}
        if asset:=_unique(title,ASSET_PATTERNS):attrs['asset_scope']=asset
        if topic:=_unique(title,TABLE_TOPICS):attrs['table_topic']=topic
        if attrs:
            attrs['statement_role']='supplemental'
            result.append((lo,end,attrs,'explicit_immediate_table_subject'))
    return result


def exhibit_attributes(text,tables):
    """Bind each exact exhibit row; a shared 99.1 number is not a business role."""
    result=[];definitions=financing_definitions(text)
    for start,end in tables:
        body=text[start:end]
        for line in re.finditer(r'(?m)^[ \t|]*(?:\d{1,3}(?:\.\d+|\.[A-Z]+)?)[ \t|]+[^\n]+$',body):
            if '|' not in line[0]:continue
            role=_unique(line[0],EXHIBIT_PATTERNS)
            if not role:continue
            attrs={'exhibit_role':role}
            if role=='press_release' and (event:=announced_event(line[0],definitions)):
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

    Bind the announcement and an immediately attached, explicit copy reference.
    Removing an ineligible event must not leave its anaphoric exhibit reference
    looking like a different unknown event. Never cross another statement/item.
    """
    result=[];definitions=financing_definitions(text)
    for line in re.finditer(r'(?m)^[^\n]+$',text):
        if '|' in line[0] or len(line[0])>4000:continue
        announcement=re.search(r'\b(?:issued|published)\s+(?:a|the)\s+press release\s+announcing\b',line[0],re.I)
        if not announcement:continue
        attrs={'exhibit_role':'press_release'}
        # Only the announced subject before the next sentence; descriptions
        # of a different release later in the paragraph cannot change it.
        subject=re.split(r'(?<=[.!?])\s+(?=[A-Z])',line[0][announcement.end():],maxsplit=1)[0]
        if event:=announced_event(subject,definitions):attrs['event_type']=event
        end=line.start()+announcement.end()+len(subject)
        continuation=text[end:end+650]
        reference=re.match(
            r'[ \t]*(?:\r?\n[ \t]*)?'
            r'(?P<sentence>(?:A copy(?: of (?:the|this|that|such) press release| thereof)?|'
            r'(?:The|This|That|Such) press release)\s+'
            r'(?:is|has been)\s+(?:(?:attached|furnished|filed|included)\s+)'
            r'(?:(?:hereto|herewith)\s+)?as\s+Exhibit\s+\d+(?:\.\d+)?'
            r'(?:\s+(?:hereto|herewith))?'
            r'(?:\s+and\s+incorporated\s+(?:herein|herein by reference|by reference))?'
            r'\.(?=\s|$))',continuation,re.I)
        if reference:end+=reference.end()
        result.append((line.start(),end,attrs,'explicit_original_release_announcement'))
    return result


def query_attributes(query):
    attrs={}
    if asset:=_unique(query,ASSET_PATTERNS):attrs['asset_scope']=[asset]
    if topic:=_unique(query,TABLE_TOPICS):attrs['table_topic']=[topic]
    if role:=_unique(query,EXHIBIT_PATTERNS):attrs['exhibit_role']=[role]
    identifiers=[a['transaction_id'] for _,_,a,_ in transaction_attributes(query)]
    if identifiers:attrs['transaction_id']=list(dict.fromkeys(identifiers))
    return attrs
