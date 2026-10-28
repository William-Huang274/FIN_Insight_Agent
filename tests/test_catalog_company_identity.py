from retrieval.catalog_company_identity import cover_names, audit_catalog
from sec_agent.research_foundation.organization_query_plan import plan_query


def test_all_catalog_names_receive_whitespace_punctuation_and_legal_suffix_compatibility():
    metadata={str(i):{'issuer_id':f'COMPANY::{i}','company_name':name} for i,name in enumerate(
        ['Delta Harbor, Inc.','Western-Circuit Corporation','星河科技'])}
    for i,query in enumerate(['DeltaHarbor revenue','Western Circuit debt','星河科技现金']):
        plan=plan_query(query,metadata,policy='conservative.v5')
        assert plan['constraint']['issuer_id']==f'COMPANY::{i}'


def test_homonyms_are_not_globally_merged():
    metadata={'a':{'issuer_id':'A','company_name':'Delta Harbor Inc.'},
              'b':{'issuer_id':'B','company_name':'DeltaHarbor Corporation'}}
    assert audit_catalog(metadata)['alias_collisions']
    assert 'issuer_id' not in plan_query('Delta Harbor revenue',metadata,policy='conservative.v5')['constraint']


def test_registrant_names_require_original_caption_not_body_or_title_guess():
    assert cover_names('Delta Harbor Inc.\n(Exact name of registrant as specified in its charter)')==['Delta Harbor Inc.']
    assert cover_names('Our customer is Delta Harbor Inc.')==[]


def test_name_only_catalog_rows_do_not_create_a_second_phantom_company():
    metadata={'a':{'issuer_id':'COMPANY::delta_harbor'}, 'b':{'company_name':'Delta Harbor'}}
    plan=plan_query('Delta Harbor cash',metadata,policy='conservative.v5')
    assert plan['constraint']['issuer_id']=='COMPANY::delta_harbor'
    assert plan['constraint']['company_names']==['Delta Harbor']
    assert not audit_catalog(metadata)['alias_collisions']


def test_line_wrapped_legal_word_is_not_registered_as_a_company_alias():
    assert cover_names('DELTA CORP\nORATION\n(Exact name of registrant as specified in its charter)')==['DELTA CORPORATION']
    assert cover_names('OTHER CUSTOMER\nALPHA INC.\n(Exact name of registrant as specified in its charter)')==['ALPHA INC.']


def test_name_only_legal_suffix_and_issuer_tail_share_one_lookup_identity():
    metadata={'a':{'issuer_id':'DELTA'}, 'b':{'company_name':'Delta Corp'}}
    plan=plan_query('Delta consolidated balance sheet',metadata,policy='conservative.v5')
    assert plan['constraint']['issuer_id']=='DELTA'
    assert plan['constraint']['company_names']==['Delta Corp']
    assert not audit_catalog(metadata)['alias_collisions']


def test_registrant_table_preserves_joint_names_without_assigning_unique_owner():
    text='[TABLE: original]\nFile number | Exact name of registrant as specified in its charter | Tax number\n1-100 | ALPHA INC. | 00-000\n1-200 | BETA COMPANY | 00-001\n[/TABLE]'
    assert cover_names(text)==['ALPHA INC.','BETA COMPANY']
    assert cover_names(text.replace('1-100 | ALPHA INC. | 00-000','ALPHA INC. | 00-000'))==[]


def test_consecutive_joint_legal_names_under_one_caption_are_not_last_name_only():
    from sec_agent.research_foundation.organization_source_filter import source_metadata
    import json
    text='001-123\n(ALPHA INC.)\n000-456\n(ALPHA L.P.)\nALPHA INC.\nALPHA L.P.\n(Exact name of registrant as specified in its charter)'
    assert cover_names(text)==['ALPHA INC.','ALPHA L.P.']
    row=source_metadata({'text':text,'source':{'metadata':json.dumps({'entity_id':'alpha','cik':'123'}),
        'url':'https://www.sec.gov/Archives/edgar/data/123/000000012326000001/report.htm'}})
    assert row['company_name_resolution']=='joint_registrants_not_a_unique_owner'
    assert row['joint_registrant_names']==['ALPHA INC.','ALPHA L.P.']
    assert 'verified_company_names' not in row and 'fact_entity_identifiers' not in row
    from retrieval.catalog_company_identity import aliases_for,verified_issuer_groups
    assert 'ALPHA L.P.' in aliases_for(row)
    assert verified_issuer_groups({'d':row})==[]


