import pytest
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
