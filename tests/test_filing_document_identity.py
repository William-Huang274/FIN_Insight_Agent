from retrieval.filing_document_identity import original_filing_key, with_document_issuer_aliases


URL='https://www.sec.gov/Archives/edgar/data/1234567/000123456725000001/acme-20241231.htm'


def test_exact_original_allows_parse_identity_alias_without_global_merge():
    data={'old_parse':{'issuer_id':'COMPANY::old-name','original_filing_key':URL},
          'new_parse':{'issuer_id':'COMPANY::new-name','original_filing_key':URL},
          'other_filing':{'issuer_id':'COMPANY::new-name','original_filing_key':URL.replace('000001','000002')},
          'unknown':{'same_document_issuer_ids':['COMPANY::old-name']}}
    result=with_document_issuer_aliases(data)
    assert result['old_parse']['same_document_issuer_ids']==['COMPANY::new-name','COMPANY::old-name']
    assert result['old_parse']['issuer_id']=='COMPANY::old-name'
    assert result['other_filing']['same_document_issuer_ids']==['COMPANY::new-name']
    assert 'same_document_issuer_ids' not in result['unknown']
    assert 'same_document_issuer_ids' not in data['old_parse']
    assert with_document_issuer_aliases({'old_parse':data['old_parse']})['old_parse']['same_document_issuer_ids']==['COMPANY::old-name']


def test_noncanonical_or_mutable_urls_are_not_identity_proof():
    assert original_filing_key(URL.replace('www.sec.gov','sec.gov'))==URL
    for value in [None, 'https://[invalid', URL+'?version=2', URL+'#section', URL.replace('https:','http:'),
                  URL.replace('www.sec.gov','evil.example'), URL.replace('www.sec.gov','user@www.sec.gov'),
                  URL.replace('/000123456725000001/','/latest/')]:
        assert original_filing_key(value) is None


def test_query_alias_keeps_all_original_checks_and_explicit_filter_exact():
    from sec_agent.research_foundation.organization_query_plan import plan_query, select_planned
    from sec_agent.research_foundation.organization_source_filter import OrganizationSourceFilter, select_documents
    from retrieval.organization_search_needs import owner_matches
    data={'old_parse':{'issuer_id':'COMPANY::acme-finance','original_filing_key':URL,'form':'10-K','period_end':'2024-12-31'},
          'new_parse':{'issuer_id':'COMPANY::acme','original_filing_key':URL,'form':'10-K','period_end':'2024-12-31'},
          'different':{'issuer_id':'COMPANY::acme-finance','original_filing_key':URL.replace('000001','000002'),'form':'10-K'}}
    plan=plan_query('Acme 10-K cash',data,policy='conservative.v5')
    assert select_planned(data,plan)[0]=={'old_parse','new_parse'}
    enriched=with_document_issuer_aliases(data)
    assert owner_matches(enriched['old_parse'],{'issuer_id':'COMPANY::acme'})
    assert not owner_matches(enriched['different'],{'issuer_id':'COMPANY::acme'})
    assert select_documents(enriched,OrganizationSourceFilter(issuer_id='COMPANY::acme'))[0]=={'new_parse'}
    old=plan_query('Acme 10-K cash',data,policy='conservative.v4')
    assert select_planned(data,old)[0]=={'new_parse'}
    assert select_planned(enriched,old)[0]=={'new_parse'}


def test_source_descriptor_gets_key_only_from_captured_source_url():
    import json
    from sec_agent.research_foundation.organization_source_filter import source_metadata
    b={'source':{'url':URL,'metadata':json.dumps({'entity_id':'COMPANY::acme'})},'text':''}
    assert source_metadata(b)['original_filing_key']==URL
    b['source']['url']='https://example.com/news'
    b['source']['metadata']=json.dumps({'original_filing_key':URL})
    assert 'original_filing_key' not in source_metadata(b)


def test_incomplete_parse_is_not_promoted_to_owned_lexical_population():
    from retrieval.organization_search_needs import owner_matches
    data = {'known': {'issuer_id': 'COMPANY::acme', 'original_filing_key': URL},
            'incomplete': {'issuer_id': None, 'company_name': 'Acme Inc.',
                           'original_filing_key': URL,
                           'same_document_issuer_ids': ['COMPANY::acme']}}
    enriched = with_document_issuer_aliases(data)
    assert 'same_document_issuer_ids' not in enriched['incomplete']
    assert not owner_matches(enriched['incomplete'], {'issuer_id': 'COMPANY::acme'})
