from ingestion.pdf_layout import _compile_text_blocks


def line(index,text,y,x=20):
    return {'line_index':index,'text':text,'bbox':[x,y,x+100,y+10]}


def test_lower_page_text_and_single_characters_are_retained():
    lines=[line(1,'Upper paragraph',100),line(2,'Lower paragraph',700),line(3,'0',730)]
    blocks=_compile_text_blocks(lines,page_width=600,table_regions=[],footnotes=[])
    assert sorted(i for b in blocks for i in b['source_line_indices'])==[1,2,3]
    assert 'Lower paragraph' in ' '.join(b['text'] for b in blocks)


def test_table_and_footnote_lines_stay_in_their_existing_representations():
    lines=[line(1,'Table value',100),line(2,'Footnote',400),line(3,'Other text',750)]
    blocks=_compile_text_blocks(lines,page_width=600,
        table_regions=[{'bbox':[0,90,200,120]}],footnotes=[{'bbox':[0,390,200,420]}])
    assert [i for b in blocks for i in b['source_line_indices']]==[3]


def test_lower_revision_context_and_parser_revision_remain_visible():
    from ingestion.pdf_layout import public_pdf_layout_projection
    blocks=_compile_text_blocks([line(1,'Comparative figures were restated.',750)],
                                 page_width=600,table_regions=[],footnotes=[])
    assert blocks[0]['block_role']=='revision_or_restatement_context'
    assert public_pdf_layout_projection({'parser_revision':'test_revision'})['parser_revision']=='test_revision'
