import pytest
from retrieval.evidence_scope import select_scoped,resolve_scope
from sec_agent.research_foundation.organization_evidence_filter import OrganizationEvidenceFilter


def fact(start,end,value,concept='cash_equivalents'):
    return {'source_char_start':start,'source_char_end':end,'concept':concept,
            'role':'table_header','period':{'kind':'date','value':value}}


def request(**kwargs):
    return OrganizationEvidenceFilter(fact_periods=[{'concept':'cash_equivalents','kind':'date','value':'2025-12-31'}],**kwargs).model_dump(mode='json',exclude_defaults=True)


def test_original_fact_period_filters_before_ranking_without_borrowing_report_date():
    rows=[{'node_id':'correct','source_interval':[0,100],'period_evidence':[fact(40,45,'2025-12-31')]},
          {'node_id':'old','source_interval':[0,100],'period_evidence':[fact(40,45,'2024-12-31')]},
          {'node_id':'wrong-measure','source_interval':[0,100],'period_evidence':[fact(40,45,'2025-12-31','restricted_cash')]},
          {'node_id':'publication-only','source_interval':[0,100],'publication_date':'2025-12-31'}]
    selected,receipt=select_scoped(rows,request())
    assert [r['node_id'] for r in selected]==['correct']
    assert receipt['counts']=={'match':1,'unknown':3,'mismatch':0}
    assert len(select_scoped(rows,request(unknown_policy='retain'))[0])==4


def test_fact_and_owner_must_share_interval_not_separate_tables():
    row={'node_id':'mixed','source_interval':[0,100],
        'evidence_scopes':[{'source_char_start':0,'source_char_end':50,'attributes':{'reporting_entity':'ALPHA INC.'}},
                           {'source_char_start':50,'source_char_end':100,'attributes':{'reporting_entity':'BETA INC.'}}],
        'period_evidence':[fact(10,15,'2024-12-31'),fact(70,75,'2025-12-31')]}
    assert not select_scoped([row],request(reporting_entity=['Alpha']))[0]
    assert select_scoped([row],request(reporting_entity=['Beta']))[0]


def test_unit_cannot_borrow_parent_fact_outside_its_own_interval():
    row={'node_id':'unit','source_interval':[0,50],'period_evidence':[fact(70,75,'2025-12-31')]}
    assert not select_scoped([row],request())[0]


def test_explicit_contract_rejects_invalid_period_and_natural_conflict():
    for value in ['2025-02-30','FY2025','2025-12-31T00:00:00']:
        with pytest.raises(ValueError):OrganizationEvidenceFilter(fact_periods=[{'concept':'cash_equivalents','kind':'date','value':value}])
    with pytest.raises(ValueError,match='conflicts_with_query:fact_periods'):
        resolve_scope('Cash equivalents as of 2024-12-31',{},request())
    resolved=resolve_scope('Cash equivalents as of 2025-12-31',{},request())
    assert resolved['unknown_policy']=='exclude'
    assert 'fact_periods' not in (resolve_scope('Published 2025-12-31 cash equivalents',{}) or {})


@pytest.mark.parametrize('identifier,scheme,accepted',[
    ('00000123','http://www.sec.gov/CIK',True),
    ('123','https://www.sec.gov/CIK/',True),
    ('456','http://www.sec.gov/CIK',False),
    ('123','different-system',False)])
def test_tagged_fact_owner_is_checked_before_candidate_scoring(identifier,scheme,accepted):
    from retrieval.fact_scope import verified_fact_owner
    owner=verified_fact_owner({'verified_company_names':['Cedar Systems Inc.'],
        'fact_entity_identifiers':[{'identifier':'123','scheme':'http://www.sec.gov/CIK'}]})
    evidence={**fact(10,15,'2025-12-31'),'entity':identifier,'entity_scheme':scheme}
    row={'node_id':'original','source_interval':[0,100],'period_evidence':[evidence],
         'fact_owner':owner,'evidence_scopes':[{'source_char_start':0,'source_char_end':100,
             'attributes':{'reporting_entity':'Cedar Systems Inc.'}}]}
    assert bool(select_scoped([row],request(reporting_entity=['Cedar Systems']))[0])==accepted
    row.pop('fact_owner')
    assert not select_scoped([row],request())[0]
    # Exploratory unknowns remain visible as unknown, not proven matches.
    selected,receipt=select_scoped([row],request(unknown_policy='retain'))
    assert selected and receipt['counts']['unknown']==1


def test_tagged_parent_identifier_cannot_prove_named_subsidiary_fact():
    from retrieval.fact_scope import verified_fact_owner
    metadata={'verified_company_names':['Cedar Parent Inc.'],
        'fact_entity_identifiers':[{'identifier':'123','scheme':'http://www.sec.gov/CIK'}]}
    row={'node_id':'conflicting','source_interval':[0,100],'fact_owner':verified_fact_owner(metadata),
         'period_evidence':[{**fact(10,15,'2025-12-31'),'entity':'123','entity_scheme':'http://www.sec.gov/CIK'}],
         'evidence_scopes':[{'source_char_start':0,'source_char_end':100,
             'attributes':{'reporting_entity':'Cedar Operating LLC'}}]}
    assert not select_scoped([row],request(reporting_entity=['Cedar Operating LLC']))[0]
    for change in ({'joint_registrant_names':['Cedar Parent Inc.','Cedar Operating LLC']},
                   {'company_name_resolution':'original_cover_url_cik_conflict'},
                   {'fact_entity_identifiers':metadata['fact_entity_identifiers']*2}):
        assert verified_fact_owner({**metadata,**change})=={}
