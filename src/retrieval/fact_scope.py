"""Fact-period eligibility from original clause/cell proofs, not filing dates.

OR across requested facts; other business conditions must hold at that same
original interval. This selects candidate evidence, never changes its values.
"""


def compact_evidence(evidence):
    fields=('concept','role','period','source_char_start','source_char_end','entity','entity_scheme')
    return [{k:e[k] for k in fields if k in e} for e in evidence]


def fact_state(row,wanted):
    from .evidence_scope import interval_matching_state
    requests=wanted.get('fact_periods',[])
    if not requests:return 'match'
    bounds=row.get('source_interval')
    if not bounds:return 'unknown'
    business={k:v for k,v in wanted.items() if k not in {'fact_periods','unknown_policy'}}
    for evidence in row.get('period_evidence',[]):
        lo,hi=evidence['source_char_start'],evidence['source_char_end']
        if not (lo<bounds[1] and hi>bounds[0]):continue
        # A source whose owner is unresolved cannot satisfy an explicit owner.
        regions=[s for s in row.get('evidence_scopes',[])
                 if s['source_char_start']<=lo and s['source_char_end']>=hi]
        state=interval_matching_state(regions,business)
        if state=='mismatch':continue
        for request in requests:
            if request['concept']!=evidence['concept']:continue
            if request['concept']=='repurchase_authorization' and evidence['role']=='authorization_event':continue
            target={k:v for k,v in request.items() if k!='concept' and v is not None}
            if evidence['period']==target:
                if state=='match':return 'match'
    # Unrecognized facts may share a mixed chunk. An observed other period
    # alone cannot prove the entire chunk has no requested fact. Strict mode
    # excludes unresolved candidates; exploration retains them explicitly.
    return 'unknown'


def inferred_fact_requirements(query):
    from .fact_period_matching import query_period_requirements,BALANCES
    from .financial_query_needs import concepts
    from .query_requirements import positive_view
    text,_=positive_view(query)
    names={n for n,_,_ in concepts(text)}
    targets=query_period_requirements(text)['targets']
    # Do not invent a Cartesian binding for mixed measures or event dates.
    if len(names)!=1 or not names<=BALANCES or any(t['kind']!='date' for t in targets):return []
    return [{'concept':next(iter(names)),**t} for t in targets]
