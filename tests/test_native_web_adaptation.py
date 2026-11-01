import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts/engineering'))
from native_web_adaptation import adapt_web


def capture(xml):
    return {'source_sha256':'source','native':{'document':{'title':'Metadata title','body':{'$xml':xml},'commentsbody':{'$xml':'<p>comment</p>'}}}}


def test_native_headings_mixed_content_and_list_tails_are_retained():
    d=adapt_web(capture('<body>lead<head rend="h1">Actual title</head><p>A<ref target="url">link</ref>tail</p><list><item>parent<list><item>nested</item></list>end</item></list></body>'))
    assert ''.join(b['text'] for b in d['blocks'])=='leadActual titleAlinktailparentnestedend'
    assert d['chapter_tree'][0]['title']=='Actual title'
    assert d['document_title']['status']=='metadata_only_not_verified_original_heading'
    assert d['native_comments']['$xml']=='<p>comment</p>'
    assert not d['original_content_coverage_verified']
    assert all(not b.get('source_container_id') for b in d['blocks'])


def test_table_attributes_and_nested_xml_retained_without_promoting_numeric_facts():
    d=adapt_web(capture('<body><table><row><cell role="head" colspan="2">Unit</cell></row><row><cell>Value</cell><cell>3</cell></row></table></body>'))
    b=d['blocks'][0]
    assert b['kind']=='table'
    assert b['headers'][0][0]['colspan']=='2'
    assert b['rows'][0][1]['text']=='3'
    assert 'original_table_cells' in b['structure_gap']
    assert d['native_text_partition_complete']


def test_empty_body_is_execution_problem_not_successful_article():
    with pytest.raises(ValueError,match='body_unavailable'):
        adapt_web({'native':{'document':None}})
