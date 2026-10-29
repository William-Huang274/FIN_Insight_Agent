import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('parser_retrieval_units', Path(__file__).resolve().parents[1] / 'scripts/engineering/parser_retrieval_units.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_slices_cover_text_without_word_cuts():
    text = 'alpha beta supercalifragilistic gamma delta'
    parts = list(module.split_text(text, 10))
    assert ''.join(p[2] for p in parts) == text
    assert all(a == 0 or text[a].isspace() or text[a-1].isspace() for a, _, _ in parts)


def test_table_does_not_merge_next_table_or_drop_headers():
    def table(value):
        return {'kind': 'table', 'text': value, 'headers': [[{'text': 'USD millions'}]],
                'rows': [[{'text': 'Cash'}, {'text': value}]], 'footer': [], 'caption': ''}
    sample = {'raw_sha256': 'a'*64, 'document_id': 'd1', 'url': 'https://example.org', 'title': 'Annual report'}
    parsed = {'raw_sha256': 'a'*64, 'status': 'parsed', 'output': {'blocks': [table('100'), table('200')]}}
    units = module.build_units(parsed, sample)
    assert len(units) == 2
    assert all('USD millions' in u['embedding_input'] for u in units)
    assert all('USD millions' in u['lexical_input'] for u in units)
    assert all('Annual report' not in u['lexical_input'] for u in units)
    assert '200' not in units[0]['body']
    assert units[0]['derived_references'][0]['block'] != units[1]['derived_references'][0]['block']


def test_plain_text_statement_caption_preserves_source_prelude():
    sample = {'raw_sha256': 'a'*64, 'document_id': 'd1', 'url': 'https://example.org', 'title': 'Annual report'}
    blocks = [{'kind': 'heading', 'text': 'February 12, 2024'},
              {'kind': 'text', 'text': 'Example Incorporated'},
              {'kind': 'text', 'text': 'Consolidated Balance Sheets'},
              {'kind': 'text', 'text': '(In thousands, except par value)'},
              {'kind': 'table', 'text': 'Cash 100', 'headers': [],
               'rows': [[{'text': 'Cash'}, {'text': '100'}]], 'footer': []}]
    units = module.build_units({'raw_sha256': 'a'*64, 'status': 'parsed', 'output': {'blocks': blocks}}, sample)
    table = next(u for u in units if u['kind'] == 'table')
    assert 'Consolidated Balance Sheets' in table['context']
    assert 'In thousands' in table['context']
    assert 'Example Incorporated' in table['context']
    assert 'Example Incorporated' not in table['lexical_input']
    assert len(table['derived_references'][0]['caption_refs']) == 4
    assert all(r['role'] == 'adjacent_source_context_not_inferred_fact' for r in table['derived_references'][0]['caption_refs'])


def test_restore_requires_complete_original_paragraph_not_word_guess():
    path = Path(__file__).resolve().parents[1] / 'scripts/engineering/restore_parser_paragraphs.py'
    spec = importlib.util.spec_from_file_location('restore', path)
    repair = importlib.util.module_from_spec(spec); spec.loader.exec_module(repair)
    raw = b'<div>As of the reporting date we <b>h</b>ad no debt (i<span>n millions).</span></div>'
    blocks = [{'kind': 'heading', 'text': 'As of the reporting date we h'},
              {'kind': 'text', 'text': 'ad no debt (i'}, {'kind': 'text', 'text': 'n millions).'}]
    restored, receipts = repair.restore(blocks, raw)
    assert len(restored) == len(receipts) == 1
    assert restored[0]['text'] == 'As of the reporting date we had no debt (in millions).'
    blocks[1]['text'] = 'ad much debt (i'
    restored, receipts = repair.restore(blocks, raw)
    assert not receipts
    assert len(restored) == 3


def test_short_heading_requires_unique_complete_original_paragraph():
    path = Path(__file__).resolve().parents[1] / 'scripts/engineering/restore_parser_paragraphs.py'
    spec = importlib.util.spec_from_file_location('restore', path)
    repair = importlib.util.module_from_spec(spec); spec.loader.exec_module(repair)
    raw = b'<p>At <b>December 31, 2024</b>, the company held cash.</p>'
    blocks = [{'kind': 'heading', 'text': 'At '},
              {'kind': 'heading', 'text': 'December 31, 2024'},
              {'kind': 'text', 'text': ', the company held cash.'}]
    restored, receipts = repair.restore(blocks, raw)
    assert len(restored) == len(receipts) == 1
    assert restored[0]['text'] == 'At December 31, 2024, the company held cash.'
    assert receipts[0]['parser_block_start'] == 0
    assert receipts[0]['parser_block_end'] == 3
    assert not repair.restore(blocks, raw + raw)[1]
    assert not repair.restore(blocks[:-1], raw)[1]


def test_empty_layout_table_excluded_but_zero_retained():
    sample = {'raw_sha256': 'a'*64, 'document_id': 'd1', 'url': 'https://example.org', 'title': 'Report'}
    blocks = [{'kind': 'table', 'text': t, 'rows': [[{'text': t}]]} for t in [' ', '—', '0', '收入']]
    units = module.build_units({'raw_sha256': 'a'*64, 'status': 'parsed', 'output': {'blocks': blocks}}, sample)
    assert [u['body'] for u in units] == ['—', '0', '收入']


def test_complete_long_table_introduction_is_not_silently_discarded():
    sample = {'raw_sha256': 'a'*64, 'document_id': 'd1', 'url': 'https://example.org', 'title': 'Report'}
    intro = 'Prior explanatory sentence. ' * 30 + 'Amounts were as follows (in thousands):'
    blocks = [{'kind': 'text', 'text': intro},
              {'kind': 'table', 'text': 'Cash 0', 'rows': [[{'text': 'Cash'}, {'text': '0'}]]}]
    parsed = {'raw_sha256': 'a'*64, 'status': 'parsed', 'output': {'blocks': blocks}}
    table = next(u for u in module.build_units(parsed, sample) if u['kind'] == 'table')
    assert intro in table['context']
    assert table['derived_references'][0]['context_omission'] is None
    blocks[0]['text'] = intro * 10
    table = next(u for u in module.build_units(parsed, sample) if u['kind'] == 'table')
    assert table['derived_references'][0]['context_omission']['block'] == 0
    assert not table['context']
