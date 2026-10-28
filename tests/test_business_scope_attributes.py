from hashlib import sha256
import pytest
from retrieval.evidence_scope import source_scopes,plan_scope
from retrieval.evidence_scoring_view import attach_scoring_view,scoring_body
from sec_agent.research_foundation.organization_evidence_filter import OrganizationEvidenceFilter


def row(text):
    return {'node_id':'a','content':text,'content_sha256':sha256(text.encode()).hexdigest(),
        'original_source':{'source_char_start':0,'source_char_end':len(text)},
        'source_structure':{'status':'verified_original_coordinates','evidence_scopes':source_scopes(text)}}


@pytest.mark.parametrize('introduction,field,value',[
    ('The classifications of pension plan asset fair value measurements within the fair value hierarchy were:', 'asset_scope','pension_plan'),
    ('9. Nuclear Decommissioning Trust Funds','asset_scope','nuclear_decommissioning_trust'),
    ('The classifications of recurring fair value measurements within the fair value hierarchy were:', 'table_topic','fair_value_measurements'),
    ('The target asset allocations for other postretirement benefit assets were:','asset_scope','postretirement_plan'),
])
def test_explicit_table_subject_not_issuer_name_binds_asset_scope(introduction,field,value):
    body=introduction+'\n[TABLE: original]\nCash | 10\n[/TABLE]'
    found=source_scopes(body)
    assert found[0]['attributes'][field]==value
    assert found[0]['attributes']['statement_role']=='supplemental'
    assert 'reporting_entity' not in found[0]['attributes']


def test_supplemental_assets_do_not_satisfy_primary_consolidated_balance_request():
    text=('ALPHA INC.\nCONSOLIDATED BALANCE SHEETS\n[TABLE: original]\nCash | 12\n[/TABLE]\n'
          'The classifications of pension plan asset fair value measurements were:\n[TABLE: original]\nCash | 999\n[/TABLE]')
    wanted=plan_scope('Alpha consolidated balance sheet cash')
    body=scoring_body(attach_scoring_view(row(text),wanted))
    assert 'Cash | 12' in body and '999' not in body


def test_nested_known_conflict_is_filtered_before_vector_and_lexical_quota():
    from retrieval.evidence_scope import select_scoped
    scopes=[{'source_char_start':0,'source_char_end':100,'attributes':{'event_type':'earnings_release'}},
            {'source_char_start':20,'source_char_end':80,'attributes':{'reporting_entity':'Other Inc.'}}]
    wanted={'event_type':['earnings_release'],'reporting_entity':['Alpha'],'unknown_policy':'retain'}
    rows=[{'node_id':'wrong-owner','source_interval':[25,70],'evidence_scopes':scopes}]
    selected,receipt=select_scoped(rows,wanted)
    assert selected==[] and receipt['counts']['mismatch']==1


def test_arbitrary_asset_mention_does_not_classify_following_table():
    assert source_scopes('We discussed the pension plan assets with our supplier.\n[TABLE: original]\nCash | 12\n[/TABLE]')==[]


def test_exhibit_number_without_description_cannot_define_business_role():
    text='[TABLE: original]\n99.1 | Press release announcing financial results\n31.1 | Certification of Principal Executive Officer\n104 | Cover Page Interactive Data File\n[/TABLE]'
    scopes=source_scopes(text)
    assert [s['attributes']['exhibit_role'] for s in scopes]==['press_release','certification','interactive_data']
    assert scopes[0]['attributes']['event_type']=='earnings_release'
    assert not source_scopes('[TABLE: original]\n99.1 | Document\n[/TABLE]')


def test_release_announcement_carries_joint_role_in_same_interval():
    from retrieval.evidence_scope import select_scoped
    text='Item 2.02 Results of Operations\nOn August 11, 2025, Example Inc. issued a press release announcing its financial results.\nItem 9.01 Exhibits\n99.1 Press release'
    scopes=source_scopes(text)
    wanted={'event_type':['earnings_release'],'exhibit_role':['press_release'],'unknown_policy':'exclude'}
    announcement={'node_id':'a','source_interval':[text.index('On August'),text.index('Item 9.01')],'evidence_scopes':scopes}
    assert select_scoped([announcement],wanted)[0]
    unrelated={'node_id':'b','source_interval':[text.index('99.1'),len(text)],'evidence_scopes':scopes}
    assert not select_scoped([unrelated],wanted)[0]


def test_original_security_ids_have_an_explicit_scheme_and_no_coupon_year_guess():
    assert plan_scope('Find the notes with CUSIP:123456AB7')['transaction_id']==['CUSIP:123456AB7']
    assert source_scopes('CUSIP:123456AB7')[0]['attributes']=={'transaction_id':'CUSIP:123456AB7'}
    assert not source_scopes('Notes due 2030 at 5.2 percent')
    with pytest.raises(ValueError,match='original_labeled_id'):
        OrganizationEvidenceFilter(transaction_id=['notes-2030'])


@pytest.mark.parametrize('subject',[
    'the commencement of the Convertible Notes Offering',
    'the pricing of its senior unsecured notes offering',
    'the completion of an offering of convertible notes',
    'a new credit facility',
])
def test_financing_release_is_not_an_unknown_earnings_candidate(subject):
    text='The Company issued a press release announcing '+subject+'. A copy is attached as Exhibit 99.1.'
    scopes=source_scopes(text)
    assert scopes[0]['attributes']=={'exhibit_role':'press_release','event_type':'financing'}
    from retrieval.evidence_scope import select_scoped
    rows=[{'node_id':'announcement','source_interval':[0,scopes[0]['source_char_end']],'evidence_scopes':scopes}]
    assert not select_scoped(rows,{'event_type':['earnings_release'],'unknown_policy':'retain'})[0]


def test_announced_subject_is_not_the_other_release_in_later_sentence():
    text=('The Company issued a press release announcing its financial results. '
          'Another press release announced its convertible notes offering.')
    assert source_scopes(text)[0]['attributes']['event_type']=='earnings_release'
    mixed='The Company issued a press release announcing financial results and a notes offering.'
    assert 'event_type' not in source_scopes(mixed)[0]['attributes']
    generic='The Company issued a press release announcing its outlook for liquidity.'
    assert 'event_type' not in source_scopes(generic)[0]['attributes']
