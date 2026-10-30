import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'/'engineering'))
from refine_document_chapters import join_heading_fragments,table_heading,refine
from finalize_structure_prechunks import classify


def heading_source(text):
    return {'id':'original:p','role':'styled_heading_candidate','text':text,'heading_eligible':True,
            'parent_id':'original:body','font_size_pt':10}


def test_native_heading_split_inside_one_parent_is_restored():
    source=heading_source('Complete Title')
    blocks=[{'kind':'heading','text':'Complete Ti','native_role':'heading','native_parent_id':'p'},
            {'kind':'text','text':'tle','native_role':'text','native_parent_id':'p'}]
    result,receipts=join_heading_fragments(blocks,[source])
    assert len(result)==1 and result[0]['text']=='Complete Title'
    assert receipts[0]['input_blocks']==[0,1]


def test_distinct_paragraphs_and_ambiguous_originals_are_never_joined():
    source=heading_source('Complete Title')
    blocks=[{'kind':'heading','text':'Complete Ti','native_role':'heading','native_parent_id':'p'},
            {'kind':'text','text':'tle','native_role':'text','native_parent_id':'q'}]
    assert not join_heading_fragments(blocks,[source])[1]
    blocks[1]['native_parent_id']='p'
    assert not join_heading_fragments(blocks,[source,{**source,'id':'other:p'}])[1]


def table(*rows):
    return {'kind':'table','text':' | '.join(c for r in rows for c in r),
            'headers':[[{'text':c} for c in r] for r in rows],'rows':[],'footer':[]}


def test_single_row_item_heading_is_not_confused_with_toc_or_financial_rows():
    source={'text':'ITEM 2.Results','id':'original:table'}
    assert table_heading(table(['ITEM 2.','Results']),source)=='ITEM 2. Results'
    assert table_heading(table(['ITEM 2.','Results','42']),source) is None
    assert table_heading(table(['ITEM 2.','Results'],['ITEM 3.','Risks']),source) is None
    assert table_heading(table(['Revenue','100']),{'text':'Revenue100'}) is None
    assert table_heading(table(['ITEM 2.','Revenue','$100.00']),{'text':'ITEM 2.Revenue$100.00'}) is None
    assert table_heading(table(['ITEM 2.','Results']),{**source,'internal_link_only':True}) is None


def test_table_heading_opens_item_scope_without_removing_physical_cells():
    physical=table(['ITEM 1.','Financial Statements']);physical['source_container_id']='original:table'
    doc={'route':'edgartools','blocks':[{'kind':'heading','level':1,'text':'PART I'},physical,
          {'kind':'text','text':'Following complete sentence.'}],
         'source_containers':[{'id':'original:table','role':'table','text':'ITEM 1.Financial Statements'}],
         'issues':[]}
    result=refine(doc)
    assert result['blocks'][1]['headers']==physical['headers']
    assert result['blocks'][1]['kind']=='table'
    assert result['blocks'][2]['chapter_blocks']==[0,1]
    assert result['chapter_tree'][1]['parent_id']=='chapter:0'
    assert result['pre_chunks'][0]['representation']=='section_heading_layout_not_data_table'
    assert classify(result)['records'][0]['role']=='retained_structure'


def test_native_title_support_is_not_just_matching_an_item_number():
    doc={'route':'edgartools','blocks':[
        {'kind':'text','text':'Item 3.02 Unregistered Sales of Equity Securities','source_container_id':'p1'},
        {'kind':'text','text':'Item 3.02 of this report contains further details.','source_container_id':'p2'}],
        'source_containers':[{'id':sid,'text':'','role':'paragraph'} for sid in ['p1','p2']],
        'parser_sections':{'item_302':{'title':'Item 3.02 - Unregistered Sales of Equity'}},'issues':[]}
    result=refine(doc)
    assert result['blocks'][0]['kind']=='heading'
    assert result['blocks'][1]['kind']=='text'


def test_repeated_multi_item_running_header_does_not_override_current_item():
    doc={'route':'edgartools','blocks':[
        {'kind':'heading','text':t,'level':1} for t in ['PART I','Item 3, 4','Item 3. Risks','Item 3, 4','Item 4. Controls']],
         'issues':[]}
    result=refine(doc)
    assert [n['title'] for n in result['chapter_tree']]==['PART I','Item 3. Risks','Item 4. Controls']
    assert result['blocks'][3]['chapter_blocks']==[0,2]


def test_complete_bold_sec_label_is_heading_even_before_a_short_body():
    doc={'route':'edgartools','blocks':[{'kind':'text','text':'Item 3. Risk Disclosures','source_container_id':'p'}],
         'source_containers':[{'id':'p','role':'styled_heading_candidate','text':'Item 3. Risk Disclosures'}],'issues':[]}
    assert refine(doc)['blocks'][0]['kind']=='heading'


def test_combined_running_label_is_not_selected_over_complete_original_title():
    doc={'route':'edgartools','blocks':[
        {'kind':'heading','level':1,'text':t,'source_container_id':str(i)} for i,t in enumerate(['PART I','Item 3, 4','Item 3. Risks'])],
        'source_containers':[],'issues':[]}
    result=refine(doc)
    assert result['chapter_tree'][1]['title']=='Item 3. Risks'
