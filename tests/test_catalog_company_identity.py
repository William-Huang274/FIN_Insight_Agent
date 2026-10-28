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
