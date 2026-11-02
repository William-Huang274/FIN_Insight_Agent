import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts/engineering'))
from structured_source_contract import describe


def test_rss_is_discovery_and_not_article_body():
    result=describe(dict(route='structured_xml',structured_xml='<rss><channel><item><title>Title</title><link>https://example.org/a</link><description>Excerpt</description></item></channel></rss>'))
    assert result['content_scope']=='feed_entries_not_full_articles'
    assert result['records'][0]['locator']=='/rss/channel/item'


def test_parallel_filing_arrays_must_match_and_unit_pointer_is_escaped():
    result=describe(dict(route='structured_json',structured_object=dict(cik=1,filings=dict(recent=dict(accessionNumber=['a'],form=[])))))
    assert not result['column_lengths_consistent']
    result=describe(dict(route='structured_json',structured_object=dict(cik=1,entityName='Entity',facts={'us-gaap':{'Rate':{'units':{'USD/shares':[{'val':1}]}}}})))
    assert result['collections'][0]['locator'].endswith('USD~1shares')
    assert result['record_count']==1
    assert not result['quality_pass']
