"""Fact-period eligibility from original clause/cell proofs, not filing dates.

OR across requested facts; other business conditions must hold at that same
original interval. This selects candidate evidence, never changes its values.
"""


def compact_evidence(evidence):
    fields=('concept','role','period','source_char_start','source_char_end','entity','entity_scheme')
    return [{k:e[k] for k in fields if k in e} for e in evidence]


def verified_fact_owner(metadata):
    """A single original registrant identity, never a joint filing's archive ID."""
    if metadata.get('joint_registrant_names') or metadata.get('company_name_resolution'):
        return {}
    names=metadata.get('verified_company_names') or [metadata.get('company_name')]
    names=[n for n in names if isinstance(n,str) and n.strip()]
    identifiers=metadata.get('fact_entity_identifiers') or []
    if len(names)!=1 or len(identifiers)!=1:return {}
    return {'company_names':names,'fact_entity_identifiers':identifiers}


def fact_state(row,wanted):
    from .evidence_scope import interval_matching_state
    requests=wanted.get('fact_periods',[])
    if not requests:return 'match'
    bounds=row.get('source_interval')
    if not bounds:return 'unknown'
    business={k:v for k,v in wanted.items() if k not in {'fact_periods','unknown_policy'}}
    for evidence in row.get('period_evidence',[]):
        lo,hi=evidence['source_char_start'],evidence['source_char_end']
        # Partial overlap is not a complete fact proof: a clipped sentence or
        # cell can leave the value/period outside the actual retrieval unit.
        # This matches the complete-span rule applied to the rerank view.
        if not (bounds[0]<=lo<hi<=bounds[1]):continue
        if evidence.get('entity') is not None:
            from .fact_period_matching import fact_entity_matches
            from .evidence_scope import matching_state
            owner=row.get('fact_owner') or {}
            if not fact_entity_matches(evidence,{'owner':owner},row):continue
            if wanted.get('reporting_entity'):
                names=owner.get('company_names') or []
                if len(names)!=1 or matching_state(
                    [{'attributes':{'reporting_entity':names[0]}}],
                    {'reporting_entity':wanted['reporting_entity']})!='match':continue
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
