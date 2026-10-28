from retrieval.same_original_metadata import resolve,DERIVED

URL='https://www.sec.gov/Archives/edgar/data/123/000000012326000001/report.htm'


def test_exact_document_can_fill_missing_form_without_issuer_or_period_inference():
    rows={'cover':{'original_filing_key':URL,'form':'10-K','period_end':'2025-12-31'},
          'excerpt':{'original_filing_key':URL,'form':None,'period_end':None},
          'annex':{'original_filing_key':URL.replace('report.htm','ex99.htm'),'form':None}}
    result=resolve(rows)
    assert result['excerpt']['form']=='10-K'
    assert result['excerpt']['period_end']=='2025-12-31'
    assert result['excerpt'][DERIVED]['form']['source_documents']==['cover']
    assert result['annex']['form'] is None and rows['excerpt']['form'] is None
    assert 'issuer_id' not in result['excerpt']


def test_conflicting_metadata_or_original_cover_blocks_cross_parse_resolution():
    rows={'a':{'original_filing_key':URL,'form':'10-K'},
          'b':{'original_filing_key':URL,'form':'10-Q'},
          'c':{'original_filing_key':URL,'form':None}}
    result=resolve(rows)
    assert all(v['form'] is None and v[DERIVED]['form']['state']=='conflict' for v in result.values())
    rows['b']={'original_filing_key':URL,'form':None,'metadata_conflicts':['form']}
    assert all(v['form'] is None for v in resolve(rows).values())


def test_discovery_metadata_foreign_urls_and_absent_authorized_cover_do_not_enrich():
    rows={'discovery':{'original_filing_key':URL,'form':'10-K','evidence_role':'discovery_metadata_only'},
          'original':{'original_filing_key':URL,'form':None},
          'foreign':{'original_filing_key':URL.replace('www.sec.gov','example.test'),'form':'10-K'}}
    result=resolve(rows)
    assert result['original']['form'] is None and DERIVED not in result['original']


def test_explicit_and_automatic_filters_share_original_document_fields():
    from sec_agent.research_foundation.organization_source_filter import select_documents,OrganizationSourceFilter
    from sec_agent.research_foundation.organization_query_plan import document_constraint_states
    from retrieval.rerank_document_context import with_document_context
    rows={'cover':{'original_filing_key':URL,'form':'10-K'},
          'excerpt':{'original_filing_key':URL,'form':None}}
    found,_=select_documents(rows,OrganizationSourceFilter(form='10-K'))
    assert found=={'cover','excerpt'}
    assert document_constraint_states(rows,{'policy':'conservative.v5','constraint':{'form':'10-Q'}})=={
        'cover':'mismatch','excerpt':'mismatch'}
    assert with_document_context([{'parent_document_id':'excerpt'}],rows)[0]['rerank_document_metadata']['form']=='10-K'