def test_joint_table_recognizes_partnership_without_guessing_merged_cells():
    text='[TABLE: original]\nFile | Exact name of registrants as specified in their charter | Tax\n1 | ALPHA INC. | 00\n2 | ALPHA L.P. | 01\n[/TABLE]'
    assert cover_names(text)==['ALPHA INC.','ALPHA L.P.']


def test_joint_filing_lookup_does_not_make_all_registrants_equivalent_fact_owners():
    from retrieval.evidence_scope import plan_scope
    from retrieval.organization_search_needs import compile_needs
    from sec_agent.research_foundation.organization_source_filter import select_documents,OrganizationSourceFilter
    metadata={'joint':{'issuer_id':'alpha','joint_registrant_names':['ALPHA INC.','ALPHA L.P.'],
                       'company_name_resolution':'joint_registrants_not_a_unique_owner'},
              'single':{'issuer_id':'alpha','verified_company_names':['ALPHA INC.'],
                        'fact_entity_identifiers':[{'scheme':'http://www.sec.gov/CIK','identifier':'123'}]}}
    for query,expected in [('Alpha consolidated balance sheet cash equivalents',[]),
                           ('Alpha Inc. consolidated balance sheet cash equivalents',['ALPHA INC.']),
                           ('Alpha L.P. consolidated balance sheet cash equivalents',['ALPHA L.P.'])]:
        plan=plan_query(query,metadata,policy='conservative.v5')
        assert plan['joint_reporting_entity_targets']['alpha']==expected
        assert 'alpha' not in plan['fact_entity_by_issuer']
        assert plan_scope(query,plan).get('reporting_entity',[])==expected
        assert all(n['owner']['company_names']==expected for n in compile_needs(query,plan)['needs'])
    assert 'joint' in select_documents(metadata,OrganizationSourceFilter(company_name='ALPHA L.P.'))[0]


def test_joint_targets_require_complete_name_and_preserve_multiple_explicit_owners():
    from retrieval.catalog_company_identity import joint_reporting_targets
    rows={'d':{'issuer_id':'p','joint_registrant_names':['NORTH INC.','NORTH L.P.']}}
    assert joint_reporting_targets('North cash',rows)=={'p':[]}
    assert joint_reporting_targets('Compare NORTH INC. with NORTH L.P. cash',rows)=={'p':['NORTH INC.','NORTH L.P.']}
    assert joint_reporting_targets('NORTH INCORPORATEDXYZ cash',rows)=={'p':[]}


def test_same_catalog_issuer_joint_comparison_has_separate_coverage_needs():
    from retrieval.organization_search_needs import compile_needs
    rows={'d':{'issuer_id':'p','joint_registrant_names':['NORTH INC.','NORTH L.P.']}}
    query='Compare NORTH INC. cash and cash equivalents and NORTH L.P. revenue'
    needs=compile_needs(query,plan_query(query,rows,policy='conservative.v5'))['needs']
    recognized={(n['concept'],tuple(n['owner']['company_names'])) for n in needs if n.get('concept')}
    assert recognized=={('cash_equivalents',('NORTH INC.',)),('revenue',('NORTH L.P.',))}
    query='Compare NORTH INC. and NORTH L.P. cash and cash equivalents'
    needs=compile_needs(query,plan_query(query,rows,policy='conservative.v5'))['needs']
    assert {tuple(n['owner']['company_names']) for n in needs if n.get('concept')=='cash_equivalents'}=={('NORTH INC.',),('NORTH L.P.',)}


