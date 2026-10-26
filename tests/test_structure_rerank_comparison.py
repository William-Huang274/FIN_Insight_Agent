from hashlib import sha256
import pytest
from scripts.engineering.compare_structure_rerank import scoring_view


def fixture():
    body='(1) Estimated construction cost.'
    original={'body':body,'digest':sha256(body.encode()).hexdigest(),'embedding_input_sha256':'f'*64}
    candidate={'content':body,'content_sha256':original['digest'],'embedding_input_sha256':'f'*64,
               'embedding_context':'Original report','node_id':'same'}
    structure={'section':None,'tables':[],'footnotes':[]}
    return candidate,original,structure


def test_empty_overlay_preserves_exact_original_scoring_input():
    row,original,structure=fixture()
    result,audit=scoring_view(row,original,structure,'')
    assert result==row and not audit['changed']


def test_scoring_copy_includes_verified_table_without_mutating_original():
    row,original,structure=fixture();text='Cost (1) | USD millions\n120'
    structure.update(section={'heading':'ITEM 2. Properties'},footnotes=[{'marker':'1',
        'table':{'source_char_start':0,'source_char_end':len(text),'content_sha256':sha256(text.encode()).hexdigest()}}])
    result,audit=scoring_view(row,original,structure,text)
    assert text in result['embedding_context'] and 'Properties' in result['embedding_context']
    assert result['content']==row['content'] and row['embedding_context']=='Original report'
    assert result['embedding_input_sha256']==row['embedding_input_sha256']
    assert audit['table_windows'][0]['complete_table']
    with pytest.raises(ValueError,match='table_mismatch'):scoring_view(row,original,structure,'changed')


def test_partial_context_explicit_and_full_candidate_body_remains():
    row,original,structure=fixture();text='12345'*1000
    structure['footnotes']=[{'marker':'1','table':{'source_char_start':0,'source_char_end':len(text),
        'content_sha256':sha256(text.encode()).hexdigest()}}]
    result,audit=scoring_view(row,original,structure,text)
    assert 'Partial marked table' in result['embedding_context']
    assert not audit['table_windows'][0]['complete_table']
    assert audit['table_windows'][0]['excerpt_end']==4000
    assert result['content']==row['content']


def test_detached_mode_does_not_change_plain_prose_or_table_without_note():
    row,original,structure=fixture()
    structure.update(section={'heading':'ITEM 7. Discussion'},tables=[{'source_char_start':0}])
    result,audit=scoring_view(row,original,structure,'',context_scope='detached-footnotes')
    assert result==row and not audit['changed']


@pytest.mark.parametrize('start,end,expected',[(50,80,True),(0,80,False),(None,None,False)])
def test_detached_mode_requires_verified_note_and_missing_parent_table(start,end,expected):
    row,original,structure=fixture();text='Original construction table (1)'
    original.update(source_char_start=start,source_char_end=end)
    structure.update(section={'heading':'ITEM 2. Properties'},footnotes=[{'marker':'1',
        'table':{'source_char_start':0,'source_char_end':len(text),'content_sha256':sha256(text.encode()).hexdigest()}}])
    result,audit=scoring_view(row,original,structure,text,context_scope='detached-footnotes')
    assert audit['changed'] is expected
    assert result['content']==row['content']
    if expected:
        assert text in result['embedding_context']
    else:
        assert result==row


def test_detached_mode_still_checks_original_identity():
    row,original,structure=fixture();row['content']='altered'
    with pytest.raises(ValueError,match='original_mismatch'):
        scoring_view(row,original,structure,'',context_scope='detached-footnotes')
