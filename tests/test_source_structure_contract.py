"""Generic structural cases: no company names or financial answer labels."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'/'engineering'))
from source_structure_contract import attach_source_structure,source_containers,reconcile_chapters
from probe_document_parsers import parse
from validate_source_structure_audit import validate


def test_short_inline_container_and_original_parent_identity():
    raw=b'<body><section><p id="title"><b>INCO</b><b>ME</b></p><p>Body.</p></section></body>'
    blocks,extra=attach_source_structure([{'kind':'text','text':'INCOME'}],raw,sec=True)
    block=blocks[0]; rows={r['id']:r for r in extra['source_containers']}
    assert rows[block['source_container_id']]['html_id']=='title'
    assert rows[block['source_parent_id']]['tag']=='section'
    assert block['source_role']=='styled_heading_candidate'
    # Bold alone is not proof of a chapter.
    assert block['kind']=='text'


def test_repeated_exact_text_never_selects_arbitrary_original():
    raw=b'<body><p><b>Note</b></p><p><b>Note</b></p></body>'
    blocks,_=attach_source_structure([{'kind':'heading','text':'Note','level':2}],raw)
    assert blocks[0]['source_location_status']=='ambiguous'
    assert len(blocks[0]['source_container_candidates'])==2
    assert 'source_container_id' not in blocks[0]


def test_referenced_short_heading_with_intervening_qualifier():
    raw=b'<a href="#section">Go</a><p id="section"><b>FULL TI</b><b>TLE</b></p><p>(Unaudited)</p><table><tr><td>0</td></tr></table>'
    blocks,_=attach_source_structure([{'kind':'text','text':'FULL TITLE'}],raw,sec=True)
    assert blocks[0]['kind']=='heading'
    assert blocks[0]['heading_basis']=='whole_container_bold_referenced_anchor'


def test_part_item_repeat_preserves_subsection_and_distinct_part_item():
    texts=['PART I','ITEM 1. Results','Details','PART I','ITEM 1','body','PART II','ITEM 1. Other']
    blocks=[{'kind':'text' if t=='body' else 'heading','text':t,'level':1 if t!='Details' else 3} for t in texts]
    tree=reconcile_chapters(blocks,True)
    assert blocks[5]['chapter_blocks']==[0,1,2]
    assert blocks[7]['chapter_blocks']==[6,7]
    assert [n['occurrence_blocks'] for n in tree[:2]]==[[0,3],[1,4]]
    assert tree[-1]['parent_id']==tree[-2]['id']


def test_table_numeric_bold_labels_not_chapters_and_layout_title_retained():
    raw=('<body><p style="font-size:10pt">'+('Body prose. '*25)+'</p>'
         '<table role="presentation"><tr><td><p style="font-size:24pt;font-weight:bold">Release title</p>'
         '<p>Revenue 100</p></td></tr></table>'
         '<table><tr><td><p style="font-size:10pt;font-weight:bold">Cash</p></td><td>100</td></tr></table></body>').encode()
    rows=source_containers(raw);tables=[r for r in rows if r['role']=='table']
    assert tables[0]['table_role']=='layout_explicit'
    assert len(tables[0]['embedded_heading_ids'])==1
    assert tables[1]['embedded_heading_ids']==[]
    assert next(r for r in rows if r['text']=='Cash')['role']=='table_label_candidate'
    assert not tables[0]['financial_semantics_inferred']


def test_web_title_uses_original_h2_without_site_suffix_or_aside_title():
    raw=b'<body><article><header><h2>Quarter results</h2></header><p>Body.</p></article><aside><h1>Other news</h1></aside></body>'
    blocks,extra=attach_source_structure([{'kind':'text','text':'Body.'}],raw,{'title':'Quarter results | Newsroom'})
    assert blocks[0]['text']=='Quarter results'
    assert extra['document_title']['status']=='verified_original_heading'
    assert not any(b['text']=='Other news' for b in blocks)


def test_unicode_container_mapping_preserves_original_characters():
    blocks,extra=attach_source_structure([{'kind':'text','text':'公司的“现金”'}],'<p>公司的“现金”</p>'.encode())
    assert blocks[0]['source_location_status']=='unique_complete_container'
    assert extra['source_containers'][0]['text']=='公司的“现金”'


def test_xml_encoding_declaration_and_comment_are_not_container_text():
    raw='<?xml version="1.0" encoding="UTF-8"?><html><body><p>公司的<!-- comment -->现金</p></body></html>'.encode()
    rows=source_containers(raw)
    assert next(r for r in rows if r['tag']=='p')['text']=='公司的现金'


def test_font_sizes_define_siblings_and_subheadings_without_staircase():
    blocks=[{'kind':'heading','text':str(i),'level':1,'source_font_size_pt':size} for i,size in enumerate([20,14,14,12,14])]
    tree=reconcile_chapters(blocks,True)
    assert [n['level'] for n in tree]==[1,2,2,3,2]


def test_navigation_reference_does_not_open_chapter():
    raw=b'<p><a href="#item">ITEM 1. Business</a></p><p>Following.</p>'
    blocks,_=attach_source_structure([{'kind':'heading','text':'ITEM 1. Business','level':1},{'kind':'text','text':'Following.'}],raw,sec=True)
    assert reconcile_chapters(blocks,True)==[]
    assert blocks[1]['chapter_ids']==[]


def test_8k_decimal_items_remain_distinct():
    blocks=[{'kind':'heading','level':1,'text':t} for t in ['Item 2.01 Acquisitions','Item 2.02 Results','Item 9.01 Exhibits']]
    assert len(reconcile_chapters(blocks,True))==3


def test_native_paragraph_keeps_word_boundaries_and_container_role(monkeypatch):
    from types import SimpleNamespace as NS,ModuleType
    def leaf(text):return NS(type=NS(name='TEXT'),children=[],text=lambda:text,path='TEXT',metadata={})
    paragraph=NS(type=NS(name='PARAGRAPH'),children=[leaf('INCOME STA'),leaf('TEMENTS')],
                 text=lambda:'INCOME STATEMENTS',path='PARAGRAPH',metadata={})
    root=NS(type=NS(name='DOCUMENT'),children=[paragraph])
    doc=NS(root=root,sections={},xbrl_facts=[],text=lambda:'INCOME STATEMENTS')
    package=ModuleType('edgar');module=ModuleType('edgar.documents')
    module.parse_html=lambda _,config:doc;module.ParserConfig=lambda **kw:NS(**kw)
    monkeypatch.setitem(sys.modules,'edgar',package);monkeypatch.setitem(sys.modules,'edgar.documents',module)
    result=parse(b'<p>INCOME STATEMENTS</p>','','edgartools')
    assert len(result['blocks'])==1
    assert result['blocks'][0]['text']=='INCOME STATEMENTS'
    assert result['blocks'][0]['native_role']=='paragraph'
    assert result['blocks'][0]['native_container_id']=='0/0'


def test_validator_rejects_chunk_gap_and_unproved_source_identity():
    doc={'blocks':[{'kind':'text','text':'AB','source_container_id':'missing'}],
         'pre_chunks':[{'kind':'prose','block':0,'start':1,'end':2}]}
    errors=validate(doc)
    assert errors['unknown_block_source']==1
    assert errors['prose_span_gap_overlap']==1