def test_joint_rerank_context_never_labels_last_cover_name_as_unique_issuer():
    from retrieval.rerank_document_context import with_document_context,document_context_text
    source={'issuer_id':'alpha','company_name':'ALPHA L.P.',
            'joint_registrant_names':['ALPHA INC.','ALPHA L.P.'],'form':'10-Q'}
    context=with_document_context([{'parent_document_id':'d'}],{'d':source})[0]['rerank_document_metadata']
    assert 'issuer' not in context
    assert context['joint_registrants']==['ALPHA INC.','ALPHA L.P.']
    assert 'NOT interchangeable statement owners' in document_context_text(context)


def test_same_original_parse_ids_use_name_scope_without_merging_other_documents():
    from sec_agent.research_foundation.organization_query_plan import select_planned
    url='https://www.sec.gov/Archives/edgar/data/123/000000012324000001/report.htm'
    metadata={'a':{'issuer_id':'A','verified_company_names':['Delta Corporation'],'original_filing_key':url},
              'b':{'issuer_id':'B','verified_company_names':['Delta Corporation'],'original_filing_key':url},
              'c':{'issuer_id':'B','company_name':'Other Company'}}
    plan=plan_query('Delta revenue',metadata,policy='conservative.v5')
    assert 'issuer_id' not in plan['constraint']
    selected,_=select_planned(metadata,plan)
    assert selected=={'a','b'}
    assert metadata['c']['issuer_id']=='B'


def test_original_cover_does_not_keep_an_unrelated_legacy_id_alias():
    from retrieval.catalog_company_identity import aliases_for
    row={'issuer_id':'COMPANY::wrong_short','verified_company_names':['Northern Circuits Inc.']}
    assert 'wrong short' not in aliases_for(row)
    assert 'issuer_id' not in plan_query('wrong short revenue',{'d':row},policy='conservative.v5')['constraint']
    assert plan_query('Northern Circuits revenue',{'d':row},policy='conservative.v5')['constraint']['issuer_id']==row['issuer_id']


def test_verified_same_cik_names_expand_lookup_across_parse_ids_not_homonyms():
    from retrieval.catalog_company_identity import verified_issuer_groups
    from sec_agent.research_foundation.organization_query_plan import select_planned
    def row(issuer,cik):return {'issuer_id':issuer,'verified_company_names':['Northern Circuits Inc.'],
        'fact_entity_identifiers':[{'scheme':'http://www.sec.gov/CIK','identifier':cik}]}
    metadata={'a':row('A','123'),'b':row('B','000123')}
    assert len(verified_issuer_groups(metadata))==1
    plan=plan_query('Northern Circuits revenue',metadata,policy='conservative.v5')
    assert {v['issuer_id'] for v in plan['constraint']['issuer_union']}=={'A','B'}
    assert select_planned(metadata,plan)[0]=={'a','b'}
    metadata['c']=row('B','456')
    assert verified_issuer_groups(metadata)==[]
    assert 'issuer_union' not in plan_query('Northern Circuits revenue',metadata,policy='conservative.v5')['constraint']


def test_url_requires_unique_cover_and_conflicting_cik_never_establishes_alias():
    from retrieval.catalog_company_identity import with_original_registrant_identity,verified_issuer_groups
    url='https://www.sec.gov/Archives/edgar/data/123/000000012324000001/report.htm'
    assert 'fact_entity_identifiers' not in with_original_registrant_identity({'original_filing_key':url})
    row={'original_filing_key':url,'verified_company_names':['Northern Circuits Inc.'],'issuer_id':'A'}
    assert with_original_registrant_identity(row)['fact_entity_identifiers'][0]['identifier']=='123'
    conflict=with_original_registrant_identity({**row,'fact_entity_identifiers':[
        {'scheme':'http://www.sec.gov/CIK','identifier':'456'}]})
    assert conflict['company_name_resolution']=='original_cover_url_cik_conflict'
    assert verified_issuer_groups({'a':conflict,'b':{**conflict,'issuer_id':'B'}})==[]
