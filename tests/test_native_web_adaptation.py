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


def source_row(sid, text, tag='p'):
    from hashlib import sha256
    return dict(id=sid, text=text, text_sha256=sha256(text.encode()).hexdigest(), tag=tag,
                parent_id=None, table_id=None, excluded_navigation=False)


def test_restore_proved_title_and_unique_body_without_claiming_full_coverage():
    title=source_row('source:/h1','Original title','h1')
    body=source_row('source:/p','Body text.')
    previous=dict(source_containers=[title,body],document_title=dict(
        status='verified_original_heading',text='Original title',source_container_id=title['id']))
    d=adapt_web(capture('<body><p>Body text.</p></body>'),previous)
    assert d['document_title']['text']=='Original title'
    assert d['blocks'][0]['source_container_id']==body['id']
    assert not d['original_content_coverage_verified']
    assert len(d['blocks'])==1  # Metadata title is not fabricated as body text.


def test_repeated_original_text_is_ambiguous_and_cross_source_baseline_rejected():
    previous=dict(source_containers=[source_row('source:/p[1]','Repeated'),source_row('source:/p[2]','Repeated')])
    d=adapt_web(capture('<body><p>Repeated</p></body>'),previous)
    assert d['blocks'][0]['source_location_status']=='ambiguous'
    assert 'source_container_id' not in d['blocks'][0]
    previous['source_containers'][0]['id']='different:/p'
    with pytest.raises(ValueError,match='identity_mismatch'):
        adapt_web(capture('<body><p>Repeated</p></body>'),previous)
