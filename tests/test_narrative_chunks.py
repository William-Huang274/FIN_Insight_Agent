from retrieval.narrative_chunks import sentence_groups


def test_original_offsets_and_abbreviations_decimals():
    text = 'Acme Inc. held U.S. cash of 3.14 million.\nIt grew 2.5%. Next year differs.'
    groups = list(sentence_groups(text, 45))
    assert ''.join(x[2] for x in groups) == text
    assert groups[0][2] == 'Acme Inc. held U.S. cash of 3.14 million.'
    assert all(text[a:b] == part for a, b, part in groups)
    assert all(a == 0 or text[a-1] in '.!?。！？' for a, _, _ in groups)


def test_chinese_no_spaces_and_closing_quote():
    text = '收入增长。现金下降。”下一期不同！尾段'
    parts = list(sentence_groups(text, 18))
    assert ''.join(x[2] for x in parts) == text
    assert parts[1][2] == '现金下降。”'


def test_long_sentence_not_cut_at_word_budget():
    text = 'word ' * 1500 + 'end.'
    assert list(sentence_groups(text, 6000)) == [(0, len(text), text)]


def test_empty_and_trailing_whitespace_preserved():
    assert list(sentence_groups('')) == []
    text = 'First sentence.   Second sentence.  '
    assert ''.join(x[2] for x in sentence_groups(text, 16)) == text


def test_parser_uses_sentence_groups_without_word_boundary_fallback():
    import importlib.util
    from pathlib import Path
    path=Path(__file__).resolve().parents[1]/'scripts/engineering/parser_retrieval_units.py'
    spec=importlib.util.spec_from_file_location('units_sentence_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    text=('Evidence remains within the original complete sentence. ' * 190).strip()
    sample={'raw_sha256':'a'*64,'document_id':'d','url':'https://example.org','title':'Report'}
    units=module.build_units({'raw_sha256':'a'*64,'status':'parsed','output':{'blocks':[
        {'kind':'text','text':text}]}},sample)
    refs=[r for u in units for r in u['derived_references']]
    assert ''.join(text[r['start']:r['end']] for r in refs)==text
    assert all(r['start']==0 or text[r['start']-1]=='.' for r in refs)
    assert all(r['segmentation']=='original_paragraph_sentence_groups.v1' for r in refs)
