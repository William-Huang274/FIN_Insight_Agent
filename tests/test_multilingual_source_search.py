import pytest
from hashlib import sha256
from retrieval.text import tokenize
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest, navigate_source_nodes


def test_chinese_query_is_not_empty_and_bm25_finds_chinese_source():
    request=SourceDocumentRequest(operation='search',query='股票薪酬费用的现金流量表调节项目')
    rows=[{'node_id':str(i),'parent_document_id':'doc','node_kind':'text','content':text,'stable_url':'https://example.org/report'} for i,text in enumerate([
        '股票薪酬费用作为非现金项目，在现金流量表经营现金流部分调节。', '产品交付与供应合同。', '董事会任免与会议记录。'])]
    result=navigate_source_nodes(rows,request,snapshot='fixture')
    assert result.items[0]['node_id']=='0'
    assert tokenize('AI/ML R&D isn\'t A&B -- 2027!')==['ai/ml','r&d',"isn't",'a&b','2027']


def test_punctuation_only_query_is_still_rejected():
    with pytest.raises(ValueError,match='source_search_query_required'):
        SourceDocumentRequest(operation='search',query='，。！？')


@pytest.mark.parametrize('body', ['[]', '{}', '— … 。', ''])
def test_source_without_lexical_terms_has_no_keyword_matches(body):
    rows=[{'node_id':'empty','parent_document_id':'doc','node_kind':'text',
           'content':body,'stable_url':'https://example.org/api'}]
    result=navigate_source_nodes(rows,SourceDocumentRequest(operation='search',query='model'),
                                 snapshot='empty-response',hybrid_enabled=False)
    assert result.items == () and result.total_matches == 0
    assert 'no lexical terms' in result.notice


def test_empty_lexical_corpus_still_reaches_scoped_hybrid_and_exact_readback():
    rows=[{'node_id':'empty','parent_document_id':'doc','node_kind':'text',
           'content':'[]','content_sha256':sha256(b'[]').hexdigest(),'stable_url':'https://example.org/api'},
          {'node_id':'foreign','parent_document_id':'other','node_kind':'text',
           'content':'model catalogue','stable_url':'https://example.org/other'}]
    observed=[]
    def ranker(eligible, query, snapshot, lexical):
        observed.append((eligible,query,snapshot,lexical))
        return eligible, {'cache_hit':True,'provider_calls':0}
    result=navigate_source_nodes(rows,SourceDocumentRequest(operation='search',query='model',document_id='doc'),
                                 snapshot='empty-response',hybrid_enabled=False,ranker=ranker)
    assert observed == [([rows[0]],'model','empty-response',[])]
    assert len(result.items)==1 and result.items[0]['node_id']=='empty'
    assert not result.items[0]['writer_citable']
    assert 'no lexical terms' in result.notice
    read=navigate_source_nodes(rows,SourceDocumentRequest(**result.items[0]['readback']),snapshot='empty-response')
    assert read.items[0]['passage']=='[]' and not read.items[0]['numeric_fact_authority']


def test_empty_nodes_do_not_hide_keyword_matches_in_mixed_corpus():
    rows=[{'node_id':str(i),'parent_document_id':'doc','node_kind':'text','content':text,
           'stable_url':'https://example.org/report'} for i,text in enumerate(['[]','cash flow','revenue'])]
    result=navigate_source_nodes(rows,SourceDocumentRequest(operation='search',query='cash'),
                                 snapshot='mixed',hybrid_enabled=False)
    assert [item['node_id'] for item in result.items]==['1']
