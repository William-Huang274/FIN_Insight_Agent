from hashlib import sha256
from retrieval.original_input_context import document_context,POLICY
from retrieval.semantic_units import split_original
from retrieval.scoped_reranking import scoring_documents
from test_semantic_units import row


def test_context_is_document_identity_not_an_inherited_answer_row():
    source=row('SIGNATURES\nSigned by the controller.')
    source['title']='Example 8-K 2026-07-31.md'
    source['original_source']['locator']='text-part:0 / chars 3958:4447'
    source['embedding_context']='Example 8-K 2026-07-31\ntext-part:0\n99.1 | Press release dated July 31'
    source['embedding_input_sha256']=sha256((source['embedding_context']+'\n'+source['content']).encode()).hexdigest()
    unit=split_original(source)[0]
    assert unit['embedding_context']=='Example 8-K 2026-07-31\ntext-part:0'
    assert unit['context_policy']==POLICY and not unit['reusable_parent_vector']
    # Existing vector/citation identities are retained on the parent.
    assert '99.1' in source['embedding_context']
    source['scoring_context_policy']=POLICY
    scoring=scoring_documents([source])[0]
    assert '99.1' not in scoring and 'Press release' not in scoring
    assert 'SIGNATURES' in scoring and 'Example 8-K' in scoring


def test_all_new_units_use_same_bounded_document_identity_not_parent_table_header():
    source=row('[TABLE: original]\nCash | 15\n[/TABLE]\nUnrelated employment contract.')
    source['embedding_context']='Cash | 99; prior table'
    units=split_original(source)
    assert len(units)>1
    assert all(u['embedding_context']=='original context' for u in units)
    assert 'Cash' not in units[-1]['embedding_context']+units[-1]['content']


def test_free_form_locator_is_not_another_semantic_preview():
    source={'title':'Example\n10-K.md','original_source':{'locator':'Cash was 500'}}
    assert document_context(source)=='Example 10-K'


def test_original_identity_only_context_survives_filename_sanitization():
    source={'title':'Example 10-Q A 2026-07-29.md',
            'original_source':{'locator':'text-part:18 / chars 0:500'},
            'embedding_context':'Example 10-Q/A 2026-07-29\ntext-part:18'}
    assert document_context(source)==source['embedding_context']
    source['embedding_context']+='\nCash 99'
    assert document_context(source)=='Example 10-Q A 2026-07-29\ntext-part:18'
