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


@pytest.mark.parametrize('separator',[' ','\n'])
@pytest.mark.parametrize('copy',[
    'A copy of the press release is attached hereto as Exhibit 99.1 and incorporated herein by reference.',
    'A copy is attached as Exhibit 99.1.',
    'Such press release has been furnished as Exhibit 99.2 hereto.',
])
def test_explicit_immediate_release_reference_keeps_event_before_scoring(separator,copy):
    from retrieval.evidence_scope import select_scoped
    announcement='The Company issued a press release announcing its convertible notes offering.'
    text=announcement+separator+copy+' Unrelated following discussion.'
    scopes=source_scopes(text)
    start=len(announcement)+len(separator);end=start+len(copy)
    assert scopes[0]['source_char_end']==end
    candidate={'node_id':'copy','source_interval':[start,end],'evidence_scopes':scopes}
    assert select_scoped([candidate],{'event_type':['earnings_release'],'unknown_policy':'retain'})[0]==[]
    view=scoring_body(attach_scoring_view(row(text),{'event_type':['earnings_release'],'unknown_policy':'retain'}))
    assert 'Exhibit 99.' not in view
    assert 'Unrelated following discussion.' in view


@pytest.mark.parametrize('intervening',[
    ' Another release concerned earnings. ',
    '\nItem 9.01 Exhibits\n',
    '\n\n',
])
def test_release_reference_does_not_jump_over_other_statements(intervening):
    announcement='The Company issued a press release announcing its notes offering.'
    text=announcement+intervening+'A copy of the press release is attached hereto as Exhibit 99.1.'
    assert source_scopes(text)[0]['source_char_end']==len(announcement)


def test_reference_does_not_change_mixed_or_unknown_announcement_identity():
    for subject in ('its liquidity outlook','financial results and a notes offering'):
        text='The Company issued a press release announcing '+subject+'. A copy is attached as Exhibit 99.1.'
        scope=source_scopes(text)[0]
        assert scope['source_char_end']==len(text)
        assert 'event_type' not in scope['attributes']


@pytest.mark.parametrize('instrument,alias',[
    ('a $900 million delayed draw term loan facility','Growth 2.5 Facility'),
    ('a revolving credit facility','Working Capital Line'),
    ('a credit agreement','New Agreement'),
    ('a senior notes offering','Offering'),
])
def test_release_and_exhibit_resolve_locally_defined_financing_objects(instrument,alias):
    text=(f'The Company entered into {instrument} (the “{alias}”).\n'
          f'On May 6, 2025, the Company issued a press release announcing the closing of the {alias}. '
          'A copy is attached as Exhibit 99.1.\n'
          f'[TABLE: original]\n99.1 | Press release relating to the {alias}\n[/TABLE]')
    found=[s for s in source_scopes(text) if s['attributes'].get('exhibit_role')=='press_release']
    assert len(found)==2 and all(s['attributes']['event_type']=='financing' for s in found)


def test_defined_financing_object_is_not_guessed_or_carried_across_documents():
    from retrieval.business_scope_attributes import financing_definitions
    release='The Company issued a press release announcing the opening of the Facility.'
    assert 'event_type' not in source_scopes(release)[0]['attributes']
    factory='The Company built a manufacturing facility (the “Facility”).\n'
    assert not financing_definitions(factory)
    assert 'event_type' not in source_scopes(factory+release)[0]['attributes']
    # A loan elsewhere in the definition sentence cannot type the named factory.
    indirect='With a term loan, it built a manufacturing facility (the “Facility”).\n'
    assert not financing_definitions(indirect)
    ambiguous='It signed a credit agreement (the “Facility”).\n'+factory
    assert not financing_definitions(ambiguous)


def test_defined_object_does_not_match_a_longer_alias_or_override_mixed_event():
    prefix='It entered a term loan facility (the “Line 1”).\n'
    longer=prefix+'It issued a press release announcing the closing of Line 10.'
    assert 'event_type' not in source_scopes(longer)[0]['attributes']
    mixed=prefix+'It issued a press release announcing financial results and the closing of Line 1.'
    assert 'event_type' not in source_scopes(mixed)[0]['attributes']


def test_table_subject_survives_complete_original_page_furniture():
    title='Recurring Non-Derivative Fair Value Measurements\n–\nAlpha financial assets by hierarchy level are as follows:'
    furniture='\n87\nTable of Contents\nALPHA INC. AND BETA COMPANY\nNOTES TO CONSOLIDATED FINANCIAL STATEMENTS (Continued)\n'
    body=title+furniture+'[TABLE: original]\nCash equivalents | 99\n[/TABLE]'
    scopes=source_scopes(body)
    assert scopes[0]['attributes']=={'table_topic':'fair_value_measurements','statement_role':'supplemental'}
    assert scopes[0]['source_char_start']==0 and scopes[0]['source_char_end']==len(body)
    wanted={'statement_role':['primary'],'unknown_policy':'retain'}
    assert '99' not in scoring_body(attach_scoring_view(row(body+'\nUnclassified text'),wanted))


def test_table_subject_is_not_carried_past_prose_or_another_table():
    heading='Fair Value Measurements\n–\nThe values are as follows:\n'
    for separator in ('Unrelated discussion.\n','[TABLE: original]\nValue | 7\n[/TABLE]\n'):
        body=heading+separator+'[TABLE: original]\nCash | 99\n[/TABLE]'
        scopes=source_scopes(body)
        assert not any(s['source_char_end']==len(body) for s in scopes)


def test_explicit_pension_introduction_with_as_follows_is_supplemental():
    body=('Pension Plan Assets, Benefit Obligations and Funded Status – '
          'The changes in assets, benefit obligations and funded status of the pension plan are as follows:\n'
          '[TABLE: original]\nCash | 999\n[/TABLE]')
    assert source_scopes(body)[0]['attributes']['asset_scope']=='pension_plan'
