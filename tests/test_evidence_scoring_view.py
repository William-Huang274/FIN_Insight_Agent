from hashlib import sha256
import pytest
from retrieval.evidence_scope import source_scopes
from retrieval.evidence_scoring_view import attach_scoring_view,scoring_body


def mixed():
    body=('ALPHA INC.\nCONSOLIDATED BALANCE SHEETS\n[TABLE: original]\nCash | 10\n[/TABLE]\n'
          'BETA COMPANY\nCONSOLIDATED BALANCE SHEETS\n[TABLE: original]\nCash | 9000\n[/TABLE]')
    return {'node_id':'mixed','content':body,'content_sha256':sha256(body.encode()).hexdigest(),
        'original_source':{'source_char_start':0,'source_char_end':len(body)},
        'source_structure':{'status':'verified_original_coordinates','evidence_scopes':source_scopes(body)}}


@pytest.mark.parametrize('unknown_policy',['retain','exclude'])
def test_one_matching_table_cannot_launder_another_table_into_scoring(unknown_policy):
    row=mixed();view=attach_scoring_view(row,{'reporting_entity':['Alpha'],
        'statement_type':['balance_sheet'],'unknown_policy':unknown_policy})
    text=scoring_body(view)
    assert 'Cash | 10' in text and '9000' not in text
    assert row['content']==view['content'] and row['content_sha256']==view['content_sha256']
    assert 'scoring_view' not in row


def test_view_is_verified_again_before_use_and_empty_scope_does_not_score():
    row=mixed();view=attach_scoring_view(row,{'reporting_entity':['Alpha']})
    view['scoring_view']['spans'][0]['source_char_end']+=1
    with pytest.raises(ValueError,match='scope_view_span_mismatch'):scoring_body(view)
    with pytest.raises(ValueError,match='no_eligible'):
        attach_scoring_view(row,{'reporting_entity':['Other']})


def test_broad_event_region_cannot_override_conflicting_nested_table_owner():
    row=mixed()
    row['source_structure']['evidence_scopes'].append({'source_char_start':0,
        'source_char_end':len(row['content']),'content_sha256':row['content_sha256'],
        'attributes':{'event_type':'earnings_release'},'basis':'explicit_sec_item_2.02'})
    view=attach_scoring_view(row,{'reporting_entity':['Alpha'],'event_type':['earnings_release'],
        'unknown_policy':'retain'})
    assert 'Cash | 10' in scoring_body(view)
    assert '9000' not in scoring_body(view)
