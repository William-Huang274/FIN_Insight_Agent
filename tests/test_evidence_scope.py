import pytest
from retrieval.evidence_scope import source_scopes, select_scoped, matching_state, plan_scope
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest


def test_same_document_different_reporting_entities_and_mixed_regions():
    text = ('ALPHA INC.\nCONSOLIDATED BALANCE SHEETS\n(millions)\n[TABLE: original]\nCash | 10\n[/TABLE]\n'
            'BETA COMPANY\nCONSOLIDATED BALANCE SHEETS\n(millions)\n[TABLE: original]\nCash | 2\n[/TABLE]')
    scopes = source_scopes(text)
    wanted = {'reporting_entity':['Alpha'], 'statement_type':['balance_sheet']}
    assert len(scopes)==2
    assert matching_state(scopes[:1], wanted)=='match'
    assert matching_state(scopes[1:], wanted)=='mismatch'
    assert matching_state(scopes, wanted)=='match'  # Never discard mixed evidence.
    rows = [{'node_id':'a','evidence_scopes':scopes[:1]}, {'node_id':'b','evidence_scopes':scopes[1:],'evidence_scope_complete':True}, {'node_id':'u'}]
    selected, receipt = select_scoped(rows,wanted)
    assert [r['node_id'] for r in selected]==['a']
    assert receipt['counts']=={'match':1,'mismatch':1,'unknown':1}
    assert [r['node_id'] for r in select_scoped(rows,{**wanted,'unknown_policy':'retain'})[0]]==['a','u']
    rows[1]['evidence_scope_complete']=False
    assert select_scoped(rows,{**wanted,'unknown_policy':'retain'})[0]==rows


def test_scope_does_not_borrow_entity_or_statement_from_another_region():
    scopes = [{'attributes':{'reporting_entity':'Alpha Inc.','statement_type':'income_statement'}},
              {'attributes':{'reporting_entity':'Beta Company','statement_type':'balance_sheet'}}]
    assert matching_state(scopes, {'reporting_entity':['Alpha'], 'statement_type':['balance_sheet']})=='mismatch'


def test_intervening_prose_never_binds_an_unrelated_table():
    assert not source_scopes('ALPHA INC.\nCONSOLIDATED BALANCE SHEETS\nThe subsidiary below has different accounts.\n[TABLE: original]\nx\n[/TABLE]')


def test_wrapped_statement_titles_and_standalone_units_are_original_scope():
    text='NORTH HARBOR INC.\nCONSOLIDATED\nBALANCE SHEETS\nUSD millions\n[TABLE: original]\nCash | 10\n[/TABLE]'
    scope=source_scopes(text)
    assert len(scope)==1
    assert scope[0]['attributes']=={'reporting_entity':'NORTH HARBOR INC.',
        'statement_type':'balance_sheet','consolidation':'consolidated'}
    assert not source_scopes(text.replace('USD millions','(The subsidiary uses USD millions)'))


def test_event_scope_does_not_confuse_earnings_and_debt_or_guess_negation():
    text = 'Item 2.02 Results of Operations and Financial Condition\nearnings\nItem 2.03 Creation of a Direct Financial Obligation\nnotes\nItem 9.01 Exhibits\n'
    scopes=source_scopes(text)
    assert matching_state(scopes[:1],{'event_type':['earnings_release']})=='match'
    assert matching_state(scopes[1:],{'event_type':['earnings_release']})=='mismatch'
    assert plan_scope('Alpha earnings release')['event_type']==['earnings_release']
    assert plan_scope('Not financing release, earnings release')['event_type']==['earnings_release']


def test_explicit_statement_request_inherits_only_an_unambiguous_catalog_owner():
    query='Alpha consolidated balance sheet cash'
    constraint={'issuer_id':'A','company_names':['Alpha Inc.']}
    assert plan_scope(query,{'constraint':constraint})['reporting_entity']==['Alpha Inc.']
    assert 'reporting_entity' not in plan_scope(query,{'constraint':{'issuer_union':[constraint]}})
    assert plan_scope('Alpha annual report cash') is None


def test_tool_schema_business_scope_and_legacy_serialization():
    old=SourceDocumentRequest(operation='search',query='cash')
    assert 'organization_evidence_filter' not in old.model_dump()
    request=SourceDocumentRequest(source_space='organization',operation='search',query='cash',
        organization_evidence_filter={'reporting_entity':['Alpha'], 'statement_type':['balance_sheet']})
    assert request.model_dump()['organization_evidence_filter']['unknown_policy']=='exclude'
    with pytest.raises(ValueError,match='requires_organization_search'):
        SourceDocumentRequest(operation='search',organization_evidence_filter={'event_type':['financing']})


def test_typed_scope_and_language_conflicts_are_not_silently_ignored():
    from retrieval.evidence_scope import resolve_scope
    with pytest.raises(ValueError,match='conflicts_with_query:statement_type'):
        resolve_scope('Alpha balance sheet',{}, {'statement_type':['cash_flow']})
    r=resolve_scope('Alpha consolidated balance sheet',{}, {'reporting_entity':['Alpha']})
    assert r=={'unknown_policy':'exclude','reporting_entity':['Alpha'],
               'statement_type':['balance_sheet'],'consolidation':['consolidated']}
    assert resolve_scope('Not financing release',{},None) is None


def test_scoring_scope_has_original_interval_and_rejects_unrelated_regions():
    from retrieval.evidence_scope import scoring_scope_text
    row={'original_source':{'source_char_start':50,'source_char_end':80},
         'source_structure':{'status':'verified_original_coordinates','evidence_scopes':[
             {'source_char_start':20,'source_char_end':100,'content_sha256':'a'*64,
              'attributes':{'reporting_entity':'Beta Company','statement_type':'balance_sheet'}}]}}
    text=scoring_scope_text(row)
    assert 'Beta Company' in text and 'ONLY to its own original interval' in text
    row['source_structure']['evidence_scopes'][0]['source_char_start']=90
    with pytest.raises(ValueError,match='unverified_evidence_scope'):scoring_scope_text(row)


def test_actual_navigation_filters_before_hybrid_and_denies_revoked_empty_scope(tmp_path, monkeypatch):
    from test_organization_candidate_index import prepared, query
    from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
    nav,reader,state,_,grant=prepared(tmp_path,monkeypatch)
    nav.warm_release()
    ci=nav._candidate_index
    # Inject verified metadata for this deterministic fixture, never product data.
    chosen=list(ci.rows)[:2]
    ci.rows[chosen[0]]['evidence_scopes']=[{'attributes':{'event_type':'earnings_release'}}]
    ci.rows[chosen[1]]['evidence_scopes']=[{'attributes':{'event_type':'financing'}}]
    original=nav.hybrid.rank
    def checked(rows,*args,**kwargs):
        assert [r['node_id'] for r in rows]==chosen[:1]
        return original(rows,*args,**kwargs)
    monkeypatch.setattr(nav.hybrid,'rank',checked)
    request=query(organization_evidence_filter={'event_type':['earnings_release']})
    result=nav.navigate(request)
    assert len(result.items)==1 and result.organization_evidence_scope['counts']['match']==1
    state['status']=404
    with pytest.raises(OrganizationExecutionUnavailable):nav.navigate(request)
